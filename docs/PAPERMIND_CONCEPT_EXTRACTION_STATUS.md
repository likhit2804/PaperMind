# PaperMind Concept Extraction: Current Status

Last verified: 2026-11-11

## Scope

This document describes only the current paper-concept extraction system. It does not claim that equations, references, notations, summaries, architecture notes, or the complete frontend pipeline have been benchmarked end to end.

## Current implementation

The active implementation is in `pipeline/research_paper/extract_paper_concepts.py`. Shared utilities are in `pipeline/utils.py`, and PDF helpers are in `pipeline/research_paper/pdf_utils.py`.

The measurable concept extractor has two stages:

### Stage 1: Candidate generation

`extract_noun_phrase_candidates()` creates a high-recall list of technical terms using rule-based linguistic and statistical heuristics. This stage is intentionally noisy so that valid concepts are not lost.

### Stage 2: Candidate verification

`filter_terms_via_ai()` filters the bounded candidate list using the configured Gemini model. If no API key is available, a deterministic offline fallback is used.

## What the benchmark runs

Run:

```powershell
python pipeline/evals/evaluate_paper_concepts.py
```

The evaluator loads the paper text, runs the two concept functions, keeps the first 15 verified terms, and scores them against gold keyphrases using stemming and exact equality. It computes micro-averaged precision, recall, and F1.

It does not invoke the command-line `main()` function of `extract_paper_concepts.py` and does not validate the final `concepts.json` artifact. This is a concept-engine benchmark, not a complete PDF-to-JSON integration test.

## Dataset

Dataset: SemEval-2010 Task 5: Automatic Keyphrase Extraction from Scientific Articles.

### Dataset domain

The dataset contains scholarly computer-science papers from ACM conference and workshop proceedings. Its four research areas are:

- C2.4 — Distributed Systems
- H3.3 — Information Search and Retrieval
- I2.11 — Distributed Artificial Intelligence / Multi-Agent Systems
- J4 — Social and Behavioral Sciences / Economics

The complete corpus contains 284 papers: 40 trial, 144 training, and 100 test papers. Therefore, this benchmark is relevant to technical academic concept extraction, but it does not yet represent domains such as physics, medicine, mathematics, or electrical engineering.

The current local subset contains four papers: `C-1`, `C-3`, `C-4`, and `C-6`. The configured `C-7` file returns HTTP 404 from the dataset mirror and is excluded. The official test split contains 100 documents, so the current result is not a full-test-set result.

Raw files are in `docs/benchmarks/semeval2010/raw/`.

Sources: [SemEval task paper](https://aclanthology.org/S10-1004/) and [AKE datasets repository](https://github.com/boudinfl/ake-datasets).

## Latest result

Result file: `docs/benchmarks/semeval2010/results/paper_concepts_eval.json`.

Protocol:

- Top 15 predictions per paper
- Porter-style stemming
- Exact-match scoring
- Micro-averaging across evaluated papers

| Metric | Result |
|---|---:|
| Papers evaluated | 4 |
| Top-k | 15 |
| Micro precision | 5.00% |
| Micro recall | 4.62% |
| Micro F1 | 4.80% |

The earlier exploratory `25.71% F1` used substring matching, all returned terms, and per-paper averaging. The previous stale result also bypassed candidate scoring. Neither is directly comparable to this current scored offline result.

## Published comparison

The official SemEval-2010 Task 5 paper reports approximately `27.5%` combined F1 for the best competition system under the top-15 exact-match protocol. PaperMind's current result is not yet a full apples-to-apples comparison because only four of the 100 test papers are available.

## Not established yet

- Full 100-paper SemEval performance.
- Performance on KP20k, Inspec, SciCite, S2ORC, Cora, or SciBERT/SDU.
- End-to-end `concepts.json` correctness.
- Domain-specific performance on PaperMind target papers.
- Stability across repeated Gemini runs.
- Fair comparison against published systems on the same complete split.

## Current limitations

1. The benchmark is incomplete.
2. Gemini verification is nondeterministic.
3. The evaluator scores functions directly rather than the final pipeline artifact.
4. The gold labels are keyphrases and may not represent every useful technical concept.
5. The code still imports the deprecated `google.generativeai` package.

## Observed extraction trace: SemEval-2010-C-1

Paper title: `Scalable Grid Service Discovery Based on UDDI`.

This paper was run through the updated POS + YAKE + TF-IDF scoring path with Gemini disabled.

| Measurement | Count |
|---|---:|
| Raw unique candidates | 1,766 |
| Global scored candidates | 75 |
| Local scored candidates | 15 |
| Consolidated candidates | 77 |
| Offline final terms | 77 |

Representative high-ranked terms were:

```text
service
grid service discovery
uddi
scalable
based
scalable grid service
grid computing
web services
uddi registries
dht
distributed
architecture
uddi registry
scalability
```

The strongest domain-relevant concepts in the trace were:

```text
grid service discovery
UDDI
UDDI registries
distributed hash tables
service discovery
grid computing
web services
proxy registry
scalability
service discovery architecture
```

The trace also exposed remaining offline-filter noise, including `based`, `will`, `full`, `allowing`, `success`, `abstract efficient`, and long grammatical fragments such as `dude architecture can support` and `uddi registries thereby making`. Candidate scoring improves ordering, but the offline verifier still needs deterministic generic-term removal, phrase-boundary cleanup, and nested-phrase reduction.

## Offline filtering update

The deterministic fallback was updated to operate on the scored candidate set instead of returning every raw candidate. It now applies automatic rules for:

- Leading and trailing stopwords
- Grammatical fragments and common function words
- Layout and citation artifacts
- Very short variable-like tokens
- Phrases longer than four words
- Nested shorter phrases when a longer informative phrase exists

On the same `C-1` trace:

| Measurement | Before filtering | After filtering |
|---|---:|---:|
| Scored candidates | 77 | 77 |
| Offline final concepts | 77 | 41 |

Examples retained by the offline filter include `grid service discovery`, `scalable grid service`, `grid computing`, `uddi registries`, `de facto industry standard`, `proxy registry`, `service discovery mechanisms`, and `distributed hash tables`.

Remaining noise includes `query`, `search`, `deployed`, `network`, `dude architecture`, and grammatical fragments such as `registries thereby making uddi`. This indicates that deterministic cleanup is reducing noise but does not yet understand phrase grammar or domain relevance reliably.

## Proposed next changes

1. Add optional spaCy noun-chunk and dependency validation to reject verb-led and grammatical fragments automatically.
2. Add YAKE and TF-IDF as explicit, independently logged ranking signals rather than describing them only as part of the combined score.
3. Add automatic common-word frequency penalties using a corpus-frequency package such as `wordfreq`, avoiding large hand-maintained rejection lists.
4. Add phrase-boundary and nested-phrase diagnostics so every removed term records a reason such as `generic_word`, `verb_fragment`, `nested_phrase`, or `layout_artifact`.
5. Save separate artifacts for `raw_candidates`, `scored_candidates`, `filtered_concepts`, and `rejected_candidates`.
6. Re-run the same paper repeatedly in offline mode and require stable output before using it as the deterministic baseline.
7. Compare offline output and Gemini output on the same scored candidate list, rather than comparing different candidate-generation paths.

## Important files

| Purpose | Location |
|---|---|
| Concept implementation | `pipeline/research_paper/extract_paper_concepts.py` |
| Official-style evaluator | `pipeline/evals/evaluate_paper_concepts.py` |
| Dataset loader | `pipeline/evaluate_public_benchmarks.py` |
| Raw SemEval files | `docs/benchmarks/semeval2010/raw/` |
| Current result | `docs/benchmarks/semeval2010/results/paper_concepts_eval.json` |

## Next steps

1. Obtain the complete SemEval test split.
2. Run all 100 papers with the same scorer.
3. Save per-paper predictions as well as aggregate metrics.
4. Add deterministic/offline repeat-run variance reporting.
5. Run the actual command-line extractor and score its generated `concepts.json`.
6. Build a small domain-specific gold set for PaperMind target papers.
