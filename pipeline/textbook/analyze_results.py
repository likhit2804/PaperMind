import os
import json
from collections import Counter

def main():
    concepts_dir = "extracted_concepts"
    if not os.path.exists(concepts_dir):
        print(f"Error: Directory {concepts_dir} not found.")
        return

    chapter_files = sorted(
        [f for f in os.listdir(concepts_dir) if f.startswith("chapter_") and f.endswith(".json")],
        key=lambda x: int(re.search(r'\d+', x).group())
    )

    global_terms_counter = Counter()
    chapter_terms = {}
    term_to_chapters = {}

    for fname in chapter_files:
        ch_num = int(re.search(r'\d+', fname).group())
        path = os.path.join(concepts_dir, fname)
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            unique_terms = data.get("unique_key_terms", [])
            chapter_terms[ch_num] = unique_terms
            
            for term in unique_terms:
                global_terms_counter[term] += 1
                if term not in term_to_chapters:
                    term_to_chapters[term] = []
                term_to_chapters[term].append(ch_num)

    total_unique_global = len(global_terms_counter)
    total_raw_extractions = sum(len(terms) for terms in chapter_terms.values())
    avg_terms_per_chapter = total_raw_extractions / len(chapter_files) if chapter_files else 0

    print("=== Global Key Term Ingestion Analysis ===")
    print(f"Total processed chapters: {len(chapter_files)}")
    print(f"Total raw extractions across all chapters: {total_raw_extractions}")
    print(f"Total unique global key terms (deduplicated): {total_unique_global}")
    print(f"Average key terms per chapter: {avg_terms_per_chapter:.2f}")
    
    # 1. Most common global terms (shared across many chapters)
    print("\nTop 15 Most Common Shared Terms (Cross-Chapter Themes):")
    most_common = global_terms_counter.most_common(15)
    for term, count in most_common:
        chapters_list = ", ".join(map(str, term_to_chapters[term]))
        print(f"  - '{term}': appeared in {count} chapters (Chapters: {chapters_list})")

    # 2. Chapter-specific unique terms
    print("\nExamples of Chapter-Specific Concepts (appeared in exactly 1 chapter):")
    chapter_specific_samples = {}
    for ch_num, terms in chapter_terms.items():
        specific = [t for t in terms if global_terms_counter[t] == 1]
        chapter_specific_samples[ch_num] = (len(specific), specific[:4])
        
    for ch_num in sorted(chapter_specific_samples.keys())[:10]:
        count, samples = chapter_specific_samples[ch_num]
        sample_str = ", ".join([f"'{s}'" for s in samples])
        print(f"  - Chapter {ch_num}: {count} unique terms. Samples: {sample_str}...")

if __name__ == "__main__":
    import re
    main()
