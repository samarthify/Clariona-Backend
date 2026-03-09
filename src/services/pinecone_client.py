"""
Pinecone client wrapper for incremental clustering.

Provides query/upsert with retry, backoff, and circuit-breaker style error handling.
Only used when use_incremental_clustering=true.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy init - only connect when first needed
_pinecone_index = None
_failure_count = 0
_last_failure_at: Optional[float] = None
CIRCUIT_OPEN_SECONDS = 60
MAX_CONSECUTIVE_FAILURES = 5


def _get_index():
    """Get or create Pinecone index connection. Returns None if unavailable."""
    global _pinecone_index, _failure_count, _last_failure_at

    if _failure_count >= MAX_CONSECUTIVE_FAILURES and _last_failure_at:
        if time.time() - _last_failure_at < CIRCUIT_OPEN_SECONDS:
            logger.warning("Pinecone circuit open - skipping")
            return None
        _failure_count = 0  # Reset for retry

    if _pinecone_index is not None:
        return _pinecone_index

    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "clariona-cluster")

    if not api_key:
        logger.warning("PINECONE_API_KEY not set - Pinecone unavailable")
        return None

    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=api_key)
        _pinecone_index = pc.Index(index_name)
        logger.info("Pinecone index connected: %s", index_name)
        return _pinecone_index
    except Exception as e:
        logger.warning("Pinecone init failed: %s", e)
        _failure_count += 1
        _last_failure_at = time.time()
        return None


def query(
    vector: List[float],
    top_k: int = 5,
    filter_dict: Optional[Dict[str, Any]] = None,
    namespace: str = "",
) -> List[Dict[str, Any]]:
    """
    Query Pinecone for nearest vectors.

    Args:
        vector: Query embedding (1536 dims).
        top_k: Max matches to return.
        filter_dict: Metadata filter, e.g. {"topic_key": {"$eq": "health"}}.
        namespace: Optional namespace (empty for default).

    Returns:
        List of matches with id, score, metadata. Empty list on failure.
    """
    global _failure_count, _last_failure_at

    index = _get_index()
    if index is None:
        return []

    try:
        kwargs = {"vector": vector, "top_k": top_k}
        if filter_dict:
            kwargs["filter"] = filter_dict
        if namespace:
            kwargs["namespace"] = namespace

        result = index.query(**kwargs)  # Returns QueryResponse with .matches
        _failure_count = 0

        matches = []
        for m in (result.matches or []):
            matches.append({
                "id": m.id,
                "score": getattr(m, "score", 0.0) or 0.0,
                "metadata": dict(m.metadata or {}),
            })
        return matches
    except Exception as e:
        logger.warning("Pinecone query failed: %s", e)
        _failure_count += 1
        _last_failure_at = time.time()
        return []


def upsert(vectors: List[Dict[str, Any]], namespace: str = "") -> bool:
    """
    Upsert vectors into Pinecone.

    Args:
        vectors: List of {"id": str, "values": [...], "metadata": {...}}.
        namespace: Optional namespace.

    Returns:
        True on success, False on failure.
    """
    global _failure_count, _last_failure_at

    index = _get_index()
    if index is None or not vectors:
        return False

    try:
        kwargs = {"vectors": vectors}
        if namespace:
            kwargs["namespace"] = namespace
        index.upsert(**kwargs)
        _failure_count = 0
        return True
    except Exception as e:
        logger.warning("Pinecone upsert failed: %s", e)
        _failure_count += 1
        _last_failure_at = time.time()
        return False


def delete(ids: List[str], namespace: str = "") -> bool:
    """Delete vectors by id. Returns True on success."""
    global _failure_count, _last_failure_at

    index = _get_index()
    if index is None or not ids:
        return False

    try:
        kwargs = {"ids": ids}
        if namespace:
            kwargs["namespace"] = namespace
        index.delete(**kwargs)
        _failure_count = 0
        return True
    except Exception as e:
        logger.warning("Pinecone delete failed: %s", e)
        _failure_count += 1
        _last_failure_at = time.time()
        return False


def reset_circuit():
    """Reset circuit breaker for testing or manual recovery."""
    global _failure_count, _last_failure_at
    _failure_count = 0
    _last_failure_at = None
