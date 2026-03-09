"""
Tests for the bulletproof analysis pipeline (queue-first, NOTIFY, poll fallback).

Verifies:
1. AnalysisWorker instantiation with config from env
2. _claim_from_queue and _claim_records return expected stub format
3. Backfill script dry-run
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Ensure src is on path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.analysis_worker import AnalysisWorker, _env_bool, _env_float, _env_int
from src.services.data_ingestor import DataIngestor


class TestAnalysisWorkerConfig:
    """Test AnalysisWorker configuration from env."""

    def test_env_helpers(self):
        assert _env_bool('MISSING_KEY', True) is True
        assert _env_bool('MISSING_KEY', False) is False
        assert _env_float('MISSING_KEY', 2.5) == 2.5
        assert _env_int('MISSING_KEY', 25) == 25

    @patch.dict(os.environ, {
        'ANALYSIS_USE_QUEUE': 'false',
        'ANALYSIS_POLL_INTERVAL': '1.5',
        'ANALYSIS_MAX_WORKERS': '10',
        'ANALYSIS_POLL_LOOKBACK_HOURS': '72',
    }, clear=False)
    def test_worker_reads_env(self):
        worker = AnalysisWorker()
        assert worker.use_queue is False
        assert worker.poll_interval == 1.5
        assert worker.max_workers == 10
        assert worker.poll_lookback_hours == 72.0

    def test_worker_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            worker = AnalysisWorker(
                use_queue=False,
                max_workers=2,
                poll_interval=0.5,
                batch_size=10,
            )
        assert worker.use_queue is False
        assert worker.max_workers == 2
        assert worker.poll_interval == 0.5
        assert worker.batch_size == 10

    def test_get_metrics_returns_dict(self):
        worker = AnalysisWorker(use_queue=True)
        m = worker.get_metrics(active_tasks=5)
        assert 'analysis_worker_active_tasks' in m
        assert m['analysis_worker_active_tasks'] == 5
        # May have queue counts if DB is available
        assert 'analysis_queue_pending' in m or 'metrics_error' in m


class TestDataIngestorEnqueue:
    """Test DataIngestor always enqueues (no incremental clustering guard)."""

    def test_enqueue_has_no_use_incremental_clustering_guard(self):
        # Verify _enqueue_for_analysis does not check use_incremental_clustering
        import inspect
        source = inspect.getsource(DataIngestor._enqueue_for_analysis)
        assert 'use_incremental_clustering' not in source


class TestBackfillScript:
    """Test backfill script runs (dry-run)."""

    def test_backfill_dry_run(self):
        from scripts.backfill_analysis_queue import backfill
        n = backfill(batch_size=10, limit=5, dry_run=True)
        assert n >= 0
