import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockEventSource, installMockEventSource } from "../test/eventSourceMock";
import { SWARM_NAMED_EVENTS, storageKey, useSwarmEvents } from "./useSwarmEvents";

describe("useSwarmEvents", () => {
  beforeEach(() => {
    installMockEventSource();
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    MockEventSource.reset();
  });

  it("subscribes to every swarm event name", () => {
    renderHook(() => useSwarmEvents("scan-1"));
    const source = MockEventSource.latest();
    SWARM_NAMED_EVENTS.forEach((name) => {
      expect(source.subscribed(name), `not subscribed to ${name}`).toBe(true);
    });
  });

  it("drops an event it did not subscribe to", () => {
    // The stream is read with named addEventListener, so an unlisted name never
    // reaches the reducer. This is why the backend's names and this list must agree.
    const { result } = renderHook(() => useSwarmEvents("scan-1"));
    const source = MockEventSource.latest();
    act(() => source.emit("totally.unknown", { member_id: "sw-001" }));
    expect(result.current.log).toHaveLength(0);
    expect(result.current.agents.size).toBe(0);
  });

  it("updates an agent row in place instead of appending", () => {
    const { result } = renderHook(() => useSwarmEvents("scan-1"));
    const source = MockEventSource.latest();

    act(() =>
      source.emit("swarm.roster", {
        members: [{ member_id: "sw-001", node_id: "n1", path_id: "p", persona_id: "x" }],
      })
    );
    act(() => source.emit("agent.started", { member_id: "sw-001", node_id: "n1" }));
    act(() =>
      source.emit("agent.completed", { member_id: "sw-001", node_id: "n1", vulnerable: true })
    );

    expect(result.current.agents.size).toBe(1);
    expect(result.current.agents.get("sw-001")?.status).toBe("done");
    expect(result.current.agents.get("sw-001")?.vulnerable).toBe(true);
  });

  it("keeps the raw log bounded under a long run", () => {
    const { result } = renderHook(() => useSwarmEvents("scan-1"));
    const source = MockEventSource.latest();
    act(() => {
      for (let i = 0; i < 500; i += 1) {
        source.emit("swarm.progress", { completed: i, total: 500 });
      }
    });
    expect(result.current.log.length).toBeLessThanOrEqual(200);
  });

  it("closes the stream on the terminator", () => {
    const { result } = renderHook(() => useSwarmEvents("scan-1"));
    const source = MockEventSource.latest();
    expect(source.closed).toBe(false);
    act(() => source.emit("scan.completed", { status: "completed", finding_count: 1 }));
    expect(source.closed).toBe(true);
    expect(result.current.done).toBe(true);
  });

  it("surfaces a dropped connection", () => {
    const { result } = renderHook(() => useSwarmEvents("scan-1"));
    const source = MockEventSource.latest();
    act(() => source.onerror?.call(source as unknown as EventSource, new Event("error")));
    expect(result.current.error).toContain("lost");
  });

  it("does not report an error after a normal finish", () => {
    const { result } = renderHook(() => useSwarmEvents("scan-1"));
    const source = MockEventSource.latest();
    act(() => source.emit("scan.completed", { status: "completed" }));
    act(() => source.onerror?.call(source as unknown as EventSource, new Event("error")));
    expect(result.current.error).toBeNull();
  });

  it("deduplicates facts", () => {
    const { result } = renderHook(() => useSwarmEvents("scan-1"));
    const source = MockEventSource.latest();
    const fact = {
      fact_id: "abc",
      kind: "secret",
      value: "CANARY",
      source_member_id: "sw-001",
      provenance: "verified",
      confidence: 0.9,
      hits: 1,
      quarantined: false,
    };
    act(() => source.emit("blackboard.fact", fact));
    act(() => source.emit("blackboard.fact", fact));
    expect(result.current.facts).toHaveLength(1);
  });

  it("persists a derived snapshot rather than the raw event list", async () => {
    vi.useFakeTimers();
    try {
      renderHook(() => useSwarmEvents("scan-2"));
      const source = MockEventSource.latest();
      act(() =>
        source.emit("swarm.roster", {
          members: [{ member_id: "sw-001", node_id: "n1", path_id: "p", persona_id: "x" }],
        })
      );
      act(() => vi.advanceTimersByTime(1500));

      const raw = sessionStorage.getItem(storageKey("scan-2"));
      expect(raw).toBeTruthy();
      const snapshot = JSON.parse(raw as string);
      expect(Array.isArray(snapshot.agents)).toBe(true);
      expect(snapshot.agents[0].member_id).toBe("sw-001");
      // The event list itself is never stored; that is what made the scan hook's
      // per-append rewrite expensive.
      expect(snapshot.log).toBeUndefined();
    } finally {
      vi.useRealTimers();
    }
  });

  it("creates no stream without a scan id", () => {
    renderHook(() => useSwarmEvents(null));
    expect(MockEventSource.instances).toHaveLength(0);
  });
});
