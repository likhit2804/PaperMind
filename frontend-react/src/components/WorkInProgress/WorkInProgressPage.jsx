import React from "react";
import HexiAvatar from "../HexiBot/HexiAvatar";
import "./WorkInProgressPage.css";

const WorkInProgressPage = ({
  featureName = "Module",
  scriptName = "",
}) => {
  return (
    <div className="pe-summary-scroll wip-container">
      <div className="pe-summary-hero wip-hero">
        <span className="pe-hero-badge">WORK IN PROGRESS • {featureName.toUpperCase()}</span>
        
        <div className="wip-content-row">
          <div className="wip-avatar-box">
            <HexiAvatar state="thinking" width={56} height={52} />
          </div>
          
          <div className="wip-text-box">
            <p className="pe-hero-text wip-one-liner">
              This feature is currently under active engineering upgrade for PaperMind — we apologize for the temporary inconvenience.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WorkInProgressPage;
