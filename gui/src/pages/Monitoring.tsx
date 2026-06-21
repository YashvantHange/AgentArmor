import { FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { FieldGroup, Input } from "../components/ui/Input";
import { LoadingBlock } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";

interface Schedule {
  id: string;
  name: string;
  cron: string;
  enabled: boolean;
  last_finding_count: number;
  drift_detected: boolean;
  last_scan_id?: string | null;
}

export default function Monitoring() {
  const [schedules, setSchedules] = useState<Schedule[] | null>(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [exportPath, setExportPath] = useState("");

  const load = () => {
    api
      .listMonitorSchedules()
      .then(setSchedules)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load schedules"));
  };

  useEffect(() => {
    load();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.createMonitorSchedule({
        name,
        target_type: "endpoint",
        target_config: { url },
        cron: "daily",
      });
      setName("");
      setUrl("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create schedule");
    }
  }

  async function runNow(id: string) {
    try {
      await api.runMonitorSchedule(id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
    }
  }

  async function exportDataset() {
    try {
      const res = await api.exportDataset({ anonymize: true });
      setExportPath(res.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  }

  if (schedules === null) {
    return (
      <div>
        <PageHeader title="Monitoring" backTo="/" />
        <LoadingBlock label="Loading schedules…" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-8">
      <PageHeader
        title="Continuous monitoring"
        subtitle="Schedule rescans and detect drift when new findings appear."
        backTo="/"
      />

      {error && (
        <Alert tone="error">{error}</Alert>
      )}

      <Card className="p-6">
        <h2 className="text-sm font-semibold text-ink-primary">New schedule</h2>
        <form onSubmit={onSubmit} className="mt-4">
          <FieldGroup>
            <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
            <Input
              label="Endpoint URL"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://api.example.com/v1/chat/completions"
              required
            />
          </FieldGroup>
          <div className="mt-4">
            <Button type="submit">Add daily schedule</Button>
          </div>
        </form>
      </Card>

      {schedules.length === 0 ? (
        <EmptyState title="No schedules" description="Add a target to run automated daily security rescans." />
      ) : (
        <ul className="space-y-2">
          {schedules.map((s) => (
            <li key={s.id}>
              <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-ink-primary">{s.name}</span>
                    <Badge tone="default">{s.cron}</Badge>
                    {s.drift_detected && <Badge tone="high">Drift</Badge>}
                  </div>
                  <p className="mt-1 text-xs text-ink-muted">
                    Last run: {s.last_finding_count} findings
                    {s.last_scan_id ? ` · scan ${s.last_scan_id.slice(0, 8)}…` : ""}
                  </p>
                </div>
                <Button variant="secondary" size="sm" onClick={() => runNow(s.id)}>
                  Run now
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <Card className="p-6">
        <h2 className="text-sm font-semibold text-ink-primary">Research dataset export</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Export anonymized findings as JSONL for papers and model training datasets.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={exportDataset}>
            Export JSONL
          </Button>
          {exportPath && (
            <span className="font-mono text-xs text-ink-muted">{exportPath}</span>
          )}
        </div>
      </Card>
    </div>
  );
}
