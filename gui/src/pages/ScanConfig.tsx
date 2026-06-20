import { FormEvent, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ScanCreateBody, ScanType } from "../api/client";

export default function ScanConfig() {
  const { type } = useParams<{ type: ScanType }>();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const scanType = (type || "endpoint") as ScanType;

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const fd = new FormData(e.currentTarget);
    const body: ScanCreateBody = {
      target_type: scanType,
      formats: ["json", "html", "sarif", "pdf"],
    };
    if (scanType === "endpoint") body.url = String(fd.get("url") || "");
    if (scanType === "provider") {
      body.provider = String(fd.get("provider") || "");
      body.model = String(fd.get("model") || "") || undefined;
    }
    if (scanType === "local") body.model = String(fd.get("model") || "");
    if (scanType === "agent") {
      body.agent = String(fd.get("agent") || "crewai");
      body.agent_config = String(fd.get("agent_config") || "") || undefined;
    }
    if (scanType === "mcp") body.mcp = String(fd.get("mcp") || "");
    if (scanType === "rag") {
      body.rag = String(fd.get("rag") || "");
      body.embedder = String(fd.get("embedder") || "bge");
    }
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
    <div className="max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-6 capitalize">{scanType} Scan</h1>
      <form onSubmit={onSubmit} className="space-y-4">
        {scanType === "endpoint" && (
          <Field label="API URL" name="url" placeholder="http://localhost:8000/v1/chat/completions" />
        )}
        {scanType === "provider" && (
          <>
            <Field label="Provider" name="provider" placeholder="openai" />
            <Field label="Model (optional)" name="model" placeholder="gpt-3.5-turbo" />
          </>
        )}
        {scanType === "local" && (
          <Field label="Model path" name="model" placeholder="llama-3.gguf" />
        )}
        {scanType === "agent" && (
          <>
            <Field label="Framework" name="agent" placeholder="crewai" defaultValue="crewai" />
            <Field label="Config file (optional)" name="agent_config" placeholder="agent.toml" />
          </>
        )}
        {scanType === "mcp" && (
          <Field label="MCP path or URL" name="mcp" placeholder="./mcp-server.py" />
        )}
        {scanType === "rag" && (
          <>
            <Field label="Corpus directory" name="rag" placeholder="./corpus" />
            <Field label="Embedder" name="embedder" placeholder="bge" defaultValue="bge" />
          </>
        )}
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 rounded-lg bg-armor-700 hover:bg-armor-500 disabled:opacity-50 font-medium"
        >
          {loading ? "Starting…" : "Start Scan"}
        </button>
      </form>
    </div>
  );
}

function Field({
  label,
  name,
  placeholder,
  defaultValue,
}: {
  label: string;
  name: string;
  placeholder?: string;
  defaultValue?: string;
}) {
  return (
    <label className="block">
      <span className="text-sm text-slate-400">{label}</span>
      <input
        name={name}
        defaultValue={defaultValue}
        placeholder={placeholder}
        className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 focus:border-armor-500 outline-none"
      />
    </label>
  );
}
