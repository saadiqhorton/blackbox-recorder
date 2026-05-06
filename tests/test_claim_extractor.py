"""Tests for the ClaimExtractor pipeline stage."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from blackbox.pipeline.claim_extractor import ClaimExtractor
from blackbox.models.claim import Claim, ClaimCategory
from blackbox.models.event import EventModel, MessageEvent

VALID_JSON = '{"claims": [{"text": "Tests passed", "category": "test_result", "verifiable": true}]}'
EMPTY_JSON = '{"claims": []}'
INVALID_JSON = "not valid json"


def _make_event(content: str = "I ran the tests and they passed.", role: str = "assistant") -> EventModel:
    return EventModel(
        session_id="test-session",
        events=[
            MessageEvent(timestamp=datetime(2025, 1, 1), role=role, content=content),
        ],
    )


class TestValidExtraction:
    def test_valid_extraction(self):
        """Mock LLM returns valid JSON, assert Claim objects correct."""
        extractor = ClaimExtractor()
        events = _make_event()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": VALID_JSON}}],
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response
            result = extractor.extract_claims(events)

        assert len(result) == 1
        assert result[0].text == "Tests passed"
        assert result[0].category == ClaimCategory.TEST_RESULT
        assert result[0].verifiable is True
        assert result[0].source_message_idx == 0


class TestNoAssistantMessages:
    def test_no_assistant_messages(self):
        """EventModel with only user messages returns empty list."""
        extractor = ClaimExtractor()
        events = _make_event(role="user")
        result = extractor.extract_claims(events)
        assert result == []


class TestLlmTimeout:
    def test_llm_timeout(self):
        """First call raises TimeoutException, second succeeds, 2 calls total."""
        extractor = ClaimExtractor()
        events = _make_event()

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": VALID_JSON}}],
        }

        mock_post = MagicMock(
            side_effect=[
                httpx.TimeoutException("Timeout", request=MagicMock()),
                mock_response,
            ]
        )

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post = mock_post
            result = extractor.extract_claims(events)

        assert len(result) == 1
        assert result[0].text == "Tests passed"
        assert mock_post.call_count == 2


class TestBadJsonResponse:
    def test_bad_json_response(self):
        """First returns invalid JSON, retries with strict prompt, succeeds."""
        extractor = ClaimExtractor()
        events = _make_event()

        bad_response = MagicMock(spec=httpx.Response)
        bad_response.status_code = 200
        bad_response.json.return_value = {
            "choices": [{"message": {"content": INVALID_JSON}}],
        }

        good_response = MagicMock(spec=httpx.Response)
        good_response.status_code = 200
        good_response.json.return_value = {
            "choices": [{"message": {"content": VALID_JSON}}],
        }

        mock_post = MagicMock(side_effect=[bad_response, good_response])

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post = mock_post
            result = extractor.extract_claims(events)

        assert len(result) == 1
        assert result[0].text == "Tests passed"
        assert mock_post.call_count == 2


class TestLlmOffline:
    def test_llm_offline(self):
        """httpx.ConnectError raises ConnectionError."""
        extractor = ClaimExtractor()
        events = _make_event()

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError(
                "Connection refused", request=MagicMock()
            )
            with pytest.raises(ConnectionError, match="not running"):
                extractor.extract_claims(events)


class TestEmptySession:
    def test_empty_session(self):
        """Zero events returns empty list."""
        extractor = ClaimExtractor()
        events = EventModel(session_id="empty", events=[])
        result = extractor.extract_claims(events)
        assert result == []
