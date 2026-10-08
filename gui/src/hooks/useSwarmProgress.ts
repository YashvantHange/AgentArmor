import { SwarmFact } from "../api/client";
import { AgentRow, SwarmState } from "./useSwarmEvents";

/**
 * Derived swarm progress.
 *
 * A pure function of SwarmState with no EventSource of its own, which is what makes
 * it testable without mocking anything.
 */

export interface SwarmProgressState {
  total: number;
  pending: number;
  running: number;
  completed: number;
  failed: number;
  skipped: number;
  settled: number;
  vulnerable: number;
  findings: number;
  percent: number;
  byPersona: Record<string, number>;
  byStatus: Record<AgentRow["status"], number>;
  topFacts: SwarmFact[];
  quarantinedFacts: number;
  tokensUsed: number;
  memberCostUsd: number;
  enrichmentCostUsd: number;
  totalCostUsd: number;
  degraded: boolean;
  finished: boolean;
  terminalStatus: string | null;
  coverageLine: string;
  currentActivity: string;
}

/** Corroboration-weighted confidence, matching the backend's brief ranking. */
function factScore(fact: SwarmFact): number {
  const weight = fact.provenance === "verified" ? 2 : fact.provenance === "inferred" ? 1 : 0;
  return weight * 100 + fact.confidence * Math.log1p(fact.hits) * 10;
}

export function coverageLine(state: SwarmState): string {
  const coverage = state.coverage;
  if (!coverage) return "";
  // Never an agent count on its own: a large roster against a shallow graph is
  // mostly persona and strategy variation, and the UI has to say so.
  return (
    `Agents ${coverage.agents} · Attack paths ${coverage.attack_paths} · ` +
    `Personas ${coverage.personas} · Strategies ${coverage.strategies} · ` +
    `Concurrency ${coverage.concurrency}`
  );
}

export function useSwarmProgress(state: SwarmState): SwarmProgressState {
  const rows = Array.from(state.agents.values());

  const byStatus: Record<AgentRow["status"], number> = {
    pending: 0,
    running: 0,
    done: 0,
    failed: 0,
    skipped: 0,
  };
  const byPersona: Record<string, number> = {};
  let vulnerable = 0;

  rows.forEach((row) => {
    byStatus[row.status] = (byStatus[row.status] ?? 0) + 1;
    if (row.persona_id) byPersona[row.persona_id] = (byPersona[row.persona_id] ?? 0) + 1;
    if (row.vulnerable) vulnerable += 1;
  });

  // A skip is progress, not a failure: it means another member already broke that
  // node, so counting it as settled is what makes the bar reach 100%.
  const settled = byStatus.done + byStatus.failed + byStatus.skipped;
  const total = Math.max(state.totalMembers, rows.length);
  const percent = total > 0 ? Math.min(100, Math.round((settled / total) * 100)) : 0;

  const visibleFacts = state.facts.filter((fact) => !fact.quarantined);
  const topFacts = [...visibleFacts].sort((a, b) => factScore(b) - factScore(a));

  const running = rows.filter((row) => row.status === "running");
  let currentActivity = "";
  if (state.done) {
    currentActivity = state.terminalStatus === "cancelled" ? "Cancelled" : "Complete";
  } else if (running.length > 0) {
    const sample = running[0];
    currentActivity =
      running.length === 1
        ? `${sample.member_id} on ${sample.node_id}`
        : `${running.length} agents running`;
  } else if (total > 0) {
    currentActivity = "Starting agents";
  }

  return {
    total,
    pending: byStatus.pending,
    running: byStatus.running,
    completed: byStatus.done,
    failed: byStatus.failed,
    skipped: byStatus.skipped,
    settled,
    vulnerable,
    findings: state.findings,
    percent,
    byPersona,
    byStatus,
    topFacts,
    quarantinedFacts: state.facts.length - visibleFacts.length,
    tokensUsed: state.tokensUsed,
    memberCostUsd: state.memberCostUsd,
    enrichmentCostUsd: state.enrichmentCostUsd,
    totalCostUsd: state.totalCostUsd,
    degraded: state.degraded,
    finished: state.done,
    terminalStatus: state.terminalStatus,
    coverageLine: coverageLine(state),
    currentActivity,
  };
}
