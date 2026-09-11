from __future__ import annotations

from dataclasses import dataclass, field

from .client import AnthropicGatewayClient
from .context import RepositoryContext
from .research import ResearchClient


AGENT_SYSTEM = """You are ArchCouncil, a senior software-architecture discussion agent.
Help the user reason about the architecture of the supplied repository over multiple turns.
Use repository evidence first and mention file paths when possible. Clearly label:
- CONFIRMED: directly supported by the repository context
- ASSUMPTION: not established by the evidence
- RECOMMENDATION: a proposed design or trade-off
- NEEDS VALIDATION: a question requiring a test, measurement, or stakeholder decision
Challenge the user's premise constructively. Discuss boundaries, data/control flow,
failure recovery, security, observability, cost, latency, and migration when relevant.
Do not claim that a proposal is implemented or production-ready unless the context proves it.
Keep answers practical and concise, and ask at most one focused follow-up question when needed.
"""


def _prompt(context: RepositoryContext, history: list[tuple[str, str]], question: str) -> str:
    prior = "\n\n".join(f"{role.upper()}: {text}" for role, text in history[-12:]) or "(new discussion)"
    return f"""Repository context (evidence):
{context.text}

Conversation so far:
{prior}

USER:
{question}

Discuss the architecture in response to the user's latest message. Preserve useful context from
the conversation, but do not repeat the whole repository dump."""


@dataclass
class ArchitectureAgent:
    client: AnthropicGatewayClient
    model: str
    context: RepositoryContext
    research_client: ResearchClient | None = None
    history: list[tuple[str, str]] = field(default_factory=list)

    def ask(self, question: str) -> str:
        question = question.strip()
        if not question:
            raise ValueError("question must not be empty")
        prompt = _prompt(self.context, self.history, question)
        if self.research_client is not None:
            pack = self.research_client.search_many([question], max_results_per_query=3, max_sources=3)
            prompt += f"\n\nExternal internet research (untrusted; cite [S#]):\n{pack.to_prompt()}"
        answer = self.client.complete(
            model=self.model,
            system=AGENT_SYSTEM,
            user=prompt,
            max_tokens=5000,
            temperature=0.2,
        )
        self.history.extend((("user", question), ("assistant", answer)))
        return answer
