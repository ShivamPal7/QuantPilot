import React, { useState } from "react";
import { TradingProvider, useTrading } from "@/context/TradingContext";
import { Header } from "@/components/Header";
import { MetricCards } from "@/components/MetricCards";
import { LiveDesk } from "@/components/LiveDesk";
import { ShadowAccounts } from "@/components/ShadowAccounts";
import { DecisionJournal } from "@/components/DecisionJournal";
import { RiskGateMatrix } from "@/components/RiskGateMatrix";
import { DecisionModal } from "@/components/DecisionModal";
import { KillSwitchModal } from "@/components/KillSwitchModal";
import { ResetModal } from "@/components/ResetModal";
import { FlattenModal } from "@/components/FlattenModal";
import { ChaosSimulatorModal } from "@/components/ChaosSimulatorModal";
import { ConfigModal } from "@/components/ConfigModal";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  LayoutDashboard,
  BookOpen,
  Layers,
  ShieldCheck,
  Flame,
  Terminal,
  ExternalLink,
} from "lucide-react";

function MainDashboard() {
  const [currentTab, setCurrentTab] = useState("live");
  const { decisions, shadowAccounts } = useTrading();

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      {/* Top Navigation & Status Bar */}
      <Header />

      {/* Main Workspace Container */}
      <main className="flex-1 max-w-[1600px] w-full mx-auto p-4 space-y-4">
        {/* Top Metric Cards (5 Columns) */}
        <MetricCards />

        {/* Tabbed Navigation for Workspace */}
        <Tabs defaultValue="live" value={currentTab} onValueChange={setCurrentTab} className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/60 pb-2">
            <TabsList className="bg-zinc-900 border-border/80">
              <TabsTrigger value="live" className="gap-1.5 text-xs">
                <LayoutDashboard className="h-3.5 w-3.5" />
                <span>Live Desk</span>
              </TabsTrigger>

              <TabsTrigger value="journal" className="gap-1.5 text-xs">
                <BookOpen className="h-3.5 w-3.5" />
                <span>Decision Journal</span>
                <span className="ml-1 text-[10px] px-1.5 py-0.2 rounded-full bg-zinc-800 text-zinc-300">
                  {decisions.length}
                </span>
              </TabsTrigger>

              <TabsTrigger value="shadow" className="gap-1.5 text-xs">
                <Layers className="h-3.5 w-3.5" />
                <span>Shadow Accounts</span>
              </TabsTrigger>

              <TabsTrigger value="risk" className="gap-1.5 text-xs">
                <ShieldCheck className="h-3.5 w-3.5" />
                <span>Risk Gate Policy</span>
              </TabsTrigger>

              <TabsTrigger value="chaos" className="gap-1.5 text-xs text-amber-400 data-[state=active]:text-amber-300">
                <Flame className="h-3.5 w-3.5" />
                <span>Chaos Scenarios</span>
              </TabsTrigger>
            </TabsList>

            <div className="text-[11px] font-mono text-zinc-500 hidden md:flex items-center gap-2">
              <span>Pure Decision Logic</span>
              <span>·</span>
              <span>Reconciled Edge Truth</span>
              <span>·</span>
              <span>Fail-Closed</span>
            </div>
          </div>

          {/* Tab 1: Live Desk */}
          <TabsContent value="live">
            <LiveDesk />
          </TabsContent>

          {/* Tab 2: Decision Journal */}
          <TabsContent value="journal">
            <DecisionJournal />
          </TabsContent>

          {/* Tab 3: Virtual Shadow Accounts */}
          <TabsContent value="shadow">
            <ShadowAccounts />
          </TabsContent>

          {/* Tab 4: Layered Risk Gate */}
          <TabsContent value="risk">
            <RiskGateMatrix />
          </TabsContent>

          {/* Tab 5: Chaos Quick Access */}
          <TabsContent value="chaos">
            <div className="p-4 rounded-lg border border-amber-900/40 bg-zinc-950/70 text-center space-y-3 py-10">
              <Flame className="h-8 w-8 text-amber-400 mx-auto" />
              <h3 className="text-base font-bold text-zinc-100">
                Chaos Testbed & Safeguard Verifier
              </h3>
              <p className="text-xs text-zinc-400 max-w-lg mx-auto">
                Trigger simulated market anomalies (flash shocks, stale candles, websocket drops, rate limits) to verify that Risk Gates, Stop-Loss brackets, and Watchdogs protect capital automatically.
              </p>
              <button
                onClick={() => {
                  const btn = document.querySelector('[title="Chaos Testbed"]');
                  // open modal directly via trigger
                }}
                className="inline-flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-md bg-amber-500 text-black hover:bg-amber-400"
              >
                <ChaosTriggerButton />
              </button>
            </div>
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/60 bg-zinc-950 px-4 py-3 text-xs text-zinc-500 font-mono mt-auto">
        <div className="max-w-[1600px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>
            <span>QuantPilot "Glass-Box Desk"</span>
            <span className="mx-2">·</span>
            <span>Delta Exchange Testnet (cdn-ind.testnet.deltaex.org)</span>
            <span className="mx-2">·</span>
            <span className="text-zinc-400">Standalone UI Mode (API Decoupled)</span>
          </div>
          <div>
            <span>No real capital · Paper trading enabled · Zero withdrawal permissions</span>
          </div>
        </div>
      </footer>

      {/* Floating / Standalone Modals */}
      <DecisionModal />
      <KillSwitchModal />
      <ResetModal />
      <FlattenModal />
      <ChaosSimulatorModal />
      <ConfigModal />
    </div>
  );
}

function ChaosTriggerButton() {
  const { setIsChaosModalOpen } = useTrading();
  return (
    <span onClick={() => setIsChaosModalOpen(true)} className="cursor-pointer">
      Open Chaos Simulator Modal
    </span>
  );
}

export default function App() {
  return (
    <TradingProvider>
      <MainDashboard />
    </TradingProvider>
  );
}
