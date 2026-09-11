import json

from arch_council.governance import (
    ARBITER_WEIGHTS,
    DebateSignal,
    EvidenceRequest,
    dedupe_evidence_requests,
    parse_arbiter_scorecard,
    parse_debate_signal,
    should_continue_debate,
)


def test_evidence_requests_deduplicate_by_taxonomy_category() -> None:
    requests = [
        EvidenceRequest("query_ir", "Need IR paper evidence", "medium"),
        EvidenceRequest("query_ir", "Need SQL semantic IR evidence", "high"),
        EvidenceRequest("workflow_recovery", "Need durable recovery evidence", "medium"),
    ]
    result = dedupe_evidence_requests(requests)
    assert [item.category for item in result] == ["query_ir", "workflow_recovery"]
    assert result[0].priority == "high"


def test_invalid_structured_debate_output_does_not_fake_convergence() -> None:
    signal = parse_debate_signal("not json")
    assert signal.has_high_impact_unresolved is True
    assert signal.material_architecture_change is True


def test_stop_rule_is_deterministic() -> None:
    stable = DebateSignal(False, (), False)
    assert should_continue_debate(round_number=1, max_rounds=3, signals=(stable, stable, stable)) is False

    unresolved = DebateSignal(True, (), False)
    assert should_continue_debate(
        round_number=1,
        max_rounds=3,
        signals=(stable, unresolved, stable),
    ) is True
    assert should_continue_debate(
        round_number=3,
        max_rounds=3,
        signals=(unresolved,),
    ) is False


def test_weighted_arbiter_score_is_computed_by_code() -> None:
    base = {criterion: 2 for criterion in ARBITER_WEIGHTS}
    candidates = {candidate: dict(base) for candidate in ("A", "B", "C")}
    candidates["C"]["external_evidence_strength"] = 4
    scorecard = parse_arbiter_scorecard(json.dumps({"candidates": candidates}))
    assert scorecard.winner == "C"
    assert scorecard.weighted_totals["C"] > scorecard.weighted_totals["A"]
