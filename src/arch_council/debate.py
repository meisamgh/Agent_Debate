from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .client import AnthropicGatewayClient
from .context import RepositoryContext
from .governance import (
    ArbiterScorecard,
    EvidenceRequest,
    dedupe_evidence_requests,
    parse_arbiter_scorecard,
    parse_debate_signal,
    parse_evidence_gaps,
    should_continue_debate,
)
from .prompts import (
    ADR_WRITER_SYSTEM,
    ARCHITECT_A_SYSTEM,
    ARCHITECT_B_SYSTEM,
    ARCHITECT_C_SYSTEM,
    ARBITER_SCORE_SYSTEM,
    CRITIC_SYSTEM,
    EVIDENCE_COVERAGE_SYSTEM,
    RESEARCH_PLANNER_SYSTEM,
    adr_prompt,
    arbiter_score_prompt,
    debate_round_prompt,
    evidence_coverage_prompt,
    proposal_prompt,
    research_query_prompt,
    revision_prompt,
)
from .research import (
    EvidenceInspector,
    ResearchClient,
    ResearchPack,
    merge_research_packs,
    parse_research_queries,
)


@dataclass(frozen=True)
class DebateRound:
    number: int
    response_a: str
    response_b: str
    response_c: str
    continued: bool


@dataclass(frozen=True)
class DebateResult:
    question: str
    model_a: str
    model_b: str
    model_c: str
    arbiter_model: str
    rounds_requested: int
    rounds_completed: int
    proposal_a: str
    proposal_b: str
    proposal_c: str
    debate_rounds: tuple[DebateRound, ...]
    revision_a: str
    revision_b: str
    revision_c: str
    decision: str
    arbiter_scorecard: ArbiterScorecard
    research_queries: tuple[str, ...] = ()
    research_evidence: str | None = None
    coverage_requests: tuple[EvidenceRequest, ...] = ()

    def to_markdown(self, context: RepositoryContext) -> str:
        created = datetime.now(UTC).isoformat()
        files = "\n".join(f"- `{path}`" for path in context.included_files) or "- none"
        rounds = "\n\n".join(
            f"""## Debate Round {round_.number}

- Continued after this round: `{round_.continued}`

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
            coverage = "\n".join(
                f"- `{request.category}` ({request.priority}): {request.question}"
                for request in self.coverage_requests
            ) or "- none"
            research = f"""
## External Research Queries

{queries}

## Evidence Coverage Requests

{coverage}

## External Research Evidence

{self.research_evidence}
"""
        score_rows = "\n".join(
            f"- Candidate {candidate}: {score:.4f}"
            for candidate, score in self.arbiter_scorecard.weighted_totals.items()
        )
        return f"""# ArchCouncil Architecture Review

- Created: {created}
- Repository: `{context.root}`
- Context mode: `{context.mode}`
- Context truncated: `{context.truncated}`
- Architect A: `{self.model_a}`
- Architect B: `{self.model_b}`
- Architect C: `{self.model_c}`
- Arbiter model: `{self.arbiter_model}`
- Maximum debate rounds: `{self.rounds_requested}`
- Debate rounds completed: `{self.rounds_completed}`
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

## Deterministic Weighted Arbitration

Winner: **Candidate {self.arbiter_scorecard.winner}**

{score_rows}

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
        arbiter_model: str | None = None,
        evidence_inspector: EvidenceInspector | None = None,
        evidence_inspection_limit: int = 4,
        evidence_request_limit: int = 4,
    ) -> None:
        if not 1 <= rounds <= 3:
            raise ValueError("rounds must be between 1 and 3")
        if not 1 <= research_query_count <= 6:
            raise ValueError("research_query_count must be between 1 and 6")
        if not 1 <= research_results_per_query <= 5:
            raise ValueError("research_results_per_query must be between 1 and 5")
        if not 0 <= evidence_inspection_limit <= 8:
            raise ValueError("evidence_inspection_limit must be between 0 and 8")
        if not 1 <= evidence_request_limit <= 8:
            raise ValueError("evidence_request_limit must be between 1 and 8")
        self.client = client
        self.model_a = model_a
        self.model_b = model_b
        self.model_c = model_c
        self.arbiter_model = arbiter_model or model_a
        self.rounds = rounds
        self.research_client = research_client
        self.research_query_count = research_query_count
        self.research_results_per_query = research_results_per_query
        self.evidence_inspector = evidence_inspector or EvidenceInspector()
        self.evidence_inspection_limit = evidence_inspection_limit
        self.evidence_request_limit = evidence_request_limit

    def _inspect(self, pack: ResearchPack | None) -> ResearchPack | None:
        if pack is None or self.evidence_inspection_limit == 0:
            return pack
        return self.evidence_inspector.inspect_pack(
            pack,
            max_sources=self.evidence_inspection_limit,
        )

    def _initial_research(
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
        pack = self.research_client.search_many(
            queries,
            max_results_per_query=self.research_results_per_query,
            max_sources=min(18, self.research_query_count * self.research_results_per_query),
        )
        return self._inspect(pack)

    def _coverage_check(
        self,
        *,
        question: str,
        proposals: tuple[str, str, str],
        research_pack: ResearchPack,
    ) -> tuple[EvidenceRequest, ...]:
        evidence = research_pack.to_prompt()
        systems = (ARCHITECT_A_SYSTEM, ARCHITECT_B_SYSTEM, ARCHITECT_C_SYSTEM)
        models = (self.model_a, self.model_b, self.model_c)
        requests: list[EvidenceRequest] = []
        for model, system, proposal in zip(models, systems, proposals, strict=True):
            raw = self.client.complete(
                model=model,
                system=system + "\n" + EVIDENCE_COVERAGE_SYSTEM,
                user=evidence_coverage_prompt(question, proposal, evidence),
                max_tokens=1000,
                temperature=0.1,
            )
            requests.extend(parse_evidence_gaps(raw))
        return dedupe_evidence_requests(requests, max_requests=self.evidence_request_limit)

    def _research_requests(
        self,
        requests: tuple[EvidenceRequest, ...],
    ) -> ResearchPack | None:
        if self.research_client is None or not requests:
            return None
        queries = [request.question for request in requests]
        pack = self.research_client.search_many(
            queries,
            max_results_per_query=self.research_results_per_query,
            max_sources=min(12, len(queries) * self.research_results_per_query),
        )
        return self._inspect(pack)

    def run(self, *, question: str, context: RepositoryContext) -> DebateResult:
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

        research_pack = self._initial_research(
            question=question,
            proposal_a=proposal_a,
            proposal_b=proposal_b,
            proposal_c=proposal_c,
        )
        coverage_requests: tuple[EvidenceRequest, ...] = ()
        if research_pack is not None:
            coverage_requests = self._coverage_check(
                question=question,
                proposals=(proposal_a, proposal_b, proposal_c),
                research_pack=research_pack,
            )
            targeted = self._research_requests(coverage_requests)
            research_pack = merge_research_packs(research_pack, targeted)

        position_a = proposal_a
        position_b = proposal_b
        position_c = proposal_c
        debate_rounds: list[DebateRound] = []

        for round_number in range(1, self.rounds + 1):
            repository_evidence = context.text if round_number == 1 else None
            external_evidence = research_pack.to_prompt() if research_pack else None
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
            signals = tuple(
                parse_debate_signal(response)
                for response in (response_a, response_b, response_c)
            )
            continue_debate = should_continue_debate(
                round_number=round_number,
                max_rounds=self.rounds,
                signals=signals,
            )
            debate_rounds.append(
                DebateRound(
                    number=round_number,
                    response_a=response_a,
                    response_b=response_b,
                    response_c=response_c,
                    continued=continue_debate,
                )
            )
            position_a, position_b, position_c = response_a, response_b, response_c

            if not continue_debate:
                break

            round_requests = dedupe_evidence_requests(
                [request for signal in signals for request in signal.evidence_requests],
                max_requests=self.evidence_request_limit,
            )
            targeted = self._research_requests(round_requests)
            research_pack = merge_research_packs(research_pack, targeted)

        external_evidence = research_pack.to_prompt() if research_pack else None
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

        score_raw = self.client.complete(
            model=self.arbiter_model,
            system=ARBITER_SCORE_SYSTEM,
            user=arbiter_score_prompt(
                question,
                revision_a,
                revision_b,
                revision_c,
                context.text,
                external_evidence,
            ),
            max_tokens=2500,
            temperature=0.0,
        )
        scorecard = parse_arbiter_scorecard(score_raw)
        score_summary = json.dumps(
            {
                "weights_applied_by_code": True,
                "scores": scorecard.scores,
                "weighted_totals": scorecard.weighted_totals,
                "winner": scorecard.winner,
            },
            indent=2,
            sort_keys=True,
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
            model=self.arbiter_model,
            system=ADR_WRITER_SYSTEM,
            user=adr_prompt(
                question,
                proposal_a,
                proposal_b,
                proposal_c,
                transcript,
                revision_a,
                revision_b,
                revision_c,
                score_summary,
                scorecard.winner,
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
            arbiter_model=self.arbiter_model,
            rounds_requested=self.rounds,
            rounds_completed=len(debate_rounds),
            proposal_a=proposal_a,
            proposal_b=proposal_b,
            proposal_c=proposal_c,
            debate_rounds=tuple(debate_rounds),
            revision_a=revision_a,
            revision_b=revision_b,
            revision_c=revision_c,
            decision=decision,
            arbiter_scorecard=scorecard,
            research_queries=research_pack.queries if research_pack else (),
            research_evidence=external_evidence,
            coverage_requests=coverage_requests,
        )


def write_report(result: DebateResult, context: RepositoryContext, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"architecture-review-{stamp}.md"
    path.write_text(result.to_markdown(context), encoding="utf-8")
    return path
