import { useState } from "react";

export default function KeyTermsPanel({ nodes, onClose, onTermSelect, onReferenceClick }) {
  const [search, setSearch] = useState("");

  const filtered = nodes.filter((n) =>
    n.label.toLowerCase().includes(search.toLowerCase()) ||
    n.definition?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="ktp-overlay">
      <div className="ktp-panel">
        {/* Header */}
        <div className="ktp-header">
          <div>
            <p className="ktp-eyebrow">Paper Knowledge</p>
            <h3 className="ktp-title">All Key Terms</h3>
          </div>
          <button className="ktp-close" onClick={onClose} aria-label="Close">X</button>
        </div>

        {/* Search */}
        <div className="ktp-search-wrap">
          <span className="ktp-search-icon">Search</span>
          <input
            className="ktp-search"
            type="text"
            placeholder="Search terms or definitions…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
          />
          <span className="ktp-count">{filtered.length}/{nodes.length}</span>
        </div>

        {/* List */}
        <div className="ktp-list">
          {filtered.map((node) => (
            <div key={node.id} className="ktp-item">
              <div className="ktp-item-header" onClick={() => onTermSelect(node)}>
                <span className="ktp-item-label">{node.label}</span>
                <span className="ktp-item-arrow">→ Graph</span>
              </div>
              <p className="ktp-item-def">{node.definition}</p>
              {node.sources && node.sources.length > 0 && (
                <div className="ktp-item-refs">
                  {node.sources.map((src, i) => (
                    <button
                      key={i}
                      className="ktp-ref-chip"
                      onClick={() => onReferenceClick(src.page, node.label)}
                      title={`Page ${src.page} · ${src.section}`}
                    >
                      p.{src.page}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          {filtered.length === 0 && (
            <p className="ktp-empty">No terms match your search.</p>
          )}
        </div>
      </div>
    </div>
  );
}
