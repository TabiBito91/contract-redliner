"""Output document generation service (ADR-004: Clone-and-Annotate).

Clones the original DOCX and inserts redline markup:
- Deletions: red text with strikethrough
- Additions: blue text with underline
- AI annotations: Word comments at change locations
- Summary appendix: table at end of document
"""

import copy
from pathlib import Path
from uuid import UUID

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn, nsdecls
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_COLOR_INDEX

from app.models.schemas import (
    AnnotatedChange,
    ChangeType,
    ExportOptions,
    RiskSeverity,
)
from app.services.diff_engine import DiffChange, InlineDiff


# --- Color constants ---
RED = RGBColor(0xCC, 0x00, 0x00)       # Deletions
BLUE = RGBColor(0x00, 0x44, 0xCC)      # Additions
ORANGE = RGBColor(0xFF, 0x88, 0x00)    # Moves
GRAY = RGBColor(0x88, 0x88, 0x88)      # Cosmetic/info

SEVERITY_COLORS = {
    RiskSeverity.CRITICAL: RGBColor(0xCC, 0x00, 0x00),
    RiskSeverity.HIGH: RGBColor(0xFF, 0x66, 0x00),
    RiskSeverity.MEDIUM: RGBColor(0xDD, 0xAA, 0x00),
    RiskSeverity.LOW: RGBColor(0x00, 0x88, 0x00),
    RiskSeverity.INFO: RGBColor(0x00, 0x44, 0xCC),
}


def _add_formatted_run(paragraph, text: str, color: RGBColor,
                       strikethrough: bool = False, underline: bool = False,
                       bold: bool = False):
    """Add a formatted run to a paragraph."""
    run = paragraph.add_run(text)
    run.font.color.rgb = color
    if strikethrough:
        run.font.strike = True
    if underline:
        run.font.underline = True
    if bold:
        run.bold = True
    return run


def _add_comment(doc, paragraph, comment_text: str, author: str = "RedlineAI"):
    """Add a Word comment to a paragraph.

    This uses low-level OOXML manipulation since python-docx doesn't
    natively support comments.
    """
    # Get or create the comments part
    comments_part = None
    for rel in doc.part.rels.values():
        if "comments" in rel.reltype:
            comments_part = rel.target_part
            break

    if comments_part is None:
        # Create a comments part - this is complex OOXML; skip for MVP
        # Comments will be implemented as inline annotations instead
        return

    # For MVP, we'll use a simpler approach: add the comment as
    # a bracketed annotation at the end of the paragraph
    run = paragraph.add_run(f"  [{comment_text}]")
    run.font.size = Pt(8)
    run.font.color.rgb = GRAY
    run.font.italic = True


def _normalize_ws(text: str) -> str:
    """Normalize whitespace for matching."""
    import re
    return re.sub(r"\s+", " ", text).strip()


def _match_para_index(doc_paragraphs, original_text: str) -> int | None:
    """Find the best matching paragraph index in the DOCX by text content."""
    if not original_text:
        return None
    norm_orig = _normalize_ws(original_text)
    if not norm_orig:
        return None

    best_idx = None
    best_ratio = 0.0
    from difflib import SequenceMatcher
    for i, para in enumerate(doc_paragraphs):
        para_text = _normalize_ws(para.text)
        if not para_text:
            continue
        # Quick exact check
        if para_text == norm_orig:
            return i
        # Fuzzy match for minor whitespace/unicode differences
        ratio = SequenceMatcher(None, para_text, norm_orig).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = i

    return best_idx if best_ratio > 0.8 else None


def _clear_paragraph(para):
    """Remove all runs from a paragraph, keeping the paragraph element."""
    for run in para.runs:
        para._element.remove(run._element)
    # Also clear any direct text nodes
    p_elem = para._element
    for child in list(p_elem):
        if child.tag.endswith("}r"):
            p_elem.remove(child)


def _apply_inline_redline(para, original_text: str, modified_text: str):
    """Replace a paragraph's content with inline redline markup."""
    _clear_paragraph(para)

    from difflib import SequenceMatcher
    matcher = SequenceMatcher(None, original_text or "", modified_text or "", autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            para.add_run(original_text[i1:i2])
        elif tag == "delete":
            _add_formatted_run(para, original_text[i1:i2], RED, strikethrough=True)
        elif tag == "insert":
            _add_formatted_run(para, modified_text[j1:j2], BLUE, underline=True)
        elif tag == "replace":
            _add_formatted_run(para, original_text[i1:i2], RED, strikethrough=True)
            _add_formatted_run(para, modified_text[j1:j2], BLUE, underline=True)


def generate_redline_docx(
    original_path: Path,
    annotated_changes: list[AnnotatedChange],
    options: ExportOptions,
    output_path: Path,
) -> Path:
    """Generate a redlined DOCX document.

    Clones the original document and inserts change markup inline.

    Args:
        original_path: Path to the original DOCX file.
        annotated_changes: Changes with optional AI summaries and risk assessments.
        options: Export configuration toggles.
        output_path: Where to save the output DOCX.

    Returns:
        Path to the generated output file.
    """
    doc = Document(str(original_path))

    # Filter changes based on options
    active_changes: list[AnnotatedChange] = []
    for ac in annotated_changes:
        if not ac.change.is_substantive and not options.show_formatting_changes:
            continue
        active_changes.append(ac)

    doc_paragraphs = list(doc.paragraphs)
    used_indices: set[int] = set()

    # Process all changes in a single pass in document order.
    # Additions are inserted immediately after the last matched paragraph
    # (their natural position) rather than appended to the end.
    last_anchor_elem = None  # XML element after which to insert additions

    for ac in active_changes:
        ct = ac.change.change_type

        if ct == ChangeType.ADDITION:
            # Insert a new paragraph after the last anchor element
            new_p = OxmlElement("w:p")
            if last_anchor_elem is not None:
                last_anchor_elem.addnext(new_p)
            else:
                # No anchor yet — fall back to appending
                doc.element.body.append(new_p)

            from docx.text.paragraph import Paragraph as DocxParagraph
            para = DocxParagraph(new_p, doc._body)
            _add_formatted_run(para, "[ADDED] ", BLUE, bold=True)
            _add_formatted_run(para, ac.change.modified_text or "", BLUE, underline=True)
            if options.include_ai_summaries and ac.ai_summary:
                _add_comment(doc, para, ac.ai_summary.summary)
            last_anchor_elem = new_p

        elif ct == ChangeType.DELETION:
            idx = _match_para_index(doc_paragraphs, ac.change.original_text)
            if idx is not None and idx not in used_indices:
                used_indices.add(idx)
                original_text = doc_paragraphs[idx].text
                _clear_paragraph(doc_paragraphs[idx])
                _add_formatted_run(doc_paragraphs[idx], original_text, RED, strikethrough=True)
                if options.include_ai_summaries and ac.ai_summary:
                    _add_comment(doc, doc_paragraphs[idx], ac.ai_summary.summary)
                last_anchor_elem = doc_paragraphs[idx]._element

        else:
            # MODIFICATION, MOVE, FORMAT_ONLY
            idx = _match_para_index(doc_paragraphs, ac.change.original_text)
            if idx is not None and idx not in used_indices:
                used_indices.add(idx)
                _apply_inline_redline(
                    doc_paragraphs[idx],
                    ac.change.original_text or "",
                    ac.change.modified_text or "",
                )
                if options.include_ai_summaries and ac.ai_summary:
                    _add_comment(doc, doc_paragraphs[idx], ac.ai_summary.summary)
                last_anchor_elem = doc_paragraphs[idx]._element

    # Insert disclaimer header at top
    disclaimer_para = doc.add_paragraph()
    disclaimer_para.paragraph_format.space_after = Pt(12)
    _add_formatted_run(
        disclaimer_para,
        "REDLINE COMPARISON - Generated by RedlineAI | ",
        GRAY, bold=True,
    )
    _add_formatted_run(
        disclaimer_para,
        "AI assessments do not constitute legal advice.",
        GRAY,
    )
    doc.element.body.insert(0, disclaimer_para._element)

    # Add legend
    legend_para = doc.add_paragraph()
    _add_formatted_run(legend_para, "Deleted text", RED, strikethrough=True)
    _add_formatted_run(legend_para, "  |  ", GRAY)
    _add_formatted_run(legend_para, "Added text", BLUE, underline=True)
    _add_formatted_run(legend_para, "  |  ", GRAY)
    _add_formatted_run(legend_para, "Moved text", ORANGE, underline=True)
    doc.element.body.insert(1, legend_para._element)

    # Add summary appendix if enabled
    if options.include_summary_appendix:
        _add_summary_appendix(doc, annotated_changes, options)

    doc.save(str(output_path))
    return output_path


def _add_summary_appendix(
    doc: Document,
    annotated_changes: list[AnnotatedChange],
    options: ExportOptions,
):
    """Append a summary table at the end of the document."""
    doc.add_page_break()
    doc.add_heading("Change Summary", level=1)

    # Disclaimer
    disclaimer = doc.add_paragraph()
    _add_formatted_run(
        disclaimer,
        "AI-generated summaries and risk assessments. This does not constitute legal advice.",
        GRAY, bold=True,
    )
    disclaimer.paragraph_format.space_after = Pt(12)

    # Determine columns
    columns = ["#", "Type", "Section"]
    if options.include_ai_summaries:
        columns.append("Summary")
    if options.include_risk_assessments:
        columns.extend(["Risk", "Recommendation"])

    # Create table
    table = doc.add_table(rows=1, cols=len(columns))
    table.style = "Table Grid"

    # Header row
    for i, col_name in enumerate(columns):
        cell = table.rows[0].cells[i]
        cell.text = col_name
        for run in cell.paragraphs[0].runs:
            run.bold = True

    # Data rows
    substantive_idx = 0
    for ac in annotated_changes:
        change = ac.change
        if not change.is_substantive and not options.show_formatting_changes:
            continue

        substantive_idx += 1
        row = table.add_row()
        col = 0

        row.cells[col].text = str(substantive_idx)
        col += 1

        row.cells[col].text = change.change_type.value.replace("_", " ").title()
        col += 1

        row.cells[col].text = change.section_context or ""
        col += 1

        if options.include_ai_summaries:
            summary_text = ac.ai_summary.summary if ac.ai_summary else ""
            row.cells[col].text = summary_text
            col += 1

        if options.include_risk_assessments:
            if ac.risk_assessment:
                severity = ac.risk_assessment.severity.value.upper()
                row.cells[col].text = severity
                # Color the risk cell
                para = row.cells[col].paragraphs[0]
                if para.runs:
                    color = SEVERITY_COLORS.get(ac.risk_assessment.severity, GRAY)
                    para.runs[0].font.color.rgb = color
                    para.runs[0].bold = True
                col += 1

                row.cells[col].text = ac.risk_assessment.recommendation
                col += 1
            else:
                row.cells[col].text = ""
                col += 1
                row.cells[col].text = ""
                col += 1


def generate_inline_redline_paragraph(
    original_text: str,
    modified_text: str,
    inline_diffs: list[InlineDiff],
) -> list[tuple[str, str]]:
    """Generate a sequence of (text, format) tuples for inline redline display.

    Returns list of tuples: (text_content, format_type)
    where format_type is one of: "normal", "deletion", "addition"
    """
    if not original_text and not modified_text:
        return [("No changes detected", "normal")]

    if not original_text:
        return [(modified_text, "addition")]
    if not modified_text:
        return [(original_text, "deletion")]

    # Reconstruct the full inline view by diffing the texts directly
    from difflib import SequenceMatcher
    matcher = SequenceMatcher(None, original_text, modified_text, autojunk=False)

    result = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result.append((original_text[i1:i2], "normal"))
        elif tag == "delete":
            result.append((original_text[i1:i2], "deletion"))
        elif tag == "insert":
            result.append((modified_text[j1:j2], "addition"))
        elif tag == "replace":
            result.append((original_text[i1:i2], "deletion"))
            result.append((modified_text[j1:j2], "addition"))

    return result
