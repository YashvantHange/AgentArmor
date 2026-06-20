const base = import.meta.env.VITE_API_URL || "http://127.0.0.1:8787";

export type ScanType = "endpoint" | "provider" | "local" | "agent" | "mcp" | "rag";

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
}

export interface ScanSummary {
  id: string;
  status: string;
  probe_count: number;
  finding_count: number;
  target: Record<string, unknown>;
  metadata?: { reports?: string[] };
}

export interface Finding {
  id: string;
  probe_id: string;
  probe_name: string;
  owasp: string[];
  severity: string;
  decision: string;
  risk_score: number;
  response_excerpt: string;
  evidence: string[];
}

export interface Settings {
  portable_mode: boolean;
  l5_enabled: boolean;
  model_dir: string;
  output_dir: string;
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
};

export function eventsUrl(scanId: string): string {
  return `${base}/v1/scans/${scanId}/events`;
}
