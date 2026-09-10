import pytest

from arch_council.cli import _build_parser


def test_rounds_defaults_to_three() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "review",
            "--repo",
            ".",
            "--question",
            "What architecture should we use?",
        ]
    )

    assert args.rounds == 3
    assert args.research is False
    assert args.research_queries == 4
    assert args.research_results == 3


def test_rounds_accepts_one_through_five() -> None:
    parser = _build_parser()

    for rounds in range(1, 6):
        args = parser.parse_args(
            [
                "review",
                "--repo",
                ".",
                "--question",
                "Question",
                "--rounds",
                str(rounds),
            ]
        )
        assert args.rounds == rounds


def test_rounds_rejects_values_outside_range() -> None:
    parser = _build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "review",
                "--repo",
                ".",
                "--question",
                "Question",
                "--rounds",
                "6",
            ]
        )


def test_model_c_override_is_available() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "review",
            "--repo",
            ".",
            "--question",
            "Question",
            "--model-c",
            "custom-model-c",
        ]
    )

    assert args.model_c == "custom-model-c"


def test_research_and_readme_only_flags_are_available() -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "review",
            "--repo",
            ".",
            "--question",
            "Question",
            "--readme-only",
            "--research",
            "--research-queries",
            "5",
            "--research-results",
            "4",
        ]
    )

    assert args.readme_only is True
    assert args.research is True
    assert args.research_queries == 5
    assert args.research_results == 4


def test_readme_only_and_diff_base_are_mutually_exclusive() -> None:
    parser = _build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
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
