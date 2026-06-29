import { useEffect, useMemo, useState } from "react";
import { ScanEvent } from "./useScanEvents";
import { probeLabelFromEvent } from "../lib/probeLabel";
import {
  etaConfidence,
  formatEtaMs,
  formatRemainingLayers,
  layerWorkUnits,
  SCAN_PHASE_LABELS,
} from "../lib/scanProgressUtils";

export interface ScanProgressState {
  total: number;
  completed: number;
  completedWorkUnits: number;
  totalWorkUnits: number;
  currentActivity: string;
  scanPhase: string;
  indeterminate: boolean;
  etaMs: number | null;
  fallbackEtaLabel: string;
  remainingByLayer: Record<string, number>;
  remainingLabel: string;
}

const FALLBACK_ETA: Record<string, string> = {
  provider: "~2–5 min (cloud scans may take longer)",
  endpoint: "~1–3 min",
  local: "~1–3 min",
  agent: "~2–4 min",
  mcp: "~2–4 min",
  rag: "~2–4 min",
  web: "~3–6 min",
};

const STORAGE_PREFIX = "agentarmor-scan-progress:";

export function persistScanProgress(scanId: string, snapshot: Record<string, unknown>) {
  try {
    sessionStorage.setItem(STORAGE_PREFIX + scanId, JSON.stringify(snapshot));
  } catch {
    /* ignore quota */
  }
}

export function loadScanProgress(scanId: string): Record<string, unknown> | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_PREFIX + scanId);
    return raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export function useScanProgress(
  events: ScanEvent[],
  options: {
    scanId?: string | null;
    polledProbeTotal: number | null;
    targetType?: string;
    elapsedMs: number;
    firstProbeCompletedMs: number | null;
  }
): ScanProgressState {
  const [planningTimedOut, setPlanningTimedOut] = useState(false);

  const totalFromEvents = useMemo(() => {
    const fromStarted = events.find(
      (e) => e.event === "scan.started" && typeof e.data.probe_count === "number" && e.data.probe_count > 0
    );
    if (fromStarted) return fromStarted.data.probe_count as number;

    const fromPlanning = events.find(
      (e) => e.event === "planning.completed" && typeof e.data.probe_count === "number"
    );
    if (fromPlanning) return fromPlanning.data.probe_count as number;

    return 0;
  }, [events]);

  const totalWorkUnitsFromStart = useMemo(() => {
    const fromStarted = events.find(
      (e) => e.event === "scan.started" && typeof e.data.total_work_units === "number"
    );
    return fromStarted ? (fromStarted.data.total_work_units as number) : 0;
  }, [events]);

  const sseTotal =
    totalFromEvents > 0 ? totalFromEvents : null;
  const total =
    options.polledProbeTotal && sseTotal && options.polledProbeTotal > sseTotal * 2
      ? sseTotal
      : options.polledProbeTotal ?? sseTotal ?? 0;

  const completedEvents = events.filter((e) => e.event === "probe.completed");
  const completed = completedEvents.length;

  const latestCompleted = completedEvents[completedEvents.length - 1];
  const remainingByLayer =
    (latestCompleted?.data.remaining_by_layer as Record<string, number> | undefined) ?? {};

  const completedWorkUnits = completedEvents.reduce((sum, e) => {
    const wu = e.data.work_units;
    if (typeof wu === "number") return sum + wu;
    const layer = typeof e.data.probe_layer === "string" ? e.data.probe_layer : "L1";
    return sum + layerWorkUnits(layer);
  }, 0);

  const totalWorkUnits =
    totalWorkUnitsFromStart > 0
      ? totalWorkUnitsFromStart
      : total > 0
        ? total * 2
        : 0;

  const latestPhase = [...events].reverse().find((e) => e.event === "scan.phase");
  const scanPhase =
    typeof latestPhase?.data.phase === "string" ? (latestPhase.data.phase as string) : "executing";

  const latestProbe = [...events].reverse().find((e) => e.event === "probe.started");
  const currentActivity = latestProbe
    ? probeLabelFromEvent(latestProbe.data)
    : SCAN_PHASE_LABELS[scanPhase] ?? "Preparing scan…";

  useEffect(() => {
    if (!options.scanId) return;
    persistScanProgress(options.scanId, {
      total,
      completed,
      completedWorkUnits,
      remainingByLayer,
      scanPhase,
      savedAt: Date.now(),
    });
  }, [options.scanId, total, completed, completedWorkUnits, remainingByLayer, scanPhase]);

  useEffect(() => {
    if (total > 0) {
      setPlanningTimedOut(false);
      return;
    }
    const id = window.setTimeout(() => setPlanningTimedOut(true), 10_000);
    return () => window.clearTimeout(id);
  }, [total]);

  const indeterminate = total === 0 && (planningTimedOut || events.length > 0);

  const probePhaseElapsed =
    options.firstProbeCompletedMs !== null
      ? Math.max(0, Date.now() - options.firstProbeCompletedMs)
      : options.elapsedMs;

  const remainingUnits =
    typeof latestCompleted?.data.remaining_work_units === "number"
      ? (latestCompleted.data.remaining_work_units as number)
      : Math.max(0, totalWorkUnits - completedWorkUnits);

  const confidence = etaConfidence(completedWorkUnits);

  let etaMs: number | null = null;
  if (completedWorkUnits >= 2 && remainingUnits > 0 && probePhaseElapsed > 0 && confidence !== "none") {
    etaMs = (probePhaseElapsed / completedWorkUnits) * remainingUnits;
    if (options.targetType === "provider") {
      etaMs *= 1.5;
    }
  }

  const fallbackEtaLabel = FALLBACK_ETA[options.targetType ?? ""] ?? FALLBACK_ETA.endpoint;

  return {
    total,
    completed,
    completedWorkUnits,
    totalWorkUnits,
    currentActivity,
    scanPhase,
    indeterminate,
    etaMs,
    fallbackEtaLabel,
    remainingByLayer,
    remainingLabel: formatRemainingLayers(remainingByLayer),
  };
}

export function scanStatusLabel(
  targetType: string | undefined,
  finished: boolean,
  scanPhase?: string
): string {
  if (finished) return "Scan complete";
  if (scanPhase && SCAN_PHASE_LABELS[scanPhase]) {
    return SCAN_PHASE_LABELS[scanPhase];
  }
  switch (targetType) {
    case "provider":
      return "Testing cloud provider…";
    case "local":
      return "Scanning local model…";
    case "agent":
      return "Testing agent framework…";
    case "mcp":
      return "Probing MCP server…";
    case "rag":
      return "Testing RAG pipeline…";
    case "web":
      return "Scanning chatbot page…";
    default:
      return "Scanning your API…";
  }
}

export function progressEtaLabel(progress: ScanProgressState): string {
  const confidence = etaConfidence(progress.completedWorkUnits);
  if (progress.etaMs !== null && progress.completedWorkUnits >= 2) {
    return formatEtaMs(progress.etaMs, confidence);
  }
  if (confidence === "none" || confidence === "low") {
    return formatEtaMs(null, confidence);
  }
  return progress.fallbackEtaLabel;
}
