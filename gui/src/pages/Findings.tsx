import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, Finding } from "../api/client";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge, severityTone } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingBlock } from "../components/ui/Spinner";
import { Alert } from "../components/ui/Alert";

export default function Findings() {
  const { scanId } = useParams<{ scanId: string }>();
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Finding | null>(null);

  const load = useCallback(() => {
    if (!scanId) return;
    setError("");
    api
      .getFindings(scanId)
      .then(setFindings)
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

      {findings.length === 0 ? (
        <EmptyState
          title="No security findings"
          description="All probes completed without triggering detection thresholds for this target."
        />
      ) : (
        <div className="space-y-2">
          {findings.map((f) => (
            <Card key={f.id} hover className="w-full p-4" onClick={() => setSelected(f)}>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-semibold text-ink-primary">{f.probe_name}</h2>
                  <p className="mt-0.5 font-mono text-xs text-ink-muted">{f.probe_id}</p>
                </div>
                <Badge tone={severityTone(f.severity)}>{f.severity}</Badge>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {f.owasp.map((t) => (
                  <Badge key={t} tone="brand">
                    {t}
                  </Badge>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={() => setSelected(null)}
          role="presentation"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="finding-title"
            className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-surface-border bg-surface-raised p-6 shadow-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id="finding-title" className="text-lg font-semibold text-ink-primary">
                  {selected.probe_name}
                </h2>
                <p className="mt-1 text-sm text-ink-muted">
                  Risk score {selected.risk_score.toFixed(2)} · {selected.decision}
                </p>
              </div>
              <Badge tone={severityTone(selected.severity)}>{selected.severity}</Badge>
            </div>

            <div className="mt-5">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Evidence</h3>
              <pre className="mt-2 overflow-x-auto rounded-lg border border-surface-border bg-surface p-4 font-mono text-xs leading-relaxed text-ink-secondary whitespace-pre-wrap">
                {selected.evidence.join("\n") || selected.response_excerpt || "No evidence captured."}
              </pre>
            </div>

            <div className="mt-6 flex justify-end">
              <Button variant="secondary" onClick={() => setSelected(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
