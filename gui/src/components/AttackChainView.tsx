import { AttackTree } from "../api/client";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";

export interface EvidenceGraphNode {
  id: string;
  type: string;
  label: string;
  severity?: string;
  owasp?: string[];
  probe_id?: string;
  successful?: boolean;
}

export interface EvidenceGraphEdge {
  from: string;
  to: string;
  relation: string;
  attack_goal?: string;
}

export interface EvidenceGraph {
  nodes: EvidenceGraphNode[];
  edges: EvidenceGraphEdge[];
}

const RELATION_LABELS: Record<string, string> = {
  escalates_to: "escalates to",
  enables: "enables",
  same_session: "same session",
  contains_step: "contains",
};

export function AttackChainView({
  attackTrees,
  evidenceGraph,
}: {
  attackTrees: AttackTree[];
  evidenceGraph: EvidenceGraph | null;
}) {
  if (attackTrees.length === 0 && (!evidenceGraph || evidenceGraph.nodes.length === 0)) {
    return null;
  }

  return (
    <div className="mb-8 space-y-4">
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Attack chains
        </h2>
        <p className="mt-1 text-xs text-ink-muted">
          Exploit paths and cross-finding relationships from L0 attack generation.
        </p>
      </div>

      {attackTrees.length > 0 && (
        <div className="space-y-3">
          {attackTrees.map((tree) => (
            <Card key={tree.attack_tree_id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-ink-primary">
                  {tree.attack_goal.replace(/_/g, " ")}
                </h3>
                <Badge tone={tree.successful ? "critical" : "default"}>
                  {tree.successful ? "Exploit chain succeeded" : "Partial chain"}
                </Badge>
              </div>
              <ol className="mt-3 space-y-2 border-l-2 border-brand-500/40 pl-4">
                {tree.path.map((step, idx) => (
                  <li key={`${step.probe_id}-${idx}`} className="relative text-sm">
                    <span className="absolute -left-[1.35rem] top-1.5 h-2 w-2 rounded-full bg-brand-500" />
                    <div className="font-medium text-ink-primary">{step.step}</div>
                    <div className="font-mono text-xs text-ink-muted">{step.probe_id}</div>
                    {step.evidence && (
                      <p className="mt-1 line-clamp-2 text-xs text-ink-secondary">{step.evidence}</p>
                    )}
                  </li>
                ))}
              </ol>
            </Card>
          ))}
        </div>
      )}

      {evidenceGraph && evidenceGraph.edges.length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-semibold text-ink-primary">Evidence graph</h3>
          <ul className="mt-3 space-y-2 text-sm text-ink-secondary">
            {evidenceGraph.edges.slice(0, 24).map((edge, idx) => {
              const fromNode = evidenceGraph.nodes.find((n) => n.id === edge.from);
              const toNode = evidenceGraph.nodes.find((n) => n.id === edge.to);
              const rel = RELATION_LABELS[edge.relation] ?? edge.relation;
              return (
                <li key={`${edge.from}-${edge.to}-${idx}`} className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-surface px-2 py-0.5 text-xs font-medium text-ink-primary">
                    {fromNode?.label ?? edge.from}
                  </span>
                  <span className="text-xs text-ink-muted">{rel}</span>
                  <span className="rounded bg-surface px-2 py-0.5 text-xs font-medium text-ink-primary">
                    {toNode?.label ?? edge.to}
                  </span>
                </li>
              );
            })}
          </ul>
          {evidenceGraph.edges.length > 24 && (
            <p className="mt-2 text-xs text-ink-muted">
              +{evidenceGraph.edges.length - 24} more relationships
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
