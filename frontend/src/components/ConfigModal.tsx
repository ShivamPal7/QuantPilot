import React from "react";
import { useTrading } from "@/context/TradingContext";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Lock, Sliders, Shield, Terminal, Clock, Check } from "lucide-react";

export function ConfigModal() {
  const { isConfigModalOpen, setIsConfigModalOpen, activeProfile } = useTrading();

  return (
    <Dialog open={isConfigModalOpen} onOpenChange={setIsConfigModalOpen}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-zinc-950 border-border p-6">
        <DialogHeader className="border-b border-border/60 pb-3 mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-zinc-100">
              <Sliders className="h-5 w-5 text-emerald-400" />
              <DialogTitle className="text-zinc-100 font-bold">
                System Configuration & Frozen Parameters
              </DialogTitle>
            </div>
            <Badge variant="cyan" className="gap-1 text-[10px]">
              <Lock className="h-3 w-3" /> FROZEN FOR DEMO (Trial #4)
            </Badge>
          </div>
          <DialogDescription className="text-zinc-400 text-xs mt-1">
            Section 10.5 & 11 Parameter Discipline: Candidate parameters were pre-declared and frozen before demo testnet session to prevent backtest overfitting.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Active Profile Status */}
          <div className="p-3 rounded-lg bg-zinc-900 border border-border/60 flex items-center justify-between text-xs font-mono">
            <div>
              <span className="text-zinc-400">Active Profile Override: </span>
              <span className="text-emerald-400 font-bold uppercase">{activeProfile} Profile</span>
            </div>
            <span className="text-zinc-400">
              Base Timeframe: {activeProfile === "demo" ? "1-Minute (Demo Accelerated)" : "1-Hour (Research Benchmark)"}
            </span>
          </div>

          {/* Config Groups Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
            {/* Risk Gate Thresholds */}
            <Card className="bg-zinc-900/60 border-border/80">
              <CardHeader className="py-2 px-3 border-b border-border/40">
                <CardTitle className="text-xs flex items-center gap-1.5 text-zinc-300">
                  <Shield className="h-3.5 w-3.5 text-emerald-400" /> Risk Limits (Section 9.5)
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 space-y-1.5 text-zinc-300">
                <div className="flex justify-between">
                  <span className="text-zinc-400">Max Open Contracts:</span>
                  <span className="text-zinc-200">10 contracts</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Leverage Ceiling:</span>
                  <span className="text-zinc-200">5.0x (Max allowed 10x)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Drawdown Ladder Rung 1:</span>
                  <span className="text-zinc-200">0.0% – 1.5% (100% Sizing)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Drawdown Ladder Rung 2:</span>
                  <span className="text-zinc-200">1.5% – 3.0% (50% Sizing)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Drawdown Ladder Rung 3:</span>
                  <span className="text-rose-400 font-semibold">&gt; 3.0% (HALT SYSTEM)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Max Book Spread:</span>
                  <span className="text-zinc-200">0.05% of mid price</span>
                </div>
              </CardContent>
            </Card>

            {/* Regime Filter Parameters */}
            <Card className="bg-zinc-900/60 border-border/80">
              <CardHeader className="py-2 px-3 border-b border-border/40">
                <CardTitle className="text-xs flex items-center gap-1.5 text-zinc-300">
                  <Sliders className="h-3.5 w-3.5 text-cyan-400" /> Regime Filter Parameters
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 space-y-1.5 text-zinc-300">
                <div className="flex justify-between">
                  <span className="text-zinc-400">ADX Trend Threshold:</span>
                  <span className="text-zinc-200">25.0 (Enter) / 22.0 (Exit)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Volatility Ratio (RV):</span>
                  <span className="text-zinc-200">2.0x Spike Trigger</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Choppiness Index Chop:</span>
                  <span className="text-zinc-200">&gt; 61.8 (Ranging / Stand-Aside)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Min Dwell Candles:</span>
                  <span className="text-zinc-200">3 candles (Hysteresis lock)</span>
                </div>
              </CardContent>
            </Card>

            {/* Strategy A: Trend Following */}
            <Card className="bg-zinc-900/60 border-border/80">
              <CardHeader className="py-2 px-3 border-b border-border/40">
                <CardTitle className="text-xs flex items-center gap-1.5 text-zinc-300">
                  <Check className="h-3.5 w-3.5 text-purple-400" /> Strategy A: Trend Following
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 space-y-1.5 text-zinc-300">
                <div className="flex justify-between">
                  <span className="text-zinc-400">Fast / Slow EMAs:</span>
                  <span className="text-zinc-200">20 / 50 periods</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">ATR Stop Distance:</span>
                  <span className="text-zinc-200">1.8 x ATR(14)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Take-Profit Target:</span>
                  <span className="text-zinc-200">3.0 x ATR(14)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Trailing Stop:</span>
                  <span className="text-emerald-400">Enabled on 1.5x ATR gain</span>
                </div>
              </CardContent>
            </Card>

            {/* Strategy B: Mean Reversion */}
            <Card className="bg-zinc-900/60 border-border/80">
              <CardHeader className="py-2 px-3 border-b border-border/40">
                <CardTitle className="text-xs flex items-center gap-1.5 text-zinc-300">
                  <Check className="h-3.5 w-3.5 text-amber-400" /> Strategy B: Mean Reversion
                </CardTitle>
              </CardHeader>
              <CardContent className="p-3 space-y-1.5 text-zinc-300">
                <div className="flex justify-between">
                  <span className="text-zinc-400">Standardized Z-Score:</span>
                  <span className="text-zinc-200">± 2.0 sigma deviation</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Mean Lookback Window:</span>
                  <span className="text-zinc-200">30 closed candles</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Max Half-Life:</span>
                  <span className="text-zinc-200">4.0 hours (Ornstein-Uhlenbeck)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Hard Time Stop:</span>
                  <span className="text-zinc-200">2 x Estimated Half-life</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-border/60 flex justify-end">
          <Button variant="secondary" size="sm" onClick={() => setIsConfigModalOpen(false)}>
            Close Inspector
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
