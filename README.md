# ArchCouncil

**ArchCouncil** is a deterministic two-model architecture review tool for software repositories.

It reads a local repository, asks two independent architecture agents to propose a design, makes them challenge each other's assumptions, gives each one revision round, and produces a final Architecture Decision Record (ADR).

The default configuration is designed for the JustWoker Anthropic-compatible gateway that exposes `POST /v1/messages`.

## Why this project

Open-ended multi-agent conversations are expensive and often converge too quickly. ArchCouncil keeps the workflow bounded:

1. Collect repository context deterministically.
2. Architect A proposes a pragmatic design independently.
3. Architect B proposes a scaling/challenger design independently.
4. A critiques B.
5. B critiques A.
6. Both revise once.
7. A produces a neutral synthesis that preserves unresolved disagreements.

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
      Cross-critique
              |
              v
       One revision each
              |
              v
       ADR synthesis
              |
              v
reports/YYYYMMDD-HHMMSS.md
```

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

```bash
arch-council review \
  --repo ../semantic_text2sql_ideal \
  --question "Should this Text-to-SQL pipeline remain deterministic, or should planning and repair move to an agent framework?"
```

Use a git diff instead of sending broad repository context:

```bash
arch-council review \
  --repo ../semantic_text2sql_ideal \
  --question "Is this change architecturally safe for production?" \
  --diff-base main
```

Use different models:

```bash
arch-council review \
  --repo . \
  --question "How should this service scale to multiple tenants?" \
  --model-a gpt-5.6-sol \
  --model-b gpt-5.6-terra
```

## Output

Each run writes a Markdown report under `reports/` containing:

- repository/question metadata
- independent proposal A
- independent proposal B
- A's critique of B
- B's critique of A
- revised proposal A
- revised proposal B
- final ADR-style synthesis

The synthesis is explicitly instructed **not** to force consensus. Unresolved claims should become measurable experiments.

## Cost controls

Repository context is bounded by `--max-context-chars` (default: 120,000 characters). Prefer `--diff-base main` for PR-style reviews. The workflow has a fixed number of LLM calls and no autonomous loop.

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
