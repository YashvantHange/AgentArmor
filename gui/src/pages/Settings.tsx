import { useEffect, useState } from "react";
import { api, Settings } from "../api/client";
import { PageHeader } from "../components/layout/PageHeader";
import { Input } from "../components/ui/Input";
import { Card } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";
import { LoadingBlock } from "../components/ui/Spinner";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api
      .getSettings()
      .then(setSettings)
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
