"""Unit tests for the Testnet-Only Safety Guard.

Per Section 2.1 of agent.md.
Supports both unittest and pytest.
"""

from __future__ import annotations

import unittest

from app.exchange.guard import (
    DENIED_PRODUCTION_HOSTS,
    InvalidTestnetHostError,
    ProductionAccessProhibitedError,
    assert_testnet_environment,
    extract_hostname,
)


class TestTestnetGuard(unittest.TestCase):
    def test_extract_hostname(self) -> None:
        self.assertEqual(extract_hostname("https://cdn-ind.testnet.deltaex.org/v2"), "cdn-ind.testnet.deltaex.org")
        self.assertEqual(extract_hostname("wss://socket-ind.testnet.deltaex.org"), "socket-ind.testnet.deltaex.org")
        self.assertEqual(extract_hostname("api.delta.exchange:443"), "api.delta.exchange")

    def test_assert_testnet_environment_success(self) -> None:
        """Should pass when pointing to valid Delta India Testnet endpoints."""
        assert_testnet_environment(
            target_env="testnet",
            rest_url="https://cdn-ind.testnet.deltaex.org",
            ws_public_url="wss://socket-ind-pub.testnet.deltaex.org",
            ws_private_url="wss://socket-ind.testnet.deltaex.org",
        )

    def test_assert_testnet_environment_rejects_production(self) -> None:
        """Must raise ProductionAccessProhibitedError if target_env is not 'testnet'."""
        with self.assertRaises(ProductionAccessProhibitedError):
            assert_testnet_environment(
                target_env="production",
                rest_url="https://cdn-ind.testnet.deltaex.org",
            )

    def test_assert_testnet_environment_rejects_production_hosts(self) -> None:
        """Must reject all explicit production hostnames."""
        for prod_host in DENIED_PRODUCTION_HOSTS:
            with self.subTest(prod_host=prod_host):
                with self.assertRaises(ProductionAccessProhibitedError):
                    assert_testnet_environment(
                        target_env="testnet",
                        rest_url=f"https://{prod_host}/v2",
                    )

    def test_assert_testnet_environment_rejects_unrecognized_hosts(self) -> None:
        """Must reject arbitrary external domains."""
        with self.assertRaises(InvalidTestnetHostError):
            assert_testnet_environment(
                target_env="testnet",
                rest_url="https://api.binance.com",
            )


if __name__ == "__main__":
    unittest.main()
