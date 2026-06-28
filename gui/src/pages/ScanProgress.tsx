import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, ScanSummary } from "../api/client";
import { useScanEvents } from "../hooks/useScanEvents";
import { useElapsedTimer } from "../hooks/useElapsedTimer";
import { useScanProgress } from "../hooks/useScanProgress";
import { PageHeader } from "../components/layout/PageHeader";
import { ReportDownloadMenu } from "../components/ReportDownloadMenu";
import { ScanProgressPanel } from "../components/ScanProgressPanel";
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
  const mountTimeMs = useRef(Date.now()).current;
  const { events, done, error } = useScanEvents(scanId ?? null);
  const [scan, setScan] = useState<ScanSummary | null>(null);
  const [pollError, setPollError] = useState("");
  const [pollingActive, setPollingActive] = useState(false);
  const [logOpen, setLogOpen] = useState(false);

  const status = scan?.status ?? "running";
  const findingCount = scan?.finding_count ?? 0;
  const selfPlay = scan?.metadata?.self_play ?? null;

  useEffect(() => {
    if (!scanId) return;

    let cancelled = false;

    const poll = async () => {
      try {
        const s = isWebScan ? await api.getWebScan(scanId) : await api.getScan(scanId);
        if (cancelled) return;
        setScan(s);
        setPollError("");
        if (TERMINAL_STATUSES.has(s.status)) {
          setPollingActive(false);
        }
      } catch (err) {
        if (!cancelled) {
          setPollError(err instanceof Error ? err.message : "Failed to refresh scan status");
          if (error) setPollingActive(false);
        }
      }
    };

    void poll();
    const interval = window.setInterval(poll, 5000);
    setPollingActive(true);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [scanId, isWebScan, error]);

  useEffect(() => {
    if (!scanId || !done) return;
    const fetchScan = isWebScan ? api.getWebScan(scanId) : api.getScan(scanId);
    fetchScan.then(setScan).catch(() => undefined);
  }, [scanId, done, isWebScan]);

  const polledProbeTotal = useMemo(() => {
    if (typeof scan?.metadata?.probe_count_planned === "number") {
      return scan.metadata.probe_count_planned;
    }
    if (scan && scan.probe_count > 0) {
      return scan.probe_count;
    }
    return null;
  }, [scan]);

  const targetType = isWebScan
    ? "web"
    : typeof scan?.target?.type === "string"
      ? scan.target.type
      : undefined;

  const { elapsedMs } = useElapsedTimer(scan?.started_at, mountTimeMs);

  const progress = useScanProgress(events, {
    polledProbeTotal,
    targetType,
    elapsedMs,
  });

  const scanFinished = done || TERMINAL_STATUSES.has(status);
  const showStreamWarning = error && !scanFinished && !pollingActive;
  const showPollingNotice = error && pollingActive && !scanFinished;

  return (
    <div className="max-w-3xl">
      <PageHeader
        title={scanFinished ? "Scan complete" : "Scan in progress"}
        subtitle={
          scanFinished
            ? "Review findings and download reports below."
            : "Live progress from the AgentArmor orchestrator."
        }
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

      <ScanProgressPanel
        targetType={targetType}
        finished={scanFinished}
        startedAt={scan?.started_at}
        fallbackStartMs={mountTimeMs}
        progress={
          scanFinished && progress.total > 0
            ? { ...progress, completed: progress.total }
            : progress
        }
        findingCount={findingCount}
      />

      {showStreamWarning && (
        <div className="mb-4">
          <Alert tone="warning">{error}</Alert>
        </div>
      )}

      {showPollingNotice && (
        <div className="mb-4">
          <Alert tone="info">
            Live stream disconnected — tracking scan via status polling. Probes: {progress.completed}/
            {progress.total || "?"}
          </Alert>
        </div>
      )}

      {pollError && !scanFinished && (
        <div className="mb-4">
          <Alert tone="warning">{pollError}</Alert>
        </div>
      )}

      <div className="mb-4">
        <button
          type="button"
          className="text-xs font-medium text-ink-muted hover:text-ink-primary"
          onClick={() => setLogOpen((v) => !v)}
        >
          {logOpen ? "Hide technical log" : "Show technical log"}
        </button>
      </div>

      {logOpen && (
        <Card className="mb-6 max-h-[28rem] overflow-y-auto p-2">
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
      )}

      {scanFinished && selfPlay && (
        <div className="mb-4">
          <Alert tone={selfPlay.successful ? "info" : "warning"}>
            Self-play red teaming: {selfPlay.rounds ?? 0} round(s)
            {selfPlay.successful ? " — vulnerability discovered" : " — no confirmed exploit chain"}
          </Alert>
        </div>
      )}

      {scanFinished && scanId && (
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to={`/findings/${scanId}`}>
            <Button>Review {findingCount} finding{findingCount === 1 ? "" : "s"}</Button>
          </Link>
          <ReportDownloadMenu scanId={scanId} isWebScan={isWebScan} />
          <Link to={`/reports/${scanId}${isWebScan ? "?kind=web" : ""}`}>
            <Button variant="secondary">Manage exports</Button>
          </Link>
        </div>
      )}
    </div>
  );
}
