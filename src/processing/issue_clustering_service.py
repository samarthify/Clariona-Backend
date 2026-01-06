"""
Issue Clustering Service - Groups similar mentions into clusters for issue detection.

Week 4: Clustering-based issue detection.
"""

# Standard library imports
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Third-party imports
import numpy as np
from sqlalchemy.orm import Session

# Local imports - config (first)
from config.config_manager import ConfigManager
from src.config.logging_config import get_logger

# Local imports - utils
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.similarity import cosine_similarity

# Local imports - database
from api.database import SessionLocal
from api.models import SentimentData, SentimentEmbedding, MentionTopic

# Module-level setup
logger = get_logger(__name__)


class IssueClusteringService:
    """
    Clusters similar mentions into groups for issue detection.
    
    Algorithm:
    1. Group mentions by topic_key
    2. Calculate embedding similarity between mentions
    3. Cluster mentions with similarity > threshold
    4. Apply time-based constraints (mentions within time window)
    5. Filter clusters by minimum size (default: 3 mentions)
    
    Week 4: Core clustering logic for issue detection.
    """
    
    def __init__(self,
                 similarity_threshold: Optional[float] = None,
                 min_cluster_size: Optional[int] = None,
                 time_window_hours: Optional[int] = None,
                 db_session: Optional[Session] = None):
        """
        Initialize clustering service.
        
        Args:
            similarity_threshold: Minimum similarity to cluster (0.0-1.0). 
                                 If None, loads from ConfigManager. Default: 0.75
            min_cluster_size: Minimum mentions per cluster. 
                            If None, loads from ConfigManager. Default: 3
            time_window_hours: Time window for clustering (hours). 
                              If None, loads from ConfigManager. Default: 24
            db_session: Optional database session. If None, creates sessions as needed.
        """
        # Load configuration from ConfigManager
        try:
            config = ConfigManager()
            self.similarity_threshold = similarity_threshold or config.get_float(
                'processing.issue.clustering.similarity_threshold', 0.75
            )
            self.min_cluster_size = min_cluster_size or config.get_int(
                'processing.issue.clustering.min_cluster_size', 3
            )
            self.time_window_hours = time_window_hours or config.get_int(
                'processing.issue.clustering.time_window_hours', 24
            )
        except Exception as e:
            logger.warning(f"Could not load ConfigManager for clustering settings: {e}. Using defaults.")
            self.similarity_threshold = similarity_threshold or 0.75
            self.min_cluster_size = min_cluster_size or 3
            self.time_window_hours = time_window_hours or 24
        
        self.db = db_session
        
        logger.info(
            f"IssueClusteringService initialized: "
            f"threshold={similarity_threshold}, "
            f"min_size={min_cluster_size}, "
            f"time_window={time_window_hours}h"
        )
    
    def _get_db_session(self) -> Session:
        """Get database session (create new if not provided)."""
        if self.db:
            return self.db
        return SessionLocal()
    
    def _close_db_session(self, session: Session):
        """Close database session if we created it."""
        if not self.db and session:
            session.close()
    
    def cluster_mentions(self, 
                        mentions: List[Dict[str, Any]], 
                        topic_key: str) -> List[List[Dict[str, Any]]]:
        """
        Cluster mentions for a specific topic.
        
        Args:
            mentions: List of mention dictionaries with:
                - entry_id: int
                - text: str
                - embedding: List[float] (optional, will fetch if missing)
                - run_timestamp: datetime
            topic_key: Topic key to cluster for
        
        Returns:
            List of clusters, where each cluster is a list of mention dictionaries.
            Clusters are sorted by size (largest first).
        """
        if not mentions:
            logger.debug(f"No mentions to cluster for topic: {topic_key}")
            return []
        
        logger.info(f"Clustering {len(mentions)} mentions for topic: {topic_key}")
        
        # Fetch embeddings if missing
        mentions_with_embeddings = self._ensure_embeddings(mentions)
        
        if not mentions_with_embeddings:
            logger.warning(f"No mentions with embeddings for topic: {topic_key}")
            return []
        
        # Group by time windows (optional - can cluster across time if needed)
        time_groups = self._group_by_time_window(mentions_with_embeddings)
        
        # Cluster within each time group
        all_clusters = []
        for time_group in time_groups:
            clusters = self._cluster_by_similarity(time_group)
            all_clusters.extend(clusters)
        
        # Filter by minimum size
        valid_clusters = [
            cluster for cluster in all_clusters 
            if len(cluster) >= self.min_cluster_size
        ]
        
        # Sort by size (largest first)
        valid_clusters.sort(key=len, reverse=True)
        
        logger.info(
            f"Clustered {len(mentions)} mentions into {len(valid_clusters)} clusters "
            f"(min_size={self.min_cluster_size})"
        )
        
        return valid_clusters
    
    def _ensure_embeddings(self, mentions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ensure all mentions have embeddings.
        Fetches from database if missing.
        
        Args:
            mentions: List of mention dictionaries
        
        Returns:
            List of mentions with embeddings (filtered to only those with embeddings)
        """
        session = self._get_db_session()
        mentions_with_embeddings = []
        
        try:
            for mention in mentions:
                # Check if embedding already provided
                if 'embedding' in mention and mention['embedding']:
                    embedding = mention['embedding']
                    if isinstance(embedding, str):
                        import json
                        embedding = json.loads(embedding)
                    
                    if isinstance(embedding, list) and len(embedding) == 1536:
                        mention['embedding'] = embedding
                        mentions_with_embeddings.append(mention)
                        continue
                
                # Fetch embedding from database
                entry_id = mention.get('entry_id')
                if not entry_id:
                    logger.warning(f"Mention missing entry_id, skipping: {mention.get('text', '')[:50]}")
                    continue
                
                embedding_record = session.query(SentimentEmbedding).filter(
                    SentimentEmbedding.entry_id == entry_id
                ).first()
                
                if embedding_record and embedding_record.embedding:
                    import json
                    if isinstance(embedding_record.embedding, str):
                        embedding = json.loads(embedding_record.embedding)
                    else:
                        embedding = embedding_record.embedding
                    
                    if isinstance(embedding, list) and len(embedding) == 1536:
                        mention['embedding'] = embedding
                        mentions_with_embeddings.append(mention)
                    else:
                        logger.debug(f"Invalid embedding for mention {entry_id}")
                else:
                    logger.debug(f"No embedding found for mention {entry_id}")
        
        finally:
            self._close_db_session(session)
        
        return mentions_with_embeddings
    
    def _group_by_time_window(self, mentions: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Group mentions by time windows.
        
        Args:
            mentions: List of mentions with run_timestamp
        
        Returns:
            List of time groups (each group is a list of mentions)
        """
        if not mentions:
            return []
        
        # Sort by timestamp
        sorted_mentions = sorted(
            mentions,
            key=lambda m: m.get('run_timestamp') or m.get('created_at') or datetime.now()
        )
        
        if self.time_window_hours <= 0:
            # No time window - return all as one group
            return [sorted_mentions]
        
        # Group by time windows
        groups = []
        current_group = [sorted_mentions[0]]
        current_window_start = self._get_timestamp(sorted_mentions[0])
        
        for mention in sorted_mentions[1:]:
            mention_time = self._get_timestamp(mention)
            time_diff = mention_time - current_window_start
            
            if time_diff <= timedelta(hours=self.time_window_hours):
                # Within same window
                current_group.append(mention)
            else:
                # New window
                groups.append(current_group)
                current_group = [mention]
                current_window_start = mention_time
        
        # Add last group
        if current_group:
            groups.append(current_group)
        
        logger.debug(f"Grouped {len(mentions)} mentions into {len(groups)} time windows")
        
        return groups
    
    def _get_timestamp(self, mention: Dict[str, Any]) -> datetime:
        """Extract timestamp from mention."""
        timestamp = mention.get('run_timestamp') or mention.get('created_at')
        if isinstance(timestamp, str):
            from dateutil.parser import parse
            return parse(timestamp)
        return timestamp or datetime.now()
    
    def _cluster_by_similarity(self, mentions: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Cluster mentions by embedding similarity.
        
        Uses hierarchical clustering approach:
        1. Calculate similarity matrix
        2. Group mentions with similarity > threshold
        3. Merge clusters if they share similar mentions
        
        Args:
            mentions: List of mentions with embeddings
        
        Returns:
            List of clusters
        """
        if len(mentions) < self.min_cluster_size:
            return []
        
        # Build similarity matrix
        n = len(mentions)
        similarity_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i + 1, n):
                similarity = self.calculate_similarity(mentions[i], mentions[j])
                similarity_matrix[i][j] = similarity
                similarity_matrix[j][i] = similarity
        
        # Cluster using connected components approach
        clusters = self._connected_components_clustering(mentions, similarity_matrix)
        
        return clusters
    
    def calculate_similarity(self, mention1: Dict[str, Any], mention2: Dict[str, Any]) -> float:
        """
        Calculate similarity between two mentions.
        
        Args:
            mention1: First mention dict with 'embedding'
            mention2: Second mention dict with 'embedding'
        
        Returns:
            Similarity score (0.0-1.0)
        """
        emb1 = mention1.get('embedding')
        emb2 = mention2.get('embedding')
        
        if not emb1 or not emb2:
            return 0.0
        
        try:
            similarity = cosine_similarity(emb1, emb2)
            # Cosine similarity is -1 to 1, but embeddings are typically 0 to 1
            # Clamp to 0-1 range
            return max(0.0, float(similarity))
        except Exception as e:
            logger.warning(f"Error calculating similarity: {e}")
            return 0.0
    
    def _connected_components_clustering(self,
                                        mentions: List[Dict[str, Any]],
                                        similarity_matrix: np.ndarray) -> List[List[Dict[str, Any]]]:
        """
        Cluster using connected components (mentions are connected if similarity > threshold).
        
        Args:
            mentions: List of mentions
            similarity_matrix: NxN similarity matrix
        
        Returns:
            List of clusters
        """
        n = len(mentions)
        visited = [False] * n
        clusters = []
        
        for i in range(n):
            if visited[i]:
                continue
            
            # Start new cluster
            cluster = [mentions[i]]
            visited[i] = True
            
            # Find all connected mentions (BFS)
            queue = [i]
            while queue:
                current = queue.pop(0)
                
                for j in range(n):
                    if not visited[j] and similarity_matrix[current][j] >= self.similarity_threshold:
                        cluster.append(mentions[j])
                        visited[j] = True
                        queue.append(j)
            
            clusters.append(cluster)
        
        return clusters
    
    def merge_clusters(self, clusters: List[List[Dict[str, Any]]]) -> List[List[Dict[str, Any]]]:
        """
        Merge similar clusters.
        
        If two clusters have high similarity (based on centroids), merge them.
        
        Args:
            clusters: List of clusters
        
        Returns:
            Merged clusters
        """
        if len(clusters) <= 1:
            return clusters
        
        # Calculate cluster centroids
        centroids = []
        for cluster in clusters:
            centroid = self._calculate_centroid(cluster)
            if centroid is not None:
                centroids.append(centroid)
            else:
                centroids.append(None)
        
        # Merge clusters with similar centroids
        merged = []
        used = [False] * len(clusters)
        
        for i in range(len(clusters)):
            if used[i]:
                continue
            
            current_cluster = clusters[i]
            current_centroid = centroids[i]
            
            if current_centroid is None:
                merged.append(current_cluster)
                used[i] = True
                continue
            
            # Find similar clusters to merge
            for j in range(i + 1, len(clusters)):
                if used[j]:
                    continue
                
                other_centroid = centroids[j]
                if other_centroid is None:
                    continue
                
                similarity = cosine_similarity(current_centroid, other_centroid)
                if similarity >= self.similarity_threshold:
                    # Merge clusters
                    current_cluster.extend(clusters[j])
                    used[j] = True
            
            merged.append(current_cluster)
            used[i] = True
        
        logger.debug(f"Merged {len(clusters)} clusters into {len(merged)} clusters")
        
        return merged
    
    def _calculate_centroid(self, cluster: List[Dict[str, Any]]) -> Optional[np.ndarray]:
        """
        Calculate centroid embedding for a cluster.
        
        Args:
            cluster: List of mentions with embeddings
        
        Returns:
            Centroid embedding vector or None
        """
        if not cluster:
            return None
        
        embeddings = []
        for mention in cluster:
            emb = mention.get('embedding')
            if emb:
                embeddings.append(np.array(emb, dtype=np.float32))
        
        if not embeddings:
            return None
        
        # Average embeddings
        centroid = np.mean(embeddings, axis=0)
        return centroid

