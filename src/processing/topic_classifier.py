"""
Topic-based classification using keyword matching and embedding similarity.
Enhanced with spaCy NLP for better keyword matching (lemmatization, phrase matching).
"""

# Standard library imports
import json
import os
import sys
import threading
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

# Optional Aho-Corasick matcher for O(n) topic matching
try:
    from .topic_matcher_aho import TopicMatcherAho
    _AHO_AVAILABLE = True
except ImportError:
    TopicMatcherAho = None
    _AHO_AVAILABLE = False

# Module-level setup - use services.analysis_worker logger so logs appear together
logger = get_logger('services.analysis_worker')

# DISABLED: spaCy causes severe performance issues with 139 topics and many keywords
# Each nlp() call takes 10+ seconds, making topic classification take hours per record
# To re-enable in the future, set ENABLE_SPACY=1 (opt-in instead of opt-out)
SPACY_ENABLED_BY_ENV = os.environ.get('ENABLE_SPACY', '').lower() in ('1', 'true', 'yes')
if SPACY_ENABLED_BY_ENV:
    try:
        import spacy
        from spacy.matcher import Matcher
        SPACY_AVAILABLE = True
        logger.info("spaCy ENABLED via ENABLE_SPACY environment variable")
    except ImportError:
        SPACY_AVAILABLE = False
        logger.warning("spaCy not available - using basic keyword matching")
    except Exception as e:
        SPACY_AVAILABLE = False
        logger.warning(f"spaCy import failed: {e} - using basic keyword matching")
else:
    SPACY_AVAILABLE = False
    logger.info("spaCy disabled (default) - using fast basic keyword matching. Set ENABLE_SPACY=1 to enable.")


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
                 max_topics: int = 5,
                 use_spacy: Optional[bool] = None):
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
            use_spacy: If False, never load spaCy (fast, for backfill/workers). If True, use if available.
                      If None, use module default (ENABLE_SPACY env).
        """
        import time as _t
        _t0 = _t.time()
        logger.info(f"TopicClassifier.__init__: start (use_spacy={use_spacy})")
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
        logger.info(f"TopicClassifier.__init__: config/thresholds done ({_t.time() - _t0:.1f}s)")
        self.max_topics = max_topics
        self.db = db_session
        
        # Set embeddings path using PathManager
        if topic_embeddings_path is None:
            path_manager = PathManager()
            topic_embeddings_path = str(path_manager.config_topic_embeddings)
            path_manager = PathManager()
            topic_embeddings_path = str(path_manager.config_topic_embeddings)
        self.topic_embeddings_path = topic_embeddings_path
        logger.info(f"TopicClassifier.__init__: embeddings path set ({_t.time() - _t0:.1f}s)")
        
        # Load master topics from database
        logger.info("TopicClassifier.__init__: loading topics from DB...")
        self.master_topics = self._load_topics_from_database()
        logger.info(f"TopicClassifier.__init__: loaded {len(self.master_topics)} topics from DB ({_t.time() - _t0:.1f}s)")
        
        # Load topic embeddings
        logger.info("TopicClassifier.__init__: loading topic embeddings from file...")
        self.topic_embeddings = self._load_topic_embeddings()
        logger.info(f"TopicClassifier.__init__: loaded {len(self.topic_embeddings)} embeddings ({_t.time() - _t0:.1f}s)")
        
        # Initialize spaCy for enhanced NLP matching (Week 2 Enhancement)
        # use_spacy=False forces fast path (no spaCy load); same as analysis worker / backfill.
        self.nlp = None
        self.use_spacy = False
        if use_spacy is False:
            # Explicitly disabled (e.g. backfill, batch) - never load spaCy, use basic keyword matching
            logger.info(f"TopicClassifier.__init__: spaCy disabled by caller ({_t.time() - _t0:.1f}s)")
        elif SPACY_AVAILABLE and (use_spacy is True or use_spacy is None):
            try:
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                    self.use_spacy = True
                    logger.info("spaCy NLP model loaded - using enhanced keyword matching")
                except OSError:
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
        
        # spaCy is not thread-safe; serialize classify() when multiple workers share this instance
        self._classify_lock = threading.Lock() if self.use_spacy else None

        # Aho-Corasick matcher for O(n) topic matching (fallback to loop if unavailable)
        self._aho_matcher = None
        if _AHO_AVAILABLE and TopicMatcherAho and self.master_topics:
            try:
                self._aho_matcher = TopicMatcherAho(self.master_topics)
                logger.info("TopicClassifier.__init__: Aho-Corasick matcher enabled")
            except Exception as e:
                logger.warning(f"TopicClassifier.__init__: Aho-Corasick matcher failed, using fallback: {e}")
                self._aho_matcher = None

        logger.info(
            f"TopicClassifier.__init__: done in {_t.time() - _t0:.1f}s — {len(self.master_topics)} topics, "
            f"{len(self.topic_embeddings)} embeddings"
            f"{', spaCy on' if self.use_spacy else ''}"
            f"{', AC matcher on' if self._aho_matcher else ''}"
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
        logger.info("TopicClassifier._load_topics_from_database: getting DB session...")
        session = self._get_db_session()
        try:
            logger.info("TopicClassifier._load_topics_from_database: querying Topic table...")
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
            
            logger.info(f"TopicClassifier._load_topics_from_database: got {len(topics_dict)} topics")
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
            logger.info(f"TopicClassifier._load_topic_embeddings: reading {embeddings_file}...")
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
                logger.info(f"TopicClassifier._load_topic_embeddings: loaded {len(result)} embeddings")
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
            logger.debug("TopicClassifier.classify: Empty text, returning []")
            return []
        
        # spaCy nlp() is not thread-safe; serialize when multiple analysis workers share this classifier
        lock = getattr(self, '_classify_lock', None)
        logger.info(f"TopicClassifier.classify: Entering (lock={lock is not None}, use_spacy={getattr(self, 'use_spacy', False)})")
        if lock:
            logger.info("TopicClassifier.classify: Waiting to acquire lock...")
            lock.acquire()
            logger.info("TopicClassifier.classify: Lock acquired")
        try:
            # If no embedding provided, use keyword-only classification (also uses spaCy for keywords)
            if not text_embedding or len(text_embedding) != 1536:
                logger.info("TopicClassifier.classify: Invalid/missing embedding, using keyword-only")
                result = self._classify_keyword_only(text)
                logger.info(f"TopicClassifier.classify: keyword-only returned {len(result)} topics")
                return result
            logger.info("TopicClassifier.classify: Calling _classify_impl with embedding")
            result = self._classify_impl(text, text_embedding)
            logger.info(f"TopicClassifier.classify: _classify_impl returned {len(result)} topics")
            return result
        except Exception as e:
            logger.error(f"TopicClassifier.classify: Exception in classify: {e}", exc_info=True)
            raise
        finally:
            # Log spaCy call count if any
            spacy_calls = getattr(self, '_spacy_call_count', 0)
            if spacy_calls > 0:
                logger.info(f"TopicClassifier.classify: Total spaCy calls this classify: {spacy_calls}")
                self._spacy_call_count = 0  # Reset for next call
            if lock:
                logger.info("TopicClassifier.classify: Releasing lock")
                lock.release()
    
    def _classify_impl(self, text: str, text_embedding: Optional[List[float]] = None) -> List[Dict[str, Any]]:
        """Internal classify implementation (called with lock held when spaCy is enabled)."""
        if getattr(self, '_aho_matcher', None):
            return self._aho_matcher.match(text, topic_keys_filter=None, max_topics=self.max_topics)
        import time as _time
        start_time = _time.time()
        num_topics = len(self.master_topics)
        logger.info(f"TopicClassifier._classify_impl: STARTED ({num_topics} topics to check)")
        text_embedding_array = np.array(text_embedding, dtype=np.float64)
        text_lower = text.lower()
        logger.info(f"TopicClassifier._classify_impl: text prepared (len={len(text_lower)})")
        
        topic_scores = []
        topics_checked = 0
        
        for topic_key, topic_data in self.master_topics.items():
            topics_checked += 1
            # Log progress every 10 topics
            if topics_checked % 10 == 0:
                elapsed = _time.time() - start_time
                logger.info(f"TopicClassifier._classify_impl: checked {topics_checked}/{num_topics} topics ({elapsed:.1f}s elapsed)")
            
            # Keyword matching: comma=OR, space=AND (embedding disabled for simplicity)
            keyword_groups = topic_data.get('keyword_groups')
            keywords = topic_data.get('keywords', [])
            keyword_score = self._keyword_match(
                text_lower,
                keywords=keywords if not keyword_groups else None,
                keyword_groups=keyword_groups
            )

            if keyword_score == 0.0:
                continue

            embedding_score = 0.0  # Embedding similarity disabled
            combined_score = keyword_score

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
        result = topic_scores[:self.max_topics]
        elapsed = _time.time() - start_time
        logger.info(f"TopicClassifier._classify_impl: DONE ({num_topics} topics -> {len(result)} results in {elapsed:.2f}s)")
        return result

    def classify_for_topic_keys(
        self,
        text: str,
        text_embedding: Optional[List[float]] = None,
        topic_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Classify text only for the given topic keys (e.g. new topics for backfill).
        Uses the same keyword + embedding scoring as classify() but only iterates
        over the specified topics. Returns matches that pass the threshold.

        Args:
            text: Text content to classify.
            text_embedding: Pre-computed embedding (1536 dims) or None for keyword-only.
            topic_keys: List of topic_key to score against. Only these are checked.

        Returns:
            List of topic dicts (topic, topic_name, confidence, keyword_score, embedding_score).
        """
        if not text or not text.strip():
            return []
        if not topic_keys:
            return []

        # Restrict to topics we have data for
        keys_to_check = [
            k for k in topic_keys
            if k in self.master_topics
        ]
        if not keys_to_check:
            return []

        if getattr(self, '_aho_matcher', None):
            return self._aho_matcher.match(text, topic_keys_filter=keys_to_check, max_topics=999999)

        text_lower = text.lower()
        text_embedding_array = None
        if text_embedding and len(text_embedding) == 1536:
            text_embedding_array = np.array(text_embedding, dtype=np.float64)

        topic_scores = []
        for topic_key in keys_to_check:
            topic_data = self.master_topics[topic_key]
            keyword_groups = topic_data.get('keyword_groups')
            keywords = topic_data.get('keywords', [])
            keyword_score = self._keyword_match(
                text_lower,
                keywords=keywords if not keyword_groups else None,
                keyword_groups=keyword_groups,
            )

            if keyword_score == 0.0:
                continue

            embedding_score = 0.0  # Embedding disabled
            combined_score = keyword_score

            if combined_score >= self.min_score_threshold:
                topic_scores.append({
                    "topic": topic_key,
                    "topic_name": topic_data.get('name', topic_key),
                    "confidence": round(combined_score, 3),
                    "keyword_score": round(keyword_score, 3),
                    "embedding_score": round(embedding_score, 3),
                })
        return topic_scores

    def _keyword_match(self, text_lower: str, keywords: Optional[List[str]] = None, keyword_groups: Optional[Dict[Any, Any]] = None) -> float:
        """
        Calculate keyword matching score using simple AND/OR logic.
        
        Logic: comma = OR, space = AND.
        - "fuel nigeria, price iran" → (fuel AND nigeria) OR (price AND iran)
        - Array elements are OR'd: ["fuel nigeria", "petrol"] → (fuel AND nigeria) OR (petrol)
        
        Args:
            text_lower: Lowercase text to search
            keywords: List of keyword strings (supports comma/space syntax)
            keyword_groups: JSONB structure — converted to same logic for consistency
        
        Returns:
            1.0 if any phrase matches, 0.0 otherwise.
        """
        if keyword_groups:
            return self._match_keyword_groups_simple(text_lower, keyword_groups)
        elif keywords:
            return self._match_simple_and_or_keywords(text_lower, keywords)
        else:
            return 0.0

    def _match_simple_and_or_keywords(self, text_lower: str, keywords: List[str]) -> float:
        """
        Match using comma=OR, space=AND logic.
        
        Each keyword string: "fuel nigeria, price iran" = (fuel AND nigeria) OR (price AND iran)
        Array elements are OR'd together.
        
        Returns:
            1.0 if any phrase matches, 0.0 otherwise.
        """
        if not keywords:
            return 0.0

        def _phrase_matches(terms: List[str]) -> bool:
            if not terms:
                return False
            return all(term.strip().lower() in text_lower for term in terms if term.strip())

        for kw in keywords:
            if not kw or not isinstance(kw, str):
                continue
            # Comma = OR: split into alternative phrase groups
            or_branches = [p.strip() for p in str(kw).split(",") if p.strip()]
            for phrase in or_branches:
                # Space = AND: all terms in phrase must appear
                terms = [t.strip() for t in phrase.split() if t.strip()]
                if _phrase_matches(terms):
                    return 1.0
        return 0.0

    def _match_keyword_groups_simple(self, text_lower: str, keyword_groups: Dict) -> float:
        """
        Convert keyword_groups to (AND phrase) OR (AND phrase) and match.
        "and" group [a,b] → phrase "a b". "or" group [a,b] → phrases "a", "b".
        require_all_groups: need at least one phrase match from each group.
        """
        if not keyword_groups or "groups" not in keyword_groups:
            return 0.0

        groups = keyword_groups["groups"]
        require_all_groups = keyword_groups.get("require_all_groups", False)

        def _phrase_matches(terms: List[str]) -> bool:
            if not terms:
                return False
            return all(term.strip().lower() in text_lower for term in terms if term.strip())

        group_phrases = []  # list of list of (list of terms)
        for group in groups:
            group_type = (group.get("type") or "or").lower()
            kws = group.get("keywords") or []
            if not kws:
                continue
            if group_type == "and":
                group_phrases.append([[t.strip().lower() for t in kws if t and str(t).strip()]])
            else:
                group_phrases.append([[str(t).strip().lower()] for t in kws if t and str(t).strip()])

        if not group_phrases:
            return 0.0

        if require_all_groups:
            for phrase_set in group_phrases:
                if not phrase_set:
                    return 0.0
                if not any(_phrase_matches(terms) for terms in phrase_set):
                    return 0.0
            return 1.0
        else:
            for phrase_set in group_phrases:
                if any(_phrase_matches(terms) for terms in phrase_set):
                    return 1.0
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
        
        # Track call count for debugging (increment counter)
        if not hasattr(self, '_spacy_call_count'):
            self._spacy_call_count = 0
        self._spacy_call_count += 1
        # Log every 50 calls to avoid flooding
        if self._spacy_call_count % 50 == 1:
            logger.info(f"_spacy_keyword_match: call #{self._spacy_call_count} (keyword='{keyword[:30]}...' if long)")
        
        try:
            # Process text and keyword with spaCy (this is the slow part!)
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
        if getattr(self, '_aho_matcher', None):
            return self._aho_matcher.match(text, topic_keys_filter=None, max_topics=self.max_topics)
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
    

