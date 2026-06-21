import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ScanCreateBody } from "../../api/client";
import { AnalysisModePicker, AnalysisModeValue } from "../../components/AnalysisModePicker";
import {
  DEFAULT_REDTEAM,
  RedTeamOptions,
  RedTeamOptionsPicker,
  redTeamToScanBody,
  settingsToRedTeam,
} from "../../components/RedTeamOptionsPicker";
import { PageHeader } from "../../components/layout/PageHeader";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Alert } from "../../components/ui/Alert";

const CHATBOT_TYPES = [
  { id: "endpoint", label: "My app or website", hint: "Chat API POST URL (not the browser page)" },
  { id: "provider", label: "OpenAI / Claude / Gemini", hint: "Hosted model" },
  { id: "local", label: "Runs on my computer", hint: "Local GGUF or HF model" },
] as const;

export default function ChatbotWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [chatbotType, setChatbotType] = useState<(typeof CHATBOT_TYPES)[number]["id"]>("endpoint");
  const [url, setUrl] = useState("");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("");
  const [authToken, setAuthToken] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisModeValue>({ analysis_mode: "offline" });
  const [redTeam, setRedTeam] = useState<RedTeamOptions>(DEFAULT_REDTEAM);
  const [connMsg, setConnMsg] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSettings().then((s) => {
      setAnalysis({
        analysis_mode: (s.analysis_mode as "offline" | "cloud") || "offline",
        analysis_provider: s.analysis_provider,
        analysis_model: s.analysis_model,
        analysis_api_key: s.analysis_api_key,
      });
      setRedTeam(settingsToRedTeam(s));
    });
  }, []);

  async function testConnection() {
    setConnMsg("");
    setError("");
    try {
      const res = await api.testConnection({
        target_type: chatbotType === "local" ? "endpoint" : chatbotType,
        url: chatbotType === "endpoint" ? url : undefined,
        provider: chatbotType === "provider" ? provider : undefined,
        model: model || undefined,
        auth_token: authToken || undefined,
        endpoint_profile: "auto",
      });
      if (res.ok) {
        const profile = res.profile ? ` (${res.profile})` : "";
        setConnMsg(`Connected${profile} — ${res.sample_excerpt?.slice(0, 80) || "response received"}`);
      } else setConnMsg(res.error || "Connection failed.");
    } catch (err) {
      setConnMsg(err instanceof Error ? err.message : "Connection failed.");
    }
  }

  async function startScan() {
    setLoading(true);
    setError("");
    const body: ScanCreateBody = {
      target_type: chatbotType,
      formats: ["json", "html", "sarif", "pdf"],
      endpoint_profile: chatbotType === "endpoint" ? "auto" : undefined,
      ...analysis,
      ...redTeamToScanBody(redTeam),
      auth_token: authToken || undefined,
    };
    if (chatbotType === "endpoint") body.url = url;
    if (chatbotType === "provider") {
      body.provider = provider;
      body.model = model || undefined;
    }
    if (chatbotType === "local") body.model = model;
    try {
      const { scan_id } = await api.createScan(body);
      navigate(`/progress/${scan_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl">
      <PageHeader
        title="Test my chatbot"
        subtitle="Check if your chatbot can be tricked into leaking secrets or ignoring rules."
        backTo="/"
      />

      {step === 1 && (
        <Card className="p-6 space-y-4">
          <h2 className="text-sm font-semibold text-ink-primary">What kind of chatbot?</h2>
          {CHATBOT_TYPES.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setChatbotType(t.id)}
              className={`w-full rounded-lg border p-4 text-left focus-ring ${
                chatbotType === t.id
                  ? "border-brand-500 bg-brand-500/10"
                  : "border-surface-border hover:border-surface-border-strong"
              }`}
            >
              <div className="font-medium text-ink-primary">{t.label}</div>
              <div className="text-xs text-ink-muted">{t.hint}</div>
            </button>
          ))}
          <Button className="w-full" onClick={() => setStep(2)}>
            Continue
          </Button>
        </Card>
      )}

      {step === 2 && (
        <Card className="p-6 space-y-4">
          <h2 className="text-sm font-semibold text-ink-primary">Connect your chatbot</h2>
          {chatbotType === "endpoint" && (
            <>
              <Input
                label="Chat API endpoint"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://your-site.com/v1/chat/completions"
              />
              <p className="text-xs text-ink-muted">
                Use the POST URL from DevTools → Network, not the .html page. Format is auto-detected.
              </p>
            </>
          )}
          {chatbotType === "provider" && (
            <>
              <Input label="Provider" value={provider} onChange={(e) => setProvider(e.target.value)} />
              <Input label="Model (optional)" value={model} onChange={(e) => setModel(e.target.value)} />
            </>
          )}
          {chatbotType === "local" && (
            <Input label="Model path" value={model} onChange={(e) => setModel(e.target.value)} />
          )}
          {(chatbotType === "endpoint" || chatbotType === "provider") && (
            <Input
              label="API key (optional)"
              type="password"
              value={authToken}
              onChange={(e) => setAuthToken(e.target.value)}
            />
          )}
          <AnalysisModePicker value={analysis} onChange={setAnalysis} />
          <RedTeamOptionsPicker
            value={redTeam}
            onChange={setRedTeam}
            scanType={chatbotType}
            analysisMode={analysis.analysis_mode}
            compact
          />
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStep(1)}>
              Back
            </Button>
            <Button variant="secondary" onClick={testConnection}>
              Test connection
            </Button>
            <Button onClick={() => setStep(3)}>Continue</Button>
          </div>
          {connMsg && <Alert tone={connMsg.startsWith("Connected") ? "info" : "warning"}>{connMsg}</Alert>}
        </Card>
      )}

      {step === 3 && (
        <Card className="p-6 space-y-4">
          <h2 className="text-sm font-semibold text-ink-primary">Review and run</h2>
          <p className="text-sm text-ink-muted">
            Runs L1–L3 probes plus L0 adaptive attacks
            {redTeam.l0_enabled ? ` (up to ${redTeam.max_variants_per_goal} variants/goal)` : ""}
            {redTeam.self_play_enabled ? ", self-play red teaming" : ""}
            {redTeam.self_play_discovery_enabled ? ", and attack discovery" : ""} in{" "}
            <strong>{analysis.analysis_mode}</strong> mode.
          </p>
          {error && <Alert tone="error">{error}</Alert>}
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStep(2)}>
              Back
            </Button>
            <Button className="flex-1" disabled={loading} onClick={startScan}>
              {loading ? "Starting…" : "Start security test"}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
