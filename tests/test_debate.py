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


def test_default_three_round_debate_uses_eleven_model_calls(tmp_path: Path) -> None:
    client = FakeClient()
    debate = ArchitectureDebate(client, model_a="model-a", model_b="model-b")

    result = debate.run(
        question="Which architecture is safer?",
        context=make_context(tmp_path),
    )

    assert len(client.calls) == 11
    assert [call["model"] for call in client.calls] == [
        "model-a",
        "model-b",
        "model-a",
        "model-b",
        "model-a",
        "model-b",
        "model-a",
        "model-b",
        "model-a",
        "model-b",
        "model-a",
    ]
    assert len(result.debate_rounds) == 3
    assert result.proposal_a == "response-1"
    assert result.proposal_b == "response-2"
    assert result.decision == "response-11"


@pytest.mark.parametrize(
    ("rounds", "expected_calls"),
    [(1, 7), (2, 9), (3, 11), (4, 13), (5, 15)],
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
        rounds=rounds,
    )

    result = debate.run(question="Question", context=make_context(tmp_path))

    assert len(client.calls) == expected_calls
    assert len(result.debate_rounds) == rounds
    assert result.rounds_requested == rounds


def test_rounds_must_be_between_one_and_five() -> None:
    client = FakeClient()

    with pytest.raises(ValueError, match="between 1 and 5"):
        ArchitectureDebate(client, model_a="a", model_b="b", rounds=0)

    with pytest.raises(ValueError, match="between 1 and 5"):
        ArchitectureDebate(client, model_a="a", model_b="b", rounds=6)


def test_initial_proposals_are_blind(tmp_path: Path) -> None:
    client = FakeClient()
    debate = ArchitectureDebate(client, model_a="model-a", model_b="model-b", rounds=1)
    context = make_context(tmp_path, text="repository evidence")

    debate.run(question="Question", context=context)

    first_prompt = str(client.calls[0]["user"])
    second_prompt = str(client.calls[1]["user"])
    assert "response-1" not in second_prompt
    assert "repository evidence" in first_prompt
    assert "repository evidence" in second_prompt


def test_each_new_round_uses_previous_round_state_symmetrically(tmp_path: Path) -> None:
    client = FakeClient()
    debate = ArchitectureDebate(client, model_a="model-a", model_b="model-b", rounds=2)
    context = make_context(tmp_path, text="UNIQUE_FULL_REPO_EVIDENCE")

    debate.run(question="Question", context=context)

    # Calls 3 and 4 are debate round 1 and produce response-3 / response-4.
    # Calls 5 and 6 are debate round 2. Both must see the previous round,
    # not the opponent's same-round answer.
    round_two_a = str(client.calls[4]["user"])
    round_two_b = str(client.calls[5]["user"])

    assert "response-3" in round_two_a
    assert "response-4" in round_two_a
    assert "response-4" in round_two_b
    assert "response-3" in round_two_b
    assert "response-5" not in round_two_b

    # Full repository evidence is sent in round 1, but later debate rounds carry
    # only the compact debate state to control token growth.
    assert "UNIQUE_FULL_REPO_EVIDENCE" in str(client.calls[2]["user"])
    assert "UNIQUE_FULL_REPO_EVIDENCE" in str(client.calls[3]["user"])
    assert "UNIQUE_FULL_REPO_EVIDENCE" not in round_two_a
    assert "UNIQUE_FULL_REPO_EVIDENCE" not in round_two_b
