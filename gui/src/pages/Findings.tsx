import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, AttackTree, Finding, ScanSummary } from "../api/client";
import { AttackChainView, EvidenceGraph } from "../components/AttackChainView";
import {
  findingCardTitle,
  findingExcerpt,
  FindingsSummary,
  formatRiskScore,
  sortFindings,
} from "../components/FindingsSummary";
import { getEnrichment, IssueDetail } from "../components/IssueDetail";
import { PageHeader } from "../components/layout/PageHeader";
import { ReportDownloadMenu } from "../components/ReportDownloadMenu";
import { Badge, severityTone } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingBlock } from "../components/ui/Spinner";
import { Alert } from "../components/ui/Alert";

export default function Findings() {
  const { scanId } = useParams<{ scanId: string }>();
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [scan, setScan] = useState<ScanSummary | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Finding | null>(null);

  const load = useCallback(() => {
    if (!scanId) return;
    setError("");
    Promise.all([api.getFindings(scanId), api.getScan(scanId)])
      .then(([f, s]) => {
        setFindings(f);
        setScan(s);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load findings"));
  }, [scanId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected]);

  const sorted = useMemo(
    () => (findings ? sortFindings(findings) : []),
    [findings]
  );

  const attackTrees = (scan?.metadata?.attack_trees as AttackTree[] | undefined) ?? [];
  const evidenceGraph = (scan?.metadata?.evidence_graph as EvidenceGraph | undefined) ?? null;
  const relationshipCount = evidenceGraph?.edges?.length ?? 0;

  if (findings === null) {
    return (
      <div>
        <PageHeader title="Findings" backTo={scanId ? `/progress/${scanId}` : "/"} />
        <LoadingBlock label="Loading findings…" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Findings"
        subtitle={`${findings.length} issue${findings.length === 1 ? "" : "s"} detected across executed probes.`}
        backTo={scanId ? `/progress/${scanId}` : "/"}
        actions={
          scanId ? (
            <div className="flex flex-wrap items-center gap-2">
              <ReportDownloadMenu scanId={scanId} compact />
              <Link to={`/reports/${scanId}`}>
                <Button variant="ghost" size="sm">
                  Manage exports
                </Button>
              </Link>
            </div>
          ) : undefined
        }
      />

      {error && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <Alert tone="error">{error}</Alert>
          <Button variant="secondary" size="sm" onClick={load}>
            Retry
          </Button>
        </div>
      )}

      <FindingsSummary scan={scan} findings={findings} />

      {findings.length === 0 ? (
        <EmptyState
          title="No security findings"
          description="All probes completed without triggering detection thresholds for this target."
        />
      ) : (
        <div className="space-y-2">
          {sorted.map((f) => {
            const title = findingCardTitle(f);
            const excerpt = findingExcerpt(f);
            const e = getEnrichment(f);
            const owaspIds = e?.owasp?.map((o) => o.id) ?? f.owasp;
            return (
              <Card key={f.id} hover className="w-full p-4" onClick={() => setSelected(f)}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <h2 className="text-base font-semibold text-ink-primary">{title}</h2>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      <Badge tone={severityTone(f.severity)}>{f.severity}</Badge>
                      <span className="text-xs text-ink-muted">Risk {formatRiskScore(f)}</span>
                    </div>
                    <p
                      className={`mt-3 line-clamp-2 text-sm ${
                        excerpt ? "font-mono text-ink-secondary" : "italic text-ink-muted"
                      }`}
                    >
                      {excerpt || "No response captured"}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {owaspIds.map((t) => (
                        <Badge key={t} tone="brand" className="text-[10px]">
                          {t}
                        </Badge>
                      ))}
                    </div>
                    <p className="mt-2 font-mono text-[10px] text-ink-muted">{f.probe_id}</p>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {(attackTrees.length > 0 || (evidenceGraph?.edges?.length ?? 0) > 0) && (
        <details className="mt-8 group">
          <summary className="cursor-pointer list-none rounded-lg border border-surface-border bg-surface-overlay px-4 py-3 text-sm font-medium text-ink-primary hover:bg-surface-border [&::-webkit-details-marker]:hidden">
            Show attack chains
            {relationshipCount > 0 ? ` (${relationshipCount} relationship${relationshipCount === 1 ? "" : "s"})` : ""}
          </summary>
          <div className="mt-4">
            <AttackChainView attackTrees={attackTrees} evidenceGraph={evidenceGraph} />
          </div>
        </details>
      )}

      {selected && <IssueDetail finding={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
