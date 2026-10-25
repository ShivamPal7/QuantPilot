"""Decision Journal persistence writer.

Per Section 9.7 of agent.md:
Persists decision records, non-trades, and engine events into SQLite.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.core.contracts import DecisionRecord
from app.core.events import BaseEngineEvent
from app.core.logging import get_logger

logger = get_logger("journal_writer")


class JournalWriter:
    """Manages SQLite writes for decisions and engine events."""

    def __init__(self, db_conn: sqlite3.Connection) -> None:
        self.conn = db_conn

    def write_decision(self, record: DecisionRecord) -> None:
        """Insert decision record into SQLite."""
        sql = """
            INSERT OR REPLACE INTO decisions (
                decision_id, timestamp, symbol, timeframe, close_price,
                regime_label, selected_strategy, verdict_action, approved_contracts,
                rejection_reason, narrative, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self.conn:
                self.conn.execute(
                    sql,
                    (
                        record.decision_id,
                        record.timestamp.isoformat(),
                        record.symbol,
                        record.timeframe,
                        float(record.candle_close_price),
                        record.regime.label.value,
                        record.allocation.selected_strategy,
                        record.risk_verdict.action.value,
                        record.risk_verdict.approved_contracts,
                        record.risk_verdict.rejection_reason,
                        record.narrative,
                        json.dumps({
                            "binding_rule": record.risk_verdict.binding_rule,
                            "intent": str(record.intent) if record.intent else None,
                        }),
                    ),
                )
        except Exception as exc:
            logger.error("Failed to write decision %s to journal: %s", record.decision_id, exc)

    def write_event(self, event: BaseEngineEvent) -> None:
        """Insert engine event into SQLite."""
        sql = "INSERT INTO engine_events (timestamp, event_type, details) VALUES (?, ?, ?)"
        try:
            with self.conn:
                self.conn.execute(
                    sql,
                    (
                        event.timestamp.isoformat(),
                        event.event_type,
                        json.dumps(getattr(event, "details", {})),
                    ),
                )
        except Exception as exc:
            logger.error("Failed to write event %s: %s", event.event_type, exc)
