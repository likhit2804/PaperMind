import express from "express";
import cors from "cors";
import path from "path";
import settings from "./config.js";
import healthRouter from "./routes/health.js";
import paperRouter from "./routes/paper.js";

const app = express();

// --------------- Middleware ---------------
app.use(cors());
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true }));

const frontendDir = path.join(settings.baseDir, "frontend-react", "dist");
app.use(express.static(frontendDir));
app.use("/app", express.static(frontendDir));
app.get("/", (_req, res) => {
  res.sendFile(path.join(frontendDir, "index.html"));
});

// --------------- Routes ---------------
app.use(healthRouter);
app.use(paperRouter);

// --------------- Error handler ---------------
app.use((err, _req, res, _next) => {
  console.error("Unhandled error:", err);
  res.status(err.status || 500).json({ detail: err.message || "Internal server error" });
});

// --------------- Start ---------------
app.listen(settings.port, () => {
  console.log(`${settings.appName} backend running at http://localhost:${settings.port}`);
});

export default app;
