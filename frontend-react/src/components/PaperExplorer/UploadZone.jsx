import { useCallback } from "react";

export default function UploadZone({ onFile }) {
  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      const file = e.dataTransfer?.files?.[0];
      if (file?.name.toLowerCase().endsWith(".pdf")) onFile(file);
    },
    [onFile]
  );

  const handleChange = useCallback(
    (e) => {
      const file = e.target.files?.[0];
      if (file) onFile(file);
    },
    [onFile]
  );

  return (
    <div
      className="upload-zone"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
    >
      <div className="uz-inner">
        <div className="uz-icon">File</div>
        <h3 className="uz-heading">Drop your research paper here</h3>
        <p className="uz-sub">PDF format · The pipeline will extract all key concepts and build the knowledge graph</p>
        <label className="uz-btn" htmlFor="pdf-upload-input">
          Choose PDF
          <input
            id="pdf-upload-input"
            type="file"
            accept=".pdf"
            onChange={handleChange}
            style={{ display: "none" }}
          />
        </label>
        <p className="uz-note">Processing takes ~60-90 seconds depending on paper length</p>
      </div>
    </div>
  );
}
