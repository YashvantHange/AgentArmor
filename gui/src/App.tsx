import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import { Shell } from "./components/layout/Shell";
import { LoadingBlock } from "./components/ui/Spinner";
import Benchmark from "./pages/Benchmark";
import Findings from "./pages/Findings";
import Home from "./pages/Home";
import Marketplace from "./pages/Marketplace";
import Monitoring from "./pages/Monitoring";
import Reports from "./pages/Reports";
import ScanConfig from "./pages/ScanConfig";
import ScanProgress from "./pages/ScanProgress";
import SettingsPage from "./pages/Settings";
import ChatbotWizard from "./pages/chatbot/ChatbotWizard";
import { ShieldIcon } from "./components/icons";

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
          if (!cancelled && attempts < 120) {
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

  if (online === null) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-app px-6 text-center">
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/15 text-brand-600 ring-1 ring-brand-500/25">
          <ShieldIcon className="h-8 w-8" />
        </div>
        <h1 className="text-lg font-semibold text-ink-primary">AgentArmor</h1>
        <p className="mt-2 max-w-sm text-sm text-ink-muted">
          Starting security engine…
        </p>
        <div className="mt-6 w-48">
          <LoadingBlock label="" />
        </div>
      </div>
    );
  }

  return (
    <Shell online={online} version={version}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/chatbot" element={<ChatbotWizard />} />
        <Route path="/scan/:type" element={<ScanConfig />} />
        <Route path="/progress/:scanId" element={<ScanProgress />} />
        <Route path="/findings/:scanId" element={<Findings />} />
        <Route path="/reports/:scanId" element={<Reports />} />
        <Route path="/benchmark" element={<Benchmark />} />
        <Route path="/marketplace" element={<Marketplace />} />
        <Route path="/monitoring" element={<Monitoring />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Shell>
  );
}
