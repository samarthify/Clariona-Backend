import logging
import time
from pathlib import Path
import os
import openai
import requests
import json
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
from dotenv import load_dotenv
from utils.openai_rate_limiter import get_rate_limiter
from utils.multi_model_rate_limiter import get_multi_model_rate_limiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PresidentialSentimentAnalyzer')

class PresidentialSentimentAnalyzer:
    """
    A sentiment analyzer that evaluates content from the President's strategic perspective.
    Instead of general positive/negative sentiment, it classifies content based on:
    - How it affects the President's agenda, image, or political capital
    - Whether it's supportive, threatening, requires attention, or is irrelevant
    """
    
    def __init__(self, president_name: str = "the President", country: str = "Nigeria", model: str = "gpt-5-nano"):
        self.president_name = president_name
        self.country = country
        self.model = model  # Model to use: gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano
        
        # Load environment variables from config/.env
        config_env_path = Path(__file__).parent.parent.parent / "config" / ".env"
        if config_env_path.exists():
            load_dotenv(config_env_path)
            logger.debug(f"Loaded environment variables from {config_env_path}")
        else:
            logger.warning(f"Config .env file not found at {config_env_path}")
        
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
        
        logger.debug(f"Presidential Sentiment Analyzer initialized for {president_name} of {country}")

    def _call_openai_for_presidential_sentiment(self, text: str) -> Tuple[str, float, str, List[str]]:
        """
        Analyze text from the President's strategic perspective using OpenAI.
        Returns: (sentiment_label, sentiment_score, justification, relevant_topics)
        """
        if not self.openai_client:
            logger.warning("OpenAI client not available. Cannot perform presidential analysis.")
            return "neutral", 0.5, "OpenAI client not available", []
        
        prompt = f"""Analyze media from {self.president_name}'s perspective. Evaluate: Does this help or hurt the President's power/reputation/governance?

Categories:
- POSITIVE: Strengthens image/agenda, builds political capital
- NEGATIVE: Threatens image/agenda, creates problems
- NEUTRAL: No material impact

Response format:
Sentiment: [POSITIVE/NEGATIVE/NEUTRAL]
Sentiment Score: [-1.0 to 1.0] (POSITIVE: 0.2-1.0, NEGATIVE: -1.0 to -0.2, NEUTRAL: -0.2 to 0.2)
Justification: [Brief strategic reasoning]
Topics: [comma-separated topics]

Text: "{text[:800]}"
"""
        
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
                            {"role": "system", "content": f"You are a strategic advisor to {self.president_name} analyzing media impact."},
                            {"role": "user", "content": prompt}
                        ],
                        store=False
                    )
                    
                    content = response.output_text.strip()
                    logger.debug(f"OpenAI response: {content}")
                    
                    # Parse the response
                    sentiment = "neutral"  # Default to neutral instead of irrelevant
                    confidence = 0.0  # Default to neutral (0.0) instead of 0.5
                    justification = "Analysis failed"
                    topics = []
                    
                    lines = content.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.lower().startswith("sentiment:"):
                            sentiment_value = line.split(":", 1)[1].strip().lower()
                            if sentiment_value in ["positive", "negative", "neutral"]:
                                sentiment = sentiment_value
                        elif line.lower().startswith("sentiment score:"):
                            try:
                                confidence = float(line.split(":", 1)[1].strip())
                                # Ensure confidence is between -1.0 and 1.0
                                confidence = max(-1.0, min(1.0, confidence))
                            except:
                                confidence = 0.0  # Default to neutral (0.0) instead of 0.5
                        elif line.lower().startswith("justification:"):
                            justification = line.split(":", 1)[1].strip()
                        elif line.lower().startswith("topics:"):
                            topics_str = line.split(":", 1)[1].strip()
                            topics = [t.strip() for t in topics_str.split(",") if t.strip()]
                    
                    # Reset retry count on success
                    multi_model_limiter.reset_retry_count(self.model, request_id)
                    return sentiment, confidence, justification, topics
                    
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
                    logger.error(f"Rate limit error after {max_retries} attempts: {e}")
                    return "neutral", 0.0, f"Rate limit error: {str(e)}", []
                continue
                
            except Exception as e:
                logger.error(f"Error in presidential sentiment analysis: {e}", exc_info=True)
                if attempt == max_retries - 1:
                    return "neutral", 0.0, f"Analysis failed: {str(e)}", []
                time.sleep(1.0)
                continue
        
        return "neutral", 0.0, "Analysis failed after retries", []

    def _identify_relevant_topics(self, text: str) -> List[str]:
        """Identify which presidential priorities are mentioned in the text."""
        text_lower = text.lower()
        relevant_topics = []
        
        for topic, keywords in self.presidential_priorities.items():
            if any(keyword in text_lower for keyword in keywords):
                relevant_topics.append(topic)
        
        return relevant_topics

    def analyze(self, text: str, source_type: str = None) -> Dict[str, Any]:
        """
        Analyze text from the President's strategic perspective.
        
        Returns:
        {
            'sentiment_label': str,  # positive/negative/neutral (using existing field)
            'sentiment_score': float,  # -1.0 to 1.0 (using existing field)
            'sentiment_justification': str,  # Strategic reasoning + recommended action (using existing field)
            'issue_label': str,  # Human-readable issue label (NEW)
            'issue_slug': str,  # URL-friendly identifier (NEW)
            'issue_confidence': float,  # Classification confidence (NEW)
            'issue_keywords': List[str],  # Keywords array (NEW)
            'ministry_hint': str,  # Ministry association hint (NEW)
            'embedding': List[float],  # OpenAI embedding vector (NEW)
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
        
        # Get presidential sentiment analysis
        sentiment, confidence, justification, topics = self._call_openai_for_presidential_sentiment(str(text))
        
        # Generate issue mapping fields (using simple fallback - governance analyzer provides actual labels)
        # Note: We removed _generate_issue_label() API call to save tokens - governance analyzer's label is used instead
        issue_label = topics[0].replace('_', ' ').title() if topics else 'General Issue'
        issue_slug = self._normalize_to_slug(issue_label)
        issue_keywords = self._extract_keywords(text, topics)
        issue_confidence = self._calculate_issue_confidence(text, sentiment, confidence)
        ministry_hint = self._infer_ministry(text, topics)
        
        # Generate recommended action
        recommended_action = self._generate_recommended_action(sentiment, topics, confidence)
        
        # Combine justification and recommended action for the existing sentiment_justification field
        full_justification = f"{justification}\n\nRecommended Action: {recommended_action}"
        
        return {
            'sentiment_label': sentiment,  # Use existing field
            'sentiment_score': confidence,  # Use existing field
            'sentiment_justification': full_justification,  # Use existing field with combined content
            'issue_label': issue_label,  # Simple fallback - governance analyzer's label is used instead
            'issue_slug': issue_slug,  # Simple fallback - governance analyzer's slug is used instead
            'issue_confidence': issue_confidence,  # NEW
            'issue_keywords': issue_keywords,  # NEW
            'ministry_hint': ministry_hint,  # NEW
            'embedding': [0.0] * 1536  # Placeholder - batch embeddings will replace this
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
                model="text-embedding-3-small",
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
            (data['sentiment_score'] < -0.2)
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


