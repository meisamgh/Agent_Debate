from arch_council.research import ResearchPack, ResearchSource, parse_research_queries


def test_parse_research_queries_accepts_bullets_and_prefixes() -> None:
    raw = """\
QUERY: durable execution agent checkpoint recovery
- LangGraph persistence checkpoint retry semantics
* Temporal workflow idempotency activity retries
"""

    queries = parse_research_queries(raw, max_queries=3)

    assert queries == [
        "durable execution agent checkpoint recovery",
        "LangGraph persistence checkpoint retry semantics",
        "Temporal workflow idempotency activity retries",
    ]


def test_research_pack_keeps_source_ids_and_urls() -> None:
    pack = ResearchPack(
        queries=("agent recovery",),
        sources=(
            ResearchSource(
                source_id="S1",
                query="agent recovery",
                title="Example source",
                url="https://example.com/evidence",
                content="Checkpointed workflows can resume after a process failure.",
                score=0.91,
            ),
        ),
    )

    prompt = pack.to_prompt()

    assert "[S1]" in prompt
    assert "https://example.com/evidence" in prompt
    assert "Checkpointed workflows" in prompt
