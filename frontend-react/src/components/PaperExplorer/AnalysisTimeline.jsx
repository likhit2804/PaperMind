import { useState, useEffect } from "react";

const STAGES = [
  {
    id: "parser",
    title: "PDF & TEXT EXTRACTION",
    desc: "Reading document structure, section headers & raw text layout",
  },
  {
    id: "concepts",
    title: "CONCEPT & DEFINITION MAPPING",
    desc: "Extracting core technical terms, domain concepts & key ideas",
  },
  {
    id: "summary",
    title: "EXECUTIVE SUMMARY & METHODOLOGY",
    desc: "Synthesizing abstract, main findings & research claims",
  },
  {
    id: "notations",
    title: "LATEX EQUATIONS & NOTATIONS",
    desc: "Parsing mathematical formulas, symbols & variable definitions",
  },
  {
    id: "architecture",
    title: "SYSTEM ARCHITECTURE & ALGORITHMS",
    desc: "Extracting model diagrams, procedures & algorithmic steps",
  },
  {
    id: "references",
    title: "CITATIONS & LITERATURE MAPPING",
    desc: "Connecting cited papers, authors & reference dependencies",
  }
];

export default function AnalysisTimeline({ fileName, onCancel }) {
  const [elapsed, setElapsed] = useState(0);
  const [activeStageIdx, setActiveStageIdx] = useState(0);

  // Timer tick (seconds)
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Sync active stage based on elapsed seconds
  useEffect(() => {
    if (elapsed < 4) {
      setActiveStageIdx(0);
    } else if (elapsed < 10) {
      setActiveStageIdx(1);
    } else if (elapsed < 18) {
      setActiveStageIdx(2);
    } else if (elapsed < 26) {
      setActiveStageIdx(3);
    } else if (elapsed < 34) {
      setActiveStageIdx(4);
    } else {
      setActiveStageIdx(5);
    }
  }, [elapsed]);

  return (
    <div className="pipeline-studio-container">
      {/* ── LEFT SIDEBAR: PIPELINE EXECUTION STATE ── */}
      <div className="pipeline-state-panel glass-panel">
        <div className="pipeline-panel-header">
          <span className="pipeline-panel-title">PIPELINE EXECUTION STATE</span>
        </div>

        <div className="pipeline-timeline">
          {STAGES.map((stage, idx) => {
            const isDone = idx < activeStageIdx;
            const isActive = idx === activeStageIdx;
            const isWaiting = idx > activeStageIdx;

            return (
              <div
                key={stage.id}
                className={`pipeline-stage-item ${isDone ? "is-done" : ""} ${
                  isActive ? "is-active" : ""
                } ${isWaiting ? "is-waiting" : ""}`}
              >
                {/* Centered Diamond Node Column */}
                <div className="pipeline-node-col">
                  <span
                    className={`pipeline-diamond ${isDone || isActive ? "is-filled" : "is-empty"}`}
                    aria-label={isDone || isActive ? "Completed or active stage" : "Waiting stage"}
                  />
                </div>

                {/* Stage Details */}
                <div className="pipeline-stage-body">
                  <div className="pipeline-stage-title-row">
                    <span className="pipeline-stage-title">{stage.title}</span>
                    <span className={`pipeline-badge ${isDone ? "badge-done" : isActive ? "badge-active" : "badge-waiting"}`}>
                      {isDone ? "DONE" : isActive ? "ACTIVE" : "WAITING"}
                    </span>
                  </div>
                  <p className="pipeline-stage-desc">{stage.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── CENTER MAIN CANVAS: LOADER & WORKBENCH ── */}
      <div className="pipeline-center-canvas glass-panel">
        {/* Top Header Bar */}
        <div className="pipeline-center-header">
          <div className="pipeline-file-info">
            <span className="pipeline-file-label">FILE:</span>
            <span className="pipeline-filename">{fileName || "RESEARCH_PAPER.PDF"}</span>
          </div>

          <div className="pipeline-header-right">
            {onCancel && (
              <button className="pipeline-cancel-btn" onClick={onCancel} title="Cancel processing">
                ✕ CANCEL
              </button>
            )}
          </div>
        </div>

        {/* Center Loader Display */}
        <div className="pipeline-center-body">
          <div className="pipeline-loader-wrapper">
            <img src="/hexagon-loader.svg" alt="Processing..." className="pipeline-hex-loader" />
          </div>

          <div className="pipeline-current-status">
            <span className="pipeline-status-heading">
              {STAGES[activeStageIdx].title}
            </span>
            <p className="pipeline-status-subtext">
              {STAGES[activeStageIdx].desc}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
