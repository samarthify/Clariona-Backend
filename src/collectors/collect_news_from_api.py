import requests
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import List, Dict, Any
import sys

# Force UTF-8 encoding for the entire script to prevent charmap codec errors
if sys.platform.startswith('win'):
    # Windows-specific encoding fix
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NewsAPICollector:
    def __init__(self):
        # Load .env from collectors folder
        env_path = Path(__file__).parent / '.env'
        load_dotenv(env_path)
        self.base_path = Path(__file__).parent.parent.parent
        
        # API Keys - Only keeping functional ones
        self.mediastack_key = os.getenv("MEDIASTACK_API_KEY")
        self.gnews_key = os.getenv("GNEWS_API_KEY")
        self.supabase_url= os.getenv("REACT_APP_SUPABASE_URL")
        self.supabase_key = os.getenv("REACT_APP_SUPABASE_ANON_KEY")
        
        # Target-specific configuration
        self.target_config = None
        
        # Validate API keys
        self._validate_api_keys()

    def set_target_config(self, target_config):
        """Set target-specific configuration for this collector"""
        self.target_config = target_config
        logger.info(f"Set target config for: {target_config.name if target_config else 'None'}")

    def _validate_api_keys(self):
        """Validate that at least some API keys are available"""
        available_apis = []
        if self.mediastack_key:
            available_apis.append("Mediastack")
        if self.gnews_key:
            available_apis.append("GNews")
            
        if not available_apis:
            raise ValueError(
                "No API keys found. Please set at least one of the following in .env:\n"
                "MEDIASTACK_API_KEY\n"
                "GNEWS_API_KEY"
            )
        logger.info(f"Available APIs: {', '.join(available_apis)}")

    def _get_target_keywords(self) -> List[str]:
        """Get keywords to filter articles based on target configuration"""
        # Hardcoded keywords for news-from-api collector
        return [
            'Asiwaju Bola Ahmed Adekunle Tinubu',
            'President of the Federal Republic of Nigeria',
            'Bola Tinubu',
            'Bola Ahmed Tinubu',
            'President of Nigeria',
            'Tinubu',
            'Bola',
            'nigeria'
        ]

    def _get_target_countries(self) -> List[str]:
        """Get countries to search based on target configuration"""
        if self.target_config and hasattr(self.target_config, 'sources'):
            news_config = self.target_config.sources.get('news')
            if news_config and hasattr(news_config, 'countries') and news_config.countries:
                return news_config.countries
        
        # Fallback to default countries for backward compatibility
        return ['qa', 'us', 'gb', 'ae', 'ng', 'in']

    def _should_include_article(self, content: str) -> bool:
        """Determine if an article should be included based on target configuration"""
        # Use hardcoded keywords
        target_keywords = self._get_target_keywords()
        content_lower = content.lower()
        
        # Check if content contains any target keywords
        has_target_keywords = any(keyword.lower() in content_lower for keyword in target_keywords)
        
        # Apply additional filters if configured
        if hasattr(self.target_config, 'sources') and 'news' in self.target_config.sources:
            news_config = self.target_config.sources['news']
            if hasattr(news_config, 'filters') and news_config.filters:
                filters = news_config.filters
                
                # Check must_contain filters
                if 'must_contain' in filters:
                    must_contain = filters['must_contain']
                    if not any(term.lower() in content_lower for term in must_contain):
                        return False
                
                # Check exclude filters
                if 'exclude' in filters:
                    exclude_terms = filters['exclude']
                    if any(term.lower() in content_lower for term in exclude_terms):
                        return False
        
        return has_target_keywords

    def collect_mediastack(self, query: str) -> List[Dict[Any, Any]]:
        """Collect news from Mediastack - Now collecting from multiple countries"""
        if not self.mediastack_key:
            # logger.warning("Mediastack API key not found")
            return []
            
        articles = []
        countries = self._get_target_countries()
        
        try:
            url = "http://api.mediastack.com/v1/news"
            
            for country_code in countries:
                params = {
                    "access_key": self.mediastack_key,
                    "keywords": f'"{query}"',  # Exact phrase matching
                    "countries": country_code,
                    "languages": "en",
                    "limit": 100,
                    "sort": "published_desc"
                }
                
                response = requests.get(url, params=params)
                if response.status_code != 200:
                    # logger.warning(f"Mediastack error response for {country_code}: {response.status_code} - {response.text}") # Changed to warning
                    continue
                    
                data = response.json()
                
                if "error" in data:
                    error = data["error"]
                    if error.get("code") == "usage_limit_reached":
                        # logger.warning("Mediastack monthly usage limit reached") # Changed to warning
                        break
                    elif error.get("code") == "rate_limit_reached":
                        # logger.warning("Mediastack rate limit reached") # Changed to warning
                        continue
                    else:
                        # logger.warning(f"Mediastack API error for {country_code}: {error.get('code')} - {error.get('message')}") # Changed to warning
                        continue
                
                results = data.get("data", [])
                logger.info(f"Mediastack returned {len(results)} articles for {country_code} - query: {query}")
                
                for article in results:
                    # Use target-specific filtering
                    content = f"{article.get('title', '')} {article.get('description', '')}"
                    if self._should_include_article(content):
                        # Map country codes to names
                        country_name = {
                            'qa': 'Qatar',
                            'us': 'US',
                            'gb': 'UK',
                            'ae': 'UAE',
                            'ng': 'Nigeria',
                            'in': 'India'
                        }.get(country_code, 'Unknown')
                        
                        articles.append({
                            "source": "News",
                            "platform": article.get("source", "Mediastack"),
                            "type": "post",
                            "post_id": article.get("url", "").split("/")[-1],
                            "date": article.get("published_at"),
                            "text": f"{article.get('title', '')} {article.get('description', '')}",
                            "url": article.get("url"),
                            "country": country_name
                        })
            
            # Log breakdown by country
            country_breakdown = {}
            for article in articles:
                country = article['country']
                country_breakdown[country] = country_breakdown.get(country, 0) + 1
            
            target_name = self.target_config.name if self.target_config else "Default Target"
            logger.info(f"Mediastack: {len(articles)} total articles matched {target_name} criteria")
            for country, count in country_breakdown.items():
                logger.info(f"  - {country}: {count} articles")
                
        except Exception as e:
            # logger.warning(f"Error collecting from Mediastack: {e}") # Changed to warning
            pass # Added pass to avoid indentation error
        
        return articles

    def collect_gnews(self, query: str) -> List[Dict[Any, Any]]:
        """Collect news from GNews - Now collecting from multiple countries"""
        if not self.gnews_key:
            # logger.warning("GNews API key not found")
            return []
            
        articles = []
        countries = self._get_target_countries()
        
        try:
            url = "https://gnews.io/api/v4/search"
            
            for country_code in countries:
                params = {
                    "q": f'"{query}"',  # Exact phrase matching
                    "token": self.gnews_key,
                    "lang": "en",
                    "country": country_code,
                    "max": 100,
                    "sortby": "publishedAt",
                    "in": "title,description"  # Search in both title and description
                }
                
                response = requests.get(url, params=params)
                if response.status_code != 200:
                    # logger.warning(f"GNews error response for {country_code}: {response.status_code} - {response.text}") # Changed to warning
                    continue
                    
                data = response.json()
                results = data.get("articles", [])
                logger.info(f"GNews returned {len(results)} articles for {country_code} - query: {query}")
                
                for article in results:
                    # Use target-specific filtering
                    content = f"{article.get('title', '')} {article.get('description', '')}"
                    if self._should_include_article(content):
                        # Map country codes to names
                        country_name = {
                            'QA': 'Qatar',
                            'US': 'US',
                            'GB': 'UK',
                            'AE': 'UAE',
                            'NG': 'Nigeria',
                            'IN': 'India'
                        }.get(country_code, 'Unknown')
                        
                        articles.append({
                            "source": "News",
                            "platform": article.get("source", {}).get("name", "GNews"),
                            "type": "post",
                            "post_id": article.get("url", "").split("/")[-1],
                            "date": article.get("publishedAt"),
                            "text": f"{article.get('title', '')} {article.get('description', '')}",
                            "url": article.get("url"),
                            "country": country_name
                        })
            
            # Log breakdown by country
            country_breakdown = {}
            for article in articles:
                country = article['country']
                country_breakdown[country] = country_breakdown.get(country, 0) + 1
            
            target_name = self.target_config.name if self.target_config else "Default Target"
            logger.info(f"GNews: {len(articles)} total articles matched {target_name} criteria")
            for country, count in country_breakdown.items():
                logger.info(f"  - {country}: {count} articles")
                
        except Exception as e:
            # logger.warning(f"Error collecting from GNews: {e}") # Changed to warning
            pass # Added pass to avoid indentation error
        
        return articles

    def collect_all(self, queries: List[str], output_file: str = None) -> None:
        """Collect news from all available sources"""
        if output_file is None:
            today = datetime.now().strftime("%Y%m%d")
            target_name = "default"
            if self.target_config:
                target_name = self.target_config.name.replace(" ", "_").lower()
            output_file = str(self.base_path / "data" / "raw" / f"news_data_{target_name}_{today}.csv")
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        all_articles = []
        source_counts = {
            "Mediastack": 0, 
            "GNews": 0
        }
        
        # Use hardcoded keywords instead of queries from database
        hardcoded_keywords = self._get_target_keywords()
        logger.info(f"Using hardcoded keywords for news-from-api collector: {hardcoded_keywords}")
        
        for query in hardcoded_keywords:
            logger.info(f"\nCollecting news for query: {query}")
            
            # Collect from functional sources only
            mediastack_articles = self.collect_mediastack(query)
            source_counts["Mediastack"] += len(mediastack_articles)
            all_articles.extend(mediastack_articles)
            
            gnews_articles = self.collect_gnews(query)
            source_counts["GNews"] += len(gnews_articles)
            all_articles.extend(gnews_articles)
        
        if all_articles:
            df = pd.DataFrame(all_articles)
            
            # Remove duplicates based on URL and text
            initial_count = len(df)
            df = df.drop_duplicates(subset=['url'])
            url_dedup_count = len(df)
            df = df.drop_duplicates(subset=['text'])
            final_count = len(df)
            
            # Save to CSV
            if os.path.exists(output_file):
                existing_df = pd.read_csv(output_file)
                df = pd.concat([existing_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=['url'])
                df = df.drop_duplicates(subset=['text'])
            
            df.to_csv(output_file, index=False)
            
            target_name = self.target_config.name if self.target_config else "Default Target"
            logger.info(f"\nCollection Summary for {target_name}:")
            logger.info(f"Total articles collected by source:")
            for source, count in source_counts.items():
                logger.info(f"  - {source}: {count} articles")
            logger.info(f"Initial article count: {initial_count}")
            logger.info(f"After URL deduplication: {url_dedup_count}")
            logger.info(f"After text deduplication: {final_count}")
            logger.info(f"Saved {final_count} unique articles to {output_file}")
        else:
            # logger.warning("No articles collected from any source")
            pass # Added pass to avoid indentation error

def main(target_and_variations: List[str], user_id: str = None):
    """Main function called by run_collectors. Accepts target/variations list and user_id."""
    if not target_and_variations:
        print("[News API] Error: No target/query variations provided.")
        return
    
    if not user_id:
        print("[News API] Error: No user_id provided.")
        return
        
    target_name = target_and_variations[0]
    queries = target_and_variations[1:]
    print(f"[News API] Received Target: {target_name}, Queries: {queries}, User ID: {user_id}")
    
    # Instantiate the collector
    collector = NewsAPICollector()
    
    # Try to determine target configuration
    try:
        from .target_config_manager import get_target_by_name
        target_config = get_target_by_name(target_name)
        if target_config:
            collector.set_target_config(target_config)
            print(f"✅ Using target configuration for: {target_config.name}")
        else:
            print(f"⚠️  No specific target configuration found for: {target_name}, using default settings")
    except Exception as e:
        print(f"⚠️  Could not load target configuration: {e}, using default settings")
    
    # Construct the output file path
    today = datetime.now().strftime("%Y%m%d")
    safe_target_name = target_name.replace(" ", "_").lower()
    output_dir = Path(__file__).parent.parent.parent / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"news_api_{safe_target_name}_{today}.csv"

    # Call the collector's collect_all method
    collector.collect_all(queries=queries, output_file=str(output_file))

# Keep __main__ block for testing
if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Collect news data from various News APIs')
    parser.add_argument('--queries', type=str, required=False, help='JSON string of query variations')
    parser.add_argument('--since', type=str, help='Start date in ISO format YYYY-MM-DDTHH:MM:SS (for incremental collection)')
    parser.add_argument('--until', type=str, help='End date in ISO format YYYY-MM-DDTHH:MM:SS (for incremental collection)')
    
    args = parser.parse_args()
    
    if args.queries:
        try:
            queries_list = json.loads(args.queries)
            print(f"[News API] Parsed queries: {queries_list}")
            
            # Note: This collector doesn't yet support incremental date ranges
            # TODO: Implement date range filtering in collect_from_mediastack and collect_from_gnews
            if args.since or args.until:
                print(f"⚠️  [News API] Date range parameters not yet implemented: {args.since} to {args.until}")
            
            # Get user_id from environment
            user_id = os.getenv('COLLECTOR_USER_ID')
            main(queries_list, user_id=user_id)
        except json.JSONDecodeError as e:
            print(f"[News API] Error parsing queries JSON: {e}")
            sys.exit(1)
    else:
        print("Running News API collector directly (without args)... Use run_collectors.py for proper execution.")
        main(["Modi", "India", "BJP", "Election", "Politics"])

    
