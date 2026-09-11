from __future__ import annotations

import json
from dataclasses import dataclass

EVIDENCE_CATEGORIES = (
    "semantic_layer",
    "query_ir",
    "schema_selection",
    "table_retrieval",
    "column_retrieval",
    "join_planning",
    "query_planning",
    "sql_generation",
    "validation",
    "execution",
    "result_verification",
    "workflow_recovery",
    "agent_orchestration",
    "observability",
    "security",
    "evaluation",
    "latency",
    "cost",
    "scalability",
    "human_escalation",
    "other",
)

ARBITER_WEIGHTS = {
    "repository_fit": 0.20,
    "external_evidence_strength": 0.20,
    "testability": 0.20,
    "predicted_correctness_impact_unverified": 0.15,
    "complexity_maintainability": 0.10,
    "recovery_robustness": 0.05,
    "latency_cost": 0.05,
    "migration_reversibility": 0.05,
}

PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class EvidenceRequest:
    category: str
    question: str
    priority: str = "medium"


@dataclass(frozen=True)
class DebateSignal:
    has_high_impact_unresolved: bool
    evidence_requests: tuple[EvidenceRequest, ...]
    material_architecture_change: bool


@dataclass(frozen=True)
class ArbiterScorecard:
    scores: dict[str, dict[str, int]]
    weighted_totals: dict[str, float]
    winner: str


def _extract_json_object(text: str) -> dict[str, object] | None:
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            raw = "\n".join(lines[1:-1]).strip()
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _evidence_request(value: object) -> EvidenceRequest | None:
    if not isinstance(value, dict):
        return None
    category = str(value.get("category", "")).strip().lower()
    question = str(value.get("question", "")).strip()
    priority = str(value.get("priority", "medium")).strip().lower()
    if category not in EVIDENCE_CATEGORIES or len(question) < 8:
        return None
    if priority not in PRIORITY_RANK:
        priority = "medium"
    return EvidenceRequest(category=category, question=question[:500], priority=priority)


def parse_evidence_gaps(text: str, *, max_gaps: int = 2) -> tuple[EvidenceRequest, ...]:
    payload = _extract_json_object(text)
    if payload is None:
        return ()
    raw_gaps = payload.get("gaps", [])
    if not isinstance(raw_gaps, list):
        return ()
    gaps: list[EvidenceRequest] = []
    for value in raw_gaps:
        request = _evidence_request(value)
        if request is not None:
            gaps.append(request)
        if len(gaps) >= max_gaps:
            break
    return tuple(gaps)


def parse_debate_signal(text: str) -> DebateSignal:
    payload = _extract_json_object(text)
    if payload is None:
        return DebateSignal(True, (), True)

    objections = payload.get("unresolved_objections", [])
    has_high = False
    if isinstance(objections, list):
        for value in objections:
            if not isinstance(value, dict):
                continue
            impact = str(value.get("impact", "")).strip().lower()
            status = str(value.get("status", "unresolved")).strip().lower()
            if impact == "high" and status == "unresolved":
                has_high = True
                break

    raw_requests = payload.get("evidence_requests", [])
    requests: list[EvidenceRequest] = []
    if isinstance(raw_requests, list):
        for value in raw_requests:
            request = _evidence_request(value)
            if request is not None:
                requests.append(request)

    material_change = bool(payload.get("material_architecture_change", False))
    return DebateSignal(has_high, tuple(requests), material_change)


def dedupe_evidence_requests(
    requests: list[EvidenceRequest] | tuple[EvidenceRequest, ...],
    *,
    max_requests: int = 4,
) -> tuple[EvidenceRequest, ...]:
    by_category: dict[str, EvidenceRequest] = {}
    for request in requests:
        current = by_category.get(request.category)
        if current is None or PRIORITY_RANK[request.priority] < PRIORITY_RANK[current.priority]:
            by_category[request.category] = request
    ordered = sorted(
        by_category.values(),
        key=lambda item: (PRIORITY_RANK[item.priority], item.category, item.question),
    )
    return tuple(ordered[:max_requests])


def should_continue_debate(
    *,
    round_number: int,
    max_rounds: int,
    signals: tuple[DebateSignal, ...] | list[DebateSignal],
) -> bool:
    if round_number >= max_rounds:
        return False
    return any(
        signal.has_high_impact_unresolved
        or signal.evidence_requests
        or signal.material_architecture_change
        for signal in signals
    )


def arbiter_rubric_text() -> str:
    descriptions = {
        "repository_fit": "Fit to the supplied repository requirements and constraints.",
        "external_evidence_strength": "Strength and applicability of cited external evidence.",
        "testability": "How falsifiable the proposal is with clear experiments and metrics.",
        "predicted_correctness_impact_unverified": (
            "Reasoning-based predicted correctness impact; this is explicitly unverified until tested."
        ),
        "complexity_maintainability": "Operational simplicity and maintainability.",
        "recovery_robustness": "Failure isolation, retries, resumability, and recovery quality.",
        "latency_cost": "Expected latency and monetary/token cost impact.",
        "migration_reversibility": "Migration safety, reversibility, and incremental adoption.",
    }
    lines = ["Score each criterion from 0 (unsupported/poor) to 4 (very strong)."]
    for name, weight in ARBITER_WEIGHTS.items():
        lines.append(f"- {name}: weight={weight:.2f}. {descriptions[name]}")
    return "\n".join(lines)


def parse_arbiter_scorecard(text: str) -> ArbiterScorecard:
    payload = _extract_json_object(text)
    if payload is None:
        raise ValueError("Arbiter returned invalid JSON scorecard")
    candidates = payload.get("candidates")
    if not isinstance(candidates, dict):
        raise TypeError("Arbiter scorecard candidates must be an object")

    normalized: dict[str, dict[str, int]] = {}
    for candidate in ("A", "B", "C"):
        raw = candidates.get(candidate)
        if not isinstance(raw, dict):
            raise TypeError(f"Arbiter scorecard candidate {candidate} must be an object")
        scores: dict[str, int] = {}
        for criterion in ARBITER_WEIGHTS:
            value = raw.get(criterion)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 4:
                raise ValueError(
                    f"Arbiter score for {candidate}.{criterion} must be an integer from 0 to 4"
                )
            scores[criterion] = value
        normalized[candidate] = scores

    totals = {
        candidate: round(
            sum(scores[name] * ARBITER_WEIGHTS[name] for name in ARBITER_WEIGHTS), 4
        )
        for candidate, scores in normalized.items()
    }
    tie_breakers = (
        "external_evidence_strength",
        "testability",
        "repository_fit",
        "predicted_correctness_impact_unverified",
    )
    winner = max(
        ("A", "B", "C"),
        key=lambda candidate: (
            totals[candidate],
            *(normalized[candidate][criterion] for criterion in tie_breakers),
            -ord(candidate),
        ),
    )
    return ArbiterScorecard(normalized, totals, winner)
