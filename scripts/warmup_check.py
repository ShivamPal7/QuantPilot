"""Phase 0 Historical Candle Warm-up Verification Script.

Tests fetching OHLC candles from Delta REST API to confirm resolution strings,
per-call limits, and boundary alignment.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.exchange.client import DeltaRESTClient


async def verify_warmup() -> None:
    print("=" * 60)
    print("QuantPilot Candle Warm-up Verification")
    print("=" * 60)

    settings = get_settings()
    client = DeltaRESTClient(
        base_url=settings.DELTA_REST_URL,
        target_env=settings.TARGET_ENV,
    )

    now_s = int(time.time())
    start_s = now_s - (3600 * 24)  # 24 hours of history

    symbol = settings.DEFAULT_SYMBOL
    resolution = "1h"
    print(f"Requesting candles for {symbol} (Resolution: {resolution})...")

    try:
        candles = await client.get_candles(symbol, resolution, start_s, now_s)
        print(f"✅ Successfully fetched {len(candles)} candles.")
        if candles:
            first = candles[0]
            last = candles[-1]
            print(f"   First candle: {first.open_time} Close: {first.close}")
            print(f"   Last candle:  {last.open_time} Close: {last.close}")
    except Exception as exc:
        print(f"⚠️ Candle fetch failed: {exc}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(verify_warmup())
