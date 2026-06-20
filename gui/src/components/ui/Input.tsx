import { InputHTMLAttributes, ReactNode } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
}

export function Input({ label, hint, error, className = "", id, ...props }: InputProps) {
  const inputId = id || props.name;
  return (
    <label htmlFor={inputId} className="block">
      <span className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</span>
      <input
        id={inputId}
        className={`mt-1.5 w-full rounded-lg border bg-surface-overlay px-3 py-2.5 text-sm text-ink-primary placeholder:text-ink-muted focus-ring ${
          error ? "border-red-500/60" : "border-surface-border hover:border-surface-border-strong focus:border-brand-500/50"
        } ${className}`}
        {...props}
      />
      {hint && !error && <p className="mt-1.5 text-xs text-ink-muted">{hint}</p>}
      {error && <p className="mt-1.5 text-xs text-red-400">{error}</p>}
    </label>
  );
}

export function FieldGroup({ children }: { children: ReactNode }) {
  return <div className="space-y-4">{children}</div>;
}
