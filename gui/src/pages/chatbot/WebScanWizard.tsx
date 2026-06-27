import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, WebDiscoverResult } from "../../api/client";
import { AuthSessionStep } from "../../components/AuthSessionStep";
import { AgentRiskCard, CapabilityMapView } from "../../components/CapabilityMapView";
import { AnalysisModePicker, AnalysisModeValue } from "../../components/AnalysisModePicker";
import { ScanDepthPicker, ScanDepthValue } from "../../components/ScanDepthPicker";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Alert } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";

type AuthMode = "none" | "manual_session";

export default function WebScanWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [discovery, setDiscovery] = useState<WebDiscoverResult | null>(null);
  const [webscanReady, setWebscanReady] = useState<boolean | null>(null);
  const [depth, setDepth] = useState<ScanDepthValue>({ scan_depth: "standard" });
  const [analysis, setAnalysis] = useState<AnalysisModeValue>({ analysis_mode: "offline" });
  const [authMode, setAuthMode] = useState<AuthMode>("none");
  const [plannerEnabled, setPlannerEnabled] = useState(false);
  const [authScanId, setAuthScanId] = useState<string | null>(null);
  const [authPreparing, setAuthPreparing] = useState(false);
  const [authContinuing, setAuthContinuing] = useState(false);

  useEffect(() => {
    api.getWebScanCapabilities().then((c) => setWebscanReady(c.webscan_ready)).catch(() => setWebscanReady(false));
    api.getSettings().then((s) => {
      setAnalysis({
        analysis_mode: s.analysis_mode || "offline",
        analysis_provider: s.analysis_provider,
        analysis_model: s.analysis_model,
        analysis_api_key: s.analysis_api_key,
      });
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (depth.scan_depth === "multi_agentic" && analysis.analysis_mode !== "cloud") {
      setAnalysis((a) => ({ ...a, analysis_mode: "cloud" }));
    }
    if (depth.scan_depth !== "multi_agentic") {
      setPlannerEnabled(false);
    }
  }, [depth.scan_depth, analysis.analysis_mode]);

  const multiAgenticBlocked =
    depth.scan_depth === "multi_agentic" &&
    analysis.analysis_mode === "cloud" &&
    !analysis.analysis_api_key;

  const plannerBlocked = plannerEnabled && multiAgenticBlocked;

  async function runDiscover() {
    setDiscovering(true);
    setError("");
    setDiscovery(null);
    try {
      const res = await api.discoverWebScan({ page_url: url });
      setDiscovery(res);
      if (!res.ok) setError(res.error || "No chat widget found on this page.");
      else setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Discovery failed.");
    } finally {
      setDiscovering(false);
    }
  }

  async function startScan() {
    setLoading(true);
    setError("");
    try {
      const { scan_id } = await api.createWebScan({
        page_url: url,
        scan_depth: depth.scan_depth,
        auth_mode: "none",
        planner_enabled: plannerEnabled,
        analysis_mode: depth.scan_depth === "multi_agentic" ? "cloud" : analysis.analysis_mode,
        analysis_provider: analysis.analysis_provider,
        analysis_model: analysis.analysis_model,
        analysis_api_key: analysis.analysis_api_key,
        formats: ["json", "html", "sarif"],
      });
      navigate(`/progress/${scan_id}?kind=web`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed.");
    } finally {
      setLoading(false);
    }
  }

  async function prepareAuthSession() {
    setAuthPreparing(true);
    setError("");
    try {
      const res = await api.prepareWebScanSession({ page_url: url });
      setAuthScanId(res.scan_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open login browser.");
    } finally {
      setAuthPreparing(false);
    }
  }

  async function continueAuthSession() {
    if (!authScanId) return;
    setAuthContinuing(true);
    setError("");
    try {
      const { scan_id } = await api.continueWebScanSession(authScanId, {
        scan_depth: depth.scan_depth,
        planner_enabled: plannerEnabled,
        analysis_mode: depth.scan_depth === "multi_agentic" ? "cloud" : analysis.analysis_mode,
        analysis_provider: analysis.analysis_provider,
        analysis_model: analysis.analysis_model,
        analysis_api_key: analysis.analysis_api_key,
        formats: ["json", "html", "sarif"],
      });
      navigate(`/progress/${scan_id}?kind=web`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to continue authenticated scan.");
    } finally {
      setAuthContinuing(false);
    }
  }

  function cancelAuthSession() {
    setAuthScanId(null);
    setError("");
  }

  return (
    <div className="max-w-xl">
      <PageHeader
        title="Test website chatbot"
        subtitle="Paste your website page URL — we find the chat widget, map agent capabilities, and run OWASP probes."
        backTo="/"
      />

      {webscanReady === false && (
        <div className="mb-4">
          <Alert tone="warning">
            Browser scanning requires Playwright. Install with: pip install &apos;agentarmor[browser]&apos; then
            agentarmor browser install
          </Alert>
        </div>
      )}

      <div className="mb-4">
        <Alert tone="info">
          <p className="font-medium text-ink-primary">Website URL testing — scope and limits</p>
          <p className="mt-2">
            This mode drives the chat through a real browser (Playwright). It is suited to public pages, embedded
            widgets, and CTF-style challenge sites. It is <strong>not</strong> a substitute for API endpoint testing
            when you need definitive, repeatable results against your own backend.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-ink-muted">
            <li>
              <strong>Works best:</strong> public chat UIs, marketing-site widgets, challenge pages (e.g. Gandalf,
              Prompt Airlines).
            </li>
            <li>
              <strong>May fail or be incomplete:</strong> sites behind login (use Login required), Cloudflare or
              bot checks, chats inside complex SPAs, or pages that need extra clicks before the chat appears.
            </li>
            <li>
              <strong>Not supported:</strong> fully automated scanning of chatgpt.com and similar apps without your
              manual sign-in; bypassing CAPTCHA or anti-bot protections.
            </li>
            <li>
              <strong>For definitive testing</strong> of your chatbot API, use{" "}
              <Link to="/chatbot" className="text-brand-600 hover:underline">
                chatbot API scanning
              </Link>{" "}
              with your completions URL and credentials.
            </li>
          </ul>
        </Alert>
      </div>

      {step === 1 && (
        <Card className="space-y-4 p-6">
          <h2 className="text-sm font-semibold text-ink-primary">Website URL</h2>
          <Input
            label="Page URL"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/support"
          />
          <p className="text-xs text-ink-muted">
            Use the public page URL where your chat widget appears — not the API endpoint from DevTools.
            Public challenge sites (e.g. gandalf.lakera.ai) work without login. For ChatGPT, Claude.ai, or
            Gemini, use <strong>Login required (SSO)</strong> in step 2 to sign in via the headed browser
            before scanning.
          </p>
          {error && <Alert tone="error">{error}</Alert>}
          <Button className="w-full" disabled={!url || discovering} onClick={runDiscover}>
            {discovering ? "Scanning page…" : "Discover chat widget"}
          </Button>
        </Card>
      )}

      {step === 2 && discovery && (
        <div className="space-y-4">
          <Card className="space-y-4 p-6">
            <h2 className="text-sm font-semibold text-ink-primary">Discovery results</h2>
            <div className="flex flex-wrap gap-2">
              {discovery.framework && <Badge tone="brand">{discovery.framework}</Badge>}
              {discovery.widget && (
                <Badge tone="default">Widget {(discovery.widget.confidence * 100).toFixed(0)}%</Badge>
              )}
            </div>
            {discovery.widget && (
              <p className="font-mono text-xs text-ink-muted break-all">
                Input: {discovery.widget.input_selector}
              </p>
            )}
          </Card>

          {discovery.capability_map && (
            <CapabilityMapView capability={discovery.capability_map} risk={discovery.agent_risk} />
          )}
          {discovery.agent_risk && discovery.agent_risk.risk_score >= 5 && (
            <AgentRiskCard risk={discovery.agent_risk} />
          )}

          <Card className="space-y-4 p-6">
            <div>
              <h3 className="text-sm font-medium text-ink-primary">Authentication</h3>
              <p className="mt-1 text-sm text-ink-muted">
                Choose login required when the chat widget is behind SSO or an enterprise portal. Required for
                native chat apps such as chatgpt.com, claude.ai, and gemini.google.com — AgentArmor opens a
                real browser window for you to sign in, then reuses your session cookies for the scan.
              </p>
              <div className="mt-2 flex gap-2">
                <Button
                  variant={authMode === "none" ? "primary" : "secondary"}
                  onClick={() => {
                    setAuthMode("none");
                    setAuthScanId(null);
                  }}
                >
                  Public page
                </Button>
                <Button
                  variant={authMode === "manual_session" ? "primary" : "secondary"}
                  onClick={() => setAuthMode("manual_session")}
                >
                  Login required (SSO)
                </Button>
              </div>
            </div>

            <ScanDepthPicker value={depth} onChange={setDepth} />
            {(depth.scan_depth === "multi_agentic" || analysis.analysis_mode === "cloud") && (
              <AnalysisModePicker
                value={analysis}
                onChange={setAnalysis}
                compact={depth.scan_depth === "standard"}
              />
            )}
            {depth.scan_depth === "multi_agentic" && (
              <label className="flex items-start gap-2 text-sm text-ink-primary">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={plannerEnabled}
                  onChange={(e) => setPlannerEnabled(e.target.checked)}
                  disabled={multiAgenticBlocked}
                />
                <span>
                  <strong>Multi-agent red team</strong> — capability-aware attack graph with Memory/A2A agents and budget
                  tracking (cloud API key required).
                </span>
              </label>
            )}
            {multiAgenticBlocked && (
              <Alert tone="warning">
                Multi-agentic scans require a cloud analysis API key. The key is used per request only and is not stored
                on the server.
              </Alert>
            )}
            {plannerBlocked && (
              <Alert tone="warning">Multi-agent red team requires a cloud analysis API key.</Alert>
            )}
            <p className="text-sm text-ink-muted">
              {depth.scan_depth === "multi_agentic"
                ? "Cloud judge validates responses; red team planner runs attack-graph paths for detected capabilities."
                : "Probes adapt to detected capabilities (RAG, tools, MCP, memory) with offline OWASP analysis."}
            </p>
            {error && <Alert tone="error">{error}</Alert>}

            {authMode === "manual_session" ? (
              <AuthSessionStep
                preparing={authPreparing}
                continuing={authContinuing}
                sessionReady={Boolean(authScanId)}
                error={error}
                onPrepare={prepareAuthSession}
                onContinue={continueAuthSession}
                onCancel={cancelAuthSession}
              />
            ) : (
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setStep(1)}>
                  Back
                </Button>
                <Button
                  className="flex-1"
                  disabled={loading || !discovery.ok || multiAgenticBlocked || plannerBlocked}
                  onClick={startScan}
                >
                  {loading ? "Starting…" : depth.scan_depth === "multi_agentic" ? "Run multi-agentic scan" : "Run security scan"}
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}

      <p className="mt-4 text-center text-xs text-ink-muted">
        Testing via API URL instead?{" "}
        <Link to="/chatbot" className="text-brand-600 hover:underline">
          Use chatbot API wizard
        </Link>
      </p>
    </div>
  );
}
