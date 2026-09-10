from pathlib import Path

import pytest

from arch_council.context import RepositoryContext
from arch_council.debate import ArchitectureDebate


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def complete(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return f"response-{len(self.calls)}"


def make_context(tmp_path: Path, text: str = "# repo context") -> RepositoryContext:
    return RepositoryContext(
        root=tmp_path,
        text=text,
        included_files=("README.md",),
        truncated=False,
        mode="repository",
    )


def test_default_three_round_council_uses_sixteen_model_calls(tmp_path: Path) -> None:
    client = FakeClient()
    debate = ArchitectureDebate(
        client,
        model_a="model-a",
        model_b="model-b",
        model_c="model-c",
    )

    result = debate.run(
        question="Which architecture is safer?",
        context=make_context(tmp_path),
    )

    assert len(client.calls) == 16
    assert [call["model"] for call in client.calls] == [
        "model-a",
        "model-b",
        "model-c",
        "model-a",
        "model-b",
        "model-c",
        "model-a",
        "model-b",
        "model-c",
        "model-a",
        "model-b",
        "model-c",
        "model-a",
        "model-b",
        "model-c",
        "model-a",
    ]
    assert len(result.debate_rounds) == 3
    assert result.proposal_a == "response-1"
    assert result.proposal_b == "response-2"
    assert result.proposal_c == "response-3"
    assert result.decision == "response-16"


@pytest.mark.parametrize(
    ("rounds", "expected_calls"),
    [(1, 10), (2, 13), (3, 16), (4, 19), (5, 22)],
)
def test_call_count_scales_with_rounds(
    tmp_path: Path,
    rounds: int,
    expected_calls: int,
) -> None:
    client = FakeClient()
    debate = ArchitectureDebate(
        client,
        model_a="model-a",
        model_b="model-b",
        model_c="model-c",
        rounds=rounds,
    )

    result = debate.run(question="Question", context=make_context(tmp_path))

    assert len(client.calls) == expected_calls
    assert len(result.debate_rounds) == rounds
    assert result.rounds_requested == rounds


def test_rounds_must_be_between_one_and_five() -> None:
    client = FakeClient()

    with pytest.raises(ValueError, match="between 1 and 5"):
        ArchitectureDebate(client, model_a="a", model_b="b", model_c="c", rounds=0)

    with pytest.raises(ValueError, match="between 1 and 5"):
        ArchitectureDebate(client, model_a="a", model_b="b", model_c="c", rounds=6)


def test_initial_proposals_are_blind(tmp_path: Path) -> None:
    client = FakeClient()
    debate = ArchitectureDebate(
        client,
        model_a="model-a",
        model_b="model-b",
        model_c="model-c",
        rounds=1,
    )
    context = make_context(tmp_path, text="repository evidence")

    debate.run(question="Question", context=context)

    proposal_a = str(client.calls[0]["user"])
    proposal_b = str(client.calls[1]["user"])
    proposal_c = str(client.calls[2]["user"])

    assert "response-1" not in proposal_b
    assert "response-1" not in proposal_c
    assert "response-2" not in proposal_c
    assert "repository evidence" in proposal_a
    assert "repository evidence" in proposal_b
    assert "repository evidence" in proposal_c


def test_each_new_round_uses_previous_round_state_symmetrically(tmp_path: Path) -> None:
    client = FakeClient()
    debate = ArchitectureDebate(
        client,
        model_a="model-a",
        model_b="model-b",
        model_c="model-c",
        rounds=2,
    )
    context = make_context(tmp_path, text="UNIQUE_FULL_REPO_EVIDENCE")

    debate.run(question="Question", context=context)

    # Calls 4, 5, 6 are round 1 and produce response-4/5/6.
    # Calls 7, 8, 9 are round 2. Each model sees all previous-round states,
    # but never another model's same-round response.
    round_two_a = str(client.calls[6]["user"])
    round_two_b = str(client.calls[7]["user"])
    round_two_c = str(client.calls[8]["user"])

    for prompt in (round_two_a, round_two_b, round_two_c):
        assert "response-4" in prompt
        assert "response-5" in prompt
        assert "response-6" in prompt

    assert "response-7" not in round_two_b
    assert "response-7" not in round_two_c
    assert "response-8" not in round_two_c

    # Full repository evidence is sent in round 1, but later rounds carry only compact
    # debate state to control token growth.
    assert "UNIQUE_FULL_REPO_EVIDENCE" in str(client.calls[3]["user"])
    assert "UNIQUE_FULL_REPO_EVIDENCE" in str(client.calls[4]["user"])
    assert "UNIQUE_FULL_REPO_EVIDENCE" in str(client.calls[5]["user"])
    assert "UNIQUE_FULL_REPO_EVIDENCE" not in round_two_a
    assert "UNIQUE_FULL_REPO_EVIDENCE" not in round_two_b
    assert "UNIQUE_FULL_REPO_EVIDENCE" not in round_two_c
