"""
XStreamRulesManager - Syncs rules from x_stream_rules table to X API.

Loads active rules from DB, diffs with current X API rules, and POSTs add/delete.
Stores x_rule_id back to DB for future deletes.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

# Load env
try:
    from dotenv import load_dotenv
    for p in [Path(__file__).resolve().parent.parent.parent / "config" / ".env",
              Path(__file__).resolve().parent.parent.parent / ".env"]:
        if p.exists():
            load_dotenv(p, override=False)
except ImportError:
    pass

logger = logging.getLogger("services.x_stream_rules_manager")

BASE_URL = "https://api.x.com"
RULES_URL = f"{BASE_URL}/2/tweets/search/stream/rules"


class XStreamRulesManager:
    """Sync rules from DB to X API."""

    def __init__(self, session: Session, bearer_token: Optional[str] = None):
        self.session = session
        self.bearer_token = bearer_token or os.environ.get("X_BEARER_TOKEN") or os.environ.get("BEARER_TOKEN")
        if not self.bearer_token:
            logger.warning("X_BEARER_TOKEN/BEARER_TOKEN not set - XStreamRulesManager will not sync")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.bearer_token}"}

    def get_x_rules(self) -> List[Dict[str, Any]]:
        """GET current rules from X API."""
        if not self.bearer_token:
            return []
        try:
            resp = requests.get(RULES_URL, headers=self._headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data") or []
        except Exception as e:
            logger.error(f"Failed to GET X API rules: {e}")
            return []

    def sync_rules_to_x_api(self) -> Dict[str, int]:
        """
        Sync DB rules to X API: add new, delete removed, update x_rule_id.
        Returns dict with created, deleted counts.
        """
        from src.api.models import XStreamRule

        if not self.bearer_token:
            logger.warning("Bearer token not set, skipping X API rule sync")
            return {"created": 0, "deleted": 0}

        # Load active rules from DB
        db_rules = self.session.query(XStreamRule).filter(XStreamRule.is_active == True).all()
        db_by_value = {(r.value, r.tag): r for r in db_rules}

        # Current X API rules
        x_rules = self.get_x_rules()
        x_by_id = {r["id"]: r for r in x_rules}
        x_by_value_tag = {(r.get("value"), r.get("tag")): r for r in x_rules}

        created = 0
        deleted = 0

        # Add rules in DB that are not in X API
        to_add = []
        for (value, tag), db_rule in db_by_value.items():
            key = (value, tag)
            if key not in x_by_value_tag:
                to_add.append({"value": value, "tag": tag or None})
                # We'll get ids from response and update db_rule.x_rule_id

        if to_add:
            try:
                payload = {"add": to_add}
                resp = requests.post(RULES_URL, headers=self._headers(), json=payload, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                new_data = data.get("data") or []
                meta = data.get("meta", {})
                summary = meta.get("summary", {}) if isinstance(meta, dict) else {}
                created = summary.get("created", len(new_data))
                # Map back: response order may match add order
                for i, r in enumerate(new_data):
                    rid = r.get("id")
                    if rid and i < len(to_add):
                        add_item = to_add[i]
                        val, tag = add_item.get("value"), add_item.get("tag")
                        db_rule = db_by_value.get((val, tag))
                        if db_rule:
                            db_rule.x_rule_id = rid
                self.session.commit()
                logger.info(f"XStreamRulesManager: Added {created} rules to X API")
            except Exception as e:
                logger.error(f"Failed to add rules to X API: {e}")
                self.session.rollback()

        # Delete X API rules that are no longer in DB (by value+tag) or have is_active=False
        active_value_tags = set(db_by_value.keys())
        to_delete_ids = []
        for xr in x_rules:
            xid = xr.get("id")
            key = (xr.get("value"), xr.get("tag"))
            if key not in active_value_tags:
                to_delete_ids.append(xid)
            else:
                # Ensure DB has x_rule_id
                db_rule = db_by_value.get(key)
                if db_rule and not db_rule.x_rule_id and xid:
                    db_rule.x_rule_id = xid

        # Also delete rules whose DB row has is_active=False but we have x_rule_id
        inactive = self.session.query(XStreamRule).filter(
            XStreamRule.is_active == False,
            XStreamRule.x_rule_id.isnot(None)
        ).all()
        for r in inactive:
            if r.x_rule_id and r.x_rule_id not in to_delete_ids:
                to_delete_ids.append(r.x_rule_id)
            r.x_rule_id = None  # clear so we don't try to delete again

        if to_delete_ids:
            try:
                payload = {"delete": {"ids": to_delete_ids}}
                resp = requests.post(RULES_URL, headers=self._headers(), json=payload, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                meta = data.get("meta", {})
                summary = meta.get("summary", {}) if isinstance(meta, dict) else {}
                deleted = summary.get("deleted", len(to_delete_ids))
                self.session.commit()
                logger.info(f"XStreamRulesManager: Deleted {deleted} rules from X API")
            except Exception as e:
                logger.error(f"Failed to delete rules from X API: {e}")
                self.session.rollback()
        else:
            self.session.commit()

        return {"created": created, "deleted": deleted}
