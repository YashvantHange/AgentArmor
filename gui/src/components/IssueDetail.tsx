import { ReactNode } from "react";
import { Finding, RiskAssessment } from "../api/client";
import { Badge, severityTone } from "./ui/Badge";
import { Button } from "./ui/Button";

export interface Enrichment {
  plain_title?: string;
  what_happened?: string;
  why_it_matters?: string;
  owasp?: { id: string; name: string; description: string }[];
  remediation?: string[];
  detection_summary?: Record<string, string>;
  agentic_notes?: string | null;
  analysis_mode?: string;
  agentic_fallback?: boolean;
}

export function getEnrichment(finding: Finding): Enrichment | null {
  const meta = finding.metadata as { enrichment?: Enrichment } | undefined;
  return meta?.enrichment ?? null;
}

export function IssueDetail({
  finding,
  onClose,
}: {
  finding: Finding;
  onClose: () => void;
}) {
  const e = getEnrichment(finding);
  const title = e?.plain_title || finding.probe_name;
  const risk = finding.risk_assessment ?? (finding.metadata?.risk_assessment as RiskAssessment | undefined);
  const attackGoal = finding.metadata?.attack_goal as string | undefined;
  const mutationChain = finding.metadata?.mutation_chain as string[] | undefined;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-surface-border bg-surface-raised p-6 shadow-panel"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-ink-primary">{title}</h2>
            <p className="mt-1 font-mono text-xs text-ink-muted">{finding.probe_id}</p>
          </div>
          <Badge tone={severityTone(finding.severity)}>{finding.severity}</Badge>
        </div>

        {e?.analysis_mode === "cloud" && (
          <p className="mt-3 text-xs text-brand-600 dark:text-brand-400">
            Cloud enhanced analysis
            {e.agentic_fallback ? " (fell back to offline)" : ""}
          </p>
        )}

        {risk && (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <RiskMetric label="Risk score" value={`${risk.risk_score}/100`} />
            <RiskMetric label="Confidence" value={`${(risk.confidence * 100).toFixed(0)}%`} />
            <RiskMetric label="Exploitability" value={`${(risk.exploitability * 100).toFixed(0)}%`} />
            <RiskMetric label="Impact" value={risk.impact} />
          </div>
        )}

        {attackGoal && (
          <div className="mt-5">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Attack chain</h3>
            <p className="mt-2 text-sm text-ink-secondary">
              Goal: <span className="font-medium">{attackGoal.replace(/_/g, " ")}</span>
              {mutationChain && mutationChain.length > 0 && (
                <> · Mutations: {mutationChain.join(" → ")}</>
              )}
            </p>
          </div>
        )}

        <Section title="What happened">
          {e?.what_happened || finding.description || "No description available."}
        </Section>

        {e?.why_it_matters && <Section title="Why it matters">{e.why_it_matters}</Section>}

        {e?.owasp && e.owasp.length > 0 && (
          <div className="mt-5">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">OWASP</h3>
            <div className="mt-2 space-y-2">
              {e.owasp.map((o) => (
                <div key={o.id} className="rounded-lg border border-surface-border bg-surface p-3">
                  <div className="text-sm font-medium text-ink-primary">
                    {o.id} — {o.name}
                  </div>
                  <p className="mt-1 text-xs text-ink-muted">{o.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {e?.remediation && e.remediation.length > 0 && (
          <div className="mt-5">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">How to fix</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-secondary">
              {e.remediation.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}

        {e?.agentic_notes && (
          <Section title="AI analyst notes">{e.agentic_notes}</Section>
        )}

        {e?.detection_summary && Object.keys(e.detection_summary).length > 0 && (
          <div className="mt-5">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Detection breakdown
            </h3>
            <ul className="mt-2 space-y-1 text-sm text-ink-secondary">
              {Object.entries(e.detection_summary).map(([k, v]) => (
                <li key={k}>
                  <span className="font-mono uppercase text-ink-muted">{k}</span>: {v}
                </li>
              ))}
            </ul>
          </div>
        )}

        <details className="mt-5">
          <summary className="cursor-pointer text-sm text-ink-muted">Technical evidence</summary>
          <pre className="mt-2 overflow-x-auto rounded-lg border border-surface-border bg-surface p-3 font-mono text-xs whitespace-pre-wrap text-ink-secondary">
            {finding.evidence?.join("\n") || finding.response_excerpt || "No evidence."}
          </pre>
        </details>

        <div className="mt-6 flex justify-end">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}

function RiskMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface p-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="mt-1 text-sm font-semibold text-ink-primary">{value}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-ink-secondary">{children}</p>
    </div>
  );
}
