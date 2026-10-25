import React, { useState } from "react";
import { useTrading } from "@/context/TradingContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Search, ExternalLink, Filter, Sparkles, BookOpen } from "lucide-react";
import { DecisionRecord } from "@/types";

export function DecisionJournal() {
  const { decisions, openDecisionModal, stepCandle } = useTrading();
  const [filter, setFilter] = useState<"ALL" | "APPROVED" | "RESIZED" | "REJECTED">("ALL");
  const [search, setSearch] = useState("");

  const filteredDecisions = decisions.filter((d) => {
    if (filter !== "ALL" && d.riskVerdict.action !== filter) return false;
    if (
      search &&
      !d.decisionId.toLowerCase().includes(search.toLowerCase()) &&
      !d.narrative.toLowerCase().includes(search.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  return (
    <Card className="bg-zinc-950/70 border-border/80">
      <CardHeader className="py-3 px-4 border-b border-border/60">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <BookOpen className="h-4 w-4 text-emerald-400" />
              <CardTitle>Decision Journal (Explainable Audit Trail)</CardTitle>
            </div>
            <p className="text-[11px] text-zinc-400 mt-0.5">
              Every closed candle produces a deterministic record with plain-language explanation and 6-point risk gate audit.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={stepCandle}
              className="gap-1.5 text-emerald-400 hover:text-emerald-300 border-emerald-500/30 text-xs"
            >
              <Sparkles className="h-3 w-3" /> Simulate Candle Close
            </Button>
          </div>
        </div>

        {/* Filter and Search Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-2 mt-3 pt-3 border-t border-border/40">
          <div className="flex items-center gap-1 w-full sm:w-auto">
            {(["ALL", "APPROVED", "RESIZED", "REJECTED"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`text-[11px] font-mono px-2.5 py-1 rounded-md transition-colors ${
                  filter === f
                    ? "bg-zinc-800 text-emerald-400 font-semibold border border-zinc-700"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-zinc-500" />
            <input
              type="text"
              placeholder="Search ID or narrative..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-zinc-900 border border-border/80 rounded-md pl-8 pr-3 py-1 text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 font-mono"
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Decision ID</TableHead>
                <TableHead>Time (UTC)</TableHead>
                <TableHead>Close Price</TableHead>
                <TableHead>Regime</TableHead>
                <TableHead>Strategy</TableHead>
                <TableHead>Risk Verdict</TableHead>
                <TableHead className="min-w-[340px]">Deterministic Plain-Language Narrative</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredDecisions.length > 0 ? (
                filteredDecisions.map((d) => (
                  <TableRow
                    key={d.decisionId}
                    className="cursor-pointer hover:bg-zinc-900/70"
                    onClick={() => openDecisionModal(d)}
                  >
                    <TableCell className="font-mono text-zinc-300 font-semibold text-[11px]">
                      {d.decisionId}
                    </TableCell>
                    <TableCell className="text-zinc-400 text-[10px] whitespace-nowrap">
                      {d.timestamp.split(" ")[1]}
                    </TableCell>
                    <TableCell className="font-mono font-medium text-zinc-200">
                      ${d.candle.close.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          d.regime.classification === "TRENDING"
                            ? "success"
                            : d.regime.classification === "RANGING"
                            ? "warning"
                            : "destructive"
                        }
                        className="text-[9px] py-0"
                      >
                        {d.regime.classification}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-zinc-300 text-[11px]">
                      {d.allocator.selectedStrategy
                        ? d.allocator.selectedStrategy.replace("_", " ")
                        : "None (Cash)"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          d.riskVerdict.action === "APPROVED"
                            ? "success"
                            : d.riskVerdict.action === "RESIZED"
                            ? "warning"
                            : "destructive"
                        }
                        className="text-[9px] py-0"
                      >
                        {d.riskVerdict.action}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-zinc-300 text-xs leading-relaxed max-w-[420px] truncate">
                      {d.narrative}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          openDecisionModal(d);
                        }}
                        className="h-6 text-[10px] gap-1 text-emerald-400 hover:text-emerald-300 px-2"
                      >
                        Explain <ExternalLink className="h-3 w-3" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={8} className="text-center p-8 text-zinc-500">
                    No decisions match the selected filter.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
