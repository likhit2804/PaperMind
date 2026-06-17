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

  const referencesJson = path.join(outDir, "references.json");
  const detailsJson = path.join(outDir, "details.json");
  const conceptsJson = path.join(outDir, "concepts.json");
  const equationsJson = path.join(outDir, "equations.json");
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
  const referencesScript = path.join(
    settings.baseDir,
    "pipeline",
    "research_paper",
    "extract_paper_references.py"
  );
  const detailsScript = path.join(
    settings.baseDir,
    "pipeline",
    "research_paper",
    "extract_paper_details.py"
  );
  const equationsScript = path.join(
    settings.baseDir,
    "pipeline",
    "research_paper",
    "extract_paper_equations.py"
  );

  try {
    // Step 1: extract concepts
    console.log(`[paper/analyze] Running concept extractor for session ${sessionId}…`);
    await runPython([conceptsScript, pdfPath, conceptsJson], settings.baseDir);

    // Step 2, 3, 4, 5: run glossary, references, details, and equations extraction in parallel
    console.log(`[paper/analyze] Running glossary, references, details, and equations extractors for session ${sessionId}…`);
    await Promise.all([
      runPython([notesScript, pdfPath, conceptsJson, notesMd], settings.baseDir),
      runPython([referencesScript, pdfPath, referencesJson], settings.baseDir),
      runPython([detailsScript, pdfPath, detailsJson], settings.baseDir),
      runPython([equationsScript, pdfPath, equationsJson], settings.baseDir)
    ]);

    // Parse outputs
    const conceptsData = JSON.parse(fs.readFileSync(conceptsJson, "utf-8"));
    const mdText = fs.readFileSync(notesMd, "utf-8");
    const glossaryNodes = parseGlossaryMd(mdText);

    // Initialize combined nodes with type: "concept"
    const nodes = glossaryNodes.map(node => ({
      ...node,
      type: "concept"
    }));

    // Parse references if available
    if (fs.existsSync(referencesJson)) {
      try {
        const refData = JSON.parse(fs.readFileSync(referencesJson, "utf-8"));
        const refs = refData.references || [];
        refs.forEach(ref => {
          nodes.push({
            id: `ref_${ref.key}`,
            label: `[${ref.key}] ${ref.title.length > 25 ? ref.title.slice(0, 22) + "..." : ref.title} (${ref.year})`,
            definition: `[Role: ${ref.citation_role}] ${ref.contribution_summary}`,
            sources: (ref.contexts || []).map(ctx => ({
              page: ctx.page,
              section: ctx.section,
              contextText: ctx.sentence
            })),
            type: "reference"
          });
        });
      } catch (err) {
        console.warn(`[paper/analyze] Failed to parse references JSON:`, err);
      }
    }

    // Parse details (notations, assumptions, limitations, future work) if available
    if (fs.existsSync(detailsJson)) {
      try {
        const detailsData = JSON.parse(fs.readFileSync(detailsJson, "utf-8"));
        
        // 1. Notations
        const notations = detailsData.notations || [];
        notations.forEach(notation => {
          nodes.push({
            id: `notation_${notation.symbol.toLowerCase().replace(/[^a-z0-9]/g, "_")}`,
            label: `Notation: ${notation.symbol}`,
            definition: notation.meaning,
            sources: (notation.anchors || []).map(anc => ({
              page: anc.page,
              section: anc.section || anc.subsection,
              contextText: anc.anchor_text
            })),
            type: "notation"
          });
        });

        // 2. Assumptions & Limitations
        const assumpLim = detailsData.assumptions_and_limitations || [];
        assumpLim.forEach((item, index) => {
          nodes.push({
            id: `detail_${item.type.toLowerCase()}_${index}`,
            label: `${item.type}: ${item.description.length > 25 ? item.description.slice(0, 22) + "..." : item.description}`,
            definition: item.description,
            sources: (item.anchors || []).map(anc => ({
              page: anc.page,
              section: anc.section || anc.subsection,
              contextText: anc.anchor_text
            })),
            type: item.type.toLowerCase() // "assumption" or "limitation"
          });
        });

        // 3. Future work
        const futureWork = detailsData.future_work || [];
        futureWork.forEach((item, index) => {
          nodes.push({
            id: `detail_future_${index}`,
            label: `Future: ${item.description.length > 25 ? item.description.slice(0, 22) + "..." : item.description}`,
            definition: item.description,
            sources: (item.anchors || []).map(anc => ({
              page: anc.page,
              section: anc.section || anc.subsection,
              contextText: anc.anchor_text
            })),
            type: "future_work"
          });
        });
      } catch (err) {
        console.warn(`[paper/analyze] Failed to parse details JSON:`, err);
      }
    }

    // Parse equations if available
    if (fs.existsSync(equationsJson)) {
      try {
        const eqData = JSON.parse(fs.readFileSync(equationsJson, "utf-8"));
        const equations = eqData.equations || [];
        equations.forEach((eq, index) => {
          nodes.push({
            id: `equation_${index}`,
            label: eq.label,
            definition: eq.description,
            latex: eq.latex,
            rawText: eq.raw_text,
            sources: [{
              page: eq.page,
              section: eq.section,
              contextText: eq.raw_text
            }],
            type: "equation"
          });
        });
      } catch (err) {
        console.warn(`[paper/analyze] Failed to parse equations JSON:`, err);
      }
    }

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
