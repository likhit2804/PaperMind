/**
 * Lightweight in-memory vector similarity service.
 * 
 * In production companies use Pinecone, Weaviate, or pgvector.
 * Here we use the Gemini Embedding API + cosine similarity
 * to keep it self-contained.
 */

import { GoogleGenerativeAI } from "@google/generative-ai";
import settings from "../config.js";

const embeddingCache = new Map();   // misconception_id → float[]

function cosineSimilarity(a, b) {
  let dot = 0, normA = 0, normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

async function getEmbedding(text) {
  if (!settings.geminiApiKey) return null;
  try {
    const genAI = new GoogleGenerativeAI(settings.geminiApiKey);
    const model = genAI.getGenerativeModel({ model: "text-embedding-004" });
    const result = await model.embedContent(text);
    return result.embedding.values;
  } catch (error) {
    console.error("Error generating vector embedding:", error.message || error);
    return null;
  }
}

/**
 * Pre-compute embeddings for all misconceptions in a topic pack.
 * Call once per topic on server start or after ingestion.
 */
export async function indexMisconceptions(misconceptions = []) {
  let indexedCount = 0;
  for (const m of misconceptions) {
    const id = m.misconception_id || m.id;
    if (!id || embeddingCache.has(id)) continue;

    const text = `${m.label || ""}. ${m.description || ""}. Symptoms: ${(m.symptoms || []).join(", ")}`;
    const embedding = await getEmbedding(text);
    if (embedding) {
      embeddingCache.set(id, { embedding, misconception: m });
      indexedCount++;
    }
  }
  return { indexed: embeddingCache.size, newlyIndexed: indexedCount };
}

/**
 * Find the top-K most similar misconceptions to a free-text query.
 */
export async function findSimilarMisconceptions(queryText, topK = 3) {
  if (embeddingCache.size === 0 || !queryText) return [];

  const queryEmbedding = await getEmbedding(queryText);
  if (!queryEmbedding) return [];

  const scored = [];
  for (const [id, { embedding, misconception }] of embeddingCache.entries()) {
    const similarity = cosineSimilarity(queryEmbedding, embedding);
    scored.push({ misconception_id: id, label: misconception.label, similarity });
  }

  scored.sort((a, b) => b.similarity - a.similarity);
  return scored.slice(0, topK);
}
