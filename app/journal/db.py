"""SQLite database setup for the Decision Journal.

Per Section 9.7 and 12.1 of agent.md:
Stores decisions, orders, fills, shadow trades, shadow stats snapshots,
engine events, and configuration snapshots in WAL mode.
"""

from __future__ import annotations

import sqlite3


def get_db_connection(db_path: str = "quantpilot.db") -> sqlite3.Connection:
    """Return a connection with WAL mode enabled."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_database(db_path: str = "quantpilot.db") -> sqlite3.Connection:
    """Initialize database tables if they do not exist with WAL mode."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    with conn:
        # Decisions table (trade and non-trade decisions)
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

        # Fills table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fills (
                fill_id TEXT PRIMARY KEY,
                client_order_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                fill_price REAL NOT NULL,
                size_contracts INTEGER NOT NULL,
                fee REAL NOT NULL,
                slippage_bps REAL NOT NULL,
                latency_ms REAL NOT NULL,
                filled_at TEXT NOT NULL
            );
        """)

        # Shadow Trades table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shadow_trades (
                trade_id TEXT PRIMARY KEY,
                strategy_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                contracts INTEGER NOT NULL,
                pnl REAL NOT NULL,
                opened_at TEXT NOT NULL,
                closed_at TEXT NOT NULL
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
