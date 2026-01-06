"""
Calculate weighted sentiment scores and sentiment index.
Converts raw sentiment scores to weighted scores and 0-100 index.
"""

# Standard library imports
from typing import Dict, List, Any, Optional
import sys
from pathlib import Path

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config.logging_config import get_logger

# Module-level setup
logger = get_logger(__name__)


class WeightedSentimentCalculator:
    """
    Calculates weighted sentiment scores and sentiment index.
    
    Weighted Sentiment Formula:
    WeightedSentimentScore = Σ(Sentiment × InfluenceWeight × ConfidenceWeight) / Σ(InfluenceWeight)
    
    Sentiment Index Formula:
    SentimentIndex = (WeightedSentimentScore + 1) × 50  // Converts -1 to 1 range to 0-100
    """
    
    def __init__(self):
        """Initialize weighted sentiment calculator."""
        logger.debug("WeightedSentimentCalculator initialized")
    
    def calculate_weighted_sentiment(
        self,
        mentions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate weighted sentiment score for a collection of mentions.
        
        Args:
            mentions: List of mention dictionaries with:
                - sentiment_score: float (-1.0 to 1.0)
                - influence_weight: float (1.0 to 5.0)
                - confidence_weight: float (0.0 to 1.0)
        
        Returns:
            {
                'weighted_sentiment_score': float,  # -1.0 to 1.0
                'sentiment_index': float,          # 0-100
                'mention_count': int,
                'total_influence_weight': float
            }
        """
        if not mentions:
            return {
                'weighted_sentiment_score': 0.0,
                'sentiment_index': 50.0,  # Neutral
                'mention_count': 0,
                'total_influence_weight': 0.0
            }
        
        # Calculate weighted sum
        weighted_sum = 0.0
        total_influence = 0.0
        
        for mention in mentions:
            sentiment_score = mention.get('sentiment_score', 0.0)
            influence_weight = mention.get('influence_weight', 1.0)
            confidence_weight = mention.get('confidence_weight', 1.0)
            
            # Weighted contribution
            contribution = sentiment_score * influence_weight * confidence_weight
            weighted_sum += contribution
            total_influence += influence_weight
        
        # Calculate weighted average
        if total_influence > 0:
            weighted_sentiment_score = weighted_sum / total_influence
        else:
            weighted_sentiment_score = 0.0
        
        # Calculate sentiment index (0-100)
        sentiment_index = self.calculate_sentiment_index(weighted_sentiment_score)
        
        return {
            'weighted_sentiment_score': round(weighted_sentiment_score, 3),
            'sentiment_index': round(sentiment_index, 2),
            'mention_count': len(mentions),
            'total_influence_weight': round(total_influence, 2)
        }
    
    def calculate_sentiment_index(self, weighted_score: float) -> float:
        """
        Convert weighted sentiment score to 0-100 index.
        
        Formula:
        SentimentIndex = (WeightedSentimentScore + 1) × 50
        
        - SentimentScore = -1.0 → Index = 0 (most negative)
        - SentimentScore = 0.0  → Index = 50 (neutral)
        - SentimentScore = 1.0  → Index = 100 (most positive)
        
        Args:
            weighted_score: Weighted sentiment score (-1.0 to 1.0)
        
        Returns:
            Sentiment index (0-100)
        """
        # Clamp to -1 to 1 range
        clamped_score = max(-1.0, min(1.0, weighted_score))
        
        # Convert to 0-100 scale
        sentiment_index = (clamped_score + 1.0) * 50.0
        
        return round(sentiment_index, 2)
    
    def calculate_sentiment_distribution(
        self,
        mentions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Calculate sentiment distribution (positive, negative, neutral).
        
        Args:
            mentions: List of mention dictionaries with sentiment_label
        
        Returns:
            {
                'positive': float,  # Proportion (0-1)
                'negative': float,
                'neutral': float
            }
        """
        if not mentions:
            return {
                'positive': 0.0,
                'negative': 0.0,
                'neutral': 1.0
            }
        
        counts = {'positive': 0, 'negative': 0, 'neutral': 0}
        
        for mention in mentions:
            sentiment_label = mention.get('sentiment_label', 'neutral')
            sentiment_label_lower = sentiment_label.lower()
            
            if sentiment_label_lower == 'positive':
                counts['positive'] += 1
            elif sentiment_label_lower == 'negative':
                counts['negative'] += 1
            else:
                counts['neutral'] += 1
        
        total = len(mentions)
        return {
            'positive': round(counts['positive'] / total, 3),
            'negative': round(counts['negative'] / total, 3),
            'neutral': round(counts['neutral'] / total, 3)
        }
    
    def calculate_emotion_distribution(
        self,
        mentions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Calculate aggregated emotion distribution.
        
        Args:
            mentions: List of mention dictionaries with emotion_distribution
        
        Returns:
            {
                'anger': float,
                'fear': float,
                'trust': float,
                'sadness': float,
                'joy': float,
                'disgust': float
            }
        """
        if not mentions:
            return {
                'anger': 0.0,
                'fear': 0.0,
                'trust': 0.0,
                'sadness': 0.0,
                'joy': 0.0,
                'disgust': 0.0
            }
        
        emotion_totals = {
            'anger': 0.0,
            'fear': 0.0,
            'trust': 0.0,
            'sadness': 0.0,
            'joy': 0.0,
            'disgust': 0.0
        }
        
        total_weight = 0.0
        
        for mention in mentions:
            emotion_dist = mention.get('emotion_distribution', {})
            influence_weight = mention.get('influence_weight', 1.0)
            
            if emotion_dist:
                for emotion, score in emotion_dist.items():
                    if emotion in emotion_totals:
                        emotion_totals[emotion] += score * influence_weight
                        total_weight += influence_weight
        
        # Normalize by total weight
        if total_weight > 0:
            emotion_distribution = {
                emotion: round(score / total_weight, 3)
                for emotion, score in emotion_totals.items()
            }
        else:
            emotion_distribution = {emotion: 0.0 for emotion in emotion_totals.keys()}
        
        return emotion_distribution


