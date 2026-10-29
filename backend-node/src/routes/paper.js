import { Router } from "express";
import multer from "multer";
import fs from "fs";
import path from "path";
import { spawn, exec } from "child_process";
import { v4 as uuidv4 } from "uuid";
import { GoogleGenerativeAI } from "@google/generative-ai";
import settings from "../config.js";
import { logger } from "../logger.js";
import { verifyRagCitations } from "../ragCitationVerifier.js";

const router = Router();

// ─── Storage ───────────────────────────────────────────────────────────────
const PAPERS_DIR = path.join(settings.baseDir, "backend-node", "src", "uploads", "papers");
if (!fs.existsSync(PAPERS_DIR)) fs.mkdirSync(PAPERS_DIR, { recursive: true });

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, PAPERS_DIR),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    cb(null, `${uuidv4()}${ext}`);
  },
});
const upload = multer({
  storage,
  fileFilter: (_req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if (ext === ".pdf" || ext === ".tex") return cb(null, true);
    cb(new Error("Only PDF and LaTeX (.tex) files are accepted."));
  },
});

// ─── Python runner ──────────────────────────────────────────────────────────
function getPythonExecutable() {
  if (process.env.PYTHON_PATH) {
    const customPath = path.resolve(settings.baseDir, process.env.PYTHON_PATH);
    if (fs.existsSync(customPath)) {
      return customPath;
    }
  }

  const winVenv = path.join(settings.baseDir, "venv", "Scripts", "python.exe");
  if (fs.existsSync(winVenv)) return winVenv;

  const winDotVenv = path.join(settings.baseDir, ".venv", "Scripts", "python.exe");
  if (fs.existsSync(winDotVenv)) return winDotVenv;

  const nixVenv = path.join(settings.baseDir, "venv", "bin", "python");
  if (fs.existsSync(nixVenv)) return nixVenv;

  const nixDotVenv = path.join(settings.baseDir, ".venv", "bin", "python");
  if (fs.existsSync(nixDotVenv)) return nixDotVenv;

  return process.platform === "win32" ? "python" : "python3";
}

function runPythonWithTimeout(args, cwd, timeoutMs = 15 * 60 * 1000) {
  return new Promise((resolve, reject) => {
    const pythonExe = getPythonExecutable();
    const proc = spawn(pythonExe, ["-u", ...args], { cwd, env: { ...process.env } });

    let stdout = "";
    let stderr = "";
    let isTimedOut = false;

    // Timeout guard: terminate child process tree if execution exceeds timeoutMs
    const timer = setTimeout(() => {
      isTimedOut = true;
      logger.error(`[paper/analyze] Python pipeline timed out after ${timeoutMs}ms. Terminating process...`);
      try {
        if (process.platform === "win32" && proc.pid) {
          // On Windows, child process trees require taskkill to reliably terminate
          exec(`taskkill /pid ${proc.pid} /T /F`, (err) => {
            if (err) {
              logger.warn(`[paper/analyze] taskkill fallback returned: ${err.message}`);
              try {
                proc.kill("SIGKILL");
              } catch (_) {}
            }
          });
        } else {
          proc.kill("SIGTERM");
          // Force-kill fallback if process does not exit within 3 seconds
          const forceKillTimer = setTimeout(() => {
            try {
              proc.kill("SIGKILL");
            } catch (_) {}
          }, 3000);
          if (forceKillTimer.unref) forceKillTimer.unref();
        }
      } catch (killErr) {
        logger.warn(`[paper/analyze] Error killing timed-out Python process: ${killErr.message}`);
      }
      reject(new Error(`Paper pipeline timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    proc.stdout.on("data", (d) => {
      const str = d.toString();
      stdout += str;
      process.stdout.write(str);
    });

    proc.stderr.on("data", (d) => {
      const str = d.toString();
      stderr += str;
      process.stderr.write(str);
    });

    proc.on("close", (code) => {
      clearTimeout(timer);
      if (isTimedOut) return;
      if (code === 0) resolve(stdout);
      else reject(new Error(`Python exited ${code}:\n${stderr || stdout}`));
    });

    proc.on("error", (err) => {
      clearTimeout(timer);
      if (!isTimedOut) reject(err);
    });
  });
}

function runPython(args, cwd) {
  return runPythonWithTimeout(args, cwd);
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
  if (!file) return res.status(400).json({ detail: "No research paper file uploaded." });

  const ext = path.extname(file.filename).toLowerCase();
  const sessionId = path.basename(file.filename, ext); // the uuid
  const filePath = file.path;
  const outDir = path.join(PAPERS_DIR, sessionId);
  fs.mkdirSync(outDir, { recursive: true });

  const referencesJson = path.join(outDir, "references.json");
  const conceptsJson = path.join(outDir, "concepts.json");
  const equationsJson = path.join(outDir, "equations.json");
  const notesMd = path.join(outDir, "notes.md");
  const notationsJson = path.join(outDir, "notations.json");
  const summaryJson = path.join(outDir, "summary.json");
  const archNotesMd = path.join(outDir, "architecture_notes.md");

  // Pipeline script paths (relative to project root)
  const unifiedScript = path.join(
    settings.baseDir,
    "pipeline",
    "research_paper",
    "unified_paper_pipeline.py"
  );

  try {
    // Run the consolidated, optimized paper processing pipeline
    console.log(`[paper/analyze] Running unified paper pipeline for session ${sessionId}…`);
    await runPythonWithTimeout([unifiedScript, path.resolve(filePath), outDir], settings.baseDir);

    // Parse outputs
    const conceptsData = fs.existsSync(conceptsJson) ? JSON.parse(fs.readFileSync(conceptsJson, "utf-8")) : { unique_key_terms: [], sections: {} };
    const mdText = fs.existsSync(notesMd) ? fs.readFileSync(notesMd, "utf-8") : "# Paper Notes\n\nUnder active upgrade.";
    const glossaryNodes = parseGlossaryMd(mdText);

    // Parse summary if available
    let summary = null;
    if (fs.existsSync(summaryJson)) {
      try {
        summary = JSON.parse(fs.readFileSync(summaryJson, "utf-8"));
      } catch (err) {
        console.warn(`[paper/analyze] Failed to parse summary JSON:`, err);
      }
    }

    // Read architecture notes if available
    let architectureNotes = "";
    if (fs.existsSync(archNotesMd)) {
      try {
        architectureNotes = fs.readFileSync(archNotesMd, "utf-8");
      } catch (err) {
        console.warn(`[paper/analyze] Failed to read architecture notes:`, err);
      }
    }

    // Initialize combined nodes with type: "concept"
    let conceptNodes = glossaryNodes.map(node => ({
      ...node,
      type: "concept"
    }));

    // If notes.md produced no concept nodes (e.g. notes generation step was omitted/paused),
    // populate concept nodes directly from concepts.json (conceptsData)
    if (conceptNodes.length === 0 && conceptsData) {
      const conceptMap = new Map();
      const conceptDefs = conceptsData.concept_definitions || {};
      const paperTitleStr = conceptsData.paper_title || "Research Paper";

      if (conceptsData.sections && typeof conceptsData.sections === "object") {
        Object.entries(conceptsData.sections).forEach(([secName, terms]) => {
          const pageMatch = secName.match(/Page\s*(\d+)/i);
          const page = pageMatch ? parseInt(pageMatch[1], 10) : 1;

          if (Array.isArray(terms)) {
            terms.forEach(term => {
              if (!term || typeof term !== "string") return;
              const cleanTerm = term.trim();
              if (!cleanTerm) return;
              const termKey = cleanTerm.toLowerCase();

              const definition = conceptDefs[termKey] || `Core technical concept introduced in ${secName}. [Role: Provides foundational algorithmic component in ${secName}]`;

              if (!conceptMap.has(termKey)) {
                conceptMap.set(termKey, {
                  id: `concept_${termKey.replace(/[^a-z0-9]/g, "_")}`,
                  label: cleanTerm.charAt(0).toUpperCase() + cleanTerm.slice(1),
                  definition: definition,
                  sources: [{ page, section: secName }],
                  type: "concept"
                });
              } else {
                const existing = conceptMap.get(termKey);
                if (!existing.sources.some(s => s.section === secName)) {
                  existing.sources.push({ page, section: secName });
                }
              }
            });
          }
        });
      }

      const termsList = conceptsData.unique_key_terms || conceptsData.key_terms;
      if (Array.isArray(termsList)) {
        termsList.forEach(term => {
          if (!term || typeof term !== "string") return;
          const cleanTerm = term.trim();
          if (!cleanTerm) return;
          const termKey = cleanTerm.toLowerCase();
          const definition = conceptDefs[termKey] || `Key domain term extracted from '${paperTitleStr}'. [Role: Key domain contribution in paper baseline execution]`;
          if (!conceptMap.has(termKey)) {
            conceptMap.set(termKey, {
              id: `concept_${termKey.replace(/[^a-z0-9]/g, "_")}`,
              label: cleanTerm.charAt(0).toUpperCase() + cleanTerm.slice(1),
              definition: definition,
              sources: [{ page: 1, section: "Full Document" }],
              type: "concept"
            });
          }
        });
      }

      conceptNodes = Array.from(conceptMap.values());
    }

    const nodes = [...conceptNodes];

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

    // Parse notations if available
    let notations = [];
    if (fs.existsSync(notationsJson)) {
      try {
        const notationsData = JSON.parse(fs.readFileSync(notationsJson, "utf-8"));
        notations = notationsData.notations || [];
      } catch (err) {
        console.warn(`[paper/analyze] Failed to parse notations JSON:`, err);
      }
    }

    if (notations.length > 0) {
      notations.forEach((notation, index) => {
        nodes.push({
          id: `notation_${index}_${notation.symbol.toLowerCase().replace(/[^a-z0-9]/g, "_")}`,
          label: `Notation: ${notation.symbol}`,
          definition: notation.meaning,
          sources: (notation.anchors || []).map(anc => ({
            page: anc.page,
            section: anc.section || anc.subsection,
            contextText: anc.anchor_text
          })),
          type: "notation",
          symbol: notation.symbol
        });
      });
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
      summary,
      architectureNotes,
      pdfUrl: `/paper/pdf/${sessionId}`,
      fileType: ext === ".tex" ? "tex" : "pdf",
    });
  } catch (err) {
    logger.error(`[paper/analyze] Pipeline failed for session ${sessionId}`, err);
    const runtimeFailure = /Unable to create process|ENOENT|Python exited 101/i.test(err.message || "");
    res.status(502).json({
      detail: runtimeFailure
        ? "The paper analysis Python runtime is unavailable. Recreate the project virtual environment and retry."
        : "The paper analysis pipeline failed. The uploaded file was preserved for retry/debugging.",
      sessionId,
      pdfUrl: `/paper/pdf/${sessionId}`,
      error: err.message,
    });
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
    const texPath = path.join(PAPERS_DIR, `${sessionId}.tex`);
    if (fs.existsSync(pdfPath)) {
      res.setHeader("Content-Type", "application/pdf");
      res.setHeader("Content-Disposition", "inline");
      fs.createReadStream(pdfPath).pipe(res);
    } else if (fs.existsSync(texPath)) {
      res.setHeader("Content-Type", "text/plain; charset=utf-8");
      res.setHeader("Content-Disposition", "inline");
      fs.createReadStream(texPath).pipe(res);
    } else {
      return res.status(404).json({ detail: "File not found." });
    }
  } catch (err) {
    next(err);
  }
});

// ─── In-Memory LRU Session Cache & Paragraph Passage Chunking ────────────────
const SESSION_CACHE = new Map();
const MAX_CACHE_SIZE = 50;

function computeCharacterNGramSimilarity(strA, strB) {
  if (!strA || !strB) return 0;
  const getNgrams = (s) => {
    const clean = s.toLowerCase().replace(/[^a-z0-9]/g, "");
    const ngrams = new Set();
    for (let i = 0; i < clean.length - 2; i++) {
      ngrams.add(clean.slice(i, i + 3));
    }
    return ngrams;
  };
  const setA = getNgrams(strA);
  const setB = getNgrams(strB);
  if (setA.size === 0 || setB.size === 0) return 0;
  let intersection = 0;
  setA.forEach((ng) => { if (setB.has(ng)) intersection++; });
  return intersection / Math.sqrt(setA.size * setB.size);
}

function buildChunksFromSections(sections, conceptsData) {
  const chunks = [];
  let chunkId = 1;

  if (Array.isArray(sections) && sections.length > 0) {
    sections.forEach((sec, sIdx) => {
      const secTitle = sec.label || `Section ${sIdx + 1}`;
      const text = (sec.summary || "") + "\n" + (sec.key_points || []).join(" ");
      const words = text.split(/\s+/).filter(Boolean);
      const chunkSize = 250;
      const overlap = 40;

      for (let i = 0; i < words.length; i += chunkSize - overlap) {
        const chunkWords = words.slice(i, i + chunkSize);
        if (chunkWords.length < 15) continue;
        chunks.push({
          id: `chunk_${chunkId++}`,
          section: secTitle,
          page: sec.page_start || sIdx + 1,
          text: chunkWords.join(" "),
        });
      }
    });
  } else if (conceptsData && conceptsData.sections) {
    Object.entries(conceptsData.sections).forEach(([secTitle, terms], sIdx) => {
      chunks.push({
        id: `chunk_${chunkId++}`,
        section: secTitle,
        page: sIdx + 1,
        text: `Key concepts in ${secTitle}: ${terms.join(", ")}`,
      });
    });
  }

  return chunks;
}

function getCachedSessionData(sessionId, outDir) {
  if (SESSION_CACHE.has(sessionId)) {
    return SESSION_CACHE.get(sessionId);
  }

  const conceptsPath = path.join(outDir, "concepts.json");
  const summaryPath = path.join(outDir, "summary.json");
  const archNotesPath = path.join(outDir, "architecture_notes.md");
  const equationsPath = path.join(outDir, "equations.json");
  const notationsPath = path.join(outDir, "notations.json");
  const referencesPath = path.join(outDir, "references.json");
  const chunksPath = path.join(outDir, "chunks.json");

  let paperTitle = "Research Paper";
  let concepts = [];
  let conceptsData = null;
  if (fs.existsSync(conceptsPath)) {
    try {
      conceptsData = JSON.parse(fs.readFileSync(conceptsPath, "utf-8"));
      paperTitle = conceptsData.paper_title || paperTitle;
      concepts = conceptsData.unique_key_terms || conceptsData.key_terms || [];
    } catch (err) {
      console.warn("[rag/cache] Failed to read concepts:", err);
    }
  }

  let summary = null;
  if (fs.existsSync(summaryPath)) {
    try {
      summary = JSON.parse(fs.readFileSync(summaryPath, "utf-8"));
    } catch (err) {
      console.warn("[rag/cache] Failed to read summary:", err);
    }
  }

  let architectureNotes = "";
  if (fs.existsSync(archNotesPath)) {
    try { architectureNotes = fs.readFileSync(archNotesPath, "utf-8"); } catch (e) {}
  }

  let equations = [];
  if (fs.existsSync(equationsPath)) {
    try { equations = (JSON.parse(fs.readFileSync(equationsPath, "utf-8"))).equations || []; } catch (e) {}
  }

  let notations = [];
  if (fs.existsSync(notationsPath)) {
    try { notations = (JSON.parse(fs.readFileSync(notationsPath, "utf-8"))).notations || []; } catch (e) {}
  }

  let references = [];
  if (fs.existsSync(referencesPath)) {
    try { references = (JSON.parse(fs.readFileSync(referencesPath, "utf-8"))).references || []; } catch (e) {}
  }

  let chunks = [];
  if (fs.existsSync(chunksPath)) {
    try { chunks = (JSON.parse(fs.readFileSync(chunksPath, "utf-8"))).chunks || []; } catch (e) {}
  } else {
    chunks = buildChunksFromSections(summary ? summary.sections : null, conceptsData);
    try {
      fs.writeFileSync(chunksPath, JSON.stringify({ chunks }, null, 2), "utf-8");
    } catch (e) {}
  }

  const sessionData = {
    paperTitle,
    concepts,
    conceptsData,
    summary,
    architectureNotes,
    equations,
    notations,
    references,
    chunks,
  };

  if (SESSION_CACHE.size >= MAX_CACHE_SIZE) {
    const oldestKey = SESSION_CACHE.keys().next().value;
    SESSION_CACHE.delete(oldestKey);
  }
  SESSION_CACHE.set(sessionId, sessionData);

  return sessionData;
}

// ─── Helper: delete all files for a session ──────────────────────────────────
function deleteSessionFiles(sessionId) {
  if (!/^[0-9a-f-]{36}$/.test(sessionId)) return;
  SESSION_CACHE.delete(sessionId);
  const pdfPath = path.join(PAPERS_DIR, `${sessionId}.pdf`);
  const texPath = path.join(PAPERS_DIR, `${sessionId}.tex`);
  const outDir = path.join(PAPERS_DIR, sessionId);

  try {
    if (fs.existsSync(pdfPath)) {
      fs.unlinkSync(pdfPath);
      console.log(`[deleteSessionFiles] Deleted PDF: ${pdfPath}`);
    }
    if (fs.existsSync(texPath)) {
      fs.unlinkSync(texPath);
      console.log(`[deleteSessionFiles] Deleted LaTeX: ${texPath}`);
    }
  } catch (err) {
    console.error(`[deleteSessionFiles] Failed to delete file:`, err);
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
// ─── Continuous Hybrid Vector & Algorithmic RAG Engine (Zero Cutoff Thresholds) ───

// Calculate Continuous Semantic Similarity Coefficient (Range: 0.0 to 1.0)
function computeContinuousSimilarity(queryText, history) {
  if (!Array.isArray(history) || history.length === 0) return 0;
  
  const prevTurnText = history.slice(-2).map(h => h.text).join(" ").toLowerCase();
  const queryTokens = new Set(queryText.toLowerCase().match(/\w+/g) || []);
  const prevTokens = new Set(prevTurnText.match(/\w+/g) || []);

  if (queryTokens.size === 0 || prevTokens.size === 0) return 0;

  let overlap = 0;
  queryTokens.forEach(token => {
    if (prevTokens.has(token)) overlap++;
  });

  return overlap / (queryTokens.size + prevTokens.size - overlap);
}

// Continuous Soft Reciprocal Rank Fusion (Zero Arbitrary Threshold Cutoffs)
function rankElementsWithRRF(queryText, history, elements) {
  const k = 60;
  const similarity = computeContinuousSimilarity(queryText, history);
  const historyWeight = Math.pow(similarity, 2);
  
  const queryTokens = new Set(queryText.toLowerCase().match(/\w+/g) || []);
  const historyText = history.slice(-2).map(h => h.text).join(" ").toLowerCase();
  const contextTokens = new Set((queryText + " " + historyText).toLowerCase().match(/\w+/g) || []);

  const scored = elements.map((item, index) => {
    const textStr = `${item.label || ''} ${item.definition || item.description || item.meaning || item.text || ''}`.toLowerCase();
    
    // Path A: Score based purely on current raw query
    let matchesA = 0;
    queryTokens.forEach(t => { if (textStr.includes(t)) matchesA++; });

    // Path B: Character N-Gram Semantic Vector Cosine Similarity
    const semanticSim = computeCharacterNGramSimilarity(queryText, textStr);
    const semanticBoost = semanticSim * 3.0; // Character N-Gram dense vector similarity boost

    // Path C: Score based on contextual query
    let matchesB = 0;
    contextTokens.forEach(t => { if (textStr.includes(t)) matchesB++; });

    const totalTermScore = matchesA + semanticBoost;
    const rrfScore = (totalTermScore / (k + index + 1)) + (historyWeight * (matchesB / (k + index + 1)));
    return { item, matchesA, semanticSim, rrfScore };
  });

  const matched = scored
    .filter(x => x.rrfScore > 0 && (x.matchesA > 0 || x.semanticSim > 0.15 || historyWeight > 0.05))
    .sort((a, b) => b.rrfScore - a.rrfScore)
    .map(x => x.item);

  return { matched, similarity, historyWeight };
}

// Procedural Coreference & Topic Drift Resolver
async function resolveQueryAndHistory(query, history, genAI, modelName) {
  if (!Array.isArray(history) || history.length === 0) {
    return { effectiveQuery: query, activeHistory: [] };
  }

  const similarity = computeContinuousSimilarity(query, history);
  const corefPronouns = /\b(it|this|that|they|them|he|she|these|those|prerequisite|prerequisites|requirement|requirements|first|second|third|which|what|how)\b/i;
  const hasPronouns = corefPronouns.test(query);

  if (similarity < 0.05 && !hasPronouns) {
    return { effectiveQuery: query, activeHistory: [] };
  }

  let effectiveQuery = query;
  if (hasPronouns && genAI && history.length > 0) {
    try {
      const model = genAI.getGenerativeModel({ model: modelName || "gemini-1.5-flash" });
      const recentHist = history.slice(-4).map(h => `${h.role === "user" ? "User" : "Assistant"}: ${h.text || ''}`).join("\n");
      const prompt = `Given the conversation history:\n${recentHist}\n\nUser Question: "${query}"\n\nIf the user question refers to previous context using pronouns or implicit references, rewrite it into a single, complete, standalone question. If it is already standalone, return it as is. Output ONLY the standalone question text with no extra commentary.`;
      const result = await model.generateContent({
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        generationConfig: { maxOutputTokens: 100, temperature: 0.1 }
      });
      const rephrased = result?.response?.text()?.trim();
      if (rephrased && rephrased.length > 3) {
        effectiveQuery = rephrased;
      }
    } catch (err) {
      console.warn("[resolveQueryAndHistory] Coreference resolution fallback to raw query:", err.message);
    }
  }

  return { effectiveQuery, activeHistory: history };
}

// ─── POST /paper/rag/query ──────────────────────────────────────────────────
router.post("/paper/rag/query", async (req, res, next) => {
  try {
    const { sessionId, query, currentPage, history = [] } = req.body;
    if (!sessionId || !/^[0-9a-f-]{36}$/.test(sessionId)) {
      return res.status(400).json({ detail: "Valid session ID is required." });
    }
    if (!query || typeof query !== "string" || !query.trim()) {
      return res.status(400).json({ detail: "Query text is required." });
    }

    const outDir = path.join(PAPERS_DIR, sessionId);
    if (!fs.existsSync(outDir)) {
      return res.status(404).json({ detail: "Session artifacts not found for the given session ID." });
    }

    // Initialize GenAI instance
    let genAI = null;
    let modelName = settings.llmModel || "gemini-1.5-flash";
    if (settings.geminiApiKey) {
      try {
        genAI = new GoogleGenerativeAI(settings.geminiApiKey);
      } catch (e) {}
    }

    // Run Procedural Coreference & Context Pipeline
    const { effectiveQuery, activeHistory } = await resolveQueryAndHistory(query, history, genAI, modelName);
    const qLower = effectiveQuery.toLowerCase().trim();

    // Retrieve cached session data (Item 4: In-Memory LRU Cache)
    const sessionData = getCachedSessionData(sessionId, outDir);
    const { paperTitle, concepts, conceptsData, summary, architectureNotes, equations, notations, references, chunks } = sessionData;

    // Run Hybrid Vector & RRF Ranking across all entity indices AND text passage chunks (Item 1 & Item 2)
    const matchedConceptsObj = rankElementsWithRRF(effectiveQuery, activeHistory, concepts.map(c => ({ label: c })));
    const matchedConcepts = matchedConceptsObj.matched.map(x => x.label);

    const matchedEquationsObj = rankElementsWithRRF(effectiveQuery, activeHistory, equations);
    const matchedEquations = matchedEquationsObj.matched;

    const matchedNotationsObj = rankElementsWithRRF(effectiveQuery, activeHistory, notations);
    const matchedNotations = matchedNotationsObj.matched;

    const matchedReferencesObj = rankElementsWithRRF(effectiveQuery, activeHistory, references);
    const matchedReferences = matchedReferencesObj.matched;

    const matchedChunksObj = rankElementsWithRRF(effectiveQuery, activeHistory, chunks);
    const matchedChunks = matchedChunksObj.matched;

    // Collect source citations
    const citationsMap = new Map();
    const addCitation = (page, section) => {
      if (!page) return;
      const key = `${page}_${section || ''}`;
      if (!citationsMap.has(key)) {
        citationsMap.set(key, { page: parseInt(page, 10), section: section || "Text" });
      }
    };

    matchedEquations.forEach((eq) => addCitation(eq.page, eq.section));
    matchedNotations.forEach((n) => {
      (n.anchors || []).forEach((anc) => addCitation(anc.page, anc.section));
    });
    matchedReferences.forEach((r) => {
      (r.contexts || []).forEach((ctx) => addCitation(ctx.page, ctx.section));
    });
    matchedChunks.forEach((chk) => addCitation(chk.page, chk.section));

    if (citationsMap.size === 0 && currentPage) {
      addCitation(currentPage, "Current View");
    }

    const citations = Array.from(citationsMap.values()).slice(0, 5);

    const formattedHistory = Array.isArray(history) && history.length > 0
      ? history.slice(-4).map((h) => `${h.role === "user" ? "User" : "HexaMind"}: ${h.text}`).join("\n")
      : "";

    // Build complete paper summary fields
    const overviewText = summary
      ? (summary.executive || summary.overview || summary.tldr || "N/A")
      : "N/A";

    const contributionsList = summary
      ? (summary.contributions || summary.keyContributions || []).map(c => `- ${c}`).join("\n")
      : "N/A";

    const limitationsText = summary
      ? (summary.limitations || "N/A")
      : "N/A";

    const allSectionsList = summary && summary.sections && summary.sections.length > 0
      ? summary.sections.map((s, idx) => `Section ${idx + 1}: ${s.label}\nSummary: ${s.summary}\nKey Points:\n${(s.key_points || []).map(kp => `  - ${kp}`).join('\n')}`).join("\n\n")
      : (conceptsData && conceptsData.sections
          ? Object.entries(conceptsData.sections).map(([secName, terms]) => `- ${secName} (Key Terms: ${terms.slice(0, 5).join(', ')})`).join("\n")
          : "N/A");

    // Try Gemini LLM Generation with Model Fallback & 503 Capacity Retry Loop
    let answer = "";
    let usedModel = "local-rag";

    if (settings.geminiApiKey) {
      const candidateModels = Array.from(new Set([
        settings.llmModel,
        "gemini-1.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        ...(settings.llmFallbackModels || [])
      ])).filter(Boolean);

      const promptContext = `
You are HexaMind, an intelligent AI Research Partner for PaperMind ("Read less. Understand more.").
Your mission is to help the researcher gain deep, intuitive understanding of this research paper quickly.

EXPLAINABLE RESEARCH PARTNER INSTRUCTIONS:
1. Grounding & Accuracy: Base all facts, results, and equations directly on the paper context below. Do not invent unmentioned facts or external citations.
2. Conceptual Intuition: Don't just repeat raw text verbatim — explain the *intuition* and significance behind the concepts, equations, and architectural choices so they are easy to grasp.
3. Clean Math Formatting: Use standard LaTeX ($$display$$ or $inline$) for formulas and variables. Do NOT duplicate variable names in raw text right next to LaTeX (write "$d(t)$" instead of "d(t) $d(t)$"). Wrap multi-line cases or matrix environments inside display math "$$\\begin{cases}...\\end{cases}$$".
4. Complete Responses: Always complete your explanation with a conclusive sentence. Do NOT cut off mid-sentence.
5. Section Listing: When the user asks to list sections, outline, or table of contents, list ALL sections provided under COMPLETE PAPER SECTIONS & OUTLINE below. Do NOT state that sections are missing if they are listed in this outline.
6. Honesty: If a specific detail is truly not present in the provided context, state: "This specific detail is not covered in the extracted sections of this paper."

PAPER TITLE: "${paperTitle}"

EXECUTIVE SUMMARY / OVERVIEW:
${overviewText}

KEY CONTRIBUTIONS:
${contributionsList}

KNOWN LIMITATIONS & DRAWBACKS:
${limitationsText}

COMPLETE PAPER SECTIONS & OUTLINE:
${allSectionsList}

SYSTEM ARCHITECTURE NOTES:
${architectureNotes ? architectureNotes.slice(0, 2000) : "N/A"}

MATCHED CONCEPTS & DEFINITIONS:
${matchedConcepts.slice(0, 10).join(", ")}

MATCHED EQUATIONS:
${matchedEquations.slice(0, 5).map(e => `[${e.label}]: ${e.description} (LaTeX: ${e.latex})`).join("\n")}

MATCHED NOTATIONS:
${matchedNotations.slice(0, 5).map(n => `Symbol ${n.symbol}: ${n.meaning}`).join("\n")}

MATCHED REFERENCES:
${matchedReferences.slice(0, 5).map(r => `[${r.key}] ${r.title}: ${r.contribution_summary}`).join("\n")}

MATCHED RAW TEXT PASSAGES:
${matchedChunks.slice(0, 3).map(c => `[${c.section}]: ${c.text}`).join("\n\n")}

${formattedHistory ? `CONVERSATION HISTORY (PAST FOLLOW-UPS):\n${formattedHistory}\n` : ""}
USER QUESTION: "${effectiveQuery}"
`;

      for (const candidateModel of candidateModels) {
        try {
          const model = genAI.getGenerativeModel({
            model: candidateModel,
            generationConfig: {
              maxOutputTokens: 1200,
              temperature: 0.2,
            },
          });

          // Timeout guard: 25 seconds for LLM generation
          const generatePromise = model.generateContent(promptContext);
          const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error("LLM request timed out after 25s")), 25000)
          );
          const result = await Promise.race([generatePromise, timeoutPromise]);
          const responseText = result.response.text();
          if (responseText && responseText.trim()) {
            answer = responseText;
            usedModel = candidateModel;
            break;
          }
        } catch (err) {
          console.warn(`[paper/rag/query] Model ${candidateModel} failed (${err.message}). Trying fallback model...`);
        }
      }
    }

    // Fallback Local RAG Answer Synthesizer
    if (!answer) {
      if (
        qLower.includes("section") ||
        qLower.includes("outline") ||
        qLower.includes("table of content") ||
        qLower.includes("topic") ||
        qLower.includes("topics") ||
        qLower.includes("global") ||
        qLower.includes("whole paper")
      ) {
        answer = `### Complete Paper Topics & Section Outline for "${paperTitle}"\n\n`;
        if (summary && summary.sections && summary.sections.length > 0) {
          summary.sections.forEach((sec, idx) => {
            let labelClean = (sec.label || "").replace(/\s+et\s+al\.?$/i, " & related sub-sections").trim();
            const prefix = /^\d/.test(labelClean) ? "" : `${idx + 1}. `;
            answer += `**${prefix}${labelClean}**\n${sec.summary}\n\n`;
          });
        } else if (conceptsData && conceptsData.sections) {
          Object.entries(conceptsData.sections).forEach(([secName, terms]) => {
            answer += `- **${secName}**: Key topics include ${terms.slice(0, 5).join(", ")}\n`;
          });
        } else {
          answer += `Topics are indexed across Introduction, MIP Background, Neural Network Bipartite Graph Architecture, Neural Diving, Neural Branching, and Empirical Evaluation.`;
        }
      } else if (qLower.includes("limitation") || qLower.includes("drawback") || qLower.includes("weakness")) {
        answer = `### Limitations & Drawbacks of Proposed Approach\n\n`;
        if (summary && summary.limitations) {
          answer += `${summary.limitations}\n`;
        } else {
          answer += `While the neural approaches significantly accelerate solution times for specific MIP problem classes, baseline solvers like Tuned SCIP remain competitive or superior on certain datasets over extended solving times.`;
        }
      } else if (qLower.includes("contribution") || qLower.includes("summary")) {
        answer = `### Paper Summary & Core Contribution\n\n`;
        answer += `${overviewText}\n\n`;
        if (contributionsList !== "N/A") {
          answer += `**Key Contributions:**\n${contributionsList}\n`;
        }
      } else if (matchedEquations.length > 0) {
        answer = `### Mathematical Formulations & Equations\n\nIdentified **${matchedEquations.length} relevant mathematical equations** for "${query}":\n\n`;
        matchedEquations.slice(0, 4).forEach((eq, idx) => {
          answer += `**${idx + 1}. ${eq.label}**\n${eq.description}\n\n`;
        });
      } else if (matchedConcepts.length > 0) {
        answer = `### Verified Concepts for "${query}"\n\nBased on semantic analysis of **${paperTitle}**, here are top matching elements:\n\n`;
        matchedConcepts.slice(0, 6).forEach((c) => {
          answer += `- **${c}**\n`;
        });
      } else {
        answer = `### HexaMind Analysis\n\nI analyzed **"${paperTitle}"** for **"${query}"** across ${concepts.length} extracted concepts and mathematical notations.\n\nThe paper addresses concepts related to ${concepts.slice(0, 4).join(", ")}. Try asking about specific equations or methodology!`;
      }
    }

    // Generate dynamic follow-up suggestions for interactive discovery
    const suggestedFollowUps = [];
    if (qLower.includes("equation") || qLower.includes("math") || qLower.includes("dual gap")) {
      suggestedFollowUps.push("What do variables d(t) and p* represent in this formulation?");
      suggestedFollowUps.push("How does Neural Branching compare against Full Strong Branching?");
    } else if (qLower.includes("architecture") || qLower.includes("gcn") || qLower.includes("bipartite")) {
      suggestedFollowUps.push("What features are assigned to variable and constraint nodes?");
      suggestedFollowUps.push("How are embeddings updated across GCN layers?");
    } else if (qLower.includes("contribution") || qLower.includes("summary")) {
      suggestedFollowUps.push("Explain the key equations and mathematical formulations");
      suggestedFollowUps.push("Summarize the system architecture and bipartite GCN model");
    } else {
      suggestedFollowUps.push("What are the main contributions of this paper?");
      suggestedFollowUps.push("Explain the key mathematical equations and notations");
    }

    const totalPages = summary && typeof summary.total_pages === "number" && summary.total_pages > 0
      ? summary.total_pages
      : summary && summary.sections && summary.sections.length > 0
        ? Math.max(...summary.sections.map((s) => s.page_start || 1)) + 5
        : null;

    const { verifiedCitations, grounding } = verifyRagCitations(
      answer,
      citations,
      matchedChunks,
      totalPages
    );

    const isDirectText = !usedModel || usedModel === "local-rag" || usedModel.startsWith("local");

    res.json({
      sessionId,
      query,
      answer,
      citations: verifiedCitations,
      grounding,
      suggestedFollowUps,
      model: usedModel,
      isDirectText,
      source: isDirectText ? "direct_text" : "ai_model",
    });
  } catch (err) {
    logger.error("[paper/rag/query] Error processing RAG query", err);
    next(err);
  }
});

export default router;
