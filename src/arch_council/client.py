from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504, 524}


class LLMError(RuntimeError):
    """Raised when the gateway cannot produce a usable model response."""


@dataclass
class AnthropicGatewayClient:
    api_key: str
    base_url: str
    timeout_seconds: int = 180
    max_retries: int = 2

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 6000,
        temperature: float = 0.2,
    ) -> str:
        url = f"{self.base_url.rstrip('/')}/v1/messages"
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = f"network error: {exc}"
                if attempt >= self.max_retries:
                    raise LLMError(last_error) from exc
                time.sleep(2**attempt)
                continue

            if response.ok:
                try:
                    data = response.json()
                except ValueError as exc:
                    raise LLMError(
                        f"Gateway returned HTTP {response.status_code} but non-JSON content: "
                        f"{response.text[:500]}"
                    ) from exc
                return self._extract_text(data)

            request_id = response.headers.get("x-oneapi-request-id", "unknown")
            cf_ray = response.headers.get("cf-ray", "unknown")
            content_type = response.headers.get("content-type", "")
            preview = response.text[:700].replace("\n", " ")
            last_error = (
                f"HTTP {response.status_code}; request_id={request_id}; cf_ray={cf_ray}; "
                f"content_type={content_type}; response={preview}"
            )

            if response.status_code not in RETRYABLE_STATUS_CODES or attempt >= self.max_retries:
                raise LLMError(last_error)

            retry_after = response.headers.get("retry-after")
            try:
                delay = float(retry_after) if retry_after else float(2**attempt)
            except ValueError:
                delay = float(2**attempt)
            time.sleep(min(delay, 120.0))

        raise LLMError(last_error or "Unknown gateway failure")

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        content = data.get("content")
        if not isinstance(content, list):
            raise LLMError(f"Unexpected Anthropic response shape: {data}")

        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        text = "\n".join(part for part in text_parts if part).strip()
        if not text:
            raise LLMError(f"No text content returned by model: {data}")
        return text
