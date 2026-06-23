export type ScanDepth = "standard" | "multi_agentic";

export interface ScanDepthValue {
  scan_depth: ScanDepth;
}

interface Props {
  value: ScanDepthValue;
  onChange: (v: ScanDepthValue) => void;
  multiAgenticRequiresCloud?: boolean;
}

export function ScanDepthPicker({ value, onChange, multiAgenticRequiresCloud = true }: Props) {
  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium text-ink-primary">Scan depth</h3>
        <p className="mt-1 text-sm text-ink-muted">
          Standard runs offline probes. Multi-agentic adds cloud LLM discovery, judge, and expanded attack planning.
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <DepthCard
          title="Standard"
          subtitle="Offline · no API cost"
          description="Heuristic discovery + capability-aware OWASP probes with bundled detection."
          active={value.scan_depth === "standard"}
          onClick={() => onChange({ scan_depth: "standard" })}
        />
        <DepthCard
          title="Multi-agent red team"
          subtitle="Cloud · attack-graph planning"
          description={
            multiAgenticRequiresCloud
              ? "Requires analysis API key. Runs capability-aware attack paths with Memory/A2A agents and budget tracking."
              : "Expanded attack-graph planning with cloud analysis."
          }
          active={value.scan_depth === "multi_agentic"}
          onClick={() => onChange({ scan_depth: "multi_agentic" })}
        />
      </div>
    </div>
  );
}

function DepthCard({
  title,
  subtitle,
  description,
  active,
  onClick,
}: {
  title: string;
  subtitle: string;
  description: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border p-4 text-left transition-colors focus-ring ${
        active
          ? "border-brand-500 bg-brand-500/10"
          : "border-surface-border bg-surface-raised hover:border-surface-border-strong"
      }`}
    >
      <div className="text-sm font-semibold text-ink-primary">{title}</div>
      <div className="text-xs text-brand-600 dark:text-brand-400">{subtitle}</div>
      <p className="mt-2 text-xs text-ink-muted">{description}</p>
    </button>
  );
}
