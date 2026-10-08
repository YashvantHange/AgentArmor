import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { BlackboardPanel } from "../components/BlackboardPanel";
import { PageHeader } from "../components/layout/PageHeader";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader } from "../components/ui/Card";
import { useSwarmEvents } from "../hooks/useSwarmEvents";
import { useSwarmProgress } from "../hooks/useSwarmProgress";

/**
 * Live swarm progress.
 *
 * The blackboard panel is the centrepiece: it is where a user sees one agent's
 * discovery become available to the others while the run is still going.
 */

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface-overlay px-3 py-2">
      <p className="text-[11px] uppercase tracking-wide text-ink-muted">{label}</p>
      <p className="mt-0.5 font-mono text-sm text-ink-primary">{value}</p>
    </div>
  );
}

export default function SwarmProgress() {
  const { scanId } = useParams<{ scanId: string }>();
  const state = useSwarmEvents(scanId ?? null);
  const progress = useSwarmProgress(state);
  const [cancelling, setCancelling] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function cancel() {
    if (!scanId) return;
    setCancelling(true);
    try {
      const result = await api.cancelSwarm(scanId);
      setNotice(
        result.cancelled
          ? "Cancelling. Results found so far are kept."
          : `Nothing running to cancel (status: ${result.status}).`
      );
    } catch (err) {
      setNotice((err as Error).message);
    } finally {
      setCancelling(false);
    }
  }

  const finished = progress.finished;
  const cancelled = progress.terminalStatus === "cancelled";

  return (
    <div className="space-y-6">
      <PageHeader
        title={state.goalName || "Swarm"}
        subtitle={progress.coverageLine || "Starting agents…"}
        backTo="/swarm"
        actions={
          finished ? undefined : (
            <Button variant="danger" onClick={cancel} disabled={cancelling}>
              {cancelling ? "Cancelling…" : "Cancel swarm"}
            </Button>
          )
        }
      />

      {state.error && !finished && <Alert tone="warning">{state.error}</Alert>}
      {notice && <Alert tone="info">{notice}</Alert>}
      {cancelled && (
        <Alert tone="warning">
          Swarm cancelled. The trace, shared facts and any findings up to that point were saved.
        </Alert>
      )}
      {progress.degraded && !finished && (
        <Alert tone="warning">
          Budget warning threshold reached. Remaining agents may be skipped.
        </Alert>
      )}

      <Card className="p-5">
        <div className="flex items-baseline justify-between">
          <h3 className="text-sm font-semibold text-ink-primary">
            {finished ? (cancelled ? "Cancelled" : "Complete") : progress.currentActivity}
          </h3>
          <span className="font-mono text-xs text-ink-muted">
            {progress.settled} / {progress.total}
          </span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-overlay">
          <div
            className="h-full rounded-full bg-brand-500 transition-[width] duration-500"
            style={{ width: `${finished ? 100 : progress.percent}%` }}
            role="progressbar"
            aria-valuenow={finished ? 100 : progress.percent}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Agents" value={progress.total} />
          <Stat label="Running" value={progress.running} />
          <Stat label="Done" value={progress.completed} />
          {/* A skip means another agent already broke that node, so it is shown
              separately from a failure rather than lumped in with one. */}
          <Stat label="Skipped" value={progress.skipped} />
          <Stat label="Failed" value={progress.failed} />
          <Stat label="Findings" value={progress.findings} />
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Stat label="Tokens" value={progress.tokensUsed.toLocaleString()} />
          <Stat label="Agent cost" value={`$${progress.memberCostUsd.toFixed(4)}`} />
          <Stat label="Analysis cost" value={`$${progress.enrichmentCostUsd.toFixed(4)}`} />
        </div>
      </Card>

      <BlackboardPanel facts={progress.topFacts} quarantined={progress.quarantinedFacts} />

      <Card className="p-5">
        <CardHeader title="Agents" subtitle="Each agent, its attack node and the persona it used." />
        {state.agents.size === 0 ? (
          <p className="py-4 text-xs text-ink-muted">Waiting for the roster…</p>
        ) : (
          <ul className="mt-2 divide-y divide-surface-border">
            {Array.from(state.agents.values()).map((row) => (
              <li key={row.member_id} className="flex flex-wrap items-center gap-2 py-2">
                <span className="w-16 font-mono text-xs text-ink-secondary">{row.member_id}</span>
                <span className="min-w-0 flex-1 truncate text-xs text-ink-primary">
                  {row.node_id}
                </span>
                <span className="text-[11px] text-ink-muted">{row.persona_id}</span>
                {row.vulnerable && <Badge tone="critical">vulnerable</Badge>}
                {row.status === "skipped" && <Badge tone="info">skipped</Badge>}
                {row.status === "failed" && <Badge tone="medium">failed</Badge>}
                {row.status === "running" && <Badge tone="brand">running</Badge>}
                {row.status === "done" && !row.vulnerable && <Badge tone="low">done</Badge>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {finished && (
        <div className="flex flex-wrap gap-3">
          <Link to={`/findings/${scanId}`}>
            <Button>Review findings</Button>
          </Link>
          <Link to={`/reports/${scanId}`}>
            <Button variant="secondary">Reports</Button>
          </Link>
        </div>
      )}
    </div>
  );
}
