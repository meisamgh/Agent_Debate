# ArchCouncil

**ArchCouncil** is a deterministic three-model architecture council for software repositories, with optional external research grounding.

It can share the whole selected repository context, a git diff, or **only the root README**. Three independent architecture reviewers first propose designs blindly. If `--research` is enabled, a separate research-planning step turns their disagreements into web-search queries, gathers outside evidence, and injects source-labeled evidence into the debate. The council then debates, revises, and produces an Architecture Decision Record (ADR).

The LLM gateway defaults to the JustWoker Anthropic-compatible `POST /v1/messages` endpoint. External web search currently uses Tavily's Search API.

## Council roles

- **Architect A — Production Pragmatist (`gpt-5.6-sol`)**: reliability, simplicity, cost, debuggability, bounded workflows.
- **Architect B — Scaling Challenger (`gpt-5.6-terra`)**: scalability, security, concurrency, observability, failure isolation, future constraints.
- **Architect C — Alternative / Mutation Architect (`gpt-5.6-luna`)**: challenges shared assumptions and proposes materially different architectures.

The council does not use simple majority voting. A strong minority position is preserved when its evidence is better.

## Evidence-grounded workflow

```text
README.md / repository / git diff
              |
              v
      3 blind proposals
      A       B       C
              |
              v
     optional Research Planner
              |
      disputed / uncertain claims
              |
              v
        Tavily web search
              |
              v
    [S1] [S2] [S3] evidence pack
              |
              v
       A <--> B <--> C
       architecture debate
              |
     evidence-backed mutation
     recovery analysis
     minority positions
              |
              v
       final revisions
              |
              v
          Final ADR
```

External sources are treated as **untrusted evidence**, not truth. The models are instructed to cite source IDs such as `[S1]`, reject weak evidence, and avoid claiming more than a source supports.

## Setup

```bash
git clone https://github.com/meisamgh/desktop-tutorial.git
cd desktop-tutorial
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Add your JustWoker key to `.env`:

```env
JUSTWOKER_API_KEY=your_key_here
```

For external web research, also add a Tavily API key:

```env
TAVILY_API_KEY=your_tavily_key_here
```

Never commit `.env`.

## Recommended architecture-only run

If you want the models to discuss architecture rather than implementation details, share only the README and enable research:

```bash
arch-council review \
  --repo "/Users/meisam/Documents/text-to-sql/semantic_text2sql_ideal" \
  --readme-only \
  --research \
  --rounds 5 \
  --question "Review the architecture described in this README. Debate the strongest production architecture. Focus on deterministic vs agentic boundaries, agent/workflow recovery, checkpointing, retries, resumability, idempotency, model and tool failures, partial execution, crash recovery, human escalation, scalability, observability, latency, cost, and maintainability. Use external evidence to challenge assumptions and introduce materially different architecture ideas."
```

With `--readme-only`, the council receives only the repository's root README; it does not receive source files or the repository tree.

## External research

`--research` works **after** the three blind proposals so outside sources do not anchor their initial thinking.

The Research Planner uses Architect C's model to generate targeted search queries from the architecture question and all three blind proposals. Tavily then searches those queries. The evidence pack includes title, URL, relevance score when available, and a bounded content excerpt for each source.

Useful controls:

```bash
--research                 # enable external evidence
--research-queries 4       # 1-6 planned searches; default 4
--research-results 3       # 1-5 results per query; default 3
```

A research-enabled run adds **one LLM call** for query planning. Tavily searches are external search calls, not LLM calls.

## Debate depth and call count

Without external research:

```text
LLM calls = 7 + (3 × rounds)
```

With `--research`:

```text
LLM calls = 8 + (3 × rounds)
```

| Debate rounds | No research | With research |
| ---: | ---: | ---: |
| 1 | 10 | 11 |
| 2 | 13 | 14 |
| 3 (default) | 16 | 17 |
| 4 | 19 | 20 |
| 5 | 22 | 23 |

Each run has three blind proposals, three calls per debate round, three final revisions, and one ADR synthesis. Research mode adds one research-planning LLM call.

## What every debate round covers

Each architect must explicitly address the strongest competing points, external evidence, concessions, rebuttals, shared assumptions, unresolved disagreements, experiments, and its current architecture position. When relevant, every round also evaluates **agent/workflow recovery**: checkpoints, retries, resumability, idempotency, timeouts, fallback models/tools, partial execution, process crashes, and human escalation.

Later rounds do not resend the full repository context. They carry compact debate state. The external evidence pack remains available so source-grounded arguments can continue across rounds.

## Other context modes

Broad repository review:

```bash
arch-council review \
  --repo ../semantic_text2sql_ideal \
  --rounds 3 \
  --question "What is the strongest production architecture for this project?"
```

Git-diff review:

```bash
arch-council review \
  --repo ../semantic_text2sql_ideal \
  --diff-base main \
  --rounds 3 \
  --question "Is this change architecturally safe for production?"
```

`--readme-only` and `--diff-base` are mutually exclusive.

## Output

Each run writes a Markdown report under `reports/` containing the three blind proposals, external research queries and source evidence when enabled, every three-way debate round, three final revisions, and the final ADR.

The ADR contains:

```text
Executive Decision
Recommended Architecture
Why
Decision Matrix
Agent / Workflow Recovery
External Evidence
AGREE
DISAGREE
MINORITY REPORT
NEEDS EXPERIMENT
Risks
Migration Plan
Do Not Change
Revisit Triggers
```

For `NEEDS EXPERIMENT`, the synthesis must provide a hypothesis, test, metric, and success criterion.

## Gateway defaults

```text
LLM base URL: https://api.justwoker.icu
LLM endpoint: /v1/messages
Auth:         Authorization: Bearer <token>
A model:      gpt-5.6-sol
B model:      gpt-5.6-terra
C model:      gpt-5.6-luna
Research:     https://api.tavily.com/search
```

`--model-c` currently uses the same JustWoker gateway as A and B. A true direct Anthropic Claude participant would require a second provider client and separate Anthropic credential.

## Development

```bash
pip install -e '.[dev]'
pytest
ruff check .
```

## Security and cost controls

- API keys are environment variables only and `.env` is ignored.
- Repository context is bounded by `--max-context-chars`.
- Search result excerpts and source count are bounded.
- External search evidence is explicitly treated as untrusted.
- The tool never executes code from the reviewed repository.
- Debate rounds are capped at five; there is no infinite autonomous loop.
- Prefer `--readme-only` for architecture-only discussion and `--diff-base main` for PR-style review.

## License

MIT
