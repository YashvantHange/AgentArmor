import { useEffect, useState } from "react";
import { api, Settings } from "../api/client";
import { AnalysisModePicker, AnalysisModeValue } from "../components/AnalysisModePicker";
import {
  DEFAULT_REDTEAM,
  RedTeamOptions,
  RedTeamOptionsPicker,
  settingsToRedTeam,
} from "../components/RedTeamOptionsPicker";
import { PageHeader } from "../components/layout/PageHeader";
import { Input } from "../components/ui/Input";
import { Card } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";
import { LoadingBlock } from "../components/ui/Spinner";
import { useTheme } from "../hooks/useTheme";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisModeValue>({ analysis_mode: "offline" });
  const [redTeam, setRedTeam] = useState<RedTeamOptions>(DEFAULT_REDTEAM);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setSettings(s);
        setAnalysis({
          analysis_mode: (s.analysis_mode as "offline" | "cloud") || "offline",
          analysis_provider: s.analysis_provider,
          analysis_model: s.analysis_model,
          analysis_api_key: s.analysis_api_key,
        });
        setRedTeam(settingsToRedTeam(s));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load settings"));
  }, []);

  async function save(updates: Partial<Settings>) {
    try {
      const next = await api.updateSettings(updates);
      setSettings(next);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    }
  }

  if (!settings) {
    return (
      <div className="max-w-xl">
        <PageHeader title="Settings" backTo="/" />
        {error ? <Alert tone="error">{error}</Alert> : <LoadingBlock label="Loading settings…" />}
      </div>
    );
  }

  return (
    <div className="max-w-xl">
      <PageHeader
        title="Settings"
        subtitle="Configure runtime paths, portable storage, and optional detection features."
        backTo="/"
      />

      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {saved && (
        <div className="mb-4">
          <Alert tone="info">Settings saved successfully.</Alert>
        </div>
      )}

      <Card className="mb-4 divide-y divide-surface-border">
        <div className="p-5">
          <AnalysisModePicker
            compact
            value={analysis}
            onChange={(v) => {
              setAnalysis(v);
              save({
                analysis_mode: v.analysis_mode,
                analysis_provider: v.analysis_provider,
                analysis_model: v.analysis_model,
                analysis_api_key: v.analysis_api_key,
              });
            }}
          />
        </div>
      </Card>

      <Card className="mb-4 divide-y divide-surface-border">
        <div className="p-5">
          <RedTeamOptionsPicker
            compact
            value={redTeam}
            onChange={(v) => {
              setRedTeam(v);
              save({
                l0_enabled: v.l0_enabled,
                max_variants_per_goal: v.max_variants_per_goal,
                l0_suites: v.l0_suites,
                cloud_mutations_enabled: v.cloud_mutations_enabled,
                self_play_enabled: v.self_play_enabled,
                self_play_max_rounds: v.self_play_max_rounds,
                self_play_stop_on_success: v.self_play_stop_on_success,
                self_play_discovery_enabled: v.self_play_discovery_enabled,
                self_play_defender_enabled: v.self_play_defender_enabled,
              });
            }}
            analysisMode={analysis.analysis_mode}
          />
        </div>
      </Card>

      <Card className="mb-4 divide-y divide-surface-border">
        <div className="p-5">
          <div className="text-sm font-medium text-ink-primary">Appearance</div>
          <p className="mt-1 text-sm text-ink-muted">Choose light or dark interface theme.</p>
          <div className="mt-4 flex gap-2">
            <ThemeOption
              label="Light"
              description="Default"
              active={theme === "light"}
              onClick={() => setTheme("light")}
            />
            <ThemeOption
              label="Dark"
              description="Low light"
              active={theme === "dark"}
              onClick={() => setTheme("dark")}
            />
          </div>
        </div>
      </Card>

      <Card className="divide-y divide-surface-border">
        <ToggleRow
          label="Portable mode"
          description="Store database and reports beside the executable in ./data/"
          checked={settings.portable_mode}
          onChange={(v) => save({ portable_mode: v })}
        />
        <ToggleRow
          label="L5 LLM judge"
          description="Enable network-based adjudication layer (requires provider API key)"
          checked={settings.l5_enabled}
          onChange={(v) => save({ l5_enabled: v })}
        />
        <div className="p-5 space-y-4">
          <Input
            label="Model directory"
            key={`model-${settings.model_dir}`}
            defaultValue={settings.model_dir}
            onBlur={(e) => {
              if (e.target.value !== settings.model_dir) save({ model_dir: e.target.value });
            }}
          />
          <Input
            label="Reports output directory"
            key={`out-${settings.output_dir}`}
            defaultValue={settings.output_dir}
            onBlur={(e) => {
              if (e.target.value !== settings.output_dir) save({ output_dir: e.target.value });
            }}
          />
        </div>
      </Card>
    </div>
  );
}

function ThemeOption({
  label,
  description,
  active,
  onClick,
}: {
  label: string;
  description: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 rounded-lg border px-4 py-3 text-left transition-colors focus-ring ${
        active
          ? "border-brand-500 bg-brand-500/10 text-brand-600 dark:text-brand-400"
          : "border-surface-border bg-surface-overlay text-ink-secondary hover:border-surface-border-strong"
      }`}
    >
      <div className="text-sm font-medium">{label}</div>
      <div className="text-xs text-ink-muted">{description}</div>
    </button>
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
    <label className="flex cursor-pointer items-start justify-between gap-4 p-5">
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
