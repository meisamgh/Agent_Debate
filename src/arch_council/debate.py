from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .client import AnthropicGatewayClient
from .context import RepositoryContext
from .prompts import (
    ARCHITECT_A_SYSTEM,
    ARCHITECT_B_SYSTEM,
    ARCHITECT_C_SYSTEM,
    CRITIC_SYSTEM,
    RESEARCH_PLANNER_SYSTEM,
    SYNTHESIS_SYSTEM,
    debate_round_prompt,
    proposal_prompt,
    research_query_prompt,
    revision_prompt,
    synthesis_prompt,
)
from .research import ResearchClient, ResearchPack, parse_research_queries


@dataclass(frozen=True)
class DebateRound:
    number: int
    response_a: str
    response_b: str
    response_c: str


@dataclass(frozen=True)
class DebateResult:
    question: str
    model_a: str
    model_b: str
    model_c: str
    rounds_requested: int
    proposal_a: str
    proposal_b: str
    proposal_c: str
    debate_rounds: tuple[DebateRound, ...]
    revision_a: str
    revision_b: str
    revision_c: str
    decision: str
    research_queries: tuple[str, ...] = ()
    research_evidence: str | None = None

    def to_markdown(self, context: RepositoryContext) -> str:
        created = datetime.now(timezone.utc).isoformat()
        files = "\n".join(f"- `{path}`" for path in context.included_files) or "- none"
        rounds = "\n\n".join(
            f"""## Debate Round {round_.number}

### Architect A

{round_.response_a}

### Architect B

{round_.response_b}

### Architect C

{round_.response_c}"""
            for round_ in self.debate_rounds
        )
        research = ""
        if self.research_evidence:
            queries = "\n".join(f"- {query}" for query in self.research_queries)
            research = f"""
## External Research Queries

{queries}

## External Research Evidence

{self.research_evidence}
"""
        return f"""# ArchCouncil Architecture Review

- Created: {created}
- Repository: `{context.root}`
- Context mode: `{context.mode}`
- Context truncated: `{context.truncated}`
- Architect A: `{self.model_a}`
- Architect B: `{self.model_b}`
- Architect C: `{self.model_c}`
- Debate rounds: `{self.rounds_requested}`
- External research: `{bool(self.research_evidence)}`

## Question

{self.question}

## Included files

{files}

## Independent Proposal A

{self.proposal_a}

## Independent Proposal B

{self.proposal_b}

## Independent Proposal C

{self.proposal_c}
{research}
{rounds}

## Final Revised Proposal A

{self.revision_a}

## Final Revised Proposal B

{self.revision_b}

## Final Revised Proposal C

{self.revision_c}

## Final ADR

{self.decision}
"""


class ArchitectureDebate:
    def __init__(
        self,
        client: AnthropicGatewayClient,
        model_a: str,
        model_b: str,
        model_c: str,
        rounds: int = 3,
        research_client: ResearchClient | None = None,
        research_query_count: int = 4,
        research_results_per_query: int = 3,
    ) -> None:
        if not 1 <= rounds <= 5:
            raise ValueError("rounds must be between 1 and 5")
        if not 1 <= research_query_count <= 6:
            raise ValueError("research_query_count must be between 1 and 6")
        if not 1 <= research_results_per_query <= 5:
            raise ValueError("research_results_per_query must be between 1 and 5")
        self.client = client
        self.model_a = model_a
        self.model_b = model_b
        self.model_c = model_c
        self.rounds = rounds
        self.research_client = research_client
        self.research_query_count = research_query_count
        self.research_results_per_query = research_results_per_query

    def _research_after_blind_proposals(
        self,
        *,
        question: str,
        proposal_a: str,
        proposal_b: str,
        proposal_c: str,
    ) -> ResearchPack | None:
        if self.research_client is None:
            return None

        raw_queries = self.client.complete(
            model=self.model_c,
            system=RESEARCH_PLANNER_SYSTEM,
            user=research_query_prompt(
                question,
                proposal_a,
                proposal_b,
                proposal_c,
                max_queries=self.research_query_count,
            ),
            max_tokens=1200,
            temperature=0.2,
        )
        queries = parse_research_queries(raw_queries, max_queries=self.research_query_count)
        if not queries:
            queries = [question]

        return self.research_client.search_many(
            queries,
            max_results_per_query=self.research_results_per_query,
            max_sources=min(18, self.research_query_count * self.research_results_per_query),
        )

    def run(self, *, question: str, context: RepositoryContext) -> DebateResult:
        # Blind proposals: no architect sees another model's first answer or external search.
        # This preserves genuine model diversity before shared evidence can anchor the council.
        proposal_a = self.client.complete(
            model=self.model_a,
            system=ARCHITECT_A_SYSTEM,
            user=proposal_prompt(question, context.text),
        )
        proposal_b = self.client.complete(
            model=self.model_b,
            system=ARCHITECT_B_SYSTEM,
            user=proposal_prompt(question, context.text),
        )
        proposal_c = self.client.complete(
            model=self.model_c,
            system=ARCHITECT_C_SYSTEM,
            user=proposal_prompt(question, context.text),
        )

        research_pack = self._research_after_blind_proposals(
            question=question,
            proposal_a=proposal_a,
            proposal_b=proposal_b,
            proposal_c=proposal_c,
        )
        external_evidence = research_pack.to_prompt() if research_pack else None

        position_a = proposal_a
        position_b = proposal_b
        position_c = proposal_c
        debate_rounds: list[DebateRound] = []

        for round_number in range(1, self.rounds + 1):
            # All three react to the same previous-round state, so no same-round response
            # can anchor another architect or create an ordering advantage.
            repository_evidence = context.text if round_number == 1 else None
            response_a = self.client.complete(
                model=self.model_a,
                system=ARCHITECT_A_SYSTEM + "\n" + CRITIC_SYSTEM,
                user=debate_round_prompt(
                    question,
                    round_number,
                    own_position=position_a,
                    opponent_1_label="Architect B",
                    opponent_1_position=position_b,
                    opponent_2_label="Architect C",
                    opponent_2_position=position_c,
                    context=repository_evidence,
                    external_evidence=external_evidence,
                ),
            )
            response_b = self.client.complete(
                model=self.model_b,
                system=ARCHITECT_B_SYSTEM + "\n" + CRITIC_SYSTEM,
                user=debate_round_prompt(
                    question,
                    round_number,
                    own_position=position_b,
                    opponent_1_label="Architect A",
                    opponent_1_position=position_a,
                    opponent_2_label="Architect C",
                    opponent_2_position=position_c,
                    context=repository_evidence,
                    external_evidence=external_evidence,
                ),
            )
            response_c = self.client.complete(
                model=self.model_c,
                system=ARCHITECT_C_SYSTEM + "\n" + CRITIC_SYSTEM,
                user=debate_round_prompt(
                    question,
                    round_number,
                    own_position=position_c,
                    opponent_1_label="Architect A",
                    opponent_1_position=position_a,
                    opponent_2_label="Architect B",
                    opponent_2_position=position_b,
                    context=repository_evidence,
                    external_evidence=external_evidence,
                ),
            )
            debate_rounds.append(
                DebateRound(
                    number=round_number,
                    response_a=response_a,
                    response_b=response_b,
                    response_c=response_c,
                )
            )
            position_a = response_a
            position_b = response_b
            position_c = response_c

        revision_a = self.client.complete(
            model=self.model_a,
            system=ARCHITECT_A_SYSTEM,
            user=revision_prompt(
                question,
                proposal_a,
                latest_own_position=position_a,
                opponent_1_label="Architect B",
                opponent_1_position=position_b,
                opponent_2_label="Architect C",
                opponent_2_position=position_c,
                context=context.text,
                external_evidence=external_evidence,
            ),
        )
        revision_b = self.client.complete(
            model=self.model_b,
            system=ARCHITECT_B_SYSTEM,
            user=revision_prompt(
                question,
                proposal_b,
                latest_own_position=position_b,
                opponent_1_label="Architect A",
                opponent_1_position=position_a,
                opponent_2_label="Architect C",
                opponent_2_position=position_c,
                context=context.text,
                external_evidence=external_evidence,
            ),
        )
        revision_c = self.client.complete(
            model=self.model_c,
            system=ARCHITECT_C_SYSTEM,
            user=revision_prompt(
                question,
                proposal_c,
                latest_own_position=position_c,
                opponent_1_label="Architect A",
                opponent_1_position=position_a,
                opponent_2_label="Architect B",
                opponent_2_position=position_b,
                context=context.text,
                external_evidence=external_evidence,
            ),
        )

        transcript = "\n\n".join(
            f"""### Round {round_.number} — Architect A
{round_.response_a}

### Round {round_.number} — Architect B
{round_.response_b}

### Round {round_.number} — Architect C
{round_.response_c}"""
            for round_ in debate_rounds
        )

        decision = self.client.complete(
            model=self.model_a,
            system=SYNTHESIS_SYSTEM,
            user=synthesis_prompt(
                question,
                proposal_a,
                proposal_b,
                proposal_c,
                transcript,
                revision_a,
                revision_b,
                revision_c,
                external_evidence=external_evidence,
            ),
            max_tokens=8000,
            temperature=0.1,
        )

        return DebateResult(
            question=question,
            model_a=self.model_a,
            model_b=self.model_b,
            model_c=self.model_c,
            rounds_requested=self.rounds,
            proposal_a=proposal_a,
            proposal_b=proposal_b,
            proposal_c=proposal_c,
            debate_rounds=tuple(debate_rounds),
            revision_a=revision_a,
            revision_b=revision_b,
            revision_c=revision_c,
            decision=decision,
            research_queries=research_pack.queries if research_pack else (),
            research_evidence=external_evidence,
        )


def write_report(result: DebateResult, context: RepositoryContext, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"architecture-review-{stamp}.md"
    path.write_text(result.to_markdown(context), encoding="utf-8")
    return path
