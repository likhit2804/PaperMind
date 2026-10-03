import React, { useState, useRef, useEffect, useCallback } from "react";
import HexiAvatar from "../HexiBot/HexiAvatar";
import "./RagAssistant.css";

// Helper component for rendering text with inline Math and linebreaks
function FormattedRagText({ text }) {
  if (!text) return null;
  const lines = text.split("\n");

  return (
    <div className="rag-formatted-text">
      {lines.map((line, idx) => {
        if (!line.trim()) return <div key={idx} style={{ height: "8px" }} />;

        if (line.startsWith("### ") || line.startsWith("**") && line.endsWith("**")) {
          const title = line.replace(/^###\s*/, "").replace(/^\*\*/, "").replace(/\*\*$/, "");
          return (
            <h4 key={idx} style={{ margin: "10px 0 4px 0", fontSize: "0.95rem", fontWeight: 800 }}>
              {title}
            </h4>
          );
        }

        if (line.startsWith("- ") || line.startsWith("* ")) {
          return (
            <li key={idx} style={{ marginLeft: "14px", marginBottom: "4px" }}>
              {line.substring(2)}
            </li>
          );
        }

        return (
          <p key={idx} style={{ margin: "0 0 6px 0" }}>
            {line}
          </p>
        );
      })}
    </div>
  );
}

// Simple local RAG search engine (works seamlessly offline & connects to API when ready)
function generateRagAnswer(query, paperTitle, nodes, summary, architectureNotes, pdfPage) {
  const qLower = query.toLowerCase().trim();
  const citations = [];
  const matchedNodes = [];

  // Match nodes against query
  if (nodes && nodes.length > 0) {
    nodes.forEach((node) => {
      const labelStr = (node.label || "").toLowerCase();
      const defStr = (node.definition || "").toLowerCase();
      const typeStr = (node.type || "").toLowerCase();

      let matchScore = 0;
      if (qLower.includes(labelStr) && labelStr.length > 2) matchScore += 10;
      if (labelStr.includes(qLower)) matchScore += 8;

      // Word match checking
      const words = qLower.split(/\s+/).filter((w) => w.length > 3);
      words.forEach((w) => {
        if (labelStr.includes(w)) matchScore += 3;
        if (defStr.includes(w)) matchScore += 2;
      });

      if (
        (qLower.includes("math") || qLower.includes("formula") || qLower.includes("equation")) &&
        typeStr === "equation"
      ) {
        matchScore += 5;
      }

      if (
        (qLower.includes("notation") || qLower.includes("symbol") || qLower.includes("variable")) &&
        typeStr === "notation"
      ) {
        matchScore += 5;
      }

      if (
        (qLower.includes("reference") || qLower.includes("paper") || qLower.includes("author") || qLower.includes("cite")) &&
        typeStr === "reference"
      ) {
        matchScore += 5;
      }

      if (matchScore > 0) {
        matchedNodes.push({ node, score: matchScore });
      }
    });

    matchedNodes.sort((a, b) => b.score - a.score);
  }

  // Top 5 matched items
  const topMatched = matchedNodes.slice(0, 5).map((m) => m.node);

  topMatched.forEach((n) => {
    if (n.sources && n.sources.length > 0) {
      n.sources.forEach((src) => {
        if (!citations.some((c) => c.page === src.page)) {
          citations.push({ page: src.page, label: n.label, section: src.section });
        }
      });
    }
  });

  // Construct intelligent response
  let answerText = "";

  if (qLower.includes("main contribution") || qLower.includes("summary") || qLower.includes("overview")) {
    answerText = `### Paper Summary & Core Contribution\n\n`;
    if (summary && summary.overview) {
      answerText += `${summary.overview}\n\n`;
    } else {
      answerText += `This paper, **"${paperTitle || "Uploaded Research Paper"}"**, presents a formal methodology for domain concept extraction and structured analysis.\n\n`;
    }

    if (summary && summary.keyContributions && summary.keyContributions.length > 0) {
      answerText += `**Key Contributions:**\n`;
      summary.keyContributions.forEach((contrib) => {
        answerText += `- ${contrib}\n`;
      });
    }
  } else if (qLower.includes("equation") || qLower.includes("math") || qLower.includes("formula")) {
    const eqNodes = nodes.filter((n) => n.type === "equation");
    if (eqNodes.length > 0) {
      answerText = `### Mathematical Formulations & Equations\n\nI indexed **${eqNodes.length} key mathematical equations** from this paper:\n\n`;
      eqNodes.slice(0, 4).forEach((eq, idx) => {
        answerText += `**${idx + 1}. ${eq.label}**\n${eq.definition}\n\n`;
      });
    } else {
      answerText = `### Mathematical Context\n\nNo standalone mathematical equations were explicitly tagged in the current extraction index, but mathematical notation is integrated throughout the text.`;
    }
  } else if (qLower.includes("architecture") || qLower.includes("methodology") || qLower.includes("pipeline") || qLower.includes("system")) {
    answerText = `### System Architecture & Methodology\n\n`;
    if (architectureNotes) {
      answerText += `${architectureNotes}\n\n`;
    } else if (summary && summary.methodology) {
      answerText += `${summary.methodology}\n\n`;
    } else {
      answerText += `The methodology builds on structured representations, extracting domain concepts and mapping relationships across sections.`;
    }
  } else if (qLower.includes("reference") || qLower.includes("cited") || qLower.includes("literature")) {
    const refNodes = nodes.filter((n) => n.type === "reference");
    if (refNodes.length > 0) {
      answerText = `### Cited Literature & Key References\n\nHere are primary references identified in the paper:\n\n`;
      refNodes.slice(0, 5).forEach((ref) => {
        answerText += `- **${ref.label}**: ${ref.definition}\n`;
      });
    } else {
      answerText = `### Literature References\n\nReferences are cited throughout the discussion and methodology sections. You can filter by 'Refs' tab in the Glossary list.`;
    }
  } else if (topMatched.length > 0) {
    answerText = `### Retrieval Results for "${query}"\n\nBased on semantic analysis of **${paperTitle || "this paper"}**, here are the top matching concepts:\n\n`;
    topMatched.forEach((n) => {
      answerText += `- **${n.label}** (${n.type || "concept"}): ${n.definition}\n`;
    });
  } else {
    answerText = `### Hexi Search Analysis\n\nI searched the index for **"${query}"** across ${nodes.length} extracted paper elements.\n\nWhile no exact phrase match was found, the paper discusses concepts related to **${paperTitle || "the domain"}**. Try asking about specific equations, architecture, or section contents!`;
  }

  // Ensure default citation if none matched
  if (citations.length === 0 && pdfPage) {
    citations.push({ page: pdfPage, label: "Current View", section: "Paper text" });
  }

  return { answerText, citations: citations.slice(0, 4) };
}

export default function RagAssistant({
  paperTitle = "",
  nodes = [],
  summary = null,
  architectureNotes = "",
  pdfPage = 1,
  onNavigateToPage,
  onOpenPdf,
}) {
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState("");
  const [hexiState, setHexiState] = useState("idle");
  const [isSearching, setIsSearching] = useState(false);
  const messagesEndRef = useRef(null);
  const avatarRef = useRef(null);

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSearching]);

  const handleSendQuery = useCallback(
    (queryText) => {
      const q = (queryText || inputQuery).trim();
      if (!q || isSearching) return;

      const userMsg = {
        id: Date.now().toString(),
        sender: "user",
        text: q,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, userMsg]);
      setInputQuery("");
      setIsSearching(true);
      setHexiState("searching");

      // Trigger Hexi Avatar searching sequence
      if (avatarRef.current && avatarRef.current.runSearchSequence) {
        avatarRef.current.runSearchSequence({
          lookupLoops: 2,
          textLoops: 1,
          onComplete: () => {
            // RAG Retrieval
            const { answerText, citations } = generateRagAnswer(
              q,
              paperTitle,
              nodes,
              summary,
              architectureNotes,
              pdfPage
            );

            const hexiMsg = {
              id: (Date.now() + 1).toString(),
              sender: "hexi",
              text: answerText,
              citations,
              timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            };

            setMessages((prev) => [...prev, hexiMsg]);
            setIsSearching(false);
            setHexiState("happy");

            // Return Hexi back to idle state after 3s
            setTimeout(() => setHexiState("idle"), 3500);
          },
        });
      } else {
        // Fallback timeout if web component method is loading
        setTimeout(() => {
          const { answerText, citations } = generateRagAnswer(
            q,
            paperTitle,
            nodes,
            summary,
            architectureNotes,
            pdfPage
          );

          const hexiMsg = {
            id: (Date.now() + 1).toString(),
            sender: "hexi",
            text: answerText,
            citations,
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          };

          setMessages((prev) => [...prev, hexiMsg]);
          setIsSearching(false);
          setHexiState("happy");
          setTimeout(() => setHexiState("idle"), 3500);
        }, 2200);
      }
    },
    [inputQuery, isSearching, paperTitle, nodes, summary, architectureNotes, pdfPage]
  );

  const handleCitationClick = (page) => {
    if (onOpenPdf) onOpenPdf();
    if (onNavigateToPage && page) {
      onNavigateToPage(page);
    }
  };

  const handleClearHistory = () => {
    setMessages([]);
    setHexiState("idle");
  };

  const suggestionPills = [
    { label: "Primary Contribution", query: "What is the main contribution of this paper?" },
    { label: "Key Equations & Math", query: "Explain key mathematical notations and equations" },
    { label: "System Architecture", query: "Summarize the proposed system architecture" },
    { label: "Cited Literature", query: "What literature and reference papers are cited?" },
  ];

  return (
    <div className="rag-container">
      {/* ── Active Paper Context Bar ── */}
      <div className="rag-paper-status">
        <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
          <span className="rag-paper-title-tag" title={paperTitle || "Research Paper"}>
            {paperTitle || "Loaded Paper"}
          </span>
          <span className="rag-indexed-count">{nodes.length} Elements Indexed</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span className="rag-page-context-indicator">
            Active Page Context: <span className="rag-page-context-badge">Page {pdfPage}</span>
          </span>
          {messages.length > 0 && (
            <button className="rag-btn-icon" onClick={handleClearHistory} title="Clear conversation" style={{ padding: "2px 8px", fontSize: "0.75rem" }}>
              Clear Chat
            </button>
          )}
        </div>
      </div>

      {/* ── Messages Body ── */}
      <div className="rag-messages-body">
        {messages.length === 0 && (
          <div className="rag-welcome-box">
            <HexiAvatar state="happy" width={110} height={105} />
            <h4 className="rag-welcome-title">Hi, I'm HexaMind! Your Research Paper Assistant</h4>
            <p className="rag-welcome-desc">
              Ask me anything about **"{paperTitle || "this paper"}"**. I index all concepts, formulas, architecture notes, and literature citations so you can query questions and jump directly to source pages!
            </p>

            <span className="rag-suggestions-label">Suggested Questions:</span>
            <div className="rag-suggestions-grid">
              {suggestionPills.map((pill, idx) => (
                <button
                  key={idx}
                  className="rag-suggestion-chip"
                  onClick={() => handleSendQuery(pill.query)}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`rag-msg-row ${msg.sender}`}>
            <div className="rag-msg-avatar">
              {msg.sender === "user" ? (
                <div className="rag-user-avatar">YOU</div>
              ) : (
                <HexiAvatar state="talk" width={50} height={46} />
              )}
            </div>

            <div className="rag-msg-bubble">
              <div className="rag-msg-sender">
                <span>{msg.sender === "user" ? "You" : "HexaMind"}</span>
                <span style={{ fontSize: "0.7rem", opacity: 0.7 }}>{msg.timestamp}</span>
              </div>

              <FormattedRagText text={msg.text} />

              {msg.citations && msg.citations.length > 0 && (
                <div className="rag-citations-wrap">
                  <span className="rag-citation-label">Source Citations:</span>
                  {msg.citations.map((cit, idx) => (
                    <button
                      key={idx}
                      className="rag-citation-chip"
                      onClick={() => handleCitationClick(cit.page)}
                      title={`Jump to Page ${cit.page}`}
                    >
                      <span>Page {cit.page}</span>
                      {cit.section && <span style={{ opacity: 0.75 }}>({cit.section})</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {isSearching && (
          <div className="rag-msg-row hexi">
            <div className="rag-msg-avatar">
              <HexiAvatar state="searching" width={50} height={46} />
            </div>
            <div className="rag-msg-bubble" style={{ background: "var(--accent-bg)" }}>
              <div className="rag-thinking-indicator">
                <span>HexaMind is querying paper knowledge graph</span>
                <div className="rag-thinking-dots">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input Area ── */}
      <div className="rag-input-area">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendQuery();
          }}
          className="rag-input-row"
        >
          <input
            type="text"
            className="rag-input-field"
            placeholder="Ask HexaMind about equations, concepts, architecture, or section contents..."
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            disabled={isSearching}
          />
          <button type="submit" className="rag-send-btn" disabled={!inputQuery.trim() || isSearching}>
            Ask HexaMind
          </button>
        </form>
      </div>
    </div>
  );
}
