import React from "react";
import { useTrading } from "@/context/TradingContext";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

export function FlattenModal() {
  const { isFlattenModalOpen, setIsFlattenModalOpen, flattenPositions, position, marketPrice } = useTrading();

  if (!position) return null;

  const handleFlatten = () => {
    flattenPositions();
    setIsFlattenModalOpen(false);
  };

  return (
    <Dialog open={isFlattenModalOpen} onOpenChange={setIsFlattenModalOpen}>
      <DialogContent className="max-w-md bg-zinc-950 border-amber-900/60 p-6">
        <DialogHeader>
          <div className="flex items-center space-x-2 text-amber-400 mb-1">
            <AlertTriangle className="h-5 w-5" />
            <DialogTitle className="text-zinc-100 font-bold">Manual Emergency Flatten</DialogTitle>
          </div>
          <DialogDescription className="text-zinc-300 text-xs">
            Send immediate market IOC reduce-only order to close active inventory and cancel all pending bracket orders.
          </DialogDescription>
        </DialogHeader>

        <div className="p-3 my-2 rounded bg-zinc-900 border border-border text-xs font-mono space-y-1">
          <div className="flex justify-between">
            <span className="text-zinc-400">Position to close:</span>
            <span className="text-zinc-100 font-bold">
              {position.side} {position.size} ct {position.symbol}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-400">Current Mark:</span>
            <span className="text-zinc-200">${marketPrice.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-400">Estimated Realized PnL:</span>
            <span
              className={
                position.unrealizedPnl >= 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"
              }
            >
              {position.unrealizedPnl >= 0 ? "+" : ""}${position.unrealizedPnl.toFixed(2)}
            </span>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="secondary" size="sm" onClick={() => setIsFlattenModalOpen(false)}>
            Cancel
          </Button>
          <Button variant="destructive" size="sm" onClick={handleFlatten} className="font-bold">
            Execute Reduce-Only Flatten
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
