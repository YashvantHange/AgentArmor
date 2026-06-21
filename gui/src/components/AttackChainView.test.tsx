import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AttackChainView } from "./AttackChainView";

describe("AttackChainView", () => {
  it("renders nothing when attack trees and evidence graph are empty", () => {
    const { container } = render(<AttackChainView attackTrees={[]} evidenceGraph={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders attack tree steps and success badge", () => {
    render(
      <AttackChainView
        attackTrees={[
          {
            attack_goal: "prompt_leak",
            attack_tree_id: "tree-1",
            successful: true,
            path: [
              {
                step: "Direct Ask",
                probe_id: "l0.suite.prompt-leak.direct",
                evidence: "leaked system prompt fragment",
              },
              {
                step: "Roleplay",
                probe_id: "l0.suite.prompt-leak.roleplay",
              },
            ],
          },
        ]}
        evidenceGraph={null}
      />
    );

    expect(screen.getByText("Attack chains")).toBeInTheDocument();
    expect(screen.getByText("prompt leak")).toBeInTheDocument();
    expect(screen.getByText("Exploit chain succeeded")).toBeInTheDocument();
    expect(screen.getByText("Direct Ask")).toBeInTheDocument();
    expect(screen.getByText("l0.suite.prompt-leak.direct")).toBeInTheDocument();
    expect(screen.getByText("leaked system prompt fragment")).toBeInTheDocument();
  });

  it("renders evidence graph relationships", () => {
    render(
      <AttackChainView
        attackTrees={[]}
        evidenceGraph={{
          nodes: [
            { id: "finding:a", type: "finding", label: "Prompt Leak" },
            { id: "finding:b", type: "finding", label: "Tool Abuse" },
          ],
          edges: [{ from: "finding:a", to: "finding:b", relation: "escalates_to" }],
        }}
      />
    );

    expect(screen.getByText("Evidence graph")).toBeInTheDocument();
    expect(screen.getByText("Prompt Leak")).toBeInTheDocument();
    expect(screen.getByText("escalates to")).toBeInTheDocument();
    expect(screen.getByText("Tool Abuse")).toBeInTheDocument();
  });
});
