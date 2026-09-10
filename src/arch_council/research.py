from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import requests


class ResearchError(RuntimeError):
    """Raised when external research cannot be completed safely."""


@dataclass(frozen=True)
class ResearchSource:
    source_id: str
    query: str
    title: str
    url: str
    content: str
    score: float | None = None


@dataclass(frozen=True)
class ResearchPack:
    queries: tuple[str, ...]
    sources: tuple[ResearchSource, ...]

    def to_prompt(self) -> str:
        if not self.sources:
            return "No external research sources were returned."

        blocks: list[str] = []
        for source in self.sources:
            score = "" if source.score is None else f"\nRelevance score: {source.score:.3f}"
            blocks.append(
                f"""[{source.source_id}]
Query: {source.query}
Title: {source.title}
URL: {source.url}{score}
Evidence: {source.content}"""
            )
        return "\n\n".join(blocks)


class ResearchClient(Protocol):
    """Provider-neutral interface consumed by the architecture debate."""

    def search_many(
        self,
        queries: list[str] | tuple[str, ...],
        *,
        max_results_per_query: int = 3,
        max_sources: int = 12,
        max_content_chars: int = 1_200,
    ) -> ResearchPack: ...


class _BaseSearchClient:
    """Shared result packing for search providers."""

    def search(self, query: str, *, max_results: int = 3) -> list[dict[str, object]]:
        raise NotImplementedError

    def search_many(
        self,
        queries: list[str] | tuple[str, ...],
        *,
        max_results_per_query: int = 3,
        max_sources: int = 12,
        max_content_chars: int = 1_200,
    ) -> ResearchPack:
        unique_queries = tuple(dict.fromkeys(q.strip() for q in queries if q.strip()))
        sources: list[ResearchSource] = []
        seen_urls: set[str] = set()

        for query in unique_queries:
            for item in self.search(query, max_results=max_results_per_query):
                url = str(item.get("url", "")).strip()
                if not url or url in seen_urls:
                    continue
                title = str(item.get("title", url)).strip() or url
                content = str(item.get("content", "")).strip()
                if len(content) > max_content_chars:
                    content = content[:max_content_chars] + " ... [truncated]"
                raw_score = item.get("score")
                score = float(raw_score) if isinstance(raw_score, (int, float)) else None
                source_id = f"S{len(sources) + 1}"
                sources.append(
                    ResearchSource(
                        source_id=source_id,
                        query=query,
                        title=title,
                        url=url,
                        content=content,
                        score=score,
                    )
                )
                seen_urls.add(url)
                if len(sources) >= max_sources:
                    return ResearchPack(queries=unique_queries, sources=tuple(sources))

        return ResearchPack(queries=unique_queries, sources=tuple(sources))


class SearXNGResearchClient(_BaseSearchClient):
    """Research client for a SearXNG instance using its JSON search API.

    No search-provider API key is required. The target SearXNG instance must allow
    JSON output (`search.formats` includes `json`). A local self-hosted instance is
    recommended because many public instances disable machine-readable output.
    """

    def __init__(self, base_url: str = "http://localhost:8080", timeout_seconds: int = 60) -> None:
        base_url = base_url.strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ResearchError("SEARXNG_URL must start with http:// or https://")
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, *, max_results: int = 3) -> list[dict[str, object]]:
        try:
            response = requests.get(
                f"{self.base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "categories": "general",
                    "language": "all",
                    "safesearch": 1,
                },
                headers={"Accept": "application/json"},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ResearchError(
                f"SearXNG request failed for {self.base_url}: {exc}. "
                "Make sure the SearXNG service is running."
            ) from exc

        if response.status_code != 200:
            preview = response.text[:500].replace("\n", " ")
            hint = ""
            if response.status_code == 403:
                hint = " Ensure `json` is enabled under `search.formats` in SearXNG settings.yml."
            raise ResearchError(
                f"SearXNG search returned HTTP {response.status_code}: {preview}.{hint}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ResearchError(
                "SearXNG returned non-JSON content. Ensure the instance supports format=json."
            ) from exc

        results = payload.get("results", [])
        if not isinstance(results, list):
            raise ResearchError("SearXNG response did not contain a results list")

        normalized: list[dict[str, object]] = []
        for item in results[:max_results]:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score"),
                }
            )
        return normalized


class TavilyResearchClient(_BaseSearchClient):
    """Optional Tavily Search API client using requests only."""

    def __init__(self, api_key: str, timeout_seconds: int = 60) -> None:
        api_key = api_key.strip()
        if not api_key:
            raise ResearchError(
                "TAVILY_API_KEY is missing. Add it to .env or choose --research-provider searxng."
            )
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, *, max_results: int = 3) -> list[dict[str, object]]:
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                    "include_answer": False,
                    "include_raw_content": False,
                },
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ResearchError(f"External research request failed: {exc}") from exc

        if response.status_code != 200:
            preview = response.text[:500].replace("\n", " ")
            raise ResearchError(
                f"Tavily search returned HTTP {response.status_code}: {preview}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ResearchError("Tavily returned a non-JSON response") from exc

        results = payload.get("results", [])
        if not isinstance(results, list):
            raise ResearchError("Tavily response did not contain a results list")
        return [item for item in results if isinstance(item, dict)]


def parse_research_queries(text: str, *, max_queries: int = 4) -> list[str]:
    """Parse one-query-per-line LLM output defensively.

    Accepts optional bullets or `QUERY:` prefixes and rejects obviously unusable lines.
    """
    queries: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for prefix in ("- ", "* ", "• "):
            if line.startswith(prefix):
                line = line[len(prefix) :].strip()
        if line.upper().startswith("QUERY:"):
            line = line.split(":", 1)[1].strip()
        if len(line) < 8 or len(line) > 300:
            continue
        if line.startswith("#"):
            continue
        if line not in queries:
            queries.append(line)
        if len(queries) >= max_queries:
            break
    return queries
