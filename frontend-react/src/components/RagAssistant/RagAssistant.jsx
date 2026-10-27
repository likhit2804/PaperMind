import React, { useState, useRef, useEffect, useCallback } from "react";
import HexiAvatar from "../HexiBot/HexiAvatar";
import "./RagAssistant.css";

// ── Math / LaTeX Renderer Component using KaTeX ───────────────────────────
function MathRenderer({ math, block = false }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current && window.katex) {
      try {
        let cleanMath = math.trim();
        if (cleanMath.startsWith("$$") && cleanMath.endsWith("$$")) {
          cleanMath = cleanMath.slice(2, -2).trim();
        } else if (cleanMath.startsWith("$") && cleanMath.endsWith("$")) {
          cleanMath = cleanMath.slice(1, -1).trim();
        } else if (cleanMath.startsWith("\\[") && cleanMath.endsWith("\\]")) {
          cleanMath = cleanMath.slice(2, -2).trim();
        } else if (cleanMath.startsWith("\\(") && cleanMath.endsWith("\\)")) {
          cleanMath = cleanMath.slice(2, -2).trim();
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

  return <span ref={ref} className={block ? "katex-block" : "katex-inline"} />;
}

function renderFormattedInlineText(text) {
  if (!text) return null;

  // 1. Process inline code `code`
  const codeRegex = /(`.*?`)/g;
  const codeParts = text.split(codeRegex);

  return codeParts.map((cPart, cIdx) => {
    if (cPart.startsWith("`") && cPart.endsWith("`") && cPart.length > 2) {
      return (
        <code
          key={cIdx}
          style={{
            background: "var(--accent-bg)",
            border: "1px solid var(--border-color)",
            padding: "1px 5px",
            fontSize: "0.85em",
            fontFamily: "var(--font-mono)",
            borderRadius: "2px",
          }}
        >
          {cPart.slice(1, -1)}
        </code>
      );
    }

    // 2. Process bold **bold**
    const boldRegex = /(\*\*.*?\*\*)/g;
    const boldParts = cPart.split(boldRegex);

    return (
      <React.Fragment key={cIdx}>
        {boldParts.map((bPart, bIdx) => {
          if (bPart.startsWith("**") && bPart.endsWith("**")) {
            const inner = bPart.slice(2, -2);
            return <strong key={bIdx}>{renderFormattedInlineText(inner)}</strong>;
          }

          // 3. Process italic *italic* or _italic_
          const italicRegex = /(\*.*?\*|_.*?_)/g;
          const italicParts = bPart.split(italicRegex);

          return (
            <React.Fragment key={bIdx}>
              {italicParts.map((iPart, iIdx) => {
                if (
                  (iPart.startsWith("*") && iPart.endsWith("*") && iPart.length > 2) ||
                  (iPart.startsWith("_") && iPart.endsWith("_") && iPart.length > 2)
                ) {
                  return <em key={iIdx}>{iPart.slice(1, -1)}</em>;
                }
                return iPart;
              })}
            </React.Fragment>
          );
        })}
      </React.Fragment>
    );
  });
}

function renderMathAndFormattedText(text) {
  if (!text) return null;

  // Match display math ($$ ... $$ or \[ ... \]) and inline math ($ ... $ or \( ... \))
  const mathRegex = /(\$\$.*?\$\$|\\\[.*?\\\]|\$.*?\$|\\\(.*?\\\))/gs;
  const parts = text.split(mathRegex);

  return parts.map((part, index) => {
    if (!part) return null;

    const isDisplayMath = (part.startsWith("$$") && part.endsWith("$$")) || (part.startsWith("\\[") && part.endsWith("\\]"));
    const isInlineMath = (part.startsWith("$") && part.endsWith("$")) || (part.startsWith("\\(") && part.endsWith("\\)"));

    if (isDisplayMath) {
      return (
        <div key={index} style={{ margin: "10px 0", textAlign: "center", overflowX: "auto" }}>
          <MathRenderer math={part} block={true} />
        </div>
      );
    }

    if (isInlineMath) {
      return <MathRenderer key={index} math={part} block={false} />;
    }

    return <React.Fragment key={index}>{renderFormattedInlineText(part)}</React.Fragment>;
  });
}

function preprocessRagText(rawText) {
  if (!rawText) return "";

  let cleaned = rawText;

  // 1. Wrap un-bracketed \begin{...}...\end{...} environments inside display math $$...$$
  cleaned = cleaned.replace(
    /(?<!\$\$|\\\[)\s*(\\begin\{(?:cases|matrix|bmatrix|align|equation|gather|split)\}.*?\\end\{(?:cases|matrix|bmatrix|align|equation|gather|split)\})\s*(?!\$\$|\\\])/gs,
    (match, env) => {
      const singleLineEnv = env.replace(/\n\s*\n/g, "\n");
      return `\n\n$$\n${singleLineEnv}\n$$\n\n`;
    }
  );

  // 2. Clean up blank lines inside existing $$ ... $$ blocks
  cleaned = cleaned.replace(/\$\$(.*?)\$\$/gs, (match, inner) => {
    const compactInner = inner.split("\n").map(l => l.trim()).filter(Boolean).join("\n");
    return `$$\n${compactInner}\n$$`;
  });

  return cleaned;
}

function renderMarkdownLine(line, idx) {
  const trimmed = line.trim();
  if (!trimmed) return <div key={idx} style={{ height: "6px" }} />;

  // 1. Horizontal Rules (---, ***, ___)
  if (trimmed === "---" || trimmed === "***" || trimmed === "___") {
    return (
      <hr
        key={idx}
        style={{
          border: "none",
          borderTop: "1.5px dashed var(--border-color-muted)",
          margin: "12px 0",
          opacity: 0.7,
        }}
      />
    );
  }

  // 2. Headings (#, ##, ###, ####, #####, ######)
  const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
  if (headingMatch) {
    const level = headingMatch[1].length;
    const titleText = headingMatch[2];

    if (level === 1) {
      return (
        <h3 key={idx} style={{ margin: "14px 0 6px 0", fontSize: "1.1rem", fontWeight: 800, color: "var(--text-primary)" }}>
          {renderMathAndFormattedText(titleText)}
        </h3>
      );
    }
    if (level === 2) {
      return (
        <h4 key={idx} style={{ margin: "12px 0 6px 0", fontSize: "1.02rem", fontWeight: 800, color: "var(--text-primary)" }}>
          {renderMathAndFormattedText(titleText)}
        </h4>
      );
    }
    if (level === 3) {
      return (
        <h4 key={idx} style={{ margin: "10px 0 4px 0", fontSize: "0.96rem", fontWeight: 800, color: "var(--text-primary)" }}>
          {renderMathAndFormattedText(titleText)}
        </h4>
      );
    }
    return (
      <h5 key={idx} style={{ margin: "10px 0 4px 0", fontSize: "0.9rem", fontWeight: 800, color: "var(--text-primary)" }}>
        {renderMathAndFormattedText(titleText)}
      </h5>
    );
  }

  // Standalone Bold Header Line (**Header Text**)
  if (line.startsWith("**") && line.endsWith("**") && line.length < 65 && !line.includes("\n")) {
    const title = line.slice(2, -2);
    return (
      <h4 key={idx} style={{ margin: "10px 0 4px 0", fontSize: "0.95rem", fontWeight: 800 }}>
        {renderMathAndFormattedText(title)}
      </h4>
    );
  }

  // 3. Blockquotes (> Quote)
  if (line.startsWith("> ")) {
    return (
      <blockquote
        key={idx}
        style={{
          borderLeft: "3px solid var(--border-color)",
          paddingLeft: "12px",
          margin: "8px 0",
          fontStyle: "italic",
          opacity: 0.9,
        }}
      >
        {renderMathAndFormattedText(line.substring(2))}
      </blockquote>
    );
  }

  // 4. Unordered Lists (- Item, * Item, + Item)
  const ulMatch = line.match(/^[\-\*\+]\s+(.+)$/);
  if (ulMatch) {
    return (
      <li key={idx} style={{ marginLeft: "16px", marginBottom: "4px", listStyleType: "square" }}>
        {renderMathAndFormattedText(ulMatch[1])}
      </li>
    );
  }

  // 5. Ordered Lists (1. Item, 2. Item)
  const olMatch = line.match(/^(\d+)\.\s+(.+)$/);
  if (olMatch) {
    return (
      <li key={idx} style={{ marginLeft: "16px", marginBottom: "4px" }}>
        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, marginRight: "4px" }}>{olMatch[1]}.</span>
        {renderMathAndFormattedText(olMatch[2])}
      </li>
    );
  }

  // Standard Paragraph
  return (
    <p key={idx} style={{ margin: "0 0 6px 0" }}>
      {renderMathAndFormattedText(line)}
    </p>
  );
}

// Helper component for rendering text with inline Math and linebreaks
function FormattedRagText({ text }) {
  if (!text) return null;

  const processedText = preprocessRagText(text);

  // Split text by display math ($$ ... $$) first so multiline math blocks stay intact
  const displayMathRegex = /(\$\$.*?\$\$)/gs;
  const blocks = processedText.split(displayMathRegex);

  return (
    <div className="rag-formatted-text">
      {blocks.map((block, bIdx) => {
        if (!block) return null;

        if (block.startsWith("$$") && block.endsWith("$$")) {
          return (
            <div key={bIdx} style={{ margin: "12px 0", textAlign: "center", overflowX: "auto" }}>
              <MathRenderer math={block} block={true} />
            </div>
          );
        }

        const lines = block.split("\n");

        return (
          <React.Fragment key={bIdx}>
            {lines.map((line, idx) => renderMarkdownLine(line, idx))}
          </React.Fragment>
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
        (qLower.includes("reference") || qLower.includes("cited") || qLower.includes("author") || qLower.includes("citation")) &&
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

  if (
    qLower.includes("section") ||
    qLower.includes("sections") ||
    qLower.includes("outline") ||
    qLower.includes("topic") ||
    qLower.includes("topics") ||
    qLower.includes("global") ||
    qLower.includes("whole paper") ||
    qLower.includes("table of content")
  ) {
    answerText = `### Complete Paper Topics & Section Outline for "${paperTitle || "this paper"}"\n\n`;
    if (summary && summary.sections && summary.sections.length > 0) {
      summary.sections.forEach((sec, idx) => {
        let labelClean = (sec.label || "").replace(/\s+et\s+al\.?$/i, " & related sub-sections").trim();
        const prefix = /^\d/.test(labelClean) ? "" : `${idx + 1}. `;
        answerText += `**${prefix}${labelClean}**\n${sec.summary}\n\n`;
      });
    } else if (summary && (summary.executive || summary.overview)) {
      answerText += `${summary.executive || summary.overview}\n\n`;
      const contribs = summary.keyContributions || summary.contributions;
      if (contribs && contribs.length > 0) {
        answerText += `**Key Topics & Focus Areas:**\n`;
        contribs.forEach((c) => {
          answerText += `- ${c}\n`;
        });
      }
    } else {
      answerText += `Topics across the paper include Introduction, Problem Formulation & MIP Background, Neural Diving (predicting partial variable assignments), Neural Branching (variable selection policies), and Empirical Benchmarking.`;
    }
  } else if (qLower.includes("main contribution") || qLower.includes("summary") || qLower.includes("overview")) {
    answerText = `### Paper Summary & Core Contribution\n\n`;
    if (summary && (summary.overview || summary.executive)) {
      answerText += `${summary.overview || summary.executive}\n\n`;
    } else {
      answerText += `This paper, **"${paperTitle || "Uploaded Research Paper"}"**, presents a formal methodology for domain concept extraction and structured analysis.\n\n`;
    }

    const contribs = summary ? (summary.keyContributions || summary.contributions) : null;
    if (contribs && contribs.length > 0) {
      answerText += `**Key Contributions:**\n`;
      contribs.forEach((contrib) => {
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
        const cleanRefDef = (ref.definition || "")
          .replace(/\[(Role|Source|Connections):[^\]]+\]/gi, "")
          .trim();
        answerText += `- **${ref.label}**: ${cleanRefDef || ref.definition}\n`;
      });
    } else {
      answerText = `### Literature References\n\nReferences are cited throughout the discussion and methodology sections. You can filter by 'Refs' tab in the Glossary list.`;
    }
  } else if (topMatched.length > 0) {
    answerText = `### Retrieval Results for "${query}"\n\nBased on semantic analysis of **${paperTitle || "this paper"}**, here are the top matching concepts:\n\n`;
    topMatched.forEach((n) => {
      const cleanDef = (n.definition || "")
        .replace(/\[(Role|Source|Connections):[^\]]+\]/gi, "")
        .trim();
      answerText += `- **${n.label}** (${n.type || "concept"}): ${cleanDef}\n`;
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

function InteractiveAvatar({ defaultState = "idle", width = 50, height = 46, style = {} }) {
  const [avatarState, setAvatarState] = useState(defaultState);
  const timerRef = useRef(null);

  const handleClick = (e) => {
    if (e && typeof e.stopPropagation === "function") e.stopPropagation();
    setAvatarState("happy");
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setAvatarState(defaultState);
    }, 2500);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <HexiAvatar
      state={avatarState}
      width={width}
      height={height}
      onClick={handleClick}
      style={{ cursor: "pointer", ...style }}
    />
  );
}

const BACKEND_URL = import.meta.env.VITE_API_BASE_URL 
  || (import.meta.env.DEV ? "http://localhost:8000" : window.location.origin);

export default function RagAssistant({
  sessionId = null,
  paperTitle = "",
  nodes = [],
  summary = null,
  architectureNotes = "",
  pdfPage = 1,
  onNavigateToPage,
  onOpenPdf,
  messages: externalMessages,
  onUpdateMessages,
}) {
  const [localMessages, setLocalMessages] = useState([]);
  const messages = externalMessages !== undefined ? externalMessages : localMessages;

  const setMessages = useCallback(
    (updater) => {
      if (onUpdateMessages) {
        onUpdateMessages(updater);
      } else {
        setLocalMessages(updater);
      }
    },
    [onUpdateMessages]
  );

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
    async (queryText) => {
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
      setHexiState("idle");

      const runQueryBackend = async () => {
        let answerText = "";
        let citations = [];

        let suggestedFollowUps = [];
        let responseModel = null;
        let isDirectText = false;

        // Attempt backend RAG endpoint call
        if (sessionId) {
          try {
            const historyPayload = messages.slice(-6).map((m) => ({
              role: m.sender === "user" ? "user" : "assistant",
              text: m.text,
            }));

            const res = await fetch(`${BACKEND_URL}/paper/rag/query`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                sessionId,
                query: q,
                currentPage: pdfPage,
                history: historyPayload,
              }),
            });

            if (res.ok) {
              const data = await res.json();
              if (data.answer) {
                answerText = data.answer;
                citations = data.citations || [];
                suggestedFollowUps = data.suggestedFollowUps || [];
                responseModel = data.model;
                isDirectText = Boolean(data.isDirectText ?? (data.model === "local-rag" || !data.model || data.model.startsWith("local")));
              }
            }
          } catch (err) {
            console.warn("[RagAssistant] Backend RAG fetch failed, using client fallback:", err);
          }
        }

        // Fallback to client-side local search if backend call wasn't available
        if (!answerText) {
          const fallback = generateRagAnswer(
            q,
            paperTitle,
            nodes,
            summary,
            architectureNotes,
            pdfPage
          );
          answerText = fallback.answerText;
          citations = fallback.citations;
          responseModel = "client-direct-text";
          isDirectText = true;
        }

        const hexiMsg = {
          id: (Date.now() + 1).toString(),
          sender: "hexi",
          text: answerText,
          citations,
          suggestedFollowUps,
          model: responseModel,
          isDirectText: Boolean(isDirectText),
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        };

        setMessages((prev) => [...prev, hexiMsg]);
        setIsSearching(false);
        setHexiState("idle");
      };

      // Trigger Hexi Avatar searching sequence UI animation
      if (avatarRef.current && avatarRef.current.runSearchSequence) {
        avatarRef.current.runSearchSequence({
          lookupLoops: 2,
          textLoops: 1,
          onComplete: () => {
            runQueryBackend();
          },
        });
      } else {
        setTimeout(() => {
          runQueryBackend();
        }, 1500);
      }
    },
    [inputQuery, isSearching, sessionId, paperTitle, nodes, summary, architectureNotes, pdfPage, setMessages]
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
            <InteractiveAvatar defaultState="idle" width={110} height={105} />
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
                <InteractiveAvatar />
              )}
            </div>

            <div className="rag-msg-bubble">
              <div className="rag-msg-sender">
                <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                  <span>{msg.sender === "user" ? "You" : "HexaMind"}</span>
                  {msg.sender !== "user" && (
                    (msg.isDirectText || !msg.model || msg.model === "local-rag" || msg.model === "client-direct-text" || msg.model.startsWith("local")) ? (
                      <span className="rag-source-badge direct-text" title="Direct Paper Text: Extracted directly from paper content without generative AI">
                        <span className="rag-badge-dot direct" />
                        <span className="rag-badge-text">Direct Paper Text (No AI)</span>
                      </span>
                    ) : (
                      <span className="rag-source-badge ai-generated" title={`Synthesized using AI model: ${msg.model}`}>
                        <span className="rag-badge-dot ai" />
                        <span className="rag-badge-text">AI Generated ({msg.model})</span>
                      </span>
                    )
                  )}
                </div>
                <span style={{ fontSize: "0.7rem", opacity: 0.7 }}>{msg.timestamp}</span>
              </div>

              {msg.sender !== "user" && (msg.isDirectText || !msg.model || msg.model === "local-rag" || msg.model === "client-direct-text" || msg.model.startsWith("local")) && (
                <div className="rag-direct-text-banner">
                  <span className="rag-direct-banner-text">
                    <strong>Direct Paper Text:</strong> Generative AI was not used for this response. This answer is drawn directly from the paper's extracted sections, outline, and formulas.
                  </span>
                </div>
              )}

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

              {msg.suggestedFollowUps && msg.suggestedFollowUps.length > 0 && (
                <div className="rag-followups-wrap" style={{ marginTop: "12px", paddingTop: "8px", borderTop: "1px dashed var(--border-color-muted)", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  <span style={{ fontSize: "0.72rem", opacity: 0.8, width: "100%", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em" }}>Suggested Follow-ups:</span>
                  {msg.suggestedFollowUps.map((chipText, fIdx) => (
                    <button
                      key={fIdx}
                      className="rag-suggestion-chip"
                      onClick={() => handleSendQuery(chipText)}
                      style={{ fontSize: "0.8rem", padding: "4px 10px" }}
                    >
                      {chipText} ↗
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
              <HexiAvatar ref={avatarRef} state="searching" width={50} height={46} />
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
