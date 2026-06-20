type Tone = "default" | "brand" | "critical" | "high" | "medium" | "low" | "info";

const tones: Record<Tone, string> = {
  default: "bg-surface-overlay text-ink-secondary border-surface-border",
  brand: "bg-brand-500/10 text-brand-400 border-brand-500/20",
  critical: "bg-red-500/10 text-red-300 border-red-500/20",
  high: "bg-orange-500/10 text-orange-300 border-orange-500/20",
  medium: "bg-amber-500/10 text-amber-300 border-amber-500/20",
  low: "bg-sky-500/10 text-sky-300 border-sky-500/20",
  info: "bg-zinc-500/10 text-zinc-300 border-zinc-500/20",
};

export function Badge({
  children,
  tone = "default",
  className = "",
}: {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function severityTone(severity: string): Tone {
  const map: Record<string, Tone> = {
    CRITICAL: "critical",
    HIGH: "high",
    MEDIUM: "medium",
    LOW: "low",
    INFO: "info",
  };
  return map[severity] || "default";
}
