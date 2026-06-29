import { useEffect, useState } from "react";
import { formatDurationMs } from "../lib/scanProgressUtils";

function parseStartMs(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : null;
}

export function useElapsedTimer(startedAt: string | null | undefined, fallbackStartMs?: number | null) {
  const [now, setNow] = useState(() => Date.now());

  const startMs = parseStartMs(startedAt) ?? fallbackStartMs ?? null;

  useEffect(() => {
    if (startMs === null) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [startMs]);

  const elapsedMs = startMs !== null ? Math.max(0, now - startMs) : 0;
  const formatted = formatDurationMs(elapsedMs);

  return { elapsedMs, formatted, active: startMs !== null };
}

export { formatEtaMs } from "../lib/scanProgressUtils";
