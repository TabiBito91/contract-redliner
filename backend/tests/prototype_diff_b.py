"""Prototype B: Hybrid Structural Matching + Character Diff.

Approach:
1. Parse documents into structured provisions (headings + their child paragraphs).
2. Match provisions between documents using heading/section-number alignment first,
   then fuzzy text similarity for unmatched provisions.
3. Detect MOVES by finding provisions that didn't match by position but match by content.
4. Within matched provision pairs, run character-level diff (difflib) to find
   specific modifications.

Strengths: Handles clause reordering (moves), section-aware, provision-level matching.
Weaknesses: More complex, relies on heading/section structure being present.
"""

import time
from difflib import SequenceMatcher
from pathlib import Path
from uuid import uuid4

from app.services.parser import DocxParser
from app.models.schemas import ChangeType, DocumentParagraph

parser = DocxParser()
FIXTURES = Path(__file__).parent / "fixtures"


class Provision:
    """A logical provision: a heading + its body paragraphs."""

    def __init__(self, heading: DocumentParagraph | None, body: list[DocumentParagraph]):
        self.heading = heading
        self.body = body
        self.section_number = heading.section_number if heading else None
        self.heading_text = heading.text if heading else ""
        self.full_text = self._compute_full_text()

    def _compute_full_text(self) -> str:
        parts = []
        if self.heading:
            parts.append(self.heading.text)
        for p in self.body:
            parts.append(p.text)
        return "\n".join(parts)

    def body_text(self) -> str:
        return "\n".join(p.text for p in self.body)

    def __repr__(self):
        return f"Provision(section={self.section_number}, heading={self.heading_text[:40]})"


def extract_provisions(paragraphs: list[DocumentParagraph]) -> list[Provision]:
    """Group paragraphs into provisions based on heading structure."""
    provisions = []
    current_heading = None
    current_body = []

    for p in paragraphs:
        if p.heading_level is not None:
            # Save previous provision
            if current_heading is not None or current_body:
                provisions.append(Provision(current_heading, current_body))
            current_heading = p
            current_body = []
        else:
            current_body.append(p)

    # Don't forget the last provision
    if current_heading is not None or current_body:
        provisions.append(Provision(current_heading, current_body))

    return provisions


def similarity(a: str, b: str) -> float:
    """Compute text similarity ratio."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def match_provisions(
    orig_provs: list[Provision],
    mod_provs: list[Provision],
) -> list[dict]:
    """Match provisions between original and modified documents.

    Strategy (revised - heading content takes priority over section numbers):
    1. Match by heading text similarity (>0.85) - most reliable when sections renumber.
    2. Match remaining by full-text (heading+body) similarity (>0.7) to detect moves.
    3. Match remaining by section number as last resort.
    4. Unmatched original provisions = deletions.
    5. Unmatched modified provisions = additions.

    Move detection: If a matched pair has significantly different positions, flag as MOVE.
    """
    matches = []
    orig_matched = set()
    mod_matched = set()

    # Pass 1: Heading text similarity (strips section numbers for comparison)
    def strip_section_num(text: str) -> str:
        """Remove leading section number for heading comparison."""
        import re
        return re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", text).strip()

    for i, op in enumerate(orig_provs):
        if not op.heading_text:
            continue
        orig_heading_clean = strip_section_num(op.heading_text)
        if not orig_heading_clean:
            continue
        best_j = -1
        best_sim = 0.0
        for j, mp in enumerate(mod_provs):
            if j in mod_matched or not mp.heading_text:
                continue
            mod_heading_clean = strip_section_num(mp.heading_text)
            if not mod_heading_clean:
                continue
            sim = similarity(orig_heading_clean, mod_heading_clean)
            if sim > best_sim:
                best_sim = sim
                best_j = j
        if best_sim > 0.85 and best_j >= 0:
            is_move = abs(i - best_j) > 1
            match_type = "move_heading" if is_move else "heading_match"
            matches.append({"orig_idx": i, "mod_idx": best_j, "match_type": match_type})
            orig_matched.add(i)
            mod_matched.add(best_j)

    # Pass 2: Full text similarity for remaining (catches renumbered + restructured)
    for i, op in enumerate(orig_provs):
        if i in orig_matched or not op.full_text.strip():
            continue
        best_j = -1
        best_sim = 0.0
        for j, mp in enumerate(mod_provs):
            if j in mod_matched or not mp.full_text.strip():
                continue
            sim = similarity(op.full_text, mp.full_text)
            if sim > best_sim:
                best_sim = sim
                best_j = j
        if best_sim > 0.5 and best_j >= 0:
            is_move = abs(i - best_j) > 1
            match_type = "move_content" if is_move else "content_match"
            matches.append({"orig_idx": i, "mod_idx": best_j, "match_type": match_type})
            orig_matched.add(i)
            mod_matched.add(best_j)

    return matches, orig_matched, mod_matched


def compute_inline_diff(original: str, modified: str) -> list[dict]:
    """Compute character-level diff within a matched provision pair."""
    if original == modified:
        return []

    matcher = SequenceMatcher(None, original, modified, autojunk=False)
    diffs = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        diffs.append({
            "tag": tag,
            "original_span": original[i1:i2] if tag in ("delete", "replace") else "",
            "modified_span": modified[j1:j2] if tag in ("insert", "replace") else "",
        })
    return diffs


def diff_hybrid(original_path: Path, modified_path: Path):
    """Compare two documents using hybrid structural matching."""
    t0 = time.perf_counter()

    orig_doc = parser.parse(original_path, uuid4())
    mod_doc = parser.parse(modified_path, uuid4())

    orig_provs = extract_provisions(orig_doc.paragraphs)
    mod_provs = extract_provisions(mod_doc.paragraphs)

    matches, orig_matched, mod_matched = match_provisions(orig_provs, mod_provs)

    changes = []

    # Process matched provisions
    for m in matches:
        oi = m["orig_idx"]
        mi = m["mod_idx"]
        op = orig_provs[oi]
        mp = mod_provs[mi]

        is_move = m["match_type"] == "move"

        # Check heading changes
        if op.heading_text != mp.heading_text:
            changes.append({
                "type": ChangeType.MODIFICATION,
                "original_text": op.heading_text,
                "modified_text": mp.heading_text,
                "section": op.section_number or mp.section_number,
                "is_heading": True,
                "is_move": is_move,
                "match_type": m["match_type"],
                "inline_diffs": compute_inline_diff(op.heading_text, mp.heading_text),
            })

        # Compare body paragraphs within the provision
        orig_body = [p.text for p in op.body]
        mod_body = [p.text for p in mp.body]

        body_matcher = SequenceMatcher(None, orig_body, mod_body, autojunk=False)
        for tag, i1, i2, j1, j2 in body_matcher.get_opcodes():
            if tag == "equal":
                if is_move:
                    # Even if text is identical, it was moved
                    for k in range(i1, i2):
                        changes.append({
                            "type": ChangeType.MOVE,
                            "original_text": orig_body[k],
                            "modified_text": mod_body[k - i1 + j1],
                            "section": op.section_number,
                            "is_move": True,
                            "match_type": m["match_type"],
                            "inline_diffs": [],
                        })
                continue
            elif tag == "delete":
                for k in range(i1, i2):
                    changes.append({
                        "type": ChangeType.DELETION,
                        "original_text": orig_body[k],
                        "modified_text": None,
                        "section": op.section_number,
                        "is_move": False,
                        "match_type": m["match_type"],
                    })
            elif tag == "insert":
                for k in range(j1, j2):
                    changes.append({
                        "type": ChangeType.ADDITION,
                        "original_text": None,
                        "modified_text": mod_body[k],
                        "section": mp.section_number,
                        "is_move": False,
                        "match_type": m["match_type"],
                    })
            elif tag == "replace":
                pairs = min(i2 - i1, j2 - j1)
                for k in range(pairs):
                    orig_t = orig_body[i1 + k]
                    mod_t = mod_body[j1 + k]
                    inline = compute_inline_diff(orig_t, mod_t)
                    changes.append({
                        "type": ChangeType.MODIFICATION,
                        "original_text": orig_t,
                        "modified_text": mod_t,
                        "section": op.section_number,
                        "is_move": is_move,
                        "match_type": m["match_type"],
                        "similarity": round(similarity(orig_t, mod_t), 3),
                        "inline_diffs": inline,
                    })
                for k in range(pairs, i2 - i1):
                    changes.append({
                        "type": ChangeType.DELETION,
                        "original_text": orig_body[i1 + k],
                        "modified_text": None,
                        "section": op.section_number,
                        "is_move": False,
                        "match_type": m["match_type"],
                    })
                for k in range(pairs, j2 - j1):
                    changes.append({
                        "type": ChangeType.ADDITION,
                        "original_text": None,
                        "modified_text": mod_body[j1 + k],
                        "section": mp.section_number,
                        "is_move": False,
                        "match_type": m["match_type"],
                    })

    # Unmatched original provisions = deleted
    for i, op in enumerate(orig_provs):
        if i not in orig_matched:
            full = op.full_text
            if full.strip():
                changes.append({
                    "type": ChangeType.DELETION,
                    "original_text": full,
                    "modified_text": None,
                    "section": op.section_number,
                    "is_move": False,
                    "match_type": "unmatched",
                })

    # Unmatched modified provisions = added
    for j, mp in enumerate(mod_provs):
        if j not in mod_matched:
            full = mp.full_text
            if full.strip():
                changes.append({
                    "type": ChangeType.ADDITION,
                    "original_text": None,
                    "modified_text": full,
                    "section": mp.section_number,
                    "is_move": False,
                    "match_type": "unmatched",
                })

    elapsed = time.perf_counter() - t0
    return changes, elapsed, len(orig_provs), len(mod_provs), matches


def evaluate():
    orig = FIXTURES / "nda_original.docx"
    mod = FIXTURES / "nda_modified.docx"

    changes, elapsed, n_orig, n_mod, matches = diff_hybrid(orig, mod)

    print(f"=== PROTOTYPE B: Hybrid Structural Matching + Character Diff ===")
    print(f"Time: {elapsed*1000:.1f}ms")
    print(f"Original provisions: {n_orig}")
    print(f"Modified provisions: {n_mod}")
    print(f"Matched provisions: {len(matches)}")
    print(f"Total changes detected: {len(changes)}")
    print()

    by_type = {}
    for c in changes:
        t = c["type"].value
        by_type[t] = by_type.get(t, 0) + 1
    for t, count in sorted(by_type.items()):
        print(f"  {t}: {count}")
    print()

    moves = [c for c in changes if c.get("is_move")]
    print(f"Moves detected: {len(moves)}")
    print()

    print("--- Provision Matches ---")
    for m in matches:
        print(f"  orig[{m['orig_idx']}] <-> mod[{m['mod_idx']}]  ({m['match_type']})")
    print()

    print("--- Changes Detail ---")
    for i, c in enumerate(changes):
        ct = c["type"].value.upper()
        section = c.get("section", "?")
        is_move = c.get("is_move", False)
        move_tag = " [MOVED]" if is_move else ""

        if c["type"] == ChangeType.MODIFICATION:
            sim = c.get("similarity", "")
            orig_preview = (c["original_text"] or "")[:60]
            mod_preview = (c["modified_text"] or "")[:60]
            print(f"  [{i+1}] {ct}{move_tag} (sim={sim}) section={section}")
            print(f"       ORIG: {orig_preview}...")
            print(f"       MOD:  {mod_preview}...")
            diffs = c.get("inline_diffs", [])
            for d in diffs[:3]:
                print(f"       DIFF: -{d.get('original_span','')[:40]}  +{d.get('modified_span','')[:40]}")
        elif c["type"] == ChangeType.DELETION:
            preview = (c["original_text"] or "")[:80]
            print(f"  [{i+1}] {ct} section={section}: {preview}...")
        elif c["type"] == ChangeType.ADDITION:
            preview = (c["modified_text"] or "")[:80]
            print(f"  [{i+1}] {ct} section={section}: {preview}...")
        elif c["type"] == ChangeType.MOVE:
            preview = (c["original_text"] or "")[:80]
            print(f"  [{i+1}] {ct} section={section}: {preview}...")
        print()

    # Score
    print("--- Accuracy Assessment ---")
    print("Known changes: 11")
    print(f"Changes reported: {len(changes)}")
    print(f"Moves detected: {len(moves)} (expected: at least 1 - Governing Law)")
    non_move_modifications = [c for c in changes if c["type"] == ChangeType.MODIFICATION and not c.get("is_move")]
    print(f"Non-move modifications: {len(non_move_modifications)}")


if __name__ == "__main__":
    evaluate()
