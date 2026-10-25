import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "success" | "warning";
  size?: "default" | "sm" | "lg" | "icon";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    const baseStyles = "inline-flex items-center justify-center whitespace-nowrap rounded-md text-xs font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 select-none";
    
    const variants = {
      default: "bg-primary text-primary-foreground hover:bg-emerald-600 shadow-sm",
      destructive: "bg-destructive text-destructive-foreground hover:bg-rose-700 shadow-sm",
      outline: "border border-border bg-transparent hover:bg-accent hover:text-accent-foreground",
      secondary: "bg-secondary text-secondary-foreground hover:bg-zinc-800",
      ghost: "hover:bg-accent hover:text-accent-foreground",
      link: "text-primary underline-offset-4 hover:underline",
      success: "bg-emerald-600/20 text-emerald-400 border border-emerald-600/30 hover:bg-emerald-600/30",
      warning: "bg-amber-500/10 text-amber-400 border border-amber-500/30 hover:bg-amber-500/20",
    };

    const sizes = {
      default: "h-8 px-3 py-1.5",
      sm: "h-7 rounded px-2 text-xs",
      lg: "h-10 rounded-md px-6 text-sm",
      icon: "h-7 w-7",
    };

    return (
      <button
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
