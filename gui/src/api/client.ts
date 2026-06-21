const base = import.meta.env.VITE_API_URL || "http://127.0.0.1:8787";

export type ScanType = "endpoint" | "provider" | "local" | "agent" | "mcp" | "rag";

export type AnalysisMode = "offline" | "cloud";

export interface ScanCreateBody {
  target_type: ScanType;
  url?: string;
  provider?: string;
  model?: string;
  agent?: string;
  agent_config?: string;
  mcp?: string;
  rag?: string;
  embedder?: string;
  formats?: string[];
  auth_token?: string;
  endpoint_profile?: string;
  request_template?: string;
  response_path?: string;
  redteam_plugins?: string[];
  analysis_mode?: AnalysisMode;
  analysis_provider?: string;
  analysis_model?: string;
  analysis_api_key?: string;
  l0_enabled?: boolean;
  max_variants_per_goal?: number;
  l0_suites?: string[];
  cloud_mutations_enabled?: boolean;
  self_play_enabled?: boolean;
  self_play_max_rounds?: number;
  self_play_stop_on_success?: boolean;
  self_play_discovery_enabled?: boolean;
  self_play_defender_enabled?: boolean;
}

export interface EvidenceGraph {
  nodes: { id: string; type: string; label: string; severity?: string; owasp?: string[] }[];
  edges: { from: string; to: string; relation: string; attack_goal?: string }[];
}

export interface ScanSummary {
  id: string;
  status: string;
  probe_count: number;
  finding_count: number;
  target: Record<string, unknown>;
  metadata?: {
    reports?: string[];
    attack_trees?: AttackTree[];
    evidence_graph?: EvidenceGraph;
    self_play?: { successful?: boolean; rounds?: number };
  };
}

export interface RiskAssessment {
  risk_score: number;
  confidence: number;
  exploitability: number;
  impact: string;
  reproducibility: number;
}

export interface AttackStep {
  step: string;
  probe_id: string;
  mutated_from?: string | null;
  evidence?: string | null;
}

export interface AttackTree {
  attack_goal: string;
  attack_tree_id: string;
  path: AttackStep[];
  successful: boolean;
}

export interface Finding {
  id: string;
  probe_id: string;
  probe_name: string;
  owasp: string[];
  severity: string;
  decision: string;
  risk_score: number;
  description?: string;
  response_excerpt: string;
  evidence: string[];
  metadata?: Record<string, unknown>;
  risk_assessment?: RiskAssessment;
}

export interface Settings {
  portable_mode: boolean;
  l5_enabled: boolean;
  model_dir: string;
  output_dir: string;
  analysis_mode?: AnalysisMode;
  analysis_provider?: string;
  analysis_model?: string;
  analysis_api_key?: string;
  l0_enabled?: boolean;
  max_variants_per_goal?: number;
  l0_suites?: string[];
  cloud_mutations_enabled?: boolean;
  self_play_enabled?: boolean;
  self_play_max_rounds?: number;
  self_play_stop_on_success?: boolean;
  self_play_discovery_enabled?: boolean;
  self_play_defender_enabled?: boolean;
}

export interface ConnectionTestBody {
  target_type: string;
  url?: string;
  provider?: string;
  model?: string;
  auth_token?: string;
  endpoint_profile?: string;
  request_template?: string;
  response_path?: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),

  createScan: (body: ScanCreateBody) =>
    request<{ scan_id: string; status: string }>("/v1/scans", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getScan: (id: string) => request<ScanSummary>(`/v1/scans/${id}`),

  getFindings: (scanId: string) =>
    request<Finding[]>(`/v1/scans/${scanId}/findings`),

  getReports: (scanId: string) =>
    request<{ reports: string[] }>(`/v1/scans/${scanId}/reports`),

  getSettings: () => request<Settings>("/v1/settings"),

  updateSettings: (body: Partial<Settings>) =>
    request<Settings>("/v1/settings", { method: "PUT", body: JSON.stringify(body) }),

  createBenchmark: (body: {
    suite: string;
    targets: { type: string; provider?: string; model?: string; label?: string }[];
  }) =>
    request<{ benchmark_id: string; status: string }>("/v1/benchmarks", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getBenchmark: (id: string) => request<Record<string, unknown>>(`/v1/benchmarks/${id}`),

  createToolsBenchmark: (body: { suite?: string; targets?: string[] }) =>
    request<{ benchmark_id: string; status: string; kind: string }>("/v1/benchmarks/tools", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getToolsBenchmark: (id: string) =>
    request<Record<string, unknown>>(`/v1/benchmarks/tools/${id}`),

  testConnection: (body: ConnectionTestBody) =>
    request<{
      ok: boolean;
      error?: string;
      latency_ms?: number;
      sample_excerpt?: string;
      status_code?: number;
      profile?: string;
      response_path?: string;
      hint?: string;
    }>("/v1/targets/test-connection", { method: "POST", body: JSON.stringify(body) }),

  listMarketplaceRules: () =>
    request<
      {
        id: string;
        name: string;
        version: string;
        description: string;
        category: string;
        owasp: string[];
      }[]
    >("/v1/marketplace/rules"),

  installMarketplaceRule: (rule_id: string) =>
    request<{ manifest_id: string; install_path: string }>("/v1/marketplace/install", {
      method: "POST",
      body: JSON.stringify({ rule_id }),
    }),

  listInstalledRules: () =>
    request<{ manifest_id: string; name: string; version: string; install_path: string }[]>(
      "/v1/marketplace/installed"
    ),

  listMonitorSchedules: () =>
    request<
      {
        id: string;
        name: string;
        cron: string;
        enabled: boolean;
        last_finding_count: number;
        drift_detected: boolean;
      }[]
    >("/v1/monitoring/schedules"),

  createMonitorSchedule: (body: {
    name: string;
    target_type: string;
    target_config: Record<string, string>;
    cron: string;
  }) =>
    request<{ id: string }>("/v1/monitoring/schedules", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  runMonitorSchedule: (scheduleId: string) =>
    request<{ status: string }>(`/v1/monitoring/schedules/${scheduleId}/run`, { method: "POST" }),

  exportDataset: (body: { scan_ids?: string[]; anonymize?: boolean }) =>
    request<{ path: string; format: string }>("/v1/datasets/export", {
      method: "POST",
      body: JSON.stringify({
        scan_ids: body.scan_ids ?? [],
        anonymize: body.anonymize ?? true,
      }),
    }),
};

export function eventsUrl(scanId: string): string {
  return `${base}/v1/scans/${scanId}/events`;
}
