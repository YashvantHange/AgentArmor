import { ReactNode } from "react";
import { AlertIcon } from "../icons";

type Tone = "warning" | "error" | "info";

const styles: Record<Tone, string> = {
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-100",
  error: "border-red-500/30 bg-red-500/10 text-red-100",
  info: "border-brand-500/30 bg-brand-500/10 text-brand-100",
};

export function Alert({
  tone = "info",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  return (
    <div className={`flex gap-3 rounded-lg border px-4 py-3 text-sm ${styles[tone]}`}>
      <AlertIcon className="mt-0.5 h-4 w-4 shrink-0 opacity-80" />
      <div>{children}</div>
    </div>
  );
}
