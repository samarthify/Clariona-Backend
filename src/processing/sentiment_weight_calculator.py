"""
Calculate influence weights for sentiment analysis.
Weights are based on source type, verification status, and reach.
"""

# Standard library imports
from typing import Dict, Optional, Any
import sys
from pathlib import Path

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config_manager import ConfigManager
from src.config.logging_config import get_logger

# Module-level setup
logger = get_logger(__name__)


class SentimentWeightCalculator:
    """
    Calculates influence weights for sentiment analysis.
    
    Influence weights determine how much a mention's sentiment contributes
    to aggregated sentiment scores. Higher weights = more influential sources.
    
    Weight Scale: 1.0 (lowest) to 5.0 (highest)
    """
    
    def __init__(self):
        """
        Initialize weight calculator with configuration from ConfigManager.
        """
        # Load configuration from ConfigManager
        try:
            config = ConfigManager()
            
            # Load source type weights
            self.source_type_weights = config.get_dict(
                'processing.sentiment.weights.source_type_weights',
                {
                    'presidency_statement': 5.0,
                    'national_media': 4.0,
                    'verified_influencer': 3.0,
                    'regional_media': 2.0,
                    'citizen_post': 1.0,
                    'news': 4.0,
                    'twitter': 1.0,
                    'facebook': 1.0,
                    'youtube': 2.0,
                    'rss': 3.0,
                }
            )
            
            # Load boost values
            self.verified_boost = config.get_float('processing.sentiment.weights.verified_boost', 1.5)
            self.high_reach_threshold = config.get_int('processing.sentiment.weights.high_reach_threshold', 100000)
            self.medium_reach_threshold = config.get_int('processing.sentiment.weights.medium_reach_threshold', 10000)
            self.high_reach_boost = config.get_float('processing.sentiment.weights.high_reach_boost', 1.3)
            self.medium_reach_boost = config.get_float('processing.sentiment.weights.medium_reach_boost', 1.1)
            
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for weight settings: {e}. Using defaults.")
            # Fallback defaults
            self.source_type_weights = {
                'presidency_statement': 5.0,
                'national_media': 4.0,
                'verified_influencer': 3.0,
                'regional_media': 2.0,
                'citizen_post': 1.0,
                'news': 4.0,
                'twitter': 1.0,
                'facebook': 1.0,
                'youtube': 2.0,
                'rss': 3.0,
            }
            self.verified_boost = 1.5
            self.high_reach_threshold = 100000
            self.medium_reach_threshold = 10000
            self.high_reach_boost = 1.3
            self.medium_reach_boost = 1.1
        
        logger.debug("SentimentWeightCalculator initialized")
    
    def calculate_influence_weight(
        self,
        source_type: Optional[str] = None,
        user_verified: bool = False,
        reach: int = 0,
        platform: Optional[str] = None
    ) -> float:
        """
        Calculate influence weight based on source characteristics.
        
        Args:
            source_type: Type of source (twitter, news, etc.)
            user_verified: Whether user/account is verified
            reach: Engagement metrics (followers, reach, cumulative_reach)
            platform: Platform name (twitter, facebook, news, etc.)
        
        Returns:
            Influence weight (1.0 - 5.0)
        """
        # Start with base weight from source type or platform
        base_weight = self._get_base_weight(source_type, platform)
        
        # Apply verification boost
        if user_verified:
            base_weight *= self.verified_boost
            logger.debug(f"Applied verification boost: {base_weight}")
        
        # Apply reach boost
        if reach > 0:
            if reach >= self.high_reach_threshold:
                base_weight *= self.high_reach_boost
                logger.debug(f"Applied high reach boost: {base_weight}")
            elif reach >= self.medium_reach_threshold:
                base_weight *= self.medium_reach_boost
                logger.debug(f"Applied medium reach boost: {base_weight}")
        
        # Cap at maximum (5.0)
        final_weight = min(base_weight, 5.0)
        
        # Ensure minimum (1.0)
        final_weight = max(final_weight, 1.0)
        
        return round(final_weight, 2)
    
    def _get_base_weight(self, source_type: Optional[str], platform: Optional[str]) -> float:
        """
        Get base weight from source type or platform.
        
        Args:
            source_type: Source type string
            platform: Platform name
        
        Returns:
            Base weight (1.0 - 5.0)
        """
        # Try source_type first
        if source_type:
            source_lower = source_type.lower()
            if source_lower in self.source_type_weights:
                return self.source_type_weights[source_lower]
        
        # Fall back to platform
        if platform:
            platform_lower = platform.lower()
            if platform_lower in self.source_type_weights:
                return self.source_type_weights[platform_lower]
        
        # Default weight for unknown sources
        return 1.0
    
    def calculate_confidence_weight(
        self,
        sentiment_score: float,
        emotion_score: Optional[float] = None
    ) -> float:
        """
        Calculate confidence weight based on sentiment and emotion scores.
        
        Higher confidence = more reliable sentiment classification.
        
        Args:
            sentiment_score: Sentiment score (-1.0 to 1.0)
            emotion_score: Emotion detection confidence (0-1)
        
        Returns:
            Confidence weight (0.0 - 1.0)
        """
        # Base confidence from sentiment score magnitude
        # Stronger sentiment (further from 0) = higher confidence
        sentiment_confidence = abs(sentiment_score)
        
        # If emotion score available, combine
        if emotion_score is not None:
            # Average of sentiment confidence and emotion confidence
            confidence = (sentiment_confidence + emotion_score) / 2.0
        else:
            confidence = sentiment_confidence
        
        # Ensure 0-1 range
        confidence = max(0.0, min(1.0, confidence))
        
        return round(confidence, 3)
    
    def get_weight_for_record(self, record: Any) -> float:
        """
        Calculate influence weight for a database record.
        
        Args:
            record: SentimentData record with source_type, platform, etc.
        
        Returns:
            Influence weight (1.0 - 5.0)
        """
        # Extract reach from various fields
        reach = 0
        if hasattr(record, 'cumulative_reach') and record.cumulative_reach:
            reach = record.cumulative_reach
        elif hasattr(record, 'direct_reach') and record.direct_reach:
            reach = record.direct_reach
        elif hasattr(record, 'retweets') and hasattr(record, 'likes'):
            # Estimate reach from engagement
            reach = (record.retweets or 0) + (record.likes or 0) * 10
        
        # Check if verified (from user fields or source)
        verified = False
        if hasattr(record, 'user_verified'):
            verified = record.user_verified or False
        
        return self.calculate_influence_weight(
            source_type=getattr(record, 'source_type', None),
            user_verified=verified,
            reach=reach,
            platform=getattr(record, 'platform', None)
        )


