import { ScanType } from "../api/client";
import { Input } from "./ui/Input";

export interface RedTeamOptions {
  l0_enabled: boolean;
  max_variants_per_goal: number;
  l0_suites: string[];
  cloud_mutations_enabled: boolean;
  self_play_enabled: boolean;
  self_play_max_rounds: number;
  self_play_stop_on_success: boolean;
  self_play_discovery_enabled: boolean;
  self_play_defender_enabled: boolean;
}

export const DEFAULT_REDTEAM: RedTeamOptions = {
  l0_enabled: true,
  max_variants_per_goal: 100,
  l0_suites: ["prompt_leak", "model_theft", "memory_poison", "poisoning"],
  cloud_mutations_enabled: true,
  self_play_enabled: false,
  self_play_max_rounds: 20,
  self_play_stop_on_success: true,
  self_play_discovery_enabled: true,
  self_play_defender_enabled: false,
};

const SUITE_OPTIONS = [
  { id: "prompt_leak", label: "Prompt leak (LLM07)" },
  { id: "model_theft", label: "Model theft (LLM10)" },
  { id: "memory_poison", label: "Memory poisoning" },
  { id: "poisoning", label: "Training-data poisoning (LLM04)" },
];

const API_SCAN_TYPES: ScanType[] = ["endpoint", "provider", "local"];

interface Props {
  value: RedTeamOptions;
  onChange: (v: RedTeamOptions) => void;
  scanType?: ScanType;
  analysisMode?: "offline" | "cloud";
  compact?: boolean;
}

export function RedTeamOptionsPicker({
  value,
  onChange,
  scanType,
  analysisMode = "offline",
  compact,
}: Props) {
  const showSelfPlay = !scanType || API_SCAN_TYPES.includes(scanType);
  const toggleSuite = (id: string) => {
    const next = value.l0_suites.includes(id)
      ? value.l0_suites.filter((s) => s !== id)
      : [...value.l0_suites, id];
    onChange({ ...value, l0_suites: next });
  };

  return (
    <div className={compact ? "space-y-4" : "space-y-5"}>
      <div>
        <h3 className="text-sm font-medium text-ink-primary">Red-team engine</h3>
        {!compact && (
          <p className="mt-1 text-sm text-ink-muted">
            L0 adaptive attacks, OWASP suites, self-play red teaming, and attack discovery.
          </p>
        )}
      </div>

      <ToggleRow
        label="L0 attack generation"
        description="Generate 100+ mutated probe variants per attack goal"
        checked={value.l0_enabled}
        onChange={(l0_enabled) => onChange({ ...value, l0_enabled })}
      />

      {value.l0_enabled && (
        <div className="space-y-4 rounded-lg border border-surface-border bg-surface-overlay p-4">
          <Input
            label="Max variants per goal"
            type="number"
            min={1}
            max={500}
            value={String(value.max_variants_per_goal)}
            onChange={(e) =>
              onChange({
                ...value,
                max_variants_per_goal: Math.max(1, parseInt(e.target.value, 10) || 100),
              })
            }
            hint="Budget for L0 mutation expansion (default 100)"
          />

          <div>
            <div className="text-sm text-ink-muted">OWASP suites</div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {SUITE_OPTIONS.map((suite) => (
                <label
                  key={suite.id}
                  className="flex cursor-pointer items-center gap-2 rounded-lg border border-surface-border px-3 py-2 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={value.l0_suites.includes(suite.id)}
                    onChange={() => toggleSuite(suite.id)}
                    className="rounded border-surface-border"
                  />
                  <span className="text-ink-secondary">{suite.label}</span>
                </label>
              ))}
            </div>
          </div>

          {analysisMode === "cloud" && (
            <ToggleRow
              label="Cloud LLM mutations"
              description="LLM-generated attack wrappers in Cloud Enhanced mode"
              checked={value.cloud_mutations_enabled}
              onChange={(cloud_mutations_enabled) =>
                onChange({ ...value, cloud_mutations_enabled })
              }
            />
          )}
        </div>
      )}

      {showSelfPlay && (
        <>
          <ToggleRow
            label="Self-play red teaming"
            description="Attacker ↔ target loop with judge validation (Phase 3)"
            checked={value.self_play_enabled}
            onChange={(self_play_enabled) => onChange({ ...value, self_play_enabled })}
          />

          {value.self_play_enabled && (
            <div className="space-y-3 rounded-lg border border-surface-border bg-surface-overlay p-4">
              <Input
                label="Max rounds"
                type="number"
                min={1}
                max={100}
                value={String(value.self_play_max_rounds)}
                onChange={(e) =>
                  onChange({
                    ...value,
                    self_play_max_rounds: Math.max(1, parseInt(e.target.value, 10) || 20),
                  })
                }
              />
              <ToggleRow
                label="Stop on first success"
                description="End self-play when a vulnerability is confirmed"
                checked={value.self_play_stop_on_success}
                onChange={(self_play_stop_on_success) =>
                  onChange({ ...value, self_play_stop_on_success })
                }
              />
              <ToggleRow
                label="Attack discovery"
                description="Propose novel attack goals from target responses"
                checked={value.self_play_discovery_enabled}
                onChange={(self_play_discovery_enabled) =>
                  onChange({ ...value, self_play_discovery_enabled })
                }
              />
              {analysisMode === "cloud" && (
                <ToggleRow
                  label="Defender simulation"
                  description="Optional guardrail simulation during self-play"
                  checked={value.self_play_defender_enabled}
                  onChange={(self_play_defender_enabled) =>
                    onChange({ ...value, self_play_defender_enabled })
                  }
                />
              )}
              {analysisMode === "offline" && value.self_play_enabled && (
                <p className="text-xs text-ink-muted">
                  Offline mode uses deterministic L0 mutations. Enable Cloud enhanced analysis for
                  LLM attacker and defender agents.
                </p>
              )}
            </div>
          )}
        </>
      )}

      {scanType === "mcp" && (
        <p className="text-xs text-ink-muted">
          MCP scans include the expanded security suite (15+ probes). L0/self-play apply to API
          endpoint scans only.
        </p>
      )}
      {scanType === "rag" && (
        <p className="text-xs text-ink-muted">
          RAG scans include synthetic poisoning probes. Enable L0 suites above for endpoint-style
          prompt attacks when testing hybrid setups.
        </p>
      )}
    </div>
  );
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4">
      <div>
        <div className="text-sm font-medium text-ink-primary">{label}</div>
        <div className="mt-1 text-sm text-ink-muted">{description}</div>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors focus-ring ${
          checked ? "bg-brand-600" : "bg-surface-border-strong"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-5" : ""
          }`}
        />
      </button>
    </label>
  );
}

export function redTeamToScanBody(options: RedTeamOptions): Record<string, unknown> {
  return {
    l0_enabled: options.l0_enabled,
    max_variants_per_goal: options.max_variants_per_goal,
    l0_suites: options.l0_suites,
    cloud_mutations_enabled: options.cloud_mutations_enabled,
    self_play_enabled: options.self_play_enabled,
    self_play_max_rounds: options.self_play_max_rounds,
    self_play_stop_on_success: options.self_play_stop_on_success,
    self_play_discovery_enabled: options.self_play_discovery_enabled,
    self_play_defender_enabled: options.self_play_defender_enabled,
  };
}

export function settingsToRedTeam(settings: Partial<RedTeamOptions>): RedTeamOptions {
  return {
    ...DEFAULT_REDTEAM,
    ...settings,
    l0_suites: settings.l0_suites ?? DEFAULT_REDTEAM.l0_suites,
  };
}
