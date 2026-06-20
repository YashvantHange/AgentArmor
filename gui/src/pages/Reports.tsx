import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";

export default function Reports() {
  const { scanId } = useParams<{ scanId: string }>();
  const [reports, setReports] = useState<string[]>([]);

  useEffect(() => {
    if (scanId) api.getReports(scanId).then((r) => setReports(r.reports));
  }, [scanId]);

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Reports</h1>
      {reports.length === 0 ? (
        <p className="text-slate-400">No reports generated yet. Wait for scan to complete.</p>
      ) : (
        <ul className="space-y-3">
          {reports.map((path) => (
            <li
              key={path}
              className="flex items-center justify-between p-4 rounded-xl border border-slate-700 bg-slate-900"
            >
              <span className="font-mono text-sm truncate">{path}</span>
              <span className="text-xs text-slate-500 uppercase">
                {path.split(".").pop()}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-sm text-slate-500 mt-6">
        Reports are written to the configured output directory. Open files from your reports folder.
      </p>
    </div>
  );
}
