"""
Generate embeddings for all topics in the database.
Run once to pre-compute topic embeddings for classification.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

import openai
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import SessionLocal
from api.models import Topic
from utils.openai_rate_limiter import get_rate_limiter

logger = logging.getLogger('TopicEmbeddingGenerator')


class TopicEmbeddingGenerator:
    """Generate embeddings for topics stored in the database."""
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize topic embedding generator.
        
        Args:
            db_session: Optional database session. If None, creates a new session.
        """
        self.db = db_session
        self.openai_client = None
        self._setup_openai()
    
    def _setup_openai(self):
        """Initialize OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=api_key)
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing OpenAI client: {e}")
    
    def _get_embedding_model(self) -> str:
        """Get embedding model name from ConfigManager."""
        try:
            from config.config_manager import ConfigManager
            config = ConfigManager()
            return config.get("models.embedding_model", "text-embedding-3-small")
        except Exception:
            return "text-embedding-3-small"
    
    def _get_db_session(self) -> Session:
        """Get database session (create new if not provided)."""
        if self.db:
            return self.db
        return SessionLocal()
    
    def _close_db_session(self, session: Session):
        """Close database session if we created it."""
        if not self.db and session:
            session.close()
    
    def load_topics_from_database(self) -> Dict[str, Dict]:
        """
        Load all active topics from the database.
        
        Returns:
            Dictionary mapping topic_key to topic data:
            {
                "topic_key": {
                    "name": "...",
                    "description": "...",
                    "keywords": [...],
                    "category": "..."
                }
            }
        """
        session = self._get_db_session()
        try:
            topics = session.query(Topic).filter(Topic.is_active == True).all()
            
            topics_dict = {}
            for topic in topics:
                # Convert keywords array to list if needed
                keywords = topic.keywords
                if keywords is None:
                    keywords = []
                elif isinstance(keywords, str):
                    # Handle case where keywords might be stored as string
                    try:
                        keywords = json.loads(keywords)
                    except:
                        keywords = []
                
                topics_dict[topic.topic_key] = {
                    "name": topic.topic_name,
                    "description": topic.description or "",
                    "keywords": keywords if isinstance(keywords, list) else list(keywords) if keywords else [],
                    "category": topic.category
                }
            
            logger.info(f"Loaded {len(topics_dict)} active topics from database")
            return topics_dict
        
        except Exception as e:
            logger.error(f"Error loading topics from database: {e}")
            return {}
        
        finally:
            self._close_db_session(session)
    
    def generate_embedding_for_topic(self, topic_key: str, topic_data: Dict) -> Optional[List[float]]:
        """
        Generate embedding for a single topic.
        
        Args:
            topic_key: Topic identifier
            topic_data: Topic data dictionary with name, description, etc.
        
        Returns:
            Embedding vector (1536 dimensions) or None on error
        """
        if not self.openai_client:
            logger.error("OpenAI client not available")
            return None
        
        # Create embedding text from name + description
        name = topic_data.get('name', '')
        description = topic_data.get('description', '')
        embedding_text = f"{name} {description}".strip()
        
        if not embedding_text:
            logger.warning(f"Empty embedding text for topic {topic_key}")
            return None
        
        try:
            rate_limiter = get_rate_limiter()
            # Estimate tokens: ~2200 tokens for embeddings (1536 dims × ~1.3 tokens)
            with rate_limiter.acquire(estimated_tokens=2200):
                response = self.openai_client.embeddings.create(
                    model=self._get_embedding_model(),
                    input=embedding_text[:8000]  # Limit text length
                )
                embedding = response.data[0].embedding
                logger.debug(f"Generated embedding for topic: {topic_key}")
                return embedding
        
        except Exception as e:
            logger.error(f"Error generating embedding for topic {topic_key}: {e}")
            return None
    
    def generate_all_embeddings(self, output_path: Optional[str] = None) -> Dict[str, List[float]]:
        """
        Generate embeddings for all active topics and optionally save to file.
        
        Args:
            output_path: Optional path to save embeddings JSON file.
                        If None, uses default: "config/topic_embeddings.json"
        
        Returns:
            Dictionary mapping topic_key to embedding vector
        """
        if not self.openai_client:
            logger.error("OpenAI client not available")
            return {}
        
        if output_path is None:
            # Use PathManager for default topic embeddings path
            path_manager = PathManager()
            output_path = str(path_manager.config_topic_embeddings)
        
        # Load topics from database
        topics = self.load_topics_from_database()
        
        if not topics:
            logger.warning("No topics found in database")
            return {}
        
        embeddings = {}
        
        logger.info(f"Generating embeddings for {len(topics)} topics...")
        
        for topic_key, topic_data in topics.items():
            embedding = self.generate_embedding_for_topic(topic_key, topic_data)
            if embedding:
                embeddings[topic_key] = embedding
            else:
                logger.warning(f"Failed to generate embedding for topic: {topic_key}")
        
        # Save embeddings to file
        if embeddings:
            output_data = {
                "version": "1.0",
                "model": "text-embedding-3-small",
                "embeddings": embeddings,
                "last_generated": datetime.now(datetime.timezone.utc).isoformat(),
                "topic_count": len(embeddings)
            }
            
            try:
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2)
                
                logger.info(f"Saved {len(embeddings)} topic embeddings to {output_path}")
            
            except Exception as e:
                logger.error(f"Error saving embeddings to file: {e}")
        
        return embeddings


# CLI script to generate embeddings
if __name__ == "__main__":
    import sys
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Optional: accept output path as command line argument
    output_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    generator = TopicEmbeddingGenerator()
    embeddings = generator.generate_all_embeddings(output_path=output_path)
    
    if embeddings:
        print(f"\n[SUCCESS] Successfully generated {len(embeddings)} topic embeddings")
        if output_path:
            print(f"  Saved to: {output_path}")
        else:
            print(f"  Saved to: config/topic_embeddings.json")
    else:
        print("\n[ERROR] Failed to generate embeddings")
        sys.exit(1)

