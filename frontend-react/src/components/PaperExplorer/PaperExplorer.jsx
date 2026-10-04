import { useState, useCallback, useEffect, useRef } from "react";
import PdfViewer from "./PdfViewer";
import UploadZone from "./UploadZone";
import AnalysisTimeline from "./AnalysisTimeline";
import RagAssistant from "../RagAssistant/RagAssistant";
import HexiAvatar from "../HexiBot/HexiAvatar";

const BACKEND_URL = import.meta.env.VITE_API_BASE_URL 
  || (import.meta.env.DEV ? "http://localhost:8000" : window.location.origin);
const STORAGE_KEY = "papermind_paper_session";

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

function groupSources(sources) {
  if (!sources || sources.length === 0) return [];
  const groups = {};
  sources.forEach((src) => {
    const page = src.page;
    const section = src.section || "the text";
    const key = `${page}_${section}`;
    if (!groups[key]) {
      groups[key] = {
        page,
        section: src.section,
        count: 0,
      };
    }
    groups[key].count += 1;
  });
  return Object.values(groups);
}

// ── Math / LaTeX Renderer Component using KaTeX CDN ───────────────────────────
function MathRenderer({ math, block = false }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current && window.katex) {
      try {
        let cleanMath = math.trim();
        // Remove enclosing $$ ... $$ or $ ... $
        if (cleanMath.startsWith("$$") && cleanMath.endsWith("$$")) {
          cleanMath = cleanMath.slice(2, -2).trim();
        } else if (cleanMath.startsWith("$") && cleanMath.endsWith("$")) {
          cleanMath = cleanMath.slice(1, -1).trim();
        }
        if (/[^-\uFFFF]/.test(cleanMath) === false && /[\u0080-\uFFFF]/.test(cleanMath) && !/[\\a-zA-Z]/.test(cleanMath)) {
          ref.current.textContent = math;
          return;
        }
        window.katex.render(cleanMath, ref.current, {
          displayMode: block,
          throwOnError: false,
        });
      } catch (err) {
        console.warn("KaTeX render error:", err);
        ref.current.textContent = math;
      }
    } else if (ref.current) {
      ref.current.textContent = math;
    }
  }, [math, block]);

  return <span ref={ref} />;
}

export default function PaperExplorer() {
  // ── Initialise from localStorage so data survives page refresh ──────────
  const saved = loadSavedSession();

  const [status, setStatus]           = useState(saved ? "ready" : "idle");
  const [error, setError]             = useState("");
  const [uploadingFileName, setUploadingFileName] = useState("");
  const [paperTitle, setPaperTitle]   = useState(saved?.paperTitle || "");
  const [nodes, setNodes]             = useState(saved?.nodes || []);
  const [summary, setSummary]         = useState(saved?.summary || null);
  const [architectureNotes, setArchitectureNotes] = useState(saved?.architectureNotes || "");
  const [mainView, setMainView]       = useState("glossary"); // 'glossary' | 'summary' | 'architecture'
  const [sessionId, setSessionId]     = useState(saved?.sessionId || null);
  const [fileType, setFileType]       = useState(saved?.fileType || "pdf");
  const [selectedNode, setSelectedNode] = useState(null);
  const [ragMessages, setRagMessages] = useState(saved?.ragMessages || []);
  
  // Tabs & Search states for the master list
  const [activeTab, setActiveTab]     = useState("all");
  const [search, setSearch]           = useState("");

  const [pdfPage, setPdfPage]         = useState(1);
  const [pdfOpen, setPdfOpen]         = useState(!!saved);
  const [pdfDocked, setPdfDocked]     = useState(true);
  const [autoFilterPage, setAutoFilterPage] = useState(true);

  const [showUpgradeBanner, setShowUpgradeBanner] = useState(false);

  // VS Code Layout Toggle States
  const [showPdf, setShowPdf] = useState(true);
  const [showMaster, setShowMaster] = useState(true);
  const [showDetail, setShowDetail] = useState(true);

  // Adjustable split pane widths
  const [pdfWidth, setPdfWidth] = useState(480);
  const [masterWidth, setMasterWidth] = useState(340);
  const [draggingResizer, setDraggingResizer] = useState(null); // null | 'pdf' | 'master'
  const dashboardRef = useRef(null);

  // pdfUrl is derived from sessionId — never stored directly (avoids stale host issues)
  const pdfUrl = sessionId ? `${BACKEND_URL}/paper/pdf/${sessionId}` : null;

  const isPdfVisible = !!(pdfOpen && pdfDocked && showPdf && pdfUrl);
  const isMasterVisible = showMaster;
  const isDetailVisible = showDetail;

  const togglePdf = useCallback(() => {
    if (!pdfOpen) {
      setPdfOpen(true);
      setShowPdf(true);
    } else {
      setShowPdf(prev => !prev);
    }
  }, [pdfOpen]);

  const toggleMaster = useCallback(() => {
    if (mainView !== "glossary") {
      setMainView("glossary");
      setShowMaster(true);
      return;
    }
    setShowMaster(prev => !prev);
  }, [mainView]);

  const toggleDetail = useCallback(() => {
    if (mainView !== "glossary") {
      setMainView("glossary");
      setShowDetail(true);
      return;
    }
    setShowDetail(prev => !prev);
  }, [mainView]);

  const startResizePdf = useCallback((e) => {
    e.preventDefault();
    setDraggingResizer("pdf");
  }, []);

  const startResizeMaster = useCallback((e) => {
    e.preventDefault();
    setDraggingResizer("master");
  }, []);

  // Window listeners for resizing
  useEffect(() => {
    if (!draggingResizer) return;

    const handleMouseMove = (e) => {
      if (!dashboardRef.current) return;
      const rect = dashboardRef.current.getBoundingClientRect();

      if (draggingResizer === "pdf") {
        const newWidth = e.clientX - rect.left;
        const minWidth = 320;
        const maxWidth = rect.width * 0.7;
        if (newWidth >= minWidth && newWidth <= maxWidth) {
          setPdfWidth(newWidth);
        }
      } else if (draggingResizer === "master") {
        const pdfPaneWidth = isPdfVisible ? pdfWidth + 8 : 0;
        const newMasterWidth = e.clientX - rect.left - pdfPaneWidth;
        const minWidth = 280;
        const maxWidth = (rect.width - pdfPaneWidth) * 0.7;
        if (newMasterWidth >= minWidth && newMasterWidth <= maxWidth) {
          setMasterWidth(newMasterWidth);
        }
      }
    };

    const handleMouseUp = () => {
      setDraggingResizer(null);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [draggingResizer, isPdfVisible, pdfWidth]);

  // VS Code hotkeys (Alt+1, Alt+2, Alt+3) for layout toggles
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.altKey) {
        if (e.key === "1") {
          e.preventDefault();
          if (pdfUrl) togglePdf();
        } else if (e.key === "2") {
          e.preventDefault();
          toggleMaster();
        } else if (e.key === "3") {
          e.preventDefault();
          toggleDetail();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [togglePdf, toggleMaster, toggleDetail, pdfUrl]);

  const getGridTemplateColumns = () => {
    if (mainView !== "glossary") {
      return isPdfVisible ? `${pdfWidth}px 8px 1fr` : "1fr";
    }
    const parts = [];
    const visibleCount = [isPdfVisible, isMasterVisible, isDetailVisible].filter(Boolean).length;
    if (visibleCount === 0) return "1fr";

    if (isPdfVisible) {
      if (isMasterVisible || isDetailVisible) {
        parts.push(`${pdfWidth}px`);
        parts.push("8px");
      } else {
        parts.push("1fr");
      }
    }

    if (isMasterVisible) {
      if (isDetailVisible) {
        parts.push(`${masterWidth}px`);
        parts.push("8px");
      } else {
        parts.push("1fr");
      }
    }

    if (isDetailVisible) {
      parts.push("1fr");
    }

    return parts.join(" ");
  };

  // Check if saved session has only concept nodes (old schema)
  useEffect(() => {
    if (nodes && nodes.length > 0) {
      const hasOtherTypes = nodes.some(n => n.type && n.type !== "concept");
      setShowUpgradeBanner(!hasOtherTypes);
    } else {
      setShowUpgradeBanner(false);
    }
  }, [nodes]);

  // ── Persist whenever session changes ────────────────────────────────────
  useEffect(() => {
    if (sessionId && nodes.length > 0) {
      saveSession({ sessionId, paperTitle, nodes, summary, architectureNotes, fileType, ragMessages });
    }
  }, [sessionId, paperTitle, nodes, summary, architectureNotes, fileType, ragMessages]);

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

    setUploadingFileName(file.name || "Research Paper");
    setStatus("uploading");
    setError("");
    setNodes([]);
    setSelectedNode(null);
    setSummary(null);
    setArchitectureNotes("");
    setRagMessages([]);
    setMainView("glossary");
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
      setSummary(data.summary || null);
      setArchitectureNotes(data.architectureNotes || "");
      setFileType(data.fileType || "pdf");
      setPdfPage(1);
      setPdfOpen(true);
      setStatus("ready");
      // Persist immediately after successful analysis
      saveSession({ 
        sessionId: sid, 
        paperTitle: data.paperTitle, 
        nodes: data.nodes || [], 
        summary: data.summary || null, 
        architectureNotes: data.architectureNotes || "",
        fileType: data.fileType || "pdf",
        ragMessages: []
      });
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, [sessionId]);

  // ── Node / reference interaction ─────────────────────────────────────────
  const handleReferenceClick = useCallback((page) => {
    setPdfPage(page);
    setPdfOpen(true);
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
    setSummary(null);
    setArchitectureNotes("");
    setRagMessages([]);
    setFileType("pdf");
    setMainView("glossary");
    setPdfOpen(false);
    setAutoFilterPage(true);
  }, [sessionId]);

  // ── Filtering Logic ──────────────────────────────────────────────────────
  const pageFilteredNodes = (pdfOpen && autoFilterPage)
    ? nodes.filter(n => n.type === "notation" || n.sources?.some(src => src.page === pdfPage))
    : nodes;

  const counts = {
    all: pageFilteredNodes.length,
    concept: pageFilteredNodes.filter(n => (n.type || "concept") === "concept").length,
    notation: pageFilteredNodes.filter(n => n.type === "notation").length,
    equation: pageFilteredNodes.filter(n => n.type === "equation").length,
    reference: pageFilteredNodes.filter(n => n.type === "reference").length,
  };

  const tabFiltered = pageFilteredNodes.filter((n) => {
    const type = n.type || "concept";
    if (activeTab === "all") return true;
    return type === activeTab;
  });

  const filtered = tabFiltered.filter((n) =>
    n.label.toLowerCase().includes(search.toLowerCase()) ||
    n.definition?.toLowerCase().includes(search.toLowerCase())
  );

  const displayType = (type) => {
    switch (type) {
      case "concept": return "Concept";
      case "notation": return "Notation";
      case "equation": return "Equation";
      case "reference": return "Reference";
      default: return "Detail";
    }
  };

  // ── Helper to Link Equations and Notations ──────────────────────────────
  const findUsedNotations = (equationNode, allNodes) => {
    if (equationNode.type !== "equation") return [];
    
    const notationNodes = allNodes.filter(n => n.type === "notation");
    const used = [];
    
    const latex = equationNode.latex || "";
    const definition = equationNode.definition || "";
    const rawText = equationNode.rawText || "";
    const searchPool = (latex + " " + definition + " " + rawText);
    
    for (const notation of notationNodes) {
      const symbol = notation.symbol || notation.label.replace(/^Notation:\s*/, "");
      if (!symbol) continue;
      
      const cleanSymbol = symbol.trim();
      if (!cleanSymbol) continue;
      
      let isUsed = false;
      
      // 1. Literal match in searchPool
      if (searchPool.includes(cleanSymbol)) {
        isUsed = true;
      }
      
      // 2. Greek unicode-to-latex mappings
      if (!isUsed) {
        const greekMap = {
          'α': '\\alpha', 'β': '\\beta', 'γ': '\\gamma', 'δ': '\\delta', 'ϵ': '\\epsilon', 'ε': '\\epsilon',
          'ζ': '\\zeta', 'η': '\\eta', 'θ': '\\theta', 'ι': '\\iota', 'κ': '\\kappa', 'λ': '\\lambda',
          'μ': '\\mu', 'ν': '\\nu', 'ξ': '\\xi', 'ο': '\\omicron', 'π': '\\pi', 'ρ': '\\rho',
          'σ': '\\sigma', 'τ': '\\tau', 'υ': '\\upsilon', 'φ': '\\phi', 'χ': '\\chi', 'ψ': '\\psi',
          'ω': '\\omega', 'Φ': '\\Phi', 'Ψ': '\\Psi', 'Ω': '\\Omega'
        };
        for (const [char, latexCmd] of Object.entries(greekMap)) {
          if (cleanSymbol.includes(char) && searchPool.includes(latexCmd)) {
            isUsed = true;
            break;
          }
        }
      }
      
      // 3. Subscript mapping (base_sub or base_{sub})
      if (!isUsed && cleanSymbol.includes('_')) {
        const parts = cleanSymbol.split('_');
        const base = parts[0];
        const sub = parts[1];
        const pattern1 = `${base}_{${sub}}`;
        const pattern2 = `${base}_${sub}`;
        if (searchPool.includes(pattern1) || searchPool.includes(pattern2)) {
          isUsed = true;
        }
      }
      
      if (isUsed) {
        used.push(notation);
      }
    }
    
    return used;
  };

  // ── Render Detail View Content ───────────────────────────────────────────
  const renderDetailContent = (node) => {
    let cleanDefinition = node.definition;
    let roleBadge = null;
    let connections = [];

    if (node.type === "reference") {
      const roleMatch = node.definition.match(/^\[Role:\s*(.+?)\]\s*(.+)$/i);
      if (roleMatch) {
        roleBadge = roleMatch[1];
        cleanDefinition = roleMatch[2];
      }
    } else if (node.type === "concept") {
      // Parse: "Def text [Role: Role explanation] [Connections: term1, term2]"
      let currentText = node.definition;
      const roleMatch = currentText.match(/\[Role:\s*(.+?)\]/i);
      if (roleMatch) {
        roleBadge = roleMatch[1];
        currentText = currentText.replace(/\[Role:\s*(.+?)\]/i, "").trim();
      }
      const connMatch = currentText.match(/\[Connections:\s*(.+?)\]/i);
      if (connMatch) {
        connections = connMatch[1].split(",").map(c => c.trim()).filter(Boolean);
        currentText = currentText.replace(/\[Connections:\s*(.+?)\]/i, "").trim();
      }
      cleanDefinition = currentText;
    }

    const getLabelForType = (type) => {
      switch (type) {
        case "concept": return "Concept Definition";
        case "notation": return "Mathematical Notation Meaning";
        case "equation": return "Equation Definition & Explanation";
        case "reference": return "Literature Reference Contribution";
        default: return "Details";
      }
    };

    const grouped = groupSources(node.sources);

    return (
      <div className={`pe-detail-body type-${node.type || "concept"}`}>
        <div className="pe-detail-header">
          <div>
            <p className={`nd-eyebrow type-${node.type || "concept"}`}>
              {node.type ? node.type.toUpperCase().replace('_', ' ') : 'Concept'}
            </p>
            <h3 className="pe-detail-title">
              {node.type === "notation" ? (
                <span>
                  Notation: <MathRenderer math={node.label.replace(/^Notation:\s*/, "")} />
                </span>
              ) : (
                node.label
              )}
            </h3>
          </div>
        </div>

        {roleBadge && (
          <div className="nd-section nd-role-section" style={{ padding: "14px 0" }}>
            <p className="nd-label">Influence Role</p>
            <span className={`nd-role-badge role-${roleBadge.toLowerCase().replace(/[^a-z]/g, "")}`}>
              {roleBadge}
            </span>
          </div>
        )}

        <div className="nd-section" style={{ padding: "14px 0" }}>
          <p className="nd-label">{getLabelForType(node.type)}</p>
          <p className="nd-definition">{cleanDefinition}</p>
        </div>

        {/* Equation LaTeX Formula Box */}
        {node.type === "equation" && node.latex && (
          <div className="pe-equation-box">
            <p className="nd-label">LaTeX Formula</p>
            <div className="pe-equation-formula">
              <MathRenderer math={node.latex} block={true} />
            </div>
            {node.rawText && (
              <details className="pe-equation-raw">
                <summary>View raw scanned text context</summary>
                <pre>{node.rawText}</pre>
              </details>
            )}
          </div>
        )}

        {/* Linked Notations for Equation */}
        {node.type === "equation" && (
          (() => {
            const linked = findUsedNotations(node, nodes);
            if (linked.length === 0) return null;
            return (
              <div className="nd-section" style={{ padding: "14px 0" }}>
                <p className="nd-label">Symbols Used in this Equation</p>
                <div className="pe-linked-notations-list">
                  {linked.map((not) => (
                    <div 
                      key={not.id} 
                      className="pe-linked-notation-item"
                      onClick={() => setSelectedNode(not)}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <strong style={{ color: "#facc15", fontFamily: "monospace", fontSize: "0.95rem" }}>
                          {not.symbol || not.label.replace(/^Notation:\s*/, "")}
                        </strong>
                        <span style={{ fontSize: "0.74rem", color: "var(--text-muted)", opacity: 0.8 }}>View Meaning ↗</span>
                      </div>
                      <p style={{ margin: "6px 0 0 0", fontSize: "0.85rem", color: "var(--text-main)", lineHeight: 1.4 }}>
                        {not.definition}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()
        )}

        {/* Connections List */}
        {connections.length > 0 && (
          <div className="nd-section" style={{ padding: "14px 0" }}>
            <p className="nd-label">Connections to other concepts</p>
            <div className="pe-connections-list">
              {connections.map((conn, idx) => {
                const targetNode = nodes.find(n => n.label.toLowerCase().trim() === conn.toLowerCase().trim());
                return (
                  <span 
                    key={idx} 
                    className="pe-connection-tag"
                    onClick={() => {
                      if (targetNode) setSelectedNode(targetNode);
                    }}
                    style={{ cursor: targetNode ? "pointer" : "default", opacity: targetNode ? 1 : 0.6 }}
                  >
                    {conn} {targetNode ? "↗" : ""}
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {grouped.length > 0 && (
          <div className="nd-section" style={{ padding: "14px 0", borderBottom: "none" }}>
            <p className="nd-label">Paper Occurrences — click to go to page</p>
            <div className="nd-occurrences-list">
              {grouped.map((src, i) => (
                <div
                  key={i}
                  className={`nd-occurrence-item type-${node.type || "concept"}`}
                  onClick={() => handleReferenceClick(src.page)}
                  title={`Jump to Page ${src.page}`}
                >
                  <span className="nd-occurrence-text">
                    It is mentioned in{" "}
                    <strong>
                      {src.section ? `Section '${src.section}'` : `Page ${src.page}`}
                    </strong>{" "}
                    (p. {src.page}){src.count > 1 ? ` — ${src.count} times` : ""}
                  </span>
                  <span className="nd-occurrence-arrow">↗</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {node.sources && node.sources.length === 0 && (
          <div className="nd-section" style={{ padding: "14px 0", borderBottom: "none" }}>
            <p className="nd-label">Source References</p>
            <p className="nd-no-sources">No exact page references found in the paper body.</p>
          </div>
        )}
      </div>
    );
  };

  const parseMarkdownInline = (text) => {
    const parts = [];
    let lastIdx = 0;
    const regex = /\*\*(.*?)\*\*|\*(.*?)\*/g;
    let match;
    let keyIdx = 0;
    
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIdx) {
        parts.push(text.slice(lastIdx, match.index));
      }
      if (match[1]) {
        parts.push(<strong key={keyIdx++}>{match[1]}</strong>);
      } else if (match[2]) {
        parts.push(<em key={keyIdx++}>{match[2]}</em>);
      }
      lastIdx = regex.lastIndex;
    }
    if (lastIdx < text.length) {
      parts.push(text.slice(lastIdx));
    }
    return parts.length > 0 ? parts : text;
  };

  const renderMarkdownRich = (md) => {
    const lines = md.split("\n");
    const elements = [];
    let inList = false;
    let listItems = [];
    let inTable = false;
    let tableHeaders = [];
    let tableRows = [];
    
    const flushList = (key) => {
      if (listItems.length > 0) {
        elements.push(
          <ul key={`ul-${key}`} className="pe-arch-list">
            {listItems.map((item, idx) => <li key={idx}>{item}</li>)}
          </ul>
        );
        listItems = [];
        inList = false;
      }
    };
    
    const flushTable = (key) => {
      if (tableRows.length > 0 || tableHeaders.length > 0) {
        elements.push(
          <div key={`table-container-${key}`} className="pe-table-wrapper">
            <table className="pe-arch-table">
              {tableHeaders.length > 0 && (
                <thead>
                  <tr>
                    {tableHeaders.map((h, idx) => <th key={idx}>{h}</th>)}
                  </tr>
                </thead>
              )}
              <tbody>
                {tableRows.map((row, rIdx) => (
                  <tr key={rIdx}>
                    {row.map((cell, cIdx) => <td key={cIdx}>{cell}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        tableHeaders = [];
        tableRows = [];
        inTable = false;
      }
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      if (line.startsWith("•") || line.startsWith("*") || line.startsWith("-")) {
        flushTable(i);
        inList = true;
        const text = line.replace(/^[•\*\-]\s*/, "");
        listItems.push(parseMarkdownInline(text));
        continue;
      } else if (inList) {
        flushList(i);
      }

      if (line.startsWith("|")) {
        flushList(i);
        inTable = true;
        const cells = line.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        if (cells.every(c => c.startsWith("-"))) {
          continue;
        }
        if (tableHeaders.length === 0 && tableRows.length === 0) {
          tableHeaders = cells;
        } else {
          tableRows.push(cells.map(c => parseMarkdownInline(c)));
        }
        continue;
      } else if (inTable) {
        flushTable(i);
      }

      if (line.startsWith("# ")) {
        elements.push(<h1 key={i}>{parseMarkdownInline(line.slice(2))}</h1>);
      } else if (line.startsWith("## ")) {
        elements.push(<h2 key={i}>{parseMarkdownInline(line.slice(3))}</h2>);
      } else if (line.startsWith("### ")) {
        elements.push(<h3 key={i}>{parseMarkdownInline(line.slice(4))}</h3>);
      } else if (line.startsWith("#### ")) {
        elements.push(<h4 key={i}>{parseMarkdownInline(line.slice(5))}</h4>);
      } else if (line) {
        elements.push(<p key={i}>{parseMarkdownInline(line)}</p>);
      }
    }
    
    flushList("end");
    flushTable("end");
    return elements;
  };

  const renderSummaryView = () => {
    if (!summary) return <div className="pe-summary-empty">No summary available.</div>;
    return (
      <div className="pe-summary-scroll">
        <div className="pe-summary-hero">
          <span className="pe-hero-badge">Executive Summary</span>
          <p className="pe-hero-text">{summary.executive}</p>
        </div>
        
        <div className="pe-summary-grid">
          {summary.research_question && (
            <div className="pe-summary-card">
              <h4>Core Research Question</h4>
              <p>{summary.research_question}</p>
            </div>
          )}
          {summary.tldr && (
            <div className="pe-summary-card">
              <h4>TL;DR</h4>
              <p>{summary.tldr}</p>
            </div>
          )}
        </div>

        {summary.contributions && summary.contributions.length > 0 && (
          <div className="pe-summary-section">
            <h3>Key Contributions</h3>
            <ul className="pe-contrib-list">
              {summary.contributions.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {summary.sections && summary.sections.length > 0 && (
          <div className="pe-summary-section">
            <h3>Section-by-Section Summary</h3>
            <div className="pe-sections-timeline">
              {summary.sections.map((sec, i) => (
                <div key={i} className="pe-section-summary-card">
                  <div className="pe-sec-header">
                    <span className="pe-sec-num">{i + 1}</span>
                    <h5>{sec.label}</h5>
                  </div>
                  <p className="pe-sec-desc">{sec.summary}</p>
                  {sec.key_points && sec.key_points.length > 0 && (
                    <ul className="pe-sec-points">
                      {sec.key_points.map((pt, j) => (
                        <li key={j}>{pt}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {summary.limitations && (
          <div className="pe-summary-section limitations">
            <h3>Limitations & Future Work</h3>
            <p>{summary.limitations}</p>
          </div>
        )}
      </div>
    );
  };

  const renderArchitectureView = () => {
    if (!architectureNotes) return <div className="pe-summary-empty">No architecture notes available.</div>;
    return (
      <div className="pe-summary-scroll markdown-body">
        {renderMarkdownRich(architectureNotes)}
      </div>
    );
  };

  const tabsRefVal = useRef(null);
  const tabsRef = useCallback((node) => {
    if (tabsRefVal.current && tabsRefVal.current._cleanupWheel) {
      tabsRefVal.current._cleanupWheel();
      tabsRefVal.current._cleanupWheel = null;
    }

    tabsRefVal.current = node;

    if (node) {
      const handleWheel = (e) => {
        if (e.deltaY !== 0) {
          e.preventDefault();
          node.scrollLeft += e.deltaY;
        }
      };
      node.addEventListener("wheel", handleWheel, { passive: false });
      node._cleanupWheel = () => {
        node.removeEventListener("wheel", handleWheel);
      };
    }
  }, []);

  return (
    <div className="paper-explorer">
      {/* ── Header ── */}
      <div className="pe-header">
        <div className="pe-title-row">
          <h2 className="pe-title">
            <span className="pe-icon">PE</span>
            Paper Details Dashboard
          </h2>
          {paperTitle && <p className="pe-paper-name">{paperTitle}</p>}
        </div>
        <div className="pe-actions">
          {nodes.length > 0 && (
            <>
              {/* Segmented Selector for Main Views */}
              <div className="pe-view-selector">
                <button 
                  className={`pe-view-btn ${mainView === "glossary" ? "active" : ""}`}
                  onClick={() => setMainView("glossary")}
                >
                  Glossary
                </button>
                <button 
                  className={`pe-view-btn ${mainView === "summary" ? "active" : ""}`}
                  onClick={() => setMainView("summary")}
                  disabled={!summary}
                >
                  Summary
                </button>
                <button 
                  className={`pe-view-btn ${mainView === "architecture" ? "active" : ""}`}
                  onClick={() => setMainView("architecture")}
                  disabled={!architectureNotes}
                >
                  Architecture
                </button>
                <button 
                  className={`pe-view-btn ${mainView === "rag" ? "active" : ""}`}
                  onClick={() => setMainView("rag")}
                  title="Ask questions about the paper using HexaMind AI Assistant"
                  style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
                >
                  <HexiAvatar state="idle" width={18} height={18} />
                  <span>HexaMind</span>
                </button>
              </div>

              <div className="pe-header-divider" />

              {/* VS Code Layout Toggles */}
              <div className="pe-layout-controls">
                <button 
                  className={`pe-layout-btn ${isPdfVisible ? "active" : ""}`} 
                  onClick={togglePdf}
                  title="Toggle PDF Panel (Alt+1)"
                  disabled={!pdfUrl}
                >
                  <svg className="layout-icon" viewBox="0 0 16 16" width="14" height="14">
                    <rect x="1" y="2" width="14" height="12" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="5.5" y1="2" x2="5.5" y2="14" stroke="currentColor" strokeWidth="1.5"/>
                    {isPdfVisible && <rect x="1.5" y="2.5" width="3.5" height="11" fill="currentColor" opacity="0.35"/>}
                  </svg>
                </button>
                <button 
                  className={`pe-layout-btn ${mainView === "glossary" && isMasterVisible ? "active" : ""}`} 
                  onClick={toggleMaster}
                  title="Toggle Glossary List (Alt+2)"
                >
                  <svg className="layout-icon" viewBox="0 0 16 16" width="14" height="14">
                    <rect x="1" y="2" width="14" height="12" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="5" y1="2" x2="5" y2="14" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="10" y1="2" x2="10" y2="14" stroke="currentColor" strokeWidth="1.5"/>
                    {mainView === "glossary" && isMasterVisible && <rect x="5.5" y="2.5" width="4" height="11" fill="currentColor" opacity="0.35"/>}
                  </svg>
                </button>
                <button 
                  className={`pe-layout-btn ${mainView === "glossary" && isDetailVisible ? "active" : ""}`} 
                  onClick={toggleDetail}
                  title="Toggle Detail Pane (Alt+3)"
                >
                  <svg className="layout-icon" viewBox="0 0 16 16" width="14" height="14">
                    <rect x="1" y="2" width="14" height="12" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="10.5" y1="2" x2="10.5" y2="14" stroke="currentColor" strokeWidth="1.5"/>
                    {mainView === "glossary" && isDetailVisible && <rect x="11" y="2.5" width="3.5" height="11" fill="currentColor" opacity="0.35"/>}
                  </svg>
                </button>
              </div>

              <div className="pe-header-divider" />

              {!pdfOpen && pdfUrl && (
                <button className="pe-btn-pdf" onClick={() => { setPdfOpen(true); setShowPdf(true); }}>
                  Open PDF
                </button>
              )}
              <button className="pe-btn-clear" onClick={handleClear} title="Upload a new paper">
                New Paper
              </button>
            </>
          )}
        </div>
      </div>

      {/* ── Upgrade Cache Banner ── */}
      {showUpgradeBanner && (
        <div className="pe-upgrade-banner">
          <div className="pe-upgrade-content">
            <strong>Dashboard Upgrade Available:</strong> This saved session only contains concept nodes. Click <strong>New Paper</strong> to re-upload and unlock math notations and cited literature in the details glossary!
          </div>
          <button className="pe-upgrade-dismiss" onClick={() => setShowUpgradeBanner(false)}>Dismiss</button>
        </div>
      )}

      {/* ── Dashboard Split View ── */}
      <div className="pe-canvas-wrapper pe-dashboard-wrapper">
        {status === "idle" && (
          <UploadZone onFile={handleFileUpload} />
        )}

        {status === "uploading" && (
          <AnalysisTimeline
            fileName={uploadingFileName}
            onCancel={() => {
              setStatus("idle");
              setUploadingFileName("");
            }}
          />
        )}

        {status === "error" && (
          <div className="pe-error-state">
            <span className="pe-error-icon">Error</span>
            <p>{error}</p>
            <button onClick={() => setStatus("idle")}>Try Again</button>
          </div>
        )}

        {status === "ready" && (
          <div 
            ref={dashboardRef}
            className={`pe-dashboard ${draggingResizer ? "is-resizing" : ""}`}
            style={{ gridTemplateColumns: getGridTemplateColumns() }}
          >
            {/* Docked PDF Pane */}
            {isPdfVisible && (
              <div className="pe-pdf-dock">
                <PdfViewer
                  url={pdfUrl}
                  page={pdfPage}
                  onPageChange={setPdfPage}
                  onClose={() => setPdfOpen(false)}
                  docked={true}
                  onToggleDock={() => setPdfDocked(false)}
                  fileType={fileType}
                />
              </div>
            )}

            {/* Resizer 1 (between PDF and Main Content) */}
            {isPdfVisible && (mainView === "glossary" ? (isMasterVisible || isDetailVisible) : true) && (
              <div
                className={`pe-resizer-col ${draggingResizer === "pdf" ? "dragging" : ""}`}
                onMouseDown={startResizePdf}
              >
                <div className="pe-resizer-line" />
              </div>
            )}

            {mainView === "glossary" ? (
              <>
                {/* Left Master List */}
                {isMasterVisible && (
                  <div className="pe-master-pane">
                    {/* Search */}
                    <div className="ktp-search-wrap">
                      <input
                        className="ktp-search"
                        type="text"
                        placeholder="Search extracted details..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                      <span className="ktp-count">{filtered.length}/{tabFiltered.length}</span>
                    </div>

                    {/* Active Page Guide Indicator with Toggle */}
                    {pdfOpen && (
                      <div className="pe-active-page-header-guide">
                        <div className="pe-active-page-guide-info">
                          <span className="pe-active-page-guide-text">
                            Glossary active on <strong>Page {pdfPage}</strong>
                          </span>
                        </div>
                        <label className="pe-auto-filter-toggle">
                          <input
                            type="checkbox"
                            checked={autoFilterPage}
                            onChange={(e) => setAutoFilterPage(e.target.checked)}
                          />
                          <span className="pe-auto-filter-toggle-label">Auto-filter</span>
                        </label>
                      </div>
                    )}

                    {/* Tabs */}
                    <div className="ktp-tabs" ref={tabsRef}>
                      <button
                        className={`ktp-tab-btn ${activeTab === "all" ? "active" : ""}`}
                        onClick={() => setActiveTab("all")}
                      >
                        All ({counts.all})
                      </button>
                      <button
                        className={`ktp-tab-btn ${activeTab === "concept" ? "active" : ""}`}
                        onClick={() => setActiveTab("concept")}
                      >
                        Concepts ({counts.concept})
                      </button>
                      <button
                        className={`ktp-tab-btn ${activeTab === "notation" ? "active" : ""}`}
                        onClick={() => setActiveTab("notation")}
                      >
                        Notations ({counts.notation})
                      </button>
                      <button
                        className={`ktp-tab-btn ${activeTab === "equation" ? "active" : ""}`}
                        onClick={() => setActiveTab("equation")}
                      >
                        Equations ({counts.equation})
                      </button>
                      <button
                        className={`ktp-tab-btn ${activeTab === "reference" ? "active" : ""}`}
                        onClick={() => setActiveTab("reference")}
                      >
                        Refs ({counts.reference})
                      </button>
                    </div>

                    {/* List */}
                    <div className="ktp-list">
                      {filtered.map((node) => {
                        const isOnActivePage = pdfOpen && node.sources?.some(src => src.page === pdfPage);
                        return (
                          <div
                            key={node.id}
                            className={`ktp-item ${selectedNode?.id === node.id ? "active" : ""} ${isOnActivePage ? "on-active-page" : ""} type-${node.type || "concept"}`}
                            onClick={() => setSelectedNode(node)}
                          >
                            <div className="ktp-item-header">
                              <div className="ktp-item-title-row">
                                <span className="ktp-item-label">
                                  {node.type === "notation" ? (
                                    <span>
                                      Notation: <MathRenderer math={node.label.replace(/^Notation:\s*/, "")} />
                                    </span>
                                  ) : (
                                    node.label
                                  )}
                                </span>
                                <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                                  {isOnActivePage && (
                                    <span className="ktp-active-page-indicator" title={`Present on Page ${pdfPage}`}>
                                      • Page {pdfPage}
                                    </span>
                                  )}
                                  <span className={`ktp-item-badge type-${node.type || "concept"}`}>
                                    {displayType(node.type || "concept")}
                                  </span>
                                </div>
                              </div>
                            </div>
                            <p className="ktp-item-def">{node.definition}</p>
                          </div>
                        );
                      })}
                      {filtered.length === 0 && (
                        <p className="ktp-empty">No matching details found.</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Resizer 2 (between Glossary and Details) */}
                {isMasterVisible && isDetailVisible && (
                  <div
                    className={`pe-resizer-col ${draggingResizer === "master" ? "dragging" : ""}`}
                    onMouseDown={startResizeMaster}
                  >
                    <div className="pe-resizer-line" />
                  </div>
                )}

                {/* Right Detail Pane */}
                {isDetailVisible && (
                  <div className="pe-detail-pane">
                    {selectedNode ? (
                      renderDetailContent(selectedNode)
                    ) : (
                      <div className="pe-detail-empty">
                        <h4>No Item Selected</h4>
                        <p>Select a concept, mathematical equation, literature reference, or research context parameter from the left sidebar to view detailed descriptions and page occurrences.</p>
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : mainView === "summary" ? (
              <div className="pe-summary-pane" style={{ overflow: "hidden", display: "flex", flexDirection: "column", height: "100%" }}>
                {renderSummaryView()}
              </div>
            ) : mainView === "architecture" ? (
              <div className="pe-architecture-pane" style={{ overflow: "hidden", display: "flex", flexDirection: "column", height: "100%" }}>
                {renderArchitectureView()}
              </div>
            ) : (
              <div className="pe-rag-pane" style={{ overflow: "hidden", display: "flex", flexDirection: "column", height: "100%" }}>
                <RagAssistant
                  sessionId={sessionId}
                  paperTitle={paperTitle}
                  nodes={nodes}
                  summary={summary}
                  architectureNotes={architectureNotes}
                  pdfPage={pdfPage}
                  onNavigateToPage={setPdfPage}
                  onOpenPdf={() => { setPdfOpen(true); setShowPdf(true); }}
                  messages={ragMessages}
                  onUpdateMessages={setRagMessages}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Floating PDF window ── */}
      {pdfUrl && pdfOpen && !pdfDocked && (
          <PdfViewer
            url={pdfUrl}
            page={pdfPage}
            onPageChange={setPdfPage}
            onClose={() => setPdfOpen(false)}
            docked={false}
            onToggleDock={() => setPdfDocked(true)}
            fileType={fileType}
          />
      )}
    </div>
  );
}
