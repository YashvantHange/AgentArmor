import { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-surface-border bg-surface/50 px-6 py-10 text-center">
      <h3 className="text-sm font-medium text-ink-primary">{title}</h3>
      {description && <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
