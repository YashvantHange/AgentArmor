import { Link } from "react-router-dom";
import type { ScanType } from "../api/client";

const TILES: { type: ScanType; title: string; desc: string; icon: string }[] = [
  { type: "endpoint", title: "API Endpoint", desc: "OpenAI-compatible HTTP API", icon: "🌐" },
  { type: "provider", title: "Cloud Provider", desc: "OpenAI, Anthropic, Gemini…", icon: "☁️" },
  { type: "local", title: "Local Model", desc: "Offline .gguf / HuggingFace", icon: "💾" },
  { type: "agent", title: "Agent Security", desc: "CrewAI, LangGraph harness", icon: "🤖" },
  { type: "mcp", title: "MCP Server", desc: "Tool discovery & abuse", icon: "🔌" },
  { type: "rag", title: "RAG Corpus", desc: "Poisoning & retrieval attacks", icon: "📚" },
];

export default function Home() {
  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">AgentArmor</h1>
      <p className="text-slate-400 mb-8">AI Security Validation — pick a scan target</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {TILES.map((t) => (
          <Link
            key={t.type}
            to={`/scan/${t.type}`}
            className="block p-5 rounded-xl border border-slate-700 bg-slate-900 hover:border-armor-500 hover:bg-slate-800 transition"
          >
            <span className="text-2xl">{t.icon}</span>
            <h2 className="text-lg font-semibold mt-2">{t.title}</h2>
            <p className="text-sm text-slate-400">{t.desc}</p>
          </Link>
        ))}
      </div>
      <Link
        to="/benchmark"
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-armor-700 hover:bg-armor-500 text-white font-medium"
      >
        📊 Run Model Benchmark
      </Link>
    </div>
  );
}
