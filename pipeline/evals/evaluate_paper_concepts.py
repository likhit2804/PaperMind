"""Evaluate PaperMind's paper-concept extractor on SemEval-2010 Task 5.

This is intentionally a concept-only evaluation. It does not evaluate
equations, references, notations, summaries, or orchestration.
"""

import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
if os.environ.get("PAPERMIND_OFFLINE") == "1":
    os.environ.pop("GEMINI_API_KEY", None)

from pipeline.evaluate_public_benchmarks import (  # noqa: E402
    fetch_semeval2010_batch,
    stem_phrase,
)
from pipeline.research_paper.extract_paper_concepts import (  # noqa: E402
    calculate_pos_yake_concepts,
    extract_global_doc_concepts,
    filter_terms_via_ai,
)

TOP_K = 15


def evaluate_official_style(sample):
    """Use SemEval-style exact matching over the top 15 predictions."""
    sections = [{"label": "Full Paper", "raw_text": sample["full_text"]}]
    local = calculate_pos_yake_concepts(sections, canonical_seeds=set(), max_candidates=15)
    global_terms = extract_global_doc_concepts(
        sections, title=sample["title"], canonical_seeds=set(), max_candidates=75
    )
    candidate_terms = list(dict.fromkeys(global_terms + local.get("Full Paper", [])))
    verified = filter_terms_via_ai(candidate_terms, sample["title"], set())
    all_filtered_terms = list(verified)
    predictions = all_filtered_terms[:TOP_K]
    gold = {stem_phrase(term) for term in sample["gold_keyphrases"]}
    candidate_stems = {stem_phrase(term) for term in candidate_terms}
    predicted = [stem_phrase(term) for term in predictions]
    true_positives = sum(1 for term in predicted if term in gold)
    matched = [term for term in predictions if stem_phrase(term) in gold]
    missed_gold = [
        term for term in sample["gold_keyphrases"] if stem_phrase(term) not in set(predicted)
    ]
    false_positives = [term for term in predictions if stem_phrase(term) not in gold]
    return {
        "sample_id": sample["id"],
        "top_k": TOP_K,
        "candidate_count": len(candidate_terms),
        "candidate_gold_recall": round(
            100 * sum(1 for term in gold if term in candidate_stems) / max(1, len(gold)), 2
        ),
        "predicted_count": len(predictions),
        "all_filtered_count": len(all_filtered_terms),
        "gold_count": len(gold),
        "true_positives": true_positives,
        "all_filtered_terms": all_filtered_terms,
        "official_top15_terms": predictions,
        "predictions": predictions,
        "matched_predictions": matched,
        "false_positive_predictions": false_positives,
        "missed_gold_keyphrases": missed_gold,
    }


def main() -> int:
    if os.environ.get("PAPERMIND_OFFLINE") == "1":
        os.environ.pop("GEMINI_API_KEY", None)
    # Use the locally available, reproducible subset for this run.
    samples = fetch_semeval2010_batch(["C-1", "C-3", "C-4", "C-6"])
    if not samples:
        print("No SemEval-2010 samples available.")
        return 1

    results = [evaluate_official_style(sample) for sample in samples]
    total_true_positives = sum(item["true_positives"] for item in results)
    total_predictions = sum(item["predicted_count"] for item in results)
    total_gold = sum(item["gold_count"] for item in results)
    precision = total_true_positives / max(1, total_predictions)
    recall = total_true_positives / max(1, total_gold)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    false_positive_counts = Counter(
        term.lower() for item in results for term in item["false_positive_predictions"]
    )
    missed_counts = Counter(
        term.lower() for item in results for term in item["missed_gold_keyphrases"]
    )
    metrics = {
        "evaluated_papers": len(results),
        "top_k": TOP_K,
        "micro_precision": round(precision * 100, 2),
        "micro_recall": round(recall * 100, 2),
        "micro_f1": round(f1 * 100, 2),
    }

    output = {
        "evaluation": "paper_concepts_only_semeval_official_style",
        "dataset": "SemEval-2010 Task 5",
        "sample_ids": [item["sample_id"] for item in results],
        "metrics": metrics,
        "diagnostics": {
            "average_candidate_count": round(
                sum(item["candidate_count"] for item in results) / len(results), 2
            ),
            "average_candidate_gold_recall": round(
                sum(item["candidate_gold_recall"] for item in results) / len(results), 2
            ),
            "common_false_positives": false_positive_counts.most_common(20),
            "common_missed_gold_keyphrases": missed_counts.most_common(20),
        },
        "per_paper": results,
    }
    output_path = os.path.join(
        ROOT, "docs", "benchmarks", "semeval2010", "results", "paper_concepts_eval.json"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)

    print(json.dumps(metrics, indent=2))
    print(f"Results saved to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
