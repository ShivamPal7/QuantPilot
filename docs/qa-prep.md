# Q&A Preparation for Judges

Per `agent.md` Section 3.3, this file prepares the human team for technical judge questions on every module with crisp two-sentence explanations.

---

### 1. System Architecture & Boundaries
- **Q:** *Why did you split the system into pure decision logic and edge adapters?*
  - **A:** By keeping strategies, risk rules, and the allocator completely pure and deterministic without I/O, we can replay market scenarios, test every failure mode in unit tests, and simulate chaos scenarios reliably without risk of spurious exchange side-effects.

### 2. Strategy Logic & Regimes
- **Q:** *How do you prevent whipsaw in choppy markets?*
  - **A:** Our regime filter evaluates trend strength and choppiness with hysteresis to prevent flickering; when conditions are detected as ranging or chaotic, the regime filter enforces a stand-aside gate that halts trend entries immediately.

### 3. Risk Management & Safeguards
- **Q:** *What happens if the exchange disconnects or reports ambiguous order states?*
  - **A:** The system treats unknown states as blocking and reconciles via idempotent client order IDs before any retry. Furthermore, every entered position is strictly accompanied by server-side bracket orders (take-profit and stop-loss) directly on Delta Exchange, so protection persists even during total network loss.

### 4. Kill Switch & Chaos
- **Q:** *What triggers your kill switch and how does it recover?*
  - **A:** The kill switch triggers on daily loss breaches, drawdown ladder halts, data stalls, or persistent reconciliation mismatches, immediately cancelling working orders and closing open positions via reduce-only orders. Resetting requires an explicit authenticated API call with a human confirmation field after exchange state confirms flat.

### 5. AI Usage & Authorship
- **Q:** *How much of this codebase was AI-generated?*
  - **A:** Only ~15% of our codebase (boilerplate scaffolding, typing contracts, HTTP/WS wrappers, and testing harnesses) was AI-scaffolded in the Green Zone. All core strategy logic, risk policies, allocator mathematics, and execution state machines are 100% human-authored and owned.
