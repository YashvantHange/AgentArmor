import { useEffect, useReducer, useRef } from "react";
import { eventsUrl, SwarmCoverage, SwarmFact, SwarmMemberRow } from "../api/client";

/**
 * Swarm event stream.
 *
 * A sibling of useScanEvents rather than an extension of it. That hook keeps every
 * event in one array and re-serialises the whole array to sessionStorage on every
 * append, which is fine at ~30 events and quadratic at swarm volume. It also
 * reduces the stream to a single "latest wins" activity, which cannot describe many
 * agents running at once.
 *
 * Here agent rows are updated in place in a Map keyed by member id, so cost is O(1)
 * per event and memory is bounded by the roster rather than by the event count. The
 * raw log is a ring buffer, and persistence is debounced and stores the derived
 * snapshot instead of the events.
 */

const NAMED_EVENTS = [
  "scan.started",
  "scan.completed",
  "swarm.plan",
  "swarm.roster",
  "swarm.progress",
  "swarm.completed",
  "agent.started",
  "agent.completed",
  "agent.failed",
  "agent.skipped",
  "blackboard.fact",
];

const LOG_LIMIT = 200;
const MAX_FACTS = 200;
const PERSIST_DEBOUNCE_MS = 1000;

export type AgentStatus = "pending" | "running" | "done" | "failed" | "skipped";

export interface AgentRow {
  member_id: string;
  node_id: string;
  path_id: string;
  persona_id: string;
  strategy: string;
  wave: number;
  status: AgentStatus;
  vulnerable: boolean;
  decision: string;
  tokens: number;
  cost_usd: number;
  error: string | null;
}

export interface SwarmLogEntry {
  event: string;
  data: Record<string, unknown>;
}

export interface SwarmState {
  goalId: string;
  goalName: string;
  llmPlanned: boolean;
  coverage: SwarmCoverage | null;
  agents: Map<string, AgentRow>;
  facts: SwarmFact[];
  log: SwarmLogEntry[];
  totalMembers: number;
  findings: number;
  tokensUsed: number;
  memberCostUsd: number;
  enrichmentCostUsd: number;
  totalCostUsd: number;
  degraded: boolean;
  done: boolean;
  terminalStatus: string | null;
  error: string | null;
}

const initialState: SwarmState = {
  goalId: "",
  goalName: "",
  llmPlanned: false,
  coverage: null,
  agents: new Map(),
  facts: [],
  log: [],
  totalMembers: 0,
  findings: 0,
  tokensUsed: 0,
  memberCostUsd: 0,
  enrichmentCostUsd: 0,
  totalCostUsd: 0,
  degraded: false,
  done: false,
  terminalStatus: null,
  error: null,
};

type Action =
  | { type: "event"; event: string; data: Record<string, unknown> }
  | { type: "error"; message: string }
  | { type: "reset"; state?: SwarmState };

function num(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function rowFrom(data: Record<string, unknown>, status: AgentStatus): AgentRow {
  return {
    member_id: str(data.member_id),
    node_id: str(data.node_id),
    path_id: str(data.path_id),
    persona_id: str(data.persona_id),
    strategy: str(data.strategy),
    wave: num(data.wave),
    status,
    vulnerable: data.vulnerable === true,
    decision: str(data.decision),
    tokens: num(data.tokens),
    cost_usd: num(data.cost_usd),
    error: typeof data.error === "string" ? data.error : null,
  };
}

/** Update one agent in place so a hundred-row grid re-renders a single tile. */
function upsert(
  agents: Map<string, AgentRow>,
  memberId: string,
  patch: Partial<AgentRow>,
  fallbackStatus: AgentStatus
): Map<string, AgentRow> {
  if (!memberId) return agents;
  const next = new Map(agents);
  const existing = next.get(memberId);
  if (existing) {
    next.set(memberId, { ...existing, ...patch });
  } else {
    next.set(memberId, {
      ...rowFrom({ member_id: memberId }, fallbackStatus),
      ...patch,
      member_id: memberId,
    });
  }
  return next;
}

function reducer(state: SwarmState, action: Action): SwarmState {
  if (action.type === "reset") {
    return action.state ?? { ...initialState, agents: new Map(), facts: [], log: [] };
  }
  if (action.type === "error") {
    return { ...state, error: action.message };
  }

  const { event, data } = action;
  const log = [...state.log, { event, data }].slice(-LOG_LIMIT);
  const next: SwarmState = { ...state, log };

  switch (event) {
    case "scan.started": {
      next.totalMembers = num(data.probe_count, state.totalMembers);
      next.goalId = str(data.goal_id, state.goalId);
      if (data.coverage) next.coverage = data.coverage as SwarmCoverage;
      return next;
    }
    case "swarm.plan": {
      next.goalId = str(data.goal_id, state.goalId);
      next.goalName = str(data.goal_name, state.goalName);
      next.llmPlanned = data.llm_planned === true;
      if (data.coverage) next.coverage = data.coverage as SwarmCoverage;
      return next;
    }
    case "swarm.roster": {
      // One batched event, so the whole roster is seeded as pending here rather
      // than arriving as a hundred separate spawn events.
      const members = Array.isArray(data.members) ? (data.members as SwarmMemberRow[]) : [];
      const agents = new Map<string, AgentRow>();
      members.forEach((member) => {
        agents.set(member.member_id, {
          member_id: member.member_id,
          node_id: member.node_id,
          path_id: member.path_id,
          persona_id: member.persona_id,
          strategy: member.strategy,
          wave: member.wave ?? 0,
          status: "pending",
          vulnerable: false,
          decision: "",
          tokens: 0,
          cost_usd: 0,
          error: null,
        });
      });
      next.agents = agents;
      next.totalMembers = Math.max(state.totalMembers, members.length);
      return next;
    }
    case "agent.started":
      next.agents = upsert(state.agents, str(data.member_id), rowFrom(data, "running"), "running");
      return next;
    case "agent.completed":
      next.agents = upsert(state.agents, str(data.member_id), rowFrom(data, "done"), "done");
      return next;
    case "agent.failed":
      next.agents = upsert(
        state.agents,
        str(data.member_id),
        { status: "failed", error: str(data.error) || "failed" },
        "failed"
      );
      return next;
    case "agent.skipped":
      next.agents = upsert(
        state.agents,
        str(data.member_id),
        { status: "skipped", error: str(data.reason) || "skipped" },
        "skipped"
      );
      return next;
    case "blackboard.fact": {
      const fact = data as unknown as SwarmFact;
      if (!fact.fact_id || state.facts.some((f) => f.fact_id === fact.fact_id)) return next;
      next.facts = [...state.facts, fact].slice(-MAX_FACTS);
      return next;
    }
    case "swarm.progress": {
      next.findings = num(data.findings, state.findings);
      next.tokensUsed = num(data.tokens_used, state.tokensUsed);
      next.memberCostUsd = num(data.member_cost_usd, state.memberCostUsd);
      next.enrichmentCostUsd = num(data.enrichment_cost_usd, state.enrichmentCostUsd);
      next.totalCostUsd = num(data.total_cost_usd, state.totalCostUsd);
      next.degraded = data.degraded === true;
      next.totalMembers = num(data.total, state.totalMembers);
      return next;
    }
    case "swarm.completed": {
      next.findings = num(data.findings, state.findings);
      next.memberCostUsd = num(data.member_cost_usd, state.memberCostUsd);
      next.enrichmentCostUsd = num(data.enrichment_cost_usd, state.enrichmentCostUsd);
      next.totalCostUsd = num(data.total_cost_usd, state.totalCostUsd);
      next.tokensUsed = num(data.tokens_used, state.tokensUsed);
      if (data.coverage) next.coverage = data.coverage as SwarmCoverage;
      return next;
    }
    case "scan.completed": {
      next.done = true;
      next.terminalStatus = str(data.status, "completed");
      next.findings = num(data.finding_count, state.findings);
      return next;
    }
    default:
      return next;
  }
}

export function storageKey(scanId: string): string {
  return `agentarmor-swarm-progress:${scanId}`;
}

interface Snapshot {
  agents: AgentRow[];
  facts: SwarmFact[];
  goalId: string;
  goalName: string;
  coverage: SwarmCoverage | null;
  totalMembers: number;
  findings: number;
  totalCostUsd: number;
  tokensUsed: number;
  done: boolean;
  terminalStatus: string | null;
}

function toSnapshot(state: SwarmState): Snapshot {
  return {
    agents: Array.from(state.agents.values()),
    facts: state.facts,
    goalId: state.goalId,
    goalName: state.goalName,
    coverage: state.coverage,
    totalMembers: state.totalMembers,
    findings: state.findings,
    totalCostUsd: state.totalCostUsd,
    tokensUsed: state.tokensUsed,
    done: state.done,
    terminalStatus: state.terminalStatus,
  };
}

function fromSnapshot(snapshot: Snapshot): SwarmState {
  const agents = new Map<string, AgentRow>();
  (snapshot.agents || []).forEach((row) => agents.set(row.member_id, row));
  return {
    ...initialState,
    ...snapshot,
    agents,
    facts: snapshot.facts || [],
    log: [],
  };
}

export function useSwarmEvents(scanId: string | null): SwarmState {
  const [state, dispatch] = useReducer(reducer, initialState);
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!scanId) return;

    let cached: SwarmState | undefined;
    try {
      const raw = sessionStorage.getItem(storageKey(scanId));
      if (raw) cached = fromSnapshot(JSON.parse(raw) as Snapshot);
    } catch {
      cached = undefined;
    }
    dispatch({ type: "reset", state: cached });

    const source = new EventSource(eventsUrl(scanId));
    let closed = false;

    const handle = (name: string, raw: string) => {
      try {
        dispatch({ type: "event", event: name, data: JSON.parse(raw) });
      } catch {
        dispatch({ type: "event", event: name, data: { raw } });
      }
      if (name === "scan.completed") {
        closed = true;
        source.close();
      }
    };

    NAMED_EVENTS.forEach((name) => {
      source.addEventListener(name, (ev) => handle(name, (ev as MessageEvent).data));
    });

    source.onerror = () => {
      if (closed) return;
      dispatch({ type: "error", message: "Connection to swarm stream lost" });
      source.close();
    };

    return () => {
      closed = true;
      source.close();
    };
  }, [scanId]);

  // Debounced, and it stores the derived snapshot rather than the raw events, so a
  // long run cannot blow the storage quota.
  useEffect(() => {
    if (!scanId) return;
    if (persistTimer.current) clearTimeout(persistTimer.current);
    persistTimer.current = setTimeout(() => {
      try {
        sessionStorage.setItem(storageKey(scanId), JSON.stringify(toSnapshot(state)));
      } catch {
        /* quota exceeded is not worth failing a render over */
      }
    }, PERSIST_DEBOUNCE_MS);
    return () => {
      if (persistTimer.current) clearTimeout(persistTimer.current);
    };
  }, [scanId, state]);

  return state;
}

export const SWARM_NAMED_EVENTS = NAMED_EVENTS;
export const swarmReducer = reducer;
export const swarmInitialState = initialState;
