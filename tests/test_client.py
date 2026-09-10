import pytest

from arch_council.client import AnthropicGatewayClient, LLMError


def test_extract_text_from_anthropic_response() -> None:
    data = {
        "content": [
            {"type": "text", "text": "hello"},
            {"type": "text", "text": "world"},
        ]
    }
    assert AnthropicGatewayClient._extract_text(data) == "hello\nworld"


def test_extract_text_rejects_missing_content() -> None:
    with pytest.raises(LLMError):
        AnthropicGatewayClient._extract_text({"content": []})
