from pathlib import Path

from arch_council.context import RepositoryContext
from arch_council.debate import ArchitectureDebate


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def complete(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return f"response-{len(self.calls)}"


def test_debate_is_bounded_to_seven_model_calls(tmp_path: Path) -> None:
    client = FakeClient()
    debate = ArchitectureDebate(client, model_a="model-a", model_b="model-b")
    context = RepositoryContext(
        root=tmp_path,
        text="# repo context",
        included_files=("README.md",),
        truncated=False,
        mode="repository",
    )

    result = debate.run(question="Which architecture is safer?", context=context)

    assert len(client.calls) == 7
    assert [call["model"] for call in client.calls] == [
        "model-a",
        "model-b",
        "model-a",
        "model-b",
        "model-a",
        "model-b",
        "model-a",
    ]
    assert result.proposal_a == "response-1"
    assert result.proposal_b == "response-2"
    assert result.decision == "response-7"


def test_initial_proposals_are_blind(tmp_path: Path) -> None:
    client = FakeClient()
    debate = ArchitectureDebate(client, model_a="model-a", model_b="model-b")
    context = RepositoryContext(
        root=tmp_path,
        text="repository evidence",
        included_files=(),
        truncated=False,
        mode="repository",
    )

    debate.run(question="Question", context=context)

    first_prompt = str(client.calls[0]["user"])
    second_prompt = str(client.calls[1]["user"])
    assert "response-1" not in second_prompt
    assert "repository evidence" in first_prompt
    assert "repository evidence" in second_prompt
