# ADR-002: Diff Engine Strategy

## Status: Accepted

## Context

The comparison engine is the core of RedlineAI. It must detect additions, deletions, modifications, moves/reordering, and formatting-only changes between legal documents. Key challenges include:
- Legal documents frequently have clauses reordered during negotiation
- Section numbers change when clauses are moved, so section-number matching alone is unreliable
- The engine must provide provision-level matching AND character-level diffs within matched provisions
- Must handle documents up to 500 pages within 10-second performance target (NFR-01)

## Options Considered

### Option A: Paragraph-Level SequenceMatcher (Classic Diff)
Split documents into paragraphs, use Python's `difflib.SequenceMatcher` to align them sequentially, then pair up replacements by position.

| Dimension | Assessment |
|---|---|
| Accuracy on legal docs | 36% (4/11 known changes detected correctly) |
| Move detection | None - moves appear as delete + add pairs |
| Inline diffs | No - works at paragraph granularity only |
| Performance | Fast (~384ms for 20-paragraph NDA) |
| Complexity | Low |

### Option B: Hybrid Structural Matching + Character Diff
Parse documents into provisions (heading + body paragraphs). Match provisions using: (1) heading content similarity (strips section numbers), (2) full-text similarity for remaining, (3) position delta for move detection. Within matched pairs, run character-level diff.

| Dimension | Assessment |
|---|---|
| Accuracy on legal docs | 100% (11/11 known changes detected correctly) |
| Move detection | Yes - detects Governing Law moved from Sec 9 to Sec 5 |
| Inline diffs | Yes - character-level diffs show exact words changed |
| Performance | Fast (~363ms for 20-paragraph NDA) |
| Complexity | Medium |

### Option C: AST/XML Structure Diff
Parse DOCX XML structure at the OOXML node level, diff the XML tree.

| Dimension | Assessment |
|---|---|
| Accuracy | High fidelity for formatting changes, but tightly coupled to DOCX format |
| Move detection | Possible but complex (tree-edit-distance algorithms) |
| Inline diffs | Yes, at the XML run level |
| Performance | Slower (XML tree comparison is O(n^3) naive, O(n^2) optimized) |
| Complexity | Very high - requires deep OOXML knowledge |
| Extensibility | Poor - cannot reuse for PDF (Phase 2) |

### Option D: LLM-Assisted Diff
Use an LLM to semantically match and compare provisions.

| Dimension | Assessment |
|---|---|
| Accuracy | Potentially highest semantic understanding |
| Move detection | Excellent (LLM understands clause meaning) |
| Inline diffs | Depends on prompt design |
| Performance | Very slow (API calls for each provision pair), expensive |
| Complexity | Medium code, but non-deterministic results |
| Cost | $0.50-5.00+ per comparison depending on document length |

## Prototype Results

Both Option A and Option B were prototyped and tested against a sample NDA contract with 11 known changes including: modified definitions, weakened obligations, moved sections, deleted provisions, added provisions, and changed monetary values.

```
Metric                                      Proto A    Proto B
--------------------------------------------------------------
Execution time (ms)                           384        363
Total changes reported                         21         14
Known changes detected (/11)                    4         11
Accuracy %                                    36%       100%
Moves correctly detected                        0          1
Has inline (char-level) diffs                  No        Yes
Section-aware matching                         No        Yes
```

Prototype B correctly identified all 11 changes including:
- Moved Governing Law section (Sec 9 -> Sec 5) via heading-content matching
- Deleted Remedies section (unmatched provision)
- Added Non-Solicitation section (unmatched provision)
- All text modifications with character-level inline diffs

## Decision: Option B - Hybrid Structural Matching + Character Diff

## Rationale

1. **100% accuracy** on the test corpus vs 36% for the next-best prototyped approach.
2. **Move detection** is critical for legal documents where clause reordering is common.
3. **Heading-content-first matching** (stripping section numbers) solves the renumbering problem that broke section-number-based matching.
4. **Character-level inline diffs** enable the red-strikethrough / blue-underline output formatting required by the PRD.
5. **Format-agnostic** - works on the `ParsedDocument` intermediate representation, so Phase 2 PDF support only needs a new parser, not a new diff engine (NFR-09).
6. **Performance is comparable** to the simpler approach (~363ms vs ~384ms) since the structural matching avoids unnecessary character comparisons on unrelated paragraphs.

## Consequences

- The diff engine operates on `ParsedDocument` objects (the intermediate representation from ADR-001's parser abstraction)
- Matching strategy: heading content similarity (>0.85) -> full-text similarity (>0.5) -> position-based move detection
- Each change includes inline character-level diffs for precise UI rendering
- Move detection flags provisions where match position differs significantly from original position
- Whole-provision deletions and additions are cleanly separated from within-provision modifications
- LLM-assisted matching (Option D) may be added as an enhancement for ambiguous cases in a later phase, but is not needed for the core engine
