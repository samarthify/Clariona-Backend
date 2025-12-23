import logging
from pathlib import Path
import importlib
import sys
from datetime import datetime
import time
import argparse
import json
from typing import List
import os
import logging

# Force UTF-8 encoding for the entire script to prevent charmap codec errors
if sys.platform.startswith('win'):
    # Windows-specific encoding fix
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s] - %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/collectors.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('CollectorsRunner')

def run_configurable_collector(target_and_variations: List[str], user_id: str = None) -> None:
    """Run the configurable collector system which determines target and runs appropriate collectors."""
    start_time = time.time()
    
    try:
        logger.info(f"{'='*10} Starting Configurable Collector System {'='*10}")
        
        # Get user_id from environment (set by the agent)
        if not user_id:
            user_id = os.environ.get('COLLECTOR_USER_ID')
            if not user_id:
                logger.warning("No COLLECTOR_USER_ID found in environment. Collectors may not work properly.")
        
        # Add src directory to Python path if not already added by agent
        src_dir = Path(__file__).parent.parent
        if str(src_dir) not in sys.path:
            sys.path.append(str(src_dir))
        
        # Import and run the configurable collector
        try:
            from collectors.configurable_collector import ConfigurableCollector
            
            collector = ConfigurableCollector()
            result = collector.run_collection_with_target_detection(target_and_variations, user_id)
            
            if result["success"]:
                logger.info(f"✅ Collection completed successfully for {result['target_name']} ({result['target_country']})")
                logger.info(f"📊 Results: {result['results']}")
            else:
                logger.error(f"❌ Collection failed: {result['error']}")
                
        except ImportError as e:
            logger.error(f"Could not import configurable collector: {e}")
            logger.info("Falling back to legacy collector system...")
            run_legacy_collectors(target_and_variations, user_id)
            
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"{'='*10} Finished Configurable Collector System - Duration: {duration:.2f}s {'='*10}")
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        logger.error(f"Error running configurable collector (Duration: {duration:.2f}s): {str(e)}", exc_info=True)

def run_legacy_collectors(target_and_variations: List[str], user_id: str = None) -> None:
    """Legacy collector system for backward compatibility."""
    logger.info("Running legacy collector system...")
    
    # List of collector modules to run - Only functional ones
    collectors = [
        'collectors.collect_news_from_api',  # Contains Mediastack and GNews
        'collectors.collect_news_apify',      # News scraping via Apify
        # 'collectors.collect_social_searcher_api', # Non-functional - REMOVED
        'collectors.collect_twitter_apify',   # Twitter data collection
        'collectors.collect_facebook_apify',  # Facebook data collection via Apify
        # 'collectors.collect_reddit_apify',    # Non-functional - REMOVED
        'collectors.collect_rss_nigerian_qatar_indian',  # Nigerian, Qatar, and Indian RSS feeds (replaces old RSS)
        'collectors.collect_youtube_api',     # YouTube TV channels collection
        # 'collectors.collect_radio_apify',     # REMOVED - Not in use, using collect_radio_hybrid instead
        'collectors.collect_instagram_apify',  # Instagram data collection via Apify
        'collectors.collect_tiktok_apify',     # TikTok data collection via Apify
    ]
    
    successful_collectors = 0
    total_collectors = len(collectors)
    
    # Run each collector, passing the queries
    for collector_module_name in collectors:
        run_collector(collector_module_name, target_and_variations, user_id)
        # Simple success check (could be improved if run_collector returned status)
        if collector_module_name in sys.modules: 
            successful_collectors += 1
    
    logger.info(f"Legacy collection complete: {successful_collectors}/{total_collectors} collectors successful")

def run_collector(module_name: str, target_and_variations: List[str], user_id: str = None) -> None:
    """Run a collector module by importing and executing its main function, passing queries."""
    collector_name = module_name.split('.')[-1]
    start_time = time.time()
    
    try:
        logger.info(f"{'='*10} Starting collector: {collector_name} {'='*10}")
        
        # Import the module
        module = importlib.import_module(module_name)
        
        # Check if module has main function that accepts the argument
        if hasattr(module, 'main') and callable(module.main):
             # Pass both queries and user_id to the collector
             if hasattr(module.main, '__code__') and module.main.__code__.co_argcount >= 2:
                 # If main function accepts 2+ arguments, pass user_id as second argument
                 module.main(target_and_variations, user_id)
             else:
                 # Fallback to original behavior
                 module.main(target_and_variations)
             
             end_time = time.time()
             duration = end_time - start_time
             logger.info(f"{'='*10} Finished collector: {collector_name} - Duration: {duration:.2f}s {'='*10}")
        else:
            logger.warning(f"{collector_name} does not have a callable main function accepting arguments.")
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        logger.error(f"Error running {collector_name} (Duration: {duration:.2f}s): {str(e)}", exc_info=True)

def main():
    """Parse arguments and run the configurable collector system."""
    # --- Argument Parsing --- 
    parser = argparse.ArgumentParser(description="Run configurable data collectors with specified queries.")
    parser.add_argument(
        '--queries',
        required=True,
        # Use triple quotes for cleaner help string
        help="""JSON string of the query list (including target name as first element). Example: '["Target Name", "query1", "query2"]'"""
    )
    args = parser.parse_args()
    
    # Decode the JSON query list
    try:
        target_and_variations = json.loads(args.queries)
        if not isinstance(target_and_variations, list) or len(target_and_variations) == 0:
            raise ValueError("Decoded queries is not a non-empty list.")
        logger.info(f"Received queries via args: {target_and_variations}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON queries argument: {args.queries}")
        sys.exit(1)
    except ValueError as ve:
        logger.error(f"Invalid queries format: {ve}. Argument: {args.queries}")
        sys.exit(1)
    # --- End Argument Parsing ---
    
    # Add src directory to Python path if not already added by agent
    src_dir = Path(__file__).parent.parent
    if str(src_dir) not in sys.path:
         sys.path.append(str(src_dir))
    
    total_start_time = time.time()
    logger.info(f"{'#'*20} Starting Configurable Collectors Run {'#'*20}")
    
    # Get user_id from environment
    user_id = os.environ.get('COLLECTOR_USER_ID')
    
    # Run the configurable collector system
    run_configurable_collector(target_and_variations, user_id)
    
    total_duration = time.time() - total_start_time
    logger.info(f"{'#'*20} End of Collection Run (Duration: {total_duration:.2f}s) {'#'*20}")

if __name__ == "__main__":
    main()
