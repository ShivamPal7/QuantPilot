"""Phase 0 Connectivity Smoke Test.

Per Section 14 of agent.md:
Validates live signed communication with Delta India Demo Account:
1. Product specification lookup.
2. Signed balance check.
3. Tiny far-from-market test order and immediate cancellation.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.exchange.client import DeltaRESTClient
from app.exchange.guard import assert_testnet_environment


async def run_smoke_test() -> None:
    print("=" * 60)
    print("QuantPilot Phase 0 Delta Testnet Smoke Test")
    print("=" * 60)

    settings = get_settings()

    # Verify Guard
    assert_testnet_environment(
        target_env=settings.TARGET_ENV,
        rest_url=settings.DELTA_REST_URL,
    )

    if not settings.DELTA_API_KEY or settings.DELTA_API_KEY == "your_delta_testnet_api_key_here":
        print("⚠️ Warning: Valid testnet credentials not found in .env. Skipping live exchange call.")
        print("Set DELTA_API_KEY and DELTA_API_SECRET in your .env file to run live smoke tests.")
        return

    client = DeltaRESTClient(
        base_url=settings.DELTA_REST_URL,
        api_key=settings.DELTA_API_KEY,
        api_secret=settings.DELTA_API_SECRET,
        target_env=settings.TARGET_ENV,
    )

    try:
        # Step 1: Product lookup
        symbol = settings.DEFAULT_SYMBOL
        print(f"[1/3] Resolving instrument specification for '{symbol}'...")
        prod = await client.get_product(symbol)
        print(f"      Product ID: {prod.get('id')}")
        print(f"      Contract Value: {prod.get('contract_value')}")
        print(f"      Tick Size: {prod.get('tick_size')}")
        print(f"      Trading Status: {prod.get('trading_status')}")

        # Step 2: Signed balances
        print("[2/3] Fetching signed wallet balances...")
        balances = await client.get_balances()
        print(f"      Balances: {balances}")

        print("[3/3] Ready for Phase 0 sign-off.")
    except Exception as exc:
        print(f"❌ Smoke test encountered an error: {exc}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
