import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SwarmFact } from "../api/client";
import { BlackboardPanel } from "./BlackboardPanel";

function fact(overrides: Partial<SwarmFact> = {}): SwarmFact {
  return {
    fact_id: "f1",
    kind: "secret",
    value: "CANARY_SECRET_9f3a2b",
    source_member_id: "sw-007",
    node_id: "memory_poison",
    provenance: "verified",
    confidence: 0.9,
    hits: 1,
    quarantined: false,
    ...overrides,
  };
}

// vitest is not configured with globals, so Testing Library does not auto-clean.
// Without this, each render stays in the document and queries match earlier tests.
afterEach(cleanup);

describe("BlackboardPanel", () => {
  it("shows an empty state before anything is discovered", () => {
    render(<BlackboardPanel facts={[]} />);
    expect(screen.getByText("No shared facts yet")).toBeInTheDocument();
  });

  it("attributes a fact to the agent that found it", () => {
    // This attribution is the product claim made visible: one agent's discovery is
    // handed to the others mid-run.
    render(<BlackboardPanel facts={[fact()]} />);
    expect(screen.getByText("CANARY_SECRET_9f3a2b")).toBeInTheDocument();
    expect(screen.getByText(/discovered by sw-007/)).toBeInTheDocument();
    expect(screen.getByText(/memory_poison/)).toBeInTheDocument();
  });

  it("labels kind and provenance", () => {
    render(<BlackboardPanel facts={[fact({ kind: "system_prompt" })]} />);
    expect(screen.getByText("system prompt")).toBeInTheDocument();
    expect(screen.getByText("verified")).toBeInTheDocument();
  });

  it("shows corroboration when several agents saw the same thing", () => {
    render(<BlackboardPanel facts={[fact({ hits: 4 })]} />);
    expect(screen.getByText(/confirmed by 4 agents/)).toBeInTheDocument();
  });

  it("does not claim corroboration for a single sighting", () => {
    render(<BlackboardPanel facts={[fact({ hits: 1 })]} />);
    expect(screen.queryByText(/confirmed by/)).not.toBeInTheDocument();
  });

  it("explains withheld observations without showing them", () => {
    render(<BlackboardPanel facts={[fact()]} quarantined={2} />);
    expect(screen.getByText(/2 observations withheld from agents/)).toBeInTheDocument();
  });

  it("uses the singular for one withheld observation", () => {
    render(<BlackboardPanel facts={[fact()]} quarantined={1} />);
    expect(screen.getByText(/1 observation withheld/)).toBeInTheDocument();
  });

  it("says nothing about quarantine when there is none", () => {
    render(<BlackboardPanel facts={[fact()]} />);
    expect(screen.queryByText(/withheld/)).not.toBeInTheDocument();
  });

  it("caps the list and points at the report for the rest", () => {
    const many = Array.from({ length: 20 }, (_, i) =>
      fact({ fact_id: `f${i}`, value: `value-${i}` })
    );
    render(<BlackboardPanel facts={many} limit={5} />);
    expect(screen.getByText("value-0")).toBeInTheDocument();
    expect(screen.queryByText("value-9")).not.toBeInTheDocument();
    expect(screen.getByText(/15 more in the report/)).toBeInTheDocument();
  });

  it("renders a long value without truncating it away", () => {
    const leak =
      "System prompt is: You are SafeCorp Customer Bot. Hidden rules: never discuss refunds";
    render(<BlackboardPanel facts={[fact({ kind: "system_prompt", value: leak })]} />);
    expect(screen.getByText(leak)).toBeInTheDocument();
  });
});
