"""
PostgreSQL LISTEN for analysis_pending NOTIFY. Runs in a dedicated thread,
signals the main loop to wake immediately when new work arrives.
"""

import logging
import os
import select
import threading

logger = logging.getLogger('services.analysis_notify_listener')


def run_listen_loop(
    database_url: str,
    on_notify,
    stop_event: threading.Event,
    reconnect_delay: float = 5.0,
) -> None:
    """
    Run LISTEN analysis_pending in a loop. On NOTIFY, calls on_notify() (from listener thread).
    on_notify should be thread-safe (e.g. loop.call_soon_threadsafe(event.set)).
    """
    import psycopg2
    
    conn = None
    while not stop_event.is_set():
        try:
            conn = psycopg2.connect(database_url)
            conn.set_isolation_level(0)  # autocommit for LISTEN
            with conn.cursor() as cur:
                cur.execute("LISTEN analysis_pending")
            logger.info("AnalysisNotifyListener: LISTEN analysis_pending started")
            
            while not stop_event.is_set():
                if select.select([conn], [], [], 1.0)[0]:
                    conn.poll()
                    while conn.notifies:
                        n = conn.notifies.pop(0)
                        logger.debug("AnalysisNotifyListener: received NOTIFY %s", n.channel)
                        try:
                            on_notify()
                        except Exception as e:
                            logger.warning("AnalysisNotifyListener: on_notify failed: %s", e)
        except Exception as e:
            logger.warning("AnalysisNotifyListener: %s (reconnecting in %.1fs)", e, reconnect_delay)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None
        if not stop_event.is_set():
            stop_event.wait(timeout=reconnect_delay)
    logger.info("AnalysisNotifyListener: stopped")
