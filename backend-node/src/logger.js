import fs from "fs";
import path from "path";
import settings from "./config.js";

// Ensure logs directory exists at project root
const LOGS_DIR = path.join(settings.baseDir, "logs");
if (!fs.existsSync(LOGS_DIR)) {
  fs.mkdirSync(LOGS_DIR, { recursive: true });
}

const SERVER_LOG_FILE = path.join(LOGS_DIR, "server.log");
const HTTP_LOG_FILE = path.join(LOGS_DIR, "access.log");

function formatLogMessage(level, message, meta = null) {
  const timestamp = new Date().toISOString();
  let metaStr = "";
  if (meta) {
    if (meta instanceof Error) {
      metaStr = ` | Stack: ${meta.stack}`;
    } else {
      metaStr = ` | Data: ${JSON.stringify(meta)}`;
    }
  }
  return `[${timestamp}] [${level.toUpperCase()}] ${message}${metaStr}\n`;
}

function appendToFile(filePath, logLine) {
  fs.appendFile(filePath, logLine, (err) => {
    if (err) {
      console.error(`Failed to write log to ${filePath}:`, err.message);
    }
  });
}

export const logger = {
  info(message, meta) {
    const formatted = formatLogMessage("INFO", message, meta);
    process.stdout.write(`\x1b[36m${formatted}\x1b[0m`); // Cyan console
    appendToFile(SERVER_LOG_FILE, formatted);
  },

  warn(message, meta) {
    const formatted = formatLogMessage("WARN", message, meta);
    process.stdout.write(`\x1b[33m${formatted}\x1b[0m`); // Yellow console
    appendToFile(SERVER_LOG_FILE, formatted);
  },

  error(message, meta) {
    const formatted = formatLogMessage("ERROR", message, meta);
    process.stderr.write(`\x1b[31m${formatted}\x1b[0m`); // Red console
    appendToFile(SERVER_LOG_FILE, formatted);
  },

  debug(message, meta) {
    if (process.env.DEBUG || process.env.NODE_ENV === "development") {
      const formatted = formatLogMessage("DEBUG", message, meta);
      process.stdout.write(`\x1b[90m${formatted}\x1b[0m`); // Gray console
      appendToFile(SERVER_LOG_FILE, formatted);
    }
  }
};

/**
 * Express Middleware for detailed HTTP Request Logging
 */
export function requestLoggerMiddleware(req, res, next) {
  const startTime = Date.now();
  const reqId = req.headers["x-request-id"] || Math.random().toString(36).substring(2, 9);
  req.reqId = reqId;

  res.on("finish", () => {
    const durationMs = Date.now() - startTime;
    const statusCode = res.statusCode;
    const method = req.method;
    const url = req.originalUrl || req.url;
    const ip = req.ip || req.socket.remoteAddress || "-";

    const logLine = `[${new Date().toISOString()}] [HTTP] ${method} ${url} ${statusCode} - ${durationMs}ms - IP: ${ip} (ReqID: ${reqId})\n`;

    // Console output based on status code
    if (statusCode >= 500) {
      process.stderr.write(`\x1b[31m${logLine}\x1b[0m`);
    } else if (statusCode >= 400) {
      process.stdout.write(`\x1b[33m${logLine}\x1b[0m`);
    } else {
      process.stdout.write(`\x1b[32m${logLine}\x1b[0m`);
    }

    appendToFile(HTTP_LOG_FILE, logLine);
  });

  next();
}
