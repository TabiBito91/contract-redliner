# ADR-004: Output Document Generation Strategy

## Status: Accepted

## Context

The system must generate formatted output documents with:
- Deletions in red text with strikethrough (PRD 13.1)
- Additions in blue text with underline (PRD 13.1)
- Preserved original formatting (fonts, styles, headings)
- AI annotations as Word comments (optional)
- Summary appendix table listing all changes, summaries, and risk assessments
- Both DOCX and PDF output formats from the same pipeline (PRD 13.2)
- Export option toggles (include/exclude summaries, risk, formatting changes)

The output must open correctly in Microsoft Word, Google Docs, and LibreOffice (AC-11).

## Options Considered

### Option A: python-docx with Manual Run-Level Formatting

Build the output DOCX programmatically using python-docx, inserting red-strikethrough runs for deletions and blue-underline runs for additions within each paragraph.

| Dimension | Assessment |
|---|---|
| Formatting fidelity | High - full control over run-level formatting (color, strikethrough, underline) |
| Word compatibility | Excellent - produces standard OOXML |
| Google Docs compat | Good - basic formatting preserved |
| PDF generation | Via python-docx -> then convert with LibreOffice CLI or similar |
| AI annotations | Can add Word comments via OOXML manipulation |
| Implementation effort | Medium - need to reconstruct paragraphs with mixed formatting runs |
| Original formatting | Must clone styles from the original document |

### Option B: OOXML Tracked Changes (Native Revisions)

Generate actual Word tracked changes (revision markup) in the DOCX XML, so users can accept/reject individual changes in Word.

| Dimension | Assessment |
|---|---|
| Formatting fidelity | Highest - identical to Word's native Compare Documents |
| Word compatibility | Best - users can accept/reject changes natively |
| Google Docs compat | Limited - Google Docs has partial tracked-changes support |
| PDF generation | Complex - need to "accept all" or render revisions for PDF |
| AI annotations | Comments work alongside tracked changes |
| Implementation effort | Very High - OOXML revision markup is extremely complex (w:ins, w:del, revision IDs, author tracking) |
| Original formatting | Preserved via cloning the original document |

### Option C: HTML-First Pipeline (HTML -> DOCX/PDF)

Generate an HTML representation of the redline first, then convert to DOCX (via python-docx or Pandoc) and PDF (via WeasyPrint or Playwright).

| Dimension | Assessment |
|---|---|
| Formatting fidelity | Medium - HTML-to-DOCX conversion loses some formatting nuance |
| Word compatibility | Moderate - converted DOCX may have style issues |
| Google Docs compat | Good if HTML is clean |
| PDF generation | Excellent - HTML renders cleanly to PDF via WeasyPrint |
| AI annotations | Easy in HTML (tooltips, sidebars), harder to convert to Word comments |
| Implementation effort | Medium - but adds conversion step complexity and potential fidelity loss |
| Original formatting | Difficult to preserve original DOCX styles through HTML round-trip |

### Option D: Clone-and-Annotate (Modify Original DOCX)

Clone the original DOCX file, then walk through it and insert formatted change markup inline at the exact paragraph/run positions identified by the diff engine.

| Dimension | Assessment |
|---|---|
| Formatting fidelity | Highest - original document formatting perfectly preserved |
| Word compatibility | Excellent - it IS a real Word document with added markup |
| Google Docs compat | Good |
| PDF generation | Via LibreOffice CLI headless conversion |
| AI annotations | Insert Word comments at change locations |
| Implementation effort | Medium-High - need to map diff positions back to DOCX XML nodes |
| Original formatting | Perfect - the original document IS the base |

## Comparison Matrix

| Criterion (Weight) | A: python-docx Manual | B: OOXML Tracked | C: HTML Pipeline | D: Clone & Annotate |
|---|---|---|---|---|
| Formatting fidelity (25%) | 8/10 | 10/10 | 5/10 | 10/10 |
| Word/GDocs/Libre compat (20%) | 8/10 | 7/10 | 6/10 | 9/10 |
| PDF generation ease (15%) | 6/10 | 4/10 | 9/10 | 6/10 |
| AI annotation support (15%) | 7/10 | 8/10 | 5/10 | 8/10 |
| Implementation effort (15%) | 7/10 | 3/10 | 6/10 | 6/10 |
| Preserves original styles (10%) | 5/10 | 8/10 | 3/10 | 10/10 |
| **Weighted Score** | **7.15** | **6.70** | **5.65** | **8.15** |

## Decision: Option D - Clone-and-Annotate

## Rationale

1. **Perfect original formatting preservation.** By cloning the original DOCX and inserting markup, all fonts, styles, headings, margins, and page layout are maintained exactly. This is critical for legal documents where formatting matters.

2. **Highest compatibility.** The output is a genuine Word document with inline formatting additions, not a programmatically-constructed one. It opens correctly in Word, Google Docs, and LibreOffice.

3. **AI annotations via Word comments.** python-docx supports adding comments to specific paragraph ranges, enabling inline AI summaries and risk badges directly in the document.

4. **PDF generation via LibreOffice headless.** `libreoffice --headless --convert-to pdf` is reliable and preserves the DOCX formatting faithfully. Alternative: use python-docx for DOCX and WeasyPrint for a separate HTML-based PDF path.

5. **Acceptable implementation effort.** The diff engine already tracks paragraph IDs that map back to the parsed document structure. The output generator needs to walk the cloned DOCX paragraphs and insert colored/formatted runs at the right positions.

6. **Option B (tracked changes) rejected** despite its appeal because OOXML revision markup is extraordinarily complex (requires managing revision IDs, author references, date stamps, and nested revision containers), and Google Docs support for tracked changes is poor. The PRD's visual red/blue markup achieves the same user goal with much less complexity.

## Consequences

- Output generation clones the original DOCX via python-docx
- Change markup is inserted as colored/formatted runs (red+strikethrough for deletions, blue+underline for additions)
- AI annotations added as Word comments linked to change paragraphs
- Summary appendix table appended at the end of the document
- PDF generated via LibreOffice headless CLI (with fallback to WeasyPrint HTML path)
- Export toggles (include/exclude AI, risk, formatting changes) control what gets inserted
- The output service accepts `AnnotatedChange[]` + the original DOCX path and produces the output file
