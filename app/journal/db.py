"""SQLite database setup for the Decision Journal.

Per Section 9.7 of agent.md:
Stores decisions, orders, fills, shadow trades, shadow stats snapshots,
engine events, and configuration snapshots.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def init_database(db_path: str = "quantpilot.db") -> sqlite3.Connection:
    """Initialize database tables if they do not exist."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    with conn:
        # Decisions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                close_price REAL NOT NULL,
                regime_label TEXT NOT NULL,
                selected_strategy TEXT,
                verdict_action TEXT NOT NULL,
                approved_contracts INTEGER NOT NULL,
                rejection_reason TEXT,
                narrative TEXT NOT NULL,
                raw_payload TEXT NOT NULL
            );
        """)

        # Engine Events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS engine_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL
            );
        """)

        # Orders table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                client_order_id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL,
                exchange_order_id TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                size_contracts INTEGER NOT NULL,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Config Snapshots table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config_snapshots (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                config_json TEXT NOT NULL
            );
        """)

    return conn
