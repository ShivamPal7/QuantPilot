export type EngineState = "RUNNING" | "PAUSED" | "HALTED" | "DEGRADED";

export type RegimeType = "TRENDING" | "RANGING" | "CHAOTIC";

export type StrategyType = "trend_following" | "mean_reversion" | "market_making";

export interface SystemHealth {
  status: "HEALTHY" | "DEGRADED" | "CRITICAL";
  process: "HEALTHY";
  eventLoopLagMs: number;
  databaseOk: boolean;
  exchangeRest: "CONNECTED";
  websocketState: "SUBSCRIBED" | "DEGRADED" | "DISCONNECTED";
  clockDriftSeconds: number;
  dataFreshnessMs: number;
  feedContiguous: boolean;
  rateLimitUsed: number;
  rateLimitMax: number;
}

export interface Position {
  symbol: string;
  side: "LONG" | "SHORT";
  size: number;
  entryPrice: number;
  markPrice: number;
  liquidationPrice: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  leverage: number;
  marginType: "ISOLATED";
  brackets: {
    takeProfit: { price: number; status: "EXCHANGE_ACTIVE" | "PENDING" };
    stopLoss: { price: number; status: "EXCHANGE_ACTIVE" | "PENDING" };
  };
}

export interface Order {
  clientOrderId: string;
  symbol: string;
  side: "BUY" | "SELL";
  type: "LIMIT" | "MARKET";
  price: number;
  size: number;
  reduceOnly: boolean;
  postOnly: boolean;
  status: "FILLED" | "OPEN" | "CANCELLED" | "REJECTED";
  timeInForce: "GTC" | "IOC";
  hasBrackets: boolean;
  timestamp: string;
}

export interface Fill {
  fillId: string;
  clientOrderId: string;
  symbol: string;
  side: "BUY" | "SELL";
  price: number;
  size: number;
  feeUsdt: number;
  feeBps: number;
  slippageBps: number;
  timestamp: string;
}

export interface ShadowAccount {
  id: StrategyType;
  name: string;
  description: string;
  tradesCount: number;
  winRate: number;
  profitFactor: number;
  netPnl: number;
  maxDrawdownPct: number;
  sharpeRatio: number;
  currentPosition: number;
  frictionPaidUsdt: number;
  allocationWeight: number;
  isActive: boolean;
}

export interface DecisionRecord {
  decisionId: string;
  timestamp: string;
  candleCloseTime: string;
  symbol: string;
  timeframe: string;
  candle: {
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  };
  dataFreshnessMs: number;
  regime: {
    classification: RegimeType;
    adx: number;
    volatilityRatio: number;
    choppinessIndex: number;
    dwellCandles: number;
    confidence: number;
  };
  strategySignals: {
    trend_following: {
      signal: "LONG" | "SHORT" | "FLAT";
      strength: number;
      reason: string;
      stopDistanceAtr: number;
    };
    mean_reversion: {
      signal: "LONG" | "SHORT" | "FLAT";
      strength: number;
      reason: string;
      zScore: number;
      halfLifeHours: number;
    };
  };
  allocator: {
    selectedStrategy: StrategyType | null;
    weight: number;
    reason: string;
    explorationFloor: number;
  };
  riskVerdict: {
    action: "APPROVED" | "RESIZED" | "REJECTED";
    bindingRule: string;
    rulesChecked: Array<{
      rule: string;
      status: "PASS" | "FAIL" | "WARN";
      detail: string;
    }>;
    approvedSize: number;
    brackets: {
      takeProfit: number;
      stopLoss: number;
    };
  };
  executionOutcome: {
    orderSent: boolean;
    clientOrderId?: string;
    status: string;
    fillPrice?: number;
    latencyMs?: number;
  };
  narrative: string;
}

export interface ChaosScenario {
  id: "PRICE_SHOCK" | "STALE_FEED" | "WS_DROP" | "UNPROTECTED_POS" | "RATE_LIMIT" | "RESTART_ORPHAN";
  title: string;
  severity: "HIGH" | "MEDIUM" | "CRITICAL";
  description: string;
  expectedBehavior: string;
  safeguardTarget: string;
}
