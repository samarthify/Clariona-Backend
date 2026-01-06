"""
Utility functions for calculating similarity between embeddings.
"""

import numpy as np
from typing import List, Union
import logging

logger = logging.getLogger('SimilarityUtils')


def cosine_similarity(vec1: Union[List[float], np.ndarray], 
                      vec2: Union[List[float], np.ndarray]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        vec1: First vector (list or numpy array)
        vec2: Second vector (list or numpy array)
    
    Returns:
        Cosine similarity score between -1 and 1 (typically 0-1 for normalized embeddings)
    """
    try:
        # Convert to numpy arrays if needed
        v1 = np.array(vec1, dtype=np.float64)
        v2 = np.array(vec2, dtype=np.float64)
        
        # Ensure same shape
        if v1.shape != v2.shape:
            raise ValueError(f"Vectors must have same shape: {v1.shape} vs {v2.shape}")
        
        # Calculate dot product
        dot_product = np.dot(v1, v2)
        
        # Calculate magnitudes
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        # Avoid division by zero
        if norm1 == 0 or norm2 == 0:
            logger.warning("Zero vector detected in cosine similarity calculation")
            return 0.0
        
        # Cosine similarity
        similarity = dot_product / (norm1 * norm2)
        
        # Clamp to [-1, 1] to handle floating point errors
        return float(np.clip(similarity, -1.0, 1.0))
    
    except Exception as e:
        logger.error(f"Error calculating cosine similarity: {e}")
        return 0.0


def cosine_similarity_batch(text_embedding: Union[List[float], np.ndarray],
                            topic_embeddings: dict) -> dict:
    """
    Calculate cosine similarity between a text embedding and multiple topic embeddings.
    
    Args:
        text_embedding: Text embedding vector (list or numpy array)
        topic_embeddings: Dictionary mapping topic_key to embedding vector
    
    Returns:
        Dictionary mapping topic_key to similarity score
    """
    try:
        text_vec = np.array(text_embedding, dtype=np.float64)
        
        similarities = {}
        for topic_key, topic_embedding in topic_embeddings.items():
            topic_vec = np.array(topic_embedding, dtype=np.float64)
            similarities[topic_key] = cosine_similarity(text_vec, topic_vec)
        
        return similarities
    
    except Exception as e:
        logger.error(f"Error calculating batch cosine similarity: {e}")
        return {}


def normalize_embedding(embedding: Union[List[float], np.ndarray]) -> np.ndarray:
    """
    Normalize an embedding vector to unit length.
    
    Args:
        embedding: Embedding vector to normalize
    
    Returns:
        Normalized numpy array
    """
    try:
        vec = np.array(embedding, dtype=np.float64)
        norm = np.linalg.norm(vec)
        
        if norm == 0:
            logger.warning("Zero vector cannot be normalized")
            return vec
        
        return vec / norm  # type: ignore[no-any-return]
    
    except Exception as e:
        logger.error(f"Error normalizing embedding: {e}")
        return np.array(embedding, dtype=np.float64)








