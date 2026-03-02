"""Prototype A: Paragraph-Level Diff using SequenceMatcher.

Approach: Split documents into paragraphs, use Python's difflib.SequenceMatcher
to align paragraphs between original and modified, then diff within matched pairs.

Strengths: Simple, fast, well-understood algorithm.
Weaknesses: Treats paragraphs as opaque blocks; moved clauses detected as delete+add.
"""

import time
from difflib import SequenceMatcher
from pathlib import Path
from uuid import uuid4

from app.services.parser import DocxParser
from app.models.schemas import ChangeType

parser = DocxParser()
FIXTURES = Path(__file__).parent / "fixtures"


def diff_paragraphs_sequence_matcher(original_path: Path, modified_path: Path):
    """Compare two documents using SequenceMatcher on paragraph texts."""
    t0 = time.perf_counter()

    orig = parser.parse(original_path, uuid4())
    mod = parser.parse(modified_path, uuid4())

    orig_texts = [p.text for p in orig.paragraphs]
    mod_texts = [p.text for p in mod.paragraphs]

    matcher = SequenceMatcher(None, orig_texts, mod_texts, autojunk=False)
    changes = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        elif tag == "delete":
            for i in range(i1, i2):
                changes.append({
                    "type": ChangeType.DELETION,
                    "original_text": orig_texts[i],
                    "modified_text": None,
                    "section": orig.paragraphs[i].parent_section or orig.paragraphs[i].section_number,
                    "original_idx": i,
                    "modified_idx": None,
                })
        elif tag == "insert":
            for j in range(j1, j2):
                changes.append({
                    "type": ChangeType.ADDITION,
                    "original_text": None,
                    "modified_text": mod_texts[j],
                    "section": mod.paragraphs[j].parent_section or mod.paragraphs[j].section_number,
                    "original_idx": None,
                    "modified_idx": j,
                })
        elif tag == "replace":
            # Pair up replacements where possible, leftovers are deletes/adds
            orig_slice = list(range(i1, i2))
            mod_slice = list(range(j1, j2))
            paired = min(len(orig_slice), len(mod_slice))

            for k in range(paired):
                oi = orig_slice[k]
                mj = mod_slice[k]
                # Compute intra-paragraph similarity
                ratio = SequenceMatcher(None, orig_texts[oi], mod_texts[mj]).ratio()
                if ratio > 0.4:
                    changes.append({
                        "type": ChangeType.MODIFICATION,
                        "original_text": orig_texts[oi],
                        "modified_text": mod_texts[mj],
                        "section": orig.paragraphs[oi].parent_section or orig.paragraphs[oi].section_number,
                        "similarity": round(ratio, 3),
                        "original_idx": oi,
                        "modified_idx": mj,
                    })
                else:
                    changes.append({
                        "type": ChangeType.DELETION,
                        "original_text": orig_texts[oi],
                        "modified_text": None,
                        "section": orig.paragraphs[oi].parent_section or orig.paragraphs[oi].section_number,
                        "original_idx": oi,
                        "modified_idx": None,
                    })
                    changes.append({
                        "type": ChangeType.ADDITION,
                        "original_text": None,
                        "modified_text": mod_texts[mj],
                        "section": mod.paragraphs[mj].parent_section or mod.paragraphs[mj].section_number,
                        "original_idx": None,
                        "modified_idx": mj,
                    })

            # Remaining unpaired
            for k in range(paired, len(orig_slice)):
                oi = orig_slice[k]
                changes.append({
                    "type": ChangeType.DELETION,
                    "original_text": orig_texts[oi],
                    "modified_text": None,
                    "section": orig.paragraphs[oi].parent_section,
                    "original_idx": oi,
                    "modified_idx": None,
                })
            for k in range(paired, len(mod_slice)):
                mj = mod_slice[k]
                changes.append({
                    "type": ChangeType.ADDITION,
                    "original_text": None,
                    "modified_text": mod_texts[mj],
                    "section": mod.paragraphs[mj].parent_section,
                    "original_idx": None,
                    "modified_idx": mj,
                })

    elapsed = time.perf_counter() - t0
    return changes, elapsed


def evaluate():
    orig = FIXTURES / "nda_original.docx"
    mod = FIXTURES / "nda_modified.docx"

    changes, elapsed = diff_paragraphs_sequence_matcher(orig, mod)

    print(f"=== PROTOTYPE A: Paragraph-Level SequenceMatcher ===")
    print(f"Time: {elapsed*1000:.1f}ms")
    print(f"Total changes detected: {len(changes)}")
    print()

    by_type = {}
    for c in changes:
        t = c["type"].value
        by_type[t] = by_type.get(t, 0) + 1
    for t, count in sorted(by_type.items()):
        print(f"  {t}: {count}")
    print()

    moves_detected = 0
    print("--- Changes Detail ---")
    for i, c in enumerate(changes):
        ct = c["type"].value.upper()
        section = c.get("section", "?")
        if c["type"] == ChangeType.MODIFICATION:
            sim = c.get("similarity", 0)
            orig_preview = (c["original_text"] or "")[:60]
            mod_preview = (c["modified_text"] or "")[:60]
            print(f"  [{i+1}] {ct} (sim={sim}) section={section}")
            print(f"       ORIG: {orig_preview}...")
            print(f"       MOD:  {mod_preview}...")
        elif c["type"] == ChangeType.DELETION:
            preview = (c["original_text"] or "")[:80]
            print(f"  [{i+1}] {ct} section={section}: {preview}...")
        elif c["type"] == ChangeType.ADDITION:
            preview = (c["modified_text"] or "")[:80]
            print(f"  [{i+1}] {ct} section={section}: {preview}...")
        print()

    # Score against known changes
    print("--- Accuracy Assessment ---")
    print("Known changes to detect: 11")
    print(f"Changes reported: {len(changes)}")
    print(f"Moves detected as moves: {moves_detected} (expected: 1 - Governing Law moved)")
    print("NOTE: SequenceMatcher cannot detect moves; they appear as delete + add pairs")


if __name__ == "__main__":
    evaluate()
