"""Typed configuration management and environment loading.

Enforces Section 2.1 and 11 of agent.md.
Supports pydantic-settings when installed, with a standard library fallback.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Optional import of pydantic-settings if installed
try:
    from pydantic import Field
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class AppSettings(BaseSettings):
        """Environment configuration loaded from environment variables or .env file."""

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

        TARGET_ENV: str = Field(default="testnet", description="Must be 'testnet'")
        DELTA_REST_URL: str = Field(
            default="https://cdn-ind.testnet.deltaex.org",
            description="REST API base URL (India testnet)",
        )
        DELTA_WS_PUBLIC_URL: str = Field(
            default="wss://socket-ind-pub.testnet.deltaex.org",
            description="Public WebSocket URL",
        )
        DELTA_WS_PRIVATE_URL: str = Field(
            default="wss://socket-ind.testnet.deltaex.org",
            description="Private authenticated WebSocket URL",
        )

        DELTA_API_KEY: str = Field(default="", description="Delta Exchange API Key")
        DELTA_API_SECRET: str = Field(default="", description="Delta Exchange API Secret")
        CONTROL_PLANE_SECRET: str = Field(
            default="dev_secret_change_me",
            description="Shared secret for state-changing endpoints",
        )

        DATABASE_PATH: str = Field(default="quantpilot.db", description="SQLite database path")
        CONFIG_FILE: str = Field(default="config/default.json", description="Parameter config file path")
        LOG_LEVEL: str = Field(default="INFO", description="Log level")
        DEFAULT_SYMBOL: str = Field(default="BTCUSD", description="Default trading symbol")

except ImportError:
    # Standard library fallback when pydantic-settings is not yet installed
    @dataclass
    class AppSettings:  # type: ignore[no-redef]
        """Fallback environment configuration using os.environ."""

        TARGET_ENV: str = os.getenv("TARGET_ENV", "testnet")
        DELTA_REST_URL: str = os.getenv("DELTA_REST_URL", "https://cdn-ind.testnet.deltaex.org")
        DELTA_WS_PUBLIC_URL: str = os.getenv("DELTA_WS_PUBLIC_URL", "wss://socket-ind-pub.testnet.deltaex.org")
        DELTA_WS_PRIVATE_URL: str = os.getenv("DELTA_WS_PRIVATE_URL", "wss://socket-ind.testnet.deltaex.org")

        DELTA_API_KEY: str = os.getenv("DELTA_API_KEY", "")
        DELTA_API_SECRET: str = os.getenv("DELTA_API_SECRET", "")
        CONTROL_PLANE_SECRET: str = os.getenv("CONTROL_PLANE_SECRET", "dev_secret_change_me")

        DATABASE_PATH: str = os.getenv("DATABASE_PATH", "quantpilot.db")
        CONFIG_FILE: str = os.getenv("CONFIG_FILE", "config/default.json")
        LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        DEFAULT_SYMBOL: str = os.getenv("DEFAULT_SYMBOL", "BTCUSD")


def load_engine_config(config_path: str | Path = "config/default.json") -> dict[str, Any]:
    """Load the JSON strategy and risk parameters."""
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found at: {path.resolve()}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Singleton instance
_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """Return cached AppSettings singleton."""
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings
