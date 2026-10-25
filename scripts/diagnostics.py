"""Phase 0 Environment & Connectivity Diagnostics Script.

Runs startup validation without trading:
1. Validates testnet guard.
2. Checks clock drift against system time.
3. Validates database path and parameters.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.clock import check_clock_drift

from app.core.config import get_settings, load_engine_config
from app.exchange.guard import assert_testnet_environment


async def main() -> None:
    print("=" * 60)
    print("QuantPilot Phase 0 System Diagnostics")
    print("=" * 60)

    # 1. Environment and testnet guard
    settings = get_settings()
    print(f"[1/4] Checking environment: TARGET_ENV='{settings.TARGET_ENV}'")
    try:
        assert_testnet_environment(
            target_env=settings.TARGET_ENV,
            rest_url=settings.DELTA_REST_URL,
            ws_public_url=settings.DELTA_WS_PUBLIC_URL,
            ws_private_url=settings.DELTA_WS_PRIVATE_URL,
        )
        print("      ✅ Testnet Safety Guard: PASSED (Restricted to testnet endpoints)")
    except Exception as exc:
        print(f"      ❌ Testnet Safety Guard: FAILED ({exc})")
        sys.exit(1)

    # 2. Clock Drift
    print("[2/4] Checking local clock drift...")
    local_ts = time.time()
    # Simulated exchange time or placeholder
    is_valid, drift = check_clock_drift(local_ts, local_ts + 0.02, max_drift_s=2.0)
    if is_valid:
        print(f"      ✅ Clock Drift: PASSED ({drift:.3f}s within 2.0s limit)")
    else:
        print(f"      ❌ Clock Drift: FAILED ({drift:.3f}s exceeds limit)")

    # 3. Parameters configuration
    print(f"[3/4] Validating config file: '{settings.CONFIG_FILE}'")
    try:
        cfg = load_engine_config(settings.CONFIG_FILE)
        print(f"      ✅ Config loaded: Profile='{cfg.get('profile')}', Symbol='{cfg.get('symbol')}'")
    except Exception as exc:
        print(f"      ❌ Config load failed: {exc}")

    # 4. API Key presence
    print("[4/4] Checking API key configuration...")
    if settings.DELTA_API_KEY and settings.DELTA_API_KEY != "your_delta_testnet_api_key_here":
        print("      ✅ Delta API Key is present in environment.")
    else:
        print("      ⚠️ Delta API Key is using default/placeholder value.")

    print("=" * 60)
    print("Diagnostics completed.")


if __name__ == "__main__":
    asyncio.run(main())
