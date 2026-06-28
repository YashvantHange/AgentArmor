import { useCallback, useEffect, useRef, useState } from "react";
import { api, ReportFormat } from "../api/client";
import { Button } from "./ui/Button";
import { Alert } from "./ui/Alert";

const FORMATS: { id: ReportFormat; label: string }[] = [
  { id: "pdf", label: "PDF" },
  { id: "html", label: "HTML" },
  { id: "sarif", label: "SARIF" },
  { id: "json", label: "JSON" },
  { id: "zip", label: "All (ZIP)" },
];

export function ReportDownloadMenu({
  scanId,
  isWebScan = false,
  pollWhileRunning = false,
  scanStatus,
  compact = false,
}: {
  scanId: string;
  isWebScan?: boolean;
  pollWhileRunning?: boolean;
  scanStatus?: string;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [reports, setReports] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState<ReportFormat | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const loadReports = useCallback(() => {
    const fetchReports = isWebScan ? api.getWebReports(scanId) : api.getReports(scanId);
    return fetchReports
      .then((r) => {
        setReports(r.reports);
        return r.reports;
      })
      .catch(() => {
        setReports([]);
        return [] as string[];
      });
  }, [scanId, isWebScan]);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

  useEffect(() => {
    if (!pollWhileRunning || scanStatus !== "running") return;
    const id = window.setInterval(() => void loadReports(), 3000);
    return () => window.clearInterval(id);
  }, [pollWhileRunning, scanStatus, loadReports]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const ready = reports !== null && reports.length > 0;
  const disabled = reports === null || !ready;

  async function handleDownload(format: ReportFormat) {
    setError("");
    setDownloading(format);
    try {
      await api.downloadReport(scanId, format, isWebScan);
      setOpen(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Download failed";
      setError(msg.includes("404") ? "Report not ready yet — wait for scan to finish." : msg);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      <Button
        variant={compact ? "secondary" : "primary"}
        size={compact ? "sm" : "md"}
        disabled={disabled}
        title={disabled && !ready ? "Reports generate when scan completes" : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        {reports === null ? "Loading…" : "Download reports"}
      </Button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 min-w-[10rem] rounded-lg border border-surface-border bg-surface-raised py-1 shadow-panel">
          {FORMATS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className="block w-full px-4 py-2 text-left text-sm text-ink-primary hover:bg-surface-overlay disabled:opacity-50"
              disabled={!!downloading}
              onClick={() => void handleDownload(id)}
            >
              {downloading === id ? `Downloading ${label}…` : label}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="absolute right-0 top-full z-10 mt-2 w-64">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
    </div>
  );
}
