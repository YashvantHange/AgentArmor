import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingBlock } from "../components/ui/Spinner";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { CopyIcon, FileIcon } from "../components/icons";

export default function Reports() {
  const { scanId } = useParams<{ scanId: string }>();
  const [reports, setReports] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!scanId) return;
    setError("");
    api
      .getReports(scanId)
      .then((r) => setReports(r.reports))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load reports"));
  }, [scanId]);

  useEffect(() => {
    load();
  }, [load]);

  async function copyPath(path: string) {
    try {
      await navigator.clipboard.writeText(path);
      setCopied(path);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setError("Could not copy path to clipboard");
    }
  }

  if (reports === null) {
    return (
      <div>
        <PageHeader title="Reports" backTo={scanId ? `/progress/${scanId}` : "/"} />
        <LoadingBlock label="Loading report artifacts…" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Export reports"
        subtitle="Generated artifacts are written to your configured output directory."
        backTo={scanId ? `/progress/${scanId}` : "/"}
      />

      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {reports.length === 0 ? (
        <EmptyState
          title="No reports yet"
          description="Reports are created when the scan completes. Return here after the orchestrator finishes."
        />
      ) : (
        <ul className="space-y-2">
          {reports.map((path) => {
            const ext = path.split(".").pop()?.toUpperCase() ?? "FILE";
            return (
              <li key={path}>
                <Card className="flex items-center justify-between gap-4 p-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-overlay text-brand-400">
                      <FileIcon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-mono text-xs text-ink-primary">{path}</p>
                      <Badge tone="default" className="mt-1">
                        {ext}
                      </Badge>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => copyPath(path)}>
                    <CopyIcon className="h-4 w-4" />
                    {copied === path ? "Copied" : "Copy path"}
                  </Button>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
