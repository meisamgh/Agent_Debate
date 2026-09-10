# ArchCouncil

**ArchCouncil** is a deterministic two-model architecture review tool for software repositories.

It reads a local repository, asks two independent architecture agents to propose a design, lets them debate for a configurable number of rounds, gives each one a final revision, and produces a final Architecture Decision Record (ADR).

The default configuration is designed for the JustWoker Anthropic-compatible gateway that exposes `POST /v1/messages`.

## Why this project

Open-ended multi-agent conversations are expensive and can converge too quickly. ArchCouncil allows deeper discussion while keeping the workflow bounded and predictable:

1. Collect repository context deterministically.
2. Architect A proposes a pragmatic design independently.
3. Architect B proposes a scaling/challenger design independently.
4. A and B debate for `--rounds` exchanges (default: 3, maximum: 5).
5. Both produce a final revised architecture.
6. A produces a neutral synthesis that preserves unresolved disagreements.

The final report classifies decisions as **AGREE**, **DISAGREE**, or **NEEDS EXPERIMENT**.

## Architecture

```text
Local repository
      |
      v
Deterministic context collector
(tree + selected files or git diff)
      |
      +--------------------+
      |                    |
      v                    v
Architect A            Architect B
(gpt-5.6-sol)          (gpt-5.6-terra)
Pragmatist             Challenger
      |                    |
      +---- blind first ---+
              |
              v
      Debate round 1
              |
              v
      Debate round 2
              |
             ...
              |
              v
      Debate round N
              |
              v
     Final revision each
              |
              v
       ADR synthesis
              |
              v
reports/YYYYMMDD-HHMMSS.md
```

Both agents in a round respond to the **previous** round state. Architect B does not get to see Architect A's same-round response, so neither side gets an ordering advantage.

The full repository context is supplied to both blind proposals and the first debate round. Later debate rounds carry forward the compact debate state (concessions, rebuttals, unresolved disagreements, proposed resolutions, and current architecture position) instead of resending the whole repository. The repository context is supplied again for each final revision.

## Setup

```bash
git clone https://github.com/meisamgh/desktop-tutorial.git
cd desktop-tutorial
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Put your **new/rotated** JustWoker key in `.env`:

```env
JUSTWOKER_API_KEY=your_key_here
```

Never commit `.env`.

## Run an architecture review

Default: **3 debate rounds / 11 LLM calls**.

```bash
arch-council review \
  --repo ../semantic_text2sql_ideal \
  --question "Should this Text-to-SQL pipeline remain deterministic, or should planning and repair move to an agent framework?"
```

For a deeper five-round debate:

```bash
arch-council review \
  --repo ../semantic_text2sql_ideal \
  --rounds 5 \
  --question "What is the strongest production architecture for this project? Challenge unnecessary complexity, scalability limits, reliability risks, and agentic-vs-deterministic trade-offs."
```

Use a git diff instead of sending broad repository context:

```bash
arch-council review \
  --repo ../semantic_text2sql_ideal \
  --question "Is this change architecturally safe for production?" \
  --diff-base main \
  --rounds 3
```

Use different models:

```bash
arch-council review \
  --repo . \
  --question "How should this service scale to multiple tenants?" \
  --model-a gpt-5.6-sol \
  --model-b gpt-5.6-terra \
  --rounds 4
```

## Debate depth and call count

`--rounds` accepts values from **1 to 5**. The number of LLM calls is deterministic:

```text
Total calls = 5 + (2 × rounds)
```

| Debate rounds | LLM calls |
| ---: | ---: |
| 1 | 7 |
| 2 | 9 |
| 3 (default) | 11 |
| 4 | 13 |
| 5 | 15 |

Each run consists of two blind proposals, two calls per debate round, two final revisions, and one ADR synthesis.

## What happens in every debate round

Each architect must explicitly return:

- strongest opponent points
- concessions
- rebuttals
- unresolved disagreements ranked by impact
- concrete tests or evidence that could resolve those disagreements
- a compact current architecture position for the next round

This makes later rounds continue the real disagreement instead of repeatedly restating the initial proposals.

## Output

Each run writes a Markdown report under `reports/` containing:

- repository/question metadata
- independent proposal A
- independent proposal B
- every A/B debate round
- final revised proposal A
- final revised proposal B
- final ADR-style synthesis

The synthesis is explicitly instructed **not** to force consensus. Unresolved claims should become measurable experiments.

## Cost controls

Repository context is bounded by `--max-context-chars` (default: 120,000 characters). Prefer `--diff-base main` for PR-style reviews. Debate depth is hard-capped at five rounds, so there is no autonomous infinite loop.

The default three-round run makes 11 LLM calls. A five-round run makes 15. Later rounds avoid resending the full repository context, which reduces context growth while preserving the evolving argument.

## Gateway

Defaults:

```text
Base URL: https://api.justwoker.icu
Endpoint:  /v1/messages
Auth:      Authorization: Bearer <token>
A model:   gpt-5.6-sol
B model:   gpt-5.6-terra
```

These can be overridden through environment variables or CLI flags.

## Development

```bash
pip install -e '.[dev]'
pytest
ruff check .
```

## Security

- API keys are read from environment variables only.
- `.env` is ignored by Git.
- Binary files and common secret/config directories are excluded from context collection.
- The tool never executes code from the target repository.
- LLM outputs are advisory; architecture decisions should still be validated with benchmarks, tests, threat modeling, and production constraints.

## License

MIT
