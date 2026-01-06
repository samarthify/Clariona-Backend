# Standard library imports
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import glob
import random
import re

# Third-party imports
import pandas as pd
from dateutil import parser

# Local imports - config (first)
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config.logging_config import get_logger
from src.config.path_manager import PathManager

# Local imports - processing modules
from .presidential_sentiment_analyzer import PresidentialSentimentAnalyzer
from .governance_analyzer import GovernanceAnalyzer
from .topic_classifier import TopicClassifier
from .record_router import RecordRouter

# Local imports - utils
from utils.common import parse_datetime as parse_datetime_common
from utils.deduplication_service import DeduplicationService
from utils.file_rotation import rotate_processed_files

# Module-level setup
logger = get_logger('DataProcessor')

class DataProcessor:
    def __init__(self, models: List[str] = None):
        """
        Initialize the data processor.
        
        Args:
            models: List of models to use for parallel processing.
                   Defaults to all 4 models: ["gpt-5-mini", "gpt-5-nano", "gpt-4.1-mini", "gpt-4.1-nano"]
        """
        logger.debug("DataProcessor.__init__: Initializing...")
        # Initialize PathManager for centralized path management
        self.path_manager = PathManager()
        self.base_path = self.path_manager.base_path  # For backward compatibility
        logger.debug(f"DataProcessor.__init__: Base path set to {self.base_path}")
        
        # Determine models to use - load from ConfigManager if not provided
        if models is None:
            try:
                from config.config_manager import ConfigManager
                config = ConfigManager()
                self.models = config.get_list("models.llm_models.available", ["gpt-5-mini", "gpt-5-nano", "gpt-4.1-mini", "gpt-4.1-nano"])
            except Exception as e:
                logger.warning(f"Could not load ConfigManager for available models, using defaults: {e}")
                self.models = ["gpt-5-mini", "gpt-5-nano", "gpt-4.1-mini", "gpt-4.1-nano"]
        else:
            self.models = models
        
        # Initialize analyzers for each model
        logger.debug(f"DataProcessor.__init__: Initializing analyzers for {len(self.models)} models...")
        self.sentiment_analyzers = {}
        self.governance_analyzers = {}
        
        for model in self.models:
            logger.debug(f"DataProcessor.__init__: Initializing analyzers for {model}...")
            self.sentiment_analyzers[model] = PresidentialSentimentAnalyzer(model=model)
            self.governance_analyzers[model] = GovernanceAnalyzer(enable_issue_classification=True, model=model)
        
        # Initialize TopicClassifier (Week 2: Topic System Integration)
        logger.debug("DataProcessor.__init__: Initializing TopicClassifier...")
        self.topic_classifier = TopicClassifier()
        
        # Initialize Issue Detection Engine (Week 4: Issue Detection System)
        logger.debug("DataProcessor.__init__: Initializing IssueDetectionEngine...")
        try:
            from .issue_detection_engine import IssueDetectionEngine
            self.issue_detection_engine = IssueDetectionEngine()
            logger.debug("DataProcessor.__init__: IssueDetectionEngine initialized")
        except Exception as e:
            logger.warning(f"Could not initialize IssueDetectionEngine: {e}. Issue detection will be disabled.")
            self.issue_detection_engine = None
        
        # Initialize Aggregation Services (Week 5: Aggregation & Integration)
        logger.debug("DataProcessor.__init__: Initializing aggregation services...")
        try:
            from .sentiment_aggregation_service import SentimentAggregationService
            from .sentiment_trend_calculator import SentimentTrendCalculator
            from .topic_sentiment_normalizer import TopicSentimentNormalizer
            
            self.aggregation_service = SentimentAggregationService()
            self.trend_calculator = SentimentTrendCalculator()
            self.normalizer = TopicSentimentNormalizer()
            logger.debug("DataProcessor.__init__: Aggregation services initialized")
        except Exception as e:
            logger.warning(f"Could not initialize aggregation services: {e}. Aggregation will be disabled.")
            self.aggregation_service = None
            self.trend_calculator = None
            self.normalizer = None
        
        # Initialize record router
        self.router = RecordRouter(models=self.models)
        
        # For backward compatibility, keep default analyzers
        self.sentiment_analyzer = self.sentiment_analyzers[self.models[0]]
        self.governance_analyzer = self.governance_analyzers[self.models[0]]
        
        random.seed(42)  # For consistent random values
        logger.debug(f"DataProcessor initialized with {len(self.models)} parallel pipelines")
        logger.debug("DataProcessor.__init__: Initialization finished.")

    def get_sentiment(self, text, source_type=None):
        """
        Analyze text using parallel Topic + Sentiment classification (Week 2).
        
        Week 2 Update: Now runs Topic and Sentiment classification in parallel for better performance.
        Topic classification replaces LLM-based ministry classification.
        
        Process:
        1. Run TopicClassifier and PresidentialSentimentAnalyzer in parallel
        2. Extract embedding from sentiment result (if available)
        3. Combine results with topics
        
        Returns combined results with topics and sentiment.
        
        Args:
            text: Text content to analyze
            source_type: Optional source type (for backward compatibility)
        
        Returns:
            Dict with sentiment, topics, and metadata:
            {
                'sentiment_label': 'positive'|'negative'|'neutral',
                'sentiment_score': float,
                'sentiment_justification': str,
                'topics': List[Dict],  # List of topic classifications
                'embedding': List[float],  # 1536-dim embedding vector
                # Legacy fields (for backward compatibility)
                'ministry_hint': str,  # Primary topic key
                'issue_slug': str,  # Will be populated in Week 4
                'issue_label': str,
            }
        """
        logger.debug(f"DataProcessor.get_sentiment: Analyzing text (first 50 chars): '{str(text)[:50]}...'")
        
        # Week 2: Run Topic and Sentiment in parallel
        logger.debug("DataProcessor.get_sentiment: Running parallel Topic + Sentiment classification...")
        
        # Week 3: Run sentiment analysis (now includes emotions and weights)
        # Extract source info for weight calculation if available
        sentiment_result = self.sentiment_analyzer.analyze(
            text,
            source_type=source_type,
            user_verified=False,  # TODO: Extract from record if available
            reach=0  # TODO: Extract from record if available
        )
        text_embedding = sentiment_result.get('embedding')
        
        # Classify topics with embedding (if available) for better accuracy
        if text_embedding and len(text_embedding) == 1536:
            logger.debug("DataProcessor.get_sentiment: Classifying topics with embedding...")
            topic_result = self.topic_classifier.classify(text, text_embedding)
        else:
            logger.debug("DataProcessor.get_sentiment: Classifying topics without embedding...")
            topic_result = self.topic_classifier.classify(text)
        
        # Get primary topic (first/highest confidence)
        primary_topic = topic_result[0] if topic_result else None
        
        # Combine results
        combined_result = {
            # Sentiment (from PresidentialSentimentAnalyzer)
            'sentiment_label': sentiment_result['sentiment_label'],
            'sentiment_score': sentiment_result['sentiment_score'],
            'sentiment_justification': sentiment_result['sentiment_justification'],
            
            # Week 3: Emotion detection
            'emotion_label': sentiment_result.get('emotion_label', 'neutral'),
            'emotion_score': sentiment_result.get('emotion_score', 0.5),
            'emotion_distribution': sentiment_result.get('emotion_distribution', {}),
            
            # Week 3: Weight calculation
            'influence_weight': sentiment_result.get('influence_weight', 1.0),
            'confidence_weight': sentiment_result.get('confidence_weight', 0.5),
            
            # Topics (from TopicClassifier) - Week 2
            # TopicClassifier returns: {topic, topic_name, confidence, keyword_score, embedding_score}
            'topics': topic_result,  # List of topic classifications
            'primary_topic_key': primary_topic['topic'] if primary_topic else None,  # Note: TopicClassifier uses 'topic' key
            'primary_topic_name': primary_topic['topic_name'] if primary_topic else None,
            
            # Embedding
            'embedding': text_embedding or [],
            
            # Legacy fields (for backward compatibility with existing code)
            'ministry_hint': primary_topic['topic'] if primary_topic else None,  # Map topic to ministry_hint
            'issue_slug': None,  # Will be populated in Week 4 (Issue Detection)
            'issue_label': None,  # Will be populated in Week 4
            'issue_confidence': None,
            'issue_keywords': None,
        }
        
        logger.debug(f"DataProcessor.get_sentiment: Combined result - Sentiment: {combined_result['sentiment_label']}, Topics: {len(topic_result)}, Primary: {combined_result['primary_topic_key']}")
        return combined_result

    def batch_get_sentiment(self, texts: List[str], source_types: List[str] = None, max_workers: int = 20) -> List[Dict[str, Any]]:
        """
        Batch process multiple texts in parallel using Topic + Sentiment classification (Week 2).
        
        Week 2 Update: Now uses parallel Topic + Sentiment classification instead of 
        LLM-based ministry classification. Much faster and more accurate.
        
        Args:
            texts: List of text strings to analyze
            source_types: Optional list of source types (must match texts length) - kept for backward compatibility
            max_workers: Maximum number of parallel workers per pipeline
            
        Returns:
            List of combined results in same order as input texts.
            Each result includes sentiment, topics, and metadata.
        """
        if not texts:
            return []
        
        if source_types is None:
            source_types = [None] * len(texts)
        elif len(source_types) != len(texts):
            logger.warning(f"source_types length ({len(source_types)}) doesn't match texts length ({len(texts)}). Padding with None.")
            source_types = source_types + [None] * (len(texts) - len(source_types))
        
        logger.info(f"Batch processing {len(texts)} texts with parallel Topic + Sentiment classification (Week 2)...")
        
        # Week 2: Use parallel Topic + Sentiment for each text
        # This is simpler and faster than the old multi-model routing
        results = []
        
        def process_single_text(text_idx: int) -> Dict[str, Any]:
            """Process a single text with Topic + Sentiment in parallel."""
            try:
                return self.get_sentiment(texts[text_idx], source_types[text_idx])
            except Exception as e:
                logger.error(f"Error processing text {text_idx}: {e}")
                return {
                    'sentiment_label': 'neutral',
                    'sentiment_score': 0.0,
                    'sentiment_justification': f'Error: {str(e)}',
                    'topics': [],
                    'primary_topic_key': None,
                    'primary_topic_name': None,
                    'embedding': [0.0] * 1536,
                    'ministry_hint': None,
                    'issue_slug': None,
                    'issue_label': None,
                    'issue_confidence': None,
                    'issue_keywords': None,
                }
        
        # Process all texts in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_text, i): i for i in range(len(texts))}
            results_dict = {}
            for future in as_completed(futures):
                text_idx = futures[future]
                try:
                    results_dict[text_idx] = future.result()
                except Exception as e:
                    logger.error(f"Error getting result for text {text_idx}: {e}")
                    results_dict[text_idx] = {
                        'sentiment_label': 'neutral',
                        'sentiment_score': 0.0,
                        'sentiment_justification': f'Error: {str(e)}',
                        'topics': [],
                        'primary_topic_key': None,
                        'primary_topic_name': None,
                        'embedding': [0.0] * 1536,
                        'ministry_hint': None,
                        'issue_slug': None,
                        'issue_label': None,
                        'issue_confidence': None,
                        'issue_keywords': None,
                    }
        
        # Return results in original order
        results = [results_dict[i] for i in range(len(texts))]
        logger.info(f"Batch processing complete: {len(results)} results")
        return results
    
    def _store_topics_in_database(self, session, mention_id: int, topics: List[Dict[str, Any]]) -> None:
        """
        Store topics in mention_topics table (Week 2).
        
        Args:
            session: Database session
            mention_id: SentimentData entry_id
            topics: List of topic classifications from TopicClassifier
        """
        from api.models import MentionTopic
        from datetime import datetime
        import numpy as np
        
        if not topics:
            return
        
        def convert_to_python_type(value):
            """Convert numpy types to Python native types for database storage."""
            if value is None:
                return None
            if isinstance(value, (np.integer, np.floating)):
                return float(value) if isinstance(value, np.floating) else int(value)
            if isinstance(value, np.ndarray):
                return value.tolist()
            return value
        
        for topic in topics:
            try:
                # Convert numpy types to Python native types
                topic_confidence = convert_to_python_type(topic.get('confidence'))
                keyword_score = convert_to_python_type(topic.get('keyword_score'))
                embedding_score = convert_to_python_type(topic.get('embedding_score'))
                
                # Check if already exists
                existing = session.query(MentionTopic).filter(
                    MentionTopic.mention_id == mention_id,
                    MentionTopic.topic_key == topic['topic']  # TopicClassifier uses 'topic' key
                ).first()
                
                if existing:
                    # Update existing
                    existing.topic_confidence = topic_confidence
                    existing.keyword_score = keyword_score
                    existing.embedding_score = embedding_score
                    existing.updated_at = datetime.now()
                else:
                    # Create new
                    mention_topic = MentionTopic(
                        mention_id=mention_id,
                        topic_key=topic['topic'],  # TopicClassifier uses 'topic' key
                        topic_confidence=topic_confidence,
                        keyword_score=keyword_score,
                        embedding_score=embedding_score
                    )
                    session.add(mention_topic)
            except Exception as e:
                logger.error(f"Error storing topic {topic.get('topic')} for mention {mention_id}: {e}")
                continue

    def detect_issues_for_topic(self, topic_key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Detect issues for a specific topic (Week 4: Issue Detection System).
        
        This method processes mentions that have been classified with the given topic
        and detects issues by clustering similar mentions together.
        
        Args:
            topic_key: Topic key to detect issues for
            limit: Optional limit on number of mentions to process
        
        Returns:
            List of created/updated issue dictionaries with:
            - issue_id: UUID of the issue
            - topic_key: Topic key
            - action: 'created' or 'updated'
            - mention_count: Number of mentions in the issue
            - priority_score: Priority score (0-100)
            - lifecycle_state: Current lifecycle state
        """
        if not self.issue_detection_engine:
            logger.warning("IssueDetectionEngine not initialized. Skipping issue detection.")
            return []
        
        try:
            logger.info(f"Detecting issues for topic: {topic_key}")
            issues = self.issue_detection_engine.detect_issues(topic_key, limit=limit)
            logger.info(f"Detected {len(issues)} issues for topic: {topic_key}")
            return issues
        except Exception as e:
            logger.error(f"Error detecting issues for topic {topic_key}: {e}", exc_info=True)
            return []
    
    def detect_issues_for_all_topics(self, limit_per_topic: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect issues for all topics that have mentions (Week 4: Issue Detection System).
        
        This method processes all topics that have mentions and detects issues for each.
        Useful for batch processing or periodic issue detection runs.
        
        Args:
            limit_per_topic: Optional limit on number of mentions to process per topic
        
        Returns:
            Dictionary mapping topic_key to list of issue dictionaries
        """
        if not self.issue_detection_engine:
            logger.warning("IssueDetectionEngine not initialized. Skipping issue detection.")
            return {}
        
        from api.database import SessionLocal
        from api.models import MentionTopic
        
        session = SessionLocal()
        results = {}
        
        try:
            # Get all topics that have mentions
            topics_with_mentions = session.query(MentionTopic.topic_key).distinct().all()
            topic_keys = [t[0] for t in topics_with_mentions]
            
            logger.info(f"Detecting issues for {len(topic_keys)} topics")
            
            for topic_key in topic_keys:
                try:
                    issues = self.detect_issues_for_topic(topic_key, limit=limit_per_topic)
                    results[topic_key] = issues
                except Exception as e:
                    logger.error(f"Error detecting issues for topic {topic_key}: {e}", exc_info=True)
                    results[topic_key] = []
            
            logger.info(f"Issue detection complete for {len(topic_keys)} topics")
            return results
            
        except Exception as e:
            logger.error(f"Error in detect_issues_for_all_topics: {e}", exc_info=True)
            return {}
        finally:
            session.close()

    def aggregate_sentiment_for_topic(
        self,
        topic_key: str,
        time_window: str = '24h'
    ) -> Optional[Dict[str, Any]]:
        """
        Aggregate sentiment for a specific topic (Week 5: Aggregation & Integration).
        
        Args:
            topic_key: Topic key to aggregate
            time_window: Time window ('15m', '1h', '24h', '7d', '30d')
        
        Returns:
            Aggregation result dictionary or None if insufficient data
        """
        if not self.aggregation_service:
            logger.warning("SentimentAggregationService not initialized. Skipping aggregation.")
            return None
        
        try:
            return self.aggregation_service.aggregate_by_topic(topic_key, time_window)
        except Exception as e:
            logger.error(f"Error aggregating sentiment for topic {topic_key}: {e}", exc_info=True)
            return None
    
    def calculate_trend_for_topic(
        self,
        topic_key: str,
        time_window: str = '24h'
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate sentiment trend for a specific topic (Week 5: Aggregation & Integration).
        
        Args:
            topic_key: Topic key to calculate trend for
            time_window: Time window ('15m', '1h', '24h', '7d', '30d')
        
        Returns:
            Trend result dictionary or None if insufficient data
        """
        if not self.trend_calculator:
            logger.warning("SentimentTrendCalculator not initialized. Skipping trend calculation.")
            return None
        
        try:
            return self.trend_calculator.calculate_trend_for_topic(topic_key, time_window)
        except Exception as e:
            logger.error(f"Error calculating trend for topic {topic_key}: {e}", exc_info=True)
            return None
    
    def normalize_sentiment_for_topic(
        self,
        topic_key: str,
        current_sentiment_index: float
    ) -> Dict[str, Any]:
        """
        Normalize sentiment index against topic baseline (Week 5: Aggregation & Integration).
        
        Args:
            topic_key: Topic key
            current_sentiment_index: Current sentiment index (0-100)
        
        Returns:
            Normalized sentiment result dictionary
        """
        if not self.normalizer:
            logger.warning("TopicSentimentNormalizer not initialized. Skipping normalization.")
            return {
                'normalized_index': current_sentiment_index,
                'baseline_index': 50.0,
                'deviation': current_sentiment_index - 50.0,
                'normalized_score': (current_sentiment_index - 50.0) / 50.0,
                'current_index': current_sentiment_index
            }
        
        try:
            return self.normalizer.normalize_sentiment_for_topic(topic_key, current_sentiment_index)
        except Exception as e:
            logger.error(f"Error normalizing sentiment for topic {topic_key}: {e}", exc_info=True)
            # Return unnormalized result on error
            return {
                'normalized_index': current_sentiment_index,
                'baseline_index': 50.0,
                'deviation': current_sentiment_index - 50.0,
                'normalized_score': (current_sentiment_index - 50.0) / 50.0,
                'current_index': current_sentiment_index
            }
    
    def run_aggregation_pipeline(
        self,
        time_window: str = '24h',
        include_trends: bool = True,
        include_normalization: bool = True,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run complete aggregation pipeline for all topics (Week 5: Aggregation & Integration).
        
        This method:
        1. Aggregates sentiment for all topics
        2. Calculates trends (if enabled)
        3. Normalizes aggregations (if enabled)
        
        Args:
            time_window: Time window ('15m', '1h', '24h', '7d', '30d')
            include_trends: Whether to calculate trends
            include_normalization: Whether to normalize aggregations
            limit: Optional limit on number of topics to process
        
        Returns:
            Dictionary with aggregation results, trends, and normalized data
        """
        if not self.aggregation_service:
            logger.warning("Aggregation services not initialized. Skipping pipeline.")
            return {}
        
        results = {
            'aggregations': {},
            'trends': {},
            'normalized': {},
            'time_window': time_window,
            'processed_at': datetime.now()
        }
        
        try:
            # Step 1: Aggregate sentiment for all topics
            logger.info(f"Running aggregation pipeline for time_window={time_window}")
            aggregations = self.aggregation_service.aggregate_all_topics(
                time_window=time_window,
                limit=limit
            )
            results['aggregations'] = aggregations
            logger.info(f"Aggregated sentiment for {len(aggregations)} topics")
            
            # Step 2: Calculate trends (if enabled)
            if include_trends and self.trend_calculator:
                logger.info("Calculating trends...")
                trends = self.trend_calculator.calculate_trends_for_all_topics(
                    time_window=time_window,
                    limit=limit
                )
                results['trends'] = trends
                logger.info(f"Calculated trends for {len(trends)} topics")
            
            # Step 3: Normalize aggregations (if enabled)
            if include_normalization and self.normalizer:
                logger.info("Normalizing aggregations...")
                normalized = {}
                for topic_key, aggregation in aggregations.items():
                    try:
                        normalized_agg = self.normalizer.normalize_aggregation(aggregation)
                        normalized[topic_key] = normalized_agg
                    except Exception as e:
                        logger.warning(f"Error normalizing aggregation for topic {topic_key}: {e}")
                        normalized[topic_key] = aggregation
                results['normalized'] = normalized
                logger.info(f"Normalized {len(normalized)} aggregations")
            
            logger.info("Aggregation pipeline complete")
            return results
            
        except Exception as e:
            logger.error(f"Error in aggregation pipeline: {e}", exc_info=True)
            return results

    def parse_date(self, date_str):
        """Parse date string using shared utility function (legacy method for backward compatibility)"""
        # Use shared parse_datetime utility function from common.py
        # Note: This method is only used in legacy process_data() method
        return parse_datetime_common(date_str)

    def detect_country(self, row):
        """
        Detect country information based on available data.
        Supported countries: US, UK, Qatar, UAE, India
        Uses a scoring system to determine the most likely country.
        """
        # If country already exists and is valid, don't overwrite it
        if not pd.isna(row.get('country')) and row['country'] not in ['none', 'unknown', '']:
            return row['country'].lower()
        
        # Initialize text for analysis
        text = str(row.get('text', '')).lower() if not pd.isna(row.get('text')) else ''
        platform = str(row.get('platform', '')).lower() if not pd.isna(row.get('platform')) else ''
        source = str(row.get('source', '')).lower() if not pd.isna(row.get('source')) else ''
        user_location = str(row.get('user_location', '')).lower() if not pd.isna(row.get('user_location')) else ''
        user_name = str(row.get('user_name', '')).lower() if not pd.isna(row.get('user_name')) else ''
        user_handle = str(row.get('user_handle', '')).lower() if not pd.isna(row.get('user_handle')) else ''
        
        # Initialize country scores
        country_scores = {'US': 0, 'UK': 0, 'Qatar': 0, 'UAE': 0, 'India': 0}
        
        # Helper function to detect language patterns
        def detect_language_patterns(text):
            # American English patterns
            us_patterns = ['color', 'center', 'favorite', 'analyze', 'organize', 'defense', 'license', 'traveling']
            # British English patterns
            uk_patterns = ['colour', 'centre', 'favourite', 'analyse', 'organise', 'defence', 'licence', 'travelling']
            # Arabic transliteration patterns
            qatar_patterns = ['al-', 'bin ', 'ibn ', 'abdul', 'sheikh', 'sharia', 'majlis', 'emir']
            
            us_count = sum(1 for pattern in us_patterns if pattern in text)
            uk_count = sum(1 for pattern in uk_patterns if pattern in text)
            qatar_count = sum(1 for pattern in qatar_patterns if pattern in text)
            
            return {'US': us_count, 'UK': uk_count, 'Qatar': qatar_count}
        
        # Helper function to detect Arabic script
        def contains_arabic(text):
            arabic_ranges = [
                (0x0600, 0x06FF),  # Arabic
                (0x0750, 0x077F),  # Arabic Supplement
                (0x08A0, 0x08FF),  # Arabic Extended-A
                (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
                (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
            ]
            
            for char in text:
                code_point = ord(char)
                if any(start <= code_point <= end for start, end in arabic_ranges):
                    return True
            return False
        
        # Helper function to detect Indic scripts
        def contains_indic_script(text):
            indic_ranges = [
                (0x0900, 0x097F),  # Devanagari
                (0x0980, 0x09FF),  # Bengali
                (0x0A00, 0x0A7F),  # Gurmukhi
                (0x0A80, 0x0AFF),  # Gujarati
                (0x0B00, 0x0B7F),  # Oriya
                (0x0B80, 0x0BFF),  # Tamil
                (0x0C00, 0x0C7F),  # Telugu
                (0x0C80, 0x0CFF),  # Kannada
                (0x0D00, 0x0D7F),  # Malayalam
                # Add other relevant Indic script ranges if needed
            ]
            
            for char in text:
                code_point = ord(char)
                if any(start <= code_point <= end for start, end in indic_ranges):
                    return True
            return False
        
        # Check for social media platforms
        if source.lower() in ['x', 'twitter', 'facebook', 'instagram', 'tiktok'] or platform.lower() in ['x', 'twitter', 'facebook', 'instagram', 'tiktok']:
            # Check user_location
            if user_location:
                if any(loc in user_location for loc in ['usa', 'united states', 'america', 'us ', 'u.s', 'u.s.a']):
                    country_scores['US'] += 3
                elif any(loc in user_location for loc in ['uk', 'united kingdom', 'england', 'scotland', 'wales', 'britain', 'great britain']):
                    country_scores['UK'] += 3
                elif any(loc in user_location for loc in ['qatar', 'doha']):
                    country_scores['Qatar'] += 3
                elif any(loc in user_location for loc in ['uae', 'united arab emirates', 'dubai', 'abu dhabi', 'sharjah']):
                    country_scores['UAE'] += 3
                elif any(loc in user_location for loc in ['india', 'bharat', 'hindustan']):
                    country_scores['India'] += 3
                
                # Check for cities/states
                us_locations = ['new york', 'california', 'texas', 'florida', 'chicago', 'los angeles', 'boston', 'washington', 'seattle', 'atlanta']
                uk_locations = ['london', 'manchester', 'liverpool', 'birmingham', 'leeds', 'glasgow', 'edinburgh', 'bristol', 'cardiff', 'belfast']
                qatar_locations = ['doha', 'al wakrah', 'al rayyan', 'lusail', 'al khor', 'dukhan', 'mesaieed', 'al shamal']
                uae_locations = ['dubai', 'abu dhabi', 'sharjah', 'ajman', 'ras al khaimah', 'fujairah', 'umm al quwain', 'al ain']
                india_locations = ['mumbai', 'delhi', 'bangalore', 'hyderabad', 'chennai', 'kolkata', 'pune', 'ahmedabad', 'jaipur', 'surat', 'lucknow', 'kanpur', 'nagpur', 'indore', 'thane', 'bhopal', 'visakhapatnam', 'patna', 'vadodara', 'ghaziabad', 'ludhiana', 'agra', 'nashik', 'faridabad', 'meerut', 'rajkot', 'kalyan-dombivli', 'vasai-virar', 'varanasi', 'srinagar', 'aurangabad', 'dhanbad', 'amritsar', 'navi mumbai', 'allahabad', 'ranchi', 'howrah', 'coimbatore', 'jabalpur', 'gwalior', 'vijayawada', 'jodhpur', 'madurai', 'raipur', 'kota', 'guwahati', 'chandigarh']
                
                for loc in us_locations:
                    if loc in user_location:
                        country_scores['US'] += 2
                for loc in uk_locations:
                    if loc in user_location:
                        country_scores['UK'] += 2
                for loc in qatar_locations:
                    if loc in user_location:
                        country_scores['Qatar'] += 2
                for loc in uae_locations:
                    if loc in user_location:
                        country_scores['UAE'] += 2
                for loc in india_locations:
                    if loc in user_location:
                        country_scores['India'] += 2
            
            # Check username and handle
            for name in [user_name, user_handle]:
                if name:
                    # Check for country codes
                    if re.search(r'\b(us|usa|america)\b', name) or name.endswith('_us') or name.endswith('_usa'):
                        country_scores['US'] += 2
                    elif re.search(r'\b(uk|gb|britain)\b', name) or name.endswith('_uk') or name.endswith('_gb'):
                        country_scores['UK'] += 2
                    elif re.search(r'\b(qa|qatar)\b', name) or name.endswith('_qa') or name.endswith('_qatar'):
                        country_scores['Qatar'] += 2
                    elif re.search(r'\b(ae|uae)\b', name) or name.endswith('_ae') or name.endswith('_uae'):
                        country_scores['UAE'] += 2
                    elif re.search(r'\b(in|india|bharat)\b', name) or name.endswith('_in') or name.endswith('_india'):
                        country_scores['India'] += 2
                    
                    # Check for city/state names
                    if any(city in name for city in ['nyc', 'newyork', 'chicago', 'la', 'losangeles', 'boston', 'texas', 'florida', 'cali', 'california']):
                        country_scores['US'] += 1
                    elif any(city in name for city in ['london', 'manchester', 'liverpool', 'birmingham', 'leeds', 'glasgow', 'edinburgh']):
                        country_scores['UK'] += 1
                    elif any(city in name for city in ['doha', 'alwakrah', 'rayyan', 'lusail']):
                        country_scores['Qatar'] += 1
                    elif any(city in name for city in ['dubai', 'abu dhabi', 'sharjah', 'ajman', 'ras al khaimah', 'fujairah', 'umm al quwain', 'al ain']):
                        country_scores['UAE'] += 1
                    elif any(city in name for city in ['mumbai', 'delhi', 'bangalore', 'bengaluru', 'chennai', 'kolkata', 'hyderabad', 'pune', 'ahmedabad', 'jaipur']):
                        country_scores['India'] += 1
                    
                    # Check for common name patterns
                    if name.startswith('american') or 'american' in name:
                        country_scores['US'] += 1
                    elif name.startswith('british') or 'british' in name:
                        country_scores['UK'] += 1
                    elif name.startswith('qatari') or 'qatari' in name:
                        country_scores['Qatar'] += 1
                    elif name.startswith('uae') or 'uae' in name:
                        country_scores['UAE'] += 1
                    elif name.startswith('indian') or 'indian' in name:
                        country_scores['India'] += 1
                    
                    # Check for Arabic names (common in Qatar)
                    if any(pattern in name for pattern in ['al-', 'bin-', 'ibn-', 'abdul', 'sheikh']):
                        country_scores['Qatar'] += 2
                    
                    # Check for Arabic script
                    if contains_arabic(name):
                        country_scores['Qatar'] += 3
                    # Check for Indic script
                    if contains_indic_script(name):
                        country_scores['India'] += 3
            
            # Check text content for country mentions
            us_terms = ['america', 'american', 'washington', 'new york', 'california', 'texas', 'usa', 'united states', 'white house', 'congress', 'nfl', 'nba']
            uk_terms = ['britain', 'british', 'london', 'manchester', 'liverpool', 'uk', 'united kingdom', 'england', 'scotland', 'wales', 'bbc', 'nhs', 'parliament']
            qatar_terms = ['qatar', 'doha', 'qatari', 'al thani', 'emir', 'gulf', 'middle east', 'arabian', 'sharia', 'islamic']
            uae_terms = ['uae', 'dubai', 'abu dhabi', 'sharjah', 'ajman', 'ras al khaimah', 'fujairah', 'umm al quwain', 'al ain']
            india_terms = ['india', 'indian', 'bharat', 'hindustan', 'mumbai', 'delhi', 'bangalore', 'hyderabad', 'chennai', 'kolkata', 'bollywood', 'cricket', 'modi', 'rupee', 'hindi', 'tamil', 'telugu', 'bengali']
            
            for term in us_terms:
                if term in text:
                    country_scores['US'] += 1
            for term in uk_terms:
                if term in text:
                    country_scores['UK'] += 1
            for term in qatar_terms:
                if term in text:
                    country_scores['Qatar'] += 1
            for term in uae_terms:
                if term in text:
                    country_scores['UAE'] += 1
            for term in india_terms:
                if term in text:
                    country_scores['India'] += 1
            
            # Check for language patterns
            language_scores = detect_language_patterns(text)
            for country, score in language_scores.items():
                country_scores[country] += score
            
            # Check for Arabic script in text (strong indicator for Qatar)
            if contains_arabic(text):
                country_scores['Qatar'] += 3
            # Check for Indic script in text (strong indicator for India)
            if contains_indic_script(text):
                country_scores['India'] += 3
        
        # Check for news sources
        elif source.lower() == 'news' or platform.lower() in ['cnn', 'bbc', 'fox', 'nbc', 'abc', 'cbs', 'newsweek', 'huffpost', 'pbs']:
            # Check source domain/name (highest priority for news)
            if platform:
                us_sources = ['cnn', 'fox', 'nbc', 'abc', 'cbs', 'usa today', 'new york times', 'washington post', 'huffpost', 'newsweek', 'politico', 'bloomberg', 'cnbc']
                uk_sources = ['bbc', 'guardian', 'telegraph', 'independent', 'daily mail', 'mirror', 'sun', 'times', 'economist', 'financial times', 'sky news']
                qatar_sources = [
                    'al jazeera', 'gulf times', 'peninsula', 'qatar tribune', 'diwan.gov.qa', 'gco.gov.qa',
                    'qatar news agency', 'qatar day', 'doha news', 'lusail news', 'al-sharq', 'raya',
                    'al-watan', 'qatar living', 'iloveqatar', 'marhaba', 'qatar observer', 'qatar gazette',
                    'qatar chronicle', 'qna', 'thepeninsulaqatar'
                ]
                india_sources = [
                    'times of india', 'the hindu', 'hindustan times', 'indian express', 'ndtv', 'india today',
                    'republic world', 'zee news', 'news18', 'firstpost', 'the wire', 'scroll.in', 'the quint',
                    'business standard', 'economic times', 'livemint', 'moneycontrol', 'ani', 'pti'
                ]
                
                for src in us_sources:
                    if src in platform.lower():
                        country_scores['US'] += 4
                for src in uk_sources:
                    if src in platform.lower():
                        country_scores['UK'] += 4
                for src in qatar_sources:
                    if src in platform.lower():
                        country_scores['Qatar'] += 4
                for src in india_sources:
                    if src in platform.lower():
                        country_scores['India'] += 4
            
            # Check user_location (domain) for news sources
            if user_location:
                if '.com' in user_location or '.org' in user_location or '.net' in user_location or '.qa' in user_location or '.in' in user_location or '.co.in' in user_location:
                    us_domains = ['cnn', 'foxnews', 'nbc', 'abc', 'cbs', 'usatoday', 'nytimes', 'washingtonpost', 'wsj', 'latimes']
                    uk_domains = ['bbc', 'guardian', 'telegraph', 'independent', 'dailymail', 'ft.com', 'economist', 'reuters']
                    qatar_domains = [
                        'aljazeera', 'gulf-times', 'thepeninsulaqatar', 'qatar', 'qna.org.qa', 'dohanews',
                        'qatarliving', 'iloveqatar', 'marhaba.qa', 'qatarday', 'lusailnews', 'alarab.qa',
                        'al-sharq', 'raya', 'al-watan', 'qatargazette', 'qatarchronicle', 'qatarobserver'
                    ]
                    india_domains = [
                        'timesofindia', 'thehindu', 'hindustantimes', 'indianexpress', 'ndtv', 'indiatoday',
                        'republicworld', 'zeenews', 'news18', 'firstpost', 'thewire', 'scroll', 'thequint',
                        'business-standard', 'economictimes', 'livemint', 'moneycontrol', 'aninews', 'ptinews'
                    ]
                    
                    for domain in us_domains:
                        if domain in user_location:
                            country_scores['US'] += 3
                    for domain in uk_domains:
                        if domain in user_location:
                            country_scores['UK'] += 3
                    for domain in qatar_domains:
                        if domain in user_location:
                            country_scores['Qatar'] += 3
                    for domain in india_domains:
                        if domain in user_location:
                            country_scores['India'] += 3
            
            # Check text content for country mentions
            us_terms = ['america', 'american', 'washington', 'new york', 'california', 'texas', 'usa', 'united states', 'white house', 'congress']
            uk_terms = ['britain', 'british', 'london', 'manchester', 'liverpool', 'uk', 'united kingdom', 'england', 'scotland', 'wales', 'parliament']
            qatar_terms = [
                'qatar', 'doha', 'qatari', 'al thani', 'emir', 'gulf', 'middle east', 'arabian',
                'lusail', 'al wakrah', 'al khor', 'education city', 'katara', 'the pearl', 'west bay',
                'aspire', 'hamad', 'khalifa', 'corniche', 'souq waqif', 'msheireb', 'al sadd'
            ]
            india_terms = [ # Reuse or expand from social media list
                'india', 'indian', 'bharat', 'hindustan', 'mumbai', 'delhi', 'bangalore', 'hyderabad', 'chennai', 'kolkata', 'bollywood', 'cricket', 'modi', 'rupee', 'hindi', 'tamil', 'telugu', 'bengali', 'parliament', 'lok sabha', 'rajya sabha', 'supreme court'
            ]
            
            for term in us_terms:
                if term in text:
                    country_scores['US'] += 1
            for term in uk_terms:
                if term in text:
                    country_scores['UK'] += 1
            for term in qatar_terms:
                if term in text:
                    country_scores['Qatar'] += 1
            for term in india_terms:
                if term in text:
                    country_scores['India'] += 1
            
            # Check for language patterns
            language_scores = detect_language_patterns(text)
            for country, score in language_scores.items():
                country_scores[country] += score
            
            # Check for Arabic script in text (strong indicator for Qatar)
            if contains_arabic(text):
                country_scores['Qatar'] += 3
            # Check for Indic script in text (strong indicator for India)
            if contains_indic_script(text):
                country_scores['India'] += 3
        
        # Determine the country with the highest score
        MIN_SCORE_THRESHOLD = 2 # Require at least this score to assign a country
        max_score = max(country_scores.values())
        if max_score >= MIN_SCORE_THRESHOLD:
            # Get the country with the highest score
            for country, score in country_scores.items():
                if score == max_score:
                    return country.lower()
        
        # Default to unknown if no country could be determined
        return 'unknown'

    def load_raw_data(self):
        """Load all raw data files"""
        raw_dir = self.path_manager.data_raw
        all_data = []
        
        # Get all CSV files from raw directory - update glob pattern to include @ files
        csv_files = list(raw_dir.glob("*.csv")) + list(raw_dir.glob("@*.csv"))
        if not csv_files:
            logger.warning("No data files found in raw directory")
            return pd.DataFrame()

        for file_path in csv_files:
            try:
                df = pd.read_csv(file_path)
                
                # Add special handling for Apify data files
                if file_path.name.startswith('@'):
                    file_type = file_path.name.split('_')[0].replace('@', '')
                    
                    if file_type == 'twitter':
                        # Handle Twitter Apify format
                        if 'full_text' in df.columns and 'text' not in df.columns:
                            df.rename(columns={'full_text': 'text'}, inplace=True)
                        if 'created_at' in df.columns and 'date' not in df.columns:
                            df.rename(columns={'created_at': 'date'}, inplace=True)
                        if 'screen_name' in df.columns and 'user_name' not in df.columns:
                            df.rename(columns={'screen_name': 'user_name'}, inplace=True)
                        df['platform'] = 'twitter'
                        df['source'] = 'twitter'
                        
                    elif file_type == 'news':
                        # Handle News Apify format
                        if 'content' in df.columns and 'text' not in df.columns:
                            df.rename(columns={'content': 'text'}, inplace=True)
                        if 'published_date' in df.columns and 'date' not in df.columns:
                            df.rename(columns={'published_date': 'date'}, inplace=True)
                        if 'source_name' in df.columns and 'user_name' not in df.columns:
                            df.rename(columns={'source_name': 'user_name'}, inplace=True)
                        df['platform'] = 'news'
                        df['source'] = 'news'
                
                # Ensure required columns exist
                required_columns = ['source', 'platform', 'date', 'text']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    # Add missing columns with default values
                    for col in missing_columns:
                        if col == 'source' or col == 'platform':
                            df[col] = file_path.stem.split('_')[0].replace('@', '')  # Use filename as source/platform
                        elif col == 'date':
                            df[col] = None
                        elif col == 'text':
                            df[col] = ''
                    logger.warning(f"Added missing columns {missing_columns} to {file_path}")
                
                # Add file info
                df['file_source'] = file_path.stem.split('_')[0].replace('@', '')  # Extract source from filename
                all_data.append(df)
                logger.info(f"Loaded {len(df)} records from {file_path}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

        if not all_data:
            logger.error("No data could be loaded from any files")
            return pd.DataFrame()

        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)
        logger.info(f"Total records loaded: {len(combined_df)}")
        return combined_df

    def populate_user_name(self, df):
        """
        Populate user_name field based on different data sources:
        - X data: "user_name" column
        - Social Searcher data: "platform" column
        - RSS News data: "source" column
        - News Data: Extract domain from "url" column (address between "https://" and "/", removing "www." if present)
        - Mention data: "source_name" column
        """
        logger.info("Populating user_name field based on data sources...")
        
        def extract_domain_from_url(url):
            """
            Extract domain from URL as per requirements:
            - Get the address between "https://" and "/"
            - Remove "www." if present
            Example: "https://www.fark.com/comments/13591050" -> "fark.com"
            """
            if pd.isna(url) or not isinstance(url, str):
                return ""
            
            # Extract domain from URL
            match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            if match:
                domain = match.group(1)
                # Remove www. if present
                domain = re.sub(r'^www\.', '', domain)
                return domain
            else:
                # Try matching just www. pattern
                www_match = re.search(r'www\.([^/]+)', url)
                if www_match:
                    return www_match.group(1)
            return ""
        
        # Process each row to determine user_name
        for idx, row in df.iterrows():
            file_source = row.get('file_source', '').lower()
            # X data (use user_name column directly)
            if file_source == 'x' or file_source == 'twitter':
                # Keep existing value if exists
                if not pd.isna(row.get('user_name')) and row['user_name'] != '':
                    continue
                    
            # Social Searcher data
            elif file_source == 'social':
                if not pd.isna(row.get('user_location')) and row.get('user_location') != '':
                    if "https://" in row['user_location'] or "www." in row['user_location']:
                        domain = extract_domain_from_url(row['user_location'])
                        df.at[idx, 'user_name'] = domain
                    else:
                        df.at[idx, 'user_name'] = row['user_location']
                elif not pd.isna(row.get('platform')):
                    df.at[idx, 'user_name'] = row['platform']
                    
            # RSS News data
            elif file_source == 'rss':
                if not pd.isna(row.get('source')):
                    df.at[idx, 'user_name'] = row['source']
                    
            # News Data
            elif file_source == 'news':
                if not pd.isna(row.get('url')):
                    domain = extract_domain_from_url(row['url'])
                    df.at[idx, 'user_name'] = domain
                    
            # Mention data
            elif file_source == 'mention':
                if not pd.isna(row.get('source_name')):
                    df.at[idx, 'user_name'] = row['source_name']
        
        logger.info(f"User_name population complete. {df['user_name'].notna().sum()} records have user_name values.")
        return df

    def process_data(self):
        """Process and analyze the data"""
        # Load raw data
        df = self.load_raw_data()
        if df.empty:
            logger.error("No data files were found or loaded. Exiting.")
            return False

        logger.info(f"Processing {len(df)} records...")

        # Debug: Count records with date before processing
        date_count_before = df['date'].notna().sum()
        logger.info(f"Records with date before processing: {date_count_before}")

        # Standardize date format
        logger.info("Standardizing dates...")
        df['date'] = df['date'].apply(self.parse_date)

        # Debug: Count records with date after processing
        date_count_after = df['date'].notna().sum()
        logger.info(f"Records with date after processing: {date_count_after}")
        
        # Add default date for records with no date
        if date_count_after < len(df):
            logger.warning(f"Found {len(df) - date_count_after} records with missing dates. Adding default date.")
            default_date = datetime.now().strftime('%Y-%m-%d')
            df['date'] = df['date'].fillna(default_date)
        
        # Filter out records with no text
        df = df[df['text'].notna() & (df['text'] != '')]
        logger.info(f"Records after removing empty text: {len(df)}")
        
        # Add normalized text for duplicate detection (using DeduplicationService)
        dedup_service = DeduplicationService()
        df['normalized_text'] = df['text'].apply(dedup_service.normalize_text)

        # Remove exact duplicates
        df = df.drop_duplicates(subset=['normalized_text'])
        logger.info(f"Records after removing exact duplicates: {len(df)}")

        # Remove similar content using a more efficient approach
        logger.info("Removing similar content (this may take a few minutes)...")
        total_rows = len(df)
        indices_to_drop = set()
        batch_size = 100  # Process in batches to show progress
        
        for idx1 in range(0, total_rows):
            if idx1 % batch_size == 0:
                logger.info(f"Processing similar content removal: {idx1}/{total_rows} records...")
            
            if idx1 in indices_to_drop:
                continue
                
            text1 = df.iloc[idx1]['normalized_text']
            # Only compare with subsequent rows to avoid redundant comparisons
            for idx2 in range(idx1 + 1, min(idx1 + 1000, total_rows)):  # Limit comparison window
                if idx2 in indices_to_drop:
                    continue
                    
                text2 = df.iloc[idx2]['normalized_text']
                # Quick length comparison before doing expensive similarity check
                len_ratio = len(text1) / len(text2) if len(text2) > len(text1) else len(text2) / len(text1)
                if len_ratio < 0.5:  # Skip if lengths are too different
                    continue
                    
                if dedup_service.is_similar_text(text1, text2):
                    # Keep the row with more information (longer text)
                    if len(str(df.iloc[idx1]['text'])) < len(str(df.iloc[idx2]['text'])):
                        indices_to_drop.add(idx1)
                        break
                    else:
                        indices_to_drop.add(idx2)
        
        # Drop the identified indices, ensuring they still exist in the DataFrame
        valid_indices_to_drop = [i for i in indices_to_drop if i in df.index]
        df = df.drop(index=valid_indices_to_drop)
        logger.info(f"Records after removing similar content: {len(df)}")

        # Detect country information
        logger.info("Detecting country information...")
        df['country'] = df.apply(self.detect_country, axis=1)
        logger.info(f"Country distribution: {df['country'].value_counts().to_dict()}")

        # Populate user_name column based on source files
        df = self.populate_user_name(df)
        
        # Apply sentiment analysis with governance classification
        logger.info("Applying dual-analyzer sentiment + classification...")
        
        # Apply analysis with source_type if available
        if 'source_type' in df.columns:
            analysis_results = df.apply(lambda row: self.get_sentiment(row['text'], row.get('source_type')), axis=1)
        else:
            analysis_results = df['text'].apply(lambda text: self.get_sentiment(text, None))
        
        # Extract all fields from the combined result
        df['sentiment_label'] = analysis_results.apply(lambda x: x['sentiment_label'])
        df['sentiment_score'] = analysis_results.apply(lambda x: x['sentiment_score'])
        df['sentiment_justification'] = analysis_results.apply(lambda x: x['sentiment_justification'])
        df['issue_label'] = analysis_results.apply(lambda x: x['issue_label'])
        df['issue_slug'] = analysis_results.apply(lambda x: x['issue_slug'])
        df['ministry_hint'] = analysis_results.apply(lambda x: x['ministry_hint'])
        df['issue_confidence'] = analysis_results.apply(lambda x: x['issue_confidence'])
        df['issue_keywords'] = analysis_results.apply(lambda x: x['issue_keywords'])
        
        logger.info(f"Completed analysis - Ministry distribution: {df['ministry_hint'].value_counts().head().to_dict()}")

        # Drop temporary columns
        df = df.drop(columns=['normalized_text'])

        # Ensure engagement columns exist before applying random values
        for col in ['likes', 'retweets', 'comments']:
            if col not in df.columns:
                logger.warning(f"Column '{col}' not found in DataFrame. Creating it with NA values.")
                df[col] = pd.NA

        df['likes'] = df.apply(lambda row: random.randint(3, 15) if pd.isna(row['likes']) or str(row['likes']).upper() == 'N/A' else row['likes'], axis=1)
        df['retweets'] = df.apply(lambda row: random.randint(1, 8) if pd.isna(row['retweets']) or str(row['retweets']).upper() == 'N/A' else row['retweets'], axis=1)
        df['comments'] = df.apply(lambda row: random.randint(2, 12) if pd.isna(row['comments']) or str(row['comments']).upper() == 'NONE' else row['comments'], axis=1)

        # Convert engagement columns to numeric, coercing errors
        for col in ['likes', 'retweets', 'comments']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        return True

    def process_files(self) -> Optional[pd.DataFrame]:
        logger.debug("DataProcessor.process_files: Entering method.")
        raw_data_dir = self.path_manager.data_raw
        processed_dir = self.path_manager.data_processed
        processed_file_path = processed_dir / "processed_data.csv"

        logger.debug(f"DataProcessor.process_files: Looking for CSVs in {raw_data_dir}")
        csv_files = list(raw_data_dir.glob("*.csv"))
        logger.debug(f"DataProcessor.process_files: Found {len(csv_files)} CSV files: {csv_files}")

        if not csv_files:
            logger.warning("No raw CSV files found to process.")
            logger.debug("DataProcessor.process_files: Exiting method - no files.")
            return None

        all_data = []
        required_columns = {'text', 'id', 'published_date', 'source', 'country'} # Example
        processed_files_record = []

        for file_path in csv_files:
            logger.debug(f"DataProcessor.process_files: Processing file: {file_path}")
            try:
                df = pd.read_csv(file_path)
                logger.debug(f"DataProcessor.process_files: Read {len(df)} rows from {file_path}. Columns: {list(df.columns)}")

                # --- Add more debug logs for cleaning steps --- 
                logger.debug("DataProcessor.process_files: Starting data cleaning steps...")
                # df = self.standardize_columns(df)
                # df = self.handle_missing_values(df)
                # df = self.normalize_dates(df)
                # df = self.deduplicate_data(df)
                logger.debug("DataProcessor.process_files: Finished data cleaning steps.")
                # --- End cleaning logs --- 

                if 'text' in df.columns:
                    texts_to_analyze = df['text'].fillna('').astype(str).tolist()
                    logger.debug(f"DataProcessor.process_files: Extracted {len(texts_to_analyze)} texts for sentiment analysis.")
                    if texts_to_analyze:
                        logger.debug(f"DataProcessor.process_files: Starting batch sentiment analysis...")
                        sentiment_results = self.sentiment_analyzer.batch_analyze(texts_to_analyze)
                        logger.debug(f"DataProcessor.process_files: Batch sentiment analysis completed. Got {len(sentiment_results)} results.")
                        if len(sentiment_results) == len(df):
                             df['sentiment_label'] = [res['sentiment_label'] for res in sentiment_results]
                             df['sentiment_score'] = [res['sentiment_score'] for res in sentiment_results]
                             logger.debug("DataProcessor.process_files: Added sentiment columns to DataFrame.")
                        else:
                            logger.warning(f"Sentiment results count ({len(sentiment_results)}) doesn't match DataFrame rows ({len(df)}). Skipping sentiment assignment for {file_path}.")
                    else:
                        logger.debug("DataProcessor.process_files: No non-empty texts found in this file for analysis.")
                        df['sentiment_label'] = 'neutral' # Assign default if no text
                        df['sentiment_score'] = 0.5
                else:
                    logger.warning(f"Column 'text' not found in {file_path}. Skipping sentiment analysis.")
                    df['sentiment_label'] = 'neutral' # Assign default if no text
                    df['sentiment_score'] = 0.5

                # --- Add enrichment logs --- 
                # df = self.enrich_data(df) # Add logs inside this if it exists
                # --- End enrichment --- 
                
                df['file_source'] = file_path.name # Track source file
                all_data.append(df)
                processed_files_record.append(str(file_path))
                logger.debug(f"DataProcessor.process_files: Added DataFrame from {file_path} to combined list.")

            except Exception as e:
                logger.error(f"Failed to process file {file_path}: {e}", exc_info=True)
                continue # Skip to the next file

        if not all_data:
            logger.warning("No data was successfully processed from any file.")
            logger.debug("DataProcessor.process_files: Exiting method - no data processed.")
            return None

        logger.debug(f"DataProcessor.process_files: Concatenating {len(all_data)} DataFrames...")
        final_df = pd.concat(all_data, ignore_index=True)
        logger.debug(f"DataProcessor.process_files: Concatenated DataFrame shape: {final_df.shape}")

        # Final global deduplication if needed
        # final_df = self.deduplicate_data(final_df, global_scope=True)
        # logger.debug(f"DataProcessor.process_files: DataFrame shape after final deduplication: {final_df.shape}")

        try:
            self.save_processed_data(final_df, processed_file_path)
            logger.info(f"Processed data saved to {processed_file_path}")
            # Rotate processed raw files after successful save
            rotate_processed_files(processed_files_record, raw_data_dir)
        except Exception as e:
            logger.error(f"Failed to save processed data or rotate files: {e}", exc_info=True)
            logger.debug("DataProcessor.process_files: Exiting method - save failed.")
            return None # Indicate failure
            
        logger.debug("DataProcessor.process_files: Finished method successfully.")
        return final_df

    def save_processed_data(self, df: pd.DataFrame, file_path: Path):
        logger.debug(f"DataProcessor.save_processed_data: Entering method. Saving DataFrame (shape: {df.shape}) to {file_path}")
        try:
            df.to_csv(file_path, index=False)
            logger.debug(f"DataProcessor.save_processed_data: Save successful to {file_path}.")
        except Exception as e:
            logger.error(f"Error saving DataFrame to {file_path}: {e}", exc_info=True)
            raise # Re-raise the exception
        logger.debug(f"DataProcessor.save_processed_data: Exiting method.")

if __name__ == "__main__":
    processor = DataProcessor()
    processor.process_data()
