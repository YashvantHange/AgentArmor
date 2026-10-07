import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, SwarmGoal } from "../api/client";
import { AnalysisModePicker, AnalysisModeValue } from "../components/AnalysisModePicker";
import { PageHeader } from "../components/layout/PageHeader";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader } from "../components/ui/Card";
import { FieldGroup, Input } from "../components/ui/Input";
import { LoadingBlock } from "../components/ui/Spinner";

/**
 * Swarm launch.
 *
 * Goals are preset cards, not a text box. A swarm pursues a fixed catalog so there
 * is no free-text instruction to sanitise, and the API has no field for one.
 *
 * The coverage line under the sliders is a requirement rather than decoration: a
 * large roster against a shallow target is mostly persona and strategy variation,
 * and showing an agent count on its own would imply far more distinct attack
 * classes than a run actually has.
 */

const LARGE_SWARM_THRESHOLD = 50;

export default function SwarmLaunch() {
  const navigate = useNavigate();
  const [goals, setGoals] = useState<SwarmGoal[] | null>(null);
  const [goalId, setGoalId] = useState("");
  const [url, setUrl] = useState("");
  const [agents, setAgents] = useState(24);
  const [concurrency, setConcurrency] = useState(8);
  const [analysis, setAnalysis] = useState<AnalysisModeValue>({ analysis_mode: "cloud" });
  const [error, setError] = useState<string | null>(null);
  const [launching, setLaunching] = useState(false);

  useEffect(() => {
    let active = true;
    // Reuse whatever analysis provider the user already configured.
    api
      .getSettings()
      .then((settings) => {
        if (!active) return;
        setAnalysis({
          analysis_mode: "cloud",
          analysis_provider: settings.analysis_provider,
          analysis_model: settings.analysis_model,
          analysis_api_key: settings.analysis_api_key,
        });
      })
      .catch(() => undefined);
    api
      .listSwarmGoals()
      .then((loaded) => {
        if (!active) return;
        setGoals(loaded);
        if (loaded.length > 0) {
          setGoalId(loaded[0].id);
          setAgents(loaded[0].suggested_agents);
        }
      })
      .catch((err: Error) => active && setError(err.message));
    return () => {
      active = false;
    };
  }, []);

  const maxAgents = goals?.[0]?.max_agents ?? 100;
  const selected = goals?.find((goal) => goal.id === goalId) ?? null;

  async function launch() {
    setError(null);
    if (!goalId) {
      setError("Choose a goal.");
      return;
    }
    if (!url.trim()) {
      setError("A target URL is required. Use the POST API URL, not the web page.");
      return;
    }
    setLaunching(true);
    try {
      const created = await api.createSwarm({
        target_type: "endpoint",
        url: url.trim(),
        goal_id: goalId,
        agents,
        max_concurrent: concurrency,
        formats: ["json", "html", "sarif", "pdf"],
        analysis_provider: analysis.analysis_provider,
        analysis_model: analysis.analysis_model,
        analysis_api_key: analysis.analysis_api_key,
      });
      navigate(`/swarm/progress/${created.scan_id}`);
    } catch (err) {
      setError((err as Error).message);
      setLaunching(false);
    }
  }

  if (!goals) {
    return (
      <div>
        <PageHeader title="Launch a swarm" backTo="/" />
        <LoadingBlock />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Launch a swarm"
        subtitle="Many specialized agents pursue one goal together, sharing what they find as they go."
        backTo="/"
      />

      {error && <Alert tone="error">{error}</Alert>}

      <Card className="p-5">
        <CardHeader title="Goal" subtitle="Pick what the swarm should try to achieve." />
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {goals.map((goal) => {
            const active = goal.id === goalId;
            return (
              <button
                key={goal.id}
                type="button"
                onClick={() => setGoalId(goal.id)}
                className={`focus-ring rounded-lg border p-3 text-left transition-colors ${
                  active
                    ? "border-brand-500/50 bg-brand-500/10"
                    : "border-surface-border bg-surface-overlay hover:border-surface-border-strong"
                }`}
                aria-pressed={active}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-ink-primary">{goal.name}</span>
                  <div className="flex gap-1">
                    {goal.owasp.map((code) => (
                      <Badge key={code} tone="brand">
                        {code}
                      </Badge>
                    ))}
                  </div>
                </div>
                <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">{goal.description}</p>
              </button>
            );
          })}
        </div>
      </Card>

      <Card className="p-5">
        <CardHeader title="Target" />
        <div className="mt-3">
          <FieldGroup>
            <Input
              label="Chat API URL"
              name="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="http://localhost:8000/v1/chat/completions"
              hint="The POST endpoint from DevTools, not the HTML page."
            />
          </FieldGroup>
        </div>
      </Card>

      <Card className="p-5">
        <CardHeader title="Size" subtitle="How many agents, and how many talk to the target at once." />
        <div className="mt-4 space-y-5">
          <label className="block">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">
                Agents
              </span>
              <span className="font-mono text-sm text-ink-primary">{agents}</span>
            </div>
            <input
              type="range"
              min={4}
              max={maxAgents}
              step={4}
              value={agents}
              onChange={(event) => setAgents(Number(event.target.value))}
              className="focus-ring mt-2 w-full accent-brand-500"
              aria-label="Number of agents"
            />
          </label>

          <label className="block">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">
                Concurrency
              </span>
              <span className="font-mono text-sm text-ink-primary">{concurrency}</span>
            </div>
            <input
              type="range"
              min={1}
              max={16}
              step={1}
              value={concurrency}
              onChange={(event) => setConcurrency(Number(event.target.value))}
              className="focus-ring mt-2 w-full accent-brand-500"
              aria-label="Concurrent agents"
            />
            <p className="mt-1.5 text-xs text-ink-muted">
              How many agents contact your target simultaneously. Your target's configured rate
              limit still applies on top of this.
            </p>
          </label>

          <p className="rounded-lg border border-surface-border bg-surface-overlay px-3 py-2 font-mono text-[11px] text-ink-secondary">
            {agents} agents · up to {concurrency} at once
            {selected ? ` · goal ${selected.id}` : ""}
          </p>

          {agents > LARGE_SWARM_THRESHOLD && (
            <Alert tone="warning">
              Large swarms send considerably more traffic to your target and cost more to run. Only
              run this against systems you own or are authorised to test.
            </Alert>
          )}
        </div>
      </Card>

      <AnalysisModePicker value={analysis} onChange={setAnalysis} />

      <div className="flex justify-end">
        <Button size="lg" onClick={launch} disabled={launching}>
          {launching ? "Starting…" : "Launch swarm"}
        </Button>
      </div>
    </div>
  );
}
