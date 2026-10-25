# Module Ownership Register

Per `agent.md` Section 3.3, every module has exactly one named human owner who can explain its logic, design choices, and edge cases to judges during the demo evaluation.

---

| Module | Primary Human Owner | Secondary Reviewer | Authorship Zone | Core Responsibilities |
|---|---|---|---|---|
| **`app.signals.trend`** | Human Lead | Team Member A | Red | Trend-following strategy logic, ATR stop calculation, reason codes |
| **`app.signals.reversion`** | Human Lead | Team Member B | Red | Short-horizon mean-reversion logic, stationarity/half-life check |
| **`app.signals.regime`** | Team Member A | Human Lead | Red | Regime filter (trending/ranging/chaotic), dwell time, hysteresis |
| **`app.shadow.allocator`** | Team Member A | Team Member C | Red | Bayesian Thompson sampling, exploration floor, stand-aside override |
| **`app.risk`** | Team Member B | Human Lead | Red | Risk gate rules, sizing, volatility scaling, kill-switch policy |
| **`app.execution`** | Team Member B | Team Member C | Red / Amber | Order intent generation, bracket attachment, reconciliation |
| **`app.journal.narrative`** | Team Member C | Human Lead | Red | Decision narrative template generation |
| **`app.exchange`** | Team Member C | AI Scaffolder | Green / Amber | Delta REST/WS connectivity, signing, rate limiter, guard |
| **`app.data`** | Team Member C | AI Scaffolder | Amber | Candle store, freshness tracking, stream builder |
| **`app.api` & `app.dashboard`** | Team Member C | AI Scaffolder | Green | FastAPI control plane, endpoints, static dashboard |
