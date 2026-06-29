/** Work-unit weights aligned with backend orchestrator/planning/work_units.py */
export const WORK_UNITS_BY_LAYER: Record<string, number> = {
  L1: 1,
  L2: 2,
  L3: 5,
  L0: 3,
  plugin: 2,
  agent: 2,
  mcp: 2,
  rag: 3,
  self_play: 8,
};

export function layerWorkUnits(layer: string | undefined): number {
  if (!layer) return 1;
  return WORK_UNITS_BY_LAYER[layer] ?? 1;
}

export type EtaConfidence = "low" | "medium" | "high" | "none";

export function etaConfidence(completedUnits: number): EtaConfidence {
  if (completedUnits < 2) return "none";
  if (completedUnits < 5) return "low";
  if (completedUnits < 15) return "medium";
  return "high";
}

export function formatDurationMs(ms: number): string {
  const totalSeconds = Math.floor(Math.max(0, ms) / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatEtaMs(
  etaMs: number | null,
  confidence: EtaConfidence
): string {
  if (confidence === "none" || etaMs === null || !Number.isFinite(etaMs) || etaMs <= 0) {
    return "ETA unavailable (insufficient data)";
  }
  if (confidence === "low") {
    return "Calculating ETA…";
  }
  const totalSeconds = Math.ceil(etaMs / 1000);
  const label =
    totalSeconds < 60
      ? `~${totalSeconds}s remaining`
      : `~${Math.ceil(totalSeconds / 60)} min remaining`;
  const confLabel = confidence === "high" ? "High" : "Medium";
  return `${label} · ${confLabel} confidence`;
}

export function formatRemainingLayers(rem: Record<string, number> | undefined): string {
  if (!rem) return "";
  const parts = ["L3", "L2", "L1", "L0", "plugin"]
    .filter((k) => (rem[k] ?? 0) > 0)
    .map((k) => `${rem[k]} ${k}`);
  return parts.length ? `Remaining: ${parts.join(" · ")}` : "";
}

export const SCAN_PHASE_LABELS: Record<string, string> = {
  planning: "Planning probes…",
  discovery: "Discovering target capabilities…",
  executing: "Executing security probes…",
  analysis: "Analyzing responses…",
  clustering: "Grouping findings…",
  report_generation: "Generating reports…",
  completed: "Scan complete",
};
