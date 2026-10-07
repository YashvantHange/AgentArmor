import { SwarmFact } from "../api/client";
import { Badge } from "./ui/Badge";
import { Card, CardHeader } from "./ui/Card";
import { EmptyState } from "./ui/EmptyState";

/**
 * The shared fact store, rendered.
 *
 * This panel is the only place the product's central claim becomes visible: that a
 * discovery made by one agent is handed to the others while the run is still going.
 * Each fact names the member that found it, so "agent 7's secret reached agents
 * 8 onward" is something a user can see rather than take on trust.
 */

const KIND_TONES: Record<string, "critical" | "high" | "medium" | "brand" | "info" | "default"> = {
  secret: "critical",
  system_prompt: "high",
  pii: "high",
  bypass: "medium",
  tool_name: "brand",
  capability: "brand",
  policy: "info",
  refusal_style: "info",
  observation: "default",
};

function kindTone(kind: string) {
  return KIND_TONES[kind] ?? "default";
}

export function BlackboardPanel({
  facts,
  quarantined = 0,
  limit = 12,
}: {
  facts: SwarmFact[];
  quarantined?: number;
  limit?: number;
}) {
  return (
    <Card>
      <CardHeader
        title="Shared blackboard"
        subtitle="What each agent learned, available to every agent that starts after it"
      />
      {facts.length === 0 ? (
        <EmptyState
          title="No shared facts yet"
          description="Facts appear here as agents discover secrets, prompt text, tools or refusal patterns."
        />
      ) : (
        <ul className="divide-y divide-surface-border">
          {facts.slice(0, limit).map((fact) => (
            <li key={fact.fact_id} className="py-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={kindTone(fact.kind)}>{fact.kind.replace(/_/g, " ")}</Badge>
                <Badge tone={fact.provenance === "verified" ? "brand" : "info"}>
                  {fact.provenance}
                </Badge>
                {fact.hits > 1 && (
                  // Independent corroboration across members is a real signal.
                  <span className="text-[11px] text-ink-muted">
                    confirmed by {fact.hits} agents
                  </span>
                )}
              </div>
              <p className="mt-1 break-words font-mono text-xs text-ink-primary">{fact.value}</p>
              <p className="mt-0.5 text-[11px] text-ink-muted">
                discovered by {fact.source_member_id}
                {fact.node_id ? ` on ${fact.node_id}` : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
      {facts.length > limit && (
        <p className="pt-2 text-[11px] text-ink-muted">
          and {facts.length - limit} more in the report
        </p>
      )}
      {quarantined > 0 && (
        // Kept out of other agents' prompts, but still worth reporting: a target
        // echoing an injection is itself a finding.
        <p className="pt-2 text-[11px] text-ink-muted">
          {quarantined} observation{quarantined === 1 ? "" : "s"} withheld from agents as
          instruction-shaped. They appear in the report.
        </p>
      )}
    </Card>
  );
}
