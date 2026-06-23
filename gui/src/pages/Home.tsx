import { Link } from "react-router-dom";
import type { ScanType } from "../api/client";
import { Card, CardHeader } from "../components/ui/Card";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import {
  BotIcon,
  ChartIcon,
  CloudIcon,
  DatabaseIcon,
  GlobeIcon,
  PlugIcon,
  ServerIcon,
  ShieldIcon,
} from "../components/icons";

const TILES: {
  type: ScanType;
  title: string;
  desc: string;
  icon: typeof GlobeIcon;
}[] = [
  { type: "endpoint", title: "API Endpoint", desc: "OpenAI-compatible HTTP APIs and gateways", icon: GlobeIcon },
  { type: "provider", title: "Cloud Provider", desc: "OpenAI, Anthropic, Gemini, and other hosted models", icon: CloudIcon },
  { type: "local", title: "Local Model", desc: "Offline GGUF weights and HuggingFace checkpoints", icon: ServerIcon },
  { type: "agent", title: "Agent Framework", desc: "CrewAI, LangGraph, and autonomous agent stacks", icon: BotIcon },
  { type: "mcp", title: "MCP Server", desc: "Model Context Protocol tool surfaces and abuse paths", icon: PlugIcon },
  { type: "rag", title: "RAG Corpus", desc: "Retrieval pipelines, poisoning, and data leakage", icon: DatabaseIcon },
];

export default function Home() {
  return (
    <div>
      <PageHeader
        title="Security validation"
        subtitle="Run structured probes against AI endpoints, providers, agents, and retrieval systems. Results include SARIF, HTML, PDF, and JSON exports."
      />

      <section className="mb-10 rounded-xl border border-brand-500/30 bg-gradient-to-br from-brand-500/10 to-surface-raised p-6 shadow-panel sm:flex sm:items-center sm:justify-between">
        <div className="flex gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-500/20 text-brand-600 dark:text-brand-400">
            <ShieldIcon className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink-primary">Test my chatbot</h2>
            <p className="mt-1 max-w-md text-sm text-ink-muted">
              Scan via website URL (browser) or connect your chat API directly for jailbreak, leak, and policy probes.
            </p>
          </div>
        </div>
        <div className="mt-4 flex flex-col gap-2 sm:mt-0">
          <Link to="/chatbot/website">
            <Button className="w-full sm:w-auto">Test via website URL</Button>
          </Link>
          <Link to="/chatbot">
            <Button variant="secondary" className="w-full sm:w-auto">
              Test via API URL
            </Button>
          </Link>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-muted">Scan targets</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {TILES.map((t) => {
            const Icon = t.icon;
            return (
              <Link key={t.type} to={`/scan/${t.type}`} className="group block focus-ring rounded-xl">
                <Card hover className="h-full p-5">
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-surface-overlay text-brand-400 ring-1 ring-surface-border group-hover:shadow-glow">
                    <Icon className="h-5 w-5" />
                  </div>
                  <CardHeader title={t.title} subtitle={t.desc} />
                  <div className="mt-4 text-xs font-medium text-brand-400 opacity-0 transition-opacity group-hover:opacity-100">
                    Configure scan →
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="mt-10 rounded-xl border border-surface-border bg-surface-raised p-5 shadow-panel sm:flex sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-ink-primary">Benchmarks</h2>
          <p className="mt-1 text-sm text-ink-muted">
            Model leaderboards and tools comparison (AgentArmor vs PyRIT, Garak, Promptfoo, Inspect AI).
          </p>
        </div>
        <Link to="/benchmark" className="mt-4 block sm:mt-0">
          <Button variant="secondary">
            <ChartIcon className="h-4 w-4" />
            Open benchmark
          </Button>
        </Link>
      </section>
    </div>
  );
}
