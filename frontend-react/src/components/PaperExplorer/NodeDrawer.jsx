export default function NodeDrawer({ node, onClose, onReferenceClick }) {
  if (!node) return null;

  return (
    <div className="node-drawer" role="dialog" aria-label={`Details for ${node.label}`}>
      {/* Header */}
      <div className="nd-header">
        <div>
          <p className="nd-eyebrow">Concept</p>
          <h3 className="nd-title">{node.label}</h3>
        </div>
        <button className="nd-close" onClick={onClose} aria-label="Close">X</button>
      </div>

      {/* Definition */}
      <div className="nd-section">
        <p className="nd-label">Definition</p>
        <p className="nd-definition">{node.definition}</p>
      </div>

      {/* Source references */}
      {node.sources && node.sources.length > 0 && (
        <div className="nd-section">
          <p className="nd-label">Source References — click to jump in PDF</p>
          <div className="nd-refs">
            {node.sources.map((src, i) => (
              <button
                key={i}
                className="nd-ref-chip"
                onClick={() => onReferenceClick(src.page, node.label)}
                title={`Jump to Page ${src.page}, ${src.section}`}
              >
                <span className="nd-ref-page">Page {src.page}</span>
                {src.section && (
                  <span className="nd-ref-section">· {src.section}</span>
                )}
                <span className="nd-ref-arrow">↗</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {node.sources && node.sources.length === 0 && (
        <div className="nd-section">
          <p className="nd-label">Source References</p>
          <p className="nd-no-sources">No page references found in the paper.</p>
        </div>
      )}
    </div>
  );
}
