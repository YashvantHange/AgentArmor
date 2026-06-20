import { FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";

interface ModelScore {
  rank: number;
  pass_rate: number;
  risk_score: number;
  target: { label: string; provider?: string };
}

export default function Benchmark() {
  const [providers, setProviders] = useState("openai,anthropic");
  const [suite, setSuite] = useState("owasp");
  const [benchmarkId, setBenchmarkId] = useState<string | null>(null);
  const [scores, setScores] = useState<ModelScore[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!benchmarkId) return;
    const interval = setInterval(async () => {
      try {
        const data = await api.getBenchmark(benchmarkId);
        const ms = (data.model_scores as ModelScore[]) || [];
        if (ms.length > 0) {
          setScores(ms);
          clearInterval(interval);
        }
      } catch {
        /* still running */
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [benchmarkId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setScores([]);
    const list = providers.split(",").map((p) => p.trim()).filter(Boolean);
    try {
      const { benchmark_id } = await api.createBenchmark({
        suite,
        targets: list.map((provider) => ({ type: "provider", provider })),
      });
      setBenchmarkId(benchmark_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Benchmark failed");
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Model Benchmark</h1>
      <form onSubmit={onSubmit} className="flex flex-wrap gap-3 mb-8">
        <input
          value={providers}
          onChange={(e) => setProviders(e.target.value)}
          placeholder="openai,anthropic,gemini"
          className="flex-1 min-w-[200px] px-3 py-2 rounded-lg bg-slate-800 border border-slate-600"
        />
        <input
          value={suite}
          onChange={(e) => setSuite(e.target.value)}
          className="w-32 px-3 py-2 rounded-lg bg-slate-800 border border-slate-600"
        />
        <button type="submit" className="px-4 py-2 rounded-lg bg-armor-700 hover:bg-armor-500">
          Run Benchmark
        </button>
      </form>
      {error && <p className="text-red-400 mb-4">{error}</p>}
      {benchmarkId && scores.length === 0 && (
        <p className="text-slate-400">Running benchmark {benchmarkId}…</p>
      )}
      {scores.length > 0 && (
        <div className="rounded-xl border border-slate-700 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-slate-800">
              <tr>
                <th className="p-3">#</th>
                <th className="p-3">Model</th>
                <th className="p-3">Pass Rate</th>
                <th className="p-3">Risk</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {scores.map((s) => (
                <tr key={s.target.label} className="border-t border-slate-800">
                  <td className="p-3">{s.rank}</td>
                  <td className="p-3 font-medium">{s.target.label}</td>
                  <td className="p-3">{(s.pass_rate * 100).toFixed(0)}%</td>
                  <td className="p-3">{s.risk_score.toFixed(2)}</td>
                  <td className="p-3 w-32">
                    <div className="h-2 bg-slate-700 rounded">
                      <div
                        className="h-2 bg-green-500 rounded"
                        style={{ width: `${s.pass_rate * 100}%` }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
