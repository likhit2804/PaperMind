import { useState, useEffect } from "react";

const STAGES = [
  {
    id: "upload",
    title: "Document Ingestion & Text Parsing",
    desc: "Reading PDF structure, section headers, and raw text layout...",
    weight: 15,
    icon: ""
  },
  {
    id: "concepts",
    title: "Core Concept & Taxonomy Extraction",
    desc: "Identifying key technical terms, domain concepts, and dependencies...",
    weight: 30,
    icon: ""
  },
  {
    id: "parallel",
    title: "Parallel AI Synthesis & Notation Mapping",
    desc: "Generating notes, executive summary, cited references & LaTeX math...",
    weight: 40,
    icon: ""
  },
  {
    id: "graph",
    title: "Finalizing Dashboard & Session",
    desc: "Connecting citations, setting up glossary & initializing viewer...",
    weight: 15,
    icon: ""
  }
];

const SUB_TASKS = [
  { id: "notes", label: "Detailed Notes", icon: "" },
  { id: "summary", label: "Executive Summary", icon: "" },
  { id: "arch", label: "Architecture Notes", icon: "" },
  { id: "refs", label: "Cited Literature", icon: "" },
  { id: "notations", label: "Math Notations", icon: "" },
  { id: "equations", label: "Key Equations", icon: "" }
];

export default function AnalysisTimeline({ fileName, onCancel }) {
  const [progress, setProgress] = useState(5);
  const [elapsed, setElapsed] = useState(0);
  const [activeStageIdx, setActiveStageIdx] = useState(0);

  // Timer tick (seconds)
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Smooth progress increment simulation
  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 92) return 92; // cap at 92% until server responds
        // Slow down as progress increases
        const delta = prev < 20 ? 4 : prev < 50 ? 2 : prev < 80 ? 1 : 0.4;
        return Math.min(92, +(prev + delta).toFixed(1));
      });
    }, 400);

    return () => clearInterval(interval);
  }, []);

  // Sync active stage based on current progress percentage
  useEffect(() => {
    if (progress < 15) {
      setActiveStageIdx(0);
    } else if (progress < 45) {
      setActiveStageIdx(1);
    } else if (progress < 85) {
      setActiveStageIdx(2);
    } else {
      setActiveStageIdx(3);
    }
  }, [progress]);

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="analysis-timeline-container">
      <div className="at-card">
        {/* Top Header */}
        <div className="at-header">
          <div className="at-file-info">
            <div>
              <h3 className="at-filename">{fileName || "Research Paper"}</h3>
              <p className="at-subtitle">Analyzing paper structure & preparing paper explorer...</p>
            </div>
          </div>
          <div className="at-timer-badge">
            <span className="at-pulse-dot"></span>
            <span className="at-timer-label">Elapsed:</span>
            <span className="at-timer-val">{formatTime(elapsed)}</span>
          </div>
        </div>

        {/* Glowing Progress Bar */}
        <div className="at-progress-section">
          <div className="at-progress-bar-bg">
            <div
              className="at-progress-bar-fill"
              style={{ width: `${progress}%` }}
            >
              <div className="at-progress-glow"></div>
            </div>
          </div>
          <div className="at-progress-meta">
            <span className="at-stage-status">
              Stage {activeStageIdx + 1} of {STAGES.length}: {STAGES[activeStageIdx].title}
            </span>
            <span className="at-pct">{Math.round(progress)}%</span>
          </div>
        </div>

        {/* Stepper Timeline */}
        <div className="at-stepper">
          {STAGES.map((stage, idx) => {
            const isDone = idx < activeStageIdx;
            const isActive = idx === activeStageIdx;
            const isPending = idx > activeStageIdx;

            return (
              <div
                key={stage.id}
                className={`at-step ${isDone ? "is-done" : ""} ${isActive ? "is-active" : ""} ${isPending ? "is-pending" : ""}`}
              >
                <div className="at-step-indicator">
                  {isDone ? (
                    <span className="at-check">✓</span>
                  ) : isActive ? (
                    <div className="at-active-spinner"></div>
                  ) : (
                    <span className="at-step-num">{idx + 1}</span>
                  )}
                </div>

                <div className="at-step-content">
                  <div className="at-step-title-row">
                    <span className="at-step-icon">{stage.icon}</span>
                    <span className="at-step-title">{stage.title}</span>
                    {isActive && <span className="at-live-pill">Processing</span>}
                    {isDone && <span className="at-done-pill">Done</span>}
                  </div>
                  <p className="at-step-desc">{stage.desc}</p>

                  {/* Sub-tasks grid inside Parallel stage */}
                  {stage.id === "parallel" && (isActive || isDone) && (
                    <div className="at-subtasks-grid">
                      {SUB_TASKS.map((sub) => {
                        const subActive = isDone || (isActive && progress >= 50);
                        return (
                          <div
                            key={sub.id}
                            className={`at-subtask-badge ${subActive ? "sub-active" : "sub-pending"}`}
                          >
                            <span className="at-subtask-icon">{sub.icon}</span>
                            <span className="at-subtask-label">{sub.label}</span>
                            {subActive && <span className="at-sub-check">✓</span>}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Action Footer */}
        {onCancel && (
          <div className="at-footer">
            <button className="at-cancel-btn" onClick={onCancel} title="Cancel processing and return to upload">
              ✕ Cancel Pipeline
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
