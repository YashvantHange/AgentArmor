import { Finding, ScanSummary } from "../api/client";
import { getEnrichment } from "./IssueDetail";
import { Badge, severityTone } from "./ui/Badge";
import { Card } from "./ui/Card";

const SEVERITY_ORDER: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
  INFO: 4,
};

function targetLabel(scan: ScanSummary): string {
  const t = scan.target ?? {};
  const type = String(t.type ?? "endpoint");
  if (type === "provider") {
    return `${String(t.provider ?? "cloud")} · ${String(t.model ?? "model")}`;
  }
  if (type === "agent") return `Agent · ${String(t.agent_framework ?? "framework")}`;
  if (type === "mcp") return `MCP · ${String(t.mcp_target ?? "target")}`;
  if (type === "rag") return `RAG · ${String(t.rag_corpus ?? "corpus")}`;
  if (type === "local") return `Local · ${String(t.model ?? "model")}`;
  if (scan.metadata?.page_url) return String(scan.metadata.page_url);
  return String(t.url ?? type);
}

function buildVerdict(findings: Finding[]): string {
  if (findings.length === 0) {
    return "0 issues — target appears resilient to executed probes.";
  }
  const high = findings.filter((f) => f.severity === "HIGH" || f.severity === "CRITICAL").length;
  const themes = new Set<string>();
  for (const f of findings.slice(0, 5)) {
    const e = getEnrichment(f);
    if (e?.plain_title) themes.add(e.plain_title.toLowerCase());
  }
  const themeHint =
    themes.size > 0 ? ` — ${[...themes].slice(0, 2).join("; ")}` : "";
  if (high > 0) {
    return `${findings.length} security issue${findings.length === 1 ? "" : "s"} found (${high} high or critical)${themeHint}.`;
  }
  return `${findings.length} security issue${findings.length === 1 ? "" : "s"} found${themeHint}.`;
}

function analysisMode(scan: ScanSummary | null): string | null {
  const fromMeta = scan?.metadata?.analysis_mode;
  if (typeof fromMeta === "string") return fromMeta;
  const first = scan?.metadata?.analysis_mode;
  return typeof first === "string" ? first : null;
}

export function FindingsSummary({
  scan,
  findings,
}: {
  scan: ScanSummary | null;
  findings: Finding[];
}) {
  const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 };
  for (const f of findings) {
    const key = f.severity as keyof typeof counts;
    if (key in counts) counts[key] += 1;
  }

  const cloudBadge =
    analysisMode(scan) === "cloud" ||
    findings.some((f) => getEnrichment(f)?.analysis_mode === "cloud");

  return (
    <Card className="mb-6 p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">Target</p>
          <p className="mt-1 truncate text-sm font-medium text-ink-primary">
            {scan ? targetLabel(scan) : "—"}
          </p>
          <p className="mt-3 text-sm leading-relaxed text-ink-secondary">{buildVerdict(findings)}</p>
        </div>
        {cloudBadge && (
          <Badge tone="brand" className="shrink-0 self-start">
            Cloud enhanced analysis
          </Badge>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {(["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((sev) =>
          counts[sev] > 0 ? (
            <Badge key={sev} tone={severityTone(sev)}>
              {counts[sev]} {sev}
            </Badge>
          ) : null
        )}
        {findings.length === 0 && (
          <Badge tone="brand">All clear</Badge>
        )}
      </div>
    </Card>
  );
}

export function sortFindings(findings: Finding[]): Finding[] {
  return [...findings].sort((a, b) => {
    const sa = SEVERITY_ORDER[a.severity] ?? 99;
    const sb = SEVERITY_ORDER[b.severity] ?? 99;
    if (sa !== sb) return sa - sb;
    return (b.risk_score ?? 0) - (a.risk_score ?? 0);
  });
}

function findingExcerpt(finding: Finding): string {
  const firstEvidence = finding.evidence?.find((e) => e.trim());
  if (firstEvidence?.trim()) {
    return firstEvidence.trim();
  }
  if (finding.request_summary?.trim()) {
    const s = finding.request_summary.trim();
    return s.length > 160 ? `${s.slice(0, 160)}…` : s;
  }
  if (finding.response_excerpt?.trim()) {
    const s = finding.response_excerpt.trim();
    return s.length > 160 ? `${s.slice(0, 160)}…` : s;
  }
  return "";
}

export function findingCardTitle(finding: Finding): string {
  const e = getEnrichment(finding);
  return e?.plain_title?.trim() || finding.probe_name || finding.probe_id;
}

export function formatRiskScore(finding: Finding): string {
  const ra = finding.risk_assessment;
  if (ra && typeof ra.risk_score === "number") {
    return `${ra.risk_score}/100`;
  }
  if (typeof finding.risk_score === "number") {
    return `${Math.round(finding.risk_score * 100)}/100`;
  }
  return "—";
}
