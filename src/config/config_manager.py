"""
Centralized configuration management.

Loads configuration from JSON files, environment variables, and provides
type-safe accessors with dot-notation support.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from dotenv import load_dotenv
import logging
from datetime import datetime

import sys
from pathlib import Path

# Add src to path for imports
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from exceptions import ConfigError, DatabaseError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Try to import jsonschema for validation (optional)
try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    logger.debug("jsonschema not available - schema validation disabled")


class ConfigManager:
    """
    Centralized configuration management.
    
    Loads configuration from:
    1. Default values (hardcoded in class)
    2. JSON config files (config/ directory)
    3. Environment variables (highest priority)
    
    Provides type-safe accessors and dot-notation key access.
    """
    
    def __init__(
        self,
        config_dir: Optional[Path] = None,
        base_path: Optional[Path] = None,
        validate: bool = True,
        use_database: bool = False,
        db_session: Optional["Session"] = None
    ):
        """
        Initialize ConfigManager.
        
        Args:
            config_dir: Directory containing config files. Defaults to config/ relative to base_path.
            base_path: Base path of the project. Defaults to project root (3 levels up from this file).
            validate: Whether to validate config against schema (requires jsonschema package).
            use_database: Whether to load configuration from database instead of files.
            db_session: Database session (required if use_database=True).
        """
        # Calculate base path if not provided
        if base_path is None:
            # This file is at src/config/config_manager.py, so go up 3 levels to project root
            base_path = Path(__file__).parent.parent.parent
        
        self.base_path = base_path.resolve()
        
        # Set config directory
        if config_dir is None:
            config_dir = self.base_path / "config"
        else:
            config_dir = Path(config_dir).resolve()
        
        self.config_dir = config_dir
        self._validate = validate and JSONSCHEMA_AVAILABLE
        self.use_database = use_database
        self.db_session = db_session
        
        # Validate database parameters
        if use_database and db_session is None:
            raise ConfigError(
                "use_database=True but db_session is None",
                details={"use_database": use_database, "db_session": None}
            )
        
        self.use_database = use_database
        
        # Load environment variables
        self._load_environment_variables()
        
        # Initialize config with defaults
        self._config: Dict[str, Any] = self._get_default_config()
        
        # Load config from database or files
        if use_database:
            try:
                self._load_from_database()
                logger.debug("ConfigManager loaded configuration from database")
            except DatabaseError:
                # Re-raise database errors as-is
                raise
            except Exception as e:
                logger.warning(f"Failed to load config from database: {e}, falling back to files")
                self._load_config_files()
                self.use_database = False  # Disable DB mode on error
        else:
            self._load_config_files()
        
        # Apply environment variable overrides (always highest priority)
        self._apply_env_overrides()
        
        # Validate config if requested
        if self._validate:
            self._validate_config()
        
        logger.debug(f"ConfigManager initialized. Config dir: {self.config_dir}, Base path: {self.base_path}, DB mode: {self.use_database}")
    
    def _load_environment_variables(self):
        """Load environment variables from .env files."""
        # Try config/.env first
        config_env_path = self.config_dir / ".env"
        if config_env_path.exists():
            load_dotenv(dotenv_path=config_env_path, override=False)
            logger.debug(f"Loaded .env from {config_env_path}")
        
        # Also load from system environment (for Railway deployment, etc.)
        load_dotenv(override=False)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration values.
        
        These are the fallback values if not specified in config files or env vars.
        """
        return {
            "paths": {
                "base": ".",
                "data_raw": "data/raw",
                "data_processed": "data/processed",
                "logs": "logs",
                "logs_agent": "logs/agent.log",
                "logs_scheduling": "logs/automatic_scheduling.log",
                "logs_collectors": "logs/collectors",
                "logs_openai": "logs/openai_calls.csv",
                "config_agent": "config/agent_config.json",
                "config_topic_embeddings": "config/topic_embeddings.json"
            },
            "processing": {
                "parallel": {
                    "max_collector_workers": 8,
                    "max_sentiment_workers": 20,
                    "max_location_workers": 8,
                    "sentiment_batch_size": 150,
                    "location_batch_size": 300
                },
                "timeouts": {
                    "collector_timeout_seconds": 1000,
                    "apify_timeout_seconds": 600,
                    "apify_wait_seconds": 600,
                    "lock_max_age_seconds": 300,
                    "scheduler_join_timeout": 10,
                    "scheduler_timeout": 30,
                    "http_request_timeout": 120
                },
                "limits": {
                    "max_records_per_batch": 500
                },
                "topic": {
                    "min_score_threshold": 0.2,
                    "confidence_threshold": 0.85,
                    "keyword_score_threshold": 0.3,
                    "embedding_score_threshold": 0.5
                },
                "sentiment": {
                    "positive_threshold": 0.2,
                    "negative_threshold": -0.2,
                    "default_neutral_score": 0.5
                },
                "prompts": {
                    "presidential_sentiment": {
                        "system_message": "You are a strategic advisor to {president_name} analyzing media impact.",
                        "user_template": """Analyze media from {president_name}'s perspective. Evaluate: Does this help or hurt the President's power/reputation/governance?

Categories:
- POSITIVE: Strengthens image/agenda, builds political capital
- NEGATIVE: Threatens image/agenda, creates problems
- NEUTRAL: No material impact

Response format:
Sentiment: [POSITIVE/NEGATIVE/NEUTRAL]
Sentiment Score: [-1.0 to 1.0] (POSITIVE: 0.2-1.0, NEGATIVE: -1.0 to -0.2, NEUTRAL: -0.2 to 0.2)
Justification: [Brief strategic reasoning]
Topics: [comma-separated topics]

Text: "{text}"
""",
                        "text_truncate_length": 800
                    },
                    "governance": {
                        "system_message": "You are a governance analyst specializing in Nigerian politics and policy.",
                        "user_template": """Categorize this Nigerian governance text into ONE federal ministry.

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
}}""",
                        "text_truncate_length": 800
                    },
                    "issue_classification": {
                        "comparison": {
                            "system_message": "You are an expert at categorizing similar content.",
                            "user_template": """Classify this mention into an existing issue or create new one.

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
}}""",
                            "text_truncate_length": 400,
                            "max_issues_to_show": 10
                        },
                        "consolidation": {
                            "system_message": "You are an expert at categorizing content into existing categories. Always match to existing issues, never create new ones.",
                            "user_template": """Classify this mention into an EXISTING issue. DO NOT create a new issue.

Ministry: {ministry}
Text: "{text}"

Existing issues ({issue_count}/20 - AT CAPACITY):
{existing_issues_list}

Return JSON:
{{
    "matched_issue_slug": "slug",
    "reasoning": "brief explanation of why this matches"
}}""",
                            "text_truncate_length": 400,
                            "max_issues_to_show": 15
                        }
                    }
                },
                "prompt_variables": {
                    "president_name": "Bola Ahmed Tinubu",
                    "country": "Nigeria"
                }
            },
            "deduplication": {
                "similarity_threshold": 0.85,
                "length_ratio_threshold": 0.5
            },
            "collectors": {
                "apify": {
                    "default_date_range_days": 7,
                    "default_since_date": "2021-01-01_00:00:00_UTC",
                    "twitter": {
                        "min_retweets": 0,
                        "min_faves": 0,
                        "min_replies": 0,
                        "filter_verified": False,
                        "filter_blue_verified": False,
                        "filter_nativeretweets": False,
                        "include_nativeretweets": False,
                        "filter_replies": False,
                        "filter_quote": False,
                        "filter_media": False,
                        "filter_images": False,
                        "filter_videos": False
                    },
                    "tiktok": {
                        "default_oldest_post_date": "1 day"
                    }
                },
                "incremental": {
                    "twitter": {
                        "default_lookback_days": 3,
                        "max_lookback_days": 14,
                        "overlap_hours": 2
                    },
                    "news": {
                        "default_lookback_days": 7,
                        "max_lookback_days": 30,
                        "overlap_hours": 6
                    },
                    "facebook": {
                        "default_lookback_days": 3,
                        "max_lookback_days": 14,
                        "overlap_hours": 2
                    },
                    "instagram": {
                        "default_lookback_days": 3,
                        "max_lookback_days": 14,
                        "overlap_hours": 2
                    },
                    "tiktok": {
                        "default_lookback_days": 3,
                        "max_lookback_days": 14,
                        "overlap_hours": 2
                    },
                    "reddit": {
                        "default_lookback_days": 3,
                        "max_lookback_days": 14,
                        "overlap_hours": 2
                    },
                    "radio": {
                        "default_lookback_days": 7,
                        "max_lookback_days": 30,
                        "overlap_hours": 6
                    },
                    "youtube": {
                        "default_lookback_days": 7,
                        "max_lookback_days": 30,
                        "overlap_hours": 6
                    },
                    "rss": {
                        "default_lookback_days": 7,
                        "max_lookback_days": 30,
                        "overlap_hours": 6
                    },
                    "default": {
                        "default_lookback_days": 7,
                        "max_lookback_days": 30,
                        "overlap_hours": 2
                    }
                },
                "rss": {
                    "feed_timeout_seconds": 30,
                    "overall_timeout_seconds": 600,
                    "max_retries": 3,
                    "delay_between_feeds_seconds": 1,
                    "feed_buffer_seconds": 5
                },
                "radio": {
                    "http_timeout_seconds": 15,
                    "request_delay_seconds": 2,
                    "max_retries": 3,
                    "retry_delay_seconds": 2,
                    "max_pages": 5,
                    "max_articles_per_page": 25
                },
                "radio_gnews": {
                    "http_timeout_seconds": 30,
                    "delay_between_requests_seconds": 1
                },
                "youtube": {
                    "delay_between_requests_seconds": 0.1,
                    "delay_between_pages_seconds": 1
                },
                "instagram": {
                    "default_max_results": 100,
                    "default_results_limit": 50,
                    "default_search_limit": 10
                },
                "tiktok": {
                    "default_max_results": 100,
                    "subtitle_timeout_seconds": 10,
                    "delay_between_runs_seconds": 3,
                    "delay_between_actors_seconds": 5
                },
                "twitter": {
                    "default_max_items": 100
                },
                "news_apify": {
                    "delay_between_queries_seconds": 2,
                    "delay_between_actors_seconds": 5
                },
                "social_searcher": {
                    "default_max_pages": 5,
                    "delay_between_requests_seconds": 2
                },
                "rss_validator": {
                    "timeout_seconds": 10
                },
                "rss_health_monitor": {
                    "timeout_seconds": 10
                },
                "keywords": {
                    "default": {
                        "youtube": ["emir", "amir", "sheikh tamim", "al thani"],
                        "radio_hybrid": ["nigeria", "government", "politics", "economy", "news"],
                        "radio_gnews": ["nigeria", "government", "politics", "economy", "news"],
                        "radio_stations": ["nigeria", "government", "politics", "economy", "news"],
                        "rss": ["middle east", "qatar", "nigeria", "gulf", "arab", "islamic", "oil", "energy", "politics", "diplomacy", "trade", "business"],
                        "rss_nigerian_qatar_indian": ["nigeria", "qatar", "india", "africa", "middle east", "gulf", "arab", "nigerian", "qatari", "indian", "politics", "business", "economy", "oil", "gas", "energy", "trade", "diplomacy"],
                        "youtube_default_fallback": ["emir"],
                        "news_from_api": ["Asiwaju Bola Ahmed Adekunle Tinubu", "President of the Federal Republic of Nigeria", "Bola Tinubu", "Bola Ahmed Tinubu", "President of Nigeria", "Tinubu", "Bola", "nigeria"],
                        "instagram": ["qatar", "doha", "sheikh tamim", "nigeria", "lagos", "abuja"],
                        "tiktok": ["nigeria", "tinubu", "lagos", "qatar", "doha"],
                        "twitter": ["qatar", "nigeria", "india", "politics", "news"],
                        "facebook": ["qatar", "nigeria", "india", "news", "politics"],
                        "news_apify": ["qatar", "nigeria", "india", "politics", "news", "government"]
                    }
                },
                # Legacy key for backward compatibility
                "default_keywords": {
                    "youtube": ["emir", "amir", "sheikh tamim", "al thani"],
                    "radio_hybrid": ["nigeria", "government", "politics", "economy", "news"],
                    "radio_gnews": ["nigeria", "government", "politics", "economy", "news"],
                    "radio_stations": ["nigeria", "government", "politics", "economy", "news"],
                    "rss": ["middle east", "qatar", "nigeria", "gulf", "arab", "islamic", "oil", "energy", "politics", "diplomacy", "trade", "business"],
                    "rss_nigerian_qatar_indian": ["nigeria", "qatar", "india", "africa", "middle east", "gulf", "arab", "nigerian", "qatari", "indian", "politics", "business", "economy", "oil", "gas", "energy", "trade", "diplomacy"],
                    "youtube_default_fallback": ["emir"],
                    "news_from_api": ["Asiwaju Bola Ahmed Adekunle Tinubu", "President of the Federal Republic of Nigeria", "Bola Tinubu", "Bola Ahmed Tinubu", "President of Nigeria", "Tinubu", "Bola", "nigeria"],
                    "instagram": ["qatar", "doha", "sheikh tamim", "nigeria", "lagos", "abuja"],
                    "tiktok": ["nigeria", "tinubu", "lagos", "qatar", "doha"],
                    "twitter": ["qatar", "nigeria", "india", "politics", "news"],
                    "facebook": ["qatar", "nigeria", "india", "news", "politics"],
                    "news_apify": ["qatar", "nigeria", "india", "politics", "news", "government"]
                },
                "source_to_collector_mapping": {
                    "news": ["collect_news_from_api", "collect_news_apify"],
                    "twitter": ["collect_twitter_apify"],
                    "facebook": ["collect_facebook_apify"],
                    "rss": ["collect_rss_nigerian_qatar_indian"],
                    "youtube": ["collect_youtube_api"],
                    "radio": ["collect_radio_hybrid"],
                    "reddit": ["collect_reddit_apify"],
                    "instagram": ["collect_instagram_apify"],
                    "tiktok": ["collect_tiktok_apify"],
                    "linkedin": ["collect_linkedin"]
                }
            },
            "database": {
                "pool_size": 30,
                "max_overflow": 20,
                "pool_recycle_seconds": 3600,
                "pool_timeout_seconds": 60
            },
            "api": {
                "cors_origins": [
                    "http://localhost:3000",
                    "http://localhost:3001",
                    "http://13.202.48.110:3000",
                    "http://13.202.48.110:3001",
                    "https://*.railway.app",
                    "https://*.up.railway.app"
                ],
                "timeouts": {
                    "http_request_timeout": 60
                },
                "pagination": {
                    "default_limit": 100
                }
            },
            "models": {
                "string_lengths": {
                    "short": 50,
                    "medium": 100,
                    "long": 200,
                    "very_long": 500,
                    "password_hash": 255,
                    "config_key": 255
                },
                "embedding_model": "text-embedding-3-small",
                "llm_models": {
                    "default": "gpt-5-nano",
                    "available": ["gpt-5-mini", "gpt-5-nano", "gpt-4.1-mini", "gpt-4.1-nano"],
                    "tpm_capacities": {
                        "gpt-5-mini": 500000,
                        "gpt-5-nano": 200000,
                        "gpt-4.1-mini": 200000,
                        "gpt-4.1-nano": 200000
                    }
                }
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "date_format": None,
                "file_path": None,
                "max_bytes": 10485760,
                "backup_count": 5,
                "log_to_console": True,
                "log_to_file": True
            }
        }
    
    def _load_from_database(self):
        """Load configuration from database."""
        if not self.db_session:
            raise ConfigError(
                "db_session is required for database mode",
                details={"use_database": self.use_database}
            )
        
        try:
            # Import here to avoid circular dependencies
            from src.api.models import SystemConfiguration
            
            query = self.db_session.query(SystemConfiguration).filter(
                SystemConfiguration.is_active == True
            )
            
            configs = query.all()
            
            # Build config dict from DB records
            for config in configs:
                # Set nested value using dot notation (category.key)
                full_key = f"{config.category}.{config.config_key}"
                # Convert JSONB to Python type
                value = config.config_value
                if isinstance(value, dict) and '_type' in value:
                    # Handle typed JSONB values if needed
                    value = value.get('value', value)
                self._set_nested(full_key, value)
            
            logger.debug(f"Loaded {len(configs)} configuration values from database")
        except Exception as e:
            logger.error(f"Error loading config from database: {e}")
            raise DatabaseError(
                f"Failed to load configuration from database: {str(e)}",
                details={"error_type": type(e).__name__}
            ) from e
    
    def _infer_type(self, value: Any) -> str:
        """Infer configuration value type."""
        if isinstance(value, bool):
            return 'bool'
        elif isinstance(value, int):
            return 'int'
        elif isinstance(value, float):
            return 'float'
        elif isinstance(value, str):
            return 'string'
        elif isinstance(value, list):
            return 'array'
        elif isinstance(value, dict):
            return 'json'
        else:
            return 'string'  # Default fallback
    
    def _load_config_files(self):
        """Load configuration from JSON files."""
        # Load agent_config.json if it exists
        agent_config_path = self.config_dir / "agent_config.json"
        if agent_config_path.exists():
            try:
                with open(agent_config_path, 'r', encoding='utf-8') as f:
                    agent_config = json.load(f)
                    
                    # Handle parallel_processing key specially - merge into processing.parallel
                    if "parallel_processing" in agent_config:
                        # Ensure processing.parallel exists in default config
                        if "processing" not in self._config:
                            self._config["processing"] = {}
                        if "parallel" not in self._config["processing"]:
                            self._config["processing"]["parallel"] = {}
                        # Merge parallel_processing values into processing.parallel
                        self._merge_dict(self._config["processing"]["parallel"], agent_config["parallel_processing"])
                    
                    # Merge other keys at top level
                    for key, value in agent_config.items():
                        if key != "parallel_processing":
                            # If key doesn't exist in defaults, add it directly
                            if key not in self._config:
                                self._config[key] = value
                            # If both are dicts, merge them
                            elif isinstance(value, dict) and isinstance(self._config[key], dict):
                                self._merge_dict(self._config[key], value)
                            # Otherwise, override with file value
                            else:
                                self._config[key] = value
                
                logger.debug(f"Loaded config from {agent_config_path}")
            except Exception as e:
                logger.warning(f"Failed to load {agent_config_path}: {e}")
        else:
            logger.debug(f"Config file not found: {agent_config_path}")
    
    def _merge_dict(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge override dictionary into base."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_dict(base[key], value)
            else:
                base[key] = value
    
    def _apply_env_overrides(self):
        """
        Apply environment variable overrides.
        
        Environment variables can override config values using the pattern:
        CONFIG__SECTION__SUBSECTION__KEY=value
        
        For example:
        CONFIG__PROCESSING__PARALLEL__MAX_COLLECTOR_WORKERS=12
        CONFIG__DATABASE__POOL_SIZE=50
        
        Nested keys use double underscore (__) as separator.
        """
        for env_key, env_value in os.environ.items():
            if env_key.startswith("CONFIG__"):
                # Remove CONFIG__ prefix
                config_key = env_key[8:]  # len("CONFIG__") = 8
                # Replace double underscores with dots for nested keys
                config_path = config_key.replace("__", ".")
                
                # Try to convert value to appropriate type
                converted_value = self._convert_env_value(env_value)
                
                # Set the value using dot notation
                self._set_nested(config_path, converted_value)
                logger.debug(f"Environment override: {config_path} = {converted_value}")
    
    def _convert_env_value(self, value: str) -> Union[str, int, float, bool, List[str]]:
        """
        Convert environment variable string to appropriate type.
        
        Supports: int, float, bool, JSON arrays, and strings.
        """
        # Try JSON parsing (for arrays, objects)
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Try boolean
        if value.lower() in ('true', 'yes', 'on', '1'):
            return True
        if value.lower() in ('false', 'no', 'off', '0'):
            return False
        
        # Try int
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _set_nested(self, key_path: str, value: Any) -> None:
        """Set a nested config value using dot-notation path."""
        keys = key_path.split('.')
        config = self._config
        
        # Navigate to the parent dict
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Set the final value
        config[keys[-1]] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot-notation.
        
        Args:
            key: Dot-separated key path (e.g., "processing.parallel.max_collector_workers")
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                if isinstance(value, dict):
                    value = value[k]
                else:
                    return default
            return value
        except (KeyError, TypeError):
            return default
    
    def get_int(self, key: str, default: int) -> int:
        """Get configuration value as integer."""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Config key '{key}' is not an integer, using default {default}")
            return default
    
    def get_float(self, key: str, default: float) -> float:
        """Get configuration value as float."""
        value = self.get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Config key '{key}' is not a float, using default {default}")
            return default
    
    def get_bool(self, key: str, default: bool) -> bool:
        """Get configuration value as boolean."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', 'on', '1')
        try:
            return bool(value)
        except (ValueError, TypeError):
            logger.warning(f"Config key '{key}' is not a boolean, using default {default}")
            return default
    
    def get_list(self, key: str, default: List[Any]) -> List[Any]:
        """Get configuration value as list."""
        value = self.get(key, default)
        if isinstance(value, list):
            return value
        logger.warning(f"Config key '{key}' is not a list, using default")
        return default
    
    def get_dict(self, key: str, default: Dict[str, Any]) -> Dict[str, Any]:
        """Get configuration value as dictionary."""
        value = self.get(key, default)
        if isinstance(value, dict):
            return value
        logger.warning(f"Config key '{key}' is not a dict, using default")
        return default
    
    def get_path(self, key: str, default: Optional[str] = None) -> Path:
        """
        Get configuration value as Path object.
        
        Paths are resolved relative to base_path.
        """
        path_str = self.get(key, default)
        if path_str is None:
            raise ValueError(f"Config key '{key}' not found and no default provided")
        
        path = Path(path_str)
        if path.is_absolute():
            return path
        return self.base_path / path
    
    def get_all(self) -> Dict[str, Any]:
        """Get the entire configuration dictionary."""
        return self._config.copy()
    
    def _validate_config(self):
        """
        Validate configuration against JSON schema.
        
        Uses config.schema.json if available and jsonschema is installed.
        """
        if not JSONSCHEMA_AVAILABLE:
            logger.debug("Schema validation skipped: jsonschema not available")
            return
        
        schema_path = self.config_dir / "config.schema.json"
        if not schema_path.exists():
            logger.debug(f"Schema file not found: {schema_path}, skipping validation")
            return
        
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            
            jsonschema.validate(instance=self._config, schema=schema)
            logger.debug("Configuration validated against schema")
        except jsonschema.ValidationError as e:
            logger.warning(f"Config validation warning: {e.message}")
            # Don't raise - just log warning (backward compatibility)
        except Exception as e:
            logger.warning(f"Config validation failed: {e}")
    
    def reload(self) -> None:
        """Reload configuration from files/database and environment variables."""
        self._config = self._get_default_config()
        
        if self.use_database and self.db_session:
            try:
                self._load_from_database()
            except Exception as e:
                logger.warning(f"Failed to reload from database: {e}, using files")
                self._load_config_files()
        else:
            self._load_config_files()
        
        self._apply_env_overrides()
        
        # Re-validate if validation was enabled
        if self._validate:
            self._validate_config()
        
        logger.info("Configuration reloaded")
