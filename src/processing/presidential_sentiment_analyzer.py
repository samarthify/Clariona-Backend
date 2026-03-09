# Standard library imports
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# Third-party imports
import openai
import requests
import pandas as pd
from dotenv import load_dotenv

# Local imports - config (first)
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config.logging_config import get_logger

# Local imports - exceptions
from exceptions import AnalysisError, RateLimitError, OpenAIError

# Local imports - utils
from utils.openai_rate_limiter import get_rate_limiter
from utils.multi_model_rate_limiter import get_multi_model_rate_limiter

# Module-level setup
logger = get_logger(__name__)

class PresidentialSentimentAnalyzer:
    """
    A sentiment analyzer that evaluates content from the President's strategic perspective.
    Instead of general positive/negative sentiment, it classifies content based on:
    - How it affects the President's agenda, image, or political capital
    - Whether it's supportive, threatening, requires attention, or is irrelevant
    
    Week 3: Enhanced with emotion detection and weighted sentiment calculation.
    """
    
    def __init__(self, president_name: str = "the President", country: str = "Nigeria", model: Optional[str] = None) -> None:
        self.president_name = president_name
        self.country = country
        
        # Load default model from ConfigManager if not provided
        if model is None:
            try:
                from config.config_manager import ConfigManager
                config = ConfigManager()
                model = config.get("models.llm_models.default", "gpt-5-nano")
            except Exception as e:
                logger.warning(f"Could not load ConfigManager for default model, using 'gpt-5-nano': {e}")
                model = "gpt-5-nano"
        
        self.model = model  # Model to use: gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano
        
        # Load environment variables from config/.env
        try:
            from src.config.path_manager import PathManager
            path_manager = PathManager()
            config_env_path = path_manager.config_dir / ".env"
        except Exception:
            config_env_path = Path(__file__).parent.parent.parent / "config" / ".env"
        
        if config_env_path.exists():
            load_dotenv(config_env_path)
            logger.debug(f"Loaded environment variables from {config_env_path}")
        else:
            logger.warning(f"Config .env file not found at {config_env_path}")
        
        # Weight calculator (emotion now from LLM, no separate EmotionAnalyzer)
        try:
            from processing.sentiment_weight_calculator import SentimentWeightCalculator
            self.weight_calculator = SentimentWeightCalculator()
            logger.debug("Sentiment weight calculator initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize weight calculator: {e}. Weights will use fallback.")
            self.weight_calculator = None
        
        # Presidential sentiment categories (using traditional labels with strategic reasoning)
        self.sentiment_categories = {
            "positive": "Strengthens presidential image, agenda, or political capital",
            "negative": "Threatens presidential image, credibility, or agenda", 
            "neutral": "No material impact on presidency or requires monitoring"
        }
        
        # Initialize OpenAI client
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY environment variable not set. Presidential analysis will not function.")
            self.openai_client = None
        else:
            try:
                self.openai_client = openai.OpenAI(api_key=self.openai_api_key)
                logger.debug(f"OpenAI client initialized successfully for presidential analysis (model: {model}).")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
                self.openai_client = None
        
        # Presidential priorities and keywords (can be updated dynamically)
        self.presidential_priorities = {
            "fuel_subsidy": ["fuel", "subsidy", "petrol", "diesel", "energy", "pump", "price"],
            "security": ["security", "terrorism", "banditry", "kidnapping", "police", "military", "defense"],
            "youth_employment": ["youth", "employment", "jobs", "unemployment", "skills", "training"],
            "foreign_relations": ["diplomacy", "foreign", "international", "trade", "partnership"],
            "infrastructure": ["roads", "bridges", "railways", "airports", "infrastructure", "development"],
            "economy": ["economy", "gdp", "inflation", "growth", "investment", "business"],
            "corruption": ["corruption", "transparency", "accountability", "anti-corruption"],
            "healthcare": ["health", "hospital", "medical", "vaccine", "disease", "healthcare"],
            "education": ["education", "school", "university", "students", "teachers", "learning"]
        }
        
        # Load sentiment thresholds and prompt variables from ConfigManager
        try:
            from config.config_manager import ConfigManager
            config = ConfigManager()
            self.positive_threshold = config.get_float("processing.sentiment.positive_threshold", 0.2)
            self.negative_threshold = config.get_float("processing.sentiment.negative_threshold", -0.2)
            # Load prompt variables (president_name and country can be overridden from config)
            config_president_name = config.get("processing.prompt_variables.president_name", None)
            config_country = config.get("processing.prompt_variables.country", None)
            if config_president_name:
                self.president_name = config_president_name
            if config_country:
                self.country = config_country
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for sentiment thresholds, using defaults: {e}")
            self.positive_threshold = 0.2
            self.negative_threshold = -0.2
        
        logger.debug(f"Presidential Sentiment Analyzer initialized for {self.president_name} of {self.country}")
    
    def _get_embedding_model(self) -> str:
        """Get embedding model name from ConfigManager."""
        try:
            from config.config_manager import ConfigManager
            config = ConfigManager()
            return config.get("models.embedding_model", "text-embedding-3-small")
        except Exception:
            return "text-embedding-3-small"

    def _get_negative_threshold(self) -> float:
        """Get negative sentiment threshold."""
        return self.negative_threshold

    _SENTIMENT_JSON_SCHEMA = {
        "type": "object",
        "properties": {
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "sentiment_score": {"type": "number"},
            "justification": {"type": "string"},
            "recommended_action": {"type": "string"},
            "emotion_distribution": {
                "type": "object",
                "properties": {
                    "anger": {"type": "number"}, "fear": {"type": "number"}, "trust": {"type": "number"},
                    "sadness": {"type": "number"}, "joy": {"type": "number"}, "disgust": {"type": "number"},
                },
                "additionalProperties": False,
            },
        },
        "required": ["sentiment", "sentiment_score", "justification", "recommended_action", "emotion_distribution"],
        "additionalProperties": False,
    }

    def _get_presidential_prompt(self, text: str) -> Tuple[str, str]:
        """
        Get system message and user prompt from config, with fallback to defaults.
        Returns: (system_message, user_prompt)
        """
        try:
            from config.config_manager import ConfigManager
            config = ConfigManager()
            
            # Get prompt templates from config
            prompt_config = config.get("processing.prompts.presidential_sentiment", {})
            system_message_template = prompt_config.get("system_message", "You advise {president_name} on media impact. Respond only with valid JSON, no markdown.")
            user_template = prompt_config.get("user_template", """Classify this text for {president_name}'s agenda impact. Return JSON only:

{"sentiment": "positive"|"negative"|"neutral", "sentiment_score": -1.0 to 1.0, "justification": "brief reason <=25 words", "recommended_action": "one-line strategic action for President", "emotion_distribution": {"anger": 0-1, "fear": 0-1, "trust": 0-1, "sadness": 0-1, "joy": 0-1, "disgust": 0-1}}

Text: "{text}"
""")
            text_truncate_length = prompt_config.get("text_truncate_length", 600)
            
            # Truncate text
            truncated_text = text[:text_truncate_length] if len(text) > text_truncate_length else text
            
            # Format templates with variables
            system_message = system_message_template.format(president_name=self.president_name)
            user_prompt = user_template.format(president_name=self.president_name, text=truncated_text)
            
            return system_message, user_prompt
        except Exception as e:
            logger.warning(f"Could not load prompt templates from ConfigManager, using defaults: {e}")
            # Fallback to hardcoded defaults
            truncated_text = text[:800] if len(text) > 800 else text
            system_message = f"You are a strategic advisor to {self.president_name} analyzing media impact. Respond only with valid JSON."
            user_prompt = f"""Analyze media from {self.president_name}'s perspective. Return JSON only:
{{"sentiment": "positive"|"negative"|"neutral", "sentiment_score": -1.0 to 1.0, "justification": "brief reason", "recommended_action": "one-line strategic action for President", "emotion_distribution": {{"anger": 0-1, "fear": 0-1, "trust": 0-1, "sadness": 0-1, "joy": 0-1, "disgust": 0-1}}}}

Text: "{truncated_text}"
"""
            return system_message, user_prompt

    def _call_openai_for_presidential_sentiment(self, text: str) -> Tuple[str, float, str, str, Dict[str, float]]:
        """
        Analyze text from the President's strategic perspective using OpenAI.
        Returns: (sentiment_label, sentiment_score, justification, recommended_action, emotion_distribution)
        """
        empty_emotion = {'anger': 0.0, 'fear': 0.0, 'trust': 0.0, 'sadness': 0.0, 'joy': 0.0, 'disgust': 0.0}
        if not self.openai_client:
            logger.warning("OpenAI client not available. Cannot perform presidential analysis.")
            return "neutral", 0.5, "OpenAI client not available", "", empty_emotion
        
        # Get prompts from config
        system_message, user_prompt = self._get_presidential_prompt(text)
        
        multi_model_limiter = get_multi_model_rate_limiter()
        request_id = f"pres_{id(text)}_{int(time.time())}"
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Acquire rate limiter for specific model (blocks if needed)
                # Updated estimate: ~750-1050 tokens (optimized prompt)
                with multi_model_limiter.acquire(self.model, estimated_tokens=1000):
                    response = self.openai_client.responses.create(
                        model=self.model,
                        input=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_prompt}
                        ],
                        store=False,
                        text={"format": {"type": "json_object"}}
                    )
                    
                    content = response.output_text.strip()
                    logger.debug(f"OpenAI response: {content}")
                    
                    # Parse JSON response
                    sentiment, confidence, justification, recommended_action, emotion_distribution = self._parse_sentiment_json(content)
                    
                    # Reset retry count on success
                    multi_model_limiter.reset_retry_count(self.model, request_id)
                    return sentiment, confidence, justification, recommended_action, emotion_distribution
                    
            except openai.RateLimitError as e:
                # Handle rate limit error
                retry_after = None
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_body = e.response.json() if hasattr(e.response, 'json') else {}
                        if 'error' in error_body and 'message' in error_body['error']:
                            message = error_body['error']['message']
                            if 'try again in' in message:
                                import re
                                match = re.search(r'try again in (\d+)ms', message)
                                if match:
                                    retry_after = int(match.group(1)) / 1000.0
                    except:
                        pass
                
                multi_model_limiter.handle_rate_limit_error(self.model, request_id, retry_after)
                
                if attempt == max_retries - 1:
                    rate_limit_error = RateLimitError(
                        f"OpenAI rate limit error after {max_retries} attempts",
                        retry_after=retry_after,
                        details={"model": self.model, "request_id": request_id, "attempt": attempt + 1}
                    )
                    logger.error(str(rate_limit_error))
                    return "neutral", 0.0, f"Rate limit error: {str(e)}", "", empty_emotion
                continue
                
            except openai.APIError as e:
                # Handle OpenAI API errors
                openai_error = OpenAIError(
                    f"OpenAI API error in presidential sentiment analysis: {str(e)}",
                    details={"model": self.model, "request_id": request_id, "attempt": attempt + 1}
                )
                logger.error(str(openai_error), exc_info=True)
                if attempt == max_retries - 1:
                    return "neutral", 0.0, f"OpenAI API error: {str(e)}", "", empty_emotion
                time.sleep(1.0)
                continue
                
            except Exception as e:
                # Handle other unexpected errors
                analysis_error = AnalysisError(
                    f"Unexpected error in presidential sentiment analysis: {str(e)}",
                    details={"model": self.model, "request_id": request_id, "attempt": attempt + 1, "error_type": type(e).__name__}
                )
                logger.error(str(analysis_error), exc_info=True)
                if attempt == max_retries - 1:
                    return "neutral", 0.0, f"Analysis failed: {str(e)}", "", empty_emotion
                time.sleep(1.0)
                continue
        
        return "neutral", 0.0, "Analysis failed after retries", "", empty_emotion

    def _parse_sentiment_json(self, content: str) -> Tuple[str, float, str, str, Dict[str, float]]:
        """Parse JSON response from LLM. Returns (sentiment, score, justification, recommended_action, emotion_distribution)."""
        empty_emotion = {'anger': 0.0, 'fear': 0.0, 'trust': 0.0, 'sadness': 0.0, 'joy': 0.0, 'disgust': 0.0}
        try:
            raw = content.strip()
            if "```json" in raw:
                start = raw.find("```json") + 7
                end = raw.find("```", start)
                raw = raw[start:end].strip() if end > 0 else raw
            elif "```" in raw:
                start = raw.find("```") + 3
                end = raw.find("```", start)
                raw = raw[start:end].strip() if end > 0 else raw
            data = json.loads(raw)
            sentiment = str(data.get("sentiment", "neutral")).strip().lower()
            if sentiment not in ("positive", "negative", "neutral"):
                sentiment = "neutral"
            score = float(data.get("sentiment_score", 0.0))
            score = max(-1.0, min(1.0, score))
            justification = str(data.get("justification", "")).strip() or "No justification provided"
            recommended_action = str(data.get("recommended_action", "")).strip()
            em = data.get("emotion_distribution") or {}
            emotion_distribution = {}
            for k in empty_emotion:
                try:
                    emotion_distribution[k] = max(0.0, min(1.0, float(em.get(k, 0))))
                except (ValueError, TypeError):
                    emotion_distribution[k] = 0.0
            return sentiment, score, justification, recommended_action, emotion_distribution
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Failed to parse sentiment JSON: {e} | content preview: {content[:200]!r}")
            return "neutral", 0.0, "Analysis failed", "", empty_emotion

    def _identify_relevant_topics(self, text: str) -> List[str]:
        """Identify which presidential priorities are mentioned in the text."""
        text_lower = text.lower()
        relevant_topics = []
        
        for topic, keywords in self.presidential_priorities.items():
            if any(keyword in text_lower for keyword in keywords):
                relevant_topics.append(topic)
        
        return relevant_topics

    def analyze(self, text: str, source_type: str = None, 
                user_verified: bool = False, reach: int = 0) -> Dict[str, Any]:
        """
        Analyze text from the President's strategic perspective.
        
        Week 3: Enhanced with emotion detection and weighted sentiment.
        
        Args:
            text: Text to analyze
            source_type: Source type (twitter, news, etc.)
            user_verified: Whether user/account is verified (for weight calculation)
            reach: Engagement metrics (for weight calculation)
        
        Returns:
        {
            'sentiment_label': str,  # positive/negative/neutral
            'sentiment_score': float,  # -1.0 to 1.0
            'sentiment_justification': str,  # Strategic reasoning + recommended action
            'emotion_label': str,  # Week 3: Primary emotion (anger, fear, trust, sadness, joy, disgust, neutral)
            'emotion_score': float,  # Week 3: Emotion confidence (0-1)
            'emotion_distribution': Dict,  # Week 3: All 6 emotions with scores
            'influence_weight': float,  # Week 3: Source influence weight (1.0-5.0)
            'confidence_weight': float,  # Week 3: Classification confidence (0-1)
            'issue_label': str,  # Human-readable issue label
            'issue_slug': str,  # URL-friendly identifier
            'issue_confidence': float,  # Classification confidence
            'issue_keywords': List[str],  # Keywords array
            'ministry_hint': str,  # Ministry association hint
            'embedding': List[float],  # OpenAI embedding vector (Week 3: Fixed - now returns real embeddings)
        }
        """
        if not text or str(text).strip() == "" or str(text).lower() == "none":
            return {
                'sentiment_label': 'neutral',
                'sentiment_score': 0.0,
                'sentiment_justification': 'Empty or null content - No action required',
                'issue_label': 'Unlabeled Content',
                'issue_slug': 'unlabeled-content',
                'issue_confidence': 0.0,
                'issue_keywords': [],
                'ministry_hint': None,
                'embedding': [0.0] * 1536  # Zero vector for empty content
            }
        
        # Get presidential sentiment analysis (LLM returns sentiment + emotion_distribution + recommended_action)
        sentiment, confidence, justification, recommended_action, emotion_distribution = self._call_openai_for_presidential_sentiment(str(text))
        
        # Topics from local keyword matching (no LLM)
        topics = self._identify_relevant_topics(str(text))
        
        # Use LLM recommended_action or fallback to rule-based if empty
        if not recommended_action:
            recommended_action = self._generate_recommended_action(sentiment, topics, confidence)
        
        # Derive emotion_label and emotion_score from emotion_distribution
        if emotion_distribution:
            primary = max(emotion_distribution.items(), key=lambda x: x[1])
            emotion_label = primary[0]
            emotion_score = round(primary[1], 3)
            if emotion_score < 0.2:
                emotion_label = 'neutral'
                emotion_score = 0.5
        else:
            emotion_label = 'neutral'
            emotion_score = 0.5
            emotion_distribution = {'anger': 0.0, 'fear': 0.0, 'trust': 0.0, 'sadness': 0.0, 'joy': 0.0, 'disgust': 0.0}
        
        # Generate issue mapping fields (fallback only; governance analyzer provides actual labels)
        issue_label = 'General Issue'
        issue_slug = self._normalize_to_slug(issue_label)
        issue_keywords = self._extract_keywords(text, topics)
        issue_confidence = self._calculate_issue_confidence(text, sentiment, confidence)
        ministry_hint = self._infer_ministry(text, topics)
        
        # Combine justification and recommended action (LLM-generated or fallback) for sentiment_justification
        full_justification = f"{justification}\n\nRecommended Action: {recommended_action}"
        
        # Get embedding
        embedding = self._get_embedding(text)
        
        # Calculate influence and confidence weights
        influence_weight = self._calculate_influence_weight(source_type, user_verified, reach)
        confidence_weight = self._calculate_confidence_weight(confidence, emotion_score)
        
        return {
            'sentiment_label': sentiment,
            'sentiment_score': confidence,
            'sentiment_justification': full_justification,
            'emotion_label': emotion_label,
            'emotion_score': emotion_score,
            'emotion_distribution': {k: round(v, 3) for k, v in emotion_distribution.items()},
            # Week 3: Weight calculation
            'influence_weight': influence_weight,
            'confidence_weight': confidence_weight,
            # Existing fields
            'issue_label': issue_label,  # Simple fallback - governance analyzer's label is used instead
            'issue_slug': issue_slug,  # Simple fallback - governance analyzer's slug is used instead
            'issue_confidence': issue_confidence,  # NEW
            'issue_keywords': issue_keywords,  # NEW
            'ministry_hint': ministry_hint,  # NEW
            'embedding': embedding  # Week 3: Actual embedding (fixes Week 2 zero vector issue)
        }

    def _generate_issue_label(self, text: str, topics: List[str], sentiment: str) -> str:
        """
        Generate a human-readable issue label based on content analysis.
        Note: This method now uses a simple fallback since governance analyzer provides the actual label.
        The API call was removed to save tokens (~195-445 tokens per record).
        """
        # Simple fallback - governance analyzer provides the actual label
        if topics:
            return f"{topics[0].replace('_', ' ').title()} Issue"
        return "General Issue"

    def _normalize_to_slug(self, label: str) -> str:
        """Convert issue label to URL-friendly slug."""
        import re
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', label.lower())
        slug = re.sub(r'\s+', '-', slug.strip())
        return slug or 'general-issue'

    def _extract_keywords(self, text: str, topics: List[str]) -> List[str]:
        """Extract relevant keywords from text and topics."""
        keywords = []
        
        # Add topic-based keywords
        topic_keywords = {
            'fuel_subsidy': ['fuel', 'subsidy', 'petrol', 'diesel', 'energy', 'pump', 'price'],
            'security': ['security', 'terrorism', 'banditry', 'kidnapping', 'police', 'military'],
            'youth_employment': ['youth', 'employment', 'jobs', 'unemployment', 'skills'],
            'foreign_relations': ['diplomacy', 'foreign', 'international', 'trade'],
            'infrastructure': ['roads', 'bridges', 'railways', 'airports', 'infrastructure'],
            'economy': ['economy', 'gdp', 'inflation', 'growth', 'investment'],
            'corruption': ['corruption', 'transparency', 'accountability'],
            'healthcare': ['health', 'hospital', 'medical', 'vaccine', 'healthcare'],
            'education': ['education', 'school', 'university', 'students', 'teachers']
        }
        
        for topic in topics:
            if topic in topic_keywords:
                keywords.extend(topic_keywords[topic])
        
        # Add common political keywords found in text
        text_lower = text.lower()
        common_keywords = [
            'president', 'government', 'policy', 'ministry', 'budget', 'reform',
            'development', 'program', 'initiative', 'project', 'funding',
            'citizens', 'public', 'community', 'nation', 'country'
        ]
        
        for keyword in common_keywords:
            if keyword in text_lower and keyword not in keywords:
                keywords.append(keyword)
        
        # Limit to top 10 keywords and remove duplicates
        keywords = list(dict.fromkeys(keywords))[:10]
        return keywords

    def _calculate_issue_confidence(self, text: str, sentiment: str, sentiment_score: float) -> float:
        """Calculate confidence in issue classification."""
        # Base confidence on sentiment score magnitude
        base_confidence = abs(sentiment_score)
        
        # Adjust based on text length (longer text = more context = higher confidence)
        text_length_factor = min(len(text) / 1000, 1.0)  # Normalize to 0-1
        
        # Adjust based on sentiment strength
        sentiment_factor = 1.0 if sentiment != 'neutral' else 0.7
        
        # Combine factors
        confidence = base_confidence * text_length_factor * sentiment_factor
        
        # Ensure confidence is between 0 and 1
        return max(0.0, min(1.0, confidence))

    def _infer_ministry(self, text: str, topics: List[str]) -> str:
        """Infer which ministry this content relates to."""
        ministry_mapping = {
            'fuel_subsidy': 'energy',
            'security': 'defense',
            'youth_employment': 'labor',
            'foreign_relations': 'foreign',
            'infrastructure': 'transport',
            'economy': 'finance',
            'corruption': 'justice',
            'healthcare': 'health',
            'education': 'education'
        }
        
        # Check topics first
        for topic in topics:
            if topic in ministry_mapping:
                return ministry_mapping[topic]
        
        # Fallback to keyword-based inference
        text_lower = text.lower()
        
        ministry_keywords = {
            'health': ['health', 'hospital', 'medical', 'doctor', 'patient', 'vaccine', 'disease'],
            'education': ['education', 'school', 'university', 'student', 'teacher', 'learning'],
            'finance': ['economy', 'budget', 'money', 'financial', 'bank', 'investment', 'tax'],
            'defense': ['security', 'military', 'police', 'terrorism', 'banditry', 'kidnapping'],
            'transport': ['road', 'bridge', 'railway', 'airport', 'transport', 'infrastructure'],
            'energy': ['fuel', 'electricity', 'power', 'energy', 'petrol', 'diesel', 'gas'],
            'agriculture': ['farm', 'crop', 'agriculture', 'food', 'farmer', 'rural'],
            'justice': ['court', 'law', 'justice', 'corruption', 'crime', 'legal'],
            'foreign': ['diplomacy', 'foreign', 'international', 'embassy', 'trade'],
            'labor': ['employment', 'job', 'worker', 'labor', 'unemployment', 'youth']
        }
        
        for ministry, keywords in ministry_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return ministry
        
        return 'general'

    def _get_embedding(self, text: str) -> List[float]:
        """Get OpenAI embedding for the text."""
        if not self.openai_client:
            logger.warning("OpenAI client not available for embedding generation")
            return [0.0] * 1536  # Return zero vector
        
        try:
            # Truncate text if too long (OpenAI has limits)
            text_for_embedding = text[:8000]  # Leave some buffer
            
            response = self.openai_client.embeddings.create(
                model=self._get_embedding_model(),
                input=text_for_embedding
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return [0.0] * 1536  # Return zero vector on error
    
    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Get OpenAI embeddings for multiple texts in a single batch call."""
        if not self.openai_client:
            logger.warning("OpenAI client not available for embedding generation")
            return [[0.0] * 1536 for _ in texts]
        
        if not texts:
            return []
        
        try:
            # Truncate texts if too long (OpenAI has limits)
            texts_for_embedding = [text[:8000] for text in texts]
            
            # Estimate tokens: ~2200 tokens per text for embeddings (1536 dims × ~1.3 tokens)
            estimated_tokens = len(texts_for_embedding) * 2200
            
            # Embeddings use text-embedding-3-small, not gpt models, so use default limiter
            rate_limiter = get_rate_limiter()
            # Batch API call - all texts in one request
            with rate_limiter.acquire(estimated_tokens=estimated_tokens):
                response = self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts_for_embedding
                )
                
                # Response.data is a list of embeddings in the same order as input
                embeddings = [item.embedding for item in response.data]
                
                # Ensure we return the same number of embeddings as input texts
                while len(embeddings) < len(texts):
                    embeddings.append([0.0] * 1536)
                
                return embeddings[:len(texts)]
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return [[0.0] * 1536 for _ in texts]

    def _calculate_influence_weight(self, source_type: Optional[str], user_verified: bool, reach: int) -> float:
        """
        Calculate influence weight (Week 3).
        
        Args:
            source_type: Source type
            user_verified: Whether verified
            reach: Engagement reach
        
        Returns:
            Influence weight (1.0-5.0)
        """
        if self.weight_calculator:
            try:
                return self.weight_calculator.calculate_influence_weight(
                    source_type=source_type,
                    user_verified=user_verified,
                    reach=reach
                )
            except Exception as e:
                logger.warning(f"Influence weight calculation failed: {e}")
        
        # Fallback: default weight
        return 1.0
    
    def _calculate_confidence_weight(self, sentiment_score: float, emotion_score: Optional[float]) -> float:
        """
        Calculate confidence weight (Week 3).
        
        Args:
            sentiment_score: Sentiment score
            emotion_score: Emotion confidence score
        
        Returns:
            Confidence weight (0.0-1.0)
        """
        if self.weight_calculator:
            try:
                return self.weight_calculator.calculate_confidence_weight(
                    sentiment_score=sentiment_score,
                    emotion_score=emotion_score
                )
            except Exception as e:
                logger.warning(f"Confidence weight calculation failed: {e}")
        
        # Fallback: use sentiment score magnitude
        return abs(sentiment_score) if sentiment_score else 0.5
    
    def _generate_recommended_action(self, sentiment: str, topics: List[str], sentiment_score: float) -> str:
        """Generate recommended presidential action based on sentiment and topics."""
        if sentiment == "positive":
            if sentiment_score > 0.6:
                return "Amplify and share this content through official channels"
            else:
                return "Monitor and potentially acknowledge this positive coverage"
        elif sentiment == "negative":
            if sentiment_score < -0.6:
                return "Prepare immediate response and counter-narrative"
            else:
                return "Monitor closely and prepare contingency response"
        else:  # neutral
            return "Monitor for potential developments"
    
    def batch_analyze(self, texts: List[str], source_types: List[str] = None) -> List[Dict[str, Any]]:
        """Analyze multiple texts from the President's perspective."""
        results = []
        
        for i, text in enumerate(texts):
            source_type = source_types[i] if source_types and i < len(source_types) else None
            result = self.analyze(text, source_type)
            results.append(result)
        
        return results
    
    def update_presidential_priorities(self, new_priorities: Dict[str, List[str]]):
        """Update the presidential priorities and keywords."""
        self.presidential_priorities.update(new_priorities)
        logger.info(f"Updated presidential priorities: {list(new_priorities.keys())}")
    
    def get_presidential_insights(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate presidential insights from a dataset of analyzed content.
        
        Returns strategic insights like:
        - Most threatening topics
        - Most supportive sources
        - Priority areas requiring attention
        """
        if data.empty:
            return {"error": "No data provided"}
        
        insights = {
            "total_items": len(data),
            "sentiment_distribution": {},
            "high_impact_items": [],
            "priority_topics": {},
            "recommended_focus_areas": []
        }
        
        # Sentiment distribution
        if 'sentiment_label' in data.columns:
            sentiment_counts = data['sentiment_label'].value_counts()
            insights["sentiment_distribution"] = sentiment_counts.to_dict()
        
        # High impact items (negative with high confidence)
        high_impact_mask = (
            (data['sentiment_label'] == 'negative') & 
            (data['sentiment_score'] < self._get_negative_threshold())
        )
        high_impact_items = data[high_impact_mask]
        insights["high_impact_items"] = high_impact_items.to_dict('records')
        
        # Priority topics analysis
        if 'relevant_topics' in data.columns:
            all_topics = []
            for topics in data['relevant_topics']:
                if isinstance(topics, list):
                    all_topics.extend(topics)
            
            topic_counts = pd.Series(all_topics).value_counts()
            insights["priority_topics"] = topic_counts.head(5).to_dict()
        
        # Recommended focus areas
        if len(high_impact_items) > 0:
            insights["recommended_focus_areas"] = [
                "Immediate response to negative content",
                "Strategic communication on neutral topics",
                "Amplification of positive content"
            ]
        
        return insights

    def test_specific_case(self, text: str, expected_sentiment: str = None) -> Dict[str, Any]:
        """
        Test the analyzer with a specific case and optionally compare with expected sentiment.
        Useful for validating the analyzer's handling of edge cases.
        """
        logger.info(f"Testing presidential analyzer with text: {text[:100]}...")
        
        result = self.analyze(text)
        
        test_result = {
            "input_text": text,
            "analyzed_sentiment": result['sentiment_label'],
            "sentiment_score": result['sentiment_score'],
            "justification": result['sentiment_justification'],
            "expected_sentiment": expected_sentiment,
            "match": expected_sentiment is None or result['sentiment_label'] == expected_sentiment
        }
        
        if expected_sentiment:
            if test_result["match"]:
                logger.info(f"✅ Test PASSED: Expected {expected_sentiment}, got {result['sentiment_label']}")
            else:
                logger.warning(f"❌ Test FAILED: Expected {expected_sentiment}, got {result['sentiment_label']}")
        else:
            logger.info(f"📊 Test result: {result['sentiment_label']} (sentiment_score: {result['sentiment_score']:.2f})")
        
        return test_result

    def batch_test_cases(self, test_cases: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Test multiple cases at once.
        
        Args:
            test_cases: List of dicts with 'text' and optional 'expected_sentiment' keys
        
        Returns:
            List of test results
        """
        results = []
        
        for i, test_case in enumerate(test_cases):
            logger.info(f"Testing case {i+1}/{len(test_cases)}")
            result = self.test_specific_case(
                test_case['text'], 
                test_case.get('expected_sentiment')
            )
            results.append(result)
        
        # Summary
        if any('expected_sentiment' in case for case in test_cases):
            passed = sum(1 for r in results if r['match'])
            total = len([case for case in test_cases if 'expected_sentiment' in case])
            logger.info(f"📈 Test Summary: {passed}/{total} cases passed")
        
        return results


