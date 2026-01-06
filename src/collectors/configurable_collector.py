"""
Configurable Collector Orchestrator
Determines target individual and runs appropriate collectors based on target-specific configurations.
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import importlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Force UTF-8 encoding for the entire script to prevent charmap codec errors
if sys.platform.startswith('win'):
    # Windows-specific encoding fix
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from .target_config_manager import TargetConfigManager, get_target_by_name, get_target_by_keywords
from .target_helper import get_target_and_queries
from src.config.path_manager import PathManager

logger = logging.getLogger(__name__)

class ConfigurableCollector:
    """
    Main orchestrator for the configurable collector system.
    Determines target individual and runs appropriate collectors.
    """
    
    def __init__(self):
        self.target_config_manager = TargetConfigManager()
        self.path_manager = PathManager()
        self.base_path = self.path_manager.base_path  # For backward compatibility
        from config.config_manager import ConfigManager
        self.config = ConfigManager()
        
        # Timeout settings from ConfigManager
        self.collector_timeout = self.config.get_int("processing.timeouts.collector_timeout_seconds", 1800)  # 30 minutes per collector
        self.overall_timeout = self.config.get_int("processing.timeouts.overall_timeout_seconds", 7200)    # 2 hours total system timeout
        
        # Available collector modules
        self.collectors = {
            'news': 'collectors.collect_news_from_api',
            'twitter': 'collectors.collect_twitter_apify',
            'facebook': 'collectors.collect_facebook_apify',
            'rss': 'collectors.collect_rss_nigerian_qatar_indian',  # Updated to new RSS collector
            'youtube': 'collectors.collect_youtube_api',
            'radio': 'collectors.collect_radio_hybrid',  # Improved hybrid radio collector
            # 'reddit': 'collectors.collect_reddit_apify',  # REMOVED - Not in use
            'instagram': 'collectors.collect_instagram_apify',
            'tiktok': 'collectors.collect_tiktok_apify',
            'linkedin': 'collectors.collect_linkedin_apify'
        }
    
    def determine_target(self, target_and_variations: List[str], user_id: Optional[str] = None) -> Optional[str]:
        """
        Determine which target individual to use based on input.
        
        Args:
            target_and_variations: List starting with target name, followed by query variations
            user_id: User ID for database lookup
            
        Returns:
            Target ID (e.g., 'emir', 'tinubu') or None if not found
        """
        if not target_and_variations:
            logger.warning("No target/query variations provided")
            return None
        
        target_name = target_and_variations[0]
        logger.info(f"Determining target for: {target_name}")
        
        # Method 1: Try to match by exact target name
        target_config = get_target_by_name(target_name)
        if target_config:
            # Find the target ID for this config
            for target_id, config in self.target_config_manager.targets.items():
                if config == target_config:
                    logger.info(f"Target determined by name: {target_id}")
                    return target_id
        
        # Method 2: Try to match by keywords
        target_config = get_target_by_keywords(target_and_variations)
        if target_config:
            # Find the target ID for this config
            for target_id, config in self.target_config_manager.targets.items():
                if config == target_config:
                    logger.info(f"Target determined by keywords: {target_id}")
                    return target_id
        
        # Method 3: Check database for user's target configuration
        if user_id:
            try:
                db_target_and_queries = get_target_and_queries(user_id)
                if db_target_and_queries:
                    db_target_name = db_target_and_queries[0]
                    target_config = get_target_by_name(db_target_name)
                    if target_config:
                        for target_id, config in self.target_config_manager.targets.items():
                            if config == target_config:
                                logger.info(f"Target determined from database: {target_id}")
                                return target_id
            except Exception as e:
                logger.warning(f"Error checking database for target: {e}")
        
        # Method 4: Fuzzy matching with available targets
        available_targets = self.target_config_manager.get_available_targets()
        for target_id in available_targets:
            target_config = self.target_config_manager.get_target_config(target_id)
            if target_config:
                # Check if any part of the target name matches
                if any(part.lower() in target_name.lower() for part in target_config.name.split()):
                    logger.info(f"Target determined by fuzzy matching: {target_id}")
                    return target_id
        
        logger.warning(f"Could not determine target for: {target_name}")
        logger.info(f"Available targets: {available_targets}")
        return None
    
    def get_enabled_collectors(self, target_id: str) -> List[str]:
        """
        Get list of enabled collectors for a specific target.
        
        Args:
            target_id: Target individual ID (e.g., 'emir', 'tinubu')
            
        Returns:
            List of enabled collector types
        """
        target_config = self.target_config_manager.get_target_config(target_id)
        if not target_config:
            logger.warning(f"No configuration found for target: {target_id}")
            return []
        
        enabled_collectors = []
        
        for source_type, source_config in target_config.sources.items():
            if source_config.enabled and source_type in self.collectors:
                enabled_collectors.append(source_type)
        
        logger.info(f"Enabled collectors for {target_id}: {enabled_collectors}")
        return enabled_collectors
    
    def run_collector(self, collector_type: str, target_id: str, target_and_variations: List[str], user_id: Optional[str] = None) -> bool:
        """
        Run a specific collector for a target.
        
        Args:
            collector_type: Type of collector (e.g., 'news', 'twitter')
            target_id: Target individual ID
            target_and_variations: Target name and query variations
            user_id: User ID for the collection
            
        Returns:
            True if successful, False otherwise
        """
        if collector_type not in self.collectors:
            logger.error(f"Unknown collector type: {collector_type}")
            return False
        
        collector_module_name = self.collectors[collector_type]
        target_config = self.target_config_manager.get_target_config(target_id)
        
        if not target_config:
            logger.error(f"No configuration found for target: {target_id}")
            return False
        
        logger.info(f"Running {collector_type} collector for {target_id} (timeout: {self.collector_timeout}s)")
        
        try:
            # Add src directory to Python path if not already added
            src_dir = Path(__file__).parent.parent
            if str(src_dir) not in sys.path:
                sys.path.append(str(src_dir))
            
            # Import the collector module
            module = importlib.import_module(collector_module_name)
            
            # Check if module has main function
            if hasattr(module, 'main') and callable(module.main):
                # Pass target-specific configuration if the collector supports it
                if hasattr(module, 'set_target_config'):
                    module.set_target_config(target_config)
                
                # Run the collector with timeout protection
                with ThreadPoolExecutor(max_workers=1) as executor:
                    # Submit the collector task
                    if hasattr(module.main, '__code__') and module.main.__code__.co_argcount >= 2:
                        future = executor.submit(module.main, target_and_variations, user_id)
                    else:
                        future = executor.submit(module.main, target_and_variations)
                    
                    # Wait for completion with timeout
                    try:
                        future.result(timeout=self.collector_timeout)
                        logger.info(f"Successfully ran {collector_type} collector for {target_id}")
                        return True
                    except FutureTimeoutError:
                        logger.error(f"Timeout ({self.collector_timeout}s) running {collector_type} collector for {target_id}")
                        return False
            else:
                logger.error(f"{collector_type} collector does not have a callable main function")
                return False
                
        except Exception as e:
            logger.error(f"Error running {collector_type} collector for {target_id}: {e}")
            return False
    
    def run_collection_for_target(self, target_and_variations: List[str], user_id: Optional[str] = None) -> Dict[str, bool]:
        """
        Run collection for a specific target individual.
        
        Args:
            target_and_variations: List starting with target name, followed by query variations
            user_id: User ID for the collection
            
        Returns:
            Dictionary mapping collector types to success status
        """
        if not target_and_variations:
            logger.error("No target/query variations provided")
            return {}
        
        # Determine target individual
        target_id = self.determine_target(target_and_variations, user_id)
        if not target_id:
            logger.error("Could not determine target individual")
            return {}
        
        logger.info(f"Running collection for target: {target_id}")
        
        # Get enabled collectors for this target
        enabled_collectors = self.get_enabled_collectors(target_id)
        if not enabled_collectors:
            logger.warning(f"No enabled collectors found for target: {target_id}")
            return {}
        
        # Add overall timeout protection
        overall_start_time = time.time()
        logger.info(f"Starting collection with overall timeout: {self.overall_timeout}s")
        
        # Run each enabled collector
        results = {}
        for i, collector_type in enumerate(enabled_collectors):
            # Check if we've exceeded the overall timeout
            if time.time() - overall_start_time > self.overall_timeout:
                logger.warning(f"Overall collection timeout ({self.overall_timeout}s) reached. Processed {i}/{len(enabled_collectors)} collectors.")
                break
                
            logger.info(f"Running collector {i+1}/{len(enabled_collectors)}: {collector_type}")
            success = self.run_collector(collector_type, target_id, target_and_variations, user_id)
            results[collector_type] = success
        
        # Log summary
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        logger.info(f"Collection complete for {target_id}: {successful}/{total} collectors successful")
        
        return results
    
    def run_collection_with_target_detection(self, queries: List[str], user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point for running collection with automatic target detection.
        
        Args:
            queries: List of queries (first element should be target name)
            user_id: User ID for the collection
            
        Returns:
            Dictionary with collection results and target information
        """
        logger.info(f"Starting collection with target detection for queries: {queries}")
        
        # Determine target
        target_id = self.determine_target(queries, user_id)
        if not target_id:
            return {
                "success": False,
                "error": "Could not determine target individual",
                "target_id": None,
                "results": {}
            }
        
        # Get target configuration
        target_config = self.target_config_manager.get_target_config(target_id)
        
        # Run collection
        collection_results = self.run_collection_for_target(queries, user_id)
        
        return {
            "success": True,
            "target_id": target_id,
            "target_name": target_config.name if target_config else "Unknown",
            "target_country": target_config.country if target_config else "Unknown",
            "queries": queries,
            "results": collection_results,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_target_summary(self) -> Dict[str, Any]:
        """Get summary of all available targets and their configurations"""
        summary = {
            "available_targets": [],
            "total_targets": 0
        }
        
        for target_id, target_config in self.target_config_manager.targets.items():
            target_info = {
                "id": target_id,
                "name": target_config.name,
                "full_name": target_config.full_name,
                "country": target_config.country,
                "country_code": target_config.country_code,
                "enabled_sources": [
                    source_type for source_type, source_config in target_config.sources.items()
                    if source_config.enabled
                ],
                "keywords": target_config.keywords
            }
            summary["available_targets"].append(target_info)
        
        summary["total_targets"] = len(summary["available_targets"])
        return summary

def main(target_and_variations: List[str], user_id: Optional[str] = None):
    """
    Main function for the configurable collector.
    This replaces the individual collector main functions.
    """
    if not target_and_variations:
        print("[Configurable Collector] Error: No target/query variations provided.")
        return
    
    if not user_id:
        print("[Configurable Collector] Error: No user_id provided.")
        return
    
    print(f"[Configurable Collector] Received Target: {target_and_variations[0]}, Queries: {target_and_variations[1:]}, User ID: {user_id}")
    
    # Create collector instance
    collector = ConfigurableCollector()
    
    # Run collection with target detection
    result = collector.run_collection_with_target_detection(target_and_variations, user_id)
    
    if result["success"]:
        print(f"✅ Collection completed successfully for {result['target_name']} ({result['target_country']})")
        print(f"📊 Results: {result['results']}")
    else:
        print(f"❌ Collection failed: {result['error']}")

if __name__ == "__main__":
    print("Running Configurable Collector directly...")
    # Example usage
    main([
        "Emir of Qatar", "Qatar", "Middle East", "Gulf Cooperation Council"
    ], "test-user-id")

