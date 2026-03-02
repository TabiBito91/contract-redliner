# ADR-006: Multi-Document Comparison Data Model

## Status: Accepted

## Context

The system must support comparing 3+ document versions against a designated original (PRD Section 12). The data model must support three comparison modes:
1. **Original to Each Version**: Each version compared independently against the original
2. **Sequential**: Each version compared against the immediately preceding version
3. **Cumulative**: All changes from all versions overlaid on the original

Each change must be attributed to the version that introduced it (PRD 12.3). The UI needs to efficiently query changes by version, by section, and by risk severity.

## Options Considered

### Option A: Pairwise Diff Storage

Store each pairwise comparison (Original↔V2, Original↔V3, V2↔V3, etc.) as an independent result set. The comparison mode determines which pairs to compute and display.

```
ComparisonSession
  ├── PairwiseDiff(Original, V2) -> [Change, Change, ...]
  ├── PairwiseDiff(Original, V3) -> [Change, Change, ...]
  └── PairwiseDiff(V2, V3) -> [Change, Change, ...]  (for sequential mode)
```

| Dimension | Assessment |
|---|---|
| Storage efficiency | Low-Medium - some changes duplicated across pairs |
| Query complexity | Low - each view maps directly to one PairwiseDiff |
| Mode switching | Fast - all pairs precomputed, just select the right one |
| UI rendering | Simple - each tab loads one PairwiseDiff result |
| Implementation | Simple - reuse the 2-document diff engine for each pair |
| Change attribution | Easy - each change is tagged with its pair (source version) |

### Option B: Unified Change Graph (DAG)

Build a directed acyclic graph where nodes are provisions and edges represent changes. Each edge carries the version that introduced it. A provision can have multiple incoming edges from different versions.

```
ProvisionNode("Section 8.2")
  ├── Edge(V1->V2): "Cap changed from $5M to $3M"
  └── Edge(V2->V3): "Cap changed from $3M to $2M"
```

| Dimension | Assessment |
|---|---|
| Storage efficiency | High - no duplication, each change stored once |
| Query complexity | High - need graph traversal for different view modes |
| Mode switching | Medium - requires different graph traversal strategies |
| UI rendering | Complex - must flatten graph to linear view for display |
| Implementation | High - graph data structure, traversal algorithms |
| Change attribution | Built-in - edges carry version info |

### Option C: Version-Control-Inspired Model (Linear Chain)

Model the document versions as a linear commit chain (like git). Each version stores its diff from the previous version. Views are computed by replaying or combining diffs.

```
V1 (Original) --diff--> V2 --diff--> V3 --diff--> V4
                                        \
                                         cumulative = merge(diff1, diff2, diff3)
```

| Dimension | Assessment |
|---|---|
| Storage efficiency | High - only sequential diffs stored |
| Query complexity | Medium - "original to V3" requires merging diffs V1→V2 and V2→V3 |
| Mode switching | Medium - sequential is direct, original-to-each requires merge |
| UI rendering | Medium - merged diffs may have conflicts or ordering issues |
| Implementation | Medium-High - diff merging is non-trivial |
| Change attribution | Good - each diff is tagged with its version |

### Option D: Precomputed View Store

Precompute all possible views (original-to-each, sequential, cumulative) at comparison time and store them as flat lists. Trade storage for query speed.

```
ComparisonSession
  ├── views/
  │   ├── original_to_v2: [AnnotatedChange, ...]
  │   ├── original_to_v3: [AnnotatedChange, ...]
  │   ├── v2_to_v3: [AnnotatedChange, ...]
  │   └── cumulative: [AnnotatedChange, ...]  (merged with version tags)
```

| Dimension | Assessment |
|---|---|
| Storage efficiency | Lowest - all views precomputed and stored |
| Query complexity | Lowest - direct lookup by view key |
| Mode switching | Instant - all views ready |
| UI rendering | Simplest - flat list per view |
| Implementation | Simple - run diff engine per pair, plus a merge step for cumulative |
| Change attribution | Direct - each change carries version_source |

## Comparison Matrix

| Criterion (Weight) | A: Pairwise | B: Graph | C: Linear Chain | D: Precomputed |
|---|---|---|---|---|
| Query speed (25%) | 8/10 | 5/10 | 6/10 | 10/10 |
| Implementation simplicity (25%) | 9/10 | 4/10 | 6/10 | 8/10 |
| Storage efficiency (15%) | 6/10 | 9/10 | 8/10 | 4/10 |
| Mode switching (15%) | 8/10 | 6/10 | 6/10 | 10/10 |
| UI integration ease (10%) | 9/10 | 5/10 | 7/10 | 10/10 |
| Change attribution (10%) | 8/10 | 9/10 | 8/10 | 9/10 |
| **Weighted Score** | **8.10** | **5.65** | **6.45** | **8.70** |

## Decision: Option D - Precomputed View Store

With Option A (Pairwise Diff Storage) as the underlying computation strategy.

## Rationale

1. **Fastest mode switching.** Users need to flip between "Original vs V2", "Original vs V3", and "Cumulative" views instantly. Precomputing all views eliminates any computation on view switch.

2. **Simplest UI integration.** Each view is a flat list of `AnnotatedChange` objects. The React frontend just renders the list for the selected view. No graph traversal or diff merging in the frontend.

3. **Reuses the existing diff engine.** The 2-document diff engine (ADR-002) runs once per document pair. For N documents, we run N-1 comparisons (original-to-each) plus N-2 (sequential), then merge for cumulative. All computation happens server-side at comparison time.

4. **Storage cost is acceptable.** For 10 documents (max per PRD), we precompute at most ~18 views. Each view is a list of changes (typically 20-100 per pair). For in-memory MVP this is negligible; for persistent storage it's a few MB at most.

5. **Change attribution is direct.** Each `AnnotatedChange` carries a `version_source` field identifying which version introduced it. The cumulative view merges changes from all versions, each tagged with their source.

## Data Model

```python
class ComparisonSession:
    id: UUID
    documents: list[DocumentInfo]       # ordered: [Original, V2, V3, ...]
    original_document_id: UUID
    comparison_mode: ComparisonMode     # user's currently selected mode
    reviewing_party: ReviewingParty
    status: SessionStatus

class ComparisonViewKey:
    """Identifies a specific precomputed view."""
    mode: str                           # "original_to_each", "sequential", "cumulative"
    source_version: str | None          # e.g., "V2", "V3" (None for cumulative)

class PrecomputedView:
    """A precomputed comparison result for one view."""
    key: ComparisonViewKey
    changes: list[AnnotatedChange]
    total_changes: int
    risk_summary: dict[RiskSeverity, int]

class SessionResult:
    """All precomputed views for a session."""
    session_id: UUID
    views: dict[str, PrecomputedView]   # keyed by view identifier
```

## Consequences

- At comparison time, the backend computes all pairwise diffs and stores them as `PrecomputedView` objects
- The cumulative view is computed by merging all original-to-each diffs, deduplicating, and tagging version sources
- Mode switching in the UI is a simple view key change (no re-computation)
- The API exposes `GET /api/comparison/sessions/{id}/views/{view_key}` for direct view access
- Memory cost for 10-document session: ~18 views x ~100 changes x ~1KB each = ~1.8MB (acceptable for MVP)
- For persistence (post-MVP), views can be serialized to JSON in SQLite/PostgreSQL
