from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .client import AnthropicGatewayClient, LLMError
from .config import Settings
from .context import build_diff_context, build_repository_context
from .debate import ArchitectureDebate, write_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arch-council",
        description="Run a bounded two-model architecture review over a local repository.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="Review a repository architecture question")
    review.add_argument("--repo", required=True, help="Path to the local repository")
    review.add_argument("--question", required=True, help="Architecture question to debate")
    review.add_argument("--model-a", help="Override Architect A model")
    review.add_argument("--model-b", help="Override Architect B model")
    review.add_argument(
        "--rounds",
        type=int,
        choices=range(1, 6),
        default=3,
        metavar="1-5",
        help="Number of A/B debate rounds after blind proposals (default: 3)",
    )
    review.add_argument("--diff-base", help="Use git diff BASE...HEAD instead of broad repo context")
    review.add_argument(
        "--max-context-chars",
        type=int,
        default=120_000,
        help="Maximum repository/diff characters sent to each architect",
    )
    review.add_argument(
        "--output-dir",
        default="reports",
        help="Directory for generated Markdown reports",
    )
    return parser


def _run_review(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    model_a = args.model_a or settings.model_a
    model_b = args.model_b or settings.model_b

    if args.diff_base:
        context = build_diff_context(
            args.repo,
            args.diff_base,
            max_chars=args.max_context_chars,
        )
    else:
        context = build_repository_context(
            args.repo,
            max_chars=args.max_context_chars,
        )

    total_calls = 5 + (2 * args.rounds)
    print(f"Repository: {context.root}")
    print(f"Context mode: {context.mode}")
    print(f"Included files: {len(context.included_files)}")
    if context.truncated:
        print("Warning: context was truncated to the configured limit.")
    print(f"Architect A: {model_a}")
    print(f"Architect B: {model_b}")
    print(f"Debate rounds: {args.rounds}")
    print(f"Planned LLM calls: {total_calls}")
    print("Flow: blind proposals → repeated debate → final revisions → ADR")

    client = AnthropicGatewayClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout_seconds=settings.timeout_seconds,
    )
    debate = ArchitectureDebate(
        client,
        model_a=model_a,
        model_b=model_b,
        rounds=args.rounds,
    )

    try:
        result = debate.run(question=args.question, context=context)
    except LLMError as exc:
        print(f"LLM gateway error: {exc}", file=sys.stderr)
        return 2

    report = write_report(result, context, Path(args.output_dir))
    print(f"\nReport written to: {report}")
    print("\n=== FINAL ADR ===\n")
    print(result.decision)
    return 0


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "review":
            raise SystemExit(_run_review(args))
        parser.error(f"Unknown command: {args.command}")
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
