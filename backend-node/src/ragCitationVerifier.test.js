/**
 * backend-node/src/ragCitationVerifier.test.js
 * 
 * Unit tests for verifyRagCitations function to safeguard against phantom
 * citations and ensure robust hallucination defense.
 */
import { verifyRagCitations } from "./ragCitationVerifier.js";
import assert from "assert";

function runTests() {
  console.log("Running RAG Citation Verifier Unit Tests...\n");

  // Test 1: Grounded answer with matching chunk citations
  {
    const answer = "The bipartite graph architecture is defined on Page 3 with detailed features.";
    const candidateCitations = [{ page: 3, section: "Section 2.1" }];
    const retrievedChunks = [{ page: 3, section: "Section 2.1", text: "bipartite graph features" }];
    
    const result = verifyRagCitations(answer, candidateCitations, retrievedChunks, 10);
    assert.strictEqual(result.grounding.isFullyGrounded, true, "Should be fully grounded");
    assert.strictEqual(result.grounding.hallucinatedPages.length, 0, "No hallucinated pages");
    assert.strictEqual(result.verifiedCitations.length, 1, "Candidate citation preserved");
    assert.strictEqual(result.grounding.groundingScore, 1.0, "Score should be 1.0");
    console.log("✓ Test 1 Passed: Grounded answer with matching citations");
  }

  // Test 2: Hallucinated page mentioned in answer text
  {
    const answer = "According to Page 42, the neural diving threshold is set to 0.05.";
    const candidateCitations = [{ page: 3, section: "Methodology" }];
    const retrievedChunks = [{ page: 3, section: "Methodology", text: "diving" }];
    
    const result = verifyRagCitations(answer, candidateCitations, retrievedChunks, 10);
    assert.strictEqual(result.grounding.isFullyGrounded, false, "Should detect hallucination");
    assert.deepStrictEqual(result.grounding.hallucinatedPages, [42], "Page 42 must be flagged");
    assert.strictEqual(result.grounding.groundingScore, 0.0, "Score should be 0.0 for completely ungrounded page");
    console.log("✓ Test 2 Passed: Flags ungrounded page 42 when paper is 10 pages");
  }

  // Test 3: Candidate citations exceeding document total pages are filtered out
  {
    const answer = "Neural branching selects branching variables efficiently.";
    const candidateCitations = [
      { page: 2, section: "Background" },
      { page: 99, section: "Phantom Section" },
      { page: -1, section: "Invalid Page" }
    ];
    const retrievedChunks = [{ page: 2, section: "Background" }];
    
    const result = verifyRagCitations(answer, candidateCitations, retrievedChunks, 12);
    assert.strictEqual(result.verifiedCitations.length, 1, "Only page 2 should pass");
    assert.strictEqual(result.verifiedCitations[0].page, 2, "Verified citation page must be 2");
    console.log("✓ Test 3 Passed: Filters candidate citations out of document bounds");
  }

  // Test 4: Answer with no page citations has full score
  {
    const answer = "The transformer model relies on self-attention mechanisms without recurrence.";
    const candidateCitations = [{ page: 1, section: "Abstract" }];
    const retrievedChunks = [{ page: 1, section: "Abstract" }];

    const result = verifyRagCitations(answer, candidateCitations, retrievedChunks, 8);
    assert.strictEqual(result.grounding.isFullyGrounded, true);
    assert.strictEqual(result.grounding.groundingScore, 1.0);
    assert.strictEqual(result.grounding.totalMentionedPages, 0);
    console.log("✓ Test 4 Passed: Clean answer with no explicit page mentions scores 1.0");
  }

  console.log("\nAll RAG Citation Verifier tests passed successfully!\n");
}

runTests();
