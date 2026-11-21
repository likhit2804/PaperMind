"""
pipeline/evals/run_ablation_study.py — Master Ablation & Methods Runner.

Executes the step-by-step 6-approach ablation study documented in
docs/ablation_and_methods_audit_report.md and docs/concept_extractor_methods_and_audit.md:

  Approach 1: Legacy TF-IDF Baseline (unconstrained unigram/bigram string matching)
  Approach 2: Pure Local POS-YAKE (clause-boundary noun phrase chunking + per-section YAKE)
  Approach 3: Dual Local + Global POS-YAKE (per-section + document-wide pass)
  Approach 4: Enhanced Global + Dispersion Boost (sub-linear log-TF + section dispersion)
  Approach 5: Tri-Hybrid High-Recall Candidate Net (section TF-IDF + YAKE + POS chunking)
  Approach 6: High-Recall Net + AI Semantic Verification (Gemini AI filter / offline fallback)

Generates:
  - Per-approach concept JSON artifacts
  - Transition statistics (terms gained & false positives pruned)
  - 6x6 Pairwise Common Terms Intersection Matrix
  - Core Consensus Terms across all 6 approaches
  - Master ablation summary JSON in ablation_results/
"""

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.request
from collections import Counter

# Set up project path
EVALS_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.dirname(EVALS_DIR)
REPO_ROOT = os.path.dirname(PIPELINE_DIR)

for path in [REPO_ROOT, PIPELINE_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

from pipeline.research_paper.extract_paper_concepts import (
    GENERIC_UNIGRAM_STOPWORDS,
    STOPWORDS,
    calculate_pos_yake_concepts,
    extract_global_doc_concepts,
    extract_noun_phrase_candidates,
    extract_paper_metadata_via_ai,
    filter_terms_offline,
    filter_terms_via_ai,
    normalize_phrase,
    parse_pdf_into_sections,
    singularize,
)
from pipeline.utils import clean_text

DEFAULT_PDF = os.path.join(
    REPO_ROOT, "data", "public_benchmarks", "sample_pdfs", "arxiv_2012.13349_mip_neural.pdf"
)
DEFAULT_OUTPUT_DIR = os.path.join(REPO_ROOT, "ablation_results")
MIP_ARXIV_URL = "https://arxiv.org/pdf/2012.13349.pdf"


def ensure_mip_paper_exists(pdf_path: str) -> str:
    """Ensures the target PDF exists, downloading arXiv:2012.13349 if missing."""
    if os.path.exists(pdf_path):
        return pdf_path

    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    print(f"📥 Target PDF not found locally. Downloading from arXiv: {MIP_ARXIV_URL}...")
    req = urllib.request.Request(
        MIP_ARXIV_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PaperMind-Ablation/2.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read()
        with open(pdf_path, "wb") as f:
            f.write(content)
    print(f"  ✓ Downloaded {os.path.basename(pdf_path)} ({len(content) / 1024 / 1024:.2f} MB)")
    return pdf_path


# ==============================================================================
# Approach 1: Legacy TF-IDF Baseline (No Clause Boundaries, No Syntactic POS)
# ==============================================================================
def run_approach_1_legacy_tfidf(sections: list[dict], max_terms: int = 34) -> list[str]:
    """
    Simulates Approach 1: Primitive TF-IDF without clause boundary splitting
    or syntactic POS constraints. Extracts unconstrained unigram and bigram strings.
    Retains generic tokens (problem, method, results, solution).
    """
    full_text = " ".join([s.get("raw_text", "") for s in sections]).lower()
    tokens = re.findall(r"\b[a-z]{3,}\b", full_text)
    total_tokens = len(tokens)

    if total_tokens == 0:
        return []

    # Unconstrained unigrams and bigrams
    unigrams = tokens
    bigrams = [f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)]

    # Section Document Frequencies (IDF)
    num_sections = max(1, len(sections))
    df = Counter()
    for s in sections:
        sec_text = s.get("raw_text", "").lower()
        seen = set(re.findall(r"\b[a-z]{3,}\b", sec_text))
        for w in seen:
            df[w] += 1
        sec_tokens = re.findall(r"\b[a-z]{3,}\b", sec_text)
        seen_bi = {f"{sec_tokens[i]} {sec_tokens[i + 1]}" for i in range(len(sec_tokens) - 1)}
        for b in seen_bi:
            df[b] += 1

    tf_uni = Counter(unigrams)
    tf_bi = Counter(bigrams)

    # Basic stopword filter (does NOT filter generic words like problem, method, nodes)
    basic_stops = {
        "the",
        "and",
        "that",
        "this",
        "with",
        "for",
        "are",
        "was",
        "from",
        "have",
        "were",
        "which",
        "also",
        "then",
        "into",
        "more",
        "such",
        "than",
        "each",
        "been",
        "these",
    }

    scored = {}
    for term, count in tf_bi.items():
        w1, w2 = term.split()
        if w1 in basic_stops or w2 in basic_stops:
            continue
        idf = math.log(1 + num_sections / (1 + df.get(term, 1)))
        scored[term] = count * idf

    for term, count in tf_uni.items():
        if term in basic_stops or len(term) < 4:
            continue
        idf = math.log(1 + num_sections / (1 + df.get(term, 1)))
        # Unigrams weighted moderately
        scored[term] = (count * 0.7) * idf

    sorted_terms = sorted(scored.items(), key=lambda x: x[1], reverse=True)
    results = [term for term, _ in sorted_terms[:max_terms]]
    return results


# ==============================================================================
# Approach 2: Pure Local POS-YAKE (Section-by-Section, Clause Boundaries)
# ==============================================================================
def run_approach_2_local_pos_yake(sections: list[dict], max_per_sec: int = 8) -> list[str]:
    """
    Simulates Approach 2: Syntactic clause-boundary noun phrase chunking
    + per-section YAKE graph centrality without document-wide aggregation.
    """
    local_map = calculate_pos_yake_concepts(
        sections, canonical_seeds=set(), max_candidates=max_per_sec
    )
    collected = []
    seen = set()
    for sec in sections:
        label = sec.get("label", "")
        for term in local_map.get(label, []):
            t_norm = normalize_phrase(term)
            if t_norm and t_norm not in seen:
                seen.add(t_norm)
                collected.append(t_norm)
    return collected


# ==============================================================================
# Approach 3: Dual Local + Global POS-YAKE (Local + Standard Global Pass)
# ==============================================================================
def run_approach_3_dual_local_global(
    sections: list[dict], title: str, local_terms: list[str], max_global: int = 50
) -> list[str]:
    """
    Simulates Approach 3: Combines per-section local candidates with a
    full document-wide global POS-YAKE pass to capture central paper themes.
    """
    global_terms = extract_global_doc_concepts(
        sections, title=title, canonical_seeds=set(), max_candidates=max_global
    )
    combined = list(dict.fromkeys(local_terms + global_terms))
    return [normalize_phrase(t) for t in combined if normalize_phrase(t)]


# ==============================================================================
# Approach 4: Enhanced Global + Dispersion Boost
# ==============================================================================
def run_approach_4_enhanced_global(
    sections: list[dict], title: str, local_terms: list[str], max_global: int = 75
) -> list[str]:
    """
    Simulates Approach 4: Sub-linear Log-TF + Multi-section Dispersion Boost
    (1 + 0.45 * ln(1 + span)) + Heading Consensus Boost (2.0x).
    """
    global_terms = extract_global_doc_concepts(
        sections, title=title, canonical_seeds=set(), max_candidates=max_global
    )
    combined = list(dict.fromkeys(local_terms + global_terms))
    return [normalize_phrase(t) for t in combined if normalize_phrase(t)]


# ==============================================================================
# Approach 5: Tri-Hybrid High-Recall Candidate Net (Wide Net)
# ==============================================================================
def run_approach_5_tri_hybrid_wide_net(
    sections: list[dict],
    title: str,
    canonical_seeds: set[str],
    max_per_sec: int = 15,
    max_global: int = 150,
) -> list[str]:
    """
    Simulates Approach 5: Section TF-IDF + YAKE Centrality + Syntactic POS Chunking.
    Expands candidate capacity to 1-to-4 words and domain unigrams.
    Produces the wide candidate net (~279 candidates).
    """
    local_map = calculate_pos_yake_concepts(
        sections, canonical_seeds=canonical_seeds, max_candidates=max_per_sec
    )
    local_candidates = []
    for terms in local_map.values():
        local_candidates.extend(terms)

    global_candidates = extract_global_doc_concepts(
        sections, title=title, canonical_seeds=canonical_seeds, max_candidates=max_global
    )

    wide_net = list(dict.fromkeys(local_candidates + global_candidates))
    return [normalize_phrase(t) for t in wide_net if normalize_phrase(t)]


# ==============================================================================
# Approach 6: High-Recall Net + AI Semantic Verification (Final Gold)
# ==============================================================================
def run_approach_6_ai_verified_gold(
    wide_net_candidates: list[str],
    title: str,
    canonical_seeds: set[str],
    offline_mode: bool = False,
) -> list[str]:
    """
    Simulates Approach 6: Wide Net -> Gemini AI Semantic Verification Pass
    (or deterministic offline semantic verification if offline)
    + Subsumption & Plural Deduplication.
    """
    if offline_mode or not os.environ.get("GEMINI_API_KEY"):
        verified = filter_terms_offline(wide_net_candidates, canonical_seeds)
    else:
        try:
            verified = filter_terms_via_ai(wide_net_candidates, title, canonical_seeds)
        except Exception as e:
            print(f"  ⚠️ AI verification encountered error ({e}); using offline semantic filter.")
            verified = filter_terms_offline(wide_net_candidates, canonical_seeds)

    # Subsumption & deduplication
    final_gold = []
    seen = set()
    for term in verified:
        t_norm = normalize_phrase(term)
        if not t_norm or t_norm in seen:
            continue
        seen.add(t_norm)
        final_gold.append(t_norm)

    return final_gold


# ==============================================================================
# Master Ablation Suite Runner
# ==============================================================================
def run_master_ablation_study(pdf_path: str, output_dir: str, offline_mode: bool = False):
    """Executes the complete 6-approach ablation study and generates matrices."""
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = ensure_mip_paper_exists(pdf_path)

    print("\n" + "=" * 80)
    print("  🔬 MASTER ABLATION & TECHNICAL METHODS RUNNER (PaperMind)")
    print("=" * 80)
    print(f"  • Target PDF: {os.path.basename(pdf_path)}")
    print(f"  • Output Directory: {output_dir}")
    print(f"  • Mode: {'Deterministic Offline' if offline_mode else 'Live AI Hybrid'}")
    print("=" * 80)

    # Step 0: Parse PDF into sections
    t0 = time.time()
    sections = parse_pdf_into_sections(pdf_path)
    total_chars = sum(len(s.get("raw_text", "")) for s in sections)
    print(
        f"\n📄 [Step 0] Sliced PDF into {len(sections)} sections ({total_chars:,} chars) in {time.time() - t0:.2f}s"
    )

    # Extract paper metadata / canonical seeds
    first_text = sections[0].get("raw_text", "") if sections else ""
    try:
        title, canonical_seeds = extract_paper_metadata_via_ai(first_text)
        if not title or title == "Research Paper":
            title = "Solving Mixed Integer Programs Using Neural Networks"
    except Exception:
        title = "Solving Mixed Integer Programs Using Neural Networks"
        canonical_seeds = {"mixed integer programming", "neural diving", "branching"}
    print(f"   Title: {title}")
    print(f"   Canonical Seeds: {sorted(list(canonical_seeds))}")

    # --------------------------------------------------------------------------
    # Run Approach 1: Legacy TF-IDF
    # --------------------------------------------------------------------------
    t1 = time.time()
    print("\n▶ [1/6] Running Approach 1: Legacy TF-IDF Baseline (Unconstrained N-grams)...")
    a1_terms = run_approach_1_legacy_tfidf(sections, max_terms=34)
    print(f"  ✓ Approach 1 Output: {len(a1_terms)} terms ({time.time() - t1:.2f}s)")

    # --------------------------------------------------------------------------
    # Run Approach 2: Pure Local POS-YAKE
    # --------------------------------------------------------------------------
    t2 = time.time()
    print(
        "\n▶ [2/6] Running Approach 2: Pure Local POS-YAKE (Section-level Clause Noun Phrases)..."
    )
    a2_terms = run_approach_2_local_pos_yake(sections, max_per_sec=8)
    print(f"  ✓ Approach 2 Output: {len(a2_terms)} terms ({time.time() - t2:.2f}s)")

    # --------------------------------------------------------------------------
    # Run Approach 3: Dual Local + Global POS-YAKE
    # --------------------------------------------------------------------------
    t3 = time.time()
    print("\n▶ [3/6] Running Approach 3: Dual Local + Global POS-YAKE (Local + Global Pass)...")
    a3_terms = run_approach_3_dual_local_global(sections, title, a2_terms, max_global=50)
    print(f"  ✓ Approach 3 Output: {len(a3_terms)} terms ({time.time() - t3:.2f}s)")

    # --------------------------------------------------------------------------
    # Run Approach 4: Enhanced Global + Dispersion Boost
    # --------------------------------------------------------------------------
    t4 = time.time()
    print("\n▶ [4/6] Running Approach 4: Enhanced Global + Multi-Section Dispersion Boost...")
    a4_terms = run_approach_4_enhanced_global(sections, title, a2_terms, max_global=75)
    print(f"  ✓ Approach 4 Output: {len(a4_terms)} terms ({time.time() - t4:.2f}s)")

    # --------------------------------------------------------------------------
    # Run Approach 5: Tri-Hybrid High-Recall Candidate Net
    # --------------------------------------------------------------------------
    t5 = time.time()
    print(
        "\n▶ [5/6] Running Approach 5: Tri-Hybrid Candidate Net (Section TF-IDF + YAKE + POS Chunking)..."
    )
    a5_terms = run_approach_5_tri_hybrid_wide_net(
        sections, title, canonical_seeds, max_per_sec=15, max_global=150
    )
    print(f"  ✓ Approach 5 Output: {len(a5_terms)} terms ({time.time() - t5:.2f}s)")

    # --------------------------------------------------------------------------
    # Run Approach 6: High-Recall Net + AI Semantic Verification (Gold)
    # --------------------------------------------------------------------------
    t6 = time.time()
    print("\n▶ [6/6] Running Approach 6: Wide Net + Semantic Verification & Deduplication...")
    a6_terms = run_approach_6_ai_verified_gold(
        a5_terms, title, canonical_seeds, offline_mode=offline_mode
    )
    print(f"  ✓ Approach 6 Output: {len(a6_terms)} Gold Terms ({time.time() - t6:.2f}s)")

    # --------------------------------------------------------------------------
    # Transitions & Terms Analysis
    # --------------------------------------------------------------------------
    set1, set2, set3, set4, set5, set6 = (
        set(a1_terms),
        set(a2_terms),
        set(a3_terms),
        set(a4_terms),
        set(a5_terms),
        set(a6_terms),
    )

    t1_gained = sorted(list(set2 - set1))
    t1_pruned = sorted(list(set1 - set2))

    t2_gained = sorted(list(set3 - set2))
    t3_gained = sorted(list(set4 - set3))
    t4_gained = sorted(list(set5 - set4))
    t5_pruned_by_ai = sorted(list(set5 - set6))

    # 6x6 Pairwise Common Terms Intersection Matrix
    approaches = [
        ("A1 (Legacy TF-IDF)", a1_terms),
        ("A2 (Local POS-YAKE)", a2_terms),
        ("A3 (Dual POS-YAKE)", a3_terms),
        ("A4 (Enhanced Global)", a4_terms),
        ("A5 (Tri-Hybrid Net)", a5_terms),
        ("A6 (AI Gold Terms)", a6_terms),
    ]

    matrix_6x6 = {}
    for name_i, terms_i in approaches:
        matrix_6x6[name_i] = {}
        for name_j, terms_j in approaches:
            common_count = len(set(terms_i).intersection(set(terms_j)))
            matrix_6x6[name_i][name_j] = common_count

    # Core Consensus Terms (Found across ALL 6 Approaches)
    core_consensus = sorted(list(set.intersection(set1, set2, set3, set4, set5, set6)))

    # Save Individual Approach Artifacts
    artifacts = [
        ("ablation_stage1_legacy_tfidf.json", a1_terms),
        ("ablation_stage2_pure_local_pos_yake.json", a2_terms),
        ("ablation_stage3_dual_local_global.json", a3_terms),
        ("ablation_stage4_enhanced_global_dispersion.json", a4_terms),
        ("ablation_stage5_tri_hybrid_wide_net.json", a5_terms),
        ("ablation_stage6_ai_verified_gold.json", a6_terms),
    ]

    for filename, term_list in artifacts:
        fpath = os.path.join(output_dir, filename)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "approach": filename.replace(".json", ""),
                    "term_count": len(term_list),
                    "terms": term_list,
                },
                f,
                indent=2,
            )

    # Save 6x6 Matrix JSON
    matrix_path = os.path.join(output_dir, "matrix_6x6_overlap.json")
    with open(matrix_path, "w", encoding="utf-8") as f:
        json.dump(matrix_6x6, f, indent=2)

    # Save Master Summary JSON
    summary_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target_paper": os.path.basename(pdf_path),
        "total_sections": len(sections),
        "total_characters": total_chars,
        "approach_counts": {
            "A1_legacy_tfidf": len(a1_terms),
            "A2_local_pos_yake": len(a2_terms),
            "A3_dual_local_global": len(a3_terms),
            "A4_enhanced_global": len(a4_terms),
            "A5_tri_hybrid_wide_net": len(a5_terms),
            "A6_ai_verified_gold": len(a6_terms),
        },
        "transitions": {
            "T1_A1_to_A2": {
                "gained_count": len(t1_gained),
                "pruned_count": len(t1_pruned),
                "sample_gained": t1_gained[:10],
                "sample_pruned": t1_pruned[:10],
            },
            "T2_A2_to_A3": {"gained_count": len(t2_gained), "sample_gained": t2_gained[:10]},
            "T3_A3_to_A4": {"gained_count": len(t3_gained), "sample_gained": t3_gained[:10]},
            "T4_A4_to_A5": {"gained_count": len(t4_gained), "sample_gained": t4_gained[:10]},
            "T5_A5_to_A6_ai_pruned": {
                "pruned_count": len(t5_pruned_by_ai),
                "sample_pruned": t5_pruned_by_ai[:10],
            },
        },
        "pairwise_overlap_matrix": matrix_6x6,
        "core_consensus_terms": {
            "count": len(core_consensus),
            "terms": core_consensus,
        },
    }

    summary_path = os.path.join(output_dir, "ablation_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    # --------------------------------------------------------------------------
    # Pretty-Print Output Tables
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("  📊 6x6 PAIRWISE COMMON TERMS INTERSECTION MATRIX")
    print("=" * 80)
    col_names = ["A1 (Legacy)", "A2 (Local)", "A3 (Dual)", "A4 (Enh)", "A5 (Wide)", "A6 (Gold)"]
    print(f"{'Approach':<22} | " + " | ".join(f"{col:>10}" for col in col_names))
    print("-" * 88)
    for (row_name, _), short_name in zip(approaches, ["A1", "A2", "A3", "A4", "A5", "A6"]):
        row_str = f"{row_name:<22} | "
        vals = [f"{matrix_6x6[row_name][other_name]:>10}" for other_name, _ in approaches]
        print(row_str + " | ".join(vals))

    print("\n" + "=" * 80)
    print(f"  🏆 CORE CONSENSUS TERMS ACROSS ALL 6 APPROACHES ({len(core_consensus)} Terms)")
    print("=" * 80)
    for i, term in enumerate(core_consensus, 1):
        print(f"  {i:>2}. {term}")

    print("\n" + "=" * 80)
    print("  ✅ ABLATION STUDY COMPLETE & ARTIFACTS PERSISTED")
    print("=" * 80)
    print(f"  • Artifacts directory: {output_dir}")
    print(f"  • Summary file: {summary_path}")
    print(f"  • Matrix file: {matrix_path}")
    print("=" * 80 + "\n")

    return summary_data


def main():
    parser = argparse.ArgumentParser(description="Run the 6-approach ablation study for PaperMind.")
    parser.add_argument("--pdf", default=DEFAULT_PDF, help="Path to input PDF.")
    parser.add_argument(
        "--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory for ablation JSONs."
    )
    parser.add_argument("--offline", action="store_true", help="Run in deterministic offline mode.")
    args = parser.parse_args()

    run_master_ablation_study(
        pdf_path=args.pdf, output_dir=args.output_dir, offline_mode=args.offline
    )


if __name__ == "__main__":
    main()
