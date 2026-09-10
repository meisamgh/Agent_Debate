# ArchCouncil

**ArchCouncil** is a deterministic three-model architecture review tool for software repositories.

It reads a local repository, asks three independent architecture agents to propose designs, lets all three debate for a configurable number of rounds, gives each one a final revision, and produces a final Architecture Decision Record (ADR).

The default configuration is designed for the JustWoker Anthropic-compatible gateway that exposes `POST /v1/messages`.

## Why three models

The goal is not majority voting. The three architects are deliberately assigned different incentives so the council explores a wider design space:

- **Architect A — Production Pragmatist (`gpt-5.6-sol`)**: reliability, simplicity, cost, debuggability, bounded workflows.
- **Architect B — Scaling Challenger (`gpt-5.6-terra`)**: scalability, security, concurrency, observability, failure isolation, future constraints.
- **Architect C — Alternative / Mutation Architect (`gpt-5.6-luna`)**: challenges shared assumptions and proposes materially different architectures that A and B may miss.

A strong minority opinion is preserved when it has credible evidence. Two models agreeing does not automatically defeat the third.

## Workflow

```text
Local repository
      |
      v
Deterministic context collector
(tree + selected files or git diff)
      |
      +----------------------+----------------------+
      |                      |                      |
      v                      v                      v
Architect A              Architect B              Architect C
Sol                      Terra                    Luna
Pragmatist               Challenger               Mutation/Alternative
      |                      |                      |
      +---------- blind independent proposals -----+
                             |
                             v
                    Three-way debate round 1
                             |
                             v
                    Three-way debate round 2
                             |
                            ...
                             |
                             v
                    Three-way debate round N
                             |
                             v
                    Final revision by A/B/C
                             |
                             v
                        ADR synthesis
                             |
                             v
                 reports/YYYYMMDD-HHMMSS.md
```

All three agents in a round respond to the **same previous-round state**. No model sees another model's same-round response, so there is no ordering advantage.

The full repository context is supplied to the three blind proposals and to round 1. Later rounds carry only compact debate state: concessions, rebuttals, shared-assumption checks, unresolved disagreements, experiments, and current architecture positions. Full repository evidence is supplied again for final revisions.

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

Default: **3 debate rounds / 16 LLM calls**.

```bash
arch-council review \
  --repo ../semantic_text2sql_ideal \
  --question "Should this Text-to-SQL pipeline remain deterministic, or should planning and repair move to an agent framework?"
```

For the deepest built-in debate:

```bash
arch-council review \
  --repo ../semantic_text2sql_ideal \
  --rounds 5 \
  --question "What is the strongest production architecture for this project? Challenge unnecessary complexity, scalability limits, reliability risks, and agentic-vs-deterministic trade-offs."
```

Use a git diff instead of broad repository context:

```bash
arch-council review \
  --repo ../semantic_text2sql_ideal \
  --question "Is this change architecturally safe for production?" \
  --diff-base main \
  --rounds 3
```

Override any of the three models:

```bash
arch-council review \
  --repo . \
  --question "How should this service scale to multiple tenants?" \
  --model-a gpt-5.6-sol \
  --model-b gpt-5.6-terra \
  --model-c gpt-5.6-luna \
  --rounds 4
```

## Debate depth and call count

`--rounds` accepts **1 to 5**. The number of LLM calls is deterministic:

```text
Total calls = 7 + (3 × rounds)
```

| Debate rounds | LLM calls |
| ---: | ---: |
| 1 | 10 |
| 2 | 13 |
| 3 (default) | 16 |
| 4 | 19 |
| 5 | 22 |

Each run consists of three blind proposals, three calls per debate round, three final revisions, and one ADR synthesis.

## What happens in every debate round

Each architect receives the previous-round positions of the other two architects and must return:

- strongest points from each other architect
- concessions
- rebuttals attributed to the relevant architect
- a shared-assumption check
- unresolved disagreements ranked by impact
- measurable ways to resolve important disagreements
- a compact current architecture position for the next round

The prompts explicitly tell models **not** to concede simply because the other two agree.

## Output

Each run writes a Markdown report under `reports/` containing:

- repository/question metadata
- three independent proposals
- every three-way debate round
- three final revised proposals
- final ADR-style synthesis

The final ADR includes:

- Executive Decision
- Recommended Architecture
- Why
- Decision Matrix
- AGREE
- DISAGREE
- MINORITY REPORT
- NEEDS EXPERIMENT
- Risks
- Migration Plan
- Do Not Change
- Revisit Triggers

For `NEEDS EXPERIMENT`, the synthesis must provide a hypothesis, test, metric, and success criterion.

## Cost controls

Repository context is bounded by `--max-context-chars` (default: 120,000 characters). Prefer `--diff-base main` for PR-style reviews. Debate depth is hard-capped at five rounds, so there is no autonomous infinite loop.

The default three-round council makes 16 LLM calls. A five-round council makes 22. Later rounds avoid resending the full repository context, which reduces context growth while preserving the evolving argument.

## Gateway

Defaults:

```text
Base URL: https://api.justwoker.icu
Endpoint:  /v1/messages
Auth:      Authorization: Bearer <token>
A model:   gpt-5.6-sol
B model:   gpt-5.6-terra
C model:   gpt-5.6-luna
```

These can be overridden through environment variables or CLI flags.

> Note: `--model-c` currently uses the same JustWoker gateway/client as A and B. If you want a true external Claude model from Anthropic as one of the three participants, ArchCouncil needs a second-provider client; that is intentionally separate from merely changing the model name.

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
