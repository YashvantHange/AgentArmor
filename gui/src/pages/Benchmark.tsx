import { FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";
import { PageHeader } from "../components/layout/PageHeader";
import { FieldGroup, Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { LoadingBlock } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";

interface ModelScore {
  rank: number;
  pass_rate: number;
  risk_score: number;
  target: { label: string; provider?: string };
}

const BENCHMARK_TIMEOUT_MS = 5 * 60 * 1000;

export default function Benchmark() {
  const [providers, setProviders] = useState("openai,anthropic");
  const [suite, setSuite] = useState("owasp");
  const [benchmarkId, setBenchmarkId] = useState<string | null>(null);
  const [scores, setScores] = useState<ModelScore[]>([]);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (!benchmarkId) return;

    const started = Date.now();
    const interval = setInterval(async () => {
      if (Date.now() - started > BENCHMARK_TIMEOUT_MS) {
        clearInterval(interval);
        setRunning(false);
        setError("Benchmark timed out after 5 minutes.");
        return;
      }

      try {
        const data = await api.getBenchmark(benchmarkId);
        const status = String(data.status ?? "");
        if (status === "failed") {
          clearInterval(interval);
          setRunning(false);
          setError(String(data.error ?? "Benchmark failed"));
          return;
        }
        const ms = (data.model_scores as ModelScore[]) || [];
        if (ms.length > 0 || status === "completed") {
          setScores(ms);
          setRunning(false);
          clearInterval(interval);
        }
      } catch {
        /* still running */
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [benchmarkId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setScores([]);
    setRunning(true);
    const list = providers
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    if (list.length === 0) {
      setError("Enter at least one provider.");
      setRunning(false);
      return;
    }
    try {
      const { benchmark_id } = await api.createBenchmark({
        suite,
        targets: list.map((provider) => ({ type: "provider", provider })),
      });
      setBenchmarkId(benchmark_id);
    } catch (err) {
      setRunning(false);
      setError(err instanceof Error ? err.message : "Benchmark failed to start");
    }
  }

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Model benchmark"
        subtitle="Compare provider pass rates using the configured OWASP LLM security suite."
        backTo="/"
      />

      <Card className="mb-8 p-6">
        <form onSubmit={onSubmit}>
          <FieldGroup>
            <Input
              label="Providers"
              name="providers"
              value={providers}
              onChange={(e) => setProviders(e.target.value)}
              placeholder="openai,anthropic,gemini"
              hint="Comma-separated LiteLLM provider identifiers"
            />
            <Input
              label="Suite"
              name="suite"
              value={suite}
              onChange={(e) => setSuite(e.target.value)}
              placeholder="owasp"
            />
          </FieldGroup>
          <div className="mt-6">
            <Button type="submit" disabled={running}>
              {running ? "Running benchmark…" : "Run benchmark"}
            </Button>
          </div>
        </form>
      </Card>

      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {running && scores.length === 0 && (
        <LoadingBlock label={`Executing benchmark ${benchmarkId ?? ""}…`} />
      )}

      {!running && scores.length === 0 && benchmarkId && !error && (
        <EmptyState title="No scores returned" description="The benchmark completed without model score data." />
      )}

      {scores.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="border-b border-surface-border bg-surface-overlay text-xs uppercase tracking-wide text-ink-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Rank</th>
                  <th className="px-4 py-3 font-medium">Target</th>
                  <th className="px-4 py-3 font-medium">Pass rate</th>
                  <th className="px-4 py-3 font-medium">Risk</th>
                  <th className="px-4 py-3 font-medium">Coverage</th>
                </tr>
              </thead>
              <tbody>
                {scores.map((s, i) => (
                  <tr key={`${s.target.label}-${i}`} className="border-t border-surface-border">
                    <td className="px-4 py-3 font-mono text-ink-muted">#{s.rank}</td>
                    <td className="px-4 py-3 font-medium text-ink-primary">{s.target.label}</td>
                    <td className="px-4 py-3">
                      <Badge tone={s.pass_rate >= 0.8 ? "brand" : s.pass_rate >= 0.5 ? "medium" : "high"}>
                        {(s.pass_rate * 100).toFixed(0)}%
                      </Badge>
                    </td>
                    <td className="px-4 py-3 font-mono text-ink-secondary">{s.risk_score.toFixed(2)}</td>
                    <td className="px-4 py-3">
                      <div className="h-2 w-32 overflow-hidden rounded-full bg-surface-border">
                        <div
                          className="h-full rounded-full bg-brand-500"
                          style={{ width: `${Math.min(100, s.pass_rate * 100)}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
