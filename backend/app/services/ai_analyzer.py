"""AI-powered change summarization and risk analysis service (ADR-003).

Uses Claude API with single-pass full-context prompting.
Sends all changes in one call for cross-change context awareness.
"""

import json
import logging
from uuid import UUID

from anthropic import Anthropic, APIError

from app.core.config import settings
from app.models.schemas import (
    AISummary,
    AnnotatedChange,
    Change,
    RiskAssessment,
    ReviewingParty,
    RiskSeverity,
)
from app.services.diff_engine import DiffChange

logger = logging.getLogger(__name__)

# --- Prompt Templates ---

SYSTEM_PROMPT = """You are a legal document analysis AI specializing in contract redline review.
You analyze changes between document versions and provide:
1. Plain-English summaries understandable by non-lawyers
2. Risk assessments from the perspective of a specific reviewing party

IMPORTANT RULES:
- Summaries must describe WHAT changed in plain language (e.g., "The indemnification cap was reduced from $5M to $2M")
- Identify the TYPE of change (scope narrowing, liability shift, timeline modification, definition change, etc.)
- Flag whether each change is substantive or cosmetic/clerical
- Group related changes and note cascading effects (e.g., if a defined term is modified, note which other clauses are affected)
- Risk assessments must be framed from the specified reviewing party's perspective
- Risk severity must be one of: critical, high, medium, low, info
- Confidence scores (0-100) should reflect how certain you are about the risk assessment
- Recommendations must be actionable and specific, not generic boilerplate

DISCLAIMER: All assessments are AI-generated and do not constitute legal advice."""

REVIEWING_PARTY_CONTEXT = {
    ReviewingParty.ORIGINAL_DRAFTER: (
        "You are reviewing from the perspective of the ORIGINAL DRAFTER - the party that authored "
        "the original document. Changes represent deviations from your intended terms. Frame risks "
        "in terms of what protections you are losing or what obligations are being added."
    ),
    ReviewingParty.COUNTERPARTY: (
        "You are reviewing from the perspective of the COUNTERPARTY - the party that made the "
        "modifications. Changes represent your negotiation positions. Frame risks in terms of "
        "whether the changes adequately protect your interests."
    ),
    ReviewingParty.NEUTRAL: (
        "You are reviewing from a NEUTRAL perspective - an objective third-party reviewer. "
        "Frame risks in terms of materiality, enforceability, and balance between the parties."
    ),
}


def _build_changes_context(changes: list[DiffChange]) -> str:
    """Format changes into a structured context string for the LLM."""
    parts = []
    for i, c in enumerate(changes):
        entry = f"CHANGE {i+1}:\n"
        entry += f"  Type: {c.change_type.value}\n"
        entry += f"  Section: {c.section_context or 'Unknown'}\n"
        entry += f"  Is Move: {c.is_move}\n"

        if c.original_text:
            entry += f"  Original Text: {c.original_text}\n"
        if c.modified_text:
            entry += f"  Modified Text: {c.modified_text}\n"

        if c.inline_diffs:
            diff_parts = []
            for d in c.inline_diffs:
                if d.original_span:
                    diff_parts.append(f"-[{d.original_span}]")
                if d.modified_span:
                    diff_parts.append(f"+[{d.modified_span}]")
            entry += f"  Inline Diffs: {' '.join(diff_parts)}\n"

        parts.append(entry)

    return "\n".join(parts)


# Tool schema for structured output
ANALYSIS_TOOL = {
    "name": "submit_analysis",
    "description": "Submit the complete analysis of all document changes.",
    "input_schema": {
        "type": "object",
        "properties": {
            "changes": {
                "type": "array",
                "description": "Analysis for each change, in the same order as provided.",
                "items": {
                    "type": "object",
                    "properties": {
                        "change_index": {
                            "type": "integer",
                            "description": "The 1-based index of the change being analyzed.",
                        },
                        "summary": {
                            "type": "string",
                            "description": "Plain-English summary of what changed (1-2 sentences).",
                        },
                        "change_category": {
                            "type": "string",
                            "description": "Category of change (e.g., 'scope narrowing', 'liability shift', 'timeline modification', 'definition change', 'new obligation', 'removed protection', 'cosmetic').",
                        },
                        "is_substantive": {
                            "type": "boolean",
                            "description": "Whether the change is substantive (true) or cosmetic/clerical (false).",
                        },
                        "related_change_indices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Indices of other changes that are related to or affected by this change.",
                        },
                        "risk_severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low", "info"],
                            "description": "Risk severity level.",
                        },
                        "risk_explanation": {
                            "type": "string",
                            "description": "2-4 sentence explanation of the risk from the reviewing party's perspective.",
                        },
                        "recommendation": {
                            "type": "string",
                            "description": "Recommended action (e.g., 'Accept as-is', 'Push back - request reinstatement of original cap').",
                        },
                        "confidence": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Confidence score for the risk assessment (0-100).",
                        },
                    },
                    "required": [
                        "change_index",
                        "summary",
                        "change_category",
                        "is_substantive",
                        "risk_severity",
                        "risk_explanation",
                        "recommendation",
                        "confidence",
                    ],
                },
            },
        },
        "required": ["changes"],
    },
}


def _get_client() -> Anthropic | None:
    """Get Anthropic client, or None if API key not configured."""
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set. AI analysis disabled.")
        return None
    return Anthropic(api_key=settings.anthropic_api_key)


async def analyze_changes(
    changes: list[DiffChange],
    reviewing_party: ReviewingParty,
    change_ids: list[UUID] | None = None,
    model: str | None = None,
) -> list[dict]:
    """Analyze all changes using a single LLM call with full context.

    Args:
        changes: List of DiffChange objects from the diff engine.
        reviewing_party: The perspective to use for risk assessment.
        change_ids: Optional UUIDs to associate with each change.
        model: Override the LLM model (defaults to settings.llm_model).

    Returns:
        List of analysis dicts (one per change) with summary, risk, etc.
        Returns empty list if API key not configured or call fails.
    """
    client = _get_client()
    if client is None:
        return []

    # Filter to substantive changes only (skip pure section-renumbering)
    substantive_changes = [c for c in changes if c._is_substantive()]
    if not substantive_changes:
        return []

    changes_context = _build_changes_context(substantive_changes)
    party_context = REVIEWING_PARTY_CONTEXT[reviewing_party]

    user_message = (
        f"Analyze the following {len(substantive_changes)} changes between two contract versions.\n\n"
        f"REVIEWING PARTY PERSPECTIVE:\n{party_context}\n\n"
        f"CHANGES TO ANALYZE:\n{changes_context}\n\n"
        f"Provide a summary and risk assessment for each change using the submit_analysis tool."
    )

    try:
        response = client.messages.create(
            model=model or settings.llm_model,
            max_tokens=8192,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
            tools=[ANALYSIS_TOOL],
            tool_choice={"type": "tool", "name": "submit_analysis"},
        )

        # Extract the tool call result
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_analysis":
                return block.input.get("changes", [])

        logger.error("No tool_use block found in LLM response.")
        return []

    except APIError as e:
        logger.error(f"Anthropic API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error during AI analysis: {e}")
        return []


def build_annotated_changes(
    diff_changes: list[DiffChange],
    ai_results: list[dict],
    reviewing_party: ReviewingParty,
    version_source: str | None = None,
) -> list[AnnotatedChange]:
    """Combine diff changes with AI analysis into AnnotatedChange objects.

    Maps AI results back to their corresponding changes, handling the
    substantive-only filtering that was applied during analysis.
    """
    # Convert DiffChanges to Change models
    all_changes = [c.to_change_model(version_source) for c in diff_changes]

    # Build index mapping: substantive changes only
    substantive_indices = [
        i for i, c in enumerate(diff_changes) if c._is_substantive()
    ]

    # Map AI results to change models
    ai_map: dict[int, dict] = {}
    for result in ai_results:
        # change_index is 1-based in the AI output, maps to substantive_indices
        ai_idx = result.get("change_index", 0) - 1
        if 0 <= ai_idx < len(substantive_indices):
            original_idx = substantive_indices[ai_idx]
            ai_map[original_idx] = result

    annotated = []
    for i, change in enumerate(all_changes):
        ai_data = ai_map.get(i)

        ai_summary = None
        risk_assessment = None

        if ai_data:
            # Build related change UUIDs
            related_indices = ai_data.get("related_change_indices", [])
            related_ids = []
            for ri in related_indices:
                ri_adjusted = ri - 1
                if 0 <= ri_adjusted < len(substantive_indices):
                    orig_ri = substantive_indices[ri_adjusted]
                    if orig_ri < len(all_changes):
                        related_ids.append(all_changes[orig_ri].id)

            ai_summary = AISummary(
                change_id=change.id,
                summary=ai_data.get("summary", ""),
                change_category=ai_data.get("change_category", ""),
                is_substantive=ai_data.get("is_substantive", True),
                related_changes=related_ids,
            )

            severity_str = ai_data.get("risk_severity", "info")
            try:
                severity = RiskSeverity(severity_str)
            except ValueError:
                severity = RiskSeverity.INFO

            risk_assessment = RiskAssessment(
                change_id=change.id,
                severity=severity,
                summary=ai_data.get("summary", ""),
                risk_explanation=ai_data.get("risk_explanation", ""),
                recommendation=ai_data.get("recommendation", ""),
                confidence=ai_data.get("confidence", 50),
                reviewing_party=reviewing_party,
            )

        annotated.append(AnnotatedChange(
            change=change,
            ai_summary=ai_summary,
            risk_assessment=risk_assessment,
        ))

    return annotated
