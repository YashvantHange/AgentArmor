import { useEffect, useState } from "react";
import { eventsUrl } from "../api/client";

export interface ScanEvent {
  event: string;
  data: Record<string, unknown>;
}

export function useScanEvents(scanId: string | null) {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!scanId) return;
    setEvents([]);
    setDone(false);
    const source = new EventSource(eventsUrl(scanId));
    source.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data) as Record<string, unknown>;
        const eventName = (msg as MessageEvent & { event?: string }).type === "message"
          ? (data as { event?: string }).event || "message"
          : "message";
        setEvents((prev) => [...prev, { event: eventName, data }]);
        if (data && typeof data === "object" && "finding_count" in data) {
          setDone(true);
          source.close();
        }
      } catch {
        setEvents((prev) => [...prev, { event: "raw", data: { raw: msg.data } }]);
      }
    };
    source.addEventListener("scan.completed", () => {
      setDone(true);
      source.close();
    });
    source.onerror = () => {
      setDone(true);
      source.close();
    };
    return () => source.close();
  }, [scanId]);

  return { events, done };
}
