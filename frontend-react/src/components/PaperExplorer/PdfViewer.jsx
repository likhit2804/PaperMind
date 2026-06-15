import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const DEFAULT_W = 500;
const DEFAULT_H = 680;

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export default function PdfViewer({ url, page, searchTerm = "", onSearchTermChange, onPageChange, onClose }) {
  const [pos, setPos] = useState({ x: window.innerWidth - DEFAULT_W - 24, y: 72 });
  const [size, setSize] = useState({ w: DEFAULT_W, h: DEFAULT_H });
  const [minimized, setMinimized] = useState(false);
  const [numPages, setNumPages] = useState(null);
  const [scale, setScale] = useState(1.1);
  const pageRef = useRef(null);
  const scrolledRef = useRef(false);

  const trimmedSearch = searchTerm.trim();
  const searchPattern = useMemo(() => {
    if (trimmedSearch.length < 2) return null;
    return new RegExp(`(${escapeRegExp(trimmedSearch)})`, "gi");
  }, [trimmedSearch]);

  useEffect(() => {
    scrolledRef.current = false;
  }, [page, trimmedSearch, scale]);

  const customTextRenderer = useCallback(
    ({ str }) => {
      if (!searchPattern) return str;
      const parts = str.split(searchPattern);
      if (parts.length === 1) return str;

      return parts
        .map((part, index) =>
          index % 2 === 1 ? `<mark class="pdf-match">${part}</mark>` : part
        )
        .join("");
    },
    [searchPattern]
  );

  const handleRenderTextLayerSuccess = useCallback(() => {
    if (!searchPattern || scrolledRef.current) return;

    window.setTimeout(() => {
      const container = pageRef.current;
      const firstMatch = container?.querySelector("mark.pdf-match");
      if (!firstMatch) return;

      scrolledRef.current = true;
      firstMatch.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 0);
  }, [searchPattern]);

  const onDragMouseDown = useCallback(
    (e) => {
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
    },
    [pos]
  );

  const onResizeMouseDown = useCallback(
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      const startX = e.clientX;
      const startY = e.clientY;
      const startWidth = size.w;
      const startHeight = size.h;

      const move = (event) => {
        setSize({
          w: Math.max(340, startWidth + event.clientX - startX),
          h: Math.max(260, startHeight + event.clientY - startY),
        });
      };

      const up = () => {
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
      };

      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    },
    [size]
  );

  const onDocumentLoadSuccess = ({ numPages: totalPages }) => setNumPages(totalPages);
  const safePage = numPages ? Math.min(Math.max(1, page), numPages) : page;

  return (
    <div
      className="pdf-float"
      style={{ left: pos.x, top: pos.y, width: size.w, height: minimized ? 44 : size.h }}
    >
      <div className="pdf-float-bar" onMouseDown={onDragMouseDown}>
        <span className="pdf-float-icon">PDF</span>
        <span className="pdf-float-title">PDF Preview · p.{safePage}</span>
        <div className="pdf-float-controls">
          <input
            className="pdf-search-input"
            type="search"
            value={searchTerm}
            onChange={(event) => onSearchTermChange?.(event.target.value)}
            placeholder="Find in page"
            title="Search inside the current PDF page"
          />
          <button
            className="pdf-ctrl-btn"
            onClick={() => setScale((currentScale) => Math.max(0.6, +(currentScale - 0.1).toFixed(1)))}
            title="Zoom out"
            type="button"
          >
            −
          </button>
          <span className="pdf-zoom-label">{Math.round(scale * 100)}%</span>
          <button
            className="pdf-ctrl-btn"
            onClick={() => setScale((currentScale) => Math.min(2.5, +(currentScale + 0.1).toFixed(1)))}
            title="Zoom in"
            type="button"
          >
            +
          </button>
          <button
            className="pdf-ctrl-btn"
            onClick={() => setMinimized((currentValue) => !currentValue)}
            title={minimized ? "Restore" : "Minimise"}
            style={{ marginLeft: 6 }}
            type="button"
          >
            {minimized ? "Restore" : "Min"}
          </button>
          <button className="pdf-ctrl-btn" onClick={onClose} title="Close" type="button">
            X
          </button>
        </div>
      </div>

      {!minimized && (
        <div className="pdf-float-body">
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
              key={`page-${safePage}-${scale}`}
              pageNumber={safePage}
              scale={scale}
              renderTextLayer
              renderAnnotationLayer
              width={size.w - 2}
              customTextRenderer={customTextRenderer}
              onRenderTextLayerSuccess={handleRenderTextLayerSuccess}
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

          <div className="pdf-resize-handle" onMouseDown={onResizeMouseDown} />
        </div>
      )}
    </div>
  );
}
