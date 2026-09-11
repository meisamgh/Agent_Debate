# ArchCouncil

**ArchCouncil** is an evidence-grounded architecture review tool for software repositories. It has two complementary modes:

- a deterministic, bounded **three-model architecture council** that debates and produces an ADR;
- a bounded **tool-using architecture agent** for interactive follow-up questions.

It can share broad repository context, a git diff, or **only the root README**. External research is provider-agnostic: **SearXNG is the default free/self-hosted provider**, while Tavily remains optional. The LLM gateway defaults to the JustWoker Anthropic-compatible `POST /v1/messages` endpoint.

## Council roles

- **Architect A — Production Pragmatist (`gpt-5.6-sol`)**: reliability, simplicity, cost, debuggability, bounded workflows.
- **Architect B — Scaling Challenger (`gpt-5.6-terra`)**: scalability, security, concurrency, observability, failure isolation, future constraints.
- **Architect C — Alternative / Mutation Architect (`gpt-5.6-luna`)**: challenges shared assumptions and proposes materially different architectures.

The council does not use simple majority voting. A strong minority position is preserved when its evidence is better.

## Council workflow

```text
README.md / repository / git diff
              |
              v
      3 blind proposals
      A       B       C
              |
              v
       Research Planner
              |
      disputed / uncertain claims
              |
              v
      ResearchProvider interface
          /             \
         v               v
   local SearXNG      Tavily (optional)
      default/free
         \               /
          v             v
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

External sources are treated as **untrusted evidence**, not truth.

## Interactive architecture agent

`arch-council chat` is a real bounded tool loop rather than just a chat prompt. With `--research`, the model decides whether external evidence is needed, chooses a focused search query, observes SearXNG/Tavily results, and then decides whether to search again or answer.

```text
user question
    |
    v
agent decision
    |--------------------|
    |                    |
 ANSWER                SEARCH
                         |
                         v
                    SearXNG tool
                         |
                         v
                    observation
                         |
                         v
                  agent decision
                         |
                  ... bounded ...
                         |
                         v
                  final synthesis
```

The default budget is **2 search actions**. If both are used, the agent performs one forced final synthesis, so the default maximum is **3 LLM calls per question**. The loop cannot run indefinitely.

Search failures are converted into observations so the agent can still answer from repository evidence instead of crashing solely because the search tool failed.

Run it with local SearXNG:

```bash
arch-council chat \
  --repo "/Users/meisam/Documents/text-to-sql/semantic_text2sql_ideal" \
  --readme-only \
  --research \
  --research-provider searxng \
  --max-tool-steps 2
```

Useful agent controls:

```bash
--research                         # give the agent a web-search tool
--research-provider searxng        # default provider
--searxng-url http://localhost:8080
--max-tool-steps 2                 # 0-5; default 2
```

Without `--research`, agent chat uses repository evidence and one LLM call per question.

The three council participants in `review` remain bounded reviewers; they are not independently autonomous agents. This keeps the debate reproducible and its call count predictable.

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
SEARXNG_URL=http://localhost:8080
```

Never commit `.env`.

## Start the integrated free SearXNG service

ArchCouncil includes `docker-compose.searxng.yml` and `searxng/settings.yml`. The supplied SearXNG configuration enables JSON output because ArchCouncil consumes the `/search?format=json` API.

```bash
docker compose -f docker-compose.searxng.yml up -d
```

The service binds only to `127.0.0.1:8080` by default.

Check that JSON search works:

```bash
curl 'http://localhost:8080/search?q=agent+recovery&format=json'
```

Stop it with:

```bash
docker compose -f docker-compose.searxng.yml down
```

## Recommended architecture-only council run

```bash
arch-council review \
  --repo "/Users/meisam/Documents/text-to-sql/semantic_text2sql_ideal" \
  --readme-only \
  --research \
  --research-provider searxng \
  --rounds 3 \
  --question "Review the architecture described in this README. Debate the strongest production architecture, including deterministic vs agentic boundaries, recovery, checkpointing, retries, resumability, idempotency, model and tool failures, scalability, observability, latency, cost, and maintainability."
```

Because `searxng` is the default research provider, `--research-provider searxng` can be omitted.

With `--readme-only`, the council receives only the repository's root README; it does not receive source files or the repository tree.

## External research providers

Council research happens **after** the three blind proposals so outside sources do not anchor the models' initial thinking. The Research Planner uses Architect C's model to generate targeted search queries from the architecture question and all three blind proposals.

Useful review controls:

```bash
--research
--research-provider searxng
--searxng-url http://localhost:8080
--research-queries 4
--research-results 3
```

Many public SearXNG instances disable JSON responses. A self-hosted instance is recommended for predictable API access.

### Optional Tavily provider

```env
TAVILY_API_KEY=your_tavily_key
```

```bash
arch-council review \
  --repo . \
  --readme-only \
  --research \
  --research-provider tavily \
  --question "What is the strongest production architecture?"
```

## Debate depth and call count

Without external research:

```text
LLM calls = 7 + (3 × rounds)
```

With research:

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

Each council run has three blind proposals, three calls per debate round, three final revisions, and one ADR synthesis. Research mode adds one research-planning LLM call. Search-provider requests are separate from LLM calls.

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

Each council run writes a Markdown report under `reports/` containing the three blind proposals, external research queries and source evidence when enabled, every three-way debate round, three final revisions, and the final ADR.

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

## Gateway and research defaults

```text
LLM base URL:       https://api.justwoker.icu
LLM endpoint:       /v1/messages
A model:            gpt-5.6-sol
B model:            gpt-5.6-terra
C model:            gpt-5.6-luna
Research provider:  searxng
SearXNG URL:        http://localhost:8080
Tavily:             optional
```

A true direct Anthropic Claude council participant would require a second provider client and separate Anthropic credential.

## Development

```bash
pip install -e '.[dev]'
pytest
ruff check .
```

## Security and cost controls

- API keys are environment variables only and `.env` is ignored.
- Local SearXNG binds to loopback (`127.0.0.1`) by default.
- Repository context is bounded by `--max-context-chars`.
- Search result excerpts and source count are bounded.
- External search evidence is explicitly treated as untrusted.
- Agent search steps are capped; there is no infinite autonomous loop.
- Debate rounds are capped at five.
- The tool never executes code from the reviewed repository.
- Prefer `--readme-only` for architecture-only discussion and `--diff-base main` for PR-style review.

## License

MIT
