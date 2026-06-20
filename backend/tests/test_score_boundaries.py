"""
Boundary tests for the scoring stack.

Most groups here are pure-function (no I/O, no app startup). The trailing UC 4
re-KYC floor group is the exception: its wiring tests (marked `slow`) construct
the DriftEngine to prove the floor fires inside _analyze_customer.

The pure-function groups below exercise mathematical boundaries:

1. Decision boundaries — score_to_level() and score_to_action() tier cut-offs.
   Key regression: before the fix, thresholds were (<= 30, <= 60, <= 85) which
   misclassified float scores in the boundary zones (30,31), (60,61), (85,86).
   After the fix: (< 31, < 61, < 86) — correct for both integer and float scores.

2. Drift primitives — velocity_band() / gaussian_kl_bits() / standardize() /
   BOCPD changepoint behaviour on clean signals.

Run: pytest tests/test_score_boundaries.py -v
"""

import numpy as np
import pytest

from app.drift.velocity import velocity_band, gaussian_kl_bits
from app.drift.bocpd import standardize, BOCPD
from app.drift.service import RE_KYC_SCORE_FLOOR, requires_re_kyc_floor
from app.ml.base import score_to_action, score_to_level
from app.schemas.enums import DecisionAction, RiskLevel
from app.sources.base import PublicSignal


class TestVelocityBand:
    def test_zero_is_natural(self):
        assert velocity_band(0.0) == "natural"

    def test_just_below_natural_boundary(self):
        assert velocity_band(0.29) == "natural"

    def test_natural_boundary_is_notable(self):
        assert velocity_band(0.30) == "notable"

    def test_mid_notable(self):
        assert velocity_band(0.5) == "notable"

    def test_just_below_structural(self):
        assert velocity_band(0.79) == "notable"

    def test_notable_boundary_is_structural(self):
        assert velocity_band(0.80) == "structural"

    def test_mid_structural(self):
        assert velocity_band(1.5) == "structural"

    def test_just_below_rapid(self):
        assert velocity_band(2.99) == "structural"

    def test_structural_boundary_is_rapid(self):
        assert velocity_band(3.00) == "rapid"

    def test_high_velocity_is_rapid(self):
        assert velocity_band(12.0) == "rapid"

    def test_band_is_one_of_four(self):
        for dv in [0.0, 0.4, 1.0, 5.0, 100.0]:
            assert velocity_band(dv) in {"natural", "notable", "structural", "rapid"}


class TestGaussianKL:
    def test_identical_distributions_zero(self):
        assert gaussian_kl_bits(0.0, 1.0, 0.0, 1.0) == pytest.approx(0.0, abs=1e-9)

    def test_mean_shift_is_positive(self):
        assert gaussian_kl_bits(0.0, 1.0, 2.0, 1.0) > 0.0

    def test_larger_mean_shift_larger_kl(self):
        small = gaussian_kl_bits(0.0, 1.0, 1.0, 1.0)
        large = gaussian_kl_bits(0.0, 1.0, 3.0, 1.0)
        assert large > small

    def test_variance_change_is_positive(self):
        assert gaussian_kl_bits(0.0, 1.0, 0.0, 4.0) > 0.0

    def test_kl_never_negative(self):
        for mu1 in [-3.0, 0.0, 2.5]:
            for var1 in [0.5, 1.0, 5.0]:
                assert gaussian_kl_bits(0.0, 1.0, mu1, var1) >= -1e-9


class TestStandardize:
    def test_output_same_length(self):
        s = np.arange(50, dtype=float)
        out = standardize(s, baseline_window=30)
        assert len(out) == len(s)

    def test_constant_series_no_nan(self):
        s = np.ones(40)
        out = standardize(s, baseline_window=30)
        assert not np.any(np.isnan(out))

    def test_returns_numpy_array(self):
        out = standardize(np.arange(40, dtype=float), baseline_window=30)
        assert isinstance(out, np.ndarray)


class TestBOCPD:
    def test_no_changepoint_on_stationary(self):
        rng = np.random.default_rng(0)
        series = standardize(rng.normal(0.0, 1.0, 120), baseline_window=30)
        result = BOCPD().run(series)
        assert all(cp > 30 for cp in result.detected_changepoints)

    def test_detects_step_change(self):
        rng = np.random.default_rng(1)
        first = rng.normal(0.0, 0.5, 60)
        second = rng.normal(6.0, 0.5, 60)
        series = standardize(np.concatenate([first, second]), baseline_window=30)
        result = BOCPD().run(series)
        assert len(result.detected_changepoints) > 0


class TestScoreToLevel:
    # --- LOW (0–30) ---

    def test_zero_is_low(self):
        assert score_to_level(0) == RiskLevel.LOW

    def test_thirty_is_low(self):
        assert score_to_level(30) == RiskLevel.LOW

    def test_fractional_below_31_is_low(self):
        # Regression: was MEDIUM before the boundary fix
        assert score_to_level(30.5) == RiskLevel.LOW
        assert score_to_level(30.9) == RiskLevel.LOW

    # --- MEDIUM (31–60) ---

    def test_31_is_medium(self):
        assert score_to_level(31) == RiskLevel.MEDIUM

    def test_mid_medium_is_medium(self):
        assert score_to_level(45) == RiskLevel.MEDIUM

    def test_sixty_is_medium(self):
        assert score_to_level(60) == RiskLevel.MEDIUM

    def test_fractional_below_61_is_medium(self):
        # Regression: was HIGH before the boundary fix
        assert score_to_level(60.5) == RiskLevel.MEDIUM
        assert score_to_level(60.9) == RiskLevel.MEDIUM

    # --- HIGH (61–85) ---

    def test_61_is_high(self):
        assert score_to_level(61) == RiskLevel.HIGH

    def test_mid_high_is_high(self):
        assert score_to_level(75) == RiskLevel.HIGH

    def test_85_is_high(self):
        assert score_to_level(85) == RiskLevel.HIGH

    def test_fractional_below_86_is_high(self):
        # Regression: was CRITICAL before the boundary fix
        assert score_to_level(85.5) == RiskLevel.HIGH
        assert score_to_level(85.9) == RiskLevel.HIGH

    # --- CRITICAL (86–100) ---

    def test_86_is_critical(self):
        assert score_to_level(86) == RiskLevel.CRITICAL

    def test_100_is_critical(self):
        assert score_to_level(100) == RiskLevel.CRITICAL

    # --- Return type ---

    def test_returns_risk_level_enum(self):
        assert isinstance(score_to_level(50), RiskLevel)

    def test_risk_level_is_str_compatible(self):
        # RiskLevel is StrEnum — must compare equal to its string value
        assert score_to_level(50) == "medium"
        assert score_to_level(70) == "high"


class TestScoreToAction:
    # --- ALLOW (low scores) ---

    def test_zero_is_allow(self):
        assert score_to_action(0, 0.9) == DecisionAction.ALLOW

    def test_30_is_allow(self):
        assert score_to_action(30, 0.9) == DecisionAction.ALLOW

    def test_fractional_below_31_is_allow(self):
        # Regression: was STEP_UP before the boundary fix
        assert score_to_action(30.5, 0.9) == DecisionAction.ALLOW
        assert score_to_action(30.9, 0.9) == DecisionAction.ALLOW

    # --- STEP_UP_VERIFICATION (medium scores) ---

    def test_31_is_step_up(self):
        assert score_to_action(31, 0.9) == DecisionAction.STEP_UP_VERIFICATION

    def test_60_is_step_up(self):
        assert score_to_action(60, 0.9) == DecisionAction.STEP_UP_VERIFICATION

    def test_fractional_below_61_is_step_up(self):
        # Regression: was BLOCK/ESCALATE before the boundary fix
        assert score_to_action(60.5, 0.9) == DecisionAction.STEP_UP_VERIFICATION
        assert score_to_action(60.9, 0.9) == DecisionAction.STEP_UP_VERIFICATION

    # --- BLOCK / ESCALATE (high + critical scores) ---

    def test_high_score_with_high_confidence_is_block(self):
        assert score_to_action(61, 0.9) == DecisionAction.BLOCK
        assert score_to_action(86, 0.9) == DecisionAction.BLOCK
        assert score_to_action(100, 0.9) == DecisionAction.BLOCK

    def test_high_score_with_low_confidence_is_escalate(self):
        assert score_to_action(61, 0.5) == DecisionAction.ESCALATE
        assert score_to_action(86, 0.5) == DecisionAction.ESCALATE
        assert score_to_action(100, 0.0) == DecisionAction.ESCALATE

    def test_confidence_threshold_is_085(self):
        assert score_to_action(70, 0.85) == DecisionAction.BLOCK
        assert score_to_action(70, 0.84) == DecisionAction.ESCALATE


class TestLevelActionConsistency:
    """
    score_to_level and score_to_action must agree on which tier a score falls in.
    After the boundary fix both functions use the same (<31 / <61 / <86) thresholds.
    """

    SCORES = [0, 15, 30, 30.5, 31, 45, 60, 60.5, 61, 75, 85, 85.5, 86, 95, 100]

    def test_low_scores_always_allow(self):
        for score in [s for s in self.SCORES if s < 31]:
            assert score_to_level(score) == RiskLevel.LOW, f"score={score}"
            assert score_to_action(score, 0.9) == DecisionAction.ALLOW, f"score={score}"

    def test_medium_scores_always_step_up(self):
        for score in [s for s in self.SCORES if 31 <= s < 61]:
            assert score_to_level(score) == RiskLevel.MEDIUM, f"score={score}"
            assert (
                score_to_action(score, 0.9) == DecisionAction.STEP_UP_VERIFICATION
            ), f"score={score}"

    def test_high_and_critical_scores_never_allow_or_step_up(self):
        for score in [s for s in self.SCORES if s >= 61]:
            level = score_to_level(score)
            action = score_to_action(score, 0.9)
            assert level in (RiskLevel.HIGH, RiskLevel.CRITICAL), f"score={score}"
            assert action in (DecisionAction.BLOCK, DecisionAction.ESCALATE), f"score={score}"


def _structural_signal(signal_type: str, severity: float = 0.0) -> PublicSignal:
    """A registry-sourced public signal.

    Severity defaults to 0.0 so the re-KYC floor tests isolate the floor: any
    score lift comes from the signal *type* (a structural change), never from
    public-risk weighting.
    """
    return PublicSignal(
        month=0,
        signal_type=signal_type,
        headline="Registry: structural change detected",
        severity=severity,
        source="zefix",
    )


class TestRequiresReKycFloor:
    """UC 4 — pure predicate gating the mandatory re-KYC score floor."""

    def test_jurisdiction_change_triggers(self):
        assert requires_re_kyc_floor([_structural_signal("jurisdiction_change")]) is True

    def test_legal_form_change_triggers(self):
        assert requires_re_kyc_floor([_structural_signal("legal_form_change")]) is True

    def test_unrelated_signal_does_not_trigger(self):
        for stype in ("news", "sanctions", "adverse_media", "name_change"):
            assert requires_re_kyc_floor([_structural_signal(stype)]) is False, stype

    def test_empty_signal_list_does_not_trigger(self):
        assert requires_re_kyc_floor([]) is False

    def test_triggers_when_mixed_with_unrelated_signals(self):
        signals = [
            _structural_signal("news"),
            _structural_signal("jurisdiction_change"),
        ]
        assert requires_re_kyc_floor(signals) is True


@pytest.mark.slow
class TestReKycScoreFloorWiring:
    """UC 4 — a confirmed jurisdiction/legal-form change floors _analyze_customer
    at RE_KYC_SCORE_FLOOR (mandatory re-KYC), overriding a low behavioral score.

    Constructs the engine (heuristic-only: _drift_model=None) and injects the
    registry signal via the _public_signals seam, which conftest otherwise stubs
    to [] for determinism.
    """

    def _stable_engine_customer(self):
        from app.drift.service import DriftEngine

        engine = DriftEngine()
        engine._drift_model = None  # heuristic-only → deterministic, no disk model
        cust = next(c for c in engine._book if c.scenario == "stable")
        return engine, cust

    def test_stable_customer_baseline_is_below_floor(self, monkeypatch):
        # Guards the premise of the floor tests: with no structural signal the
        # stable customer scores below the floor, so a later >= floor result is
        # attributable to the floor and not to an already-high score.
        engine, cust = self._stable_engine_customer()
        monkeypatch.setattr(engine, "_public_signals", lambda c: [])
        assert engine._analyze_customer(cust)["drift_score"] < RE_KYC_SCORE_FLOOR

    def test_jurisdiction_change_floors_score(self, monkeypatch):
        engine, cust = self._stable_engine_customer()
        monkeypatch.setattr(
            engine, "_public_signals",
            lambda c: [_structural_signal("jurisdiction_change")],
        )
        assert engine._analyze_customer(cust)["drift_score"] >= RE_KYC_SCORE_FLOOR

    def test_legal_form_change_floors_score(self, monkeypatch):
        engine, cust = self._stable_engine_customer()
        monkeypatch.setattr(
            engine, "_public_signals",
            lambda c: [_structural_signal("legal_form_change")],
        )
        assert engine._analyze_customer(cust)["drift_score"] >= RE_KYC_SCORE_FLOOR

    def test_unrelated_signal_does_not_floor(self, monkeypatch):
        engine, cust = self._stable_engine_customer()
        monkeypatch.setattr(
            engine, "_public_signals",
            lambda c: [_structural_signal("news")],
        )
        assert engine._analyze_customer(cust)["drift_score"] < RE_KYC_SCORE_FLOOR
