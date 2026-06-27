import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
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

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export default function ScanProgress() {
  const { scanId } = useParams<{ scanId: string }>();
  const [searchParams] = useSearchParams();
  const isWebScan = searchParams.get("kind") === "web";
  const { events, done, error } = useScanEvents(scanId ?? null);
  const [findingCount, setFindingCount] = useState(0);
  const [status, setStatus] = useState<string>("running");
  const [polledProbeCount, setPolledProbeCount] = useState<number | null>(null);
  const [polledProbeTotal, setPolledProbeTotal] = useState<number | null>(null);
  const [pollingActive, setPollingActive] = useState(false);
  const [selfPlay, setSelfPlay] = useState<{ successful?: boolean; rounds?: number } | null>(null);

  useEffect(() => {
    if (!scanId || !done) return;
    const fetchScan = isWebScan ? api.getWebScan(scanId) : api.getScan(scanId);
    fetchScan.then((s) => {
      setFindingCount(s.finding_count);
      setStatus(s.status);
      setSelfPlay(s.metadata?.self_play ?? null);
    });
  }, [scanId, done, isWebScan]);

  useEffect(() => {
    if (!scanId || done || !error) return;

    let cancelled = false;
    setPollingActive(true);

    const poll = async () => {
      try {
        const s = isWebScan ? await api.getWebScan(scanId) : await api.getScan(scanId);
        if (cancelled) return;
        setStatus(s.status);
        setFindingCount(s.finding_count);
        setPolledProbeCount(s.probe_count);
        const planned = s.metadata?.probe_count_planned;
        if (typeof planned === "number") {
          setPolledProbeTotal(planned);
        }
        if (TERMINAL_STATUSES.has(s.status)) {
          setPollingActive(false);
          setSelfPlay(s.metadata?.self_play ?? null);
        }
      } catch {
        if (!cancelled) setPollingActive(false);
      }
    };

    void poll();
    const interval = window.setInterval(poll, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [scanId, done, error, isWebScan]);

  const probeStats = useMemo(() => {
    const started = events.filter((e) => e.event === "probe.started").length;
    const completed = events.filter((e) => e.event === "probe.completed").length;
    const totalFromEvents =
      (events.find((e) => e.event === "scan.started" && (e.data.probe_count as number) > 0)?.data
        .probe_count as number | undefined) ??
      (events.find((e) => e.event === "planning.completed")?.data.probe_count as number | undefined) ??
      started;
    const total = polledProbeTotal ?? totalFromEvents;
    const completedCount = polledProbeCount ?? completed;
    return { started, completed: completedCount, total };
  }, [events, polledProbeCount, polledProbeTotal]);

  const scanFinished = done || TERMINAL_STATUSES.has(status);
  const showStreamWarning = error && !scanFinished && !pollingActive;
  const showPollingNotice = error && pollingActive && !scanFinished;

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Scan in progress"
        subtitle="Live probe execution stream from the AgentArmor orchestrator."
        backTo="/"
        actions={
          scanFinished ? (
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

      {!scanFinished && probeStats.total > 0 && (
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

      {showStreamWarning && (
        <div className="mb-4">
          <Alert tone="warning">{error}</Alert>
        </div>
      )}

      {showPollingNotice && (
        <div className="mb-4">
          <Alert tone="info">
            Live stream disconnected — tracking scan via status polling. Probes: {probeStats.completed}/
            {probeStats.total || "?"}
          </Alert>
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
                {ev.event === "discovery.completed" && (
                  <p className="mt-1 text-xs text-ink-muted">
                    Widget {ev.data.widget_found ? "found" : "not found"}
                    {ev.data.framework ? ` · ${String(ev.data.framework)}` : ""}
                    {typeof ev.data.widget_confidence === "number"
                      ? ` · ${((ev.data.widget_confidence as number) * 100).toFixed(0)}%`
                      : ""}
                  </p>
                )}
                {ev.event === "planning.completed" && (
                  <p className="mt-1 text-xs text-ink-muted">
                    {String(ev.data.probe_count ?? 0)} probe(s) planned
                  </p>
                )}
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

      {scanFinished && selfPlay && (
        <div className="mb-4">
          <Alert tone={selfPlay.successful ? "info" : "warning"}>
            Self-play red teaming: {selfPlay.rounds ?? 0} round(s)
            {selfPlay.successful ? " — vulnerability discovered" : " — no confirmed exploit chain"}
          </Alert>
        </div>
      )}

      {scanFinished && (
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
