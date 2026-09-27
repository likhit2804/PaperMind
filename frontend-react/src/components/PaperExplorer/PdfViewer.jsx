import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const DEFAULT_W = 500;
const DEFAULT_H = 680;

// ── Math / LaTeX Renderer Component using KaTeX ──────────────────────────────
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
        }
        const hasNonLatexUnicode = /[^\x00-\x7F]/.test(cleanMath) && !/[\\a-zA-Z]/.test(cleanMath);
        if (hasNonLatexUnicode) {
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

// ── LaTeX Inline Text parser ─────────────────────────────────────────────────
function LatexInline({ text }) {
  if (!text) return null;
  const parts = text.split(/(\$(?:[^$]|\\\$)*\$|\\\(.*?\\\))/g);
  return (
    <>
      {parts.map((part, idx) => {
        if (part.startsWith("$") && part.endsWith("$")) {
          return <MathRenderer key={idx} math={part.slice(1, -1)} block={false} />;
        }
        if (part.startsWith("\\(") && part.endsWith("\\)")) {
          return <MathRenderer key={idx} math={part.slice(2, -2)} block={false} />;
        }
        return <span key={idx}>{cleanTextFormatting(part)}</span>;
      })}
    </>
  );
}

// ── LaTeX Document Preview Component ─────────────────────────────────────────
function LatexPreview({ texText, scale }) {
  const { title, author, body } = parseLatex(texText);

  // Normalize equation blocks
  let normalized = body
    .replace(/\\begin\s*\{(?:equation|align|eqnarray|gather)\*?\}([\s\S]*?)\\end\s*\{(?:equation|align|eqnarray|gather)\*?\}/g, "\n\n$$\n$1\n$$\n\n")
    .replace(/\\\[([\s\S]*?)\\\]/g, "\n\n$$\n$1\n$$\n\n");

  const blocks = normalized.split(/\n\s*\n+/);

  return (
    <div className="tex-preview-container" style={{ fontSize: `${scale * 0.8}rem` }}>
      {title && <h1 className="tex-preview-title">{stripFormatting(title)}</h1>}
      {author && <div className="tex-preview-author">{stripFormatting(author)}</div>}
      
      <div className="tex-preview-body">
        {blocks.map((block, idx) => {
          const trimmed = block.trim();
          if (!trimmed) return null;

          if (trimmed.startsWith("\\section")) {
            const heading = extractBracedContent(trimmed, "\\section");
            return <h2 key={idx} className="tex-preview-h2">{heading}</h2>;
          }
          if (trimmed.startsWith("\\subsection")) {
            const heading = extractBracedContent(trimmed, "\\subsection");
            return <h3 key={idx} className="tex-preview-h3">{heading}</h3>;
          }
          if (trimmed.startsWith("\\subsubsection")) {
            const heading = extractBracedContent(trimmed, "\\subsubsection");
            return <h4 key={idx} className="tex-preview-h4">{heading}</h4>;
          }

          if (trimmed.startsWith("\\begin{abstract}")) {
            const abstractContent = trimmed
              .replace(/\\begin\{abstract\}/, "")
              .replace(/\\end\{abstract\}/, "")
              .trim();
            return (
              <div key={idx} className="tex-preview-abstract">
                <strong>Abstract</strong>—<LatexInline text={abstractContent} />
              </div>
            );
          }

          if (trimmed.startsWith("$$") && trimmed.endsWith("$$")) {
            const math = trimmed.slice(2, -2).trim();
            return <MathRenderer key={idx} math={math} block={true} />;
          }

          // Handle list items
          if (trimmed.startsWith("\\begin{itemize}") || trimmed.startsWith("\\begin{enumerate}")) {
            const items = trimmed
              .replace(/\\begin\{(?:itemize|enumerate)\}/, "")
              .replace(/\\end\{(?:itemize|enumerate)\}/, "")
              .split(/\\item/g)
              .map(i => i.trim())
              .filter(Boolean);
            return (
              <ul key={idx} className="tex-preview-ul">
                {items.map((item, itemIdx) => (
                  <li key={itemIdx} className="tex-preview-li">
                    <LatexInline text={item} />
                  </li>
                ))}
              </ul>
            );
          }

          return (
            <p key={idx} className="tex-preview-p">
              <LatexInline text={trimmed} />
            </p>
          );
        })}
      </div>
    </div>
  );
}

// ── Helper Utilities ─────────────────────────────────────────────────────────
function parseLatex(tex) {
  let clean = tex.replace(/(?<!\\)%[^\n]*/g, "");

  let title = "";
  const titleMatch = clean.match(/\\title\s*\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}/);
  if (titleMatch) title = titleMatch[1].trim();

  let author = "";
  const authorMatch = clean.match(/\\author\s*\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}/);
  if (authorMatch) author = authorMatch[1].trim().replace(/\\\\/g, ", ");

  let body = clean;
  const docMatch = clean.match(/\\begin\s*\{document\}([\s\S]*)\\end\s*\{document\}/);
  if (docMatch) body = docMatch[1];

  body = body.replace(/\\maketitle/g, "");

  return { title, author, body };
}

function extractBracedContent(str, command) {
  const idx = str.indexOf(command);
  if (idx === -1) return str;
  const start = str.indexOf("{", idx);
  if (start === -1) return str;
  
  let depth = 1;
  let content = "";
  for (let i = start + 1; i < str.length; i++) {
    if (str[i] === "{") depth++;
    else if (str[i] === "}") depth--;
    
    if (depth === 0) {
      content = str.slice(start + 1, i);
      break;
    }
  }
  return cleanTextFormatting(content.trim());
}

function stripFormatting(str) {
  return str.replace(/\\[a-zA-Z]+/g, "").replace(/[\{\}]/g, "").trim();
}

function cleanTextFormatting(str) {
  return str
    .replace(/\\cite(?:p|t|alt|author)?\s*\{([^}]+)\}/g, "[$1]")
    .replace(/\\ref\s*\{([^}]+)\}/g, "$1")
    .replace(/\\[a-zA-Z]+\{([^}]+)\}/g, "$1")
    .replace(/\\(?:bar|tilde|hat)\s+([a-zA-Z])/g, "$1")
    .replace(/[\{\}]/g, "")
    .replace(/\\\\/g, "\n");
}

export default function PdfViewer({ url, page, onPageChange, onClose, docked = false, onToggleDock, fileType = "pdf" }) {
  const [pos, setPos] = useState({ x: window.innerWidth - DEFAULT_W - 24, y: 72 });
  const [size, setSize] = useState({ w: DEFAULT_W, h: DEFAULT_H });
  const [minimized, setMinimized] = useState(false);
  const [numPages, setNumPages] = useState(null);
  const [scale, setScale] = useState(1.1);
  const pageRef = useRef(null);

  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(DEFAULT_W);
  const [containerHeight, setContainerHeight] = useState(DEFAULT_H);

  // LaTeX support states
  const [texText, setTexText] = useState("");
  const [loadingTex, setLoadingTex] = useState(false);
  const [texError, setTexError] = useState(null);
  const [texMode, setTexMode] = useState("preview"); // 'preview' | 'source'

  useEffect(() => {
    if (fileType !== "tex" || !url) return;
    setLoadingTex(true);
    setTexError(null);
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load LaTeX file");
        return res.text();
      })
      .then((text) => {
        setTexText(text);
        setLoadingTex(false);
      })
      .catch((err) => {
        setTexError(err.message);
        setLoadingTex(false);
      });
  }, [url, fileType]);

  // ResizeObserver to dynamically track docked container width AND height
  useEffect(() => {
    if (!docked || !containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      if (!entries || entries.length === 0) return;
      const { width, height } = entries[0].contentRect;
      if (width > 0) setContainerWidth(width);
      if (height > 0) setContainerHeight(height);
    });

    observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
    };
  }, [docked]);

  const onDragMouseDown = (e) => {
    if (docked) return;
    if (e.target.closest(".pdf-float-controls")) return;
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const startPosX = pos.x;
    const startPosY = pos.y;

    const move = (event) => {
      setPos({
        x: Math.max(0, startPosX + event.clientX - startX),
        y: Math.max(0, startPosY + event.clientY - startY),
      });
    };

    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
    };

    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  };

  const onResizeMouseDown = (e, dir) => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const startY = e.clientY;
    const startW = size.w;
    const startH = size.h;
    const startPosX = pos.x;
    const startPosY = pos.y;

    const move = (ev) => {
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;

      let newW = startW;
      let newH = startH;
      let newX = startPosX;
      let newY = startPosY;

      // Horizontal
      if (dir.includes('e')) newW = Math.max(320, startW + dx);
      if (dir.includes('w')) {
        newW = Math.max(320, startW - dx);
        newX = startPosX + (startW - newW);
      }
      // Vertical
      if (dir.includes('s')) newH = Math.max(240, startH + dy);
      if (dir.includes('n')) {
        newH = Math.max(240, startH - dy);
        newY = startPosY + (startH - newH);
      }

      setSize({ w: newW, h: newH });
      setPos({ x: Math.max(0, newX), y: Math.max(0, newY) });
    };

    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    // Set cursor on body so it stays consistent during drag
    const cursors = { n:'ns-resize', s:'ns-resize', e:'ew-resize', w:'ew-resize', ne:'nesw-resize', sw:'nesw-resize', nw:'nwse-resize', se:'nwse-resize' };
    document.body.style.cursor = cursors[dir] || 'nwse-resize';
    document.body.style.userSelect = 'none';

    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  };

  const onDocumentLoadSuccess = ({ numPages: totalPages }) => setNumPages(totalPages);
  const safePage = numPages ? Math.min(Math.max(1, page), numPages) : page;

  return (
    <div
      ref={containerRef}
      className={`pdf-float ${docked ? "docked" : ""}`}
      style={docked ? {} : { left: pos.x, top: pos.y, width: size.w, height: minimized ? 44 : size.h }}
    >
      <style>{`
        .tex-editor-view {
          background: #1e1e1e;
          color: #d4d4d4;
          font-family: "Fira Code", "JetBrains Mono", Consolas, Monaco, monospace;
          height: calc(100% - 44px);
          width: 100%;
          overflow: auto;
          padding: 12px 0;
          text-align: left;
          border-radius: 0 0 6px 6px;
        }
        .tex-code-block {
          margin: 0;
          padding: 0;
        }
        .tex-code-line {
          display: flex;
          line-height: 1.5;
          padding: 0 16px;
        }
        .tex-code-line:hover {
          background: #2d2d2d;
        }
        .tex-line-num {
          color: #858585;
          width: 40px;
          min-width: 40px;
          user-select: none;
          text-align: right;
          padding-right: 16px;
        }
        .tex-line-content {
          white-space: pre-wrap;
          word-break: break-all;
        }
        
        /* Premium LaTeX Preview styles */
        .tex-preview-container {
          background: #1e1e1e;
          color: #d4d4d4;
          font-family: Georgia, Cambria, "Times New Roman", Times, serif;
          height: calc(100% - 44px);
          width: 100%;
          overflow-y: auto;
          padding: 24px 32px;
          text-align: justify;
          border-radius: 0 0 6px 6px;
          line-height: 1.6;
        }
        .tex-preview-title {
          font-size: 1.5rem;
          font-weight: 700;
          text-align: center;
          margin-bottom: 8px;
          font-family: system-ui, -apple-system, sans-serif;
          color: #ffffff;
          line-height: 1.3;
        }
        .tex-preview-author {
          font-size: 0.9rem;
          text-align: center;
          margin-bottom: 20px;
          color: #999999;
          font-family: system-ui, -apple-system, sans-serif;
        }
        .tex-preview-abstract {
          background: #252526;
          border-left: 4px solid #007acc;
          padding: 12px 16px;
          margin: 16px 0 20px 0;
          font-size: 0.85rem;
          border-radius: 0 4px 4px 0;
          font-style: italic;
          color: #cccccc;
        }
        .tex-preview-h2 {
          font-size: 1.2rem;
          font-weight: 600;
          margin-top: 22px;
          margin-bottom: 10px;
          border-bottom: 1px solid #3c3c3c;
          padding-bottom: 4px;
          color: #ffffff;
          font-family: system-ui, -apple-system, sans-serif;
        }
        .tex-preview-h3 {
          font-size: 1.05rem;
          font-weight: 600;
          margin-top: 16px;
          margin-bottom: 6px;
          color: #eeeeee;
          font-family: system-ui, -apple-system, sans-serif;
        }
        .tex-preview-h4 {
          font-size: 0.95rem;
          font-weight: 600;
          margin-top: 12px;
          margin-bottom: 4px;
          color: #dddddd;
          font-family: system-ui, -apple-system, sans-serif;
        }
        .tex-preview-p {
          margin-bottom: 12px;
          text-indent: 1.5em;
        }
        .tex-preview-p:first-of-type {
          text-indent: 0;
        }
        .tex-preview-ul {
          margin-left: 20px;
          margin-bottom: 12px;
        }
        .tex-preview-li {
          margin-bottom: 6px;
        }
        
        /* [data-theme="dark"] is actually LIGHT mode in index.css */
        [data-theme="dark"] .tex-preview-container {
          background: #ffffff;
          color: #222222;
          box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.05);
        }
        [data-theme="dark"] .tex-preview-title {
          color: #111111;
        }
        [data-theme="dark"] .tex-preview-author {
          color: #555555;
        }
        [data-theme="dark"] .tex-preview-abstract {
          background: #f7f9fa;
          border-left-color: #47a;
          color: #333333;
        }
        [data-theme="dark"] .tex-preview-h2 {
          border-bottom-color: #eaeaea;
          color: #111111;
        }
        [data-theme="dark"] .tex-preview-h3 {
          color: #eeeeee;
        }
        [data-theme="dark"] .tex-preview-h4 {
          color: #dddddd;
        }
      `}</style>
      <div className="pdf-float-bar" onMouseDown={onDragMouseDown}>
        <span className="pdf-float-icon" style={fileType === "tex" ? { backgroundColor: "#47a" } : {}}>{fileType === "tex" ? "TEX" : "PDF"}</span>
        <span className="pdf-float-title">
          {docked
            ? (fileType === "tex" ? "LaTeX Preview" : `p.${safePage}${numPages ? ` / ${numPages}` : ""}`)
            : (fileType === "tex" ? (texMode === "preview" ? "LaTeX Preview" : "LaTeX Source") : `PDF Preview · p.${safePage}`)
          }
        </span>
        <div className="pdf-float-controls">
          {/* ── DOCKED mode: minimal toolbar — just navigation + float ── */}
          {docked ? (
            <>
              {fileType === "tex" && (
                <button
                  className="pdf-ctrl-btn"
                  onClick={() => setTexMode(prev => prev === "preview" ? "source" : "preview")}
                  title={texMode === "preview" ? "Show raw source" : "Show preview"}
                  type="button"
                  style={{ width: "auto", padding: "0 8px", fontSize: "0.68rem" }}
                >
                  {texMode === "preview" ? "Source" : "Preview"}
                </button>
              )}
              {onToggleDock && (
                <button
                  className="pdf-ctrl-btn pdf-float-only-btn"
                  onClick={onToggleDock}
                  title="View paper in floating window"
                  type="button"
                >
                  ⤢ Float
                </button>
              )}
            </>
          ) : (
            /* ── FLOATING mode: full controls ── */
            <>
              {fileType === "tex" && (
                <button
                  className="pdf-ctrl-btn"
                  onClick={() => setTexMode(prev => prev === "preview" ? "source" : "preview")}
                  title={texMode === "preview" ? "Show raw LaTeX source" : "Show formatted preview"}
                  type="button"
                  style={{ width: "auto", padding: "0 8px", fontSize: "0.68rem" }}
                >
                  {texMode === "preview" ? "Raw Source" : "Preview"}
                </button>
              )}
              <button
                className="pdf-ctrl-btn"
                onClick={() => setScale(s => Math.max(0.6, +(s - 0.1).toFixed(1)))}
                title="Zoom out"
                type="button"
              >−</button>
              <span className="pdf-zoom-label">{Math.round(scale * 100)}%</span>
              <button
                className="pdf-ctrl-btn"
                onClick={() => setScale(s => Math.min(2.5, +(s + 0.1).toFixed(1)))}
                title="Zoom in"
                type="button"
              >+</button>
              {onToggleDock && (
                <button
                  className="pdf-ctrl-btn"
                  onClick={onToggleDock}
                  title="Dock to split view"
                  type="button"
                  style={{ width: "auto", padding: "0 8px", fontSize: "0.68rem" }}
                >
                  🗗 Dock
                </button>
              )}
              <button
                className="pdf-ctrl-btn"
                onClick={() => setMinimized(v => !v)}
                title={minimized ? "Restore" : "Minimise"}
                type="button"
              >
                {minimized ? "▲" : "▼"}
              </button>
              <button className="pdf-ctrl-btn" onClick={onClose} title="Close" type="button">✕</button>
            </>
          )}
        </div>
      </div>

      {!minimized && (
        <div className="pdf-float-body">
          {fileType === "tex" ? (
            loadingTex ? (
              <div className="pdf-doc-loading">
                <img src="/hexagon-loader.svg" alt="Loading..." className="pe-hex-loader-sm" />
                <span>Loading LaTeX Source...</span>
              </div>
            ) : texError ? (
              <div className="pdf-doc-error">{texError}</div>
            ) : texMode === "preview" ? (
              <LatexPreview texText={texText} scale={scale} />
            ) : (
              <div className="tex-editor-view" style={{ fontSize: `${scale * 0.75}rem` }}>
                <pre className="tex-code-block">
                  <code>
                    {texText.split("\n").map((line, idx) => (
                      <div key={idx} className="tex-code-line">
                        <span className="tex-line-num">{idx + 1}</span>
                        <span className="tex-line-content">{line || " "}</span>
                      </div>
                    ))}
                  </code>
                </pre>
              </div>
            )
          ) : (
            <>
              <Document
                file={url}
                onLoadSuccess={onDocumentLoadSuccess}
                loading={
                  <div className="pdf-doc-loading">
                    <img src="/hexagon-loader.svg" alt="Loading..." className="pe-hex-loader-sm" />
                    <span>Loading PDF...</span>
                  </div>
                }
                error={<div className="pdf-doc-error">Could not load PDF</div>}
              >
                <Page
                  inputRef={pageRef}
                  key={`page-${safePage}-${scale}-${docked}`}
                  pageNumber={safePage}
                  scale={scale}
                  renderTextLayer
                  renderAnnotationLayer
                  height={docked ? containerHeight - 46 : undefined}
                  width={docked ? undefined : size.w - 2}
                />
              </Document>

              {numPages && (
                <div className="pdf-page-bar">
                  <button
                    className="pdf-page-btn"
                    disabled={safePage <= 1}
                    onClick={() => onPageChange?.(safePage - 1)}
                    type="button"
                  >
                    ‹
                  </button>
                  <span className="pdf-page-info">
                    Page <strong>{safePage}</strong> of {numPages}
                  </span>
                  <button
                    className="pdf-page-btn"
                    disabled={safePage >= numPages}
                    onClick={() => onPageChange?.(safePage + 1)}
                    type="button"
                  >
                    ›
                  </button>
                </div>
              )}
            </>
          )}

          {!docked && (
            <>
              <div className="pdf-rh pdf-rh-n"  onMouseDown={e => onResizeMouseDown(e,'n')} />
              <div className="pdf-rh pdf-rh-s"  onMouseDown={e => onResizeMouseDown(e,'s')} />
              <div className="pdf-rh pdf-rh-e"  onMouseDown={e => onResizeMouseDown(e,'e')} />
              <div className="pdf-rh pdf-rh-w"  onMouseDown={e => onResizeMouseDown(e,'w')} />
              <div className="pdf-rh pdf-rh-ne" onMouseDown={e => onResizeMouseDown(e,'ne')} />
              <div className="pdf-rh pdf-rh-nw" onMouseDown={e => onResizeMouseDown(e,'nw')} />
              <div className="pdf-rh pdf-rh-se" onMouseDown={e => onResizeMouseDown(e,'se')} />
              <div className="pdf-rh pdf-rh-sw" onMouseDown={e => onResizeMouseDown(e,'sw')} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
