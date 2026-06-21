import { FormEvent, useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { api, ScanCreateBody, ScanType } from "../api/client";
import { AnalysisModePicker, AnalysisModeValue } from "../components/AnalysisModePicker";
import {
  DEFAULT_REDTEAM,
  RedTeamOptions,
  RedTeamOptionsPicker,
  redTeamToScanBody,
  settingsToRedTeam,
} from "../components/RedTeamOptionsPicker";
import { PageHeader } from "../components/layout/PageHeader";
import { FieldGroup, Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";
import { Card } from "../components/ui/Card";

const VALID_TYPES: ScanType[] = ["endpoint", "provider", "local", "agent", "mcp", "rag"];

const TITLES: Record<ScanType, string> = {
  endpoint: "API endpoint scan",
  provider: "Cloud provider scan",
  local: "Local model scan",
  agent: "Agent framework scan",
  mcp: "MCP server scan",
  rag: "RAG corpus scan",
};

const SUBTITLES: Record<ScanType, string> = {
  endpoint: "Chat API POST URL — auto-detects OpenAI and common JSON formats.",
  provider: "Run probes against a hosted model via LiteLLM routing.",
  local: "Evaluate weights running on this machine.",
  agent: "Exercise agent orchestration frameworks with security probes.",
  mcp: "Audit MCP tool servers for unsafe capabilities.",
  rag: "Test retrieval corpora for poisoning and leakage.",
};

export default function ScanConfig() {
  const { type } = useParams<{ type: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisModeValue>({ analysis_mode: "offline" });
  const [redTeam, setRedTeam] = useState<RedTeamOptions>(DEFAULT_REDTEAM);

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

  if (!type || !VALID_TYPES.includes(type as ScanType)) {
    return <Navigate to="/" replace />;
  }

  const scanType = type as ScanType;

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const fd = new FormData(e.currentTarget);
    const body: ScanCreateBody = {
      target_type: scanType,
      formats: ["json", "html", "sarif", "pdf"],
      endpoint_profile: scanType === "endpoint" ? "auto" : undefined,
      ...analysis,
      ...redTeamToScanBody(redTeam),
    };

    if (scanType === "endpoint") body.url = String(fd.get("url") || "").trim();
    if (scanType === "provider") {
      body.provider = String(fd.get("provider") || "").trim();
      body.model = String(fd.get("model") || "").trim() || undefined;
    }
    if (scanType === "local") body.model = String(fd.get("model") || "").trim();
    if (scanType === "agent") {
      body.agent = String(fd.get("agent") || "crewai").trim();
      body.agent_config = String(fd.get("agent_config") || "").trim() || undefined;
    }
    if (scanType === "mcp") body.mcp = String(fd.get("mcp") || "").trim();
    if (scanType === "rag") {
      body.rag = String(fd.get("rag") || "").trim();
      body.embedder = String(fd.get("embedder") || "bge").trim();
    }

    const authToken = String(fd.get("auth_token") || "").trim();
    if (authToken) body.auth_token = authToken;

    const required =
      (scanType === "endpoint" && !body.url) ||
      (scanType === "provider" && !body.provider) ||
      (scanType === "local" && !body.model) ||
      (scanType === "mcp" && !body.mcp) ||
      (scanType === "rag" && !body.rag);

    if (required) {
      setError("Please fill in all required fields.");
      setLoading(false);
      return;
    }

    try {
      const { scan_id } = await api.createScan(body);
      navigate(`/progress/${scan_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed to start");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl">
      <PageHeader title={TITLES[scanType]} subtitle={SUBTITLES[scanType]} backTo="/" />

      <Card className="p-6">
        <form onSubmit={onSubmit}>
          <FieldGroup>
            {scanType === "endpoint" && (
              <Input
                label="API URL"
                name="url"
                required
                placeholder="http://localhost:8000/v1/chat/completions"
              />
            )}
            {scanType === "provider" && (
              <>
                <Input label="Provider" name="provider" required placeholder="openai" />
                <Input label="Model" name="model" placeholder="gpt-4o-mini" hint="Optional — uses provider default when empty" />
              </>
            )}
            {scanType === "local" && (
              <Input label="Model path" name="model" required placeholder="C:\\models\\llama-3.gguf" />
            )}
            {scanType === "agent" && (
              <>
                <Input label="Framework" name="agent" defaultValue="crewai" required />
                <Input label="Config file" name="agent_config" placeholder="agent.toml" hint="Optional agent configuration path" />
              </>
            )}
            {scanType === "mcp" && (
              <Input label="MCP path or URL" name="mcp" required placeholder="./mcp-server.py" />
            )}
            {scanType === "rag" && (
              <>
                <Input label="Corpus directory" name="rag" required placeholder="./corpus" />
                <Input label="Embedder" name="embedder" defaultValue="bge" />
              </>
            )}
            {(scanType === "endpoint" || scanType === "provider") && (
              <Input
                label="Bearer token (optional)"
                name="auth_token"
                type="password"
                placeholder="sk-... or Bearer token"
              />
            )}
          </FieldGroup>

          <div className="mt-6 border-t border-surface-border pt-6">
            <AnalysisModePicker value={analysis} onChange={setAnalysis} />
          </div>

          <div className="mt-6 border-t border-surface-border pt-6">
            <RedTeamOptionsPicker
              value={redTeam}
              onChange={setRedTeam}
              scanType={scanType}
              analysisMode={analysis.analysis_mode}
            />
          </div>

          {error && (
            <div className="mt-4">
              <Alert tone="error">{error}</Alert>
            </div>
          )}

          <div className="mt-6 flex gap-3">
            <Button type="submit" disabled={loading} className="flex-1">
              {loading ? "Starting scan…" : "Start scan"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
