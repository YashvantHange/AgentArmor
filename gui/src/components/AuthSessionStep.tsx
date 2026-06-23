import { Button } from "./ui/Button";
import { Alert } from "./ui/Alert";
import { Card } from "./ui/Card";

interface AuthSessionStepProps {
  preparing: boolean;
  continuing: boolean;
  sessionReady: boolean;
  error?: string;
  onPrepare: () => void;
  onContinue: () => void;
  onCancel: () => void;
}

export function AuthSessionStep({
  preparing,
  continuing,
  sessionReady,
  error,
  onPrepare,
  onContinue,
  onCancel,
}: AuthSessionStepProps) {
  return (
    <Card className="space-y-4 p-6">
      <h2 className="text-sm font-semibold text-ink-primary">Enterprise login (SSO)</h2>
      <p className="text-sm text-ink-muted">
        Open a browser window to sign in to your portal. Session cookies are encrypted locally and never sent to cloud
        LLM providers.
      </p>
      {!sessionReady ? (
        <Button className="w-full" disabled={preparing} onClick={onPrepare}>
          {preparing ? "Opening browser…" : "Open login browser"}
        </Button>
      ) : (
        <>
          <Alert tone="info">
            Complete login in the browser window, then continue. The scan reuses your authenticated session.
          </Alert>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onCancel} disabled={continuing}>
              Cancel
            </Button>
            <Button className="flex-1" disabled={continuing} onClick={onContinue}>
              {continuing ? "Starting scan…" : "Continue scan"}
            </Button>
          </div>
        </>
      )}
      {error && <Alert tone="error">{error}</Alert>}
    </Card>
  );
}
