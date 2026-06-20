import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, Finding } from "../api/client";

const SEV_COLOR: Record<string, string> = {
  CRITICAL: "text-red-400",
  HIGH: "text-orange-400",
  MEDIUM: "text-yellow-400",
  LOW: "text-blue-400",
  INFO: "text-slate-400",
};

export default function Findings() {
  const { scanId } = useParams<{ scanId: string }>();
  const [findings, setFindings] = useState<Finding[]>([]);
  const [selected, setSelected] = useState<Finding | null>(null);

  useEffect(() => {
    if (scanId) api.getFindings(scanId).then(setFindings);
  }, [scanId]);

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Findings</h1>
      {findings.length === 0 ? (
        <p className="text-slate-400">No findings — target passed all probes.</p>
      ) : (
        <div className="space-y-3">
          {findings.map((f) => (
            <button
              key={f.id}
              onClick={() => setSelected(f)}
              className="w-full text-left p-4 rounded-xl border border-slate-700 bg-slate-900 hover:border-armor-500"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="font-semibold">{f.probe_name}</h2>
                  <p className="text-sm text-slate-400">{f.probe_id}</p>
                </div>
                <span className={`font-bold ${SEV_COLOR[f.severity] || ""}`}>{f.severity}</span>
              </div>
              <div className="flex gap-2 mt-2">
                {f.owasp.map((t) => (
                  <span key={t} className="text-xs px-2 py-0.5 rounded bg-indigo-900 text-indigo-200">
                    {t}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      )}
      {selected && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center p-4"
          onClick={() => setSelected(null)}
        >
          <div
            className="bg-slate-900 border border-slate-600 rounded-xl p-6 max-w-lg w-full max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-xl font-bold mb-2">{selected.probe_name}</h2>
            <p className={`mb-4 ${SEV_COLOR[selected.severity]}`}>
              {selected.severity} · risk {selected.risk_score.toFixed(2)}
            </p>
            <h3 className="text-sm text-slate-400 mb-1">Evidence</h3>
            <pre className="text-sm bg-slate-800 p-3 rounded mb-4 whitespace-pre-wrap">
              {selected.evidence.join("\n") || selected.response_excerpt}
            </pre>
            <button
              onClick={() => setSelected(null)}
              className="px-4 py-2 rounded bg-slate-700 hover:bg-slate-600"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
