"""
Emotion detection for sentiment analysis.
Detects 6 emotions: Anger, Fear, Trust, Sadness, Joy, Disgust
"""

# Standard library imports
from typing import Dict, Any, Optional, List
import sys
import threading
from pathlib import Path

# Third-party imports
# (transformers imported conditionally below)

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_manager import ConfigManager
from src.config.logging_config import get_logger

# Module-level setup
logger = get_logger(__name__)

# Try to import transformers for HuggingFace model
try:
    from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers not available - emotion detection will use fallback")


class EmotionAnalyzer:
    """
    Analyzes text for emotions using HuggingFace emotion classification model.
    
    Detects 6 emotions:
    - anger
    - fear
    - trust (positive emotion)
    - sadness
    - joy (positive emotion)
    - disgust
    
    Falls back to keyword-based detection if model not available.
    
    Week 3 Performance: Uses lazy loading to avoid loading model on initialization.
    Model is loaded only when first needed, preventing pipeline delays.
    """
    
    # Class-level cache for shared model instance (singleton pattern)
    _shared_pipeline = None
    _shared_model_name = None
    _model_loaded = False
    _load_lock = threading.Lock()  # Thread safety for concurrent loading
    
    def __init__(self, model_name: Optional[str] = None, lazy_load: bool = True):
        """
        Initialize emotion analyzer.
        
        Args:
            model_name: Optional HuggingFace model name. 
                       If None, loads from ConfigManager. 
                       Default: j-hartmann/emotion-english-distilroberta-base
            lazy_load: If True, model is loaded on first use (default). If False, loads immediately.
                      Lazy loading prevents pipeline delays from model initialization.
        """
        # Load model name from ConfigManager if not provided
        if model_name is None:
            try:
                config = ConfigManager()
                model_name = config.get(
                    'processing.emotion.model_name',
                    'j-hartmann/emotion-english-distilroberta-base'
                )
            except Exception as e:
                logger.warning(f"Could not load ConfigManager for emotion model: {e}. Using default.")
                model_name = 'j-hartmann/emotion-english-distilroberta-base'
        
        self.model_name = model_name
        self.emotion_pipeline = None
        self.use_model = False
        self.lazy_load = lazy_load
        
        # Use shared pipeline if same model (singleton pattern for performance)
        # Check without lock first for speed
        if self.model_name == EmotionAnalyzer._shared_model_name and EmotionAnalyzer._model_loaded:
            self.emotion_pipeline = EmotionAnalyzer._shared_pipeline
            self.use_model = True
            logger.debug(f"EmotionAnalyzer: Using shared model instance for {self.model_name}")
        elif not lazy_load:
            # Load immediately if lazy_load is False
            self._load_model()
    
    def _load_model(self):
        """Load the emotion model (thread-safe lazy loading)."""
        if self.use_model and self.emotion_pipeline:
            return  # Instance already has it
            
        # Check shared state again under lock
        with EmotionAnalyzer._load_lock:
            # Re-check if another thread loaded it while we waited
            if self.model_name == EmotionAnalyzer._shared_model_name and EmotionAnalyzer._model_loaded:
                self.emotion_pipeline = EmotionAnalyzer._shared_pipeline
                self.use_model = True
                logger.debug(f"EmotionAnalyzer: Using shared model instance (loaded by other thread)")
                return
            
            # Not loaded yet, proceed with loading
            if TRANSFORMERS_AVAILABLE:
                try:
                    logger.info(f"Loading emotion model: {self.model_name} (this may take 10-30 seconds on first load)")
                    pipeline_instance = pipeline(
                        "text-classification",
                        model=self.model_name,
                        top_k=None,  # Returns all scores
                        device=-1    # Force CPU to avoid meta tensor/device map issues
                    )
                    
                    # Cache for reuse
                    EmotionAnalyzer._shared_pipeline = pipeline_instance
                    EmotionAnalyzer._shared_model_name = self.model_name
                    EmotionAnalyzer._model_loaded = True
                    
                    self.emotion_pipeline = pipeline_instance
                    self.use_model = True
                    logger.info("Emotion model loaded successfully (cached for reuse)")
                except Exception as e:
                    logger.warning(f"Failed to load emotion model: {e}. Using keyword-based fallback.")
                    self.use_model = False
            else:
                logger.warning("transformers not available - using keyword-based emotion detection")
                self.use_model = False
    
    def analyze_emotion(self, text: str) -> Dict[str, Any]:
        """
        Analyze text for emotions.
        
        Args:
            text: Text to analyze
        
        Returns:
            {
                'emotion_label': str,  # Primary emotion (anger, fear, trust, sadness, joy, disgust, neutral)
                'emotion_score': float,  # Confidence score (0-1)
                'emotion_distribution': {
                    'anger': float,
                    'fear': float,
                    'trust': float,
                    'sadness': float,
                    'joy': float,
                    'disgust': float
                }
            }
        """
        if not text or not text.strip():
            return self._empty_result()
        
        # Lazy load model on first use (if not already loaded)
        if self.lazy_load and not self.use_model:
            self._load_model()
        
        if self.use_model and self.emotion_pipeline:
            return self._analyze_with_model(text)
        else:
            return self._analyze_with_keywords(text)
    
    def _analyze_with_model(self, text: str) -> Dict[str, Any]:
        """Analyze emotions using HuggingFace model."""
        try:
            # Model returns all emotion scores
            # Pipeline with return_all_scores=True returns a list of dicts: [{'label': '...', 'score': ...}, ...]
            results = self.emotion_pipeline(text, truncation=True, max_length=512)
            
            # Handle different return formats
            # If it's a list of lists (batch), take first item
            if isinstance(results, list) and len(results) > 0:
                if isinstance(results[0], list):
                    results = results[0]  # Unwrap batch
                # If first item is a dict, we're good
                # If first item is not a dict, might be a different format
                if not isinstance(results[0], dict):
                    logger.warning(f"Unexpected pipeline output format: {type(results[0])}")
                    return self._analyze_with_keywords(text)
            
            # Map model labels to our emotion labels
            emotion_mapping = {
                'anger': 'anger',
                'fear': 'fear',
                'sadness': 'sadness',
                'joy': 'joy',
                'disgust': 'disgust',
                'neutral': 'neutral',
                # Some models use different labels
                'surprise': 'neutral',
                'anticipation': 'trust',
                'trust': 'trust',
            }
            
            # Build emotion distribution
            emotion_distribution = {
                'anger': 0.0,
                'fear': 0.0,
                'trust': 0.0,
                'sadness': 0.0,
                'joy': 0.0,
                'disgust': 0.0
            }
            
            # Process model results
            for result in results:
                # Handle both dict and tuple formats
                if isinstance(result, dict):
                    label = result.get('label', '').lower()
                    score = result.get('score', 0.0)
                elif isinstance(result, (list, tuple)) and len(result) >= 2:
                    # Format: (label, score) or [label, score]
                    label = str(result[0]).lower()
                    score = float(result[1])
                else:
                    logger.warning(f"Unexpected result format: {type(result)}")
                    continue
                
                # Map to our emotion labels
                mapped_label = emotion_mapping.get(label, 'neutral')
                
                if mapped_label in emotion_distribution:
                    emotion_distribution[mapped_label] = score
                elif mapped_label == 'neutral':
                    # Distribute neutral across all emotions (small amount)
                    for emotion in emotion_distribution:
                        emotion_distribution[emotion] += score / 6
            
            # Find primary emotion (highest score)
            primary_emotion = max(emotion_distribution.items(), key=lambda x: x[1])
            emotion_label = primary_emotion[0]
            emotion_score = primary_emotion[1]
            
            # If all scores are very low, consider it neutral
            if emotion_score < 0.2:
                emotion_label = 'neutral'
                emotion_score = 0.5  # Default neutral confidence
            
            return {
                'emotion_label': emotion_label,
                'emotion_score': round(emotion_score, 3),
                'emotion_distribution': {k: round(v, 3) for k, v in emotion_distribution.items()}
            }
            
        except Exception as e:
            logger.error(f"Error analyzing emotion with model: {e}", exc_info=True)
            return self._analyze_with_keywords(text)  # Fallback to keywords
    
    def _analyze_with_keywords(self, text: str) -> Dict[str, Any]:
        """
        Fallback: Analyze emotions using keyword matching.
        Less accurate but works without model.
        """
        text_lower = text.lower()
        
        # Emotion keywords
        emotion_keywords = {
            'anger': ['angry', 'rage', 'furious', 'outraged', 'frustrated', 'irritated', 'annoyed', 'mad'],
            'fear': ['afraid', 'scared', 'terrified', 'worried', 'anxious', 'panic', 'fearful', 'nervous'],
            'trust': ['trust', 'confident', 'hopeful', 'optimistic', 'reassured', 'secure', 'safe'],
            'sadness': ['sad', 'depressed', 'disappointed', 'upset', 'unhappy', 'grief', 'mourning', 'sorrow'],
            'joy': ['happy', 'joyful', 'excited', 'pleased', 'delighted', 'celebrating', 'cheerful', 'glad'],
            'disgust': ['disgusted', 'revolted', 'sickened', 'appalled', 'horrified', 'repulsed']
        }
        
        # Count keyword matches
        emotion_scores = {}
        for emotion, keywords in emotion_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            # Normalize score (0-1)
            emotion_scores[emotion] = min(matches / len(keywords), 1.0) if matches > 0 else 0.0
        
        # If no matches, return neutral
        if sum(emotion_scores.values()) == 0:
            return self._empty_result()
        
        # Normalize scores to sum to 1.0
        total = sum(emotion_scores.values())
        emotion_distribution = {k: v / total for k, v in emotion_scores.items()}
        
        # Find primary emotion
        primary_emotion = max(emotion_distribution.items(), key=lambda x: x[1])
        emotion_label = primary_emotion[0]
        emotion_score = primary_emotion[1]
        
        return {
            'emotion_label': emotion_label,
            'emotion_score': round(emotion_score, 3),
            'emotion_distribution': {k: round(v, 3) for k, v in emotion_distribution.items()}
        }
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty emotion result."""
        return {
            'emotion_label': 'neutral',
            'emotion_score': 0.5,
            'emotion_distribution': {
                'anger': 0.0,
                'fear': 0.0,
                'trust': 0.0,
                'sadness': 0.0,
                'joy': 0.0,
                'disgust': 0.0
            }
        }

