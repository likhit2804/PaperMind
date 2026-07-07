import { getWeakConcepts } from "./mongoService.js";
import { fetchQuestionContextForConcepts, fetchPrerequisiteBottlenecks } from "./neo4jService.js";
import { getStudent } from "./database.js";
import { KnowledgeBase } from "./knowledgeBase.js";

export async function buildQuestionGenerationContext(studentId, fallbackConcepts = [], subject = null) {
  const weakConcepts = await getWeakConcepts(studentId, 5);
  const conceptIds =
    weakConcepts.length > 0 ? weakConcepts : (Array.isArray(fallbackConcepts) ? fallbackConcepts : []);

  let graphContext = [];
  let bottlenecks = [];
  try {
    graphContext = await fetchQuestionContextForConcepts(conceptIds, 20);
    bottlenecks = await fetchPrerequisiteBottlenecks(conceptIds);
  } catch (_error) {
    // Degrade gracefully when Neo4j is temporarily unavailable.
    graphContext = [];
    bottlenecks = [];
  }

  // Fallback to local KnowledgeBase prerequisite bottleneck detection if Neo4j is disabled/returned no bottlenecks
  if (bottlenecks.length === 0) {
    try {
      const resolvedSubject = subject || getStudent(studentId)?.subject;
      if (resolvedSubject) {
        const kb = new KnowledgeBase(resolvedSubject);
        const concepts = kb.concepts?.concepts || [];
        
        // Recursive helper to find all prerequisites (multi-level deep)
        const getPrereqsRecursive = (cid, visited = new Set()) => {
          if (visited.has(cid)) return new Set();
          visited.add(cid);
          
          const concept = concepts.find(c => c.id === cid);
          const directPrereqs = concept?.prerequisites || [];
          const allPrereqs = new Set(directPrereqs);
          
          for (const p of directPrereqs) {
            const nested = getPrereqsRecursive(p, visited);
            for (const np of nested) {
              allPrereqs.add(np);
            }
          }
          return allPrereqs;
        };

        // If both a prerequisite concept and the dependent concept are weak, it's a bottleneck
        for (const blocked of conceptIds) {
          const allPrereqsForBlocked = getPrereqsRecursive(blocked);
          for (const bottleneck of conceptIds) {
            if (bottleneck !== blocked && allPrereqsForBlocked.has(bottleneck)) {
              bottlenecks.push({
                bottleneck,
                blocked,
              });
            }
          }
        }
      }
    } catch (localErr) {
      console.warn("Failed to compute local prerequisite bottlenecks:", localErr.message || localErr);
    }
  }

  return {
    target_concepts: conceptIds,
    graph_context: graphContext,
    prerequisite_bottlenecks: bottlenecks,
  };
}
