from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str = "https://api.justwoker.icu"
    model_a: str = "gpt-5.6-sol"
    model_b: str = "gpt-5.6-terra"
    model_c: str = "gpt-5.6-luna"
    searxng_url: str = "http://localhost:8080"
    tavily_api_key: str | None = None
    timeout_seconds: int = 180

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        api_key = os.getenv("JUSTWOKER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "JUSTWOKER_API_KEY is missing. Copy .env.example to .env and add your token."
            )
        tavily_api_key = os.getenv("TAVILY_API_KEY", "").strip() or None
        return cls(
            api_key=api_key,
            base_url=os.getenv("ARCH_COUNCIL_BASE_URL", "https://api.justwoker.icu").rstrip("/"),
            model_a=os.getenv("ARCHITECT_A_MODEL", "gpt-5.6-sol"),
            model_b=os.getenv("ARCHITECT_B_MODEL", "gpt-5.6-terra"),
            model_c=os.getenv("ARCHITECT_C_MODEL", "gpt-5.6-luna"),
            searxng_url=os.getenv("SEARXNG_URL", "http://localhost:8080").rstrip("/"),
            tavily_api_key=tavily_api_key,
            timeout_seconds=int(os.getenv("ARCH_COUNCIL_TIMEOUT_SECONDS", "180")),
        )
