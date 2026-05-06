from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from blackbox.config import load_config
from blackbox.models.claim import Claim, ClaimCategory
from blackbox.models.event import EventModel, MessageEvent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Extract structured claims from the following agent message.\n"
    "Categories: test_result, outcome, scope, approach, state.\n"
    'Return JSON: {"claims": [{"text": str, "category": str, "verifiable": bool}]}'
)

STRICTER_PROMPT = (
    "Return ONLY valid JSON with no additional text.\n"
    "Extract structured claims from the following agent message.\n"
    "Categories: test_result, outcome, scope, approach, state.\n"
    'Return JSON: {"claims": [{"text": str, "category": str, "verifiable": bool}]}'
)


def _build_payload(provider: str, model: str, messages: list[dict]) -> dict[str, Any]:
    """Build the request payload for the given provider."""
    if provider == "anthropic":
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")
        return {
            "model": model,
            "max_tokens": 1024,
            "system": system_msg,
            "messages": [{"role": "user", "content": user_msg}],
            "temperature": 0.0,
        }
    return {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
    }


def _build_headers(provider: str, api_key: str | None) -> dict[str, str]:
    """Build request headers for the given provider."""
    headers: dict[str, str] = {}
    if provider == "anthropic":
        if api_key:
            headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    elif provider in ("openai", "ollama") and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _parse_response(provider: str, response: httpx.Response) -> list[dict]:
    """Parse the LLM response into a list of claim dicts."""
    data = response.json()
    if provider == "anthropic":
        content = data["content"][0]["text"]
    else:
        content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return parsed.get("claims", [])


def _validate_claims(raw_claims: list[dict]) -> list[Claim]:
    """Validate raw claim dicts into Claim objects, skipping invalid entries."""
    claims: list[Claim] = []
    for item in raw_claims:
        try:
            category = ClaimCategory(item["category"])
            claims.append(
                Claim(
                    text=item["text"],
                    category=category,
                    source_message_idx=0,
                    verifiable=item.get("verifiable", True),
                )
            )
        except (ValueError, KeyError, TypeError):
            logger.warning("Skipping invalid claim entry: %s", item)
    return claims


class ClaimExtractor:
    """Extracts structured claims from assistant messages using an LLM."""

    def __init__(self) -> None:
        config = load_config()
        self.provider = config.llm.provider
        self.model = config.llm.model
        self.base_url = config.llm.base_url.rstrip("/")
        self.api_key = config.llm.api_key

    def _call_llm(self, messages: list[dict], strict: bool = False) -> list[Claim]:
        """Make an LLM API call and return parsed claims."""
        prompt = STRICTER_PROMPT if strict else SYSTEM_PROMPT
        payload = _build_payload(self.provider, self.model, [
            {"role": "system", "content": prompt},
            {"role": "user", "content": messages[0]["content"]},
        ])
        headers = _build_headers(self.provider, self.api_key)

        url = self._build_url()
        timeout = httpx.Timeout(60.0, connect=15.0)

        with httpx.Client(timeout=timeout, headers=headers) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            try:
                raw_claims = _parse_response(self.provider, resp)
            except (json.JSONDecodeError, KeyError, IndexError):
                if not strict:
                    return self._call_llm(messages, strict=True)
                logger.warning("Strict prompt also returned invalid JSON — skipping")
                return []

        return _validate_claims(raw_claims)

    def _extract_single(self, content: str) -> list[Claim]:
        """Extract claims from a single message content string, with retries."""
        try:
            return self._call_llm([{"content": content}])
        except httpx.TimeoutException:
            logger.warning("LLM timeout, retrying once...")
            try:
                return self._call_llm([{"content": content}])
            except httpx.TimeoutException:
                logger.warning("Retry timed out too — skipping")
                return []

    def _build_url(self) -> str:
        if self.provider == "anthropic":
            return f"{self.base_url}/v1/messages"
        return f"{self.base_url}/chat/completions"

    def extract_claims(self, events: EventModel) -> list[Claim]:
        """Extract claims from all assistant messages in the event model."""
        assistant_msgs = [
            e for e in events.events
            if isinstance(e, MessageEvent) and e.role == "assistant" and e.content.strip()
        ]

        if not assistant_msgs:
            return []

        all_claims: list[Claim] = []
        for msg in assistant_msgs:
            try:
                claims = self._extract_single(msg.content)
            except httpx.ConnectError as e:
                raise ConnectionError(
                    f"{self.provider.capitalize()} not running — start with 'ollama serve' "
                    f"or check your API endpoint at {self.base_url}"
                ) from e

            if not claims:
                continue

            for c in claims:
                c.source_message_idx = events.events.index(msg)

            all_claims.extend(claims)

        return all_claims

    def _build_url(self) -> str:
        if self.provider == "anthropic":
            return f"{self.base_url}/v1/messages"
        return f"{self.base_url}/chat/completions"

    def extract_claims(self, events: EventModel) -> list[Claim]:
        """Extract claims from all assistant messages in the event model."""
        assistant_msgs = [
            e for e in events.events
            if isinstance(e, MessageEvent) and e.role == "assistant" and e.content.strip()
        ]

        if not assistant_msgs:
            return []

        all_claims: list[Claim] = []
        for msg in assistant_msgs:
            try:
                claims = self._call_llm([{"content": msg.content}])
            except httpx.TimeoutException:
                logger.warning("LLM timeout on message %s, retrying once...", msg.timestamp)
                try:
                    claims = self._call_llm([{"content": msg.content}])
                except httpx.TimeoutException:
                    logger.warning("Retry timed out too — skipping message %s", msg.timestamp)
                    continue
            except httpx.ConnectError as e:
                raise ConnectionError(
                    f"{self.provider.capitalize()} not running — start with 'ollama serve' "
                    f"or check your API endpoint at {self.base_url}"
                ) from e

            if not claims:
                continue

            for c in claims:
                c.source_message_idx = events.events.index(msg)

            all_claims.extend(claims)

        return all_claims
