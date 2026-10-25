import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "cyan";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants = {
    default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
    secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
    destructive: "border-transparent bg-destructive/15 text-rose-400 border border-rose-500/20",
    outline: "text-zinc-300 border border-border",
    success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400 border",
    warning: "border-amber-500/30 bg-amber-500/10 text-amber-400 border",
    cyan: "border-cyan-500/30 bg-cyan-500/10 text-cyan-400 border",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 font-mono tracking-wide",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };
