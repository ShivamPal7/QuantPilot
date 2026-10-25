# Third-Party Dependencies and Attributions Register

Every third-party library, utility, or external code snippet is recorded here with its licence, maintenance state, purpose, and attribution.

---

## Approved Dependencies

| Name | Version | Licence | Purpose | Maintenance State / Notes |
|---|---|---|---|---|
| **fastapi** | `>=0.115.0` | MIT | Web framework for control plane & dashboard | Actively maintained, industry standard |
| **uvicorn** | `>=0.32.0` | BSD-3-Clause | ASGI server for FastAPI | Actively maintained |
| **pydantic** | `>=2.9.0` | MIT | Data parsing, validation, typed contracts | Actively maintained (v2 core in Rust) |
| **pydantic-settings** | `>=2.5.0` | MIT | Typed environment and configuration loading | Actively maintained |
| **httpx** | `>=0.27.0` | BSD-3-Clause | Async HTTP client for REST & testing | Actively maintained |
| **websockets** | `>=13.1` | BSD-3-Clause | Async WebSocket client for market data & order streams | Actively maintained |
| **pandas** | `>=2.2.0` | BSD-3-Clause | Dataframe processing for candle data | Actively maintained |
| **numpy** | `>=2.0.0` | BSD-3-Clause | Numerical calculations for indicators & stats | Actively maintained |
| **python-dotenv** | `>=1.0.1` | BSD-3-Clause | Loading `.env` file into environment variables | Actively maintained |
| **pytest** | `>=8.3.0` | MIT | Test framework for unit, integration, and chaos tests | Actively maintained |
| **pytest-asyncio** | `>=0.24.0` | Apache-2.0 | Async test support | Actively maintained |

---

## Prohibited Patterns
- No unreviewed external bot frameworks (orchestration must be owned by the team).
- No piped curl-to-shell installer scripts.
- No packages with copyleft licences (GPL/AGPL) that could conflict with distribution requirements.
