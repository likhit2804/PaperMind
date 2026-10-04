import React, { useState } from "react";
import HexiAvatar from "../HexiBot/HexiAvatar";
import RagAssistant from "./RagAssistant";
import "./HexiFloatingDrawer.css";

export default function HexiFloatingDrawer({
  paperTitle = "",
  nodes = [],
  summary = null,
  architectureNotes = "",
  pdfPage = 1,
  onNavigateToPage,
  onOpenPdf,
}) {
  const [isOpen, setIsOpen] = useState(false);

  const toggleDrawer = () => {
    setIsOpen((prev) => !prev);
  };

  return (
    <div className="hexi-floating-widget">
      {/* Drawer Slide-out Window */}
      {isOpen && (
        <div className="hexi-drawer-window">
          <div className="hexi-drawer-header-bar">
            <div className="hexi-drawer-title-group">
              <span style={{ fontWeight: 800, fontSize: "0.85rem", fontFamily: "var(--font-mono)" }}>
                HEXAMIND AI ASSISTANT
              </span>
            </div>
            <button
              className="hexi-drawer-close-btn"
              onClick={() => setIsOpen(false)}
              title="Close Drawer"
            >
              ✕
            </button>
          </div>

          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <RagAssistant
              paperTitle={paperTitle}
              nodes={nodes}
              summary={summary}
              architectureNotes={architectureNotes}
              pdfPage={pdfPage}
              onNavigateToPage={onNavigateToPage}
              onOpenPdf={onOpenPdf}
            />
          </div>
        </div>
      )}

      {/* Floating Action Avatar Button */}
      <button
        className="hexi-trigger-btn"
        onClick={toggleDrawer}
        title={isOpen ? "Close HexaMind Assistant" : "Ask HexaMind about this paper"}
      >
        <span className="hexi-trigger-pulse" />
        <span className="hexi-trigger-badge">{isOpen ? "CLOSE" : "HEXAMIND"}</span>
        <HexiAvatar state="idle" width={48} height={48} />
      </button>
    </div>
  );
}
