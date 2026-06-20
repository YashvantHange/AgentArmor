import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useScanEvents } from "../hooks/useScanEvents";

export default function ScanProgress() {
  const { scanId } = useParams<{ scanId: string }>();
  const { events, done } = useScanEvents(scanId ?? null);
  const [findingCount, setFindingCount] = useState(0);

  useEffect(() => {
    if (!scanId || !done) return;
    api.getScan(scanId).then((s) => setFindingCount(s.finding_count));
  }, [scanId, done]);

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Scan Progress</h1>
      <p className="text-slate-400 mb-4 font-mono text-sm">{scanId}</p>
      <div className="rounded-xl border border-slate-700 bg-slate-900 p-4 max-h-96 overflow-y-auto space-y-2">
        {events.length === 0 && <p className="text-slate-500">Waiting for events…</p>}
        {events.map((ev, i) => (
          <div key={i} className="text-sm font-mono border-b border-slate-800 pb-2">
            <span className="text-armor-500">{ev.event}</span>
            <pre className="text-slate-400 mt-1 whitespace-pre-wrap">
              {JSON.stringify(ev.data, null, 2)}
            </pre>
          </div>
        ))}
      </div>
      {done && (
        <div className="mt-6 flex gap-3">
          <Link
            to={`/findings/${scanId}`}
            className="px-4 py-2 rounded-lg bg-armor-700 hover:bg-armor-500"
          >
            View {findingCount} Finding(s)
          </Link>
          <Link
            to={`/reports/${scanId}`}
            className="px-4 py-2 rounded-lg border border-slate-600 hover:border-armor-500"
          >
            Export Reports
          </Link>
        </div>
      )}
    </div>
  );
}
