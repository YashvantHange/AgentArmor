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
  scan_mode?: "standard" | "multi_agent_redteam";
  scan_depth?: string;
  planner_v2?: boolean;
  finding_groups?: boolean;
  scan_profile?: string;
  owasp_ids?: string[];
}

export interface ScanProfile {
  id: string;
  name: string;
  description: string;
  target_types: string[];
  owasp_ids: string[];
  scan_depth: string;
  scan_mode: string;
}

export interface EvidenceGraph {
  nodes: { id: string; type: string; label: string; severity?: string; owasp?: string[] }[];
  edges: { from: string; to: string; relation: string; attack_goal?: string }[];
}

export type ReportFormat = "pdf" | "html" | "sarif" | "json" | "zip";

export interface ScanSummary {
  id: string;
  status: string;
  probe_count: number;
  finding_count: number;
  started_at?: string | null;
  completed_at?: string | null;
  target: Record<string, unknown>;
  metadata?: {
    reports?: string[];
    attack_trees?: AttackTree[];
    evidence_graph?: EvidenceGraph;
    self_play?: { successful?: boolean; rounds?: number };
    redteam_trace?: Record<string, unknown>;
    redteam_summary?: Record<string, unknown>;
    probe_count_planned?: number;
    scan_kind?: string;
    page_url?: string;
    analysis_mode?: AnalysisMode;
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

export function eventsUrl(scanId: string): string {
  return `${base}/v1/scans/${scanId}/events`;
}

function reportDownloadUrl(scanId: string, format: ReportFormat, isWebScan: boolean): string {
  const prefix = isWebScan ? `/v1/web-scans/${scanId}` : `/v1/scans/${scanId}`;
  return `${base}${prefix}/reports/download?format=${format}`;
}

export interface WebDiscoverBody {
  page_url: string;
}

export interface WebDiscoverResult {
  ok: boolean;
  error?: string;
  framework?: string | null;
  widget?: {
    confidence: number;
    input_selector: string;
    send_selector?: string | null;
    framework?: string | null;
  } | null;
  candidates?: unknown[];
  capability_map?: {
    framework?: string | null;
    rag: boolean;
    memory: boolean;
    mcp: boolean;
    a2a: boolean;
    tools: string[];
    agentic_score: number;
    risk_score: number;
    risk_reasons: string[];
  } | null;
  agent_risk?: {
    tool_count: number;
    rag_enabled: boolean;
    memory_enabled: boolean;
    mcp_enabled: boolean;
    external_actions: boolean;
    agentic_score: number;
    risk_score: number;
    risk_reasons: string[];
  } | null;
}

export interface WebScanCreateBody {
  page_url: string;
  scan_depth?: "standard" | "multi_agentic";
  auth_mode?: "none" | "manual_session";
  planner_enabled?: boolean;
  owasp_filters?: string[];
  analysis_mode?: AnalysisMode;
  analysis_provider?: string;
  analysis_model?: string;
  analysis_api_key?: string;
  formats?: string[];
}

export interface WebScanContinueBody {
  scan_depth?: "standard" | "multi_agentic";
  planner_enabled?: boolean;
  owasp_filters?: string[];
  analysis_mode?: AnalysisMode;
  analysis_provider?: string;
  analysis_model?: string;
  analysis_api_key?: string;
  formats?: string[];
}

export const api = {
  health: () => request<{ status: string; version: string; webscan_ready?: boolean }>("/health"),

  createScan: (body: ScanCreateBody) =>
    request<{ scan_id: string; status: string }>("/v1/scans", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listScanProfiles: (targetType?: string) =>
    request<ScanProfile[]>(
      `/v1/scans/profiles${targetType ? `?target_type=${encodeURIComponent(targetType)}` : ""}`
    ),

  getScan: (id: string) => request<ScanSummary>(`/v1/scans/${id}`),

  getFindings: (scanId: string) =>
    request<Finding[]>(`/v1/scans/${scanId}/findings`),

  getReports: (scanId: string) =>
    request<{ reports: string[] }>(`/v1/scans/${scanId}/reports`),

  getWebReports: (scanId: string) =>
    request<{ reports: string[] }>(`/v1/web-scans/${scanId}/reports`),

  downloadReport: async (
    scanId: string,
    format: ReportFormat,
    isWebScan = false
  ): Promise<void> => {
    const url = reportDownloadUrl(scanId, format, isWebScan);
    const res = await fetch(url);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition") ?? "";
    const match = /filename="?([^";\n]+)"?/.exec(disposition);
    const ext = format === "zip" ? "zip" : format;
    const filename = match?.[1] ?? `scan-${scanId}.${ext}`;
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  },

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

  getWebScanCapabilities: () =>
    request<{
      webscan_ready: boolean;
      hint?: string;
      scan_depths: string[];
      auth_modes?: string[];
      planner_requires_multi_agentic?: boolean;
    }>("/v1/web-scans/capabilities"),

  discoverWebScan: (body: WebDiscoverBody) =>
    request<WebDiscoverResult>("/v1/web-scans/discover", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  createWebScan: (body: WebScanCreateBody) =>
    request<{ scan_id: string; status: string; scan_kind: string }>("/v1/web-scans", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  prepareWebScanSession: (body: WebDiscoverBody) =>
    request<{ scan_id: string; status: string; message?: string }>("/v1/web-scans/prepare-session", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  continueWebScanSession: (scanId: string, body: WebScanContinueBody) =>
    request<{ scan_id: string; status: string; scan_kind: string }>(
      `/v1/web-scans/${scanId}/continue`,
      { method: "POST", body: JSON.stringify(body) }
    ),

  getWebScan: (id: string) => request<ScanSummary & { scan_kind?: string }>(`/v1/web-scans/${id}`),
};

