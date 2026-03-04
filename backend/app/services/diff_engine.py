"""Hybrid Structural Diff Engine (ADR-002).

Implements provision-level matching with character-level inline diffs.
Matching strategy:
  1. Heading content similarity (strips section numbers) - handles renumbering
  2. Full-text similarity for remaining - catches restructured provisions
  3. Position delta for move detection
  4. Character-level difflib within matched pairs for inline diffs
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from uuid import uuid4

from app.models.schemas import (
    Change,
    ChangeType,
    DocumentParagraph,
    ParsedDocument,
)


# --- Provision grouping ---

@dataclass
class Provision:
    """A logical provision: a heading + its body paragraphs."""
    heading: DocumentParagraph | None
    body: list[DocumentParagraph]
    index: int  # position in the document

    @property
    def section_number(self) -> str | None:
        return self.heading.section_number if self.heading else None

    @property
    def heading_text(self) -> str:
        return self.heading.text if self.heading else ""

    @property
    def full_text(self) -> str:
        parts = []
        if self.heading:
            parts.append(self.heading.text)
        for p in self.body:
            parts.append(p.text)
        return "\n".join(parts)

    @property
    def body_text(self) -> str:
        return "\n".join(p.text for p in self.body)


@dataclass
class InlineDiff:
    """A character-level diff span within a matched text pair."""
    tag: str  # "insert", "delete", "replace"
    original_span: str
    modified_span: str


@dataclass
class DiffChange:
    """A detected change with full context for rendering and AI analysis."""
    change_type: ChangeType
    original_text: str | None = None
    modified_text: str | None = None
    section_context: str | None = None
    is_move: bool = False
    is_heading: bool = False
    inline_diffs: list[InlineDiff] = field(default_factory=list)
    similarity: float | None = None
    original_paragraph_id: str | None = None
    modified_paragraph_id: str | None = None

    def to_change_model(self, version_source: str | None = None) -> Change:
        """Convert to the API Change schema."""
        return Change(
            id=uuid4(),
            change_type=self.change_type,
            original_text=self.original_text,
            modified_text=self.modified_text,
            section_context=self.section_context,
            original_paragraph_id=self.original_paragraph_id,
            modified_paragraph_id=self.modified_paragraph_id,
            is_substantive=self._is_substantive(),
            version_source=version_source,
        )

    def _is_substantive(self) -> bool:
        """Determine if the change is substantive vs cosmetic/formatting."""
        if self.change_type in (ChangeType.ADDITION, ChangeType.DELETION):
            return True
        if self.change_type == ChangeType.MOVE:
            # A move with no text changes is structural, not substantive
            if self.original_text == self.modified_text:
                return False
            return True
        # For modifications, check if only section numbers changed
        if self.inline_diffs:
            for d in self.inline_diffs:
                orig = d.original_span.strip()
                mod = d.modified_span.strip()
                # If both are just numbers (section renumbering), not substantive
                if orig.replace(".", "").isdigit() and mod.replace(".", "").isdigit():
                    continue
                return True
            return False
        return True


# --- Section number stripping ---

_SECTION_NUM_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s*")


def _strip_section_number(text: str) -> str:
    """Remove leading section number for heading comparison."""
    return _SECTION_NUM_RE.sub("", text).strip()


def _section_label(section_num: str | None, heading_text: str | None) -> str | None:
    """Build a display label from a section number and heading text.

    Combines both where available so that distinct provisions with the same
    section number (e.g. the original §10 and a newly-added §10) produce
    distinct labels and are never incorrectly grouped together.

    Examples:
        ("10", "10. No Assignment")      -> "10. No Assignment"
        ("11", "11. Governing Law")      -> "11. Governing Law"
        (None, "Confidential Info")      -> "Confidential Info"
        ("3",  None)                     -> "3"
    """
    heading_clean = _strip_section_number(heading_text or "")
    if section_num and heading_clean:
        return f"{section_num}. {heading_clean}"
    return section_num or heading_text or None


# --- Similarity ---

def _similarity(a: str, b: str) -> float:
    """Compute text similarity ratio using SequenceMatcher."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


# --- Provision extraction ---

def extract_provisions(paragraphs: list[DocumentParagraph]) -> list[Provision]:
    """Group paragraphs into provisions based on heading structure."""
    provisions: list[Provision] = []
    current_heading: DocumentParagraph | None = None
    current_body: list[DocumentParagraph] = []
    idx = 0

    for p in paragraphs:
        if p.heading_level is not None:
            if current_heading is not None or current_body:
                provisions.append(Provision(current_heading, current_body, idx))
                idx += 1
            current_heading = p
            current_body = []
        else:
            current_body.append(p)

    if current_heading is not None or current_body:
        provisions.append(Provision(current_heading, current_body, idx))

    return provisions


# --- Provision matching ---

@dataclass
class ProvisionMatch:
    """A matched pair of provisions between original and modified documents."""
    orig_idx: int
    mod_idx: int
    match_type: str  # "heading_match", "move_heading", "content_match", "move_content"
    is_move: bool = False


def match_provisions(
    orig_provs: list[Provision],
    mod_provs: list[Provision],
    heading_threshold: float = 0.85,
    content_threshold: float = 0.5,
) -> tuple[list[ProvisionMatch], set[int], set[int]]:
    """Match provisions between original and modified documents.

    Strategy:
    1. Heading content similarity (strips section numbers) - most reliable.
    2. Full-text similarity for remaining - catches restructured provisions.
    3. Position delta determines if a match is a MOVE.
    """
    matches: list[ProvisionMatch] = []
    orig_matched: set[int] = set()
    mod_matched: set[int] = set()

    # Pass 1: Heading content similarity
    for i, op in enumerate(orig_provs):
        if not op.heading_text:
            continue
        orig_clean = _strip_section_number(op.heading_text)
        if not orig_clean:
            continue

        best_j = -1
        best_sim = 0.0
        for j, mp in enumerate(mod_provs):
            if j in mod_matched or not mp.heading_text:
                continue
            mod_clean = _strip_section_number(mp.heading_text)
            if not mod_clean:
                continue
            sim = _similarity(orig_clean, mod_clean)
            if sim > best_sim:
                best_sim = sim
                best_j = j

        if best_sim >= heading_threshold and best_j >= 0:
            is_move = abs(i - best_j) > 1
            match_type = "move_heading" if is_move else "heading_match"
            matches.append(ProvisionMatch(i, best_j, match_type, is_move))
            orig_matched.add(i)
            mod_matched.add(best_j)

    # Pass 2: Full text similarity for remaining
    for i, op in enumerate(orig_provs):
        if i in orig_matched or not op.full_text.strip():
            continue

        best_j = -1
        best_sim = 0.0
        for j, mp in enumerate(mod_provs):
            if j in mod_matched or not mp.full_text.strip():
                continue
            sim = _similarity(op.full_text, mp.full_text)
            if sim > best_sim:
                best_sim = sim
                best_j = j

        if best_sim >= content_threshold and best_j >= 0:
            is_move = abs(i - best_j) > 1
            match_type = "move_content" if is_move else "content_match"
            matches.append(ProvisionMatch(i, best_j, match_type, is_move))
            orig_matched.add(i)
            mod_matched.add(best_j)

    # Pass 3: Section-number matching for completely replaced provisions.
    # When a provision is fully rewritten (same section number, very different
    # content), Passes 1 & 2 leave it unmatched, producing a DELETION + ADDITION
    # pair that renders as separate paragraphs in the export.  Matching by
    # identical section number converts the pair to a MODIFICATION so that
    # _apply_inline_redline can render the change inline.
    for i, op in enumerate(orig_provs):
        if i in orig_matched or not op.section_number:
            continue
        for j, mp in enumerate(mod_provs):
            if j in mod_matched or not mp.section_number:
                continue
            if op.section_number == mp.section_number:
                is_move = abs(i - j) > 1
                match_type = "move_heading" if is_move else "heading_match"
                matches.append(ProvisionMatch(i, j, match_type, is_move))
                orig_matched.add(i)
                mod_matched.add(j)
                break

    return matches, orig_matched, mod_matched


# --- Inline character diff ---

def compute_inline_diffs(original: str, modified: str) -> list[InlineDiff]:
    """Compute character-level diffs between two text strings."""
    if original == modified:
        return []

    matcher = SequenceMatcher(None, original, modified, autojunk=False)
    diffs = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        diffs.append(InlineDiff(
            tag=tag,
            original_span=original[i1:i2] if tag in ("delete", "replace") else "",
            modified_span=modified[j1:j2] if tag in ("insert", "replace") else "",
        ))
    return diffs


# --- Main diff function ---

def compare_documents(
    original: ParsedDocument,
    modified: ParsedDocument,
    version_label: str = "Modified",
) -> list[DiffChange]:
    """Compare two parsed documents and return a list of changes.

    This is the main entry point for the diff engine.
    """
    orig_provs = extract_provisions(original.paragraphs)
    mod_provs = extract_provisions(modified.paragraphs)

    matches, orig_matched, mod_matched = match_provisions(orig_provs, mod_provs)
    changes: list[DiffChange] = []

    # Process matched provisions
    for m in matches:
        op = orig_provs[m.orig_idx]
        mp = mod_provs[m.mod_idx]
        section = _section_label(
            mp.section_number or op.section_number,
            mp.heading_text or op.heading_text,
        )

        # Compare headings
        if op.heading_text and mp.heading_text and op.heading_text != mp.heading_text:
            changes.append(DiffChange(
                change_type=ChangeType.MODIFICATION,
                original_text=op.heading_text,
                modified_text=mp.heading_text,
                section_context=section,
                is_move=m.is_move,
                is_heading=True,
                inline_diffs=compute_inline_diffs(op.heading_text, mp.heading_text),
                original_paragraph_id=op.heading.id if op.heading else None,
                modified_paragraph_id=mp.heading.id if mp.heading else None,
            ))

        # Compare body paragraphs within the provision
        orig_body = [p.text for p in op.body]
        mod_body = [p.text for p in mp.body]

        body_matcher = SequenceMatcher(None, orig_body, mod_body, autojunk=False)
        for tag, i1, i2, j1, j2 in body_matcher.get_opcodes():
            if tag == "equal":
                if m.is_move:
                    # Even identical text was moved
                    for k in range(i1, i2):
                        changes.append(DiffChange(
                            change_type=ChangeType.MOVE,
                            original_text=orig_body[k],
                            modified_text=mod_body[k - i1 + j1],
                            section_context=op.body[k].section_number or section,
                            is_move=True,
                            original_paragraph_id=op.body[k].id,
                            modified_paragraph_id=mp.body[k - i1 + j1].id,
                        ))
                continue

            if tag == "delete":
                for k in range(i1, i2):
                    changes.append(DiffChange(
                        change_type=ChangeType.DELETION,
                        original_text=orig_body[k],
                        section_context=op.body[k].section_number or section,
                        original_paragraph_id=op.body[k].id,
                    ))

            elif tag == "insert":
                for k in range(j1, j2):
                    changes.append(DiffChange(
                        change_type=ChangeType.ADDITION,
                        modified_text=mod_body[k],
                        section_context=mp.body[k].section_number or section,
                        modified_paragraph_id=mp.body[k].id,
                    ))

            elif tag == "replace":
                pairs = min(i2 - i1, j2 - j1)
                for k in range(pairs):
                    orig_t = orig_body[i1 + k]
                    mod_t = mod_body[j1 + k]
                    para_section = (
                        op.body[i1 + k].section_number
                        or mp.body[j1 + k].section_number
                        or section
                    )
                    changes.append(DiffChange(
                        change_type=ChangeType.MODIFICATION,
                        original_text=orig_t,
                        modified_text=mod_t,
                        section_context=para_section,
                        is_move=m.is_move,
                        inline_diffs=compute_inline_diffs(orig_t, mod_t),
                        similarity=round(_similarity(orig_t, mod_t), 3),
                        original_paragraph_id=op.body[i1 + k].id,
                        modified_paragraph_id=mp.body[j1 + k].id,
                    ))
                # Remaining unpaired
                for k in range(pairs, i2 - i1):
                    changes.append(DiffChange(
                        change_type=ChangeType.DELETION,
                        original_text=orig_body[i1 + k],
                        section_context=op.body[i1 + k].section_number or section,
                        original_paragraph_id=op.body[i1 + k].id,
                    ))
                for k in range(pairs, j2 - j1):
                    changes.append(DiffChange(
                        change_type=ChangeType.ADDITION,
                        modified_text=mod_body[j1 + k],
                        section_context=mp.body[j1 + k].section_number or section,
                        modified_paragraph_id=mp.body[j1 + k].id,
                    ))

    # Unmatched original provisions = deleted
    for i, op in enumerate(orig_provs):
        if i not in orig_matched and op.full_text.strip():
            changes.append(DiffChange(
                change_type=ChangeType.DELETION,
                original_text=op.full_text,
                section_context=_section_label(op.section_number, op.heading_text),
                original_paragraph_id=op.heading.id if op.heading else (op.body[0].id if op.body else None),
            ))

    # Unmatched modified provisions = added
    for j, mp in enumerate(mod_provs):
        if j not in mod_matched and mp.full_text.strip():
            changes.append(DiffChange(
                change_type=ChangeType.ADDITION,
                modified_text=mp.full_text,
                section_context=_section_label(mp.section_number, mp.heading_text),
                modified_paragraph_id=mp.heading.id if mp.heading else (mp.body[0].id if mp.body else None),
            ))

    # Sort into document section-number order.
    # Numeric contexts (e.g. "3", "10", "12.11") sort before non-numeric heading
    # texts, which fall back to alphabetical order.  Python's sort is stable so
    # changes that share the same section_context keep their relative order.
    def _section_sort_key(c: DiffChange) -> tuple:
        ctx = c.section_context or ""
        if not ctx:
            # No section context = preamble/title; sort before everything else
            return (-1, 0.0, "")
        m = re.match(r"^(\d+(?:\.\d+)*)", ctx)
        if m:
            return (0, float(m.group(1)), ctx)
        return (1, 0.0, ctx)

    changes.sort(key=_section_sort_key)
    return changes
