from arch_council.agent import ArchitectureAgent
from arch_council.context import RepositoryContext


class FakeClient:
    def complete(self, **kwargs):
        return f"answer to: {kwargs['user'].split('USER:')[-1].strip()}"


def test_agent_preserves_conversation_history() -> None:
    context = RepositoryContext(root=__import__('pathlib').Path('.'), text='README evidence', included_files=(), truncated=False, mode='readme')
    agent = ArchitectureAgent(FakeClient(), 'model', context)
    first = agent.ask('What is the current boundary?')
    second = agent.ask('What should change?')
    assert 'current boundary' in first
    assert 'What is the current boundary?' in second or len(agent.history) == 4
