"""Unit tests for causal drift hypothesis classifier."""

from __future__ import annotations

import numpy as np
import pytest

from app.drift.causal import CausalSignature, causal_assessment, classify_causal, compute_signature


class TestClassifyCausal:
    def test_risk_signature_gives_risk_label(self):
        # Volume up, margin collapses, counterparties risky, corridors shift — classic transit
        sig = CausalSignature(
            volume_change=0.9,
            margin_change=-0.22,
            counterparty_change=0.30,
            corridor_change=0.20,
        )
        verdict = classify_causal(sig)
        assert verdict.label == "risk"
        assert verdict.causal_llr > 0

    def test_benign_signature_gives_benign_label(self):
        # Volume up, margin preserved, counterparties clean, corridors stable — normal growth
        sig = CausalSignature(
            volume_change=0.8,
            margin_change=-0.01,
            counterparty_change=0.01,
            corridor_change=0.00,
        )
        verdict = classify_causal(sig)
        assert verdict.label == "benign"
        assert verdict.causal_llr < 0

    def test_p_risk_is_in_unit_interval(self):
        for sig in [
            CausalSignature(0.9, -0.22, 0.30, 0.20),
            CausalSignature(0.8, -0.01, 0.01, 0.00),
            CausalSignature(0.5, -0.10, 0.10, 0.05),
        ]:
            verdict = classify_causal(sig)
            assert 0.0 <= verdict.p_risk <= 1.0

    def test_contributions_cover_all_signature_dimensions(self):
        sig = CausalSignature(0.5, -0.05, 0.05, 0.02)
        verdict = classify_causal(sig)
        assert set(verdict.contributions.keys()) == {
            "volume_change",
            "margin_change",
            "counterparty_change",
            "corridor_change",
        }

    def test_margin_collapse_alone_drives_risk_verdict(self):
        # Margin collapse is the tightest discriminator — extreme collapse should suffice
        sig = CausalSignature(
            volume_change=0.5,   # neutral
            margin_change=-0.22, # clear collapse
            counterparty_change=0.0,  # no change
            corridor_change=0.0,
        )
        verdict = classify_causal(sig)
        # margin collapse contribution should be the largest positive contributor
        assert verdict.contributions["margin_change"] > 0
        assert verdict.label in ("risk", "ambiguous")

    def test_risk_p_risk_exceeds_benign_p_risk(self):
        risk_sig = CausalSignature(0.9, -0.22, 0.30, 0.20)
        benign_sig = CausalSignature(0.8, -0.01, 0.01, 0.00)
        assert classify_causal(risk_sig).p_risk > classify_causal(benign_sig).p_risk


class TestComputeSignature:
    def _make_windows(
        self,
        n: int = 14,
        vol_end: float = 8000.0,
        margin_end: float = 0.03,
        cp_end: float = 0.35,
        corr_end: float = 0.25,
    ) -> dict:
        rng = np.random.default_rng(99)
        vol_start, margin_start, cp_start, corr_start = 5000.0, 0.25, 0.05, 0.05
        vols, margins, cps, corrs = [], [], [], []
        for i in range(n):
            t = i / (n - 1)
            vols.append(rng.normal(vol_start + t * (vol_end - vol_start), 100.0, 21))
            margins.append(rng.normal(margin_start + t * (margin_end - margin_start), 0.01, 21))
            cps.append(rng.normal(cp_start + t * (cp_end - cp_start), 0.01, 21))
            corrs.append(rng.normal(corr_start + t * (corr_end - corr_start), 0.01, 21))
        return {
            "monthly_volume": vols,
            "margin_ratio": margins,
            "counterparty_risk": cps,
            "corridor_risk": corrs,
        }

    def test_volume_change_is_positive_for_growing_volume(self):
        sig = compute_signature(self._make_windows(vol_end=9000.0))
        assert sig.volume_change > 0

    def test_margin_change_is_negative_for_collapsing_margin(self):
        sig = compute_signature(self._make_windows(margin_end=0.03))
        assert sig.margin_change < 0

    def test_returns_zero_signature_if_not_enough_windows(self):
        tiny = {"monthly_volume": [np.ones(21)] * 3}
        sig = compute_signature(tiny, baseline_windows=3)
        assert sig.volume_change == 0.0


class TestCausalAssessment:
    def test_end_to_end_uses_simulator_benign_customer(self):
        from app.drift.simulator import generate_customer
        cust = generate_customer("bdd-test", "BDD Benign", "benign_expansion", seed=42)
        verdict = causal_assessment(cust.causal_windows())
        assert verdict.label == "benign"

    def test_end_to_end_uses_simulator_risk_customer(self):
        from app.drift.simulator import generate_customer
        cust = generate_customer("bdd-test", "BDD Risk", "combined", seed=42)
        verdict = causal_assessment(cust.causal_windows())
        assert verdict.label == "risk"
