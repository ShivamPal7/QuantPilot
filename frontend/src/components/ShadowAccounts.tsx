import React from "react";
import { useTrading } from "@/context/TradingContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Layers, TrendingUp, RotateCcw, Percent, BarChart3, Scale } from "lucide-react";

export function ShadowAccounts() {
  const { shadowAccounts } = useTrading();

  return (
    <div className="space-y-4">
      {/* Mandatory Honesty Warning per Section 2.4 */}
      <Alert variant="warning" className="bg-amber-950/20 border-amber-500/30 text-amber-300">
        <AlertCircle className="h-4 w-4 text-amber-400" />
        <AlertTitle className="text-amber-300 font-semibold uppercase tracking-wider">
          Hypothetical Shadow Performance · Realistic Modelled Friction
        </AlertTitle>
        <AlertDescription className="text-zinc-300">
          Shadow accounts run in parallel on every closed candle. They model taker fee (5.0 bps),
          calibrated execution slippage (0.8–1.2 bps), and margin constraints. These are paper results
          used by the Allocator to assign real testnet risk, not guaranteed forward performance.
        </AlertDescription>
      </Alert>

      {/* Strategy Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {shadowAccounts.map((s) => (
          <Card
            key={s.id}
            className={`bg-zinc-950/70 border-border/80 transition-all ${
              s.isActive ? "border-purple-500/40 ring-1 ring-purple-500/20" : ""
            }`}
          >
            <CardHeader className="p-3.5 pb-2">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-zinc-200 text-xs normal-case font-bold font-mono">
                    {s.name}
                  </CardTitle>
                  <CardDescription className="text-[11px] text-zinc-400 line-clamp-2 mt-1">
                    {s.description}
                  </CardDescription>
                </div>
                {s.isActive ? (
                  <Badge variant="cyan" className="text-[9px] py-0">
                    ALLOCATED
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-[9px] py-0 text-zinc-500">
                    PAPER
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-3.5 pt-2 space-y-2">
              <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-2 border-t border-border/40">
                <div>
                  <span className="text-[10px] text-zinc-500">Net Paper PnL</span>
                  <div
                    className={`font-bold text-sm ${
                      s.netPnl >= 0 ? "text-emerald-400" : "text-rose-400"
                    }`}
                  >
                    {s.netPnl >= 0 ? "+" : ""}${s.netPnl.toFixed(2)}
                  </div>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-500">Win Rate / PF</span>
                  <div className="font-semibold text-zinc-200">
                    {s.winRate.toFixed(1)}% / {s.profitFactor.toFixed(2)}
                  </div>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-500">Max Drawdown</span>
                  <div className="text-zinc-300">{s.maxDrawdownPct.toFixed(1)}%</div>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-500">Sharpe Ratio</span>
                  <div className="text-zinc-300">{s.sharpeRatio.toFixed(2)}</div>
                </div>
              </div>

              {/* Allocation Weight Slider preview */}
              <div className="pt-2">
                <div className="flex justify-between text-[10px] font-mono text-zinc-400 mb-1">
                  <span>Allocator Probability Weight:</span>
                  <span className="text-purple-400 font-bold">
                    {(s.allocationWeight * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-zinc-900 h-1.5 rounded-full overflow-hidden border border-border/40">
                  <div
                    className="bg-purple-500 h-full rounded-full transition-all duration-300"
                    style={{ width: `${s.allocationWeight * 100}%` }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Comprehensive Audit Table */}
      <Card className="bg-zinc-950/70 border-border/80">
        <CardHeader className="py-2.5 px-4 border-b border-border/60">
          <CardTitle>Cross-Strategy Telemetry & Cost Model Deduction</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Strategy Module</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Sample Trades</TableHead>
                  <TableHead>Win Rate</TableHead>
                  <TableHead>Profit Factor</TableHead>
                  <TableHead>Net Paper PnL</TableHead>
                  <TableHead>Max DD</TableHead>
                  <TableHead>Friction Paid</TableHead>
                  <TableHead>Current Paper Position</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shadowAccounts.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-semibold text-zinc-200">{s.name}</TableCell>
                    <TableCell>
                      {s.isActive ? (
                        <Badge variant="success" className="text-[9px] py-0">
                          LIVE ALLOCATED
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-[9px] py-0 text-zinc-400">
                          SHADOW ONLY
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>{s.tradesCount}</TableCell>
                    <TableCell>{s.winRate.toFixed(1)}%</TableCell>
                    <TableCell>{s.profitFactor.toFixed(2)}</TableCell>
                    <TableCell
                      className={`font-semibold ${
                        s.netPnl >= 0 ? "text-emerald-400" : "text-rose-400"
                      }`}
                    >
                      {s.netPnl >= 0 ? "+" : ""}${s.netPnl.toFixed(2)}
                    </TableCell>
                    <TableCell>{s.maxDrawdownPct.toFixed(1)}%</TableCell>
                    <TableCell className="text-zinc-400 font-mono text-[11px]">
                      -${s.frictionPaidUsdt.toFixed(2)}
                    </TableCell>
                    <TableCell className="text-zinc-300">
                      {s.currentPosition > 0
                        ? `LONG ${s.currentPosition} ct`
                        : s.currentPosition < 0
                        ? `SHORT ${Math.abs(s.currentPosition)} ct`
                        : "FLAT"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
