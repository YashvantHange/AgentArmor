import { ReactNode } from "react";
import { AlertIcon } from "../icons";

type Tone = "warning" | "error" | "info";

const styles: Record<Tone, string> = {
  warning: "alert-warning",
  error: "alert-error",
  info: "alert-info",
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
