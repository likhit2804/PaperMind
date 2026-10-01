import express from "express";
import cors from "cors";
import path from "path";
import settings from "./config.js";
import { logger, requestLoggerMiddleware } from "./logger.js";
import healthRouter from "./routes/health.js";
import paperRouter from "./routes/paper.js";

const app = express();

// --------------- Middleware ---------------
app.use(requestLoggerMiddleware);
app.use(cors());
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true }));

import fs from "fs";

const frontendDir = path.join(settings.baseDir, "frontend-react", "dist");
if (fs.existsSync(frontendDir)) {
  app.use(express.static(frontendDir));
  app.use("/app", express.static(frontendDir));
  app.get("/", (_req, res) => {
    res.sendFile(path.join(frontendDir, "index.html"));
  });
} else {
  app.get("/", (_req, res) => {
    res.json({ message: "PaperMind Backend API Online", status: "ok" });
  });
}

// --------------- Routes ---------------
app.use(healthRouter);
app.use(paperRouter);

// --------------- Error handler ---------------
app.use((err, req, res, _next) => {
  logger.error(`Unhandled error on ${req.method} ${req.url}`, err);
  res.status(err.status || 500).json({ detail: err.message || "Internal server error" });
});

// --------------- Start ---------------
app.listen(settings.port, () => {
  logger.info(`${settings.appName} backend running at http://localhost:${settings.port}`);
});

export default app;

