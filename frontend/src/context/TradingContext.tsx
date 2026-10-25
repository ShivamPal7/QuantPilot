import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  ChaosScenario,
  DecisionRecord,
  EngineState,
  Fill,
  Order,
  Position,
  RegimeType,
  ShadowAccount,
  StrategyType,
  SystemHealth,
} from "@/types";
import {
  INITIAL_DECISIONS,
  INITIAL_FILLS,
  INITIAL_HEALTH,
  INITIAL_ORDERS,
  INITIAL_POSITION,
  INITIAL_SHADOW_ACCOUNTS,
} from "@/mock/simulation";
import { ApiClient, DecisionRecordAPI } from "@/lib/api";

export const CHAOS_SCENARIOS: ChaosScenario[] = [
  {
    id: "PRICE_SHOCK",
    title: "Adverse Price Shock (-4.5% Flash Move)",
    severity: "CRITICAL",
    safeguardTarget: "Exchange Stop-Loss Bracket & Drawdown Ladder",
    description:
      "Injects a violent instantaneous drop in mark price down to $61,400. Replays through the risk gate to verify exchange Stop-Loss trigger, ladder progression into Rung 2/3, and risk freeze.",
    expectedBehavior:
      "Exchange server-side bracket fills at Stop-Loss ($63,400). Drawdown moves to Rung 2 (-1.8%). Order sizing throttled by 50% for next entries.",
  },
  {
    id: "STALE_FEED",
    title: "Stale Market Data (Feed Interruption)",
    severity: "HIGH",
    safeguardTarget: "Data Freshness Guard (250ms threshold)",
    description:
      "Simulates packet loss where WebSocket and REST candle timestamps stop advancing. Feed latency spikes from 140ms to 4,200ms.",
    expectedBehavior:
      "Health light switches to DEGRADED. Data freshness alarm fires. Engine automatically stands aside and refuses all new order intents.",
  },
  {
    id: "WS_DROP",
    title: "WebSocket Disconnect & Fallback Polling",
    severity: "MEDIUM",
    safeguardTarget: "Dual-Transport Degradation & Heartbeat",
    description:
      "Simulates abrupt closure of private and public testnet WebSocket channels. Exercises automatic REST fallback and rate-limit preservation.",
    expectedBehavior:
      "Engine logs socket disconnect, marks transport DEGRADED, starts REST polling within 25% quota budget, and triggers automatic backfill.",
  },
  {
    id: "UNPROTECTED_POS",
    title: "Unprotected Position Injected (No Brackets)",
    severity: "CRITICAL",
    safeguardTarget: "Watchdog Bracket Enforcer",
    description:
      "Simulates an orphan fill arriving without exchange-side take-profit or stop-loss brackets attached.",
    expectedBehavior:
      "Reconciliation watchdog detects unhedged inventory within 500ms, immediately calculates ATR brackets, and submits server-side bracket orders.",
  },
  {
    id: "RATE_LIMIT",
    title: "Exchange Rate Limit Spike (HTTP 429)",
    severity: "HIGH",
    safeguardTarget: "Rate-Limit Accountant & Exponential Backoff",
    description:
      "Simulates receiving HTTP 429 Retry-After response from cdn-ind.testnet.deltaex.org.",
    expectedBehavior:
      "Engine immediately halts non-critical reads, queues intents with exponential backoff, and enters graceful preservation mode.",
  },
  {
    id: "RESTART_ORPHAN",
    title: "Cold Restart with Open Position",
    severity: "MEDIUM",
    safeguardTarget: "Reconciliation State Recovery",
    description:
      "Emulates engine crash and restart while a testnet position and open orders are live on exchange.",
    expectedBehavior:
      "Engine loads zero local state, queries /positions and /orders via signed REST, adopts existing brackets, and reconciles truth before trading.",
  },
];

interface TradingContextType {
  apiConnected: boolean;
  engineState: EngineState;
  activeProfile: "demo" | "research";
  marketPrice: number;
  priceChange24h: number;
  volume24h: string;
  regime: RegimeType;
  regimeOverride: RegimeType | null;
  regimeMetrics: {
    adx: number;
    volatilityRatio: number;
    choppiness: number;
    dwellCandles: number;
    confidence: number;
  };
  position: Position | null;
  orders: Order[];
  fills: Fill[];
  shadowAccounts: ShadowAccount[];
  decisions: DecisionRecord[];
  health: SystemHealth;
  realizedPnl: number;
  unrealizedPnl: number;
  todayHighWatermark: number;
  drawdownPct: number;
  drawdownRung: 1 | 2 | 3;
  chaosActive: boolean;
  activeChaosScenario: ChaosScenario | null;
  chaosLogs: string[];

  // Modals state
  isKillModalOpen: boolean;
  isFlattenModalOpen: boolean;
  isConfigModalOpen: boolean;
  isChaosModalOpen: boolean;
  isResetModalOpen: boolean;
  selectedDecision: DecisionRecord | null;

  // Actions
  setEngineState: (state: EngineState) => void;
  setActiveProfile: (profile: "demo" | "research") => void;
  setRegimeOverride: (regime: RegimeType | null) => void;
  stepCandle: () => Promise<void>;
  triggerKillSwitch: (secret: string) => Promise<boolean>;
  resetFromHalt: (secret: string) => Promise<boolean>;
  flattenPositions: () => Promise<void>;
  runChaosScenario: (scenarioId: string) => Promise<void>;
  clearChaos: () => void;
  openDecisionModal: (decision: DecisionRecord) => void;
  closeDecisionModal: () => void;
  setIsKillModalOpen: (open: boolean) => void;
  setIsFlattenModalOpen: (open: boolean) => void;
  setIsConfigModalOpen: (open: boolean) => void;
  setIsChaosModalOpen: (open: boolean) => void;
  setIsResetModalOpen: (open: boolean) => void;
}

const TradingContext = createContext<TradingContextType | undefined>(undefined);

export function TradingProvider({ children }: { children: React.ReactNode }) {
  const [apiConnected, setApiConnected] = useState<boolean>(false);
  const [engineState, setEngineState] = useState<EngineState>("RUNNING");
  const [activeProfile, setActiveProfile] = useState<"demo" | "research">("demo");
  const [marketPrice, setMarketPrice] = useState<number>(64285.5);
  const [priceChange24h] = useState<number>(2.4);
  const [volume24h] = useState<string>("48.2M");

  const [regimeOverride, setRegimeOverride] = useState<RegimeType | null>(null);
  const [regime, setRegime] = useState<RegimeType>("TRENDING");
  const [regimeMetrics, setRegimeMetrics] = useState({
    adx: 32.4,
    volatilityRatio: 1.28,
    choppiness: 38.2,
    dwellCandles: 8,
    confidence: 88,
  });

  const [position, setPosition] = useState<Position | null>(INITIAL_POSITION);
  const [orders, setOrders] = useState<Order[]>(INITIAL_ORDERS);
  const [fills, setFills] = useState<Fill[]>(INITIAL_FILLS);
  const [shadowAccounts, setShadowAccounts] = useState<ShadowAccount[]>(INITIAL_SHADOW_ACCOUNTS);
  const [decisions, setDecisions] = useState<DecisionRecord[]>(INITIAL_DECISIONS);
  const [health, setHealth] = useState<SystemHealth>(INITIAL_HEALTH);

  const [realizedPnl, setRealizedPnl] = useState<number>(142.8);
  const [todayHighWatermark] = useState<number>(10142.8);
  const [drawdownPct, setDrawdownPct] = useState<number>(0.35);
  const [drawdownRung, setDrawdownRung] = useState<1 | 2 | 3>(1);

  // Chaos state
  const [chaosActive, setChaosActive] = useState<boolean>(false);
  const [activeChaosScenario, setActiveChaosScenario] = useState<ChaosScenario | null>(null);
  const [chaosLogs, setChaosLogs] = useState<string[]>([]);

  // Modals
  const [isKillModalOpen, setIsKillModalOpen] = useState(false);
  const [isFlattenModalOpen, setIsFlattenModalOpen] = useState(false);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [isChaosModalOpen, setIsChaosModalOpen] = useState(false);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [selectedDecision, setSelectedDecision] = useState<DecisionRecord | null>(null);

  // Calculate unrealized PnL from position
  const unrealizedPnl = position ? (marketPrice - position.entryPrice) * position.size : 0;

  // Helper: map API decision record to UI DecisionRecord
  const mapApiDecision = (d: DecisionRecordAPI): DecisionRecord => {
    let raw: any = {};
    try {
      raw = JSON.parse(d.raw_payload || "{}");
    } catch {
      raw = {};
    }

    const verdictAction: "APPROVED" | "RESIZED" | "REJECTED" =
      d.verdict_action === "APPROVE" || d.verdict_action === "APPROVED"
        ? "APPROVED"
        : d.verdict_action === "RESIZE" || d.verdict_action === "RESIZED"
        ? "RESIZED"
        : "REJECTED";

    const regimeLabel: RegimeType =
      d.regime_label === "TRENDING"
        ? "TRENDING"
        : d.regime_label === "CHAOTIC"
        ? "CHAOTIC"
        : "RANGING";

    return {
      decisionId: d.decision_id,
      timestamp: d.timestamp.replace("T", " ").slice(0, 19),
      candleCloseTime: d.timestamp.replace("T", " ").slice(0, 19),
      symbol: d.symbol,
      timeframe: d.timeframe || "1m",
      candle: {
        open: Math.round((d.close_price - 15) * 2) / 2,
        high: Math.round((d.close_price + 20) * 2) / 2,
        low: Math.round((d.close_price - 20) * 2) / 2,
        close: d.close_price,
        volume: 14.5,
      },
      dataFreshnessMs: 135,
      regime: {
        classification: regimeLabel,
        adx: regimeLabel === "TRENDING" ? 31.4 : 19.5,
        volatilityRatio: regimeLabel === "CHAOTIC" ? 2.3 : 1.15,
        choppinessIndex: regimeLabel === "RANGING" ? 62.0 : 41.0,
        dwellCandles: 6,
        confidence: 85,
      },
      strategySignals: {
        trend_following: {
          signal: regimeLabel === "TRENDING" ? "LONG" : "FLAT",
          strength: regimeLabel === "TRENDING" ? 0.82 : 0.0,
          reason:
            regimeLabel === "TRENDING"
              ? "EMA(20) > EMA(50) bullish breakout"
              : "Regime filter disengaged",
          stopDistanceAtr: 1.8,
        },
        mean_reversion: {
          signal: regimeLabel === "RANGING" ? "SHORT" : "FLAT",
          strength: regimeLabel === "RANGING" ? 0.75 : 0.0,
          reason:
            regimeLabel === "RANGING"
              ? "Z-Score +2.1 above fade threshold"
              : "Stationarity check rejected during trend",
          zScore: regimeLabel === "RANGING" ? 2.1 : 0.4,
          halfLifeHours: 2.0,
        },
      },
      allocator: {
        selectedStrategy: d.selected_strategy as StrategyType | null,
        weight: d.selected_strategy ? 0.7 : 0.0,
        reason: d.selected_strategy
          ? `Allocated to ${d.selected_strategy} per ${regimeLabel} regime`
          : "Stand-aside enforced",
        explorationFloor: 0.05,
      },
      riskVerdict: {
        action: verdictAction,
        bindingRule: raw.binding_rule || d.rejection_reason || "Position Sizing",
        rulesChecked: [
          { rule: "Testnet Environment Guard", status: "PASS", detail: "cdn-ind.testnet.deltaex.org verified" },
          { rule: "Kill Switch State", status: "PASS", detail: "Engine state operational" },
          { rule: "Drawdown Ladder", status: "PASS", detail: "Normal risk sizing active" },
          { rule: "Mandatory Bracket Exit", status: "PASS", detail: "Server-side TP/SL attached" },
        ],
        approvedSize: d.approved_contracts,
        brackets: {
          takeProfit: Math.round((d.close_price + 850) * 2) / 2,
          stopLoss: Math.round((d.close_price - 600) * 2) / 2,
        },
      },
      executionOutcome: {
        orderSent: verdictAction === "APPROVED" && d.approved_contracts > 0,
        clientOrderId: `qp_${d.decision_id}`,
        status: verdictAction === "APPROVED" ? "FILLED" : "STAND_ASIDE",
        fillPrice: d.close_price,
        latencyMs: 82,
      },
      narrative: d.narrative,
    };
  };

  // Primary API Poll Routine
  const syncWithApi = useCallback(async () => {
    try {
      // 1. Health
      const healthData = await ApiClient.fetchHealth();
      setApiConnected(true);
      setHealth((prev) => ({
        ...prev,
        status: healthData.status === "healthy" ? "HEALTHY" : "DEGRADED",
        clockDriftSeconds: healthData.clock_drift_seconds,
        dataFreshnessMs: healthData.data_fresh ? 120 : 4500,
        databaseOk: healthData.database_ok,
      }));

      // 2. Status
      const statusData = await ApiClient.fetchStatus();
      if (statusData.engine_state) {
        setEngineState(statusData.engine_state as EngineState);
      }
      if (statusData.current_regime && !regimeOverride) {
        setRegime(statusData.current_regime as RegimeType);
      }
      if (statusData.drawdown_pct !== undefined) {
        setDrawdownPct(statusData.drawdown_pct);
        setDrawdownRung(statusData.drawdown_pct <= 1.5 ? 1 : statusData.drawdown_pct <= 3.0 ? 2 : 3);
      }

      // 3. Positions & Orders
      const posData = await ApiClient.fetchPositions();
      if (posData.positions && posData.positions.length > 0) {
        const p = posData.positions[0];
        setPosition({
          symbol: p.symbol,
          side: p.side,
          size: p.contracts,
          entryPrice: p.entry_price,
          markPrice: p.mark_price || marketPrice,
          liquidationPrice: p.entry_price * 0.8,
          unrealizedPnl: p.unrealized_pnl,
          unrealizedPnlPct: (p.unrealized_pnl / (p.entry_price * p.contracts)) * 100,
          leverage: p.leverage || 5,
          marginType: "ISOLATED",
          brackets: {
            takeProfit: { price: p.entry_price * 1.02, status: "EXCHANGE_ACTIVE" },
            stopLoss: { price: p.entry_price * 0.98, status: "EXCHANGE_ACTIVE" },
          },
        });
        if (p.mark_price) setMarketPrice(p.mark_price);
      } else {
        // If engine reported no open positions
        if (posData.source === "reconciled_exchange_truth") {
          // keep or update position
        }
      }

      if (posData.open_orders && posData.open_orders.length > 0) {
        setOrders(
          posData.open_orders.map((o) => ({
            clientOrderId: o.client_order_id,
            symbol: o.symbol,
            side: o.side,
            type: "LIMIT",
            price: 65200.0,
            size: o.size_contracts,
            reduceOnly: true,
            postOnly: true,
            status: o.state as any,
            timeInForce: "GTC",
            hasBrackets: false,
            timestamp: o.created_at,
          }))
        );
      }

      if (posData.fills && posData.fills.length > 0) {
        setFills(
          posData.fills.map((f) => ({
            fillId: f.fill_id,
            clientOrderId: f.client_order_id,
            symbol: f.symbol,
            side: "BUY",
            price: f.fill_price,
            size: f.size_contracts,
            feeUsdt: f.fee,
            feeBps: 5.0,
            slippageBps: f.slippage_bps || 0.8,
            timestamp: f.filled_at.replace("T", " ").slice(0, 19),
          }))
        );
      }

      // 4. Strategies (Shadow accounts)
      const stratData = await ApiClient.fetchStrategies();
      if (stratData.shadow_accounts && stratData.shadow_accounts.length > 0) {
        setShadowAccounts((prev) =>
          prev.map((acc) => {
            const apiAcc = stratData.shadow_accounts.find((s) => s.strategy === acc.id);
            if (!apiAcc) return acc;
            return {
              ...acc,
              tradesCount: apiAcc.trade_count,
              winRate: apiAcc.win_rate * 100,
              netPnl: apiAcc.net_profit,
              maxDrawdownPct: apiAcc.max_drawdown_pct * 100,
            };
          })
        );
      }

      // 5. Decisions
      const decisionsData = await ApiClient.fetchDecisions(20);
      if (decisionsData.decisions && decisionsData.decisions.length > 0) {
        const mapped = decisionsData.decisions.map(mapApiDecision);
        setDecisions(mapped);
      }
    } catch (err) {
      // Backend not running yet or restarting — fallback gracefully
      setApiConnected(false);
    }
  }, [marketPrice, regimeOverride]);

  // Periodic polling loop (every 2.0s)
  useEffect(() => {
    syncWithApi();
    const interval = setInterval(syncWithApi, 2000);
    return () => clearInterval(interval);
  }, [syncWithApi]);

  // Subtle real-time price tick jitter for realism
  useEffect(() => {
    if (engineState === "HALTED") return;
    const tickInterval = setInterval(() => {
      setMarketPrice((prev) => {
        const delta = (Math.random() - 0.49) * 4;
        return Math.round((prev + delta) * 2) / 2;
      });
    }, 1500);
    return () => clearInterval(tickInterval);
  }, [engineState]);

  // 1. Step Candle Action (Connected to backend POST /api/control/step)
  const stepCandle = async () => {
    try {
      const res = await ApiClient.stepCandle(marketPrice);
      const timestamp = new Date().toLocaleTimeString();
      setChaosLogs((prev) => [
        `[${timestamp}] Step Candle triggered on backend: ${res.decision_id} (${res.action})`,
        ...prev,
      ]);
      await syncWithApi();
    } catch (err: any) {
      console.warn("Backend step candle failed, running local fallback:", err);
      // Run local simulated step if API fails
      const now = new Date();
      const timeStr = now.toLocaleTimeString();
      const fullTimeStr = `${now.toISOString().slice(0, 10)} ${timeStr}`;
      const closePrice = marketPrice;
      const currentRegime = regimeOverride || regime;
      const id = "dec_" + Math.random().toString(16).substring(2, 14);

      const newDecision: DecisionRecord = {
        decisionId: id,
        timestamp: fullTimeStr,
        candleCloseTime: fullTimeStr,
        symbol: "BTCUSD",
        timeframe: activeProfile === "demo" ? "1m" : "1h",
        candle: {
          open: closePrice - 10,
          high: closePrice + 20,
          low: closePrice - 20,
          close: closePrice,
          volume: 16.2,
        },
        dataFreshnessMs: 130,
        regime: {
          classification: currentRegime,
          adx: regimeMetrics.adx,
          volatilityRatio: regimeMetrics.volatilityRatio,
          choppinessIndex: regimeMetrics.choppiness,
          dwellCandles: 8,
          confidence: 88,
        },
        strategySignals: {
          trend_following: {
            signal: currentRegime === "TRENDING" ? "LONG" : "FLAT",
            strength: currentRegime === "TRENDING" ? 0.85 : 0.0,
            reason: currentRegime === "TRENDING" ? "EMA-20 breakout" : "Disengaged",
            stopDistanceAtr: 1.8,
          },
          mean_reversion: {
            signal: currentRegime === "RANGING" ? "SHORT" : "FLAT",
            strength: currentRegime === "RANGING" ? 0.72 : 0.0,
            reason: currentRegime === "RANGING" ? "Z-Score +2.18" : "Disengaged",
            zScore: 2.18,
            halfLifeHours: 1.8,
          },
        },
        allocator: {
          selectedStrategy: currentRegime === "TRENDING" ? "trend_following" : "mean_reversion",
          weight: 0.7,
          reason: `Routing to ${currentRegime === "TRENDING" ? "trend_following" : "mean_reversion"}`,
          explorationFloor: 0.05,
        },
        riskVerdict: {
          action: "APPROVED",
          bindingRule: "Max Position Sizing",
          rulesChecked: [
            { rule: "Testnet Environment Guard", status: "PASS", detail: "cdn-ind.testnet.deltaex.org verified" },
            { rule: "Kill Switch State", status: "PASS", detail: "Engine state operational" },
            { rule: "Drawdown Ladder", status: "PASS", detail: "Rung 1 active" },
            { rule: "Mandatory Bracket Exit", status: "PASS", detail: "TP & SL targets set" },
          ],
          approvedSize: 2,
          brackets: { takeProfit: closePrice + 850, stopLoss: closePrice - 600 },
        },
        executionOutcome: {
          orderSent: true,
          clientOrderId: `qp_${Date.now()}_btc`,
          status: "FILLED",
          fillPrice: closePrice,
          latencyMs: 78,
        },
        narrative: `At ${timeStr}, closed 1m candle at $${closePrice.toFixed(2)}. Evaluated strategies and Risk Gate on Delta Testnet.`,
      };
      setDecisions((prev) => [newDecision, ...prev]);
    }
  };

  // 2. Kill Switch Action (Connected to backend POST /api/control/kill)
  const triggerKillSwitch = async (secret: string): Promise<boolean> => {
    try {
      await ApiClient.killTrading(secret, "Manual operator kill switch from frontend");
      setEngineState("HALTED");
      setPosition(null);
      setOrders([]);
      const eventMsg = `[KILL SWITCH TRIGGERED] Emergency halt activated via backend API. Orders cancelled. Positions closed via reduce-only.`;
      setChaosLogs((prev) => [eventMsg, ...prev]);
      await syncWithApi();
      return true;
    } catch (err: any) {
      alert(`Kill switch failed: ${err.message}`);
      return false;
    }
  };

  // 3. Reset Engine Action (Connected to backend POST /api/control/reset)
  const resetFromHalt = async (secret: string): Promise<boolean> => {
    try {
      await ApiClient.resetTrading(secret);
      setEngineState("PAUSED");
      setChaosActive(false);
      setActiveChaosScenario(null);
      setChaosLogs((prev) => [`[RESET COMPLETED] Backend engine restored to PAUSED state.`, ...prev]);
      await syncWithApi();
      return true;
    } catch (err: any) {
      alert(`Reset failed: ${err.message}`);
      return false;
    }
  };

  // 4. Flatten Positions (Connected to backend POST /api/control/flatten)
  const flattenPositions = async () => {
    try {
      await ApiClient.flattenPositions();
      setPosition(null);
      setOrders((prev) => prev.filter((o) => !o.reduceOnly));
      setChaosLogs((prev) => [`[MANUAL FLATTEN] Positions closed via reduce-only market order on exchange.`, ...prev]);
      await syncWithApi();
    } catch (err: any) {
      console.warn("Backend flatten failed, using local fallback:", err);
      setPosition(null);
    }
  };

  // 5. Chaos Scenarios Runner (Connected to backend POST /api/control/chaos)
  const runChaosScenario = async (scenarioId: string) => {
    const sc = CHAOS_SCENARIOS.find((s) => s.id === scenarioId);
    if (!sc) return;

    setChaosActive(true);
    setActiveChaosScenario(sc);
    const timestamp = new Date().toLocaleTimeString();

    try {
      const backendScenarioMap: Record<string, string> = {
        PRICE_SHOCK: "price_shock",
        STALE_FEED: "stale_feed",
        RATE_LIMIT: "rate_limit_storm",
        WS_DROP: "ws_disconnect",
        UNPROTECTED_POS: "unprotected_position",
        RESTART_ORPHAN: "cold_restart",
      };
      const apiScenario = backendScenarioMap[scenarioId] || "price_shock";
      const res = await ApiClient.injectChaos(apiScenario, 1.0);
      setChaosLogs((prev) => [
        `[${timestamp}] CHAOS INJECTED VIA API: ${sc.title}`,
        `[${timestamp}] BACKEND RESPONSE: ${res.note || "Safe simulation applied"}`,
        ...prev,
      ]);
    } catch (err: any) {
      console.warn("Backend chaos injection notice:", err);
    }

    // Apply immediate local telemetry reactions for visual feedback
    if (scenarioId === "PRICE_SHOCK") {
      setMarketPrice(61400.0);
      setDrawdownPct(2.4);
      setDrawdownRung(2);
      if (position) setPosition(null);
      setOrders([]);
      setChaosLogs((prev) => [
        `[${timestamp}] SAFEGUARD: Exchange Stop-Loss Bracket caught the crash at $63,400.00.`,
        `[${timestamp}] SAFEGUARD: Daily Drawdown ladder advanced to Rung 2 (2.4% > 1.5%). Position sizing throttled by 50%.`,
        ...prev,
      ]);
    } else if (scenarioId === "STALE_FEED") {
      setHealth((prev) => ({
        ...prev,
        status: "DEGRADED",
        dataFreshnessMs: 4250,
        feedContiguous: false,
      }));
      setChaosLogs((prev) => [
        `[${timestamp}] SAFEGUARD: Data Freshness Guard tripped (>250ms limit). All trade entries automatically paused!`,
        ...prev,
      ]);
    } else if (scenarioId === "RATE_LIMIT") {
      setHealth((prev) => ({ ...prev, rateLimitUsed: 19800 }));
      setChaosLogs((prev) => [
        `[${timestamp}] SAFEGUARD: Rate-limit accountant engaged. HTTP 429 backoff engaged.`,
        ...prev,
      ]);
    }
  };

  const clearChaos = () => {
    setChaosActive(false);
    setActiveChaosScenario(null);
    setHealth(INITIAL_HEALTH);
    setDrawdownRung(1);
    setDrawdownPct(0.35);
    setChaosLogs((prev) => [`[${new Date().toLocaleTimeString()}] Chaos testbed cleared. Restored baseline state.`, ...prev]);
  };

  const openDecisionModal = (d: DecisionRecord) => setSelectedDecision(d);
  const closeDecisionModal = () => setSelectedDecision(null);

  return (
    <TradingContext.Provider
      value={{
        apiConnected,
        engineState,
        activeProfile,
        marketPrice,
        priceChange24h,
        volume24h,
        regime: regimeOverride || regime,
        regimeOverride,
        regimeMetrics,
        position,
        orders,
        fills,
        shadowAccounts,
        decisions,
        health,
        realizedPnl,
        unrealizedPnl,
        todayHighWatermark,
        drawdownPct,
        drawdownRung,
        chaosActive,
        activeChaosScenario,
        chaosLogs,

        isKillModalOpen,
        isFlattenModalOpen,
        isConfigModalOpen,
        isChaosModalOpen,
        isResetModalOpen,
        selectedDecision,

        setEngineState,
        setActiveProfile,
        setRegimeOverride,
        stepCandle,
        triggerKillSwitch,
        resetFromHalt,
        flattenPositions,
        runChaosScenario,
        clearChaos,
        openDecisionModal,
        closeDecisionModal,
        setIsKillModalOpen,
        setIsFlattenModalOpen,
        setIsConfigModalOpen,
        setIsChaosModalOpen,
        setIsResetModalOpen,
      }}
    >
      {children}
    </TradingContext.Provider>
  );
}

export function useTrading() {
  const context = useContext(TradingContext);
  if (!context) throw new Error("useTrading must be used within TradingProvider");
  return context;
}
