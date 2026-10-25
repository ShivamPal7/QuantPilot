import React from "react";
import { useTrading } from "@/context/TradingContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertOctagon,
  Activity,
  Play,
  Pause,
  RotateCcw,
  Sliders,
  Flame,
  ShieldAlert,
  Clock,
  Sparkles,
} from "lucide-react";

export function Header() {
  const {
    engineState,
    setEngineState,
    activeProfile,
    setActiveProfile,
    health,
    stepCandle,
    setIsKillModalOpen,
    setIsFlattenModalOpen,
    setIsConfigModalOpen,
    setIsChaosModalOpen,
    setIsResetModalOpen,
    chaosActive,
  } = useTrading();

  return (
    <header className="border-b border-border/80 bg-zinc-950/95 sticky top-0 z-40 backdrop-blur px-4 py-2.5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 max-w-[1600px] mx-auto">
        {/* Left: Branding & Core Badges */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <div className="h-7 w-7 rounded-md bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Activity className="h-4 w-4 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-bold text-sm tracking-tight text-zinc-100">QuantPilot</span>
                <span className="text-[11px] font-mono uppercase px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700/50">
                  Glass-Box Desk
                </span>
              </div>
            </div>
          </div>

          <div className="hidden sm:flex items-center space-x-2">
            <Badge variant="success" className="gap-1 text-[10px]">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping inline-block" />
              DELTA TESTNET
            </Badge>

            <span className="text-[11px] font-mono text-zinc-500 hidden lg:inline">
              cdn-ind.testnet.deltaex.org
            </span>
          </div>

          {/* Engine State Indicator */}
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-zinc-900 border border-border">
            <span
              className={`h-2 w-2 rounded-full ${
                engineState === "RUNNING"
                  ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"
                  : engineState === "PAUSED"
                  ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]"
                  : engineState === "HALTED"
                  ? "bg-rose-500 animate-pulse shadow-[0_0_10px_rgba(244,63,94,1)]"
                  : "bg-cyan-400"
              }`}
            />
            <span className="text-xs font-mono font-semibold tracking-wider text-zinc-200">
              {engineState}
            </span>
          </div>

          {chaosActive && (
            <Badge variant="destructive" className="animate-pulse gap-1 text-[10px]">
              <Flame className="h-3 w-3" /> CHAOS ACTIVE
            </Badge>
          )}
        </div>

        {/* Center / Right: Profiles & Interactive Desk Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Profile Switcher */}
          <div className="flex items-center bg-zinc-900/90 rounded-md border border-border p-0.5 text-xs font-mono">
            <button
              onClick={() => setActiveProfile("demo")}
              className={`px-2 py-1 rounded transition-colors text-[11px] ${
                activeProfile === "demo"
                  ? "bg-emerald-500/20 text-emerald-300 font-medium"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
              title="Demo Profile: 1-minute candle cadence for hackathon live evaluation"
            >
              Demo Profile (1m)
            </button>
            <button
              onClick={() => setActiveProfile("research")}
              className={`px-2 py-1 rounded transition-colors text-[11px] ${
                activeProfile === "research"
                  ? "bg-emerald-500/20 text-emerald-300 font-medium"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
              title="Research Profile: 1-hour cadence per multi-day persistence literature"
            >
              Research (1h)
            </button>
          </div>

          {/* Clock Drift Telemetry */}
          <div className="hidden xl:flex items-center space-x-1 text-[11px] font-mono text-zinc-400 px-2 py-1 rounded bg-zinc-900/60 border border-border/40">
            <Clock className="h-3 w-3 text-emerald-400" />
            <span>NTP Drift: {health.clockDriftSeconds}s</span>
          </div>

          {/* Quick Engine Actions */}
          {engineState === "RUNNING" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEngineState("PAUSED")}
              className="gap-1.5 text-zinc-300 hover:text-white"
            >
              <Pause className="h-3 w-3 text-amber-400" /> Pause
            </Button>
          )}

          {engineState === "PAUSED" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEngineState("RUNNING")}
              className="gap-1.5 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10"
            >
              <Play className="h-3 w-3" /> Resume
            </Button>
          )}

          {/* Step Candle button: Lets human demonstrator simulate next closed candle instant decision */}
          <Button
            variant="secondary"
            size="sm"
            onClick={stepCandle}
            className="gap-1.5 text-emerald-400 hover:bg-zinc-800 border border-zinc-700/60"
            title="Simulate immediate closed candle event to evaluate strategies and risk gate"
          >
            <Sparkles className="h-3 w-3 text-emerald-400" />
            <span className="hidden sm:inline">Step Candle</span>
          </Button>

          {/* Chaos Simulator button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsChaosModalOpen(true)}
            className="gap-1 text-amber-400 hover:text-amber-300 border-amber-500/30 hover:bg-amber-500/10"
          >
            <Flame className="h-3 w-3" />
            <span className="hidden sm:inline">Chaos Testbed</span>
          </Button>

          {/* Config Inspector */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsConfigModalOpen(true)}
            className="text-zinc-400 hover:text-zinc-200"
            title="Inspect frozen engine parameters and risk limits"
          >
            <Sliders className="h-3.5 w-3.5" />
          </Button>

          {/* Manual Flatten */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsFlattenModalOpen(true)}
            className="text-zinc-400 hover:text-rose-400 hover:border-rose-900/50"
            title="Emergency market close of all open inventory"
          >
            Flatten
          </Button>

          {/* If Halted, show Reset */}
          {engineState === "HALTED" ? (
            <Button
              variant="success"
              size="sm"
              onClick={() => setIsResetModalOpen(true)}
              className="gap-1.5 font-semibold"
            >
              <RotateCcw className="h-3 w-3" /> Reset Engine
            </Button>
          ) : (
            /* Emergency Kill Switch */
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setIsKillModalOpen(true)}
              className="gap-1.5 font-bold tracking-wider px-3 shadow-md"
            >
              <ShieldAlert className="h-3.5 w-3.5" />
              KILL SWITCH
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
