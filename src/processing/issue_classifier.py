"""
Phase 2: Dynamic Issue Classification
Classifies mentions into specific issues within each ministry.
Uses AI to compare and match to existing issue labels (max 20 per ministry).
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import openai
import sys

# Add src to path for imports
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.openai_rate_limiter import get_rate_limiter
from utils.multi_model_rate_limiter import get_multi_model_rate_limiter
from exceptions import AnalysisError, RateLimitError, OpenAIError

# Use centralized logging configuration
try:
    from src.config.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class IssueClassifier:
    """
    Dynamically classifies mentions into issues within a ministry.
    Maintains a list of up to 20 issue labels per ministry.
    """
    
    def __init__(self, storage_dir: str = "ministry_issues", model: str = "gpt-5-nano") -> None:
        """
        Initialize the issue classifier.
        
        Args:
            storage_dir: Directory to store ministry issue label JSON files
            model: Model to use (gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano)
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.model = model  # Model to use for classification
        
        self.openai_client = None
        self.setup_openai()
        
        logger.debug(f"IssueClassifier initialized with storage: {self.storage_dir}, model: {model}")
    
    def setup_openai(self):
        """Initialize OpenAI client if API key is available."""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.openai_client = openai.OpenAI(api_key=api_key)
            logger.debug("OpenAI client initialized for issue classification")
        else:
            logger.warning("OpenAI API key not available for issue classification")
    
    def get_ministry_file(self, ministry: str) -> Path:
        """Get the JSON file path for a ministry's issue labels."""
        return self.storage_dir / f"{ministry}.json"
    
    def load_ministry_issues(self, ministry: str) -> Dict:
        """
        Load existing issue labels for a ministry.
        
        Returns:
            {
                "ministry": "petroleum_resources",
                "issue_count": 3,
                "max_issues": 20,
                "issues": [
                    {
                        "slug": "fuel-subsidy-removal",
                        "label": "Fuel Subsidy Removal",
                        "mention_count": 150,
                        "created_at": "2025-11-02T10:00:00",
                        "last_updated": "2025-11-02T15:30:00"
                    },
                    ...
                ]
            }
        """
        file_path = self.get_ministry_file(ministry)
        
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading issues for {ministry}: {e}")
                return self._create_empty_ministry_data(ministry)
        else:
            return self._create_empty_ministry_data(ministry)
    
    def save_ministry_issues(self, ministry: str, data: Dict):
        """Save ministry issue labels to JSON file."""
        file_path = self.get_ministry_file(ministry)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved issues for {ministry}")
        except Exception as e:
            logger.error(f"Error saving issues for {ministry}: {e}")
    
    def _create_empty_ministry_data(self, ministry: str) -> Dict:
        """Create empty ministry data structure."""
        return {
            "ministry": ministry,
            "issue_count": 0,
            "max_issues": 20,
            "issues": []
        }
    
    def classify_issue(self, text: str, ministry: str) -> Tuple[str, str]:
        """
        Classify a mention into an issue within the ministry.
        
        Args:
            text: The text content to classify
            ministry: The ministry category
        
        Returns:
            (issue_slug, issue_label) tuple
        """
        if not self.openai_client:
            return self._fallback_classification(text, ministry)
        
        # Load existing issues for this ministry
        ministry_data = self.load_ministry_issues(ministry)
        existing_issues = ministry_data.get('issues', [])
        max_issues = ministry_data.get('max_issues', 20)
        
        # If somehow we're over the limit, trim to top N by mention count
        if len(existing_issues) > max_issues:
            logger.warning(f"Ministry {ministry} has {len(existing_issues)} issues, exceeding limit of {max_issues}. Trimming to top {max_issues} by mention count.")
            existing_issues.sort(key=lambda x: x.get('mention_count', 0), reverse=True)
            ministry_data['issues'] = existing_issues[:max_issues]
            ministry_data['issue_count'] = len(ministry_data['issues'])
            self.save_ministry_issues(ministry, ministry_data)
        
        # If no existing issues, create first one
        if not existing_issues:
            return self._create_new_issue(text, ministry, ministry_data)
        
        # If at max capacity (20 issues), use consolidation (no new issues allowed)
        if len(existing_issues) >= max_issues:
            return self._classify_with_consolidation(text, ministry, ministry_data)
        
        # Normal classification: compare to existing issues (may create new if under limit)
        return self._classify_with_comparison(text, ministry, ministry_data)
    
    def _get_issue_classification_prompts(self, text: str, ministry: str, existing_issues: List[Dict], is_consolidation: bool = False) -> Tuple[str, str]:
        """
        Get system message and user prompt from config, with fallback to defaults.
        Returns: (system_message, user_prompt)
        """
        try:
            from config.config_manager import ConfigManager
            config = ConfigManager()
            
            # Get prompt templates from config
            prompt_type = "consolidation" if is_consolidation else "comparison"
            prompt_config = config.get(f"processing.prompts.issue_classification.{prompt_type}", {})
            
            system_message = prompt_config.get("system_message", 
                "You are an expert at categorizing similar content." if not is_consolidation 
                else "You are an expert at categorizing content into existing categories. Always match to existing issues, never create new ones.")
            
            user_template = prompt_config.get("user_template", 
                """Classify this mention into an existing issue or create new one.

Ministry: {ministry}
Text: "{text}"

Existing issues ({issue_count}/20):
{existing_issues_list}

Return JSON:
{{
    "matches_existing": true/false,
    "matched_issue_slug": "slug" or null,
    "new_issue_slug": "new-slug" or null,
    "new_issue_label": "Label" or null,
    "reasoning": "brief"
}}""" if not is_consolidation else """Classify this mention into an EXISTING issue. DO NOT create a new issue.

Ministry: {ministry}
Text: "{text}"

Existing issues ({issue_count}/20 - AT CAPACITY):
{existing_issues_list}

Return JSON:
{{
    "matched_issue_slug": "slug",
    "reasoning": "brief explanation of why this matches"
}}""")
            
            text_truncate_length = prompt_config.get("text_truncate_length", 400)
            max_issues_to_show = prompt_config.get("max_issues_to_show", 10 if not is_consolidation else 15)
            
            # Truncate text
            truncated_text = text[:text_truncate_length] if len(text) > text_truncate_length else text
            
            # Truncate issues list
            truncated_issues = existing_issues[:max_issues_to_show] if len(existing_issues) > max_issues_to_show else existing_issues
            truncated_issues_list = "\n".join([
                f"{i+1}. {issue['slug']}: {issue['label']} ({issue['mention_count']} mentions)"
                for i, issue in enumerate(truncated_issues)
            ])
            
            # Format template with variables
            user_prompt = user_template.format(
                ministry=ministry,
                text=truncated_text,
                issue_count=len(existing_issues),
                existing_issues_list=truncated_issues_list
            )
            
            return system_message, user_prompt
        except Exception as e:
            logger.warning(f"Could not load prompt templates from ConfigManager, using defaults: {e}")
            # Fallback to hardcoded defaults
            truncated_text = text[:400] if len(text) > 400 else text
            max_issues = 15 if is_consolidation else 10
            truncated_issues = existing_issues[:max_issues] if len(existing_issues) > max_issues else existing_issues
            truncated_issues_list = "\n".join([
                f"{i+1}. {issue['slug']}: {issue['label']} ({issue['mention_count']} mentions)"
                for i, issue in enumerate(truncated_issues)
            ])
            
            if is_consolidation:
                system_message = "You are an expert at categorizing content into existing categories. Always match to existing issues, never create new ones."
                user_prompt = f"""Classify this mention into an EXISTING issue. DO NOT create a new issue.

Ministry: {ministry}
Text: "{truncated_text}"

Existing issues ({len(existing_issues)}/20 - AT CAPACITY):
{truncated_issues_list}

Return JSON:
{{
    "matched_issue_slug": "slug",
    "reasoning": "brief explanation of why this matches"
}}
"""
            else:
                system_message = "You are an expert at categorizing similar content."
                user_prompt = f"""Classify this mention into an existing issue or create new one.

Ministry: {ministry}
Text: "{truncated_text}"

Existing issues ({len(existing_issues)}/20):
{truncated_issues_list}

Return JSON:
{{
    "matches_existing": true/false,
    "matched_issue_slug": "slug" or null,
    "new_issue_slug": "new-slug" or null,
    "new_issue_label": "Label" or null,
    "reasoning": "brief"
}}
"""
            return system_message, user_prompt

    def _classify_with_comparison(self, text: str, ministry: str, ministry_data: Dict) -> Tuple[str, str]:
        """Compare new mention to existing issues and decide match or create new."""
        existing_issues = ministry_data['issues']
        
        # Get prompts from config
        system_message, user_prompt = self._get_issue_classification_prompts(text, ministry, existing_issues, is_consolidation=False)
        
        multi_model_limiter = get_multi_model_rate_limiter()
        request_id = f"issue_{id(text)}_{int(time.time())}"
        max_retries = 3
        result = None
        
        for attempt in range(max_retries):
            try:
                # Acquire rate limiter for specific model (blocks if needed)
                # Updated estimate: ~520-870 tokens (optimized prompt, varies by issue count)
                with multi_model_limiter.acquire(self.model, estimated_tokens=800):
                    response = self.openai_client.responses.create(
                        model=self.model,
                        input=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_prompt}
                        ],
                        store=False
                    )
                    
                    result_text = response.output_text.strip()
                    
                    # Parse JSON response
                    if "```json" in result_text:
                        json_start = result_text.find("```json") + 7
                        json_end = result_text.find("```", json_start)
                        result_text = result_text[json_start:json_end].strip()
                    
                    result = json.loads(result_text)
                    
                    # Reset retry count on success
                    multi_model_limiter.reset_retry_count(self.model, request_id)
                    break
                    
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
                        details={"model": self.model, "request_id": request_id, "attempt": attempt + 1, "ministry": ministry}
                    )
                    logger.error(str(rate_limit_error))
                    return self._fallback_classification(text, ministry)
                continue
                
            except openai.APIError as e:
                # Handle OpenAI API errors
                openai_error = OpenAIError(
                    f"OpenAI API error in issue classification: {str(e)}",
                    details={"model": self.model, "request_id": request_id, "attempt": attempt + 1, "ministry": ministry}
                )
                logger.error(str(openai_error))
                if attempt == max_retries - 1:
                    return self._fallback_classification(text, ministry)
                time.sleep(1.0)
                continue
                
            except Exception as e:
                # Handle other unexpected errors
                analysis_error = AnalysisError(
                    f"Unexpected error in issue classification: {str(e)}",
                    details={"model": self.model, "request_id": request_id, "attempt": attempt + 1, "ministry": ministry, "error_type": type(e).__name__}
                )
                logger.error(str(analysis_error), exc_info=True)
                if attempt == max_retries - 1:
                    return self._fallback_classification(text, ministry)
                time.sleep(1.0)
                continue
        
        if result is None:
            return self._fallback_classification(text, ministry)
        
        try:
            if result.get('matches_existing'):
                # Match to existing issue
                slug = result.get('matched_issue_slug')
                # Find the label
                for issue in existing_issues:
                    if issue['slug'] == slug:
                        # Update mention count
                        issue['mention_count'] += 1
                        from datetime import datetime
                        issue['last_updated'] = datetime.now().isoformat()
                        ministry_data['issues'] = existing_issues
                        self.save_ministry_issues(ministry, ministry_data)
                        return slug, issue['label']
                
                # Fallback if slug not found
                return existing_issues[0]['slug'], existing_issues[0]['label']
            
            else:
                # Check if we're already at the limit before creating new issue
                max_issues = ministry_data.get('max_issues', 20)
                if len(existing_issues) >= max_issues:
                    # At limit - find most similar existing issue to match instead
                    logger.debug(f"At max capacity ({max_issues} issues) for {ministry}, matching to existing issue instead of creating new one")
                    # Return the most recently updated issue as fallback
                    most_recent = max(existing_issues, key=lambda x: x.get('last_updated', x.get('created_at', '')))
                    most_recent['mention_count'] += 1
                    from datetime import datetime
                    most_recent['last_updated'] = datetime.now().isoformat()
                    ministry_data['issues'] = existing_issues
                    self.save_ministry_issues(ministry, ministry_data)
                    return most_recent['slug'], most_recent['label']
                
                # Create new issue (only if under limit)
                new_slug = result.get('new_issue_slug', self._generate_slug(text))
                new_label = result.get('new_issue_label', text[:50])
                
                # Add new issue to ministry data
                from datetime import datetime
                now = datetime.now().isoformat()
                new_issue = {
                    'slug': new_slug,
                    'label': new_label,
                    'mention_count': 1,
                    'created_at': now,
                    'last_updated': now
                }
                ministry_data['issues'].append(new_issue)
                ministry_data['issue_count'] = len(ministry_data['issues'])
                self.save_ministry_issues(ministry, ministry_data)
                
                return new_slug, new_label
        
        except AnalysisError:
            # Re-raise analysis errors as-is
            raise
        except Exception as e:
            analysis_error = AnalysisError(
                f"Unexpected error in issue classification: {str(e)}",
                details={"ministry": ministry, "error_type": type(e).__name__}
            )
            logger.error(str(analysis_error), exc_info=True)
            return self._fallback_classification(text, ministry)
    
    def _create_new_issue(self, text: str, ministry: str, ministry_data: Dict) -> Tuple[str, str]:
        """Create the first issue for a ministry."""
        from datetime import datetime
        
        # Generate issue label from text
        slug = self._generate_slug(text)
        label = self._generate_label(text)
        
        now = datetime.now().isoformat()
        new_issue = {
            'slug': slug,
            'label': label,
            'mention_count': 1,
            'created_at': now,
            'last_updated': now
        }
        
        ministry_data['issues'].append(new_issue)
        ministry_data['issue_count'] = 1
        self.save_ministry_issues(ministry, ministry_data)
        
        return slug, label
    
    def _classify_with_consolidation(self, text: str, ministry: str, ministry_data: Dict) -> Tuple[str, str]:
        """
        Handle classification when at 20 issue limit.
        Only matches to existing issues - never creates new ones.
        """
        existing_issues = ministry_data['issues']
        max_issues = ministry_data.get('max_issues', 20)
        
        # If somehow we're over the limit, enforce it by keeping only top N by mention count
        if len(existing_issues) > max_issues:
            logger.warning(f"Ministry {ministry} has {len(existing_issues)} issues, exceeding limit of {max_issues}. Trimming to top {max_issues} by mention count.")
            # Sort by mention count (descending) and keep only top max_issues
            existing_issues.sort(key=lambda x: x.get('mention_count', 0), reverse=True)
            ministry_data['issues'] = existing_issues[:max_issues]
            ministry_data['issue_count'] = len(ministry_data['issues'])
            self.save_ministry_issues(ministry, ministry_data)
        
        # Force match to existing - don't allow new issue creation
        # Use comparison but with a flag to prevent new issue creation
        result = self._classify_with_comparison_forced_match(text, ministry, ministry_data)
        
        return result
    
    def _classify_with_comparison_forced_match(self, text: str, ministry: str, ministry_data: Dict) -> Tuple[str, str]:
        """
        Compare to existing issues but always match to an existing one (never create new).
        Used when at the 20 issue limit.
        """
        existing_issues = ministry_data['issues']
        
        # Get prompts from config (consolidation mode)
        system_message, user_prompt = self._get_issue_classification_prompts(text, ministry, existing_issues, is_consolidation=True)
        
        multi_model_limiter = get_multi_model_rate_limiter()
        request_id = f"issue_forced_{id(text)}_{int(time.time())}"
        max_retries = 3
        result = None
        
        for attempt in range(max_retries):
            try:
                with multi_model_limiter.acquire(self.model, estimated_tokens=800):
                    response = self.openai_client.responses.create(
                        model=self.model,
                        input=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_prompt}
                        ],
                        store=False
                    )
                    
                    result_text = response.output_text.strip()
                    
                    # Parse JSON response
                    if "```json" in result_text:
                        json_start = result_text.find("```json") + 7
                        json_end = result_text.find("```", json_start)
                        result_text = result_text[json_start:json_end].strip()
                    
                    result = json.loads(result_text)
                    multi_model_limiter.reset_retry_count(self.model, request_id)
                    break
                    
            except openai.RateLimitError as e:
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
                    # Fallback to most mentioned issue
                    most_mentioned = max(existing_issues, key=lambda x: x.get('mention_count', 0))
                    return most_mentioned['slug'], most_mentioned['label']
                continue
                
            except Exception as e:
                logger.error(f"Error in forced match classification: {e}")
                if attempt == max_retries - 1:
                    # Fallback to most mentioned issue
                    most_mentioned = max(existing_issues, key=lambda x: x.get('mention_count', 0))
                    return most_mentioned['slug'], most_mentioned['label']
                time.sleep(1.0)
                continue
        
        # Find and update the matched issue
        if result and result.get('matched_issue_slug'):
            slug = result.get('matched_issue_slug')
            for issue in existing_issues:
                if issue['slug'] == slug:
                    issue['mention_count'] += 1
                    from datetime import datetime
                    issue['last_updated'] = datetime.now().isoformat()
                    ministry_data['issues'] = existing_issues
                    self.save_ministry_issues(ministry, ministry_data)
                    return slug, issue['label']
        
        # Fallback: return most mentioned issue
        most_mentioned = max(existing_issues, key=lambda x: x.get('mention_count', 0))
        most_mentioned['mention_count'] += 1
        from datetime import datetime
        most_mentioned['last_updated'] = datetime.now().isoformat()
        ministry_data['issues'] = existing_issues
        self.save_ministry_issues(ministry, ministry_data)
        return most_mentioned['slug'], most_mentioned['label']
    
    def _generate_slug(self, text: str) -> str:
        """Generate a slug from text."""
        words = text.lower().split()[:4]
        slug = '-'.join(w for w in words if len(w) > 3)
        return slug if slug else 'general-issue'
    
    def _generate_label(self, text: str) -> str:
        """Generate a label from text."""
        words = text.split()[:8]
        return ' '.join(words).title()
    
    def _fallback_classification(self, text: str, ministry: str) -> Tuple[str, str]:
        """Fallback classification when OpenAI is not available."""
        slug = self._generate_slug(text)
        label = self._generate_label(text)
        return slug, label








