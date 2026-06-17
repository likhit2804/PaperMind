import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const DEFAULT_W = 500;
const DEFAULT_H = 680;

export default function PdfViewer({ url, page, onPageChange, onClose, docked = false, onToggleDock }) {
  const [pos, setPos] = useState({ x: window.innerWidth - DEFAULT_W - 24, y: 72 });
  const [size, setSize] = useState({ w: DEFAULT_W, h: DEFAULT_H });
  const [minimized, setMinimized] = useState(false);
  const [numPages, setNumPages] = useState(null);
  const [scale, setScale] = useState(1.1);
  const pageRef = useRef(null);

  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(DEFAULT_W);

  // ResizeObserver to dynamically track docked container width
  useEffect(() => {
    if (!docked || !containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      if (!entries || entries.length === 0) return;
      const { width } = entries[0].contentRect;
      if (width > 0) {
        setContainerWidth(width);
      }
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

  const onResizeMouseDown = (e) => {
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
  };

  const onDocumentLoadSuccess = ({ numPages: totalPages }) => setNumPages(totalPages);
  const safePage = numPages ? Math.min(Math.max(1, page), numPages) : page;

  return (
    <div
      ref={containerRef}
      className={`pdf-float ${docked ? "docked" : ""}`}
      style={docked ? {} : { left: pos.x, top: pos.y, width: size.w, height: minimized ? 44 : size.h }}
    >
      <div className="pdf-float-bar" onMouseDown={onDragMouseDown}>
        <span className="pdf-float-icon">PDF</span>
        <span className="pdf-float-title">PDF Preview · p.{safePage}</span>
        <div className="pdf-float-controls">
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

          {/* Toggle Dock/Float */}
          {onToggleDock && (
            <button
              className="pdf-ctrl-btn toggle-dock-btn"
              onClick={onToggleDock}
              title={docked ? "Float window" : "Dock to side"}
              type="button"
              style={{ width: "auto", padding: "0 8px", fontSize: "0.68rem", display: "flex", gap: "3px", alignItems: "center" }}
            >
              <span>{docked ? "🗗 Float" : "🗗 Dock"}</span>
            </button>
          )}

          {!docked && (
            <button
              className="pdf-ctrl-btn"
              onClick={() => setMinimized((currentValue) => !currentValue)}
              title={minimized ? "Restore" : "Minimise"}
              style={{ marginLeft: 6 }}
              type="button"
            >
              {minimized ? "Restore" : "Min"}
            </button>
          )}
          
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
              key={`page-${safePage}-${scale}-${docked}`}
              pageNumber={safePage}
              scale={scale}
              renderTextLayer
              renderAnnotationLayer
              width={docked ? containerWidth - 20 : size.w - 2}
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

          {!docked && <div className="pdf-resize-handle" onMouseDown={onResizeMouseDown} />}
        </div>
      )}
    </div>
  );
}
