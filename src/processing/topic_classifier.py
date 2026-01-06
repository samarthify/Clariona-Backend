"""
Topic-based classification using keyword matching and embedding similarity.
Enhanced with spaCy NLP for better keyword matching (lemmatization, phrase matching).
"""

# Standard library imports
import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union, Any

# Third-party imports
import numpy as np
from sqlalchemy.orm import Session

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_manager import ConfigManager
from src.config.path_manager import PathManager
from src.config.logging_config import get_logger

# Local imports - database
from api.database import SessionLocal
from api.models import Topic, OwnerConfig

# Local imports - utils
from utils.similarity import cosine_similarity

# Module-level setup
logger = get_logger('TopicClassifier')

# Try to import spaCy for enhanced NLP matching
try:
    import spacy
    from spacy.matcher import Matcher
    SPACY_AVAILABLE = True
    logger.debug("spaCy available for enhanced NLP matching")
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not available - using basic keyword matching. Install with: pip install spacy && python -m spacy download en_core_web_sm")
except Exception as e:
    SPACY_AVAILABLE = False
    logger.warning(f"spaCy import failed: {e} - using basic keyword matching")


class TopicClassifier:
    """
    Classifies mentions into multiple topics using keyword matching and embeddings.
    """
    
    def __init__(self, 
                 db_session: Optional[Session] = None,
                 topic_embeddings_path: Optional[str] = None,
                 keyword_weight: float = 0.4,
                 embedding_weight: float = 0.6,
                 min_score_threshold: Optional[float] = None,
                 max_topics: int = 5):
        """
        Initialize topic classifier.
        
        Args:
            db_session: Optional database session. If None, creates sessions as needed.
            topic_embeddings_path: Path to pre-computed topic embeddings JSON file.
                                  If None, uses default: "config/topic_embeddings.json"
            keyword_weight: Weight for keyword matching (0.0-1.0)
            embedding_weight: Weight for embedding similarity (0.0-1.0)
            min_score_threshold: Minimum combined score to include topic. If None, loads from config.
            max_topics: Maximum number of topics to return
        """
        # Validate weights
        if abs(keyword_weight + embedding_weight - 1.0) > 0.01:
            logger.warning(f"Weights don't sum to 1.0: {keyword_weight} + {embedding_weight} = {keyword_weight + embedding_weight}")
        
        self.keyword_weight = keyword_weight
        self.embedding_weight = embedding_weight
        
        # Load thresholds from ConfigManager if not provided
        if min_score_threshold is None:
            try:
                config = ConfigManager()
                self.min_score_threshold = config.get_float("processing.topic.min_score_threshold", 0.2)
                self.keyword_score_threshold = config.get_float("processing.topic.keyword_score_threshold", 0.3)
                self.embedding_score_threshold = config.get_float("processing.topic.embedding_score_threshold", 0.5)
                self.confidence_threshold = config.get_float("processing.topic.confidence_threshold", 0.85)
            except Exception as e:
                logger.warning(f"Could not load ConfigManager for topic thresholds, using defaults: {e}")
                self.min_score_threshold = 0.2
                self.keyword_score_threshold = 0.3
                self.embedding_score_threshold = 0.5
                self.confidence_threshold = 0.85
        else:
            self.min_score_threshold = min_score_threshold
            # Still load other thresholds from config
            try:
                config = ConfigManager()
                self.keyword_score_threshold = config.get_float("processing.topic.keyword_score_threshold", 0.3)
                self.embedding_score_threshold = config.get_float("processing.topic.embedding_score_threshold", 0.5)
                self.confidence_threshold = config.get_float("processing.topic.confidence_threshold", 0.85)
            except Exception:
                self.keyword_score_threshold = 0.3
                self.embedding_score_threshold = 0.5
                self.confidence_threshold = 0.85
        
        self.max_topics = max_topics
        self.db = db_session
        
        # Set embeddings path using PathManager
        if topic_embeddings_path is None:
            path_manager = PathManager()
            topic_embeddings_path = str(path_manager.config_topic_embeddings)
            path_manager = PathManager()
            topic_embeddings_path = str(path_manager.config_topic_embeddings)
        self.topic_embeddings_path = topic_embeddings_path
        
        # Load master topics from database
        self.master_topics = self._load_topics_from_database()
        
        # Load topic embeddings
        self.topic_embeddings = self._load_topic_embeddings()
        
        # Initialize spaCy for enhanced NLP matching (Week 2 Enhancement)
        self.nlp = None
        self.use_spacy = False
        if SPACY_AVAILABLE:
            try:
                # Try to load English model (prefer small for speed)
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                    self.use_spacy = True
                    logger.info("spaCy NLP model loaded - using enhanced keyword matching")
                except OSError:
                    # Model not installed, try medium or large
                    try:
                        self.nlp = spacy.load("en_core_web_md")
                        self.use_spacy = True
                        logger.info("spaCy NLP model (medium) loaded - using enhanced keyword matching")
                    except OSError:
                        logger.warning("spaCy models not found. Install with: python -m spacy download en_core_web_sm")
                        self.use_spacy = False
            except Exception as e:
                logger.warning(f"Failed to load spaCy model: {e} - using basic keyword matching")
                self.use_spacy = False
        
        logger.info(
            f"TopicClassifier initialized with {len(self.master_topics)} topics, "
            f"{len(self.topic_embeddings)} embeddings loaded"
            f"{', spaCy enabled' if self.use_spacy else ''}"
        )
    
    def _get_db_session(self) -> Session:  # type: ignore[no-any-return]
        """Get database session (create new if not provided)."""
        if self.db:
            return self.db
        return SessionLocal()
    
    def _close_db_session(self, session: Session):
        """Close database session if we created it."""
        if not self.db and session:
            session.close()
    
    def _load_topics_from_database(self) -> Dict[str, Dict]:
        """Load all active topics from the database."""
        session = self._get_db_session()
        try:
            topics = session.query(Topic).filter(Topic.is_active == True).all()
            
            topics_dict = {}
            for topic in topics:
                # Convert keywords array to list if needed
                keywords = topic.keywords
                if keywords is None:
                    keywords = []
                elif isinstance(keywords, str):
                    try:
                        keywords = json.loads(keywords)
                    except:
                        keywords = []
                
                # Load keyword_groups if available
                keyword_groups = None
                if topic.keyword_groups:
                    if isinstance(topic.keyword_groups, dict):
                        keyword_groups = topic.keyword_groups
                    elif isinstance(topic.keyword_groups, str):
                        try:
                            keyword_groups = json.loads(topic.keyword_groups)
                        except:
                            keyword_groups = None
                
                topics_dict[topic.topic_key] = {
                    "name": topic.topic_name,
                    "description": topic.description or "",
                    "keywords": keywords if isinstance(keywords, list) else list(keywords) if keywords else [],
                    "keyword_groups": keyword_groups,  # Add keyword_groups
                    "category": topic.category
                }
            
            logger.debug(f"Loaded {len(topics_dict)} topics from database")
            return topics_dict
        
        except Exception as e:
            logger.error(f"Error loading topics from database: {e}")
            logger.info("Falling back to loading topics from JSON file...")
            return self._load_topics_from_json_fallback()
        
        finally:
            self._close_db_session(session)
    
    def _load_topics_from_json_fallback(self) -> Dict[str, Dict]:
        """Fallback: Load topics from master_topics.json if database fails."""
        try:
            path_manager = PathManager()
            topics_file = path_manager.get_config_file('master_topics.json')
            
            if not topics_file.exists():
                logger.warning(f"Topics JSON file not found: {topics_file}")
                return {}
            
            with open(topics_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                topics_dict = data.get('topics', {})
                
                # Convert to same format as database
                result = {}
                for topic_key, topic_data in topics_dict.items():
                    result[topic_key] = {
                        "name": topic_data.get('name', topic_key),
                        "description": topic_data.get('description', ''),
                        "keywords": topic_data.get('keywords', []),
                        "keyword_groups": topic_data.get('keyword_groups'),  # Add keyword_groups support
                        "category": topic_data.get('category')
                    }
                
                logger.info(f"Loaded {len(result)} topics from JSON fallback")
                return result
        
        except Exception as e:
            logger.error(f"Error loading topics from JSON fallback: {e}")
            return {}
    
    def _load_topic_embeddings(self) -> Dict[str, np.ndarray]:
        """Load pre-computed topic embeddings from JSON file."""
        try:
            embeddings_file = Path(self.topic_embeddings_path)
            
            if not embeddings_file.exists():
                logger.warning(f"Topic embeddings file not found: {self.topic_embeddings_path}")
                logger.info("Run topic_embedding_generator.py to generate embeddings")
                return {}
            
            with open(embeddings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                embeddings_dict = data.get('embeddings', {})
                
                # Convert lists to numpy arrays
                result = {}
                for topic_key, embedding in embeddings_dict.items():
                    if isinstance(embedding, list) and len(embedding) > 0:
                        result[topic_key] = np.array(embedding, dtype=np.float64)
                
                logger.debug(f"Loaded {len(result)} topic embeddings from file")
                return result
        
        except Exception as e:
            logger.error(f"Error loading topic embeddings: {e}")
            return {}
    
    def classify(self, text: str, text_embedding: Optional[List[float]] = None) -> List[Dict[str, Any]]:
        """
        Classify text into multiple topics.
        
        Args:
            text: Text content to classify
            text_embedding: Pre-computed embedding vector (1536 dimensions).
                          If None, uses keyword-only classification.
        
        Returns:
            List of topic classifications sorted by confidence:
            [
                {
                    "topic": "fuel_pricing",
                    "topic_name": "Fuel Pricing",
                    "confidence": 0.85,
                    "keyword_score": 0.7,
                    "embedding_score": 0.9
                },
                ...
            ]
        """
        if not text or not text.strip():
            return []
        
        # If no embedding provided, use keyword-only classification
        if not text_embedding or len(text_embedding) != 1536:
            logger.debug("Invalid or missing embedding provided, using keyword-only classification")
            return self._classify_keyword_only(text)
        
        text_embedding_array = np.array(text_embedding, dtype=np.float64)
        text_lower = text.lower()
        
        topic_scores = []
        
        for topic_key, topic_data in self.master_topics.items():
            # Keyword matching with AND/OR support
            keyword_groups = topic_data.get('keyword_groups')
            keywords = topic_data.get('keywords', [])
            keyword_score = self._keyword_match(
                text_lower,
                keywords=keywords if not keyword_groups else None,
                keyword_groups=keyword_groups
            )
            
            # Embedding similarity
            embedding_score = 0.0
            if topic_key in self.topic_embeddings:
                topic_emb = self.topic_embeddings[topic_key]
                similarity = cosine_similarity(text_embedding_array, topic_emb)
                # Normalize similarity to 0-1 range (cosine similarity is typically -1 to 1)
                embedding_score = max(0.0, float(similarity))
            else:
                logger.debug(f"No embedding found for topic: {topic_key}")
            
            # Combined score with improved precision
            # Require at least some keyword OR embedding match
            if keyword_score == 0.0 and embedding_score < 0.25:
                continue  # Skip if no keywords and very low embedding
            
            combined_score = (
                self.keyword_weight * keyword_score +
                self.embedding_weight * embedding_score
            )
            
            # Boost if both keyword and embedding agree (stronger signal)
            if keyword_score > 0.15 and embedding_score > 0.25:
                combined_score = min(combined_score * 1.15, 1.0)
            
            # Additional boost for high confidence matches
            if keyword_score > self.keyword_score_threshold or embedding_score > self.embedding_score_threshold:
                combined_score = min(combined_score * 1.05, 1.0)
            
            if combined_score >= self.min_score_threshold:
                topic_scores.append({
                    "topic": topic_key,
                    "topic_name": topic_data.get('name', topic_key),
                    "confidence": round(combined_score, 3),
                    "keyword_score": round(keyword_score, 3),
                    "embedding_score": round(embedding_score, 3)
                })
        
        # Sort by confidence and return top N
        topic_scores.sort(key=lambda x: x['confidence'], reverse=True)
        return topic_scores[:self.max_topics]
    
    def _keyword_match(self, text_lower: str, keywords: Optional[List[str]] = None, keyword_groups: Optional[Dict[Any, Any]] = None) -> float:
        """
        Calculate keyword matching score with AND/OR logic support.
        
        Args:
            text_lower: Lowercase text to search
            keywords: Simple keyword list (backward compatibility)
            keyword_groups: JSONB structure with AND/OR groups
        
        Returns:
            Normalized score (0.0-1.0) based on keyword matches.
        """
        # Use keyword_groups if available, otherwise fall back to keywords
        if keyword_groups:
            return self._match_keyword_groups(text_lower, keyword_groups)
        elif keywords:
            return self._match_simple_keywords(text_lower, keywords)
        else:
            return 0.0
    
    def _match_simple_keywords(self, text_lower: str, keywords: List[str]) -> float:
        """
        Original simple OR matching (backward compatibility).
        
        Args:
            text_lower: Lowercase text to search
            keywords: List of keywords to match (OR logic)
        
        Returns:
            Normalized score (0.0-1.0) based on keyword matches.
        """
        if not keywords:
            return 0.0
        
        # Count keyword matches (exact word boundaries for better precision)
        matches = 0
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # Check for word boundary matches (more precise)
            if keyword_lower in text_lower:
                # Boost if it's a whole word match
                if f" {keyword_lower} " in f" {text_lower} " or text_lower.startswith(keyword_lower + " ") or text_lower.endswith(" " + keyword_lower):
                    matches += 1.2  # Boost for whole word matches
                else:
                    matches += 1.0
        
        if matches == 0:
            return 0.0
        
        # Base score: proportion of keywords matched (capped at 1.0)
        base_score = min(matches / len(keywords), 1.0)
        
        # Boost score if multiple matches (logarithmic scaling)
        if matches > 1:
            boost = 1 + (np.log(matches + 1) / 8)  # Slightly stronger boost
            base_score = min(base_score * boost, 1.0)
        
        return min(base_score, 1.0)
    
    def _match_keyword_groups(self, text_lower: str, keyword_groups: Dict) -> float:
        """
        Match keywords using AND/OR group logic.
        
        Structure:
        {
            "groups": [
                {"type": "or", "keywords": ["fuel", "petrol"]},
                {"type": "and", "keywords": ["price", "increase"]}
            ],
            "require_all_groups": false  // true = AND between groups, false = OR between groups
        }
        
        Args:
            text_lower: Lowercase text to search
            keyword_groups: Dictionary with groups and logic
        
        Returns:
            Normalized score (0.0-1.0) based on keyword matches.
        """
        if not keyword_groups or 'groups' not in keyword_groups:
            return 0.0
        
        groups = keyword_groups['groups']
        require_all_groups = keyword_groups.get('require_all_groups', False)
        
        if not groups:
            return 0.0
        
        group_results = []
        
        for group in groups:
            group_type = group.get('type', 'or').lower()
            group_keywords = group.get('keywords', [])
            
            if not group_keywords:
                continue
            
            if group_type == 'or':
                # OR group: any keyword matches
                group_matches = sum(
                    1 for keyword in group_keywords
                    if self._keyword_in_text(text_lower, keyword.lower())
                )
                group_score = min(group_matches / len(group_keywords), 1.0) if group_matches > 0 else 0.0
                group_results.append({
                    'matched': group_matches > 0,
                    'score': group_score,
                    'match_count': group_matches,
                    'total': len(group_keywords)
                })
            
            elif group_type == 'and':
                # AND group: all keywords must match
                group_matches = sum(
                    1 for keyword in group_keywords
                    if self._keyword_in_text(text_lower, keyword.lower())
                )
                group_score = 1.0 if group_matches == len(group_keywords) else 0.0
                group_results.append({
                    'matched': group_matches == len(group_keywords),
                    'score': group_score,
                    'match_count': group_matches,
                    'total': len(group_keywords)
                })
        
        if not group_results:
            return 0.0
        
        # Combine group results
        if require_all_groups:
            # All groups must match (AND between groups)
            all_matched = all(g['matched'] for g in group_results)
            if not all_matched:
                return 0.0
            # Average score of all groups
            return sum(g['score'] for g in group_results) / len(group_results)
        else:
            # Any group matches (OR between groups)
            matched_groups = [g for g in group_results if g['matched']]
            if not matched_groups:
                return 0.0
            # Use best matching group score
            return max(g['score'] for g in matched_groups)
    
    def _keyword_in_text(self, text_lower: str, keyword_lower: str) -> bool:
        """
        Check if keyword exists in text (with word boundary detection).
        Uses spaCy for enhanced matching if available (lemmatization, phrase matching).
        
        Args:
            text_lower: Lowercase text to search
            keyword_lower: Lowercase keyword to find
        
        Returns:
            True if keyword found in text, False otherwise.
        """
        # Week 2 Enhancement: Use spaCy for better matching
        if self.use_spacy and self.nlp:
            return self._spacy_keyword_match(text_lower, keyword_lower)
        
        # Fallback to basic string matching
        if keyword_lower in text_lower:
            # Check for whole word match (preferred)
            if (f" {keyword_lower} " in f" {text_lower} " or 
                text_lower.startswith(keyword_lower + " ") or 
                text_lower.endswith(" " + keyword_lower)):
                return True
            return True  # Partial match also counts
        return False
    
    def _spacy_keyword_match(self, text: str, keyword: str) -> bool:
        """
        Enhanced keyword matching using spaCy NLP (Week 2 Enhancement).
        
        Benefits:
        - Lemmatization: "fuels", "fueling", "fueled" all match "fuel"
        - Phrase matching: Better handling of multi-word keywords
        - Token-based matching: More accurate than string matching
        
        Args:
            text: Text to search (can be lowercase or mixed case)
            keyword: Keyword to find (can be lowercase or mixed case)
        
        Returns:
            True if keyword found, False otherwise.
        """
        if not self.nlp:
            return False
        
        try:
            # Process text and keyword with spaCy
            doc = self.nlp(text)
            keyword_doc = self.nlp(keyword)
            
            # Get lemmatized forms (exclude stop words and punctuation)
            text_lemmas = [token.lemma_.lower() for token in doc if not token.is_stop and not token.is_punct]
            keyword_lemmas = [token.lemma_.lower() for token in keyword_doc if not token.is_stop and not token.is_punct]
            
            # Single word keyword: check if lemma matches
            if len(keyword_lemmas) == 1:
                keyword_lemma = keyword_lemmas[0]
                if keyword_lemma in text_lemmas:
                    return True
                # Also check original keyword (for exact matches)
                keyword_lower = keyword.lower()
                text_lower = text.lower()
                if keyword_lower in text_lower:
                    return True
            
            # Multi-word keyword: check if all lemmas appear in order
            elif len(keyword_lemmas) > 1:
                # Check if all keyword lemmas appear in text lemmas
                if all(lemma in text_lemmas for lemma in keyword_lemmas):
                    # Check if they appear in order (approximate)
                    text_tokens = [token.lemma_.lower() for token in doc]
                    keyword_tokens = keyword_lemmas
                    
                    # Find positions of keyword tokens in text
                    positions = []
                    for kw_token in keyword_tokens:
                        if kw_token in text_tokens:
                            positions.append(text_tokens.index(kw_token))
                    
                    # If all tokens found and in order (allow small gaps)
                    if len(positions) == len(keyword_tokens):
                        # Check if positions are roughly in order
                        if positions == sorted(positions):
                            return True
                        # Allow small gaps (within 3 tokens)
                        if max(positions) - min(positions) <= len(keyword_tokens) + 2:
                            return True
                
                # Fallback: check original string match
                keyword_lower = keyword.lower()
                text_lower = text.lower()
                if keyword_lower in text_lower:
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"spaCy keyword matching failed for '{keyword}': {e}, falling back to basic matching")
            # Fallback to basic string matching
            keyword_lower = keyword.lower()
            text_lower = text.lower()
            return keyword_lower in text_lower
    
    def _classify_keyword_only(self, text: str) -> List[Dict[str, Any]]:
        """Fallback classification using only keywords."""
        text_lower = text.lower()
        topic_scores = []
        
        for topic_key, topic_data in self.master_topics.items():
            # Keyword matching with AND/OR support
            keyword_groups = topic_data.get('keyword_groups')
            keywords = topic_data.get('keywords', [])
            keyword_score = self._keyword_match(
                text_lower,
                keywords=keywords if not keyword_groups else None,
                keyword_groups=keyword_groups
            )
            
            if keyword_score >= self.min_score_threshold:
                topic_scores.append({
                    "topic": topic_key,
                    "topic_name": topic_data.get('name', topic_key),
                    "confidence": round(keyword_score, 3),
                    "keyword_score": round(keyword_score, 3),
                    "embedding_score": 0.0
                })
        
        topic_scores.sort(key=lambda x: x['confidence'], reverse=True)
        return topic_scores[:self.max_topics]
    
    def get_topics_for_owner(self, owner_key: str) -> List[str]:  # type: ignore[no-any-return]
        """
        Get list of topics for a specific owner (president/minister) from database.
        
        Args:
            owner_key: Owner identifier (e.g., 'president', 'petroleum_resources')
        
        Returns:
            List of topic keys
        """
        session = self._get_db_session()
        try:
            owner_config = session.query(OwnerConfig).filter(
                OwnerConfig.owner_key == owner_key,
                OwnerConfig.is_active == True
            ).first()
            
            if owner_config and owner_config.topics:
                # Convert array to list if needed
                topics = owner_config.topics
                if isinstance(topics, str):
                    try:
                        topics = json.loads(topics)
                    except:
                        topics = []
                elif not isinstance(topics, list):
                    topics = list(topics) if topics else []
                
                return topics
            
            logger.warning(f"No active config found for owner: {owner_key}")
            return []
        
        except Exception as e:
            logger.error(f"Error loading owner config for {owner_key}: {e}")
            return []
        
        finally:
            self._close_db_session(session)
    
    def filter_topics_for_owner(self, classifications: List[Dict], owner_key: str) -> List[Dict]:
        """
        Filter topic classifications to only include topics relevant to an owner.
        
        Args:
            classifications: List of topic classifications from classify()
            owner_key: Owner identifier
        
        Returns:
            Filtered list of classifications
        """
        owner_topics = set(self.get_topics_for_owner(owner_key))
        
        if not owner_topics:
            logger.debug(f"No topics configured for owner: {owner_key}, returning all classifications")
            return classifications
        
        filtered = [
            cls for cls in classifications
            if cls.get('topic') in owner_topics
        ]
        
        return filtered
    

