import React from "react";
import { useTrading } from "@/context/TradingContext";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Activity,
  Layers,
  TrendingUp,
  FileText,
  Clock,
  Compass,
} from "lucide-react";

export function DecisionModal() {
  const { selectedDecision, closeDecisionModal } = useTrading();

  if (!selectedDecision) return null;
  const d = selectedDecision;

  return (
    <Dialog open={!!selectedDecision} onOpenChange={(open) => !open && closeDecisionModal()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto p-6 bg-zinc-950 border-border">
        {/* Header */}
        <DialogHeader className="border-b border-border/60 pb-3 mb-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center space-x-2">
              <span className="font-mono text-sm font-bold text-zinc-100">{d.decisionId}</span>
              <Badge variant="outline" className="text-[10px]">
                {d.symbol} · {d.timeframe} Candle
              </Badge>
              <Badge
                variant={
                  d.riskVerdict.action === "APPROVED"
                    ? "success"
                    : d.riskVerdict.action === "RESIZED"
                    ? "warning"
                    : "destructive"
                }
              >
                {d.riskVerdict.action}
              </Badge>
            </div>
            <div className="text-[11px] font-mono text-zinc-400 flex items-center gap-1">
              <Clock className="h-3 w-3 text-emerald-400" />
              <span>{d.timestamp} UTC</span>
            </div>
          </div>
          <DialogDescription className="text-zinc-400 text-xs mt-1">
            Glass-Box Decision Audit: Full deterministic trace of market data, strategy conviction, allocator routing, and risk gate verification.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* 1. Deterministic Plain-Language Narrative */}
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-4">
            <div className="flex items-center space-x-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-1.5">
              <FileText className="h-4 w-4" />
              <span>Deterministic Explanation Narrative</span>
            </div>
            <p className="text-zinc-100 text-xs leading-relaxed font-sans">
              {d.narrative}
            </p>
          </div>

          {/* 2. Grid of Candle & Regime decomposition */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Candle Details */}
            <Card className="bg-zinc-900/60 border-border/80">
              <CardHeader className="py-2 px-3 border-b border-border/40">
                <CardTitle className="text-xs flex items-center gap-1.5">
                  <Activity className="h-3.5 w-3.5 text-cyan-400" /> Closed Candle Telemetry
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 text-xs font-mono space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-zinc-400">Open / Close:</span>
                  <span className="text-zinc-200">
                    ${d.candle.open.toFixed(2)} / ${d.candle.close.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">High / Low:</span>
                  <span className="text-zinc-200">
                    ${d.candle.high.toFixed(2)} / ${d.candle.low.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Volume:</span>
                  <span className="text-zinc-200">{d.candle.volume} BTC</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Data Freshness:</span>
                  <span className="text-emerald-400">{d.dataFreshnessMs} ms (Contiguous)</span>
                </div>
              </CardContent>
            </Card>

            {/* Regime Filter Breakdown */}
            <Card className="bg-zinc-900/60 border-border/80">
              <CardHeader className="py-2 px-3 border-b border-border/40">
                <CardTitle className="text-xs flex items-center gap-1.5">
                  <Compass className="h-3.5 w-3.5 text-purple-400" /> Regime Filter Analysis
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 text-xs font-mono space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-zinc-400">Classification:</span>
                  <span className="font-bold text-zinc-100">{d.regime.classification}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">ADX Trend Strength:</span>
                  <span className="text-zinc-200">{d.regime.adx} (Threshold 25.0)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">RV Ratio (Short/Long):</span>
                  <span className="text-zinc-200">{d.regime.volatilityRatio}x</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Choppiness Index:</span>
                  <span className="text-zinc-200">{d.regime.choppinessIndex} / 100</span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 3. Strategy Signals Evaluated */}
          <Card className="bg-zinc-900/60 border-border/80">
            <CardHeader className="py-2 px-3 border-b border-border/40">
              <CardTitle className="text-xs flex items-center gap-1.5">
                <TrendingUp className="h-3.5 w-3.5 text-emerald-400" /> Pure Strategy Signals
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 space-y-2 text-xs">
              <div className="p-2.5 rounded bg-zinc-950/60 border border-border/40 font-mono">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-zinc-200">Strategy A: Trend Following</span>
                  <Badge
                    variant={
                      d.strategySignals.trend_following.signal === "LONG"
                        ? "success"
                        : d.strategySignals.trend_following.signal === "SHORT"
                        ? "destructive"
                        : "outline"
                    }
                    className="text-[9px]"
                  >
                    Signal: {d.strategySignals.trend_following.signal} (Conviction{" "}
                    {d.strategySignals.trend_following.strength})
                  </Badge>
                </div>
                <p className="text-[11px] text-zinc-400 font-sans">
                  {d.strategySignals.trend_following.reason}
                </p>
              </div>

              <div className="p-2.5 rounded bg-zinc-950/60 border border-border/40 font-mono">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-zinc-200">Strategy B: Mean Reversion</span>
                  <Badge
                    variant={
                      d.strategySignals.mean_reversion.signal === "LONG"
                        ? "success"
                        : d.strategySignals.mean_reversion.signal === "SHORT"
                        ? "destructive"
                        : "outline"
                    }
                    className="text-[9px]"
                  >
                    Signal: {d.strategySignals.mean_reversion.signal} (Conviction{" "}
                    {d.strategySignals.mean_reversion.strength})
                  </Badge>
                </div>
                <p className="text-[11px] text-zinc-400 font-sans">
                  {d.strategySignals.mean_reversion.reason}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* 4. Risk Gate 6-Point Audit Matrix */}
          <Card className="bg-zinc-900/60 border-border/80">
            <CardHeader className="py-2 px-3 border-b border-border/40 flex flex-row items-center justify-between">
              <CardTitle className="text-xs flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> Layered Risk Gate Matrix (Section 9.5)
              </CardTitle>
              <Badge variant="outline" className="text-[10px] font-mono">
                Binding Rule: {d.riskVerdict.bindingRule}
              </Badge>
            </CardHeader>
            <CardContent className="p-3">
              <div className="space-y-1.5">
                {d.riskVerdict.rulesChecked.map((r, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded bg-zinc-950/60 border border-border/40 text-xs font-mono"
                  >
                    <div className="flex items-center space-x-2">
                      {r.status === "PASS" ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      ) : r.status === "WARN" ? (
                        <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 text-rose-500" />
                      )}
                      <span className="font-medium text-zinc-200">{r.rule}</span>
                    </div>
                    <span className="text-zinc-400 text-[11px]">{r.detail}</span>
                  </div>
                ))}
              </div>

              {/* Bracket Protection Result */}
              {d.riskVerdict.brackets.takeProfit > 0 && (
                <div className="mt-3 p-2.5 rounded bg-zinc-950/80 border border-emerald-500/20 flex items-center justify-between text-xs font-mono">
                  <span className="text-zinc-400">Enforced Server Brackets:</span>
                  <div className="flex gap-2">
                    <span className="text-emerald-400">
                      TP: ${d.riskVerdict.brackets.takeProfit.toLocaleString()}
                    </span>
                    <span className="text-rose-400">
                      SL: ${d.riskVerdict.brackets.stopLoss.toLocaleString()}
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Footer */}
        <div className="mt-4 pt-3 border-t border-border/60 flex justify-end">
          <Button variant="secondary" size="sm" onClick={closeDecisionModal}>
            Close Audit Trace
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
