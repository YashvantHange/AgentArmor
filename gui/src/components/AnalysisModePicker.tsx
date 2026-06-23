export type AnalysisMode = "offline" | "cloud";

export interface AnalysisModeValue {
  analysis_mode: AnalysisMode;
  analysis_provider?: string;
  analysis_model?: string;
  analysis_api_key?: string;
}

interface Props {
  value: AnalysisModeValue;
  onChange: (v: AnalysisModeValue) => void;
  compact?: boolean;
}

export function AnalysisModePicker({ value, onChange, compact }: Props) {
  return (
    <div className={compact ? "space-y-3" : "space-y-4"}>
      <div>
        <h3 className="text-sm font-medium text-ink-primary">Analysis mode</h3>
        {!compact && (
          <p className="mt-1 text-sm text-ink-muted">
            Choose how findings are explained after probes complete.
          </p>
        )}
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <ModeCard
          title="Offline"
          subtitle="Private · no API cost"
          description="Bundled detection models + built-in issue guides."
          active={value.analysis_mode === "offline"}
          onClick={() => onChange({ ...value, analysis_mode: "offline" })}
        />
        <ModeCard
          title="Multi-agent analysis"
          subtitle="Cloud · attack-graph red team"
          description="Uses your provider API for capability-aware planning, judge, and confidence scoring."
          active={value.analysis_mode === "cloud"}
          onClick={() => onChange({ ...value, analysis_mode: "cloud" })}
        />
      </div>
      {value.analysis_mode === "cloud" && (
        <div className="space-y-3 rounded-lg border border-surface-border bg-surface-overlay p-4">
          <label className="block text-sm">
            <span className="text-ink-muted">Analysis provider</span>
            <select
              className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm"
              value={value.analysis_provider || "openai"}
              onChange={(e) => onChange({ ...value, analysis_provider: e.target.value })}
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="gemini">Gemini</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-ink-muted">Analysis model</span>
            <input
              className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm"
              placeholder="gpt-4o-mini"
              value={value.analysis_model || ""}
              onChange={(e) => onChange({ ...value, analysis_model: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            <span className="text-ink-muted">Analysis API key</span>
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm"
              placeholder="sk-..."
              value={value.analysis_api_key || ""}
              onChange={(e) => onChange({ ...value, analysis_api_key: e.target.value })}
            />
          </label>
        </div>
      )}
    </div>
  );
}

function ModeCard({
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
