"""
Tests for GdeltAdapter (app.sources.gdelt).

The synchronous ``gdeltdoc`` client is the mocked boundary — no real GDELT
requests are made. A ``FakeGdelt`` returns crafted pandas DataFrames so the
tests exercise signal extraction (BOCPD volume changepoints, funding/pivot
title classification), graceful degradation on errors, and month clamping.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.sources.cost import ADAPTER_SIGNAL_TYPES, AdapterStatus, SourceCost
from app.sources.gdelt import (
    GdeltAdapter,
    _date_to_month,
    _has_pivot_cluster,
    _parse_seendate,
    _series_column,
    _tone_to_severity,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeGdelt:
    """Stand-in for ``gdeltdoc.GdeltDoc`` returning canned DataFrames."""

    def __init__(
        self,
        *,
        timelines: dict[str, pd.DataFrame] | None = None,
        articles: pd.DataFrame | None = None,
        raises: dict[str, Exception] | None = None,
    ) -> None:
        self._timelines = timelines or {}
        self._articles = articles if articles is not None else pd.DataFrame()
        self._raises = raises or {}

    def timeline_search(self, mode: str, filters: object) -> pd.DataFrame:
        if mode in self._raises:
            raise self._raises[mode]
        return self._timelines.get(mode, pd.DataFrame())

    def article_search(self, filters: object) -> pd.DataFrame:
        if "articles" in self._raises:
            raise self._raises["articles"]
        return self._articles


def _volume_df(counts: list[float]) -> pd.DataFrame:
    """Weekly raw-volume timeline ending near today (so months land in range)."""
    end = pd.Timestamp.now().normalize()
    dates = pd.date_range(end=end, periods=len(counts), freq="W")
    return pd.DataFrame(
        {"datetime": dates, "Article Count": counts, "All Articles": counts}
    )


def _tone_df(tones: list[float]) -> pd.DataFrame:
    end = pd.Timestamp.now().normalize()
    dates = pd.date_range(end=end, periods=len(tones), freq="W")
    return pd.DataFrame({"datetime": dates, "Average Tone": tones})


# A flat baseline followed by a sustained ~8x jump — an unambiguous regime change.
_FLAT = [5.0, 6.0, 4.0, 5.0, 6.0, 4.0, 5.0, 5.0, 6.0, 4.0] * 3  # 30 points
_SPIKE = [42.0, 44.0, 41.0, 43.0, 42.0, 44.0, 41.0, 43.0, 42.0, 44.0]  # 10 points
_VOLUME_WITH_CP = _FLAT + _SPIKE


def _recent_seendate(days_ago: int = 5) -> str:
    ts = pd.Timestamp.now() - pd.Timedelta(days=days_ago)
    return ts.strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------

class TestAdapterMetadata:
    def test_cost_is_free(self):
        assert GdeltAdapter.cost is SourceCost.FREE

    def test_status_is_planned(self):
        assert GdeltAdapter.status is AdapterStatus.PLANNED

    def test_requires_no_api_key(self):
        assert GdeltAdapter.requires_api_key is False

    def test_use_cases(self):
        assert set(GdeltAdapter.use_cases) == {1, 6, 8, 10}

    def test_signal_types_subset_of_known(self):
        assert set(GdeltAdapter.signal_types) <= set(ADAPTER_SIGNAL_TYPES)

    def test_record_url_builds_timeline_link(self):
        url = GdeltAdapter().record_url("Acme AG")
        assert url is not None
        assert "api.gdeltproject.org" in url
        assert "timelinevolraw" in url

    def test_record_url_empty_returns_none(self):
        assert GdeltAdapter().record_url("") is None


# ---------------------------------------------------------------------------
# fetch() — always None (news source, no entity record)
# ---------------------------------------------------------------------------

class TestFetch:
    async def test_fetch_returns_none(self):
        adapter = GdeltAdapter(client=FakeGdelt())
        assert await adapter.fetch("drift-1", "Acme AG") is None


# ---------------------------------------------------------------------------
# fetch_signals() — guard clauses
# ---------------------------------------------------------------------------

class TestGuards:
    async def test_blank_name_returns_empty(self):
        adapter = GdeltAdapter(client=FakeGdelt(articles=_make_articles()))
        assert await adapter.fetch_signals("d", "   ") == []

    async def test_no_data_returns_empty(self):
        adapter = GdeltAdapter(client=FakeGdelt())
        assert await adapter.fetch_signals("d", "Acme AG") == []


# ---------------------------------------------------------------------------
# UC1 — news volume via BOCPD
# ---------------------------------------------------------------------------

class TestNewsVolume:
    async def test_volume_changepoint_emits_signal(self):
        client = FakeGdelt(
            timelines={
                "timelinevolraw": _volume_df(_VOLUME_WITH_CP),
                "timelinetone": _tone_df([1.0] * len(_VOLUME_WITH_CP)),
            }
        )
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        vol_signals = [s for s in signals if s.signal_type in ("news", "adverse_media")]
        assert vol_signals, "expected a volume regime-change signal"
        for s in vol_signals:
            assert 0 <= s.month <= 11
            assert s.source_url and "timelinevolraw" in s.source_url

    async def test_negative_tone_escalates_to_adverse_media(self):
        client = FakeGdelt(
            timelines={
                "timelinevolraw": _volume_df(_VOLUME_WITH_CP),
                "timelinetone": _tone_df([-6.0] * len(_VOLUME_WITH_CP)),
            }
        )
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        assert any(s.signal_type == "adverse_media" for s in signals)
        assert all(s.severity >= 0.65 for s in signals if s.signal_type == "adverse_media")

    async def test_positive_tone_stays_news(self):
        client = FakeGdelt(
            timelines={
                "timelinevolraw": _volume_df(_VOLUME_WITH_CP),
                "timelinetone": _tone_df([3.0] * len(_VOLUME_WITH_CP)),
            }
        )
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        vol_signals = [s for s in signals if s.signal_type in ("news", "adverse_media")]
        assert vol_signals
        assert all(s.signal_type == "news" for s in vol_signals)

    async def test_flat_series_emits_no_volume_signal(self):
        client = FakeGdelt(
            timelines={"timelinevolraw": _volume_df([5.0] * 40)}
        )
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        assert [s for s in signals if s.signal_type in ("news", "adverse_media")] == []

    async def test_short_series_skipped(self):
        client = FakeGdelt(timelines={"timelinevolraw": _volume_df([5.0, 40.0, 5.0])})
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        assert signals == []

    async def test_tone_aligned_by_date_not_by_position(self):
        # Regression: timelinetone is a SEPARATE GDELT call whose rows need not
        # line up positionally with timelinevolraw. Tone MUST be matched by date,
        # not by the volume changepoint's positional index. The tone here is
        # negative on the spike days (the regime change) and positive earlier,
        # but its ROWS ARE REVERSED so positional and date order diverge: an
        # `iloc[cp]` lookup lands on a positive (recent-first) row → "news" (the
        # bug), while the date-aligned lookup reads the real negative tone on the
        # changepoint day → "adverse_media".
        end = pd.Timestamp.now().normalize()
        vol_dates = pd.date_range(end=end, periods=len(_VOLUME_WITH_CP), freq="D")
        vol_df = pd.DataFrame(
            {
                "datetime": vol_dates,
                "Article Count": _VOLUME_WITH_CP,
                "All Articles": _VOLUME_WITH_CP,
            }
        )
        # Negative tone from a few points before the spike onward (margin for the
        # exact changepoint index); positive before. Then reverse the row order.
        neg_from = len(_FLAT) - 5
        tone_vals = [3.0 if i < neg_from else -6.0 for i in range(len(vol_dates))]
        tone_df = pd.DataFrame({"datetime": vol_dates, "Average Tone": tone_vals})
        tone_df = tone_df.iloc[::-1].reset_index(drop=True)  # break positional alignment

        client = FakeGdelt(
            timelines={"timelinevolraw": vol_df, "timelinetone": tone_df}
        )
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        vol_signals = [s for s in signals if s.signal_type in ("news", "adverse_media")]
        assert vol_signals, "expected a volume regime-change signal"
        assert all(s.signal_type == "adverse_media" for s in vol_signals)
        assert all(s.severity >= 0.65 for s in vol_signals)

    async def test_misaligned_tone_falls_back_when_day_absent(self):
        # If the changepoint day has no tone row at all, severity must fall back
        # to "regime change, tone unknown" (0.50 → news), never crash.
        end = pd.Timestamp.now().normalize()
        vol_dates = pd.date_range(end=end, periods=len(_VOLUME_WITH_CP), freq="D")
        vol_df = pd.DataFrame(
            {
                "datetime": vol_dates,
                "Article Count": _VOLUME_WITH_CP,
                "All Articles": _VOLUME_WITH_CP,
            }
        )
        # Tone covers only the most recent 3 days — the changepoint day is absent.
        tone_dates = pd.date_range(end=end, periods=3, freq="D")
        tone_df = pd.DataFrame({"datetime": tone_dates, "Average Tone": [-6.0] * 3})
        client = FakeGdelt(
            timelines={"timelinevolraw": vol_df, "timelinetone": tone_df}
        )
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        vol_signals = [s for s in signals if s.signal_type in ("news", "adverse_media")]
        assert vol_signals
        assert all(s.signal_type == "news" for s in vol_signals)


# ---------------------------------------------------------------------------
# UC6 / UC10 — funding + pivot article classification
# ---------------------------------------------------------------------------

def _make_articles(rows: list[dict[str, str]] | None = None) -> pd.DataFrame:
    rows = rows or [
        {
            "title": "Acme AG raises $50M in new funding round",
            "url": "https://news.example/funding",
            "seendate": _recent_seendate(3),
            "domain": "reuters.com",
        },
        {
            "title": "Acme AG reports quarterly earnings",
            "url": "https://news.example/earnings",
            "seendate": _recent_seendate(6),
            "domain": "example.com",
        },
    ]
    return pd.DataFrame(rows)


class TestFundingAndPivot:
    async def test_funding_title_emits_funding_event(self):
        client = FakeGdelt(articles=_make_articles())
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        funding = [s for s in signals if s.signal_type == "funding_event"]
        assert len(funding) == 1
        assert "funding" in funding[0].headline.lower()
        assert funding[0].source_url == "https://news.example/funding"
        assert funding[0].source == "reuters.com"

    async def test_non_matching_titles_ignored(self):
        rows = [
            {
                "title": "Acme AG opens new office",
                "url": "https://news.example/office",
                "seendate": _recent_seendate(2),
                "domain": "example.com",
            }
        ]
        client = FakeGdelt(articles=_make_articles(rows))
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        assert signals == []

    async def test_pivot_cluster_emits_business_model_change(self):
        rows = [
            {
                "title": f"Acme AG rebrands and unveils new product line {i}",
                "url": f"https://news.example/pivot{i}",
                "seendate": _recent_seendate(2 + i),
                "domain": "techcrunch.com",
            }
            for i in range(3)
        ]
        client = FakeGdelt(articles=_make_articles(rows))
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        pivots = [s for s in signals if s.signal_type == "business_model_change"]
        assert len(pivots) == 3
        assert all(s.severity == pytest.approx(0.60) for s in pivots)

    async def test_single_pivot_article_below_cluster_threshold(self):
        rows = [
            {
                "title": "Acme AG announces strategic shift to crypto",
                "url": "https://news.example/pivot",
                "seendate": _recent_seendate(2),
                "domain": "techcrunch.com",
            }
        ]
        client = FakeGdelt(articles=_make_articles(rows))
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        assert [s for s in signals if s.signal_type == "business_model_change"] == []

    async def test_nan_cells_do_not_become_string_nan(self):
        # A partial GDELT response can carry NaN cells (a *truthy* float). A
        # missing url/domain must become None / the display name, never "nan".
        articles = pd.DataFrame(
            [
                {
                    "title": "Acme AG raises $50M in funding",
                    "url": float("nan"),
                    "seendate": _recent_seendate(2),
                    "domain": float("nan"),
                }
            ]
        )
        client = FakeGdelt(articles=articles)
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        funding = [s for s in signals if s.signal_type == "funding_event"]
        assert len(funding) == 1
        assert funding[0].source_url is None
        assert funding[0].source == "GDELT 2.0 (news)"

    async def test_nan_title_row_is_skipped(self):
        # A row whose title is NaN must be dropped, not classified as "nan".
        articles = pd.DataFrame(
            [
                {
                    "title": float("nan"),
                    "url": "https://news.example/x",
                    "seendate": _recent_seendate(2),
                    "domain": "example.com",
                }
            ]
        )
        client = FakeGdelt(articles=articles)
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        assert signals == []


# ---------------------------------------------------------------------------
# Resilience — a failing query degrades to [] rather than raising
# ---------------------------------------------------------------------------

class TestResilience:
    async def test_timeline_error_does_not_crash(self):
        client = FakeGdelt(
            raises={"timelinevolraw": ValueError("GDELT returned HTML")},
            articles=_make_articles(),
        )
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        # Volume mode failed, but the funding signal from articles survives.
        assert any(s.signal_type == "funding_event" for s in signals)

    async def test_article_error_does_not_crash(self):
        client = FakeGdelt(
            timelines={
                "timelinevolraw": _volume_df(_VOLUME_WITH_CP),
                "timelinetone": _tone_df([1.0] * len(_VOLUME_WITH_CP)),
            },
            raises={"articles": RuntimeError("network down")},
        )
        signals = await GdeltAdapter(client=client).fetch_signals("d", "Acme AG")
        assert isinstance(signals, list)
        assert all(s.signal_type != "funding_event" for s in signals)

    async def test_all_queries_failing_returns_empty(self):
        client = FakeGdelt(
            raises={
                "timelinevolraw": ValueError("x"),
                "articles": ValueError("y"),
            }
        )
        assert await GdeltAdapter(client=client).fetch_signals("d", "Acme AG") == []


# ---------------------------------------------------------------------------
# since_month clamping
# ---------------------------------------------------------------------------

class TestSinceMonth:
    async def test_signals_never_exceed_month_bounds(self):
        client = FakeGdelt(
            timelines={
                "timelinevolraw": _volume_df(_VOLUME_WITH_CP),
                "timelinetone": _tone_df([-6.0] * len(_VOLUME_WITH_CP)),
            },
            articles=_make_articles(),
        )
        signals = await GdeltAdapter(client=client).fetch_signals(
            "d", "Acme AG", since_month=99
        )
        for s in signals:
            assert 0 <= s.month <= 11


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    @pytest.mark.parametrize(
        "tone,expected",
        [
            (None, 0.50),
            (-8.0, 0.85),
            (-3.0, 0.65),
            (-0.5, 0.50),
            (2.0, 0.35),
        ],
    )
    def test_tone_to_severity(self, tone, expected):
        assert _tone_to_severity(tone) == pytest.approx(expected)

    def test_series_column_skips_axis_columns(self):
        assert _series_column(["datetime", "Article Count", "All Articles"]) == "Article Count"

    def test_series_column_none_when_only_axis(self):
        assert _series_column(["datetime", "All Articles"]) is None

    def test_parse_seendate_gdelt_format(self):
        dt = _parse_seendate("20260115T143000Z")
        assert dt is not None
        assert (dt.year, dt.month, dt.day) == (2026, 1, 15)

    def test_parse_seendate_garbage_returns_none(self):
        assert _parse_seendate("not-a-date") is None
        assert _parse_seendate("") is None

    def test_date_to_month_clamps_to_since_month(self):
        old = pd.Timestamp.now().to_pydatetime()
        # An old-but-within-window date still cannot fall below the requested floor.
        assert _date_to_month(old, since_month=8) >= 8

    def test_has_pivot_cluster(self):
        assert _has_pivot_cluster([10, 10, 11]) is True   # 3 within 2-month window
        assert _has_pivot_cluster([10, 11]) is False       # only 2
        assert _has_pivot_cluster([2, 6, 11]) is False     # spread too wide
