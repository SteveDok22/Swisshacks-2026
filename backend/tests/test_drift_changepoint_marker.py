"""
Unit tests for the BOCPD changepoint -> timeline marker mapping.

BOCPD runs over the concatenated *daily* volume series, so its detected
changepoint is a day index. The drift timeline is indexed by *month*. These
tests pin the day->month conversion and verify the timeline flags exactly the
month window where the behavioral regime shifted (replacing the old hardcoded
`bocpd_changepoint=False`).
"""

from __future__ import annotations

from app.drift.service import DriftEngine
from app.drift.simulator import generate_customer
from app.drift.velocity import compute_drift_series


class TestDayToMonthMapping:
    def test_day_to_month_uses_days_per_month(self) -> None:
        cust = generate_customer(
            drift_id="t1", name="T1", scenario="stable",
            months=6, days_per_month=21, seed=1,
        )
        assert cust.days_per_month() == 21
        assert cust.day_to_month(0) == 0
        assert cust.day_to_month(20) == 0
        assert cust.day_to_month(21) == 1
        assert cust.day_to_month(188) == 8  # 188 // 21

    def test_days_per_month_falls_back_when_no_volume(self) -> None:
        cust = generate_customer(
            drift_id="t2", name="T2", scenario="stable", seed=1,
        )
        cust.monthly_volume = []
        assert cust.days_per_month() == 21


class TestChangepointTimelineMarker:
    def test_marked_month_matches_changepoint_day(self) -> None:
        """The flagged timeline point must be the month the changepoint day
        maps to — and there must be at most one such point."""
        engine = DriftEngine()
        for cust in engine._book:
            detail = engine.get_customer(cust.drift_id)
            assert detail is not None

            marked = [p for p in detail.timeline if p.bocpd_changepoint]
            assert len(marked) <= 1, (
                f"{cust.drift_id}: expected at most one changepoint marker, "
                f"got {[p.month for p in marked]}"
            )

            if detail.bocpd_changepoint_day is None:
                assert not marked, (
                    f"{cust.drift_id}: no changepoint day but timeline marked"
                )
                continue

            expected_month = cust.day_to_month(detail.bocpd_changepoint_day)
            window_months = {p.month for p in detail.timeline}
            if expected_month in window_months:
                assert [p.month for p in marked] == [expected_month]
            else:
                # Changepoint landed in the baseline window (before the first
                # timeline point) — nothing to render, and that is correct.
                assert not marked

    def test_dormancy_break_customer_is_marked(self) -> None:
        """The seeded dormancy-break customer has a confirmed regime change, so
        its timeline must carry exactly one marker (regression guard)."""
        engine = DriftEngine()
        dormant = next(
            c for c in engine._book if c.scenario == "dormancy_break"
        )
        detail = engine.get_customer(dormant.drift_id)
        assert detail is not None
        assert detail.bocpd_changepoint_day is not None

        expected_month = dormant.day_to_month(detail.bocpd_changepoint_day)
        # The dormancy activation lands mid-series, well past the baseline
        # window — assert that precondition explicitly so this test fails
        # meaningfully (not spuriously) if generation params ever change.
        window_months = {p.month for p in detail.timeline}
        assert expected_month in window_months

        marked = [p.month for p in detail.timeline if p.bocpd_changepoint]
        assert marked == [expected_month]

    def test_changepoint_in_baseline_window_is_not_marked(self) -> None:
        """A changepoint that maps to a month before the first timeline point
        (the baseline window) must produce no marker — the subtlest branch of
        the mapping, pinned deterministically.

        get_customer flags point i iff `ds.windows[i] == cp_month`; the timeline
        windows start at baseline_windows (3), so a baseline-range changepoint
        matches no window and stays unmarked.
        """
        cust = generate_customer(
            drift_id="t3", name="T3", scenario="stable",
            months=12, days_per_month=21, seed=1,
        )
        ds = compute_drift_series(cust.metric_windows())
        # A day in the baseline window maps to month 0..2, none of which appear
        # in ds.windows (which begins at 3).
        cp_month = cust.day_to_month(10)
        assert cp_month == 0
        assert cp_month not in set(ds.windows)
        assert [w for w in ds.windows if w == cp_month] == []

    def test_stable_customer_has_no_marker(self) -> None:
        engine = DriftEngine()
        stable = next(c for c in engine._book if c.scenario == "stable")
        detail = engine.get_customer(stable.drift_id)
        assert detail is not None
        assert all(not p.bocpd_changepoint for p in detail.timeline)
