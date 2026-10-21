/**
 * backend-node/src/ragCitationVerifier.js
 * 
 * Production RAG citation verification and hallucination defense.
 * Verifies that page numbers and section citations returned by LLM answers
 * or retrieved elements are grounded in actual extracted paper chunks.
 */

/**
 * Extracts and verifies RAG citations against actual retrieved chunks and document boundaries.
 * Detects and flags phantom/hallucinated page references in synthesized answers.
 *
 * @param {string} answer - The synthesized answer from Gemini or fallback RAG.
 * @param {Array<{page: number, section: string}>} candidateCitations - Candidate citations collected from entities/chunks.
 * @param {Array<{page: number, section?: string, text?: string}>} retrievedChunks - Chunks actually retrieved by RRF.
 * @param {number|null} [totalPages=null] - Total pages in the paper if known.
 * @returns {{
 *   verifiedCitations: Array<{page: number, section: string}>,
 *   grounding: {
 *     isFullyGrounded: boolean,
 *     hallucinatedPages: number[],
 *     totalMentionedPages: number,
 *     groundingScore: number
 *   }
 * }}
 */
export function verifyRagCitations(answer = "", candidateCitations = [], retrievedChunks = [], totalPages = null) {
  const validRetrievedPages = new Set();

  if (Array.isArray(retrievedChunks)) {
    retrievedChunks.forEach((c) => {
      const pageNum = typeof c.page === "number" ? c.page : parseInt(c.page, 10);
      if (!isNaN(pageNum) && pageNum > 0) {
        validRetrievedPages.add(pageNum);
      }
    });
  }

  if (Array.isArray(candidateCitations)) {
    candidateCitations.forEach((cit) => {
      const pageNum = typeof cit.page === "number" ? cit.page : parseInt(cit.page, 10);
      if (!isNaN(pageNum) && pageNum > 0) {
        validRetrievedPages.add(pageNum);
      }
    });
  }

  // Extract explicit page references in synthesized answer text: e.g. "Page 4", "page 12", "p. 5"
  const textPageRegex = /\b(?:page|p\.)\s*(\d+)\b/gi;
  const mentionedPages = [];
  let match;
  while ((match = textPageRegex.exec(answer || "")) !== null) {
    const pageVal = parseInt(match[1], 10);
    if (!isNaN(pageVal)) {
      mentionedPages.push(pageVal);
    }
  }

  const hallucinatedInText = mentionedPages.filter((p) => {
    if (totalPages && p > totalPages) return true;
    return !validRetrievedPages.has(p);
  });

  const uniqueHallucinated = Array.from(new Set(hallucinatedInText));
  const uniqueMentioned = Array.from(new Set(mentionedPages));

  // Filter candidate citations to ensure validity
  const verifiedCitations = (candidateCitations || []).filter((cit) => {
    const pageNum = typeof cit.page === "number" ? cit.page : parseInt(cit.page, 10);
    if (isNaN(pageNum) || pageNum < 1) return false;
    if (totalPages && pageNum > totalPages) return false;
    return true;
  });

  const groundedMentionedCount = uniqueMentioned.length - uniqueHallucinated.length;
  const groundingScore = uniqueMentioned.length === 0
    ? 1.0
    : Math.max(0, Math.min(1.0, groundedMentionedCount / uniqueMentioned.length));

  return {
    verifiedCitations,
    grounding: {
      isFullyGrounded: uniqueHallucinated.length === 0,
      hallucinatedPages: uniqueHallucinated,
      totalMentionedPages: uniqueMentioned.length,
      groundingScore: Number(groundingScore.toFixed(3)),
    },
  };
}

export default verifyRagCitations;
