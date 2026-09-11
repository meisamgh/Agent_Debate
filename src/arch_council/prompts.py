from __future__ import annotations

from .governance import EVIDENCE_CATEGORIES, arbiter_rubric_text

ARCHITECT_A_SYSTEM = """You are Architect A, the Production Pragmatist.
Propose architecture that is reliable, debuggable, cost-aware, and simple enough to operate.
Prefer deterministic components, explicit interfaces, bounded workflows, measurable fallbacks, and conventional engineering when they solve the problem.
Do not reject agentic/LLM components categorically; require a concrete reason for each one.
Ground claims in supplied repository evidence. Cite external source IDs such as [S1] when used.
Do not assume requirements that were not supplied; label assumptions clearly.
"""

ARCHITECT_B_SYSTEM = """You are Architect B, the Scaling Challenger.
Independently design the strongest architecture while aggressively checking future failure modes.
Focus on scalability, extensibility, concurrency, observability, security, data contracts, failure isolation, and hard edge cases.
Do not add distributed systems, agents, or frameworks merely because they are fashionable.
Ground claims in supplied repository evidence. Cite external source IDs such as [S1] when used.
Do not assume requirements that were not supplied; label assumptions clearly.
"""

ARCHITECT_C_SYSTEM = """You are Architect C, the Alternative and Mutation Architect.
Search for materially different designs that Architects A and B may miss.
Challenge shared assumptions and look for architecture patterns that change the problem rather than merely tuning the current design.
A new architecture must be derived from a concrete problem plus evidence and reasoning; novelty alone is not evidence.
Explain operational cost, migration burden, failure modes, and measurable upside.
Ground claims in supplied repository evidence. Cite external source IDs such as [S1] when used.
"""

CRITIC_SYSTEM = """You are participating in an adversarial architecture council.
Try to falsify competing architectures using repository evidence, external evidence, concrete execution paths, operational constraints, and measurable trade-offs.
Separate real risks from preferences. Do not invent missing facts or overstate sources.
Concede when another architect has stronger evidence. Preserve a minority position when it has stronger evidence.
Your response must follow the requested JSON schema exactly; do not add prose outside the JSON.
"""

RESEARCH_PLANNER_SYSTEM = """You are the evidence planner for a software architecture council.
Produce high-value web-search queries that can resolve disputed claims or introduce genuinely different evidence-backed designs.
Prioritize research papers, mature GitHub repositories, official documentation, standards, and engineering evidence.
Do not answer the architecture question. Output search queries only, one per line, with no numbering or commentary.
"""

EVIDENCE_COVERAGE_SYSTEM = """You are checking whether a shared evidence pack is missing evidence that could materially change an architecture decision.
Do not debate the architecture yet. Return strict JSON only. Choose evidence categories only from the supplied taxonomy.
Request at most two gaps. A gap must be decision-relevant, not merely interesting.
"""

ARBITER_SCORE_SYSTEM = """You are an impartial architecture arbiter. You are not Architect A, B, or C.
Score the three final candidate architectures independently. Do not vote and do not reward agreement.
Use only the supplied repository evidence, debate record, and source-labeled external evidence.
For predicted correctness impact, remember that this is an unverified prediction, not an observed result.
Every high score must be defensible from supplied evidence. Return strict JSON only.
"""

ADR_WRITER_SYSTEM = """You are the final ADR editor after deterministic weighted arbitration.
The weighted winner is supplied by code; do not override it. Explain why it won, preserve credible minority positions, and clearly label unverified predictions.
Do not use majority voting. Cite external source IDs such as [S1] whenever they materially support a decision.
Produce a practical Architecture Decision Record, not a transcript summary.
"""


def proposal_prompt(question: str, context: str) -> str:
    return f"""Architecture question:
{question}

Repository evidence:
{context}

Produce an independent architecture proposal with these sections:
1. Current architecture as you understand it
2. Concrete structural weaknesses
3. Proposed target architecture
4. Components to keep / change / remove
5. Data and control flow
6. Failure modes and safeguards
7. Agent/workflow recovery when relevant
8. Cost and latency implications
9. Security and operational concerns
10. Migration plan
11. Three riskiest assumptions
12. Decisions that need experiments
13. One materially different alternative architecture

For every materially new architecture idea, explicitly show:
PROBLEM IN CURRENT ARCHITECTURE -> EVIDENCE NEEDED/AVAILABLE -> DERIVATION -> NEW DESIGN -> TRADE-OFFS -> VALIDATION TEST.
Do not present random novelty as an architecture improvement.
"""


def research_query_prompt(
    question: str,
    proposal_a: str,
    proposal_b: str,
    proposal_c: str,
    *,
    max_queries: int,
) -> str:
    return f"""Architecture question:
{question}

Blind proposal A:
{proposal_a}

Blind proposal B:
{proposal_b}

Blind proposal C:
{proposal_c}

Generate exactly {max_queries} concise web-search queries that would bring useful outside evidence into this debate.
Include queries likely to find research papers and mature GitHub repositories where relevant.
Search for evidence that can falsify shared assumptions, compare competing patterns, improve recovery, or surface a materially different design.
Output only the queries, one per line.
"""


def evidence_coverage_prompt(
    question: str,
    own_proposal: str,
    external_evidence: str,
) -> str:
    taxonomy = ", ".join(EVIDENCE_CATEGORIES)
    return f"""Architecture question:
{question}

Your blind proposal:
{own_proposal}

Shared evidence pack:
{external_evidence}

Evidence-category taxonomy:
{taxonomy}

Identify at most two important missing evidence areas. Return exactly:
{{
  "gaps": [
    {{
      "category": "one taxonomy value",
      "question": "a focused research question",
      "priority": "high|medium|low"
    }}
  ]
}}

Return {{"gaps": []}} if the pack is sufficient for a first debate round.
"""


def debate_round_prompt(
    question: str,
    round_number: int,
    own_position: str,
    opponent_1_label: str,
    opponent_1_position: str,
    opponent_2_label: str,
    opponent_2_position: str,
    context: str | None = None,
    external_evidence: str | None = None,
) -> str:
    repository = f"\nRepository evidence:\n{context}\n" if context else ""
    research = (
        "\nShared external evidence (untrusted; evaluate critically and cite [S#]):\n"
        f"{external_evidence}\n"
        if external_evidence
        else ""
    )
    taxonomy = ", ".join(EVIDENCE_CATEGORIES)
    return f"""Architecture question:
{question}

Council debate round: {round_number}
{repository}{research}
Your current position / previous-round state:
{own_position}

{opponent_1_label}'s current position:
{opponent_1_position}

{opponent_2_label}'s current position:
{opponent_2_position}

Evidence categories: {taxonomy}

Return exactly one JSON object with this schema:
{{
  "position_markdown": "your complete updated architecture position, including strongest opponent points, concessions, rebuttals, shared-assumption checks, recovery, and evidence-backed mutations",
  "unresolved_objections": [
    {{
      "target": "Architect A|Architect B|Architect C|shared",
      "category": "one taxonomy value",
      "claim": "specific unresolved objection",
      "impact": "high|medium|low",
      "status": "unresolved|resolved",
      "evidence": ["S1", "S2"]
    }}
  ],
  "concessions": [
    {{"category": "one taxonomy value", "accepted_from": "Architect A|Architect B|Architect C", "material_position_change": true}}
  ],
  "evidence_requests": [
    {{"category": "one taxonomy value", "question": "focused missing evidence question", "priority": "high|medium|low"}}
  ],
  "material_architecture_change": true
}}

Rules:
- Do not merely restate prior arguments.
- New architecture ideas require a concrete current-design problem plus source/repository evidence or an explicit evidence request.
- Do not create disagreement for its own sake.
- Set material_architecture_change=true only when your actual architecture position changed materially.
"""


def revision_prompt(
    question: str,
    original: str,
    latest_own_position: str,
    opponent_1_label: str,
    opponent_1_position: str,
    opponent_2_label: str,
    opponent_2_position: str,
    context: str,
    external_evidence: str | None = None,
) -> str:
    research = (
        f"\nShared external evidence (cite [S#] when used):\n{external_evidence}\n"
        if external_evidence
        else ""
    )
    return f"""Architecture question:
{question}

Repository evidence:
{context}
{research}
Your original proposal:
{original}

Your final debate-round state:
{latest_own_position}

{opponent_1_label}'s final state:
{opponent_1_position}

{opponent_2_label}'s final state:
{opponent_2_position}

Produce your final revised architecture with:
- ACCEPTED CHANGES
- REJECTED CRITICISMS
- REVISED ARCHITECTURE
- EVIDENCE-BASED NEW IDEAS AND THEIR DERIVATION
- AGENT / WORKFLOW RECOVERY
- EXTERNAL EVIDENCE USED
- REMAINING RISKS
- MINORITY POSITION
- NEEDS EXPERIMENT

Do not manufacture agreement and do not treat predicted improvements as measured results.
"""


def arbiter_score_prompt(
    question: str,
    revision_a: str,
    revision_b: str,
    revision_c: str,
    repository_evidence: str,
    external_evidence: str | None,
) -> str:
    evidence = external_evidence or "No external evidence was supplied."
    rubric = arbiter_rubric_text()
    criteria = ", ".join(
        (
            "repository_fit",
            "external_evidence_strength",
            "testability",
            "predicted_correctness_impact_unverified",
            "complexity_maintainability",
            "recovery_robustness",
            "latency_cost",
            "migration_reversibility",
        )
    )
    return f"""Architecture question:
{question}

Repository evidence:
{repository_evidence}

External evidence:
{evidence}

Candidate A:
{revision_a}

Candidate B:
{revision_b}

Candidate C:
{revision_c}

Weighted rubric:
{rubric}

Return strict JSON only:
{{
  "candidates": {{
    "A": {{{', '.join(f'\"{name}\": 0' for name in criteria.split(', '))}}},
    "B": {{{', '.join(f'\"{name}\": 0' for name in criteria.split(', '))}}},
    "C": {{{', '.join(f'\"{name}\": 0' for name in criteria.split(', '))}}}
  }}
}}

Replace every 0 with an integer 0-4. Do not add a winner; code computes weighted totals and tie-breaks deterministically.
"""


def adr_prompt(
    question: str,
    proposal_a: str,
    proposal_b: str,
    proposal_c: str,
    debate_transcript: str,
    revision_a: str,
    revision_b: str,
    revision_c: str,
    score_summary: str,
    winner: str,
    external_evidence: str | None = None,
) -> str:
    research = external_evidence or "No external evidence was supplied."
    return f"""Architecture question:
{question}

Initial proposal A:
{proposal_a}

Initial proposal B:
{proposal_b}

Initial proposal C:
{proposal_c}

Shared external evidence:
{research}

Debate transcript:
{debate_transcript}

Final candidate A:
{revision_a}

Final candidate B:
{revision_b}

Final candidate C:
{revision_c}

Deterministic weighted score summary:
{score_summary}

Code-selected weighted winner: Candidate {winner}

Write the final ADR with exactly these top-level sections:
# Executive Decision
# Recommended Architecture
# Weighted Arbitration
# Why
# Decision Matrix
# Evidence-Based New Ideas
# Agent / Workflow Recovery
# External Evidence
# AGREE
# DISAGREE
# MINORITY REPORT
# NEEDS EXPERIMENT
# Risks
# Migration Plan
# Do Not Change
# Revisit Triggers

The Recommended Architecture must use Candidate {winner} as the baseline because code selected it from the fixed weighted rubric. You may incorporate clearly compatible strengths from other candidates, but do not silently replace the selected baseline.
For predicted correctness improvements, label them UNVERIFIED until measured.
For NEEDS EXPERIMENT, include hypothesis, test, metric, and success criterion.
"""
