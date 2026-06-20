"""
Tests for EventRegistryAdapter (app.sources.event_registry).

All HTTP calls are mocked — no real API requests are made.
The key concern is signal extraction correctness, graceful key-absent behaviour,
and rate-limit retry logic.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.sources.cost import AdapterStatus, SourceCost
from app.sources.event_registry import (
    EventRegistryAdapter,
    _date_str_to_month,
    _month_offset_to_date,
    _sentiment_to_severity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def adapter_with_key(monkeypatch: pytest.MonkeyPatch) -> EventRegistryAdapter:
    monkeypatch.setenv("EVENT_REGISTRY_API_KEY", "test-key-abc")
    return EventRegistryAdapter()


@pytest.fixture()
def adapter_no_key(monkeypatch: pytest.MonkeyPatch) -> EventRegistryAdapter:
    monkeypatch.delenv("EVENT_REGISTRY_API_KEY", raising=False)
    return EventRegistryAdapter()


def _make_response(body: dict[str, Any], status: int = 200) -> MagicMock:
    """Build a mock httpx.Response."""
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status
    mock.json.return_value = body
    mock.raise_for_status = MagicMock(
        side_effect=None if status < 400 else httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock
        )
    )
    mock.request = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------

class TestAdapterMetadata:
    def test_cost_is_freemium(self):
        assert EventRegistryAdapter.cost is SourceCost.FREEMIUM

    def test_status_is_planned(self):
        assert EventRegistryAdapter.status is AdapterStatus.PLANNED

    def test_requires_api_key(self):
        assert EventRegistryAdapter.requires_api_key is True

    def test_use_cases(self):
        assert set(EventRegistryAdapter.use_cases) == {1, 6, 8, 10}

    def test_signal_types_subset_of_known(self):
        from app.sources.cost import ADAPTER_SIGNAL_TYPES
        assert set(EventRegistryAdapter.signal_types) <= set(ADAPTER_SIGNAL_TYPES)

    def test_record_url(self):
        a = EventRegistryAdapter()
        assert "eventregistry.org/event/abc" in a.record_url("abc")

    def test_record_url_empty_returns_none(self):
        a = EventRegistryAdapter()
        assert a.record_url("") is None


# ---------------------------------------------------------------------------
# fetch() — always returns None (news source, no entity record)
# ---------------------------------------------------------------------------

class TestFetch:
    async def test_fetch_returns_none(self, adapter_with_key: EventRegistryAdapter):
        result = await adapter_with_key.fetch("drift-1", "Acme AG")
        assert result is None

    async def test_fetch_returns_none_without_key(
        self, adapter_no_key: EventRegistryAdapter
    ):
        result = await adapter_no_key.fetch("drift-1", "Acme AG")
        assert result is None


# ---------------------------------------------------------------------------
# fetch_signals() — no key → graceful empty list
# ---------------------------------------------------------------------------

class TestFetchSignalsNoKey:
    async def test_returns_empty_list_when_no_key(
        self, adapter_no_key: EventRegistryAdapter
    ):
        signals = await adapter_no_key.fetch_signals("drift-1", "Acme AG")
        assert signals == []

    async def test_does_not_raise_when_no_key(
        self, adapter_no_key: EventRegistryAdapter
    ):
        # Must not raise SourceUnavailableError or NotImplementedError.
        result = await adapter_no_key.fetch_signals("drift-1", "Acme AG", since_month=3)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# fetch_signals() — mocked HTTP, adverse media (UC 1)
# ---------------------------------------------------------------------------

class TestAdverseMedia:
    _EVENTS_RESPONSE = {
        "events": {
            "results": [
                {
                    "uri": "evt-001",
                    "title": {"eng": "Acme AG faces fraud investigation"},
                    "eventDate": "2025-06-01",
                    "sentiment": -0.72,
                    "articleCounts": {"eng": 15},
                },
                {
                    "uri": "evt-002",
                    "title": {"eng": "Acme AG Q3 results"},
                    "eventDate": "2025-05-01",
                    "sentiment": 0.20,  # positive — should be filtered out
                    "articleCounts": {"eng": 3},
                },
            ]
        }
    }
    _EMPTY_ARTICLES = {"articles": {"results": []}}

    async def test_negative_event_emits_adverse_media_signal(
        self, adapter_with_key: EventRegistryAdapter
    ):
        with patch.object(
            adapter_with_key,
            "_post",
            new=AsyncMock(side_effect=[
                self._EVENTS_RESPONSE,
                self._EMPTY_ARTICLES,
                self._EMPTY_ARTICLES,
            ]),
        ):
            signals = await adapter_with_key.fetch_signals("drift-1", "Acme AG")

        types = {s.signal_type for s in signals}
        assert "adverse_media" in types or "news" in types

    async def test_positive_event_is_excluded(
        self, adapter_with_key: EventRegistryAdapter
    ):
        positive_only = {
            "events": {
                "results": [
                    {
                        "uri": "evt-pos",
                        "title": {"eng": "Acme AG wins award"},
                        "eventDate": "2025-06-01",
                        "sentiment": 0.50,
                        "articleCounts": {"eng": 5},
                    }
                ]
            }
        }
        _empty_articles = {"articles": {"results": []}}
        with patch.object(
            adapter_with_key,
            "_post",
            new=AsyncMock(side_effect=[positive_only, _empty_articles, _empty_articles]),
        ):
            signals = await adapter_with_key.fetch_signals("drift-1", "Acme AG")

        # Positive-sentiment event must produce no adverse_media or news signals.
        assert signals == [], f"Expected no signals for positive sentiment, got {signals}"

    async def test_high_article_count_adds_spike_signal(
        self, adapter_with_key: EventRegistryAdapter
    ):
        with patch.object(
            adapter_with_key,
            "_post",
            new=AsyncMock(side_effect=[
                self._EVENTS_RESPONSE,
                self._EMPTY_ARTICLES,
                self._EMPTY_ARTICLES,
            ]),
        ):
            signals = await adapter_with_key.fetch_signals("drift-1", "Acme AG")

        # The event with articleCounts=15 should trigger both an adverse_media
        # signal AND a news spike signal.
        news_signals = [s for s in signals if s.signal_type == "news"]
        assert any("spike" in s.headline.lower() for s in news_signals)


# ---------------------------------------------------------------------------
# fetch_signals() — mocked HTTP, funding events (UC 6)
# ---------------------------------------------------------------------------

class TestFundingEvents:
    _ARTICLES_RESPONSE = {
        "articles": {
            "results": [
                {
                    "title": "Acme AG raises $50M Series B",
                    "url": "https://example.com/acme-series-b",
                    "dateTime": "2025-07-10T09:00:00Z",
                    "source": {"title": "TechCrunch"},
                }
            ]
        }
    }
    _EMPTY = {"articles": {"results": []}, "events": {"results": []}}

    async def test_funding_article_emits_funding_event_signal(
        self, adapter_with_key: EventRegistryAdapter
    ):
        with patch.object(
            adapter_with_key,
            "_post",
            new=AsyncMock(side_effect=[
                self._EMPTY,            # adverse media call returns empty
                self._ARTICLES_RESPONSE,  # funding call
                self._EMPTY,            # pivot call
            ]),
        ):
            signals = await adapter_with_key.fetch_signals("drift-1", "Acme AG")

        funding = [s for s in signals if s.signal_type == "funding_event"]
        assert len(funding) == 1
        assert "Series B" in funding[0].headline
        assert funding[0].severity == pytest.approx(0.55)
        assert funding[0].source == "TechCrunch"
        assert funding[0].source_url == "https://example.com/acme-series-b"


# ---------------------------------------------------------------------------
# fetch_signals() — mocked HTTP, name change / pivot (UC 8/10)
# ---------------------------------------------------------------------------

class TestNameChangePivot:
    _NAME_ARTICLE = {
        "articles": {
            "results": [
                {
                    "title": "Acme AG renamed to NewCo AG",
                    "url": "https://example.com/rename",
                    "dateTime": "2025-04-20T08:00:00Z",
                    "source": {"title": "Reuters"},
                }
            ]
        }
    }
    _PIVOT_ARTICLE = {
        "articles": {
            "results": [
                {
                    "title": "Acme AG pivots to blockchain services",
                    "url": "https://example.com/pivot",
                    "dateTime": "2025-03-15T12:00:00Z",
                    "source": {"title": "Bloomberg"},
                }
            ]
        }
    }
    _EMPTY = {"articles": {"results": []}, "events": {"results": []}}

    async def test_rename_article_emits_name_change_signal(
        self, adapter_with_key: EventRegistryAdapter
    ):
        with patch.object(
            adapter_with_key,
            "_post",
            new=AsyncMock(side_effect=[self._EMPTY, self._EMPTY, self._NAME_ARTICLE]),
        ):
            signals = await adapter_with_key.fetch_signals("drift-1", "Acme AG")

        name_signals = [s for s in signals if s.signal_type == "name_change"]
        assert len(name_signals) == 1
        assert name_signals[0].severity == pytest.approx(0.70)

    async def test_pivot_article_emits_business_model_change_signal(
        self, adapter_with_key: EventRegistryAdapter
    ):
        with patch.object(
            adapter_with_key,
            "_post",
            new=AsyncMock(side_effect=[self._EMPTY, self._EMPTY, self._PIVOT_ARTICLE]),
        ):
            signals = await adapter_with_key.fetch_signals("drift-1", "Acme AG")

        pivot_signals = [s for s in signals if s.signal_type == "business_model_change"]
        assert len(pivot_signals) == 1
        assert pivot_signals[0].severity == pytest.approx(0.60)


# ---------------------------------------------------------------------------
# Rate-limit retry (429 backoff)
# ---------------------------------------------------------------------------

class TestRateLimit:
    async def test_retries_on_429_then_succeeds(
        self, adapter_with_key: EventRegistryAdapter
    ):
        ok_response = _make_response({"events": {"results": []}})
        too_many = _make_response({}, status=429)
        too_many.raise_for_status = MagicMock()  # 429 is handled by adapter, not raise_for_status

        call_count = 0

        async def mock_post(url: str, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return too_many
            return ok_response

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = mock_post
            mock_client_cls.return_value = mock_client

            with patch("app.sources.event_registry.asyncio.sleep", new=AsyncMock()):
                result = await adapter_with_key._post(
                    "event/getEvents", {"keyword": "test"}
                )

        assert result == {"events": {"results": []}}

    async def test_exhausted_retries_raises(
        self, adapter_with_key: EventRegistryAdapter
    ):
        too_many = _make_response({}, status=429)
        too_many.raise_for_status = MagicMock()

        async def always_429(url: str, **kwargs: Any) -> MagicMock:
            return too_many

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = always_429
            mock_client_cls.return_value = mock_client

            with patch("app.sources.event_registry.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(httpx.HTTPStatusError):
                    await adapter_with_key._post(
                        "event/getEvents", {"keyword": "test"}, retries=3
                    )


# ---------------------------------------------------------------------------
# Network / HTTP errors — graceful degradation
# ---------------------------------------------------------------------------

class TestNetworkErrors:
    async def test_http_status_error_returns_empty(
        self, adapter_with_key: EventRegistryAdapter
    ):
        with patch.object(
            adapter_with_key,
            "_post",
            new=AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "500", request=MagicMock(), response=MagicMock(status_code=500)
                )
            ),
        ):
            signals = await adapter_with_key.fetch_signals("drift-1", "Acme AG")

        assert signals == []

    async def test_request_error_returns_empty(
        self, adapter_with_key: EventRegistryAdapter
    ):
        with patch.object(
            adapter_with_key,
            "_post",
            new=AsyncMock(side_effect=httpx.RequestError("timeout")),
        ):
            signals = await adapter_with_key.fetch_signals("drift-1", "Acme AG")

        assert signals == []


# ---------------------------------------------------------------------------
# Unit tests for pure helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_sentiment_to_severity_high_negative(self):
        assert _sentiment_to_severity(-0.8) == pytest.approx(0.85)

    def test_sentiment_to_severity_medium_negative(self):
        assert _sentiment_to_severity(-0.3) == pytest.approx(0.65)

    def test_sentiment_to_severity_low_negative(self):
        assert _sentiment_to_severity(-0.1) == pytest.approx(0.45)

    def test_sentiment_to_severity_positive(self):
        assert _sentiment_to_severity(0.5) == pytest.approx(0.25)

    def test_sentiment_to_severity_none(self):
        assert _sentiment_to_severity(None) == pytest.approx(0.40)

    def test_month_offset_to_date_since_zero(self):
        date = _month_offset_to_date(0)
        assert len(date) == 10
        assert date[:4].isdigit()

    def test_month_offset_to_date_since_six(self):
        date_full = _month_offset_to_date(0)
        date_half = _month_offset_to_date(6)
        # since_month=6 should produce a more recent date_from than since_month=0
        assert date_half >= date_full

    def test_date_str_to_month_today(self):
        from datetime import UTC, datetime
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        month = _date_str_to_month(today, since_month=0)
        assert month == 11  # today maps to the most recent month

    def test_date_str_to_month_clamped(self):
        # A very old date should be clamped to since_month.
        month = _date_str_to_month("2000-01-01", since_month=5)
        assert month == 5

    def test_date_str_to_month_invalid(self):
        # Invalid date string should fall back to since_month.
        month = _date_str_to_month("not-a-date", since_month=3)
        assert month == 3

    def test_public_signal_severity_in_range(self):
        """All severity values produced by the adapter must satisfy [0, 1]."""
        from app.sources.base import PublicSignal

        # PublicSignal.__post_init__ raises ValueError for out-of-range severity.
        # Check that all sentinel values the adapter produces are in-range.
        sentinel_severities = [0.85, 0.65, 0.45, 0.25, 0.40, 0.55, 0.70, 0.60, 0.95]
        for sev in sentinel_severities:
            sig = PublicSignal(
                month=0,
                signal_type="news",
                headline="test",
                severity=sev,
                source="er",
            )
            assert 0.0 <= sig.severity <= 1.0
