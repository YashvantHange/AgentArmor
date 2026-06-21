import { useEffect, useState } from "react";
import { api } from "../api/client";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { LoadingBlock } from "../components/ui/Spinner";

interface Rule {
  id: string;
  name: string;
  version: string;
  description: string;
  category: string;
  owasp: string[];
}

export default function Marketplace() {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [installed, setInstalled] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => {
    Promise.all([api.listMarketplaceRules(), api.listInstalledRules()])
      .then(([r, i]) => {
        setRules(r);
        setInstalled(i.map((x) => x.manifest_id));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load marketplace"));
  };

  useEffect(() => {
    load();
  }, []);

  async function install(ruleId: string) {
    setBusy(ruleId);
    setError("");
    try {
      await api.installMarketplaceRule(ruleId);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Install failed");
    } finally {
      setBusy(null);
    }
  }

  if (rules === null) {
    return (
      <div>
        <PageHeader title="Marketplace" subtitle="Community probes, suites, and assertion packs." backTo="/" />
        <LoadingBlock label="Loading marketplace…" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Rule marketplace"
        subtitle="Install community security probes and OWASP packs into your scan orchestrator."
        backTo="/"
      />

      {error && (
        <div className="mb-4">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      <div className="space-y-3">
        {rules.map((rule) => {
          const isInstalled = installed.includes(rule.id);
          return (
            <Card key={rule.id} className="p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-sm font-semibold text-ink-primary">{rule.name}</h2>
                    <Badge tone="default">{rule.category}</Badge>
                    <Badge tone="brand">v{rule.version}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-ink-muted">{rule.description}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {rule.owasp.map((tag) => (
                      <Badge key={tag} tone="brand">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
                <Button
                  variant={isInstalled ? "secondary" : "primary"}
                  size="sm"
                  disabled={isInstalled || busy === rule.id}
                  onClick={() => install(rule.id)}
                >
                  {isInstalled ? "Installed" : busy === rule.id ? "Installing…" : "Install"}
                </Button>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
