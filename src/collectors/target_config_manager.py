"""
Target Configuration Manager for configurable collector system.
Handles loading and managing target-specific configurations for different individuals.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class TargetSourceConfig:
    """Configuration for a specific source type for a target"""
    enabled: bool
    countries: List[str] = None
    keywords: List[str] = None
    locations: List[str] = None
    feeds: List[str] = None
    filters: Dict[str, Any] = None

@dataclass
class TargetConfig:
    """Complete configuration for a target individual"""
    name: str
    full_name: str
    country: str
    country_code: str
    keywords: List[str]
    sources: Dict[str, TargetSourceConfig]
    sentiment_rules: Dict[str, List[str]]

class TargetConfigManager:
    """Manages target configurations for the collector system"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config directory relative to project root
            config_path = Path(__file__).parent.parent.parent / "config" / "target_configs.json"
        
        self.config_path = Path(config_path)
        self.config_data = {}
        self.targets = {}
        self._load_config()
    
    def _load_config(self):
        """Load the target configuration file"""
        try:
            if not self.config_path.exists():
                logger.warning(f"Target config file not found: {self.config_path}")
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
            
            # Parse target configurations
            for target_id, target_data in self.config_data.get("targets", {}).items():
                self.targets[target_id] = self._parse_target_config(target_data)
            
            logger.info(f"Loaded {len(self.targets)} target configurations")
            
        except Exception as e:
            logger.error(f"Error loading target config: {e}")
            self.config_data = {}
            self.targets = {}
    
    def _parse_target_config(self, target_data: Dict[str, Any]) -> TargetConfig:
        """Parse raw target data into TargetConfig object"""
        sources = {}
        
        # Parse source configurations
        for source_type, source_data in target_data.get("sources", {}).items():
            filters = source_data.get("filters", {})
            sources[source_type] = TargetSourceConfig(
                enabled=source_data.get("enabled", True),
                countries=source_data.get("countries", []),
                keywords=source_data.get("keywords", []),
                locations=source_data.get("locations", []),
                feeds=source_data.get("feeds", []),
                filters=filters
            )
        
        return TargetConfig(
            name=target_data.get("name", ""),
            full_name=target_data.get("full_name", ""),
            country=target_data.get("country", ""),
            country_code=target_data.get("country_code", ""),
            keywords=target_data.get("keywords", []),
            sources=sources,
            sentiment_rules=target_data.get("sentiment_rules", {})
        )
    
    def get_target_config(self, target_id: str) -> Optional[TargetConfig]:
        """Get configuration for a specific target"""
        return self.targets.get(target_id)
    
    def get_target_by_name(self, target_name: str) -> Optional[TargetConfig]:
        """Get target configuration by name (case-insensitive)"""
        target_name_lower = target_name.lower()
        
        for target_id, target_config in self.targets.items():
            if (target_name_lower in target_config.name.lower() or 
                target_name_lower in target_config.full_name.lower() or
                any(keyword.lower() in target_name_lower for keyword in target_config.keywords)):
                return target_config
        
        return None
    
    def get_target_by_keywords(self, keywords: List[str]) -> Optional[TargetConfig]:
        """Get target configuration by matching keywords"""
        if not keywords:
            return None
        
        best_match = None
        best_score = 0
        
        for target_id, target_config in self.targets.items():
            score = 0
            for keyword in keywords:
                if any(keyword.lower() in target_keyword.lower() or 
                       target_keyword.lower() in keyword.lower() 
                       for target_keyword in target_config.keywords):
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = target_config
        
        return best_match if best_score > 0 else None
    
    def get_available_targets(self) -> List[str]:
        """Get list of available target IDs"""
        return list(self.targets.keys())
    
    def get_target_names(self) -> List[str]:
        """Get list of target names"""
        return [config.name for config in self.targets.values()]
    
    def is_source_enabled(self, target_id: str, source_type: str) -> bool:
        """Check if a specific source is enabled for a target"""
        target_config = self.get_target_config(target_id)
        if not target_config:
            return False
        
        source_config = target_config.sources.get(source_type)
        if not source_config:
            return False
        
        return source_config.enabled
    
    def get_source_config(self, target_id: str, source_type: str) -> Optional[TargetSourceConfig]:
        """Get source configuration for a specific target and source type"""
        target_config = self.get_target_config(target_id)
        if not target_config:
            return None
        
        return target_config.sources.get(source_type)
    
    def get_enabled_collectors(self, target_id: str) -> List[str]:
        """Get list of enabled collector names for a specific target"""
        target_config = self.get_target_config(target_id)
        if not target_config:
            return []
        
        # Map source types to collector module names
        # Some sources have multiple collectors (news, radio)
        source_to_collector = {
            "news": ["collect_news_from_api", "collect_news_apify"],  # Run BOTH news collectors
            "twitter": ["collect_twitter_apify"],
            "facebook": ["collect_facebook_apify"],
            "rss": ["collect_rss_nigerian_qatar_indian"],
            "youtube": ["collect_youtube_api"],
            "radio": ["collect_radio_hybrid"],  # Use radio_hybrid, not radio_apify
            "reddit": ["collect_reddit_apify"],
            "instagram": ["collect_instagram_apify"],
            "tiktok": ["collect_tiktok_apify"],
            "linkedin": ["collect_linkedin"]  # No apify version yet
        }
        
        enabled_collectors = []
        for source_type, source_config in target_config.sources.items():
            if source_config.enabled:
                # source_to_collector[source_type] is now a list of collectors
                collector_names = source_to_collector.get(source_type, [])
                enabled_collectors.extend(collector_names)
        
        return enabled_collectors
    
    def get_collection_settings(self) -> Dict[str, Any]:
        """Get global collection settings"""
        return self.config_data.get("collection_settings", {})
    
    def get_default_sources(self) -> Dict[str, bool]:
        """Get default source enablement settings"""
        return self.config_data.get("default_sources", {})
    
    def reload_config(self):
        """Reload configuration from file"""
        self._load_config()
    
    def validate_target_config(self, target_id: str) -> List[str]:
        """Validate a target configuration and return list of issues"""
        issues = []
        target_config = self.get_target_config(target_id)
        
        if not target_config:
            issues.append(f"Target '{target_id}' not found")
            return issues
        
        # Validate required fields
        if not target_config.name:
            issues.append("Target name is required")
        if not target_config.keywords:
            issues.append("Target keywords are required")
        if not target_config.sources:
            issues.append("Target sources configuration is required")
        
        # Validate source configurations
        for source_type, source_config in target_config.sources.items():
            if source_config.enabled:
                if source_type == "news" and not source_config.countries:
                    issues.append(f"News source enabled but no countries specified for {target_id}")
                if source_type == "rss" and not source_config.feeds:
                    issues.append(f"RSS source enabled but no feeds specified for {target_id}")
        
        return issues

# Global instance for easy access
target_config_manager = TargetConfigManager()

def get_target_config(target_id: str) -> Optional[TargetConfig]:
    """Convenience function to get target configuration"""
    return target_config_manager.get_target_config(target_id)

def get_target_by_name(target_name: str) -> Optional[TargetConfig]:
    """Convenience function to get target by name"""
    return target_config_manager.get_target_by_name(target_name)

def get_target_by_keywords(keywords: List[str]) -> Optional[TargetConfig]:
    """Convenience function to get target by keywords"""
    return target_config_manager.get_target_by_keywords(keywords)

