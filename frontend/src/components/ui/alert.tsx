import * as React from "react";
import { cn } from "@/lib/utils";

const Alert = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { variant?: "default" | "destructive" | "warning" | "success" }
>(({ className, variant = "default", ...props }, ref) => {
  const variants = {
    default: "bg-zinc-900 text-zinc-100 border-border",
    destructive: "border-rose-900/50 text-rose-300 bg-rose-950/20 [&>svg]:text-rose-400",
    warning: "border-amber-900/50 text-amber-300 bg-amber-950/20 [&>svg]:text-amber-400",
    success: "border-emerald-900/50 text-emerald-300 bg-emerald-950/20 [&>svg]:text-emerald-400",
  };

  return (
    <div
      ref={ref}
      role="alert"
      className={cn("relative w-full rounded-lg border p-3 text-xs [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-3 [&>svg]:top-3.5", variants[variant], className)}
      {...props}
    />
  );
});
Alert.displayName = "Alert";

const AlertTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h5
    ref={ref}
    className={cn("mb-1 font-semibold leading-none tracking-tight text-xs", className)}
    {...props}
  />
));
AlertTitle.displayName = "AlertTitle";

const AlertDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("text-xs [&_p]:leading-relaxed opacity-90", className)}
    {...props}
  />
));
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertTitle, AlertDescription };
