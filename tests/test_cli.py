import pytest

from arch_council.cli import _build_parser


def test_review_defaults() -> None:
    args = _build_parser().parse_args(
        ["review", "--repo", ".", "--question", "What architecture should we use?"]
    )
    assert args.rounds == 3
    assert args.research is False
    assert args.research_provider == "searxng"
    assert args.research_queries == 4
    assert args.research_results == 3
    assert args.evidence_inspections == 4
    assert args.arbiter_model is None


def test_chat_command_is_available() -> None:
    args = _build_parser().parse_args(["chat", "--repo", ".", "--readme-only"])
    assert args.command == "chat"
    assert args.readme_only is True
    assert args.max_tool_steps == 2


def test_chat_tool_budget_can_be_overridden() -> None:
    args = _build_parser().parse_args(
        ["chat", "--repo", ".", "--research", "--max-tool-steps", "4"]
    )
    assert args.research is True
    assert args.max_tool_steps == 4


def test_rounds_accepts_one_through_three() -> None:
    parser = _build_parser()
    for rounds in range(1, 4):
        args = parser.parse_args(
            ["review", "--repo", ".", "--question", "Question", "--rounds", str(rounds)]
        )
        assert args.rounds == rounds


def test_rounds_rejects_four() -> None:
    with pytest.raises(SystemExit):
        _build_parser().parse_args(
            ["review", "--repo", ".", "--question", "Question", "--rounds", "4"]
        )


def test_arbiter_and_evidence_budget_can_be_overridden() -> None:
    args = _build_parser().parse_args(
        [
            "review",
            "--repo",
            ".",
            "--question",
            "Question",
            "--arbiter-model",
            "judge-model",
            "--evidence-inspections",
            "6",
        ]
    )
    assert args.arbiter_model == "judge-model"
    assert args.evidence_inspections == 6


def test_research_and_readme_only_flags_are_available() -> None:
    args = _build_parser().parse_args(
        [
            "review",
            "--repo",
            ".",
            "--question",
            "Question",
            "--readme-only",
            "--research",
            "--research-provider",
            "searxng",
            "--searxng-url",
            "http://127.0.0.1:8888",
            "--research-queries",
            "5",
            "--research-results",
            "4",
        ]
    )
    assert args.readme_only is True
    assert args.research is True
    assert args.research_provider == "searxng"
    assert args.searxng_url == "http://127.0.0.1:8888"
    assert args.research_queries == 5
    assert args.research_results == 4


def test_tavily_remains_an_optional_provider() -> None:
    args = _build_parser().parse_args(
        [
            "review",
            "--repo",
            ".",
            "--question",
            "Question",
            "--research",
            "--research-provider",
            "tavily",
        ]
    )
    assert args.research_provider == "tavily"


def test_readme_only_and_diff_base_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        _build_parser().parse_args(
            [
                "review",
                "--repo",
                ".",
                "--question",
                "Question",
                "--readme-only",
                "--diff-base",
                "main",
            ]
        )
