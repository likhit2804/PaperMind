import { Router } from "express";
import multer from "multer";
import fs from "fs";
import path from "path";
import { spawn } from "child_process";
import { v4 as uuidv4 } from "uuid";
import settings from "../config.js";

const router = Router();

// ─── Storage ───────────────────────────────────────────────────────────────
const PAPERS_DIR = path.join(settings.baseDir, "backend-node", "src", "uploads", "papers");
if (!fs.existsSync(PAPERS_DIR)) fs.mkdirSync(PAPERS_DIR, { recursive: true });

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, PAPERS_DIR),
  filename: (_req, _file, cb) => cb(null, `${uuidv4()}.pdf`),
});
const upload = multer({
  storage,
  fileFilter: (_req, file, cb) => {
    if (file.originalname.toLowerCase().endsWith(".pdf")) return cb(null, true);
    cb(new Error("Only PDF files are accepted."));
  },
});

// ─── Python runner ──────────────────────────────────────────────────────────
function runPython(args, cwd) {
  return new Promise((resolve, reject) => {
    const pythonExe = process.env.PYTHON_PATH
      ? path.resolve(settings.baseDir, process.env.PYTHON_PATH)
      : "python";

    const proc = spawn(pythonExe, args, { cwd, env: { ...process.env } });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => (stdout += d.toString()));
    proc.stderr.on("data", (d) => (stderr += d.toString()));
    proc.on("close", (code) => {
      if (code === 0) resolve(stdout);
      else reject(new Error(`Python exited ${code}:\n${stderr}`));
    });
    proc.on("error", reject);
  });
}

// ─── Glossary parser ─────────────────────────────────────────────────────────
// Parses lines like:
//   * **term** *(Sources: Page 3 (Section 'Foo'), Page 5 (Section 'Bar'))*: definition text
function parseGlossaryMd(mdText) {
  const nodes = [];
  const lineRe = /^\* \*\*(.+?)\*\* \*\(Sources: (.+?)\)\*: (.+)$/;
  const srcRe = /Page (\d+) \(Section '(.+?)'\)/g;

  for (const line of mdText.split("\n")) {
    const m = line.trim().match(lineRe);
    if (!m) continue;

    const [, label, sourcesRaw, definition] = m;
    const sources = [];
    let sm;
    while ((sm = srcRe.exec(sourcesRaw)) !== null) {
      sources.push({ page: parseInt(sm[1], 10), section: sm[2] });
    }
    srcRe.lastIndex = 0; // reset for next iteration

    nodes.push({
      id: label.toLowerCase().replace(/\s+/g, "_"),
      label,
      definition,
      sources,
    });
  }
  return nodes;
}

// ─── POST /paper/analyze ────────────────────────────────────────────────────
router.post("/paper/analyze", upload.single("file"), async (req, res, next) => {
  const file = req.file;
  if (!file) return res.status(400).json({ detail: "No PDF file uploaded." });

  const sessionId = path.basename(file.filename, ".pdf"); // the uuid
  const pdfPath = file.path;
  const outDir = path.join(PAPERS_DIR, sessionId);
  fs.mkdirSync(outDir, { recursive: true });

  const conceptsJson = path.join(outDir, "concepts.json");
  const notesMd = path.join(outDir, "notes.md");

  // Pipeline script paths (relative to project root)
  const conceptsScript = path.join(
    settings.baseDir,
    "pipeline",
    "research_paper",
    "extract_paper_concepts.py"
  );
  const notesScript = path.join(
    settings.baseDir,
    "pipeline",
    "research_paper",
    "generate_paper_notes.py"
  );

  try {
    // Step 1: extract concepts
    console.log(`[paper/analyze] Running concept extractor for session ${sessionId}…`);
    await runPython([conceptsScript, pdfPath, conceptsJson], settings.baseDir);

    // Step 2: generate glossary with definitions + sources
    console.log(`[paper/analyze] Running notes generator for session ${sessionId}…`);
    await runPython([notesScript, pdfPath, conceptsJson, notesMd], settings.baseDir);

    // Parse outputs
    const conceptsData = JSON.parse(fs.readFileSync(conceptsJson, "utf-8"));
    const mdText = fs.readFileSync(notesMd, "utf-8");
    const nodes = parseGlossaryMd(mdText);

    res.json({
      sessionId,
      paperTitle: conceptsData.paper_title || "Research Paper",
      nodes,
      pdfUrl: `/paper/pdf/${sessionId}`,
    });
  } catch (err) {
    console.error("[paper/analyze] Pipeline failed:", err);
    // Clean up PDF on error to avoid orphan files
    try { fs.unlinkSync(pdfPath); } catch (_) {}
    next(err);
  }
});

// ─── GET /paper/pdf/:sessionId ───────────────────────────────────────────────
router.get("/paper/pdf/:sessionId", (req, res, next) => {
  try {
    const { sessionId } = req.params;
    // Sanitize: only allow uuid-shaped session ids (hex + dashes)
    if (!/^[0-9a-f-]{36}$/.test(sessionId)) {
      return res.status(400).json({ detail: "Invalid session ID." });
    }
    const pdfPath = path.join(PAPERS_DIR, `${sessionId}.pdf`);
    if (!fs.existsSync(pdfPath)) {
      return res.status(404).json({ detail: "PDF not found." });
    }
    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", "inline");
    fs.createReadStream(pdfPath).pipe(res);
  } catch (err) {
    next(err);
  }
});

// ─── Helper: delete all files for a session ──────────────────────────────────
function deleteSessionFiles(sessionId) {
  if (!/^[0-9a-f-]{36}$/.test(sessionId)) return;
  const pdfPath = path.join(PAPERS_DIR, `${sessionId}.pdf`);
  const outDir = path.join(PAPERS_DIR, sessionId);

  try {
    if (fs.existsSync(pdfPath)) {
      fs.unlinkSync(pdfPath);
      console.log(`[deleteSessionFiles] Deleted PDF: ${pdfPath}`);
    }
  } catch (err) {
    console.error(`[deleteSessionFiles] Failed to delete PDF ${pdfPath}:`, err);
  }

  try {
    if (fs.existsSync(outDir)) {
      fs.rmSync(outDir, { recursive: true, force: true });
      console.log(`[deleteSessionFiles] Deleted directory: ${outDir}`);
    }
  } catch (err) {
    console.error(`[deleteSessionFiles] Failed to delete directory ${outDir}:`, err);
  }
}

// ─── DELETE /paper/:sessionId ────────────────────────────────────────────────
router.delete("/paper/:sessionId", (req, res) => {
  const { sessionId } = req.params;
  if (!/^[0-9a-f-]{36}$/.test(sessionId)) {
    return res.status(400).json({ detail: "Invalid session ID." });
  }
  deleteSessionFiles(sessionId);
  res.json({ detail: "Session files deleted successfully." });
});

export default router;
