import React, { createContext, useContext, useEffect, useState } from "react";
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
  stepCandle: () => void;
  triggerKillSwitch: (secret: string) => boolean;
  resetFromHalt: (secret: string) => boolean;
  flattenPositions: () => void;
  runChaosScenario: (scenarioId: string) => void;
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

  // Calculate unrealized PnL from market price
  const unrealizedPnl = position
    ? (marketPrice - position.entryPrice) * position.size
    : 0;
  const unrealizedPnlPct = position
    ? ((marketPrice - position.entryPrice) / position.entryPrice) * 100 * position.leverage
    : 0;

  // Real-time market tick generator (simulation)
  useEffect(() => {
    if (engineState === "HALTED") return;

    const interval = setInterval(() => {
      setMarketPrice((prev) => {
        // small realistic tick (-$2.5 to +$2.5)
        const delta = (Math.random() - 0.49) * 5;
        const next = Math.round((prev + delta) * 2) / 2; // respect 0.5 tick size
        return next;
      });

      // jitter health metrics slightly for realistic glass-box telemetries
      setHealth((prev) => ({
        ...prev,
        eventLoopLagMs: Math.round((1.2 + Math.random() * 0.5) * 10) / 10,
        clockDriftSeconds: Math.round((0.035 + Math.random() * 0.01) * 1000) / 1000,
        dataFreshnessMs: Math.round(135 + Math.random() * 25),
        rateLimitUsed: prev.rateLimitUsed + Math.floor(Math.random() * 2),
      }));
    }, 1200);

    return () => clearInterval(interval);
  }, [engineState]);

  // Handle regime override or dynamic updates
  useEffect(() => {
    if (regimeOverride) {
      setRegime(regimeOverride);
      if (regimeOverride === "TRENDING") {
        setRegimeMetrics({ adx: 34.2, volatilityRatio: 1.35, choppiness: 34.1, dwellCandles: 9, confidence: 92 });
      } else if (regimeOverride === "RANGING") {
        setRegimeMetrics({ adx: 19.8, volatilityRatio: 0.91, choppiness: 59.2, dwellCandles: 5, confidence: 81 });
      } else {
        setRegimeMetrics({ adx: 16.4, volatilityRatio: 2.62, choppiness: 72.4, dwellCandles: 3, confidence: 94 });
      }
    }
  }, [regimeOverride]);

  // Step candle — runs the decision engine locally!
  const stepCandle = () => {
    if (engineState === "HALTED") {
      alert("Trading engine is currently HALTED by kill switch. Reset engine first.");
      return;
    }

    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    const dateStr = now.toISOString().slice(0, 10);
    const fullTimeStr = `${dateStr} ${timeStr}`;

    const closePrice = marketPrice;
    const openPrice = closePrice - (Math.random() - 0.48) * 35;
    const highPrice = Math.max(openPrice, closePrice) + Math.random() * 20;
    const lowPrice = Math.min(openPrice, closePrice) - Math.random() * 20;

    const currentRegime = regimeOverride || regime;
    let selectedStrategy: StrategyType | null = null;
    let action: "APPROVED" | "RESIZED" | "REJECTED" = "APPROVED";
    let narrative = "";
    let approvedSize = 0;
    const id = "dec_" + Math.random().toString(16).substring(2, 14);

    if (currentRegime === "TRENDING") {
      selectedStrategy = "trend_following";
      approvedSize = position ? 0 : 2;
      action = position ? "RESIZED" : "APPROVED";
      narrative = `At ${timeStr}, closed 1m candle at $${closePrice.toFixed(
        2
      )}. Regime filter verified TRENDING market (ADX ${regimeMetrics.adx}). Strategy 'trend_following' signaled LONG. Risk Gate checked 6 safeguards: ${
        position ? "existing inventory held (max 2 contracts reached)." : "approved 2 contracts with server-side TP/SL brackets."
      }`;
    } else if (currentRegime === "RANGING") {
      selectedStrategy = "mean_reversion";
      approvedSize = 1;
      action = "APPROVED";
      narrative = `At ${timeStr}, closed 1m candle at $${closePrice.toFixed(
        2
      )}. Regime filter confirmed RANGING conditions (Choppiness ${regimeMetrics.choppiness}). Strategy 'mean_reversion' signaled SHORT (fade deviation +2.1 sigma). Risk Gate verified half-life exit timer and approved 1 contract.`;
    } else {
      selectedStrategy = null;
      action = "REJECTED";
      approvedSize = 0;
      narrative = `At ${timeStr}, closed 1m candle at $${closePrice.toFixed(
        2
      )}. Regime filter detected CHAOTIC volatility spike. Stand-aside mandatory rule triggered. All entry intents rejected; capital protected.`;
    }

    const newDecision: DecisionRecord = {
      decisionId: id,
      timestamp: fullTimeStr,
      candleCloseTime: fullTimeStr,
      symbol: "BTCUSD",
      timeframe: activeProfile === "demo" ? "1m" : "1h",
      candle: {
        open: Math.round(openPrice * 2) / 2,
        high: Math.round(highPrice * 2) / 2,
        low: Math.round(lowPrice * 2) / 2,
        close: Math.round(closePrice * 2) / 2,
        volume: Math.round((10 + Math.random() * 25) * 10) / 10,
      },
      dataFreshnessMs: Math.round(120 + Math.random() * 40),
      regime: {
        classification: currentRegime,
        adx: regimeMetrics.adx,
        volatilityRatio: regimeMetrics.volatilityRatio,
        choppinessIndex: regimeMetrics.choppiness,
        dwellCandles: regimeMetrics.dwellCandles + 1,
        confidence: regimeMetrics.confidence,
      },
      strategySignals: {
        trend_following: {
          signal: currentRegime === "TRENDING" ? "LONG" : "FLAT",
          strength: currentRegime === "TRENDING" ? 0.88 : 0.0,
          reason:
            currentRegime === "TRENDING"
              ? "EMA(20) > EMA(50) bullish trend expansion"
              : "Trend filter disengaged in non-trending regime",
          stopDistanceAtr: 1.8,
        },
        mean_reversion: {
          signal: currentRegime === "RANGING" ? "SHORT" : "FLAT",
          strength: currentRegime === "RANGING" ? 0.76 : 0.0,
          reason:
            currentRegime === "RANGING"
              ? "Z-Score +2.18 above +2.0 fade threshold"
              : "Stationarity check rejected during trending flow",
          zScore: currentRegime === "RANGING" ? 2.18 : 0.45,
          halfLifeHours: 1.9,
        },
      },
      allocator: {
        selectedStrategy,
        weight: selectedStrategy === "trend_following" ? 0.7 : selectedStrategy === "mean_reversion" ? 0.3 : 0.0,
        reason:
          currentRegime === "CHAOTIC"
            ? "Chaotic lockout — 100% allocation to Cash"
            : `Regime priority routing to ${selectedStrategy}`,
        explorationFloor: 0.05,
      },
      riskVerdict: {
        action,
        bindingRule:
          action === "APPROVED"
            ? "Max Position Sizing"
            : action === "RESIZED"
            ? "Inventory Limit"
            : "Regime Stand-Aside",
        rulesChecked: [
          { rule: "Testnet Environment Guard", status: "PASS", detail: "cdn-ind.testnet.deltaex.org verified" },
          { rule: "Kill Switch State", status: "PASS", detail: "Engine state RUNNING" },
          { rule: "Drawdown Ladder", status: "PASS", detail: `Rung ${drawdownRung} active` },
          { rule: "Mandatory Bracket Exit", status: "PASS", detail: "TP & SL targets set" },
        ],
        approvedSize,
        brackets: {
          takeProfit: Math.round((closePrice + 850) * 2) / 2,
          stopLoss: Math.round((closePrice - 600) * 2) / 2,
        },
      },
      executionOutcome: {
        orderSent: action === "APPROVED" && approvedSize > 0,
        clientOrderId: `qp_${Date.now()}_btc`,
        status: action === "APPROVED" ? "FILLED" : "STAND_ASIDE",
        fillPrice: closePrice,
        latencyMs: 76,
      },
      narrative,
    };

    setDecisions((prev) => [newDecision, ...prev.slice(0, 19)]);
  };

  // Kill Switch
  const triggerKillSwitch = (secret: string): boolean => {
    if (!secret || secret.trim().length === 0) return false;

    setEngineState("HALTED");
    setPosition(null);
    setOrders([]);
    setHealth((prev) => ({
      ...prev,
      status: "CRITICAL",
    }));

    const eventMsg = `[KILL SWITCH TRIGGERED] Emergency halt activated via Control Plane. All ${orders.length} orders cancelled. Open positions closed with reduce-only orders.`;
    setChaosLogs((prev) => [eventMsg, ...prev]);

    return true;
  };

  // Reset from halt
  const resetFromHalt = (secret: string): boolean => {
    if (!secret || secret.trim().length === 0) return false;

    setEngineState("RUNNING");
    setHealth((prev) => ({
      ...prev,
      status: "HEALTHY",
      websocketState: "SUBSCRIBED",
      dataFreshnessMs: 140,
    }));
    setChaosActive(false);
    setActiveChaosScenario(null);
    setChaosLogs((prev) => [`[RESET COMPLETED] Engine restored to RUNNING state.`, ...prev]);
    return true;
  };

  // Manual Flatten
  const flattenPositions = () => {
    if (!position) return;
    const exitPrice = marketPrice;
    const pnl = (exitPrice - position.entryPrice) * position.size;

    setRealizedPnl((prev) => prev + pnl);
    setPosition(null);
    setOrders((prev) => prev.filter((o) => !o.reduceOnly));

    const fillId = `fill_${Date.now().toString().slice(-7)}`;
    setFills((prev) => [
      {
        fillId,
        clientOrderId: `qp_flatten_${Date.now()}`,
        symbol: "BTCUSD",
        side: position.side === "LONG" ? "SELL" : "BUY",
        price: exitPrice,
        size: position.size,
        feeUsdt: 6.42,
        feeBps: 5.0,
        slippageBps: 1.1,
        timestamp: new Date().toLocaleTimeString(),
      },
      ...prev,
    ]);
  };

  // Chaos Scenarios Runner
  const runChaosScenario = (scenarioId: string) => {
    const sc = CHAOS_SCENARIOS.find((s) => s.id === scenarioId);
    if (!sc) return;

    setChaosActive(true);
    setActiveChaosScenario(sc);

    const timestamp = new Date().toLocaleTimeString();

    if (scenarioId === "PRICE_SHOCK") {
      const shockPrice = 61400.0;
      setMarketPrice(shockPrice);
      setDrawdownPct(2.4);
      setDrawdownRung(2);
      if (position) {
        setPosition(null); // SL bracket triggered!
        setRealizedPnl((prev) => prev - 110.0);
      }
      setOrders([]);
      setChaosLogs((prev) => [
        `[${timestamp}] CHAOS: Adverse Price Shock injected! Price plunged to $61,400.`,
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
        `[${timestamp}] CHAOS: Market feed halted. Heartbeat elapsed without packet. Latency 4,250ms.`,
        `[${timestamp}] SAFEGUARD: Data Freshness Guard tripped (>250ms limit). All trade entries automatically paused!`,
        ...prev,
      ]);
    } else if (scenarioId === "WS_DROP") {
      setHealth((prev) => ({
        ...prev,
        status: "DEGRADED",
        websocketState: "DISCONNECTED",
      }));
      setChaosLogs((prev) => [
        `[${timestamp}] CHAOS: Private & Public WebSocket connections abruptly dropped.`,
        `[${timestamp}] SAFEGUARD: Degraded to REST polling fallback within 25% quota. Reconnect supervisor active.`,
        ...prev,
      ]);
    } else if (scenarioId === "UNPROTECTED_POS") {
      setPosition({
        symbol: "BTCUSD",
        side: "LONG",
        size: 1,
        entryPrice: marketPrice,
        markPrice: marketPrice,
        liquidationPrice: marketPrice * 0.8,
        unrealizedPnl: 0,
        unrealizedPnlPct: 0,
        leverage: 5,
        marginType: "ISOLATED",
        brackets: {
          takeProfit: { price: 0, status: "PENDING" },
          stopLoss: { price: 0, status: "PENDING" },
        },
      });
      setChaosLogs((prev) => [
        `[${timestamp}] CHAOS: Injected naked 1-contract position without brackets.`,
        `[${timestamp}] SAFEGUARD: Watchdog scanned state within 500ms — detected missing bracket!`,
        `[${timestamp}] SAFEGUARD: Watchdog auto-dispatched server-side TP ($${(marketPrice + 800).toFixed(0)}) & SL ($${(marketPrice - 550).toFixed(0)}).`,
        ...prev,
      ]);
      // auto protect after 1.5s
      setTimeout(() => {
        setPosition((prev) =>
          prev
            ? {
                ...prev,
                brackets: {
                  takeProfit: { price: Math.round(marketPrice + 800), status: "EXCHANGE_ACTIVE" },
                  stopLoss: { price: Math.round(marketPrice - 550), status: "EXCHANGE_ACTIVE" },
                },
              }
            : null
        );
      }, 1500);
    } else if (scenarioId === "RATE_LIMIT") {
      setHealth((prev) => ({
        ...prev,
        rateLimitUsed: 19800,
      }));
      setChaosLogs((prev) => [
        `[${timestamp}] CHAOS: HTTP 429 quota warning triggered (19,800 / 20,000 weight consumed).`,
        `[${timestamp}] SAFEGUARD: Rate-limit accountant engaged. Non-critical polling suspended. Backoff engaged.`,
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
    setChaosLogs((prev) => [`[${new Date().toLocaleTimeString()}] Chaos testbed cleared. Restored baseline testnet state.`, ...prev]);
  };

  const openDecisionModal = (d: DecisionRecord) => setSelectedDecision(d);
  const closeDecisionModal = () => setSelectedDecision(null);

  return (
    <TradingContext.Provider
      value={{
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
