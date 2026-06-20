import { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  onClick?: () => void;
}

export function Card({ children, className = "", hover, onClick }: CardProps) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={`rounded-xl border border-surface-border bg-surface-raised shadow-panel text-left ${
        hover ? "transition-colors hover:border-brand-500/40 hover:bg-surface-overlay" : ""
      } ${className}`}
    >
      {children}
    </Tag>
  );
}

export function CardHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-1">
      <h3 className="text-sm font-semibold text-ink-primary">{title}</h3>
      {subtitle && <p className="mt-1 text-xs leading-relaxed text-ink-muted">{subtitle}</p>}
    </div>
  );
}
