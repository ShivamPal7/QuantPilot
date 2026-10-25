import React from "react";
import { useTrading } from "@/context/TradingContext";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  TrendingUp,
  Activity,
  Layers,
  ShieldCheck,
  DollarSign,
  AlertTriangle,
  ArrowUpRight,
  Wifi,
  Database,
  Cpu,
} from "lucide-react";
import { RegimeType } from "@/types";

export function MetricCards() {
  const {
    marketPrice,
    priceChange24h,
    regime,
    regimeOverride,
    setRegimeOverride,
    regimeMetrics,
    shadowAccounts,
    health,
    realizedPnl,
    unrealizedPnl,
    drawdownPct,
    drawdownRung,
    position,
  } = useTrading();

  const activeStrategy = shadowAccounts.find((s) => s.id === "trend_following");

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      {/* 1. Active Instrument & Live Price */}
      <Card className="bg-zinc-950/70 border-border/80">
        <CardContent className="p-3.5 flex flex-col justify-between h-full space-y-2">
          <div className="flex items-center justify-between text-muted-foreground text-xs">
            <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-emerald-400" /> BTCUSD PERP
            </span>
            <span className="font-mono text-[10px] text-zinc-400">Tick: $0.5</span>
          </div>

          <div>
            <div className="text-xl font-mono font-bold text-zinc-100 tracking-tight flex items-baseline gap-1.5">
              ${marketPrice.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              <span className="text-xs font-mono font-normal text-emerald-400 flex items-center">
                <ArrowUpRight className="h-3 w-3" />+{priceChange24h}%
              </span>
            </div>
            <div className="text-[11px] font-mono text-zinc-400 mt-0.5">
              Delta Testnet Perpetual · 0.001 BTC/ct
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 2. Market Regime Filter */}
      <Card className="bg-zinc-950/70 border-border/80">
        <CardContent className="p-3.5 flex flex-col justify-between h-full space-y-2">
          <div className="flex items-center justify-between text-muted-foreground text-xs">
            <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
              <TrendingUp className="h-3.5 w-3.5 text-cyan-400" /> REGIME FILTER
            </span>
            <Badge
              variant={
                regime === "TRENDING" ? "success" : regime === "RANGING" ? "warning" : "destructive"
              }
              className="text-[10px] py-0"
            >
              {regime}
            </Badge>
          </div>

          <div>
            <div className="text-xs font-mono text-zinc-200 flex items-center justify-between">
              <span>ADX: {regimeMetrics.adx.toFixed(1)}</span>
              <span>RV: {regimeMetrics.volatilityRatio.toFixed(2)}x</span>
              <span>Chop: {regimeMetrics.choppiness.toFixed(0)}</span>
            </div>

            {/* Quick Demo Regime Switcher */}
            <div className="flex items-center gap-1 mt-2">
              <span className="text-[10px] text-zinc-500">Test:</span>
              {(["AUTO", "TRENDING", "RANGING", "CHAOTIC"] as const).map((r) => {
                const isSelected = r === "AUTO" ? regimeOverride === null : regimeOverride === r;
                return (
                  <button
                    key={r}
                    onClick={() => setRegimeOverride(r === "AUTO" ? null : (r as RegimeType))}
                    className={`text-[9px] font-mono px-1.5 py-0.5 rounded border transition-colors ${
                      isSelected
                        ? "bg-zinc-800 text-emerald-300 border-zinc-600 font-semibold"
                        : "bg-zinc-900/60 text-zinc-500 border-border/40 hover:text-zinc-300"
                    }`}
                  >
                    {r}
                  </button>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 3. Allocator Choice & Weight */}
      <Card className="bg-zinc-950/70 border-border/80">
        <CardContent className="p-3.5 flex flex-col justify-between h-full space-y-2">
          <div className="flex items-center justify-between text-muted-foreground text-xs">
            <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5 text-purple-400" /> ALLOCATOR
            </span>
            <span className="font-mono text-[10px] text-purple-400">Dirichlet Prior</span>
          </div>

          <div>
            <div className="text-sm font-mono font-bold text-zinc-100 truncate">
              {regime === "CHAOTIC"
                ? "STAND-ASIDE (CASH)"
                : regime === "TRENDING"
                ? "Trend Following"
                : "Mean Reversion"}
            </div>
            <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 mt-1">
              <span>Allocated Weight:</span>
              <span className="text-emerald-400 font-semibold">
                {regime === "CHAOTIC" ? "0.0%" : regime === "TRENDING" ? "65.0%" : "35.0%"}
              </span>
            </div>
            <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden mt-1.5">
              <div
                className="bg-purple-500 h-full transition-all duration-300"
                style={{
                  width: regime === "CHAOTIC" ? "0%" : regime === "TRENDING" ? "65%" : "35%",
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4. Health & Safety Lights */}
      <Card className="bg-zinc-950/70 border-border/80">
        <CardContent className="p-3.5 flex flex-col justify-between h-full space-y-2">
          <div className="flex items-center justify-between text-muted-foreground text-xs">
            <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> SYSTEM HEALTH
            </span>
            <Badge
              variant={health.status === "HEALTHY" ? "success" : "destructive"}
              className="text-[10px] py-0"
            >
              {health.status}
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-1.5 text-[10px] font-mono">
            <div className="flex items-center gap-1 text-zinc-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span>WS: {health.websocketState.slice(0, 3)}</span>
            </div>
            <div className="flex items-center gap-1 text-zinc-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span>Feed: {health.dataFreshnessMs}ms</span>
            </div>
            <div className="flex items-center gap-1 text-zinc-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span>DB: SQLite OK</span>
            </div>
            <div className="flex items-center gap-1 text-zinc-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span>Drift: {health.clockDriftSeconds}s</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 5. Today's PnL & Drawdown Ladder */}
      <Card className="bg-zinc-950/70 border-border/80">
        <CardContent className="p-3.5 flex flex-col justify-between h-full space-y-2">
          <div className="flex items-center justify-between text-muted-foreground text-xs">
            <span className="font-semibold text-zinc-300 flex items-center gap-1.5">
              <DollarSign className="h-3.5 w-3.5 text-emerald-400" /> TODAY'S PNL
            </span>
            <span
              className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-semibold ${
                drawdownRung === 1
                  ? "bg-emerald-500/10 text-emerald-400"
                  : drawdownRung === 2
                  ? "bg-amber-500/10 text-amber-400"
                  : "bg-rose-500/10 text-rose-400"
              }`}
            >
              Rung {drawdownRung} ({drawdownRung === 1 ? "100%" : drawdownRung === 2 ? "50%" : "0%"})
            </span>
          </div>

          <div>
            <div className="flex items-baseline justify-between font-mono">
              <span className="text-base font-bold text-emerald-400">
                +${(realizedPnl + unrealizedPnl).toFixed(2)}
              </span>
              <span className="text-xs text-zinc-400">
                uPnL: {unrealizedPnl >= 0 ? "+" : ""}${unrealizedPnl.toFixed(2)}
              </span>
            </div>
            <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 mt-1">
              <span>Drawdown:</span>
              <span className={drawdownPct > 1.5 ? "text-amber-400" : "text-zinc-300"}>
                {drawdownPct.toFixed(2)}% / 3.0% Max
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
