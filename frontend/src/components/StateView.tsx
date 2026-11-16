import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

function renderValue(value: unknown): ReactNode {
  if (value === null || value === undefined) return <span className="text-muted-foreground">—</span>;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return <span className="whitespace-pre-wrap break-words">{String(value)}</span>;
  return <pre className="mono max-h-56 overflow-auto rounded-lg bg-muted/60 p-3 text-xs leading-relaxed">{JSON.stringify(value, null, 2)}</pre>;
}

export function StateView({ state, className }: { state: Record<string, unknown>; className?: string }) {
  const entries = Object.entries(state);
  if (!entries.length) return <p className="text-sm text-muted-foreground">—</p>;
  return (
    <div className={cn("grid gap-4", className)}>
      {entries.map(([key, value]) => (
        <div key={key} className="grid gap-1 border-b border-border/70 pb-3 last:border-0 last:pb-0 md:grid-cols-[140px_minmax(0,1fr)] md:gap-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{key}</div>
          <div className="text-sm">{renderValue(value)}</div>
        </div>
      ))}
    </div>
  );
}
