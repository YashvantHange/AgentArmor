import { useEffect, useState } from "react";

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
  const totalSeconds = Math.floor(elapsedMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const formatted = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;

  return { elapsedMs, formatted, active: startMs !== null };
}

export function formatEtaMs(etaMs: number | null): string {
  if (etaMs === null || !Number.isFinite(etaMs) || etaMs <= 0) return "";
  const totalSeconds = Math.ceil(etaMs / 1000);
  if (totalSeconds < 60) return `~${totalSeconds}s remaining`;
  const minutes = Math.ceil(totalSeconds / 60);
  return `~${minutes} min remaining`;
}
