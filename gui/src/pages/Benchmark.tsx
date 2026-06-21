import { FormEvent, ReactNode, useEffect, useState } from "react";
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

interface ToolScore {
  tool: string;
  detection_rate: number | null;
  status: string;
  detail?: string;
}

const BENCHMARK_TIMEOUT_MS = 5 * 60 * 1000;

type BenchmarkTab = "models" | "tools";

export default function Benchmark() {
  const [tab, setTab] = useState<BenchmarkTab>("models");
  const [providers, setProviders] = useState("openai,anthropic");
  const [suite, setSuite] = useState("owasp");
  const [toolsSuite, setToolsSuite] = useState("owasp-llm01");
  const [toolsTargets, setToolsTargets] = useState("corpus");
  const [benchmarkId, setBenchmarkId] = useState<string | null>(null);
  const [scores, setScores] = useState<ModelScore[]>([]);
  const [toolScores, setToolScores] = useState<ToolScore[]>([]);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (!benchmarkId) return;

    const started = Date.now();
    const isTools = tab === "tools";
    const interval = setInterval(async () => {
      if (Date.now() - started > BENCHMARK_TIMEOUT_MS) {
        clearInterval(interval);
        setRunning(false);
        setError("Benchmark timed out after 5 minutes.");
        return;
      }

      try {
        const data = isTools
          ? await api.getToolsBenchmark(benchmarkId)
          : await api.getBenchmark(benchmarkId);
        const status = String(data.status ?? "");
        if (status === "failed") {
          clearInterval(interval);
          setRunning(false);
          setError(String(data.error ?? "Benchmark failed"));
          return;
        }
        if (isTools) {
          const ts = (data.tool_scores as ToolScore[]) || [];
          if (ts.length > 0 || status === "completed") {
            setToolScores(ts);
            setRunning(false);
            clearInterval(interval);
          }
        } else {
          const ms = (data.model_scores as ModelScore[]) || [];
          if (ms.length > 0 || status === "completed") {
            setScores(ms);
            setRunning(false);
            clearInterval(interval);
          }
        }
      } catch {
        /* still running */
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [benchmarkId, tab]);

  async function onSubmitModels(e: FormEvent) {
    e.preventDefault();
    setError("");
    setScores([]);
    setToolScores([]);
    setRunning(true);
    setTab("models");
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

  async function onSubmitTools(e: FormEvent) {
    e.preventDefault();
    setError("");
    setScores([]);
    setToolScores([]);
    setRunning(true);
    setTab("tools");
    const targets = toolsTargets
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    try {
      const { benchmark_id } = await api.createToolsBenchmark({
        suite: toolsSuite,
        targets: targets.length ? targets : ["corpus"],
      });
      setBenchmarkId(benchmark_id);
    } catch (err) {
      setRunning(false);
      setError(err instanceof Error ? err.message : "Tools benchmark failed to start");
    }
  }

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Benchmarks"
        subtitle="Compare model pass rates or red-team tool detection on shared OWASP scenarios."
        backTo="/"
      />

      <div className="mb-6 flex gap-2">
        <TabButton active={tab === "models"} onClick={() => setTab("models")}>
          Model leaderboard
        </TabButton>
        <TabButton active={tab === "tools"} onClick={() => setTab("tools")}>
          Tools comparison
        </TabButton>
      </div>

      {tab === "models" && (
        <Card className="mb-8 p-6">
          <form onSubmit={onSubmitModels}>
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
              <Button type="submit" disabled={running && tab === "models"}>
                {running && tab === "models" ? "Running benchmark…" : "Run model benchmark"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {tab === "tools" && (
        <Card className="mb-8 p-6">
          <form onSubmit={onSubmitTools}>
            <FieldGroup>
              <Input
                label="Suite"
                name="toolsSuite"
                value={toolsSuite}
                onChange={(e) => setToolsSuite(e.target.value)}
                placeholder="owasp-llm01"
                hint="owasp-llm01, owasp-llm07, or corpus alias"
              />
              <Input
                label="Targets"
                name="toolsTargets"
                value={toolsTargets}
                onChange={(e) => setToolsTargets(e.target.value)}
                placeholder="corpus,dvllm,localhost"
                hint="Comma-separated — corpus uses built-in vulnerability fixtures"
              />
            </FieldGroup>
            <p className="mt-3 text-xs text-ink-muted">
              Compares AgentArmor vs PyRIT, Garak, Promptfoo, and Inspect AI on the same scenario
              corpus. External tools use CLI when installed, otherwise reference baselines.
            </p>
            <div className="mt-6">
              <Button type="submit" disabled={running && tab === "tools"}>
                {running && tab === "tools" ? "Running comparison…" : "Run tools comparison"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {running && scores.length === 0 && toolScores.length === 0 && (
        <LoadingBlock label={`Executing ${tab === "tools" ? "tools comparison" : "benchmark"} ${benchmarkId ?? ""}…`} />
      )}

      {tab === "models" && scores.length > 0 && (
        <ModelScoresTable scores={scores} />
      )}

      {tab === "tools" && toolScores.length > 0 && (
        <ToolsScoresTable scores={toolScores} />
      )}

      {!running && tab === "models" && scores.length === 0 && benchmarkId && !error && (
        <EmptyState title="No scores returned" description="The benchmark completed without model score data." />
      )}

      {!running && tab === "tools" && toolScores.length === 0 && benchmarkId && !error && (
        <EmptyState title="No tool scores returned" description="The tools comparison completed without scores." />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors focus-ring ${
        active
          ? "border-brand-500 bg-brand-500/10 text-brand-600 dark:text-brand-400"
          : "border-surface-border text-ink-muted hover:border-surface-border-strong"
      }`}
    >
      {children}
    </button>
  );
}

function ModelScoresTable({ scores }: { scores: ModelScore[] }) {
  return (
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
  );
}

function ToolsScoresTable({ scores }: { scores: ToolScore[] }) {
  const sorted = [...scores].sort(
    (a, b) => (b.detection_rate ?? -1) - (a.detection_rate ?? -1)
  );
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-surface-border bg-surface-overlay text-xs uppercase tracking-wide text-ink-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Tool</th>
              <th className="px-4 py-3 font-medium">Detection rate</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Detail</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((s) => (
              <tr key={s.tool} className="border-t border-surface-border">
                <td className="px-4 py-3 font-medium text-ink-primary">{s.tool}</td>
                <td className="px-4 py-3">
                  {s.detection_rate != null ? (
                    <Badge tone={s.detection_rate >= 85 ? "brand" : s.detection_rate >= 70 ? "medium" : "high"}>
                      {s.detection_rate.toFixed(0)}%
                    </Badge>
                  ) : (
                    "N/A"
                  )}
                </td>
                <td className="px-4 py-3 text-ink-muted">{s.status}</td>
                <td className="px-4 py-3 text-xs text-ink-muted">{s.detail || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
