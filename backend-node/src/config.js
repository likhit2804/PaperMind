import { config } from "dotenv";
import path from "path";
import { fileURLToPath } from "url";
import { z } from "zod";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Project root is two levels up from backend-node/src/
const baseDir = path.resolve(__dirname, "..", "..");

// Load .env from project root
config({ path: path.join(baseDir, ".env") });

// ─── Zod Schema for 12-Factor Boot Validation ───────────────────────────────
const envSchema = z.object({
  PORT: z.coerce.number().int().positive().default(8000),
  GEMINI_API_KEY: z.string().optional().nullable(),
  OPENAI_API_KEY: z.string().optional().nullable(),
  LLM_MODEL: z.string().default("gemini-1.5-flash"),
  AGENT_MODEL: z.string().optional(),
  LLM_FALLBACK_MODELS: z
    .string()
    .default("gemini-1.5-flash,gemini-2.5-flash-lite,gemini-2.0-flash,gemini-1.5-pro"),
  LLM_503_RETRIES: z.coerce.number().int().min(0).max(10).default(1),
  LLM_RETRY_BASE_MS: z.coerce.number().int().min(100).max(30000).default(1500),
  LLM_MAX_CONCURRENCY: z.coerce.number().int().min(1).max(20).default(4),
  LLM_CACHE_TTL_SECONDS: z.coerce.number().int().min(0).default(900),
  NEO4J_URI: z.string().optional().nullable(),
  NEO4J_USER: z.string().optional().nullable(),
  NEO4J_PASSWORD: z.string().optional().nullable(),
  NEO4J_DATABASE: z.string().default("neo4j"),
  MONGO_URI: z.string().optional().nullable(),
  MONGO_DB_NAME: z.string().default("papermind"),
});

const parseResult = envSchema.safeParse(process.env);
if (!parseResult.success) {
  console.error("❌ Fatal Configuration Error in backend-node:");
  for (const issue of parseResult.error.issues) {
    console.error(`   - ${issue.path.join(".")}: ${issue.message}`);
  }
  process.exit(1);
}

const env = parseResult.data;

const settings = {
  appName: "PaperMind",
  port: env.PORT,
  baseDir,
  knowledgeBaseDir: path.join(baseDir, "knowledge_base"),
  dbPath: path.join(baseDir, "db", "papermind.db"),
  schemaPath: path.join(baseDir, "db", "schema.sql"),

  // LLM Settings
  geminiApiKey: env.GEMINI_API_KEY || null,
  openaiApiKey: env.OPENAI_API_KEY || null,
  llmModel: env.LLM_MODEL,
  agentModel: env.AGENT_MODEL || env.LLM_MODEL,
  llmFallbackModels: env.LLM_FALLBACK_MODELS.split(",")
    .map((item) => item.trim())
    .filter(Boolean),
  llm503Retries: env.LLM_503_RETRIES,
  llmRetryBaseMs: env.LLM_RETRY_BASE_MS,
  llmMaxConcurrency: env.LLM_MAX_CONCURRENCY,
  llmCacheTtlSeconds: env.LLM_CACHE_TTL_SECONDS,

  // Graph + User Stores
  neo4jUri: env.NEO4J_URI || null,
  neo4jUser: env.NEO4J_USER || null,
  neo4jPassword: env.NEO4J_PASSWORD || null,
  neo4jDatabase: env.NEO4J_DATABASE,
  mongoUri: env.MONGO_URI || null,
  mongoDbName: env.MONGO_DB_NAME,
};

export default settings;
