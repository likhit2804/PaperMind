import { useState, useCallback, useEffect } from "react";
import GraphCanvas from "./GraphCanvas";
import NodeDrawer from "./NodeDrawer";
import KeyTermsPanel from "./KeyTermsPanel";
import PdfViewer from "./PdfViewer";
import UploadZone from "./UploadZone";

const BACKEND_URL = "http://localhost:8000";
const STORAGE_KEY = "cogniweave_paper_session";

// ── Helpers ──────────────────────────────────────────────────────────────────
function loadSavedSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveSession(data) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    console.warn("Could not persist paper session:", e);
  }
}

function clearSession() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.warn("Could not clear paper session:", error);
  }
}

export default function PaperExplorer() {
  // ── Initialise from localStorage so data survives page refresh ──────────
  const saved = loadSavedSession();

  const [status, setStatus]           = useState(saved ? "ready" : "idle");
  const [error, setError]             = useState("");
  const [paperTitle, setPaperTitle]   = useState(saved?.paperTitle || "");
  const [nodes, setNodes]             = useState(saved?.nodes || []);
  const [sessionId, setSessionId]     = useState(saved?.sessionId || null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [showKeyTerms, setShowKeyTerms] = useState(false);

  // pdfUrl is derived from sessionId — never stored directly (avoids stale host issues)
  const pdfUrl = sessionId ? `${BACKEND_URL}/paper/pdf/${sessionId}` : null;

  const [pdfPage, setPdfPage] = useState(1);
  const [pdfSearchTerm, setPdfSearchTerm] = useState("");
  const [pdfOpen, setPdfOpen] = useState(!!saved);

  // ── Persist whenever session changes ────────────────────────────────────
  useEffect(() => {
    if (sessionId && nodes.length > 0) {
      saveSession({ sessionId, paperTitle, nodes });
    }
  }, [sessionId, paperTitle, nodes]);

  // ── Upload handler ───────────────────────────────────────────────────────
  const handleFileUpload = useCallback(async (file) => {
    // If there is an existing sessionId, delete it from the backend first
    if (sessionId) {
      try {
        await fetch(`${BACKEND_URL}/paper/${sessionId}`, { method: "DELETE" });
      } catch (err) {
        console.warn("Failed to delete previous paper from backend:", err);
      }
    }

    setStatus("uploading");
    setError("");
    setNodes([]);
    setSelectedNode(null);
    setPdfSearchTerm("");
    setPdfOpen(false);
    clearSession();

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${BACKEND_URL}/paper/analyze`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Analysis failed");

      const sid = data.sessionId;
      setPaperTitle(data.paperTitle);
      setNodes(data.nodes || []);
      setSessionId(sid);
      setPdfPage(1);
      setPdfOpen(true);
      setStatus("ready");
      // Persist immediately after successful analysis
      saveSession({ sessionId: sid, paperTitle: data.paperTitle, nodes: data.nodes || [] });
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, [sessionId]);

  // ── Node / reference interaction ─────────────────────────────────────────
  const handleNodeClick = useCallback((node) => {
    setSelectedNode(node);
    setShowKeyTerms(false);
  }, []);

  const handleReferenceClick = useCallback((page, search = "") => {
    setPdfPage(page);
    setPdfSearchTerm(search);
    setPdfOpen(true);
  }, []);

  const handleTermSelect = useCallback((node) => {
    setSelectedNode(node);
    setShowKeyTerms(false);
  }, []);

  // ── Clear / re-upload ─────────────────────────────────────────────────────
  const handleClear = useCallback(() => {
    if (sessionId) {
      fetch(`${BACKEND_URL}/paper/${sessionId}`, { method: "DELETE" })
        .catch(err => console.warn("Failed to delete paper from backend:", err));
    }
    clearSession();
    setStatus("idle");
    setNodes([]);
    setPaperTitle("");
    setSessionId(null);
    setSelectedNode(null);
    setPdfSearchTerm("");
    setPdfOpen(false);
  }, [sessionId]);

  return (
    <div className="paper-explorer">
      {/* ── Header ── */}
      <div className="pe-header">
        <div className="pe-title-row">
          <h2 className="pe-title">
            <span className="pe-icon">PE</span>
            Paper Knowledge Graph
          </h2>
          {paperTitle && <p className="pe-paper-name">{paperTitle}</p>}
        </div>
        <div className="pe-actions">
          {nodes.length > 0 && (
            <>
              <button
                className="pe-btn-terms"
                onClick={() => { setShowKeyTerms(true); setSelectedNode(null); }}
              >
                All Key Terms ({nodes.length})
              </button>
              {!pdfOpen && pdfUrl && (
                <button className="pe-btn-pdf" onClick={() => setPdfOpen(true)}>
                  Open PDF
                </button>
              )}
              <button className="pe-btn-clear" onClick={handleClear} title="Upload a new paper">
                ↺ New Paper
              </button>
            </>
          )}
        </div>
      </div>

      {/* ── Canvas area ── */}
      <div className="pe-canvas-wrapper">
        {status === "idle" && (
          <UploadZone onFile={handleFileUpload} />
        )}

        {status === "uploading" && (
          <div className="pe-loading">
            <img src="/hexagon-loader.svg" alt="Loading…" className="pe-hex-loader" />
            <p>Extracting concepts from PDF…</p>
            <p className="pe-loading-sub">Running Python pipeline (may take 60-90s)</p>
          </div>
        )}

        {status === "error" && (
          <div className="pe-error-state">
            <span className="pe-error-icon">Error</span>
            <p>{error}</p>
            <button onClick={() => setStatus("idle")}>Try Again</button>
          </div>
        )}

        {status === "ready" && (
          <GraphCanvas
            nodes={nodes}
            selectedNode={selectedNode}
            onNodeClick={handleNodeClick}
          />
        )}
      </div>

      {/* ── Node detail drawer ── */}
      {selectedNode && (
        <NodeDrawer
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
          onReferenceClick={handleReferenceClick}
        />
      )}

      {/* ── Key terms panel ── */}
      {showKeyTerms && (
        <KeyTermsPanel
          nodes={nodes}
          onClose={() => setShowKeyTerms(false)}
          onTermSelect={handleTermSelect}
          onReferenceClick={handleReferenceClick}
        />
      )}

      {/* ── Floating PDF window ── */}
      {pdfUrl && pdfOpen && (
          <PdfViewer
            url={pdfUrl}
            page={pdfPage}
            searchTerm={pdfSearchTerm}
            onSearchTermChange={setPdfSearchTerm}
            onPageChange={setPdfPage}
            onClose={() => setPdfOpen(false)}
          />
      )}
    </div>
  );
}
