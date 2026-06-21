import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, AttackTree, Finding, ScanSummary } from "../api/client";
import { AttackChainView, EvidenceGraph } from "../components/AttackChainView";
import { getEnrichment, IssueDetail } from "../components/IssueDetail";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge, severityTone } from "../components/ui/Badge";
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
      />

      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      <AttackChainView
        attackTrees={(scan?.metadata?.attack_trees as AttackTree[] | undefined) ?? []}
        evidenceGraph={(scan?.metadata?.evidence_graph as EvidenceGraph | undefined) ?? null}
      />

      {findings.length === 0 ? (
        <EmptyState
          title="No security findings"
          description="All probes completed without triggering detection thresholds for this target."
        />
      ) : (
        <div className="space-y-2">
          {findings.map((f) => {
            const e = getEnrichment(f);
            const title = e?.plain_title || f.probe_name;
            const owaspIds = e?.owasp?.map((o) => o.id) ?? f.owasp;
            return (
              <Card key={f.id} hover className="w-full p-4" onClick={() => setSelected(f)}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="truncate text-sm font-semibold text-ink-primary">{title}</h2>
                    <p className="mt-0.5 font-mono text-xs text-ink-muted">{f.probe_id}</p>
                    {e?.what_happened && (
                      <p className="mt-2 line-clamp-2 text-xs text-ink-muted">{e.what_happened}</p>
                    )}
                  </div>
                  <Badge tone={severityTone(f.severity)}>{f.severity}</Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {owaspIds.map((t) => (
                    <Badge key={t} tone="brand">
                      {t}
                    </Badge>
                  ))}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {selected && <IssueDetail finding={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
