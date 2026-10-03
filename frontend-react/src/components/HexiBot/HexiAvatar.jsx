import React, { useEffect, useRef, useImperativeHandle, forwardRef } from "react";
import "./hexi-bot.js";
import { useTheme } from "../../context/ThemeContext";

const HexiAvatar = forwardRef(function HexiAvatar(
  { state = "idle", width = 160, height = 150, className = "", style = {}, onSearchComplete },
  ref
) {
  const botRef = useRef(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (botRef.current) {
      if (typeof botRef.current.setTheme === "function") {
        botRef.current.setTheme(theme || "light");
      }
    }
  }, [theme]);

  useEffect(() => {
    if (botRef.current) {
      if (state === "searching" || state === "search") {
        if (typeof botRef.current.runSearchSequence === "function") {
          botRef.current.runSearchSequence({
            lookupLoops: 2,
            textLoops: 2,
            onComplete: () => {
              if (onSearchComplete) onSearchComplete();
            },
          });
        }
      } else if (typeof botRef.current.setState === "function") {
        botRef.current.setState(state);
      }
    }
  }, [state, onSearchComplete]);

  useImperativeHandle(ref, () => ({
    setState: (newState) => {
      if (botRef.current && typeof botRef.current.setState === "function") {
        botRef.current.setState(newState);
      }
    },
    runSearchSequence: (opts) => {
      if (botRef.current && typeof botRef.current.runSearchSequence === "function") {
        botRef.current.runSearchSequence(opts);
      }
    },
  }));

  return (
    <div
      className={`hexi-avatar-container ${className}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: typeof width === "number" ? `${width}px` : width,
        height: typeof height === "number" ? `${height}px` : height,
        ...style,
      }}
    >
      <hexi-bot
        ref={botRef}
        state={state}
        theme={theme || "light"}
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
});

export default HexiAvatar;
