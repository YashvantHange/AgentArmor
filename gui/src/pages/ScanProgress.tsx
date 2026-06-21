import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useScanEvents } from "../hooks/useScanEvents";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { Card } from "../components/ui/Card";
import { CheckCircleIcon } from "../components/icons";

function formatEventLabel(event: string) {
  return event.replace(/\./g, " · ");
}

export default function ScanProgress() {
  const { scanId } = useParams<{ scanId: string }>();
  const { events, done, error } = useScanEvents(scanId ?? null);
  const [findingCount, setFindingCount] = useState(0);
  const [status, setStatus] = useState<string>("running");
  const [selfPlay, setSelfPlay] = useState<{ successful?: boolean; rounds?: number } | null>(null);

  useEffect(() => {
    if (!scanId || !done) return;
    api.getScan(scanId).then((s) => {
      setFindingCount(s.finding_count);
      setStatus(s.status);
      setSelfPlay(s.metadata?.self_play ?? null);
    });
  }, [scanId, done]);

  const probeStats = useMemo(() => {
    const started = events.filter((e) => e.event === "probe.started").length;
    const completed = events.filter((e) => e.event === "probe.completed").length;
    const total =
      (events.find((e) => e.event === "scan.started")?.data.probe_count as number | undefined) ??
      started;
    return { started, completed, total };
  }, [events]);

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Scan in progress"
        subtitle="Live probe execution stream from the AgentArmor orchestrator."
        backTo="/"
        actions={
          done ? (
            <Badge tone="brand">
              <CheckCircleIcon className="mr-1 inline h-3 w-3" />
              Completed
            </Badge>
          ) : (
            <Badge tone="default">Running</Badge>
          )
        }
      />

      <div className="mb-4 rounded-lg border border-surface-border bg-surface-overlay px-4 py-3 font-mono text-xs text-ink-muted">
        Scan ID · {scanId}
      </div>

      {!done && probeStats.total > 0 && (
        <div className="mb-4 grid grid-cols-3 gap-3">
          {[
            ["Probes", probeStats.total],
            ["Started", probeStats.started],
            ["Completed", probeStats.completed],
          ].map(([label, value]) => (
            <Card key={label} className="px-4 py-3 text-center">
              <div className="text-lg font-semibold text-ink-primary">{value}</div>
              <div className="text-xs text-ink-muted">{label}</div>
            </Card>
          ))}
        </div>
      )}

      {error && (
        <div className="mb-4">
          <Alert tone="warning">{error}</Alert>
        </div>
      )}

      <Card className="max-h-[28rem] overflow-y-auto p-2">
        {events.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-ink-muted">Waiting for orchestrator events…</div>
        ) : (
          <ul className="divide-y divide-surface-border">
            {events.map((ev, i) => (
              <li key={`${ev.event}-${i}`} className="px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-medium uppercase tracking-wide text-brand-400">
                    {formatEventLabel(ev.event)}
                  </span>
                  <span className="font-mono text-[11px] text-ink-muted">
                    {typeof ev.data.probe_id === "string" ? ev.data.probe_id : ""}
                  </span>
                </div>
                {ev.event === "probe.completed" && (
                  <p className="mt-1 text-xs text-ink-muted">
                    Decision: {String(ev.data.decision ?? "—")} · Severity: {String(ev.data.severity ?? "—")}
                    {ev.data.error ? ` · Error: ${String(ev.data.error)}` : ""}
                    {ev.data.profile ? ` · Profile: ${String(ev.data.profile)}` : ""}
                  </p>
                )}
                {ev.event === "scan.completed" && (
                  <p className="mt-1 text-xs text-ink-muted">
                    {String(ev.data.finding_count ?? 0)} finding(s) · status {String(ev.data.status ?? status)}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {done && selfPlay && (
        <div className="mb-4">
          <Alert tone={selfPlay.successful ? "info" : "warning"}>
            Self-play red teaming: {selfPlay.rounds ?? 0} round(s)
            {selfPlay.successful ? " — vulnerability discovered" : " — no confirmed exploit chain"}
          </Alert>
        </div>
      )}

      {done && (
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to={`/findings/${scanId}`}>
            <Button>Review {findingCount} finding{findingCount === 1 ? "" : "s"}</Button>
          </Link>
          <Link to={`/reports/${scanId}`}>
            <Button variant="secondary">Export reports</Button>
          </Link>
        </div>
      )}
    </div>
  );
}
