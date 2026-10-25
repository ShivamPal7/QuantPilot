# Architecture and Engineering Decisions Log (ADR)

All design deviations, exchange discoveries, and architectural choices are recorded here.

---

## ADR 001: Initial Architecture & Scaffolding
- **Date:** 2026-10-25
- **Status:** Approved
- **Context:** Setting up the project skeleton according to `agent.md` (Section 12).
- **Decision:**
  - Structure application into clean layers: `api`, `core`, `exchange`, `data`, `signals`, `shadow`, `risk`, `execution`, `journal`, and `dashboard`.
  - Enforce pure-logic core (`signals`, `risk`, `shadow`, `allocator`) with I/O and adapters strictly isolated at the edges.
  - Implement a mandatory testnet-only guard at `app.exchange.guard` to prevent connecting to production hostnames.
- **Consequences:** Clean separation of concerns, high testability with in-memory fake exchanges, strict safety against real-money risk.

---

## ADR 002: Testnet Target Environment
- **Date:** 2026-10-25
- **Status:** Approved
- **Context:** Delta Exchange has multiple environments (Global prod, Global testnet, India prod, India testnet / Demo account).
- **Decision:**
  - Target India Testnet / Demo Account:
    - REST: `https://cdn-ind.testnet.deltaex.org`
    - WS Public: `wss://socket-ind-pub.testnet.deltaex.org`
    - WS Private: `wss://socket-ind.testnet.deltaex.org`
  - Explicitly reject production hosts: `api.delta.exchange`, `cdn.deltaex.org`, `socket.deltaex.org`, `socket-pub.deltaex.org`.
