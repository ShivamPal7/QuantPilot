import React from "react";
import { useTrading } from "@/context/TradingContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Shield, ArrowUpRight, ArrowDownRight, CheckCircle2, AlertCircle } from "lucide-react";

export function LiveDesk() {
  const { position, orders, fills, setIsFlattenModalOpen, marketPrice } = useTrading();

  return (
    <div className="space-y-4">
      {/* 1. Exchange-Reconciled Positions */}
      <Card className="bg-zinc-950/70 border-border/80">
        <CardHeader className="py-2.5 px-4 border-b border-border/60 flex flex-row items-center justify-between">
          <div className="flex items-center space-x-2">
            <CardTitle>Exchange-Reconciled Positions</CardTitle>
            <Badge variant="outline" className="text-[10px] text-zinc-400">
              Source: Signed Delta REST Truth
            </Badge>
          </div>
          {position && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setIsFlattenModalOpen(true)}
              className="h-6 text-[11px] px-2"
            >
              Close Position
            </Button>
          )}
        </CardHeader>
        <CardContent className="p-0">
          {position ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Symbol</TableHead>
                    <TableHead>Side</TableHead>
                    <TableHead>Contracts</TableHead>
                    <TableHead>Entry Price</TableHead>
                    <TableHead>Mark Price</TableHead>
                    <TableHead>Liq. Price</TableHead>
                    <TableHead>Unrealized PnL</TableHead>
                    <TableHead>Server-Side Brackets (Take-Profit / Stop-Loss)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell className="font-bold text-zinc-100">{position.symbol}</TableCell>
                    <TableCell>
                      <Badge
                        variant={position.side === "LONG" ? "success" : "destructive"}
                        className="text-[10px]"
                      >
                        {position.side} {position.leverage}x
                      </Badge>
                    </TableCell>
                    <TableCell>{position.size} ct (0.00{position.size} BTC)</TableCell>
                    <TableCell className="text-zinc-300">
                      ${position.entryPrice.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-zinc-100 font-semibold">
                      ${marketPrice.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-rose-400/90">
                      ${position.liquidationPrice.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`font-semibold ${
                          position.unrealizedPnl >= 0 ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        {position.unrealizedPnl >= 0 ? "+" : ""}${position.unrealizedPnl.toFixed(2)} (
                        {position.unrealizedPnlPct >= 0 ? "+" : ""}
                        {position.unrealizedPnlPct.toFixed(2)}%)
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2 text-[11px]">
                        <span className="inline-flex items-center text-emerald-400 gap-1 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                          <CheckCircle2 className="h-3 w-3" /> TP: $
                          {position.brackets.takeProfit.price.toLocaleString()}
                        </span>
                        <span className="inline-flex items-center text-rose-400 gap-1 bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/20">
                          <Shield className="h-3 w-3" /> SL: $
                          {position.brackets.stopLoss.price.toLocaleString()}
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="p-8 text-center text-zinc-500 text-xs font-mono">
              No open positions on Delta Exchange Testnet. System is flat (Cash).
            </div>
          )}
        </CardContent>
      </Card>

      {/* 2. Active Orders & Reconciled Fills in 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Working Orders */}
        <Card className="bg-zinc-950/70 border-border/80">
          <CardHeader className="py-2.5 px-4 border-b border-border/60 flex flex-row items-center justify-between">
            <CardTitle>Working Orders & Brackets</CardTitle>
            <span className="text-[11px] font-mono text-zinc-400">{orders.length} active</span>
          </CardHeader>
          <CardContent className="p-0">
            {orders.length > 0 ? (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Client ID</TableHead>
                      <TableHead>Side / Type</TableHead>
                      <TableHead>Price</TableHead>
                      <TableHead>Qty</TableHead>
                      <TableHead>Flags</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {orders.map((o) => (
                      <TableRow key={o.clientOrderId}>
                        <TableCell className="text-zinc-400 font-mono text-[10px]">
                          {o.clientOrderId}
                        </TableCell>
                        <TableCell>
                          <span
                            className={
                              o.side === "BUY" ? "text-emerald-400 font-medium" : "text-rose-400 font-medium"
                            }
                          >
                            {o.side} {o.type}
                          </span>
                        </TableCell>
                        <TableCell className="font-semibold text-zinc-200">
                          ${o.price.toLocaleString()}
                        </TableCell>
                        <TableCell>{o.size}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            {o.reduceOnly && (
                              <span className="text-[9px] px-1 bg-zinc-800 text-zinc-300 rounded border border-zinc-700">
                                REDUCE
                              </span>
                            )}
                            {o.postOnly && (
                              <span className="text-[9px] px-1 bg-zinc-800 text-zinc-300 rounded border border-zinc-700">
                                POST
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="cyan" className="text-[9px] py-0">
                            {o.status}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="p-6 text-center text-zinc-500 text-xs font-mono">
                No pending or working bracket orders.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Reconciled Fills */}
        <Card className="bg-zinc-950/70 border-border/80">
          <CardHeader className="py-2.5 px-4 border-b border-border/60 flex flex-row items-center justify-between">
            <CardTitle>Recent Reconciled Fills</CardTitle>
            <span className="text-[11px] font-mono text-zinc-400">Execution Quality Audited</span>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Side</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Fee (USDT)</TableHead>
                    <TableHead>Slippage</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {fills.map((f) => (
                    <TableRow key={f.fillId}>
                      <TableCell className="text-zinc-500 text-[10px]">{f.timestamp}</TableCell>
                      <TableCell>
                        <span className={f.side === "BUY" ? "text-emerald-400" : "text-rose-400"}>
                          {f.side}
                        </span>
                      </TableCell>
                      <TableCell className="font-semibold text-zinc-200">
                        ${f.price.toLocaleString()}
                      </TableCell>
                      <TableCell>{f.size} ct</TableCell>
                      <TableCell className="text-zinc-400 font-mono text-[11px]">
                        ${f.feeUsdt.toFixed(2)} ({f.feeBps} bps)
                      </TableCell>
                      <TableCell>
                        <span className="text-emerald-400 text-[11px]">
                          {f.slippageBps} bps
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
