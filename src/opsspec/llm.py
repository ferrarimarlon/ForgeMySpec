from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib import error, request


class LLMError(RuntimeError):
    """Raised when an LLM provider cannot produce a valid response."""


@dataclass
class LLMSettings:
    provider: str
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    timeout_seconds: int = 45
    extra_headers: Dict[str, str] = field(default_factory=dict)


class LLMProvider:
    name = "base"

    def generate_spec_draft(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        return self.generate_json(prompt, system_prompt)

    def generate_json(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        raise NotImplementedError


class OpenAIResponsesProvider(LLMProvider):
    name = "openai"

    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.api_key = settings.api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = settings.base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1/responses"
        self.model = settings.model or os.getenv("OPENAI_MODEL") or "gpt-codex"

    def generate_json(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is not configured.")

        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
            ],
            "temperature": self.settings.temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        return _post_json(self.base_url, headers, payload, self.settings.timeout_seconds, content_path=("output_text",))


class AnthropicMessagesProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, settings: LLMSettings):
        self.settings = settings
        self.api_key = settings.api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = settings.base_url or os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com/v1/messages"
        self.model = settings.model or os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest"

    def generate_json(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise LLMError("ANTHROPIC_API_KEY is not configured.")

        payload = {
            "model": self.model,
            "max_tokens": 1600,
            "temperature": self.settings.temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        return _post_json(self.base_url, headers, payload, self.settings.timeout_seconds, content_path=("content", 0, "text"))


def build_provider(settings: LLMSettings) -> LLMProvider:
    providers = {
        "openai": OpenAIResponsesProvider,
        "anthropic": AnthropicMessagesProvider,
    }
    provider_cls = providers.get(settings.provider)
    if not provider_cls:
        raise LLMError(f"Unknown provider: {settings.provider}")
    return provider_cls(settings)


def _post_json(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: int,
    content_path: tuple[Any, ...],
) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    for key, value in headers.items():
        req.add_header(key, value)

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMError(f"Provider HTTP failure: {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise LLMError(f"Network failure while calling provider: {exc}") from exc

    data = json.loads(raw)
    text = _extract_text(data, content_path)
    if not text:
        raise LLMError("Provider did not return usable text.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Provider returned invalid JSON: {exc}") from exc


def _extract_text(payload: Dict[str, Any], content_path: tuple[Any, ...]) -> str:
    if content_path == ("output_text",):
        direct = payload.get("output_text")
        if direct:
            return direct
        texts = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if "text" in content:
                    texts.append(content["text"])
        return "\n".join(texts).strip()

    cursor: Any = payload
    for key in content_path:
        cursor = cursor[key]
    return cursor.strip() if isinstance(cursor, str) else ""
