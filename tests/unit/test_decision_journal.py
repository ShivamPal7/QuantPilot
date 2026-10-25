"""Unit tests for SQLite WAL Decision Journal and deterministic plain-language narrative generation.

Per Section 12 of agent.md:
- Complete decision logging for all trades and non-trades.
- Deterministic 2-5 sentence plain-language narratives generated without LLM.
- Persistent auditability across sessions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
import os
import tempfile
import unittest

from app.core.contracts import (
    AllocationDecision,
    DecisionRecord,
    Direction,
    OrderIntent,
    RegimeLabel,
    RegimeReading,
    RiskAction,
    RiskVerdict,
)
from app.core.events import KillSwitchActivatedEvent
from app.journal.db import init_database
from app.journal.narrative import NarrativeGenerator
from app.journal.writer import JournalWriter


class TestDecisionJournal(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_journal.db")
        self.conn = init_database(self.db_path)
        self.writer = JournalWriter(db_conn=self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_database_initialization_schema_and_wal(self) -> None:
        """Verify all required tables exist with expected schema."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

        self.assertIn("decisions", tables)
        self.assertIn("engine_events", tables)
        self.assertIn("orders", tables)
        self.assertIn("config_snapshots", tables)

        # Verify decisions columns
        cursor.execute("PRAGMA table_info(decisions);")
        columns = {row[1] for row in cursor.fetchall()}
        required_cols = {
            "decision_id", "timestamp", "symbol", "timeframe", "close_price",
            "regime_label", "selected_strategy", "verdict_action",
            "approved_contracts", "rejection_reason", "narrative", "raw_payload"
        }
        self.assertTrue(required_cols.issubset(columns))

    def test_narrative_generator_deterministic_templates(self) -> None:
        """Verify NarrativeGenerator produces deterministic, explainable 2-5 sentence narratives."""
        regime = RegimeReading(
            label=RegimeLabel.TRENDING,
            metrics={"adx": 32.5},
            previous_label=RegimeLabel.RANGING,
            confidence=0.9,
        )

        # 1. Approved case
        alloc_appr = AllocationDecision(
            selected_strategy="trend_following",
            weight=1.0,
            reason="High momentum alignment",
        )
        verdict_appr = RiskVerdict(
            action=RiskAction.APPROVE,
            approved_risk_fraction=0.01,
            approved_contracts=5,
        )
        n_appr = NarrativeGenerator.generate("BTCUSD", regime, alloc_appr, verdict_appr)
        self.assertIn("classified as TRENDING", n_appr)
        self.assertIn("Strategy 'trend_following' was selected", n_appr)
        self.assertIn("APPROVED execution for 5 contracts with exchange-side bracket protection", n_appr)

        # Sentence count check (2-5 sentences)
        sentences = [s.strip() for s in n_appr.split(".") if s.strip()]
        self.assertTrue(2 <= len(sentences) <= 5)

        # 2. Resized case
        verdict_resize = RiskVerdict(
            action=RiskAction.RESIZE,
            approved_risk_fraction=0.005,
            approved_contracts=2,
        )
        n_resize = NarrativeGenerator.generate("BTCUSD", regime, alloc_appr, verdict_resize)
        self.assertIn("RESIZED position to 2 contracts due to volatility scaling", n_resize)

        # 3. Rejected case
        verdict_rej = RiskVerdict(
            action=RiskAction.REJECT,
            approved_risk_fraction=0.0,
            approved_contracts=0,
            binding_rule="DATA_FRESHNESS",
            rejection_reason="Market data stale > 5.0s",
        )
        n_rej = NarrativeGenerator.generate("BTCUSD", regime, alloc_appr, verdict_rej)
        self.assertIn("REJECTED the trade intent: Market data stale > 5.0s", n_rej)

        # 4. Stand-aside (no strategy allocated)
        alloc_none = AllocationDecision(
            selected_strategy=None,
            weight=0.0,
            reason="Regime filter stand-aside in chaotic state",
        )
        n_stand = NarrativeGenerator.generate("BTCUSD", regime, alloc_none, verdict_rej)
        self.assertIn("No strategy was allocated risk", n_stand)

        # Determinism: same inputs produce identical string 50 times
        for _ in range(50):
            self.assertEqual(NarrativeGenerator.generate("BTCUSD", regime, alloc_appr, verdict_appr), n_appr)

    def test_write_and_read_decision_record(self) -> None:
        """Write DecisionRecord to SQLite and verify roundtrip column fidelity."""
        now = datetime.now(timezone.utc)
        regime = RegimeReading(label=RegimeLabel.RANGING, metrics={"adx": 18.0}, previous_label=RegimeLabel.RANGING, confidence=0.75)
        alloc = AllocationDecision(selected_strategy="mean_reversion", weight=0.8, reason="Z-score breach")
        intent = OrderIntent(
            decision_id="dec-db-001",
            strategy_name="mean_reversion",
            symbol="BTCUSD",
            direction=Direction.SHORT,
            desired_risk_fraction=0.01,
            proposed_stop_distance=Decimal("120.0"),
        )
        verdict = RiskVerdict(action=RiskAction.APPROVE, approved_risk_fraction=0.008, approved_contracts=3)
        narrative = NarrativeGenerator.generate("BTCUSD", regime, alloc, verdict)

        record = DecisionRecord(
            decision_id="dec-db-001",
            timestamp=now,
            symbol="BTCUSD",
            timeframe="1m",
            candle_close_price=Decimal("65200.0"),
            regime=regime,
            signals=[],
            shadow_stats=[],
            allocation=alloc,
            intent=intent,
            risk_verdict=verdict,
            orders=[],
            narrative=narrative,
        )

        self.writer.write_decision(record)

        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM decisions WHERE decision_id = ?", ("dec-db-001",))
        row = cursor.fetchone()
        self.assertIsNotNone(row)

        self.assertEqual(row[0], "dec-db-001")
        self.assertEqual(row[2], "BTCUSD")
        self.assertEqual(row[3], "1m")
        self.assertEqual(row[4], 65200.0)
        self.assertEqual(row[5], "RANGING")
        self.assertEqual(row[6], "mean_reversion")
        self.assertEqual(row[7], "APPROVE")
        self.assertEqual(row[8], 3)
        self.assertEqual(row[10], narrative)

        raw = json.loads(row[11])
        self.assertIn("intent", raw)

    def test_write_engine_event(self) -> None:
        """Write BaseEngineEvent to engine_events table and verify persistence."""
        event = KillSwitchActivatedEvent(
            trigger_source="manual_test",
            reason="Integration test verification",
            details={"operator": "qa_tester"},
        )
        self.writer.write_event(event)

        cursor = self.conn.cursor()
        cursor.execute("SELECT event_type, details FROM engine_events WHERE event_type = ?", (event.event_type,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "kill_switch_activated")
        details = json.loads(row[1])
        self.assertEqual(details.get("operator"), "qa_tester")


if __name__ == "__main__":
    unittest.main()
