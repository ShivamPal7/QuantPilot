# System Limitations and Failure Modes

Documenting what would break the system is a deliberate engineering feature designed to prove realistic risk awareness.

---

## Known Limitations

1. **Testnet Book Realism & Slippage:**
   - Delta Exchange Testnet order books are significantly thinner than production books.
   - Large market orders may incur unrealistic simulated slippage or partial fills.
   - Mitigation: Use marketable limit orders with IOC bounded tightly to the spread; measure realized slippage and feedback median slippage into the shadow cost model.

2. **Timeframe Compromise for Live Demo:**
   - Academic research on trend-following and momentum suggests optimal performance on multi-hour to multi-day horizons.
   - For a live 10-minute judging evaluation, a short-timeframe "Demo Profile" is provided to demonstrate live execution.
   - Disclaimer: Demo profile parameters are strictly for demonstration and not indicative of genuine production edge.

3. **Rate Limits & Polling Latency:**
   - Delta enforces 20,000 weight per 5-minute fixed window.
   - Heavy REST polling could exhaust quota rapidly.
   - Mitigation: Rely on WebSocket streams for market data, ticker, and position updates; use REST exclusively for actions, warm-up, and low-frequency reconciliation.

4. **Single Instrument Scope in v1:**
   - v1 operates exclusively on BTC perpetual futures (`BTCUSD` / `BTCUSDT`).
   - Cross-instrument hedging and statistical arbitrage across multiple currency pairs are explicitly out of scope for v1.

5. **Single Threaded Async Execution:**
   - While Python `asyncio` handles concurrent network streams efficiently, CPU-intensive indicator recomputations on very large dataframes could momentarily block the event loop.
   - Mitigation: Pure indicator calculations run on fixed small windows of candle history (e.g. 100-200 candles) only at closed candle boundaries.
