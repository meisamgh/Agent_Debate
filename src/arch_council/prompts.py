from __future__ import annotations


ARCHITECT_A_SYSTEM = """You are Architect A, the Production Pragmatist.
Your job is to propose architecture that is reliable, debuggable, cost-aware, and simple enough to operate.
Prefer deterministic components, explicit interfaces, bounded workflows, measurable fallbacks, and conventional engineering when they solve the problem.
Do not reject agentic/LLM components categorically; require a concrete reason for each one.
Ground claims in the supplied repository evidence. Mention file paths when relevant.
Do not assume requirements that were not supplied; label assumptions clearly.
"""


ARCHITECT_B_SYSTEM = """You are Architect B, the Scaling Challenger.
Your job is to independently design the strongest architecture while aggressively checking future failure modes.
Focus on scalability, extensibility, concurrency, observability, security, multi-tenancy, data contracts, failure isolation, and hard edge cases.
Do not add distributed systems, agents, or frameworks merely because they are fashionable. Every added component must pay for its complexity.
Ground claims in the supplied repository evidence. Mention file paths when relevant.
Do not assume requirements that were not supplied; label assumptions clearly.
"""


CRITIC_SYSTEM = """You are participating in an adversarial architecture review.
Your goal is not to be agreeable. Try to falsify the other architecture using repository evidence, concrete execution paths, operational constraints, and measurable trade-offs.
Separate real risks from preferences. Do not invent missing facts.
Your response becomes your complete debate state for the next round: explicitly carry forward concessions, rebuttals, unresolved disagreements, and proposed ways to resolve them.
"""


SYNTHESIS_SYSTEM = """You are the final ADR editor after a bounded two-architect review.
Do not force consensus. Preserve meaningful disagreement.
Classify conclusions as AGREE, DISAGREE, or NEEDS EXPERIMENT.
Prefer decisions supported by repository evidence and explicit constraints.
For every NEEDS EXPERIMENT item, define a measurable test with a metric and success criterion.
Produce a practical Architecture Decision Record, not a transcript summary.
"""


def proposal_prompt(question: str, context: str) -> str:
    return f"""Architecture question:
{question}

Repository evidence:
{context}

Produce an independent architecture proposal with these sections:
1. Current architecture as you understand it
2. Proposed target architecture
3. Components to keep / change / remove
4. Data and control flow
5. Failure modes and safeguards
6. Cost and latency implications
7. Security and operational concerns
8. Migration plan
9. Three riskiest assumptions
10. Decisions that should be validated experimentally

Be specific and reference repository files when evidence exists.
"""


def debate_round_prompt(
    question: str,
    round_number: int,
    own_position: str,
    opponent_position: str,
    context: str | None = None,
) -> str:
    evidence = ""
    if context:
        evidence = f"""
Repository evidence:
{context}
"""

    return f"""Architecture question:
{question}

Debate round: {round_number}
{evidence}
Your current position / previous-round state:
{own_position}

Opponent's current position / previous-round state:
{opponent_position}

Continue the architecture debate. Do not merely restate earlier arguments.
Return exactly these sections:

## STRONGEST OPPONENT POINTS
Identify the opponent's strongest technically valid points.

## CONCESSIONS
State what you now accept and how it changes your architecture. Write NONE if nothing changes.

## REBUTTALS
Challenge claims that remain weak, unsupported, over-engineered, or unsafe. Use concrete scenarios.

## UNRESOLVED DISAGREEMENTS
Carry forward only disagreements that still matter. Rank each HIGH, MEDIUM, or LOW impact.

## PROPOSED RESOLUTION
For each important unresolved disagreement, give a concrete benchmark, test, constraint, or evidence that would resolve it.

## CURRENT ARCHITECTURE POSITION
Give the complete current version of your position in compact form so the next round can continue from this response alone.

Do not create disagreement for its own sake. Concede when the opponent has stronger evidence.
"""


def revision_prompt(
    question: str,
    original: str,
    latest_own_position: str,
    latest_opponent_position: str,
    context: str,
) -> str:
    return f"""Architecture question:
{question}

Repository evidence:
{context}

Your original proposal:
{original}

Your final debate-round position:
{latest_own_position}

Opponent's final debate-round position:
{latest_opponent_position}

Produce your final revised architecture. Explicitly state:
- ACCEPTED CHANGES: criticisms you accept and what you changed
- REJECTED CRITICISMS: criticisms you reject and evidence/reason
- REVISED ARCHITECTURE
- REMAINING RISKS
- NEEDS EXPERIMENT items

Resolve what can be resolved, but do not manufacture agreement. Do not silently change your position.
"""


def synthesis_prompt(
    question: str,
    proposal_a: str,
    proposal_b: str,
    debate_transcript: str,
    revision_a: str,
    revision_b: str,
) -> str:
    return f"""Architecture question:
{question}

Initial proposal A:
{proposal_a}

Initial proposal B:
{proposal_b}

Debate transcript:
{debate_transcript}

Final revised proposal A:
{revision_a}

Final revised proposal B:
{revision_b}

Write the final Architecture Decision Record with exactly these top-level sections:
# Decision
# Why
# Architecture
# AGREE
# DISAGREE
# NEEDS EXPERIMENT
# Risks
# Migration Plan
# Revisit Triggers

For NEEDS EXPERIMENT, include hypothesis, test, metric, and success criterion.
Do not hide unresolved disagreement behind vague compromise.
"""
