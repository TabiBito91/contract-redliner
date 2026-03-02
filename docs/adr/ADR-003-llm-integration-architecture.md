# ADR-003: LLM Integration Architecture

## Status: Accepted

## Context

The AI layer powers two core features:
1. **Change Summarization** - Plain-English summaries for each detected change (PRD 11.1)
2. **Risk Assessment** - Party-aware risk analysis with severity, explanation, recommendation, and confidence (PRD 14.2)

Requirements:
- NFR-02: AI summary generation shall complete within 30 seconds of diff completion
- Must handle ~50 changes for a typical 30-page contract
- Risk assessments must shift perspective based on reviewing party role
- Must include confidence scores (0-100)
- Cost must be reasonable for per-comparison use

This ADR covers four sub-decisions: LLM selection, prompt strategy, cost/performance management, and pipeline placement.

## LLM Selection

| Model | Input $/M | Output $/M | Quality (Legal) | Speed | Structured Output |
|---|---|---|---|---|---|
| Claude Sonnet 4.5 | $3.00 | $15.00 | Excellent | Fast | Excellent (tool_use) |
| Claude Haiku 4.5 | $1.00 | $5.00 | Good | Very fast | Excellent (tool_use) |
| GPT-4o | $2.50 | $10.00 | Excellent | Fast | Good (json_mode) |
| GPT-4o-mini | $0.15 | $0.60 | Moderate | Very fast | Good |
| Local (Llama 3.x) | Free | Free | Poor-Moderate | Slow (no GPU) | Poor |

**Selected: Claude Sonnet 4.5** as primary, **Claude Haiku 4.5** as fast/cheap fallback.

Rationale: Claude excels at legal document analysis, provides reliable structured output via tool_use, and the Anthropic SDK is already a project dependency. Haiku 4.5 provides a 70% cost reduction for bulk summarization while maintaining good quality.

## Options Considered: Prompt Strategy

### Option A: Per-Change Prompting (1 call per change)

Each change sent individually with system prompt + change context.

- **Calls:** ~50 for a 30-page contract
- **Input tokens:** 50 x ~900 = 45,000
- **Output tokens:** 50 x ~200 = 10,000
- **Cost (Sonnet):** $0.135 + $0.150 = **$0.285**
- **Cost (Haiku):** $0.045 + $0.050 = **$0.095**
- **Latency:** ~100s sequential, ~10-15s parallel (rate-limited)
- **Pros:** Simple, each change gets full attention, easy to parallelize
- **Cons:** System prompt repeated 50x (wasteful), no cross-change context (can't detect cascading effects), high latency

### Option B: Section-Batched Prompting (1 call per section group)

Group changes by section and send batches of 5-10 changes per call.

- **Calls:** ~7 for a 30-page contract
- **Input tokens:** 7 x ~4,500 = 31,500
- **Output tokens:** 7 x ~1,000 = 7,000
- **Cost (Sonnet):** $0.095 + $0.105 = **$0.200**
- **Cost (Haiku):** $0.032 + $0.035 = **$0.067**
- **Latency:** ~21s sequential, ~5s parallel
- **Pros:** Better context within sections, fewer calls, can detect related changes within a section
- **Cons:** Doesn't capture cross-section relationships (e.g., definition change cascading to multiple clauses)

### Option C: Single-Pass Full-Context Prompting

Send ALL changes in one prompt. The LLM sees the full picture and generates summaries + risk assessments for every change at once.

- **Calls:** 1 (or 2 if the response is very long)
- **Input tokens:** ~20,000 (system prompt + all changes with context)
- **Output tokens:** ~8,000 (structured output for all changes)
- **Cost (Sonnet):** $0.060 + $0.120 = **$0.180**
- **Cost (Haiku):** $0.020 + $0.040 = **$0.060**
- **Latency:** ~5-8s (single call, streaming)
- **Pros:** Full cross-document context, can detect cascading effects (e.g., redefined term used in 5 clauses), lowest latency, cheapest via prompt caching
- **Cons:** Long output may hit token limits for very large documents (200+ changes), output quality may degrade at the tail end of very long responses

### Option D: On-Demand Lazy Evaluation

Don't call LLM during comparison. Generate summaries/risk on-demand when user clicks a change.

- **Calls:** 0 upfront, ~1 per user interaction
- **Cost per click (Sonnet):** ~$0.006
- **Latency:** ~2s per click
- **Pros:** Zero upfront cost, only pay for what's viewed
- **Cons:** Violates NFR-02 (summaries within 30s of diff), poor UX (user waits on every click), no summary dashboard, no export with AI annotations

## Comparison Matrix

| Criterion (Weight) | A: Per-Change | B: Batched | C: Single-Pass | D: On-Demand |
|---|---|---|---|---|
| Quality (cross-change context) (25%) | 5/10 | 7/10 | 10/10 | 5/10 |
| Latency (25%) | 3/10 | 7/10 | 9/10 | 2/10 |
| Cost efficiency (20%) | 5/10 | 7/10 | 9/10 | 10/10 |
| Implementation simplicity (15%) | 9/10 | 6/10 | 7/10 | 8/10 |
| NFR-02 compliance (15%) | 6/10 | 8/10 | 10/10 | 0/10 |
| **Weighted Score** | **5.30** | **7.00** | **9.00** | **4.70** |

## Decision: Option C - Single-Pass Full-Context Prompting

### With the following architecture:

**Primary Model:** Claude Sonnet 4.5 for summaries + risk analysis
**Fallback Model:** Claude Haiku 4.5 for cost-sensitive or high-volume scenarios
**Prompt Strategy:** Single-pass full-context with structured JSON output
**Pipeline Placement:** Async post-processing (fires immediately after diff completes, streams results to frontend via WebSocket)
**Caching:** Prompt caching on the system prompt (90% savings on repeated calls with same instructions)

### Cost Estimate (30-page contract, ~50 changes)

| Scenario | Input Tokens | Output Tokens | Cost |
|---|---|---|---|
| Sonnet (no cache) | ~20,000 | ~8,000 | $0.18 |
| Sonnet (cached system prompt) | ~20,000 | ~8,000 | ~$0.13 |
| Haiku (no cache) | ~20,000 | ~8,000 | $0.06 |
| Haiku (cached system prompt) | ~20,000 | ~8,000 | ~$0.04 |

### Overflow Strategy

For very large documents (200+ changes), split into batches of ~80 changes each, with a shared preamble containing document type and reviewing party context. Each batch gets full summaries; a final consolidation call identifies cross-batch relationships.

## Rationale

1. **Full context is critical for legal analysis.** A definition change in Section 1 may cascade to 5 other clauses. Only Option C gives the LLM visibility into all changes simultaneously to detect these relationships (PRD 11.1: "Groups related changes where applicable").

2. **Single call is fastest and cheapest.** One API call with streaming delivers results in 5-8s, well within the 30-second NFR-02 requirement. Prompt caching brings cost to ~$0.13 per comparison with Sonnet.

3. **Structured output via tool_use** ensures reliable JSON parsing. No regex extraction or fragile output parsing needed.

4. **Async post-processing** means the diff results display immediately while AI analysis streams in. The UI can show a "generating summaries..." indicator that progressively fills in as results arrive.

## Consequences

- The AI service accepts a full list of `DiffChange` objects and the reviewing party role
- Returns structured `AISummary` + `RiskAssessment` for each change
- Uses Anthropic SDK with `tool_use` for structured output
- Streams partial results via WebSocket to the frontend as they're generated
- Prompt caching enabled via `cache_control` on the system prompt
- Fallback to Haiku if Sonnet rate-limited or user selects "fast mode"
- Environment variable `ANTHROPIC_API_KEY` required; graceful degradation (diff works without AI) if not set
