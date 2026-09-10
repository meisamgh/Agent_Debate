from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .client import AnthropicGatewayClient
from .context import RepositoryContext
from .prompts import (
    ARCHITECT_A_SYSTEM,
    ARCHITECT_B_SYSTEM,
    CRITIC_SYSTEM,
    SYNTHESIS_SYSTEM,
    debate_round_prompt,
    proposal_prompt,
    revision_prompt,
    synthesis_prompt,
)


@dataclass(frozen=True)
class DebateRound:
    number: int
    response_a: str
    response_b: str


@dataclass(frozen=True)
class DebateResult:
    question: str
    model_a: str
    model_b: str
    rounds_requested: int
    proposal_a: str
    proposal_b: str
    debate_rounds: tuple[DebateRound, ...]
    revision_a: str
    revision_b: str
    decision: str

    @property
    def critique_a(self) -> str:
        return self.debate_rounds[0].response_a

    @property
    def critique_b(self) -> str:
        return self.debate_rounds[0].response_b

    def to_markdown(self, context: RepositoryContext) -> str:
        created = datetime.now(timezone.utc).isoformat()
        files = "\n".join(f"- `{path}`" for path in context.included_files) or "- none"
        rounds = "\n\n".join(
            f"""## Debate Round {round_.number}

### Architect A

{round_.response_a}

### Architect B

{round_.response_b}"""
            for round_ in self.debate_rounds
        )
        return f"""# ArchCouncil Architecture Review

- Created: {created}
- Repository: `{context.root}`
- Context mode: `{context.mode}`
- Context truncated: `{context.truncated}`
- Architect A: `{self.model_a}`
- Architect B: `{self.model_b}`
- Debate rounds: `{self.rounds_requested}`

## Question

{self.question}

## Included files

{files}

## Independent Proposal A

{self.proposal_a}

## Independent Proposal B

{self.proposal_b}

{rounds}

## Final Revised Proposal A

{self.revision_a}

## Final Revised Proposal B

{self.revision_b}

## Final ADR

{self.decision}
"""


class ArchitectureDebate:
    def __init__(
        self,
        client: AnthropicGatewayClient,
        model_a: str,
        model_b: str,
        rounds: int = 3,
    ) -> None:
        if not 1 <= rounds <= 5:
            raise ValueError("rounds must be between 1 and 5")
        self.client = client
        self.model_a = model_a
        self.model_b = model_b
        self.rounds = rounds

    def run(self, *, question: str, context: RepositoryContext) -> DebateResult:
        # Blind first proposals: neither architect sees the other's answer.
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

        position_a = proposal_a
        position_b = proposal_b
        debate_rounds: list[DebateRound] = []

        for round_number in range(1, self.rounds + 1):
            # Both architects react to the same previous-round state. Architect B does not get
            # to see A's same-round response, which avoids an ordering advantage.
            evidence = context.text if round_number == 1 else None
            response_a = self.client.complete(
                model=self.model_a,
                system=ARCHITECT_A_SYSTEM + "\n" + CRITIC_SYSTEM,
                user=debate_round_prompt(
                    question,
                    round_number,
                    own_position=position_a,
                    opponent_position=position_b,
                    context=evidence,
                ),
            )
            response_b = self.client.complete(
                model=self.model_b,
                system=ARCHITECT_B_SYSTEM + "\n" + CRITIC_SYSTEM,
                user=debate_round_prompt(
                    question,
                    round_number,
                    own_position=position_b,
                    opponent_position=position_a,
                    context=evidence,
                ),
            )
            debate_rounds.append(
                DebateRound(
                    number=round_number,
                    response_a=response_a,
                    response_b=response_b,
                )
            )
            position_a = response_a
            position_b = response_b

        revision_a = self.client.complete(
            model=self.model_a,
            system=ARCHITECT_A_SYSTEM,
            user=revision_prompt(
                question,
                proposal_a,
                latest_own_position=position_a,
                latest_opponent_position=position_b,
                context=context.text,
            ),
        )
        revision_b = self.client.complete(
            model=self.model_b,
            system=ARCHITECT_B_SYSTEM,
            user=revision_prompt(
                question,
                proposal_b,
                latest_own_position=position_b,
                latest_opponent_position=position_a,
                context=context.text,
            ),
        )

        transcript = "\n\n".join(
            f"""### Round {round_.number} — Architect A
{round_.response_a}

### Round {round_.number} — Architect B
{round_.response_b}"""
            for round_ in debate_rounds
        )

        # Architect A acts as ADR editor only after both sides have revised. It is instructed
        # to preserve disagreement rather than manufacture consensus.
        decision = self.client.complete(
            model=self.model_a,
            system=SYNTHESIS_SYSTEM,
            user=synthesis_prompt(
                question,
                proposal_a,
                proposal_b,
                transcript,
                revision_a,
                revision_b,
            ),
            max_tokens=7000,
            temperature=0.1,
        )

        return DebateResult(
            question=question,
            model_a=self.model_a,
            model_b=self.model_b,
            rounds_requested=self.rounds,
            proposal_a=proposal_a,
            proposal_b=proposal_b,
            debate_rounds=tuple(debate_rounds),
            revision_a=revision_a,
            revision_b=revision_b,
            decision=decision,
        )


def write_report(result: DebateResult, context: RepositoryContext, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"architecture-review-{stamp}.md"
    path.write_text(result.to_markdown(context), encoding="utf-8")
    return path
