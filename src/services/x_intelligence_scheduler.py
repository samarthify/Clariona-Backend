"""
X Intelligence Scheduler - Runs Rising (20 min), Stabilization (30 min), Safety Net (6 h) jobs.

Uses same rules as Filtered Stream. Each job runs in a thread to avoid blocking the event loop.
"""

import asyncio
import logging
import os
from datetime import datetime

from api.database import SessionLocal
from services.x_recent_search_jobs import run_rising, run_stabilization, run_safety_net

logger = logging.getLogger("services.x_intelligence_scheduler")

# Enable/disable the search layers (stream is separate)
X_LAYERS_ENABLED = os.getenv("X_LAYERS_ENABLED", "true").lower() == "true"


def _run_rising_sync():
    session = SessionLocal()
    try:
        processed, skipped = run_rising(session)
        logger.info(f"X Rising job: processed={processed} rules_skipped={skipped}")
    except Exception as e:
        logger.error(f"X Rising job error: {e}", exc_info=True)
    finally:
        session.close()


def _run_stabilization_sync():
    session = SessionLocal()
    try:
        processed, skipped = run_stabilization(session)
        logger.info(f"X Stabilization job: processed={processed} rules_skipped={skipped}")
    except Exception as e:
        logger.error(f"X Stabilization job error: {e}", exc_info=True)
    finally:
        session.close()


def _run_safety_net_sync():
    session = SessionLocal()
    try:
        processed, skipped = run_safety_net(session)
        logger.info(f"X Safety Net job: processed={processed} rules_skipped={skipped}")
    except Exception as e:
        logger.error(f"X Safety Net job error: {e}", exc_info=True)
    finally:
        session.close()


class XIntelligenceScheduler:
    """Schedules Rising (20 min), Stabilization (30 min), Safety Net (6 h) jobs."""

    def __init__(self):
        self._scheduler = None
        self._running = False

    async def start(self):
        if not X_LAYERS_ENABLED:
            logger.info("X Intelligence layers disabled (X_LAYERS_ENABLED=false)")
            return
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.interval import IntervalTrigger
        except ImportError:
            logger.error("APScheduler not installed - X Intelligence jobs will not run")
            return

        self._scheduler = AsyncIOScheduler()
        loop = asyncio.get_event_loop()

        async def run_rising_async():
            await loop.run_in_executor(None, _run_rising_sync)

        async def run_stabilization_async():
            await loop.run_in_executor(None, _run_stabilization_sync)

        async def run_safety_net_async():
            await loop.run_in_executor(None, _run_safety_net_sync)

        # Run sync jobs in executor so we don't block the event loop
        self._scheduler.add_job(
            run_rising_async,
            trigger=IntervalTrigger(minutes=20),
            id="x_rising",
            name="X Rising (20 min)",
            replace_existing=True,
        )
        self._scheduler.add_job(
            run_stabilization_async,
            trigger=IntervalTrigger(minutes=30),
            id="x_stable",
            name="X Stabilization (30 min)",
            replace_existing=True,
        )
        self._scheduler.add_job(
            run_safety_net_async,
            trigger=IntervalTrigger(hours=6),
            id="x_safety",
            name="X Safety Net (6 h)",
            replace_existing=True,
        )

        self._scheduler.start()
        self._running = True
        logger.info("X Intelligence Scheduler started (Rising 20m, Stable 30m, Safety 6h)")

    async def stop(self):
        self._running = False
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("X Intelligence Scheduler stopped.")
