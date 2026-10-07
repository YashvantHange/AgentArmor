import { vi } from "vitest";

/**
 * Minimal EventSource stand-in.
 *
 * The repository had no fetch or EventSource mocking before this, so this is a
 * deliberately small new pattern with a single consumer (useSwarmEvents.test.ts)
 * rather than a general-purpose network harness.
 */

type Listener = (event: MessageEvent) => void;

export class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  closed = false;
  onerror: ((this: EventSource, ev: Event) => unknown) | null = null;
  private listeners = new Map<string, Listener[]>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(name: string, listener: Listener): void {
    const existing = this.listeners.get(name) ?? [];
    existing.push(listener);
    this.listeners.set(name, existing);
  }

  close(): void {
    this.closed = true;
  }

  /** Deliver one server event. Unsubscribed names are dropped, as in the browser. */
  emit(name: string, data: unknown): void {
    const listeners = this.listeners.get(name);
    if (!listeners) return;
    const event = { data: JSON.stringify(data) } as MessageEvent;
    listeners.forEach((listener) => listener(event));
  }

  /** True when the hook subscribed to this event name. */
  subscribed(name: string): boolean {
    return this.listeners.has(name);
  }

  static latest(): MockEventSource {
    const instance = MockEventSource.instances[MockEventSource.instances.length - 1];
    if (!instance) throw new Error("no EventSource was created");
    return instance;
  }

  static reset(): void {
    MockEventSource.instances = [];
  }
}

export function installMockEventSource(): void {
  MockEventSource.reset();
  vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
}
