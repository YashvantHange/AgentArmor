export function Spinner({ className = "" }: { className?: string }) {
  return (
    <div
      className={`h-5 w-5 animate-spin rounded-full border-2 border-surface-border border-t-brand-500 ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-surface-border bg-surface-raised px-4 py-8 text-sm text-ink-muted">
      <Spinner />
      {label}
    </div>
  );
}
