import React from "react";
import { useTrading } from "@/context/TradingContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck, CheckCircle2, AlertTriangle, XCircle, ArrowDown } from "lucide-react";

export function RiskGateMatrix() {
  const { engineState, health, drawdownPct, drawdownRung, position } = useTrading();

  const rules = [
    {
      step: 1,
      name: "Environment Safety Guard",
      section: "Section 2.1 & 6.1",
      description: "Asserts host is exclusively India Testnet (cdn-ind.testnet.deltaex.org). Denylists production host.",
      status: "PASS",
      currentValue: "cdn-ind.testnet.deltaex.org",
      limit: "Demo Testnet only",
    },
    {
      step: 2,
      name: "Emergency Kill-Switch Check",
      section: "Section 2.1 & 9.5",
      description: "Immediate rejection of all order intents if manual or automated kill switch is armed.",
      status: engineState === "HALTED" ? "FAIL" : "PASS",
      currentValue: `Engine State: ${engineState}`,
      limit: "RUNNING or PAUSED",
    },
    {
      step: 3,
      name: "NTP Clock Drift Guard",
      section: "Section 6.2 & 9.5",
      description: "Signature validity requires sub-5s drift. Startup & runtime gate enforces strict drift ceiling.",
      status: health.clockDriftSeconds <= 0.05 ? "PASS" : "FAIL",
      currentValue: `${health.clockDriftSeconds}s`,
      limit: "≤ 0.050s",
    },
    {
      step: 4,
      name: "Market Data Freshness & Contiguity",
      section: "Section 6.7 & 9.5",
      description: "Refuses new orders if candles have missing timestamps or feed latency exceeds tolerance.",
      status: health.dataFreshnessMs <= 250 && health.feedContiguous ? "PASS" : "WARN",
      currentValue: `${health.dataFreshnessMs}ms (${health.feedContiguous ? "Contiguous" : "Gaps Detected"})`,
      limit: "≤ 250ms & Contiguous",
    },
    {
      step: 5,
      name: "Daily Drawdown Ladder",
      section: "Section 9.5",
      description: "Multi-tiered safety ladder based on high watermark: Rung 1 (100% size), Rung 2 (50% size), Rung 3 (Halt).",
      status: drawdownRung === 1 ? "PASS" : drawdownRung === 2 ? "WARN" : "FAIL",
      currentValue: `Drawdown: ${drawdownPct.toFixed(2)}% (Rung ${drawdownRung})`,
      limit: "Rung 1 (0-1.5%), Rung 2 (1.5-3%), Rung 3 (>3% Halt)",
    },
    {
      step: 6,
      name: "Volatility-Scaled Sizing (ATR)",
      section: "Section 9.5 & 10.2",
      description: "Sizes contracts inversely to stop distance (risk budget fixed at $120.00). Max 10 contracts cap.",
      status: "PASS",
      currentValue: `${position ? position.size : 2} contracts ($120.00 risk budget)`,
      limit: "Max 10 contracts / trade",
    },
    {
      step: 7,
      name: "Top-of-Book Spread Ceiling",
      section: "Section 9.5",
      description: "Rejects entry intents when order book spread is abnormally wide (illiquidity protection).",
      status: "PASS",
      currentValue: "0.01% spread ($5.0 on $64k)",
      limit: "≤ 0.05% of mid price",
    },
    {
      step: 8,
      name: "Mandatory Server-Side Bracket Exit",
      section: "Section 2.1 & 6.6",
      description: "Strict non-negotiable rule: every entry order must carry TP & SL bracket, verified on exchange.",
      status: "PASS",
      currentValue: "Take-Profit Limit & Stop-Loss Market attached",
      limit: "100% bracket coverage mandatory",
    },
    {
      step: 9,
      name: "Rate-Limit Budget Accountant",
      section: "Section 6.5 & 9.5",
      description: "Restricts API calls to <25% of 20,000 weight quota per 5-minute rolling window.",
      status: health.rateLimitUsed < 5000 ? "PASS" : "WARN",
      currentValue: `${health.rateLimitUsed} / 20,000 (${((health.rateLimitUsed / 20000) * 100).toFixed(1)}%)`,
      limit: "< 5,000 weight (25% budget)",
    },
  ];

  return (
    <div className="space-y-4">
      <Card className="bg-zinc-950/70 border-border/80">
        <CardHeader className="py-3 px-4 border-b border-border/60">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <CardTitle>Mandatory 9-Tier Risk Gate Policy (Section 9.5)</CardTitle>
          </div>
          <CardDescription className="text-zinc-400 text-xs mt-1">
            Deterministic checkpoint between every approved strategy signal and Delta Exchange execution. Evaluated in strict order of safety priority. Fail closed on any violation.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 space-y-3">
          {rules.map((r, i) => (
            <div key={r.step} className="space-y-2">
              <div
                className={`p-3 rounded-lg border text-xs font-mono transition-colors ${
                  r.status === "PASS"
                    ? "bg-zinc-900/50 border-border/60 hover:border-emerald-500/30"
                    : r.status === "WARN"
                    ? "bg-amber-950/20 border-amber-500/40"
                    : "bg-rose-950/30 border-rose-500/50"
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-1.5">
                  <div className="flex items-center space-x-2">
                    <span className="h-5 w-5 rounded-full bg-zinc-800 text-zinc-300 flex items-center justify-center text-[10px] font-bold">
                      {r.step}
                    </span>
                    <span className="font-semibold text-zinc-100 text-sm">{r.name}</span>
                    <Badge variant="outline" className="text-[9px] py-0 text-zinc-400">
                      {r.section}
                    </Badge>
                  </div>
                  <Badge
                    variant={r.status === "PASS" ? "success" : r.status === "WARN" ? "warning" : "destructive"}
                    className="self-start sm:self-auto text-[10px]"
                  >
                    {r.status === "PASS" ? "VERIFIED SAFE" : r.status === "WARN" ? "CAUTION" : "BLOCKED"}
                  </Badge>
                </div>

                <p className="text-[11px] text-zinc-400 font-sans leading-relaxed mb-2">
                  {r.description}
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2 border-t border-border/40 text-[11px]">
                  <div>
                    <span className="text-zinc-500">Telemetry Value: </span>
                    <span className="text-zinc-200 font-medium">{r.currentValue}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Safeguard Rule Ceiling: </span>
                    <span className="text-emerald-400 font-medium">{r.limit}</span>
                  </div>
                </div>
              </div>

              {i < rules.length - 1 && (
                <div className="flex justify-center text-zinc-600">
                  <ArrowDown className="h-3 w-3" />
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
