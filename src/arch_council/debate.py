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
    critique_prompt,
    proposal_prompt,
    revision_prompt,
    synthesis_prompt,
)


@dataclass(frozen=True)
class DebateResult:
    question: str
    model_a: str
    model_b: str
    proposal_a: str
    proposal_b: str
    critique_a: str
    critique_b: str
    revision_a: str
    revision_b: str
    decision: str

    def to_markdown(self, context: RepositoryContext) -> str:
        created = datetime.now(timezone.utc).isoformat()
        files = "\n".join(f"- `{path}`" for path in context.included_files) or "- none"
        return f"""# ArchCouncil Architecture Review

- Created: {created}
- Repository: `{context.root}`
- Context mode: `{context.mode}`
- Context truncated: `{context.truncated}`
- Architect A: `{self.model_a}`
- Architect B: `{self.model_b}`

## Question

{self.question}

## Included files

{files}

## Independent Proposal A

{self.proposal_a}

## Independent Proposal B

{self.proposal_b}

## A Critiques B

{self.critique_a}

## B Critiques A

{self.critique_b}

## Revised Proposal A

{self.revision_a}

## Revised Proposal B

{self.revision_b}

## Final ADR

{self.decision}
"""


class ArchitectureDebate:
    def __init__(self, client: AnthropicGatewayClient, model_a: str, model_b: str) -> None:
        self.client = client
        self.model_a = model_a
        self.model_b = model_b

    def run(self, *, question: str, context: RepositoryContext) -> DebateResult:
        # Blind first round: neither architect sees the other's first proposal.
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

        critique_a = self.client.complete(
            model=self.model_a,
            system=ARCHITECT_A_SYSTEM + "\n" + CRITIC_SYSTEM,
            user=critique_prompt(question, proposal_a, proposal_b, context.text),
        )
        critique_b = self.client.complete(
            model=self.model_b,
            system=ARCHITECT_B_SYSTEM + "\n" + CRITIC_SYSTEM,
            user=critique_prompt(question, proposal_b, proposal_a, context.text),
        )

        revision_a = self.client.complete(
            model=self.model_a,
            system=ARCHITECT_A_SYSTEM,
            user=revision_prompt(question, proposal_a, critique_a, critique_b, context.text),
        )
        revision_b = self.client.complete(
            model=self.model_b,
            system=ARCHITECT_B_SYSTEM,
            user=revision_prompt(question, proposal_b, critique_b, critique_a, context.text),
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
                critique_a,
                critique_b,
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
            proposal_a=proposal_a,
            proposal_b=proposal_b,
            critique_a=critique_a,
            critique_b=critique_b,
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
