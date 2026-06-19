"""
Prompt templates for Claude.

Design philosophy:
- Prompts in code (not separate files) for type safety + easy refactoring
- Each prompt has a clear role: system message defines persona, user message asks specific question
- Templates are pure functions: (data) → str
- All inputs are pre-anonymized (no PII reaches this layer)

The PERSONA matters:
We give Claude the persona of a "senior compliance officer at a Swiss
private bank". This produces output in the right register:
- Professional but not bureaucratic
- Concise and decision-oriented
- Aware of Swiss regulatory context (FINMA, AMLA)
"""

from __future__ import annotations

from typing import Any


# === System persona ===
# Used in EVERY prompt to anchor Claude's voice/style
COMPLIANCE_OFFICER_PERSONA = """You are a senior compliance analyst at a Swiss private bank operating under FINMA supervision. You write clear, professional assessments for fellow compliance officers reviewing flagged cases.

Your style:
- Concise and decision-oriented (no fluff)
- Professional but human (avoid bureaucratic jargon)
- Reference regulatory context where relevant (FINMA, MiCA, FATF, SFC, FSRA)
- Use precise risk vocabulary (not "concerning" — say "behavioral deviation")
- Never invent facts not in the input data
- Never mention you are an AI

You are given anonymized case data. Client identifiers are pseudonyms (e.g., CLIENT_AAF7). Amounts are bucketed ranges. This is intentional — privacy by design under FINMA data sovereignty requirements."""


# === Prompt builders ===


def executive_summary_prompt(
    *,
    case_type: str,
    risk_score: float,
    risk_level: str,
    recommended_action: str,
    top_features: list[dict[str, Any]],
    anonymized_context: dict[str, Any],
    jurisdiction: str,
) -> str:
    """
    Generate a one-paragraph executive summary.
    
    Target: 60-90 words. The compliance officer reads this first.
    """
    features_text = _format_features(top_features)
    context_text = _format_context(anonymized_context)
    
    return f"""Write a one-paragraph executive summary (60-90 words) for the following flagged case.

CASE METADATA:
- Type: {case_type}
- Risk score: {risk_score:.1f}/100 ({risk_level})
- Recommended action: {recommended_action}
- Jurisdiction: {jurisdiction}

TOP CONTRIBUTING FEATURES (SHAP analysis):
{features_text}

ANONYMIZED CONTEXT:
{context_text}

Write the summary as a single paragraph. Lead with the outcome (what the action is and why). Then describe the most decisive signals. End with what should happen next. Do NOT use bullet points or headings — flowing prose only."""


def risk_factors_prompt(
    *,
    risk_score: float,
    risk_level: str,
    top_features: list[dict[str, Any]],
    anonymized_context: dict[str, Any],
) -> str:
    """
    Walk through WHY the model scored this case as it did.
    
    Target: 2-3 short paragraphs. More detail than exec summary.
    """
    features_text = _format_features(top_features, include_contributions=True)
    context_text = _format_context(anonymized_context)
    
    return f"""Explain the risk factors that drove this case's score of {risk_score:.1f}/100 ({risk_level}).

CONTRIBUTING FEATURES (with SHAP impact):
{features_text}

ANONYMIZED CONTEXT:
{context_text}

Write 2-3 short paragraphs (total 120-180 words). Walk through the top 3 most impactful features. For each, explain:
1. What the signal is (in plain language, not feature names)
2. Why it matters from a compliance perspective
3. Whether it's increasing or decreasing risk

Avoid feature names like "amount_vs_typical_ratio". Translate to natural language ("the transaction size relative to client baseline"). Do not use bullet points."""


def counterfactual_narrative_prompt(
    *,
    original_score: float,
    counterfactuals: list[dict[str, Any]],
) -> str:
    """
    Turn DiCE counterfactuals into a human narrative.
    
    Target: 80-120 words explaining what would change the outcome.
    """
    scenarios_text = "\n".join([
        f"Scenario {cf['scenario_id']}: {cf['summary']}"
        for cf in counterfactuals[:3]
    ])
    
    return f"""The model identified scenarios where this case (current score: {original_score:.1f}/100) would have been approved instead of flagged.

ALTERNATIVE SCENARIOS:
{scenarios_text}

Write 80-120 words of flowing prose explaining what aspects of this specific case made it risky, and what would have needed to be different for it to be acceptable. Frame this as helpful context for the compliance officer — these are NOT recommendations to approve, but insight into what the model considers borderline.

Start with "The model identified..." or similar. End with a sentence noting these alternatives are illustrative, not actionable. No bullet points."""


def action_rationale_prompt(
    *,
    recommended_action: str,
    risk_score: float,
    confidence: float,
    jurisdiction: str,
    jurisdiction_rules: dict[str, Any],
) -> str:
    """
    Justify the recommended action with regulatory context.
    
    Target: 80-120 words. Includes specific regulatory references.
    """
    rules_text = _format_jurisdiction_rules(jurisdiction_rules)
    
    return f"""Explain why the recommended action for this case is "{recommended_action}", with confidence {confidence:.0%}.

CONTEXT:
- Risk score: {risk_score:.1f}/100
- Jurisdiction: {jurisdiction}

APPLICABLE JURISDICTION RULES:
{rules_text}

Write 80-120 words explaining the decision logic. Reference at least one specific regulatory requirement that applies (e.g., FINMA AMLA, MiCA Article X, SFC AMLO). Be concrete about WHAT the compliance officer should do next (e.g., callback to client on known channel, file MROS report within 24h, etc.). No bullet points."""


# === Internal formatters ===


def _format_features(
    features: list[dict[str, Any]],
    include_contributions: bool = False,
) -> str:
    """Format SHAP features for prompt inclusion."""
    if not features:
        return "  (none reported)"
    
    lines = []
    for i, f in enumerate(features[:5], 1):
        if include_contributions:
            sign = "+" if f.get("contribution", 0) > 0 else ""
            contrib = f"  (impact: {sign}{f.get('contribution', 0):.2f})"
        else:
            contrib = ""
        label = f.get("human_label") or f.get("name", "unknown")
        direction = f.get("direction", "")
        marker = (
            "↑ risk" if direction == "risk_increasing"
            else "↓ risk" if direction == "risk_decreasing"
            else ""
        )
        lines.append(f"  {i}. {label} {marker}{contrib}")
    return "\n".join(lines)


def _format_context(context: dict[str, Any]) -> str:
    """Format anonymized context for prompt inclusion."""
    if not context:
        return "  (no additional context)"
    
    lines = []
    for key, value in context.items():
        # Skip empty values
        if value is None or value == "":
            continue
        # Display key in human-readable form
        readable_key = key.replace("_", " ").capitalize()
        lines.append(f"  {readable_key}: {value}")
    return "\n".join(lines) if lines else "  (no additional context)"


def _format_jurisdiction_rules(rules: dict[str, Any]) -> str:
    """Format jurisdiction rule pack for prompt inclusion."""
    if not rules:
        return "  (no specific rules loaded)"
    
    lines = []
    if "regulator" in rules:
        lines.append(f"  Regulator: {rules['regulator']}")
    if "officer_notes" in rules:
        lines.append(f"  Notes: {rules['officer_notes']}")
    if "applicable_rules" in rules:
        for rule in rules.get("applicable_rules", []):
            lines.append(f"  - {rule}")
    return "\n".join(lines) if lines else "  (no rules to display)"
