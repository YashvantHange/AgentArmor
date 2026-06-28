/** Human-readable probe label from SSE or finding fields. */

export function formatProbeIdFallback(probeId: string): string {
  const segment = probeId.includes(".") ? probeId.split(".").slice(1).join(" ") : probeId;
  return segment.replace(/[-_]/g, " ");
}

export function probeLabelFromEvent(data: Record<string, unknown>): string {
  if (typeof data.name === "string" && data.name.trim()) {
    return data.name;
  }
  if (typeof data.probe_id === "string") {
    return formatProbeIdFallback(data.probe_id);
  }
  return "Running probe…";
}
