import { useEffect, useState } from "react";
import { eventsUrl } from "../api/client";

export interface ScanEvent {
  event: string;
  data: Record<string, unknown>;
}

const NAMED_EVENTS = [
  "scan.started",
  "scan.heartbeat",
  "discovery.started",
  "discovery.completed",
  "planning.completed",
  "probe.started",
  "probe.waiting",
  "probe.completed",
  "scan.completed",
];

const SILENT_EVENTS = new Set(["scan.heartbeat"]);

export function useScanEvents(scanId: string | null) {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scanId) return;

    setEvents([]);
    setDone(false);
    setError(null);

    const source = new EventSource(eventsUrl(scanId));
    let closed = false;

    const append = (eventName: string, raw: string) => {
      if (SILENT_EVENTS.has(eventName)) return;
      try {
        const data = JSON.parse(raw) as Record<string, unknown>;
        setEvents((prev) => [...prev, { event: eventName, data }]);
        if (eventName === "scan.completed") {
          setDone(true);
          closed = true;
          source.close();
        }
      } catch {
        setEvents((prev) => [...prev, { event: eventName, data: { raw } }]);
      }
    };

    for (const name of NAMED_EVENTS) {
      source.addEventListener(name, (ev) => append(name, (ev as MessageEvent).data));
    }

    source.onerror = () => {
      if (closed) return;
      setError("Connection to scan stream lost");
      source.close();
    };

    return () => {
      closed = true;
      source.close();
    };
  }, [scanId]);

  return { events, done, error };
}
