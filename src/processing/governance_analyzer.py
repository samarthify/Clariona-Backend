"""
Governance-focused analyzer for presidential content.
Maps all content to standardized governance categories and tracks sentiment.
"""

import logging
import os
import openai
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from .governance_categories import (
    FEDERAL_MINISTRIES,
    MINISTRY_SUBCATEGORIES,
    ISSUES_CATEGORIES,
    POSITIVE_CATEGORIES,
    NON_GOVERNANCE_CATEGORIES,
    get_category_label,
    is_governance_category,
    is_issues_category,
    is_positive_category,
    get_category_type,
    map_to_closest_category,
    get_federal_ministries,
    get_ministry_subcategories
)
from utils.openai_rate_limiter import get_rate_limiter
from utils.multi_model_rate_limiter import get_multi_model_rate_limiter

# Use centralized logging configuration
try:
    from src.config.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

# Issue keyword patterns for normalization
ISSUE_PATTERNS = {
    # Petroleum/Energy issues
    "fuel-subsidy-removal": ["subsidy", "removal", "fuel", "petrol", "eliminate"],
    "fuel-price-increase": ["fuel", "price", "increase", "hike", "cost", "expensive"],
    "fuel-scarcity": ["scarcity", "shortage", "queue", "unavailable", "fuel"],
    "oil-theft": ["theft", "pipeline", "vandalism", "steal", "oil"],
    "nnpc-reforms": ["nnpc", "reform", "restructure", "transformation"],
    
    # Security/Interior issues
    "banditry-attacks": ["bandit", "attack", "raid", "armed", "bandits", "zamfara", "katsina", "kaduna"],
    "kidnapping": ["kidnap", "abduct", "hostage", "ransom"],
    "insurgency": ["boko haram", "insurgency", "terrorism", "iswap"],
    "herder-farmer-conflict": ["herder", "farmer", "clash", "cattle", "conflict"],
    "police-brutality": ["police", "brutality", "sars", "abuse", "excessive force"],
    
    # Education issues
    "asuu-strike": ["asuu", "strike", "lecturers", "academic"],
    "school-infrastructure": ["school", "infrastructure", "building", "facility"],
    "education-funding": ["education", "budget", "funding", "allocation"],
    "student-loan": ["student", "loan", "scheme", "nelfund"],
    
    # Health issues
    "healthcare-crisis": ["healthcare", "hospital", "medical", "crisis"],
    "drug-shortage": ["drug", "shortage", "medicine", "unavailable"],
    "doctor-strike": ["doctor", "strike", "medical", "personnel"],
    
    # Economic/Budget issues
    "budget-implementation": ["budget", "implementation", "execution", "2024", "2025"],
    "budget-increase": ["budget", "increase", "raise", "higher"],
    "fiscal-policy": ["fiscal", "policy", "monetary", "economic"],
    "debt-management": ["debt", "loan", "borrowing", "repayment"],
    
    # Foreign Affairs
    "diplomatic-visit": ["visit", "bilateral", "diplomatic", "delegation"],
    "visa-policy": ["visa", "entry", "immigration", "permit"],
    "international-cooperation": ["cooperation", "partnership", "agreement", "treaty"],
    
    # Works/Infrastructure
    "road-construction": ["road", "construction", "highway", "infrastructure"],
    "project-commissioning": ["commission", "project", "inauguration", "launch"],
    
    # Justice
    "corruption-scandal": ["corruption", "scandal", "fraud", "embezzle"],
    "judicial-reform": ["judicial", "reform", "court", "justice"],
    
    # Agriculture
    "food-security": ["food", "security", "agriculture", "farming"],
    "farmer-support": ["farmer", "support", "subsidy", "input"],
    
    # Transportation
    "railway-development": ["railway", "train", "rail", "track"],
    "airport-upgrade": ["airport", "aviation", "upgrade", "terminal"],
    
    # General fallback
    "government-policy": ["policy", "government", "administration"],
    "political-statement": ["statement", "comment", "remark", "political"]
}

def normalize_issue_title(ai_title: str, ministry: str) -> tuple:
    """
    Normalize AI-generated issue title to canonical slug for grouping.
    Returns: (issue_slug, canonical_label)
    """
    if not ai_title:
        return "general-issue", "General Issue"
    
    ai_title_lower = ai_title.lower()
    
    # Score each pattern based on keyword matches
    best_match = None
    best_score = 0
    
    for slug, keywords in ISSUE_PATTERNS.items():
        score = sum(1 for kw in keywords if kw in ai_title_lower)
        if score > best_score:
            best_score = score
            best_match = slug
    
    # If we found a good match (2+ keywords), use it
    if best_match and best_score >= 2:
        # Convert slug to readable label
        canonical_label = best_match.replace("-", " ").title()
        return best_match, canonical_label
    
    # Otherwise, create a slug from the AI title (but group similar ones)
    # Extract key words and create a short slug
    words = ai_title_lower.split()
    # Remove common words
    stop_words = {"the", "a", "an", "in", "on", "at", "for", "to", "of", "and", "or"}
    key_words = [w for w in words if w not in stop_words and len(w) > 3][:3]
    
    if key_words:
        slug = "-".join(key_words)
        return slug, ai_title
    else:
        return "general-issue", ai_title

class GovernanceAnalyzer:
    """
    Analyzes content and maps it to standardized governance categories.
    Phase 1: Ministry classification (36 ministries)
    Phase 2: Issue classification within ministry (dynamic, max 20 per ministry)
    """
    
    def __init__(self, enable_issue_classification: bool = True, model: Optional[str] = None) -> None:
        """
        Initialize the governance analyzer.
        
        Args:
            enable_issue_classification: If True, performs Phase 2 (issue classification)
            model: Model to use (gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano). If None, uses config default.
        """
        self.openai_client = None
        self.enable_issue_classification = enable_issue_classification
        self.issue_classifier = None
        
        # Load default model from ConfigManager if not provided
        if model is None:
            try:
                from config.config_manager import ConfigManager
                config = ConfigManager()
                model = config.get("models.llm_models.default", "gpt-5-nano")
            except Exception as e:
                logger.warning(f"Could not load ConfigManager for default model, using 'gpt-5-nano': {e}")
                model = "gpt-5-nano"
        
        self.model = model  # Model to use for classification
        
        self.setup_openai()
        
        if self.enable_issue_classification:
            from .issue_classifier import IssueClassifier
            self.issue_classifier = IssueClassifier(model=model)
            logger.debug(f"Two-phase classification enabled (Ministry + Issue) with model {model}")
        
    def setup_openai(self):
        """Initialize OpenAI client if API key is available."""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.openai_client = openai.OpenAI(api_key=api_key)
            logger.debug("OpenAI client initialized for governance analysis")
        else:
            logger.warning("OpenAI API key not available for governance analysis")
    
    def analyze(self, text: str, source_type: Optional[str] = None, sentiment: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze text and return governance category and metadata.
        
        Phase 1: Classify into ministry
        Phase 2 (optional): Classify into specific issue within ministry
        
        Args:
            text: Text to analyze
            source_type: Source type (e.g., 'twitter', 'news')
            sentiment: Pre-computed sentiment from Presidential Analyzer ('positive', 'negative', or 'neutral')
        
        Returns:
            {
                'governance_category': 'fuel-subsidy-removal',  # issue_slug (or ministry if Phase 2 disabled)
                'category_label': 'Fuel Subsidy Removal',  # issue_label (or ministry name if Phase 2 disabled)
                'ministry_category': 'petroleum_resources',  # ministry
                'ministry_hint': 'petroleum_resources',  # ministry for filtering
                'category_type': 'non_governance',
                'sentiment': 'negative',  # Passed from Presidential Analyzer
                'sentiment_score': 0.8,  # Passed from Presidential Analyzer
                'governance_relevance': 0.9,
                'confidence': 0.85,
                'keywords': ['budget', 'economy', 'finance'],
                'embedding': [...],
                'is_governance_content': True,
                'page_type': 'issues'  # 'issues' or 'positive_coverage' (determined by sentiment)
            }
        """
        if not text or not text.strip():
            return self._get_default_result(sentiment=sentiment)
        
        try:
            # Phase 1: Ministry classification
            if self.openai_client:
                result = self._analyze_with_openai(text, source_type, sentiment)
            else:
                result = self._analyze_fallback(text, source_type, sentiment)
            
            # Phase 2: Issue classification (if enabled)
            if self.enable_issue_classification and self.issue_classifier:
                ministry = result.get('ministry_hint', 'non_governance')
                if ministry != 'non_governance':
                    issue_slug, issue_label = self.issue_classifier.classify_issue(text, ministry)
                    result['governance_category'] = issue_slug
                    result['category_label'] = issue_label
                    logger.debug(f"Phase 2: Classified into issue '{issue_slug}' under ministry '{ministry}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in governance analysis: {e}")
            return self._get_default_result(error=str(e), sentiment=sentiment)
    
    def _analyze_with_openai(self, text: str, source_type: str = None, sentiment: str = None) -> Dict[str, Any]:
        """Analyze using OpenAI API."""
        
        # Get prompts from config
        system_message, user_prompt = self._get_governance_prompts(text)
        
        multi_model_limiter = get_multi_model_rate_limiter()
        request_id = f"gov_{id(text)}_{int(time.time())}"
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Acquire rate limiter for specific model (blocks if needed)
                # Updated estimate: ~930-1230 tokens (optimized prompt)
                with multi_model_limiter.acquire(self.model, estimated_tokens=1200):
                    # Get governance category (ministry classification only)
                    response = self.openai_client.responses.create(
                        model=self.model,
                        input=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_prompt}
                        ],
                        store=False
                    )
                    
                    result_text = response.output_text.strip()
                    analysis = self._parse_openai_response(result_text, sentiment)
                    
                    # Use placeholder embedding - batch embeddings will replace this
                    analysis['embedding'] = [0.0] * 1536
                    
                    # Reset retry count on success
                    multi_model_limiter.reset_retry_count(self.model, request_id)
                    
                    return analysis
                    
            except openai.RateLimitError as e:
                # Handle rate limit error
                retry_after = None
                if hasattr(e, 'response') and e.response is not None:
                    # Try to extract retry_after from response
                    try:
                        error_body = e.response.json() if hasattr(e.response, 'json') else {}
                        if 'error' in error_body and 'message' in error_body['error']:
                            message = error_body['error']['message']
                            # Extract retry_after from message if present
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
                    return self._analyze_fallback(text, source_type, sentiment)
                continue
                
            except openai.APIError as e:
                # Handle OpenAI API errors
                openai_error = OpenAIError(
                    f"OpenAI API error in governance analysis: {str(e)}",
                    details={"model": self.model, "request_id": request_id, "attempt": attempt + 1}
                )
                logger.error(str(openai_error))
                if attempt == max_retries - 1:
                    return self._analyze_fallback(text, source_type, sentiment)
                time.sleep(1.0)
                continue
                
            except Exception as e:
                # Handle other unexpected errors
                analysis_error = AnalysisError(
                    f"Unexpected error in governance analysis: {str(e)}",
                    details={"model": self.model, "request_id": request_id, "attempt": attempt + 1, "error_type": type(e).__name__}
                )
                logger.error(str(analysis_error), exc_info=True)
                if attempt == max_retries - 1:
                    return self._analyze_fallback(text, source_type, sentiment)
                time.sleep(1.0)
                continue
        
        return self._analyze_fallback(text, source_type, sentiment)
    
    def _get_governance_prompts(self, text: str) -> Tuple[str, str]:
        """
        Get system message and user prompt from config, with fallback to defaults.
        Returns: (system_message, user_prompt)
        """
        try:
            from config.config_manager import ConfigManager
            config = ConfigManager()
            
            # Get prompt templates from config
            prompt_config = config.get("processing.prompts.governance", {})
            system_message = prompt_config.get("system_message", "You are a governance analyst specializing in Nigerian politics and policy.")
            user_template = prompt_config.get("user_template", """Categorize this Nigerian governance text into ONE federal ministry.

Text: "{text}"

Ministries (use exact key):
1. agriculture_food_security 2. aviation_aerospace 3. budget_economic_planning 4. communications_digital 5. defence 6. education 7. environment_ecological 8. finance 9. foreign_affairs 10. health_social_welfare 11. housing_urban 12. humanitarian_poverty 13. industry_trade 14. interior 15. justice 16. labour_employment 17. marine_blue_economy 18. niger_delta 19. petroleum_resources 20. power 21. science_technology 22. solid_minerals 23. sports_development 24. tourism 25. transportation 26. water_resources 27. women_affairs 28. works 29. youth_development 30. livestock_development 31. information_culture 32. police_affairs 33. steel_development 34. special_duties 35. fct_administration 36. art_culture_creative 37. non_governance

Return JSON:
{{
    "ministry_category": "exact_key",
    "governance_relevance": 0.0-1.0,
    "confidence": 0.0-1.0,
    "keywords": ["kw1", "kw2"],
    "reasoning": "brief"
}}""")
            text_truncate_length = prompt_config.get("text_truncate_length", 800)
            
            # Truncate text
            truncated_text = text[:text_truncate_length] if len(text) > text_truncate_length else text
            
            # Format template with variables
            user_prompt = user_template.format(text=truncated_text)
            
            return system_message, user_prompt
        except Exception as e:
            logger.warning(f"Could not load prompt templates from ConfigManager, using defaults: {e}")
            # Fallback to hardcoded defaults
            truncated_text = text[:800] if len(text) > 800 else text
            system_message = "You are a governance analyst specializing in Nigerian politics and policy."
            user_prompt = f"""Categorize this Nigerian governance text into ONE federal ministry.

Text: "{truncated_text}"

Ministries (use exact key):
1. agriculture_food_security 2. aviation_aerospace 3. budget_economic_planning 4. communications_digital 5. defence 6. education 7. environment_ecological 8. finance 9. foreign_affairs 10. health_social_welfare 11. housing_urban 12. humanitarian_poverty 13. industry_trade 14. interior 15. justice 16. labour_employment 17. marine_blue_economy 18. niger_delta 19. petroleum_resources 20. power 21. science_technology 22. solid_minerals 23. sports_development 24. tourism 25. transportation 26. water_resources 27. women_affairs 28. works 29. youth_development 30. livestock_development 31. information_culture 32. police_affairs 33. steel_development 34. special_duties 35. fct_administration 36. art_culture_creative 37. non_governance

Return JSON:
{{
    "ministry_category": "exact_key",
    "governance_relevance": 0.0-1.0,
    "confidence": 0.0-1.0,
    "keywords": ["kw1", "kw2"],
    "reasoning": "brief"
}}
"""
            return system_message, user_prompt

    def _create_governance_prompt(self, text: str, source_type: str = None) -> str:
        """Create prompt for governance analysis with 36 federal ministry categories."""
        _, user_prompt = self._get_governance_prompts(text)
        return user_prompt
    
    def _parse_openai_response(self, response_text: str, sentiment: str = None) -> Dict[str, Any]:
        """Parse OpenAI response and return structured data."""
        try:
            # Try to extract JSON from response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text
            
            # Parse JSON
            analysis = json.loads(json_text)
            
            # Get ministry category only (Phase 1: Ministry classification only)
            ministry_category = analysis.get('ministry_category', 'non_governance')
            
            # Use passed sentiment from Presidential Analyzer (default to neutral if not provided)
            sentiment = sentiment or 'neutral'
            
            # Validate ministry category
            if ministry_category not in FEDERAL_MINISTRIES and ministry_category != 'non_governance':
                ministry_category = 'non_governance'
            
            # Get ministry display name
            ministry_label = FEDERAL_MINISTRIES.get(ministry_category, 'Non-Governance Content')
            
            # Determine category type and page type
            category_type = get_category_type(ministry_category)
            
            # Determine page type based on sentiment (from Presidential Analyzer)
            if sentiment == 'negative':
                page_type = 'issues'
            elif sentiment == 'positive':
                page_type = 'positive_coverage'
            else:
                page_type = 'issues'  # Default to issues for neutral
            
            result = {
                'governance_category': ministry_category,  # Ministry slug (will be used for issue_slug in Phase 1)
                'category_label': ministry_label,  # Ministry display name (will be used for issue_label in Phase 1)
                'ministry_category': ministry_category,  # Ministry category
                'ministry_hint': ministry_category,  # Ministry for filtering
                'category_type': category_type,
                'sentiment': sentiment,  # From Presidential Analyzer
                'sentiment_score': 0.5,  # Placeholder (actual score comes from Presidential Analyzer)
                'governance_relevance': float(analysis.get('governance_relevance', 0.0)),
                'confidence': float(analysis.get('confidence', 0.5)),
                'keywords': analysis.get('keywords', []),
                'reasoning': analysis.get('reasoning', ''),
                'is_governance_content': float(analysis.get('governance_relevance', 0.0)) >= 0.3,
                'page_type': page_type
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing OpenAI response: {e}")
            return self._get_default_result(error=f"Parse error: {e}", sentiment=sentiment)
    
    def _get_embedding_model(self) -> str:
        """Get embedding model name from ConfigManager."""
        try:
            from config.config_manager import ConfigManager
            config = ConfigManager()
            return config.get("models.embedding_model", "text-embedding-3-small")
        except Exception:
            return "text-embedding-3-small"
    
    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text."""
        try:
            if self.openai_client:
                rate_limiter = get_rate_limiter()
                # Embeddings: ~2200 tokens (1536 dims × ~1.3 tokens per dim)
                with rate_limiter.acquire(estimated_tokens=2200):
                    response = self.openai_client.embeddings.create(
                        model=self._get_embedding_model(),
                        input=text[:8000]  # Limit text length
                    )
                    return response.data[0].embedding
            else:
                # Return zero vector if no OpenAI client
                return [0.0] * 1536
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return [0.0] * 1536
    
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
    
    def _analyze_fallback(self, text: str, source_type: str = None, sentiment: str = None) -> Dict[str, Any]:
        """Fallback analysis when OpenAI is not available."""
        
        # Basic keyword-based categorization
        text_lower = text.lower()
        
        # Simple keyword matching for basic categories
        # Map keywords to federal ministry keys
        ministry_keywords = {
            'budget_economic_planning': ['economy', 'budget', 'economic', 'fiscal', 'monetary', 'inflation'],
            'works': ['infrastructure', 'road', 'bridge', 'construction', 'development', 'project'],
            'education': ['education', 'school', 'university', 'student', 'teacher', 'learning'],
            'health_social_welfare': ['health', 'hospital', 'medical', 'healthcare', 'doctor', 'medicine'],
            'interior': ['security', 'police', 'crime', 'safety', 'law enforcement', 'terrorism'],
            'agriculture_food_security': ['agriculture', 'farming', 'food', 'crop', 'farm', 'agricultural'],
            'power': ['energy', 'power', 'electricity', 'renewable'],
            'petroleum_resources': ['oil', 'gas', 'petroleum', 'fuel'],
            'transportation': ['transport', 'transportation', 'traffic', 'vehicle', 'mobility'],
            'housing_urban': ['housing', 'house', 'home', 'residential', 'urban development'],
            'environment_ecological': ['environment', 'climate', 'pollution', 'conservation', 'green'],
            'finance': ['finance', 'banking', 'financial', 'bank'],
            'foreign_affairs': ['foreign', 'diplomacy', 'international', 'embassy'],
            'justice': ['justice', 'court', 'legal', 'judiciary', 'corruption'],
            'defence': ['defense', 'military', 'armed forces', 'war'],
            'labour_employment': ['employment', 'job', 'work', 'labour', 'unemployment'],
            'water_resources': ['water', 'sanitation', 'irrigation'],
            'women_affairs': ['women', 'gender', 'female', 'equality'],
            'youth_development': ['youth', 'young', 'teenager', 'adolescent'],
            'science_technology': ['technology', 'science', 'innovation', 'digital'],
            'communications_digital': ['communication', 'telecom', 'digital', 'cyber']
        }
        
        # Find best matching category
        best_ai_suggestion = 'non_governance'
        max_matches = 0
        
        for category, keywords in ministry_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            if matches > max_matches:
                max_matches = matches
                best_ai_suggestion = category
        
        # Use the best category directly (Phase 1: Ministry only)
        ministry_category = best_ai_suggestion
        ministry_label = FEDERAL_MINISTRIES.get(ministry_category, 'Non-Governance Content')
        
        # Use passed sentiment from Presidential Analyzer (default to neutral if not provided)
        sentiment = sentiment or 'neutral'
        
        # Determine category type and page type
        category_type = get_category_type(ministry_category)
        
        if sentiment == 'negative':
            page_type = 'issues'
        elif sentiment == 'positive':
            page_type = 'positive_coverage'
        else:
            page_type = 'issues'  # Default to issues for neutral
        
        return {
            'governance_category': ministry_category,  # Ministry slug
            'category_label': ministry_label,  # Ministry display name
            'ministry_category': ministry_category,  # Ministry category
            'ministry_hint': ministry_category,  # Ministry for filtering
            'category_type': category_type,
            'sentiment': sentiment,  # From Presidential Analyzer
            'sentiment_score': 0.5,  # Placeholder (actual score comes from Presidential Analyzer)
            'governance_relevance': 0.5 if ministry_category != 'non_governance' else 0.1,
            'confidence': 0.6,
            'keywords': [],
            'reasoning': 'Fallback analysis',
            'is_governance_content': ministry_category != 'non_governance',
            'page_type': page_type,
            'embedding': [0.0] * 1536
        }
    
    def _get_default_result(self, error: str = None, sentiment: str = None) -> Dict[str, Any]:
        """Return default result for errors or empty content."""
        # Use passed sentiment or default to neutral
        sentiment = sentiment or 'neutral'
        
        # Determine page type based on sentiment
        if sentiment == 'negative':
            page_type = 'issues'
        elif sentiment == 'positive':
            page_type = 'positive_coverage'
        else:
            page_type = 'issues'  # Default to issues
        
        return {
            'governance_category': 'non_governance',  # Ministry slug
            'category_label': 'Non-Governance Content',  # Ministry display name
            'ministry_category': 'non_governance',  # Ministry category
            'ministry_hint': 'non_governance',  # Ministry for filtering
            'category_type': 'non_governance',
            'sentiment': sentiment,  # From Presidential Analyzer
            'sentiment_score': 0.5,  # Placeholder
            'governance_relevance': 0.0,
            'confidence': 0.0,
            'keywords': [],
            'reasoning': error or 'No content to analyze',
            'is_governance_content': False,
            'page_type': page_type,
            'embedding': [0.0] * 1536
        }
