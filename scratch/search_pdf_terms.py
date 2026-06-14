import fitz
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

doc = fitz.open("entropy-25-00738-v2.pdf")
terms = ["classification module", "tc module", "tc", "threshold classification"]

for i, page in enumerate(doc):
    text = page.get_text("text")
    for term in terms:
        matches = list(re.finditer(re.escape(term), text, re.IGNORECASE))
        if matches:
            print(f"Page {i+1} matches for '{term}':")
            for match in matches:
                start = max(0, match.start() - 60)
                end = min(len(text), match.end() + 60)
                snippet = text[start:end].replace("\n", " ")
                print(f"  ... {snippet} ...")

doc.close()
