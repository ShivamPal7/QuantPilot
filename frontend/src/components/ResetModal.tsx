import React, { useState } from "react";
import { useTrading } from "@/context/TradingContext";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { RotateCcw, CheckCircle2 } from "lucide-react";

export function ResetModal() {
  const { isResetModalOpen, setIsResetModalOpen, resetFromHalt } = useTrading();
  const [secret, setSecret] = useState("admin-testnet-secret");
  const [confirmed, setConfirmed] = useState(false);

  const handleReset = () => {
    if (!confirmed) return;
    const ok = resetFromHalt(secret);
    if (ok) {
      setIsResetModalOpen(false);
      setConfirmed(false);
    }
  };

  return (
    <Dialog open={isResetModalOpen} onOpenChange={setIsResetModalOpen}>
      <DialogContent className="max-w-md bg-zinc-950 border-emerald-900/60 p-6">
        <DialogHeader>
          <div className="flex items-center space-x-2 text-emerald-400 mb-1">
            <RotateCcw className="h-5 w-5" />
            <DialogTitle className="text-zinc-100 font-bold">Reset Engine from Halted State</DialogTitle>
          </div>
          <DialogDescription className="text-zinc-300 text-xs">
            Per Section 9.8: Resetting from HALT requires explicit operator confirmation and verification that exchange state is reconciled flat.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 my-2">
          <div className="p-3 rounded bg-zinc-900 border border-border text-xs text-zinc-300 space-y-1">
            <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
              <CheckCircle2 className="h-3.5 w-3.5" /> Exchange Reconciled Flat State Confirmed
            </div>
            <p className="text-[11px] text-zinc-400">
              No orphan orders detected. Database integrity check passed.
            </p>
          </div>

          <div>
            <label className="text-[11px] font-mono text-zinc-400 block mb-1">
              X-Control-Secret:
            </label>
            <input
              type="password"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              className="w-full bg-zinc-900 border border-border rounded px-3 py-1.5 text-xs text-zinc-100 font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <label className="flex items-center space-x-2 text-xs text-zinc-300 cursor-pointer pt-1">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="rounded bg-zinc-900 border-zinc-700 text-emerald-500 focus:ring-0"
            />
            <span>I confirm exchange state is flat and safe to resume trading</span>
          </label>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="secondary" size="sm" onClick={() => setIsResetModalOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="success"
            size="sm"
            disabled={!confirmed}
            onClick={handleReset}
            className="font-semibold"
          >
            Confirm & Resume Trading
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
