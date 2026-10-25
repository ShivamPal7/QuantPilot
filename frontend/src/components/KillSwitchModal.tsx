import React, { useState } from "react";
import { useTrading } from "@/context/TradingContext";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ShieldAlert, AlertTriangle } from "lucide-react";

export function KillSwitchModal() {
  const { isKillModalOpen, setIsKillModalOpen, triggerKillSwitch } = useTrading();
  const [secret, setSecret] = useState("admin-testnet-secret");
  const [error, setError] = useState("");

  const handleConfirm = () => {
    if (!secret.trim()) {
      setError("Control secret required per Section 2.2 security policy.");
      return;
    }
    const success = triggerKillSwitch(secret);
    if (success) {
      setIsKillModalOpen(false);
      setError("");
    } else {
      setError("Failed to execute emergency halt.");
    }
  };

  return (
    <Dialog open={isKillModalOpen} onOpenChange={setIsKillModalOpen}>
      <DialogContent className="max-w-md bg-zinc-950 border-rose-900/60 p-6">
        <DialogHeader>
          <div className="flex items-center space-x-2 text-rose-500 mb-1">
            <ShieldAlert className="h-5 w-5" />
            <DialogTitle className="text-rose-400 font-bold">EMERGENCY KILL SWITCH</DialogTitle>
          </div>
          <DialogDescription className="text-zinc-300 text-xs">
            Section 2.1 Non-Negotiable Safety Rule: This action will immediately halt the engine loop, cancel all open orders on Delta Exchange Testnet, and close any live position with reduce-only market orders.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 my-2">
          <div className="p-3 rounded bg-rose-950/20 border border-rose-900/40 text-xs text-rose-300 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
            <div>
              State will be locked into <strong>HALTED</strong> mode. Restarting requires an explicit human reset with a verified flat state.
            </div>
          </div>

          <div>
            <label className="text-[11px] font-mono text-zinc-400 block mb-1">
              X-Control-Secret Authorization:
            </label>
            <input
              type="password"
              value={secret}
              onChange={(e) => {
                setSecret(e.target.value);
                setError("");
              }}
              placeholder="Enter shared secret..."
              className="w-full bg-zinc-900 border border-border rounded px-3 py-1.5 text-xs text-zinc-100 font-mono focus:outline-none focus:ring-1 focus:ring-rose-500"
            />
            {error && <p className="text-[11px] text-rose-400 mt-1">{error}</p>}
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="secondary" size="sm" onClick={() => setIsKillModalOpen(false)}>
            Cancel
          </Button>
          <Button variant="destructive" size="sm" onClick={handleConfirm} className="font-bold">
            HALT TRADING DESK NOW
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
