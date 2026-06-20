import { useEffect, useState } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import Benchmark from "./pages/Benchmark";
import Findings from "./pages/Findings";
import Home from "./pages/Home";
import Reports from "./pages/Reports";
import ScanConfig from "./pages/ScanConfig";
import ScanProgress from "./pages/ScanProgress";
import SettingsPage from "./pages/Settings";

export default function App() {
  const [online, setOnline] = useState<boolean | null>(null);
  const [version, setVersion] = useState("");

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;
    const poll = () => {
      api
        .health()
        .then((h) => {
          if (!cancelled) {
            setOnline(true);
            setVersion(h.version);
          }
        })
        .catch(() => {
          if (!cancelled && attempts < 60) {
            attempts += 1;
            setTimeout(poll, 500);
          } else if (!cancelled) {
            setOnline(false);
          }
        });
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="font-bold text-armor-500">
            AgentArmor
          </Link>
          <nav className="flex gap-4 text-sm">
            <Link to="/benchmark" className="text-slate-300 hover:text-white">
              Benchmark
            </Link>
            <Link to="/settings" className="text-slate-300 hover:text-white">
              Settings
            </Link>
          </nav>
          <div className="text-xs text-slate-500">
            {online === null ? "…" : online ? `v${version}` : "Sidecar offline"}
          </div>
        </div>
      </header>
      {online === false && (
        <div className="bg-amber-900/50 text-amber-200 text-sm text-center py-2">
          Start sidecar: <code className="font-mono">agentarmor serve</code>
        </div>
      )}
      <main className="flex-1 p-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/scan/:type" element={<ScanConfig />} />
          <Route path="/progress/:scanId" element={<ScanProgress />} />
          <Route path="/findings/:scanId" element={<Findings />} />
          <Route path="/reports/:scanId" element={<Reports />} />
          <Route path="/benchmark" element={<Benchmark />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
