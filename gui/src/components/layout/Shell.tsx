import { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ChartIcon,
  HomeIcon,
  SettingsIcon,
  ShieldIcon,
} from "../icons";

const NAV = [
  { to: "/", label: "Dashboard", icon: HomeIcon },
  { to: "/benchmark", label: "Benchmark", icon: ChartIcon },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export function Shell({
  children,
  online,
  version,
}: {
  children: ReactNode;
  online: boolean | null;
  version: string;
}) {
  const location = useLocation();

  return (
    <div className="flex min-h-screen bg-[#09090b]">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-surface-border bg-surface lg:flex">
        <div className="flex items-center gap-2.5 border-b border-surface-border px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/15 text-brand-400 ring-1 ring-brand-500/20">
            <ShieldIcon className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-semibold text-ink-primary">AgentArmor</div>
            <div className="text-[11px] text-ink-muted">Security Console</div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {NAV.map(({ to, label, icon: Icon }) => {
            const active = location.pathname === to;
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-ring ${
                  active
                    ? "bg-brand-500/10 text-brand-400"
                    : "text-ink-secondary hover:bg-surface-overlay hover:text-ink-primary"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0 opacity-80" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-surface-border p-4">
          <StatusPill online={online} version={version} />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-surface-border bg-surface/80 px-4 py-3 backdrop-blur lg:hidden">
          <Link to="/" className="flex items-center gap-2 text-sm font-semibold text-ink-primary">
            <ShieldIcon className="h-4 w-4 text-brand-400" />
            AgentArmor
          </Link>
          <StatusPill online={online} version={version} compact />
        </header>

        {online === false && (
          <div className="border-b border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-center text-sm text-amber-100">
            Backend service is starting or offline. Scans will be unavailable until the sidecar is ready.
          </div>
        )}

        <main className="flex-1 px-4 py-6 sm:px-8 lg:px-10 lg:py-8">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}

function StatusPill({
  online,
  version,
  compact,
}: {
  online: boolean | null;
  version: string;
  compact?: boolean;
}) {
  const label =
    online === null ? "Connecting" : online ? `Online · v${version}` : "Offline";
  const dot =
    online === null ? "bg-amber-400 animate-pulse" : online ? "bg-brand-400" : "bg-red-400";

  return (
    <div
      className={`flex items-center gap-2 rounded-lg border border-surface-border bg-surface-overlay ${
        compact ? "px-2.5 py-1.5 text-xs" : "px-3 py-2 text-xs"
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      <span className="font-medium text-ink-secondary">{label}</span>
    </div>
  );
}
