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
