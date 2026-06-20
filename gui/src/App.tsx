import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import { Shell } from "./components/layout/Shell";
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

  return (
    <Shell online={online} version={version}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/scan/:type" element={<ScanConfig />} />
        <Route path="/progress/:scanId" element={<ScanProgress />} />
        <Route path="/findings/:scanId" element={<Findings />} />
        <Route path="/reports/:scanId" element={<Reports />} />
        <Route path="/benchmark" element={<Benchmark />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </Shell>
  );
}
