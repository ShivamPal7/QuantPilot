"""Unit tests for configuration loading."""

from __future__ import annotations

import unittest

from app.core.config import AppSettings, load_engine_config


class TestConfig(unittest.TestCase):
    def test_load_default_config(self) -> None:
        cfg = load_engine_config("config/default.json")
        self.assertEqual(cfg["profile"], "default")
        self.assertEqual(cfg["symbol"], "BTCUSD")
        self.assertIn("strategies", cfg)
        self.assertIn("risk", cfg)

    def test_load_demo_config(self) -> None:
        cfg = load_engine_config("config/demo.json")
        self.assertEqual(cfg["profile"], "demo")
        self.assertEqual(cfg["timeframe"], "1m")

    def test_app_settings_default(self) -> None:
        settings = AppSettings()
        self.assertEqual(settings.TARGET_ENV, "testnet")
        self.assertIn("testnet", settings.DELTA_REST_URL)


if __name__ == "__main__":
    unittest.main()
