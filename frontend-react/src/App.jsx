import { useEffect, useState } from "react";
import { ThemeProvider } from "./context/ThemeContext";
import ThemeToggle from "./components/ThemeToggle";
import Banner from "./components/Banner";
import PaperExplorer from "./components/PaperExplorer/PaperExplorer";

import HexagonIcon from "./components/HexagonIcon";

const BACKEND_URL = import.meta.env.VITE_API_BASE_URL 
  || (import.meta.env.DEV ? "http://localhost:8000" : window.location.origin);

const isProduction = import.meta.env.PROD || import.meta.env.VITE_APP_ENV === "production";
const showDevStatus = !isProduction && import.meta.env.VITE_SHOW_DEV_STATUS !== "false";

function AppContent() {
  const [backendOnline, setBackendOnline] = useState(false);
  const [backendStatus, setBackendStatus] = useState("Checking Backend...");
  const [errorMessage, setErrorMessage] = useState("");

  const isLiveServer = window.location.port === "5500" || window.location.port === "5501";

  // Health check on load
  useEffect(() => {
    async function checkBackend() {
      try {
        const res = await fetch(`${BACKEND_URL}/health`);
        if (res.ok) {
          setBackendOnline(true);
          setBackendStatus("Backend Connected");
        } else {
          throw new Error();
        }
      } catch {
        setBackendOnline(false);
        setBackendStatus("Backend Offline");
        setErrorMessage(`Cannot connect to Node backend at ${BACKEND_URL}`);
      }
    }
    checkBackend();
  }, []);

  return (
    <>
      {/* Background outline shapes */}
      <div className="bg-shapes">
        <svg className="bg-shape shape-1" viewBox="0 0 100 100" fill="none">
          <circle cx="50" cy="50" r="48" stroke="currentColor" strokeWidth="0.25" />
          <circle cx="50" cy="50" r="35" stroke="currentColor" strokeWidth="0.15" strokeDasharray="2 2" />
        </svg>
        <svg className="bg-shape shape-2" viewBox="0 0 100 100" fill="none">
          <rect x="2" y="2" width="96" height="96" rx="10" stroke="currentColor" strokeWidth="0.25" />
          <path d="M10 0 L10 100 M20 0 L20 100 M30 0 L30 100 M40 0 L40 100 M50 0 L50 100 M60 0 L60 100 M70 0 L70 100 M80 0 L80 100 M90 0 L90 100" stroke="currentColor" strokeWidth="0.05" />
        </svg>
        <svg className="bg-shape shape-3" viewBox="0 0 100 100" fill="none">
          <polygon points="50,2 98,85 2,85" stroke="currentColor" strokeWidth="0.25" />
        </svg>
      </div>

      <div className="container full-width">
        {showDevStatus && isLiveServer && (
          <Banner type="error" className="live-server-warning" style={{ marginBottom: "20px" }}>
            Warning: You are viewing this page via a VS Code Live Server port. To prevent database writes from triggering automatic browser reloads, please use the official Node server address:{" "}
            <a href="http://localhost:8000" style={{ color: "inherit", fontWeight: 700 }}>
              http://localhost:8000
            </a>.
          </Banner>
        )}

        {errorMessage && (
          <Banner type="error" style={{ marginBottom: "20px" }}>
            {errorMessage}
          </Banner>
        )}

        <header>
          <h1>
            <HexagonIcon size={32} />
            <span>PaperMind</span>
          </h1>
          <p>Read less. Understand more.</p>
          {showDevStatus && (
            <div className={`connection-badge ${backendOnline ? "online" : "offline"}`}>
              <span className="dot"></span>
              <span>{backendStatus}</span>
            </div>
          )}
          <ThemeToggle />
        </header>

        <PaperExplorer />
      </div>
    </>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}
