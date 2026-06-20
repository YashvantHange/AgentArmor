import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowLeftIcon } from "../icons";

export function PageHeader({
  title,
  subtitle,
  backTo,
  actions,
}: {
  title: string;
  subtitle?: string;
  backTo?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        {backTo && (
          <Link
            to={backTo}
            className="mb-3 inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted transition-colors hover:text-ink-primary"
          >
            <ArrowLeftIcon className="h-3.5 w-3.5" />
            Back
          </Link>
        )}
        <h1 className="text-2xl font-semibold tracking-tight text-ink-primary">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-ink-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
