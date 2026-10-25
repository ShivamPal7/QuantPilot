import React from "react";
import { useTrading, CHAOS_SCENARIOS } from "@/context/TradingContext";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Flame, ShieldCheck, Play, RotateCcw, Terminal, AlertTriangle } from "lucide-react";

export function ChaosSimulatorModal() {
  const {
    isChaosModalOpen,
    setIsChaosModalOpen,
    runChaosScenario,
    clearChaos,
    chaosActive,
    activeChaosScenario,
    chaosLogs,
  } = useTrading();

  return (
    <Dialog open={isChaosModalOpen} onOpenChange={setIsChaosModalOpen}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-zinc-950 border-amber-900/60 p-6">
        <DialogHeader className="border-b border-border/60 pb-3 mb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-amber-400">
              <Flame className="h-5 w-5" />
              <DialogTitle className="text-zinc-100 font-bold">
                Chaos Testbed & Resilience Demonstrator (Section 13.4)
              </DialogTitle>
            </div>
            {chaosActive && (
              <Button
                variant="outline"
                size="sm"
                onClick={clearChaos}
                className="h-7 text-xs gap-1 text-emerald-400 border-emerald-500/40"
              >
                <RotateCcw className="h-3 w-3" /> Clear Chaos & Restore
              </Button>
            )}
          </div>
          <DialogDescription className="text-zinc-400 text-xs mt-1">
            Replays simulated production anomalies on the local decision engine without firing harmful traffic to Delta Exchange. Proves that risk gates and watchdogs respond as specified.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Active Chaos Notice if running */}
          {chaosActive && activeChaosScenario && (
            <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-500/40 text-amber-300 text-xs flex items-start gap-2 animate-in fade-in">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-400" />
              <div>
                <span className="font-bold">ACTIVE TEST SCENARIO: {activeChaosScenario.title}</span>
                <p className="text-zinc-300 text-[11px] mt-0.5">
                  Target: {activeChaosScenario.safeguardTarget} — {activeChaosScenario.expectedBehavior}
                </p>
              </div>
            </div>
          )}

          {/* Grid of Chaos Scenarios */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {CHAOS_SCENARIOS.map((sc) => (
              <Card
                key={sc.id}
                className="bg-zinc-900/60 border-border/80 hover:border-zinc-700 transition-colors"
              >
                <CardHeader className="p-3.5 pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-xs text-zinc-200 normal-case font-bold font-mono">
                      {sc.title}
                    </CardTitle>
                    <Badge
                      variant={
                        sc.severity === "CRITICAL"
                          ? "destructive"
                          : sc.severity === "HIGH"
                          ? "warning"
                          : "outline"
                      }
                      className="text-[9px] py-0"
                    >
                      {sc.severity}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="p-3.5 pt-1 space-y-2">
                  <p className="text-[11px] text-zinc-400 leading-relaxed font-sans">
                    {sc.description}
                  </p>
                  <div className="p-2 rounded bg-zinc-950/80 border border-border/40 text-[10px] font-mono text-zinc-300">
                    <span className="text-emerald-400 font-semibold">Expected: </span>
                    {sc.expectedBehavior}
                  </div>
                  <div className="pt-1 flex justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => runChaosScenario(sc.id)}
                      className="h-7 text-xs gap-1.5 text-amber-400 hover:text-amber-300 hover:bg-amber-500/10 border-amber-500/30"
                    >
                      <Play className="h-3 w-3" /> Run Scenario
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Live Chaos Console / Event Log */}
          <Card className="bg-zinc-950 border-border/80">
            <CardHeader className="py-2.5 px-3 border-b border-border/60 flex flex-row items-center justify-between">
              <CardTitle className="text-xs flex items-center gap-1.5 font-mono text-zinc-300">
                <Terminal className="h-3.5 w-3.5 text-emerald-400" /> Chaos & Safeguard Audit Event Stream
              </CardTitle>
              <span className="text-[10px] font-mono text-zinc-500">Live Telemetry</span>
            </CardHeader>
            <CardContent className="p-3">
              <div className="bg-black/80 rounded border border-border/40 p-3 font-mono text-[11px] h-40 overflow-y-auto space-y-1 text-zinc-300">
                {chaosLogs.length > 0 ? (
                  chaosLogs.map((log, i) => (
                    <div
                      key={i}
                      className={
                        log.includes("SAFEGUARD")
                          ? "text-emerald-400 font-semibold"
                          : log.includes("CHAOS")
                          ? "text-amber-400 font-semibold"
                          : log.includes("KILL SWITCH")
                          ? "text-rose-400 font-bold"
                          : "text-zinc-400"
                      }
                    >
                      {log}
                    </div>
                  ))
                ) : (
                  <div className="text-zinc-600 text-center pt-8">
                    Select a scenario above to test automated system safeguards on screen.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="mt-4 pt-3 border-t border-border/60 flex justify-end">
          <Button variant="secondary" size="sm" onClick={() => setIsChaosModalOpen(false)}>
            Close Testbed
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
