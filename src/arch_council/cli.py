from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .client import AnthropicGatewayClient, LLMError
from .config import Settings
from .context import build_diff_context, build_readme_context, build_repository_context
from .debate import ArchitectureDebate, write_report
from .research import ResearchError, TavilyResearchClient


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arch-council",
        description="Run a bounded three-model architecture review over a local repository.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    review = subparsers.add_parser("review", help="Review a repository architecture question")
    review.add_argument("--repo", required=True, help="Path to the local repository")
    review.add_argument("--question", required=True, help="Architecture question to debate")
    review.add_argument("--model-a", help="Override Architect A model")
    review.add_argument("--model-b", help="Override Architect B model")
    review.add_argument("--model-c", help="Override Architect C model")
    review.add_argument(
        "--rounds",
        type=int,
        choices=range(1, 6),
        default=3,
        metavar="1-5",
        help="Number of three-way debate rounds after blind proposals (default: 3)",
    )
    context_group = review.add_mutually_exclusive_group()
    context_group.add_argument(
        "--diff-base",
        help="Use git diff BASE...HEAD instead of broad repo context",
    )
    context_group.add_argument(
        "--readme-only",
        action="store_true",
        help="Share only the root README with the council; no source files or repo tree",
    )
    review.add_argument(
        "--research",
        action="store_true",
        help="Search external web sources after blind proposals and ground the debate in evidence",
    )
    review.add_argument(
        "--research-queries",
        type=int,
        choices=range(1, 7),
        default=4,
        metavar="1-6",
        help="Number of research queries planned when --research is enabled (default: 4)",
    )
    review.add_argument(
        "--research-results",
        type=int,
        choices=range(1, 6),
        default=3,
        metavar="1-5",
        help="Maximum search results per research query (default: 3)",
    )
    review.add_argument(
        "--max-context-chars",
        type=int,
        default=120_000,
        help="Maximum repository/diff/README characters sent to each architect",
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
    model_c = args.model_c or settings.model_c

    if args.readme_only:
        context = build_readme_context(args.repo, max_chars=args.max_context_chars)
    elif args.diff_base:
        context = build_diff_context(args.repo, args.diff_base, max_chars=args.max_context_chars)
    else:
        context = build_repository_context(args.repo, max_chars=args.max_context_chars)

    research_client = None
    if args.research:
        if not settings.tavily_api_key:
            raise RuntimeError(
                "--research requires TAVILY_API_KEY. Add it to .env or run without --research."
            )
        research_client = TavilyResearchClient(settings.tavily_api_key)

    total_llm_calls = 7 + (3 * args.rounds) + (1 if args.research else 0)
    print(f"Repository: {context.root}")
    print(f"Context mode: {context.mode}")
    print(f"Included files: {len(context.included_files)}")
    if context.truncated:
        print("Warning: context was truncated to the configured limit.")
    print(f"Architect A: {model_a} (Production Pragmatist)")
    print(f"Architect B: {model_b} (Scaling Challenger)")
    print(f"Architect C: {model_c} (Alternative/Mutation Architect)")
    print(f"Debate rounds: {args.rounds}")
    print(f"External research: {'enabled' if args.research else 'disabled'}")
    if args.research:
        print(
            f"Research plan: {args.research_queries} queries × up to "
            f"{args.research_results} results/query"
        )
    print(f"Planned LLM calls: {total_llm_calls}")
    print(
        "Flow: 3 blind proposals → optional external research → "
        "three-way debate → 3 final revisions → ADR"
    )

    client = AnthropicGatewayClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout_seconds=settings.timeout_seconds,
    )
    debate = ArchitectureDebate(
        client,
        model_a=model_a,
        model_b=model_b,
        model_c=model_c,
        rounds=args.rounds,
        research_client=research_client,
        research_query_count=args.research_queries,
        research_results_per_query=args.research_results,
    )

    try:
        result = debate.run(question=args.question, context=context)
    except (LLMError, ResearchError) as exc:
        print(f"Review error: {exc}", file=sys.stderr)
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
