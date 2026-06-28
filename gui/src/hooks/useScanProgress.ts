import { useEffect, useMemo, useState } from "react";
import { ScanEvent } from "./useScanEvents";
import { probeLabelFromEvent } from "../lib/probeLabel";

export interface ScanProgressState {
  total: number;
  completed: number;
  currentActivity: string;
  indeterminate: boolean;
  etaMs: number | null;
  fallbackEtaLabel: string;
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

export function useScanProgress(
  events: ScanEvent[],
  options: {
    polledProbeTotal: number | null;
    targetType?: string;
    elapsedMs: number;
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

  const total = options.polledProbeTotal ?? totalFromEvents;
  const completed = events.filter((e) => e.event === "probe.completed").length;

  const latestProbe = [...events].reverse().find((e) => e.event === "probe.started");
  const currentActivity = latestProbe ? probeLabelFromEvent(latestProbe.data) : "Preparing scan…";

  useEffect(() => {
    if (total > 0) {
      setPlanningTimedOut(false);
      return;
    }
    const id = window.setTimeout(() => setPlanningTimedOut(true), 10_000);
    return () => window.clearTimeout(id);
  }, [total]);

  const indeterminate = total === 0 && (planningTimedOut || events.length > 0);

  let etaMs: number | null = null;
  if (completed >= 2 && total > completed && options.elapsedMs > 0) {
    etaMs = (options.elapsedMs / completed) * (total - completed);
    if (options.targetType === "provider") {
      etaMs *= 1.5;
    }
  }

  const fallbackEtaLabel =
    FALLBACK_ETA[options.targetType ?? ""] ?? FALLBACK_ETA.endpoint;

  return {
    total,
    completed,
    currentActivity,
    indeterminate,
    etaMs,
    fallbackEtaLabel,
  };
}

export function scanStatusLabel(targetType: string | undefined, finished: boolean): string {
  if (finished) return "Scan complete";
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
