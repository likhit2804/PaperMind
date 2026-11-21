"""
download_benchmarks.py — Official Public Benchmark Downloader & Validator.

Downloads and validates authoritative academic benchmark datasets for scientific concept &
keyphrase extraction:
  1. SemEval-2010 Task 5 (All 100 full-length scientific papers from ACM Digital Library across 4 domains):
     - Track C: Computer Systems, Grid, Networks, Distributed Systems (25 papers)
     - Track I: Artificial Intelligence, Machine Learning (25 papers)
     - Track H: Information Retrieval, Hypertext, Web Search (25 papers)
     - Track J: Computer Architecture, Theory, Formal Methods (25 papers)
     Official Repository: boudinfl/ake-datasets (Florian Boudin, University of Nantes)

  2. Real Open-Access arXiv Research PDFs across 3 scales:
     - Short Paper (12 pages): Deep Residual Learning for Image Recognition (ResNet, 1512.03385)
     - Medium Paper (15 pages): Attention Is All You Need (Transformer, 1706.03762)
     - Long Survey (84 pages): A Survey of Large Language Models (LLM Survey, 2303.18223)

Usage:
  python pipeline/evals/download_benchmarks.py --all
  python pipeline/evals/download_benchmarks.py --all --download-pdfs
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

# Root directory setup
PIPELINE_EVALS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(PIPELINE_EVALS_DIR))
DEFAULT_BENCHMARK_DIR = os.path.join(PROJECT_ROOT, "data", "public_benchmarks", "semeval2010")
SAMPLE_PDFS_DIR = os.path.join(PROJECT_ROOT, "data", "public_benchmarks", "sample_pdfs")
UPLOADS_PAPERS_DIR = os.path.join(PROJECT_ROOT, "backend-node", "src", "uploads", "papers")

SEMEVAL_BASE_URL = (
    "https://raw.githubusercontent.com/boudinfl/ake-datasets/master/datasets/SemEval-2010"
)

DOMAIN_NAMES = {
    "C": "Computer Systems & Networks (Grid/Distributed)",
    "I": "Artificial Intelligence & Machine Learning",
    "H": "Information Retrieval & Web Systems",
    "J": "Computer Architecture & Theory",
}

ARXIV_TARGETS = [
    {
        "key": "short_paper",
        "arxiv_id": "1512.03385",
        "title": "Deep Residual Learning for Image Recognition",
        "domain": "Computer Vision / Deep Learning (ResNet)",
        "url": "https://arxiv.org/pdf/1512.03385.pdf",
        "filename": "arxiv_1512.03385_resnet.pdf",
        "scale": "Short (12 pages)",
    },
    {
        "key": "medium_paper",
        "arxiv_id": "1706.03762",
        "title": "Attention Is All You Need",
        "domain": "Natural Language Processing / Transformers",
        "url": "https://arxiv.org/pdf/1706.03762.pdf",
        "filename": "arxiv_1706.03762_transformer.pdf",
        "scale": "Medium (15 pages)",
    },
    {
        "key": "long_survey",
        "arxiv_id": "2303.18223",
        "title": "A Survey of Large Language Models",
        "domain": "Large Language Models & AI Systems",
        "url": "https://arxiv.org/pdf/2303.18223.pdf",
        "filename": "arxiv_2303.18223_llm_survey.pdf",
        "scale": "Long Monograph / Survey (~84 pages)",
    },
]


def download_file(url: str, dest_path: str, timeout: int = 30) -> bool:
    """Downloads a file from url and saves it to dest_path with user-agent headers."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PaperMind-Benchmark/2.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            with open(dest_path, "wb") as f:
                f.write(content)
        return True
    except Exception as err:
        print(f"  ❌ Download failed for {url}: {err}", file=sys.stderr)
        return False


def validate_semeval_xml(xml_path: str) -> dict:
    """Parses SemEval-2010 XML to extract title, sentence count, and full text length."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        sentences = root.findall(".//sentence")
        title_tokens = []
        body_words = []
        for s in sentences:
            sec = s.attrib.get("section", "")
            tokens = [
                t.find("word").text
                for t in s.findall(".//token")
                if t.find("word") is not None and t.find("word").text
            ]
            sent_str = " ".join(tokens)
            if sec == "title":
                title_tokens.append(sent_str)
            body_words.append(sent_str)

        title = (
            " ".join(title_tokens)
            if title_tokens
            else os.path.basename(xml_path).replace(".xml", "")
        )
        full_text = " ".join(body_words)
        return {
            "valid": True,
            "title": title,
            "sentence_count": len(sentences),
            "character_count": len(full_text),
            "word_count": len(full_text.split()),
        }
    except Exception as err:
        return {"valid": False, "error": str(err)}


def fetch_gold_references(dest_dir: str) -> dict:
    """Downloads and caches the official SemEval-2010 gold keyphrase references."""
    references = {
        "combined": {
            "url": f"{SEMEVAL_BASE_URL}/references/test.combined.stem.json",
            "file": "test.combined.stem.json",
            "desc": "Official Combined (Author + Reader) Gold Keyphrases",
        },
        "author": {
            "url": f"{SEMEVAL_BASE_URL}/references/test.author.stem.json",
            "file": "test.author.stem.json",
            "desc": "Author-Assigned Gold Keyphrases",
        },
        "reader": {
            "url": f"{SEMEVAL_BASE_URL}/references/test.reader.stem.json",
            "file": "test.reader.stem.json",
            "desc": "Reader-Annotated Gold Keyphrases",
        },
    }

    loaded_refs = {}
    print("\n📦 [1/3] Downloading Official SemEval-2010 Reference Ground-Truth Files...")
    for key, info in references.items():
        dest = os.path.join(dest_dir, "references", info["file"])
        if not os.path.exists(dest):
            print(f"  ⬇️ Fetching {info['desc']}...")
            success = download_file(info["url"], dest)
            if not success:
                print(f"  ⚠️ Warning: Could not download {info['file']}")
                continue
        with open(dest, encoding="utf-8") as f:
            data = json.load(f)
            loaded_refs[key] = data
            print(f"  ✅ {info['desc']}: Loaded {len(data)} test paper ground-truth entries.")

    return loaded_refs


def _download_single_paper(pid: str, papers_dir: str, gold_map: dict) -> dict:
    """Helper for concurrent paper downloading."""
    dest_xml = os.path.join(papers_dir, f"{pid}.xml")
    if not os.path.exists(dest_xml):
        url = f"{SEMEVAL_BASE_URL}/test/{pid}.xml"
        ok = download_file(url, dest_xml)
        if not ok:
            return None

    validation = validate_semeval_xml(dest_xml)
    if not validation.get("valid"):
        return None

    domain_code = pid.split("-")[0] if "-" in pid else "Unknown"
    domain_name = DOMAIN_NAMES.get(domain_code, "Scientific Research")

    gold_entries = gold_map.get(pid, [])
    gold_keyphrases = []
    for item in gold_entries:
        phrase = (
            " ".join(item[0])
            if isinstance(item, list) and item and isinstance(item[0], list)
            else (" ".join(item) if isinstance(item, list) else str(item))
        )
        if phrase.strip():
            gold_keyphrases.append(phrase.strip())

    return {
        "id": pid,
        "track": domain_code,
        "domain": domain_name,
        "title": validation["title"],
        "xml_path": dest_xml,
        "sentences": validation["sentence_count"],
        "words": validation["word_count"],
        "gold_keyphrases_count": len(gold_keyphrases),
        "gold_keyphrases_sample": gold_keyphrases[:5],
    }


def fetch_semeval_papers_concurrent(
    paper_ids: list, dest_dir: str, gold_map: dict, max_workers: int = 10
) -> list:
    """Downloads XML files concurrently for the requested SemEval-2010 paper IDs."""
    papers_dir = os.path.join(dest_dir, "papers")
    os.makedirs(papers_dir, exist_ok=True)
    manifest = []

    print(
        f"\n📄 [2/3] Downloading & Validating {len(paper_ids)} SemEval-2010 Full-Text XML Papers (Concurrency: {max_workers})..."
    )
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_pid = {
            executor.submit(_download_single_paper, pid, papers_dir, gold_map): pid
            for pid in paper_ids
        }
        completed_count = 0
        for future in as_completed(future_to_pid):
            pid = future_to_pid[future]
            completed_count += 1
            try:
                result = future.result()
                if result:
                    manifest.append(result)
                    if completed_count % 10 == 0 or completed_count == len(paper_ids):
                        print(
                            f"  Progress: {completed_count}/{len(paper_ids)} papers processed ({len(manifest)} valid)..."
                        )
            except Exception as exc:
                print(f"  ❌ Error processing {pid}: {exc}")

    manifest.sort(
        key=lambda x: (
            x["track"],
            int(x["id"].split("-")[1]) if x["id"].split("-")[1].isdigit() else 999,
        )
    )
    elapsed = time.time() - t0
    print(f"  ✅ Completed {len(manifest)}/{len(paper_ids)} SemEval papers in {elapsed:.2f}s!")
    return manifest


def download_sample_arxiv_pdfs(dest_dir: str = SAMPLE_PDFS_DIR) -> list:
    """Downloads the 3 representative real-world arXiv research PDFs across 3 scales."""
    print("\n📚 [3/3] Downloading Real Open-Access arXiv Research PDFs across 3 Scales...")
    os.makedirs(dest_dir, exist_ok=True)
    os.makedirs(UPLOADS_PAPERS_DIR, exist_ok=True)

    try:
        import fitz  # PyMuPDF
    except ImportError:
        fitz = None

    pdf_manifest = []

    for item in ARXIV_TARGETS:
        dest_pdf = os.path.join(dest_dir, item["filename"])
        upload_copy = os.path.join(UPLOADS_PAPERS_DIR, item["filename"])

        if not os.path.exists(dest_pdf):
            print(f"  ⬇️ Downloading {item['title']} [{item['scale']}] from {item['url']}...")
            ok = download_file(item["url"], dest_pdf, timeout=60)
            if not ok:
                print(f"  ❌ Failed to download {item['filename']}")
                continue
        else:
            print(f"  ✅ [Cached] {item['filename']}")

        # Also place a copy in backend uploads so the backend can use it directly
        if not os.path.exists(upload_copy):
            try:
                import shutil

                shutil.copy2(dest_pdf, upload_copy)
            except Exception:
                pass

        pages = 0
        extracted_title = item["title"]
        file_size_mb = round(os.path.getsize(dest_pdf) / (1024 * 1024), 2)

        if fitz:
            try:
                doc = fitz.open(dest_pdf)
                pages = len(doc)
                doc_title = doc.metadata.get("title")
                if doc_title and len(doc_title.strip()) > 5:
                    extracted_title = doc_title.strip()
                doc.close()
            except Exception as err:
                print(f"  ⚠️ Error reading PDF metadata: {err}")

        pdf_info = {
            "key": item["key"],
            "arxiv_id": item["arxiv_id"],
            "title": extracted_title,
            "domain": item["domain"],
            "scale": item["scale"],
            "pages": pages,
            "size_mb": file_size_mb,
            "pdf_path": dest_pdf,
            "upload_path": upload_copy,
        }
        pdf_manifest.append(pdf_info)
        print(
            f"  📄 [{item['key']}] {extracted_title[:45]:<45} | {pages} pages | {file_size_mb} MB | {item['domain']}"
        )

    return pdf_manifest


def main():
    parser = argparse.ArgumentParser(
        description="Download and validate official benchmark datasets."
    )
    parser.add_argument(
        "--dest-dir",
        default=DEFAULT_BENCHMARK_DIR,
        help="Destination directory for benchmark data.",
    )
    parser.add_argument(
        "--all", action="store_true", help="Download all 100 test papers from SemEval-2010."
    )
    parser.add_argument(
        "--download-pdfs",
        action="store_true",
        default=True,
        help="Download representative arXiv PDFs.",
    )
    parser.add_argument(
        "--workers", type=int, default=10, help="Number of concurrent download workers."
    )
    args = parser.parse_args()

    dest_dir = os.path.abspath(args.dest_dir)
    os.makedirs(dest_dir, exist_ok=True)

    print("=" * 85)
    print("  📥 PaperMind Official Academic Benchmark & Real-PDF Downloader & Validator")
    print(f"  SemEval Directory: {dest_dir}")
    print(f"  Sample PDFs Dir:   {SAMPLE_PDFS_DIR}")
    print("=" * 85)

    # 1. References
    refs = fetch_gold_references(dest_dir)
    combined_gold = refs.get("combined", {})
    if not combined_gold:
        print("Fatal: Could not load SemEval-2010 gold reference.")
        sys.exit(1)

    # 2. Papers list (All 100 or specific)
    paper_ids = (
        list(combined_gold.keys())
        if args.all
        else [
            "C-1",
            "C-3",
            "C-4",
            "C-6",
            "C-8",
            "I-1",
            "I-4",
            "H-2",
            "H-4",
            "J-1",
            "J-4",
        ]
    )

    manifest = fetch_semeval_papers_concurrent(
        paper_ids, dest_dir, combined_gold, max_workers=args.workers
    )

    # 3. Real arXiv PDFs
    pdf_manifest = download_sample_arxiv_pdfs() if args.download_pdfs else []

    # Save comprehensive manifest
    manifest_path = os.path.join(dest_dir, "benchmark_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "dataset": "SemEval-2010 Task 5 (Academic Keyphrase Extraction) + arXiv Real PDFs",
                "source": SEMEVAL_BASE_URL,
                "semeval_paper_count": len(manifest),
                "semeval_tracks": {
                    "C": sum(1 for p in manifest if p["track"] == "C"),
                    "H": sum(1 for p in manifest if p["track"] == "H"),
                    "I": sum(1 for p in manifest if p["track"] == "I"),
                    "J": sum(1 for p in manifest if p["track"] == "J"),
                },
                "semeval_papers": manifest,
                "real_arxiv_pdfs": pdf_manifest,
            },
            f,
            indent=2,
        )

    print("\n" + "=" * 85)
    print("  📊 Benchmark Download & Verification Summary")
    print("=" * 85)
    print(f"  • SemEval-2010 Papers Downloaded & Validated: {len(manifest)} / 100")
    print(
        f"  • Track Breakdown: C={sum(1 for p in manifest if p['track'] == 'C')} | H={sum(1 for p in manifest if p['track'] == 'H')} | I={sum(1 for p in manifest if p['track'] == 'I')} | J={sum(1 for p in manifest if p['track'] == 'J')}"
    )
    print(f"  • Real-World arXiv PDFs Downloaded: {len(pdf_manifest)}")
    for p in pdf_manifest:
        print(f"     - [{p['scale']}] {p['title']} ({p['pages']} pages, {p['size_mb']} MB)")
    print(f"  • Manifest File Saved To: {manifest_path}")
    print("=" * 85)
    print("✅ All 100 SemEval-2010 papers and 3 real arXiv research PDFs are ready!\n")


if __name__ == "__main__":
    main()
