// Offline analysis mode was removed in v1.4.0 — every scan runs the multi-agent
// (cloud) analysis path, which requires a provider API key.
export type AnalysisMode = "cloud";

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
        <h3 className="text-sm font-medium text-ink-primary">Multi-agent analysis</h3>
        {!compact && (
          <p className="mt-1 text-sm text-ink-muted">
            Every scan runs the multi-agent analysis path — capability-aware attack-graph
            planning, an LLM judge, and confidence scoring. A provider API key is required.
          </p>
        )}
      </div>
      <div className="space-y-3 rounded-lg border border-surface-border bg-surface-overlay p-4">
        <label className="block text-sm">
          <span className="text-ink-muted">Analysis provider</span>
          <select
            className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm"
            value={value.analysis_provider || "openai"}
            onChange={(e) => onChange({ ...value, analysis_mode: "cloud", analysis_provider: e.target.value })}
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
            onChange={(e) => onChange({ ...value, analysis_mode: "cloud", analysis_model: e.target.value })}
          />
        </label>
        <label className="block text-sm">
          <span className="text-ink-muted">Analysis API key</span>
          <input
            type="password"
            className="mt-1 w-full rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm"
            placeholder="sk-..."
            value={value.analysis_api_key || ""}
            onChange={(e) => onChange({ ...value, analysis_mode: "cloud", analysis_api_key: e.target.value })}
          />
        </label>
      </div>
    </div>
  );
}
