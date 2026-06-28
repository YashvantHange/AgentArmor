import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, ReportFormat } from "../api/client";
import { PageHeader } from "../components/layout/PageHeader";
import { ReportDownloadMenu } from "../components/ReportDownloadMenu";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { LoadingBlock } from "../components/ui/Spinner";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { CopyIcon, FileIcon } from "../components/icons";
import { isTauri, openReportFolder } from "../lib/isTauri";

function formatFromPath(path: string): ReportFormat | null {
  const ext = path.split(".").pop()?.toLowerCase();
  if (ext === "pdf" || ext === "html" || ext === "sarif" || ext === "json") {
    return ext;
  }
  return null;
}

function reportDirectory(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const idx = normalized.lastIndexOf("/");
  return idx >= 0 ? path.slice(0, idx) : path;
}

export default function Reports() {
  const { scanId } = useParams<{ scanId: string }>();
  const [searchParams] = useSearchParams();
  const isWebScan = searchParams.get("kind") === "web";
  const [reports, setReports] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!scanId) return;
    setError("");
    const fetchReports = isWebScan ? api.getWebReports(scanId) : api.getReports(scanId);
    fetchReports
      .then((r) => setReports(r.reports))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load reports"));
  }, [scanId, isWebScan]);

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

  async function downloadFormat(format: ReportFormat) {
    if (!scanId) return;
    setError("");
    setDownloading(format);
    try {
      await api.downloadReport(scanId, format, isWebScan);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Download failed";
      setError(msg.includes("404") ? "Report not ready yet — wait for scan to finish." : msg);
    } finally {
      setDownloading(null);
    }
  }

  async function downloadFile(path: string) {
    const format = formatFromPath(path);
    if (format) {
      await downloadFormat(format);
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

  const folderPath = reports.length > 0 ? reportDirectory(reports[0]) : null;

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Export reports"
        subtitle="Download generated artifacts or open the output folder."
        backTo={scanId ? `/progress/${scanId}${isWebScan ? "?kind=web" : ""}` : "/"}
        actions={
          scanId ? <ReportDownloadMenu scanId={scanId} isWebScan={isWebScan} compact /> : undefined
        }
      />

      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {folderPath && isTauri() && (
        <div className="mb-4">
          <Button variant="secondary" size="sm" onClick={() => void openReportFolder(folderPath)}>
            Open folder
          </Button>
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
            const format = formatFromPath(path);
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
                  <div className="flex shrink-0 items-center gap-2">
                    {format && (
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!!downloading}
                        onClick={() => void downloadFile(path)}
                      >
                        {downloading === format ? "Downloading…" : "Download"}
                      </Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => copyPath(path)}>
                      <CopyIcon className="h-4 w-4" />
                      {copied === path ? "Copied" : "Copy path"}
                    </Button>
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
