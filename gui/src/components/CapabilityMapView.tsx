import { Badge } from "./ui/Badge";
import { Card } from "./ui/Card";

export interface CapabilityMapData {
  framework?: string | null;
  rag: boolean;
  memory: boolean;
  mcp: boolean;
  a2a: boolean;
  tools: string[];
  agentic_score: number;
  risk_score: number;
  risk_reasons: string[];
}

export interface AgentRiskData {
  tool_count: number;
  rag_enabled: boolean;
  memory_enabled: boolean;
  mcp_enabled: boolean;
  external_actions: boolean;
  agentic_score: number;
  risk_score: number;
  risk_reasons: string[];
}

interface Props {
  capability: CapabilityMapData;
  risk?: AgentRiskData | null;
}

function ScoreBar({ label, value, max = 10 }: { label: string; value: number; max?: number }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-ink-muted">
        <span>{label}</span>
        <span>{value.toFixed(1)}{max === 1 ? "" : `/${max}`}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-border">
        <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function CapabilityMapView({ capability, risk }: Props) {
  const reasons = risk?.risk_reasons?.length ? risk.risk_reasons : capability.risk_reasons;

  return (
    <Card className="space-y-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink-primary">Capability Map</h3>
        {capability.framework && <Badge tone="brand">{capability.framework}</Badge>}
      </div>

      <div className="flex flex-wrap gap-2">
        {capability.rag && <Badge tone="default">RAG</Badge>}
        {capability.memory && <Badge tone="default">Memory</Badge>}
        {capability.mcp && <Badge tone="default">MCP</Badge>}
        {capability.a2a && <Badge tone="default">A2A</Badge>}
        {!capability.rag && !capability.memory && !capability.mcp && !capability.a2a && (
          <span className="text-xs text-ink-muted">No advanced agentic signals detected</span>
        )}
      </div>

      {capability.tools.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-ink-muted">Tools detected</p>
          <p className="text-sm text-ink-primary">{capability.tools.join(" · ")}</p>
        </div>
      )}

      <ScoreBar label="Agentic score" value={capability.agentic_score} max={1} />
      <ScoreBar label="Agent risk score" value={capability.risk_score} max={10} />

      {reasons.length > 0 && (
        <ul className="list-inside list-disc space-y-1 text-xs text-ink-muted">
          {reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function AgentRiskCard({ risk }: { risk: AgentRiskData }) {
  return (
    <Card className="border-brand-500/30 bg-brand-500/5 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">Agent Risk Score</p>
      <p className="mt-1 text-3xl font-bold text-ink-primary">{risk.risk_score.toFixed(1)}<span className="text-lg font-normal text-ink-muted">/10</span></p>
      {risk.risk_reasons.length > 0 && (
        <ul className="mt-3 list-inside list-disc space-y-1 text-sm text-ink-muted">
          {risk.risk_reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
    </Card>
  );
}
