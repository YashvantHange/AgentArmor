import { formatEtaMs, useElapsedTimer } from "../hooks/useElapsedTimer";
import { ScanProgressState, scanStatusLabel } from "../hooks/useScanProgress";
import { Card } from "./ui/Card";

export function ScanProgressPanel({
  targetType,
  finished,
  startedAt,
  fallbackStartMs,
  progress,
  findingCount,
}: {
  targetType?: string;
  finished: boolean;
  startedAt: string | null | undefined;
  fallbackStartMs?: number | null;
  progress: ScanProgressState;
  findingCount: number;
}) {
  const { formatted } = useElapsedTimer(startedAt, fallbackStartMs);
  const pct =
    progress.total > 0 ? Math.min(100, Math.round((progress.completed / progress.total) * 100)) : 0;
  const etaLabel =
    progress.etaMs !== null && progress.completed >= 2
      ? formatEtaMs(progress.etaMs)
      : progress.fallbackEtaLabel;

  return (
    <div className="mb-6 space-y-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            {!finished && (
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-60" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-brand-500" />
              </span>
            )}
            <p className="text-sm font-medium text-ink-primary">
              {scanStatusLabel(targetType, finished)}
            </p>
          </div>
          <p className="font-mono text-sm tabular-nums text-ink-muted">{formatted}</p>
        </div>

        <div className="mt-4">
          {progress.indeterminate || progress.total === 0 ? (
            <>
              <div className="h-2 overflow-hidden rounded-full bg-surface-overlay">
                <div className="h-full w-1/3 animate-pulse rounded-full bg-brand-500/70" />
              </div>
              <p className="mt-2 text-xs text-ink-muted">Preparing probes…</p>
            </>
          ) : (
            <>
              <div className="h-2 overflow-hidden rounded-full bg-surface-overlay">
                <div
                  className="h-full rounded-full bg-brand-500 transition-all duration-300"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-muted">
                <span>
                  {progress.completed} / {progress.total} probes ({pct}%)
                </span>
                {!finished && <span>{etaLabel}</span>}
              </div>
            </>
          )}
        </div>

        {!finished && (
          <p className="mt-3 text-sm text-ink-secondary">
            Current: <span className="font-medium text-ink-primary">{progress.currentActivity}</span>
          </p>
        )}
      </Card>

      {(progress.total > 0 || findingCount > 0) && (
        <div className="grid grid-cols-3 gap-3">
          {[
            ["Probes", progress.total || "—"],
            ["Completed", progress.completed],
            ["Findings", findingCount],
          ].map(([label, value]) => (
            <Card key={label} className="px-4 py-3 text-center">
              <div className="text-lg font-semibold text-ink-primary">{value}</div>
              <div className="text-xs text-ink-muted">{label}</div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
