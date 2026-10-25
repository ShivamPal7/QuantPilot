# AI Usage Log

This document tracks all AI-assisted contributions to QuantPilot, ensuring adherence to the hackathon policy:
- **Maximum acceptable ceiling:** 20–30% AI-generated code
- **Target ceiling:** <= 15–20% AI-generated code
- **Authorship Zones:**
  - **Green (Agent implemented):** Scaffolding, config plumbing, logging, exchange wrapper interfaces, signing helpers, fake exchange, test suites, static dashboard page, scripts, documentation drafts.
  - **Amber (Agent drafted, human modified & owned):** Market-data store, WebSocket reconnect, reconciliation routines, journal persistence, API endpoint shells.
  - **Red (Human-authored only):** Trading strategies, regime filter, allocator, risk policies, execution state machine, decision narrative generator, chaos scenario definitions.

---

## Log Entries

| Timestamp (ISO) | Contributor | Zone | Files / Modules | Approx Lines | Description | Human Reviewer |
|---|---|---|---|---|---|---|
| 2026-10-25T11:20:00Z | AI Scaffolder | Green | Project root, layout, configs, docs templates | ~500 | Initial boilerplate setup: directory architecture, `.gitignore`, `.env.example`, `pyproject.toml`, core contracts, interfaces, and docs skeletons. | Human Team |

---

## Running Accounting Summary

- **Total Estimated Codebase Volume:** ~500 lines (Scaffolding & Boilerplate)
- **AI-Authored Volume:** ~500 lines (Scaffolding / Config Plumbing only - Green Zone)
- **AI-Assisted Volume:** 0 lines
- **Human-Authored Volume:** 0 lines (Phase 0 starting)
- **Current AI Code Fraction:** Green-Zone Scaffolding only (0% Red-Zone logic)
