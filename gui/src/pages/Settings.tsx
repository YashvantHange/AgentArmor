import { useEffect, useState } from "react";
import { api, Settings } from "../api/client";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getSettings().then(setSettings);
  }, []);

  async function save(updates: Partial<Settings>) {
    const next = await api.updateSettings(updates);
    setSettings(next);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (!settings) return <p className="text-slate-400">Loading settings…</p>;

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>
      <div className="space-y-6">
        <Toggle
          label="Portable mode"
          desc="Store data in ./data/ next to executable"
          checked={settings.portable_mode}
          onChange={(v) => save({ portable_mode: v })}
        />
        <Toggle
          label="L5 LLM Judge"
          desc="Enable network-based judge (requires API key)"
          checked={settings.l5_enabled}
          onChange={(v) => save({ l5_enabled: v })}
        />
        <label className="block">
          <span className="text-sm text-slate-400">Model directory</span>
          <input
            defaultValue={settings.model_dir}
            onBlur={(e) => save({ model_dir: e.target.value })}
            className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600"
          />
        </label>
        <label className="block">
          <span className="text-sm text-slate-400">Reports output directory</span>
          <input
            defaultValue={settings.output_dir}
            onBlur={(e) => save({ output_dir: e.target.value })}
            className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600"
          />
        </label>
      </div>
      {saved && <p className="text-green-400 mt-4 text-sm">Settings saved.</p>}
    </div>
  );
}

function Toggle({
  label,
  desc,
  checked,
  onChange,
}: {
  label: string;
  desc: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-3 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1"
      />
      <div>
        <div className="font-medium">{label}</div>
        <div className="text-sm text-slate-400">{desc}</div>
      </div>
    </label>
  );
}
