"""Unit tests for Delta API request signing."""

from __future__ import annotations

import unittest

from app.exchange.signing import build_auth_headers, generate_delta_signature


class TestSigning(unittest.TestCase):
    def test_generate_delta_signature(self) -> None:
        secret = "test_secret_key"
        method = "GET"
        timestamp = "1700000000"
        path = "/v2/wallet/balances"

        sig = generate_delta_signature(
            secret=secret,
            method=method,
            timestamp=timestamp,
            path=path,
        )
        self.assertIsInstance(sig, str)
        self.assertEqual(len(sig), 64)

    def test_build_auth_headers(self) -> None:
        headers = build_auth_headers(
            api_key="my_key",
            api_secret="my_secret",
            method="POST",
            path="/v2/orders",
            body='{"symbol":"BTCUSD"}',
            timestamp_seconds=1700000000,
        )

        self.assertEqual(headers["api-key"], "my_key")
        self.assertEqual(headers["timestamp"], "1700000000")
        self.assertIn("signature", headers)
        self.assertIn("User-Agent", headers)
        self.assertEqual(len(headers["signature"]), 64)


if __name__ == "__main__":
    unittest.main()
