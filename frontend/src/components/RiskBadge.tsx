import type { RiskSeverity } from "@/types/api";
import { cn } from "@/lib/utils";

const config: Record<RiskSeverity, { label: string; classes: string }> = {
  critical: { label: "Critical", classes: "bg-risk-critical/15 text-risk-critical border-risk-critical/30" },
  high:     { label: "High",     classes: "bg-risk-high/15 text-risk-high border-risk-high/30" },
  medium:   { label: "Medium",   classes: "bg-risk-medium/15 text-risk-medium border-risk-medium/30" },
  low:      { label: "Low",      classes: "bg-risk-low/15 text-risk-low border-risk-low/30" },
  info:     { label: "Info",     classes: "bg-risk-info/15 text-risk-info border-risk-info/30" },
};

export default function RiskBadge({
  severity,
  className,
}: {
  severity: RiskSeverity;
  className?: string;
}) {
  const c = config[severity];
  return (
    <span
      className={cn(
        "text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border leading-none shrink-0",
        c.classes,
        className,
      )}
    >
      {c.label}
    </span>
  );
}
