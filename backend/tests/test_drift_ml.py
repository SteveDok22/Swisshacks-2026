"""
Tests for ml/extractors/drift.py (DriftFeatureExtractor) and the drift
training pipeline.

Coverage:
- Feature vector has exactly 20 dimensions with the expected names
- All features are finite floats
- extract() handles a minimal/empty dict gracefully (no KeyError)
- BOCPD changepoint flag maps correctly
- generate_drift_training_data() returns the right shape and label balance
- train_drift_model() fits without error and produces reasonable metrics
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.extractors.drift import DriftFeatureExtractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_analysis() -> dict:
    """Return the smallest analysis dict that DriftFeatureExtractor needs."""
    from app.drift.causal import CausalSignature, CausalVerdict
    from app.drift.dormancy import DormancyResult
    from app.drift.stability import StabilityResult

    causal = CausalVerdict(
        causal_llr=0.5,
        p_risk=0.6,
        label="ambiguous",
        signature=CausalSignature(
            volume_change=0.3,
            margin_change=-0.1,
            counterparty_change=0.05,
            corridor_change=0.02,
        ),
        contributions={},
    )
    stability = StabilityResult(
        suspicion=0.2,
        stability_anomaly=0.15,
        environmental_movement=0.1,
        own_volatility=0.12,
        cohort_volatility=0.30,
        is_suspicious=False,
        detail="ok",
    )
    dormancy = DormancyResult(
        dormancy_break=0.0,
        dormancy_depth=0.0,
        activation_strength=0.0,
        baseline_volume=5000.0,
        active_volume=5100.0,
        is_dormancy_break=False,
        detail="no dormancy break",
    )
    return {
        "latest_velocity": 0.5,
        "max_velocity": 1.2,
        "final_drift": 3.0,
        "bocpd_changepoint_day": 42,
        "internal_risk": 0.35,
        "propagated_risk": 0.01,
        "public_risk": 0.2,
        "confirmation_lift": 1.5,
        "causal": causal,
        "stability": stability,
        "dormancy": dormancy,
    }


# ---------------------------------------------------------------------------
# DriftFeatureExtractor
# ---------------------------------------------------------------------------

class TestDriftFeatureExtractor:
    def test_feature_count(self):
        extractor = DriftFeatureExtractor()
        assert len(extractor.feature_names) == 20

    def test_feature_names_unique(self):
        extractor = DriftFeatureExtractor()
        assert len(extractor.feature_names) == len(set(extractor.feature_names))

    def test_labels_cover_all_features(self):
        extractor = DriftFeatureExtractor()
        for name in extractor.feature_names:
            assert name in extractor.feature_labels

    def test_extract_returns_all_features(self):
        extractor = DriftFeatureExtractor()
        analysis = _make_minimal_analysis()
        features = extractor.extract(analysis)
        assert set(features.keys()) == set(extractor.feature_names)

    def test_all_features_are_floats(self):
        extractor = DriftFeatureExtractor()
        analysis = _make_minimal_analysis()
        features = extractor.extract(analysis)
        for name, value in features.items():
            assert isinstance(value, float), f"{name} is not float"
            assert np.isfinite(value), f"{name} is not finite"

    def test_bocpd_changepoint_set_when_day_present(self):
        extractor = DriftFeatureExtractor()
        analysis = _make_minimal_analysis()
        analysis["bocpd_changepoint_day"] = 100
        features = extractor.extract(analysis)
        assert features["bocpd_changepoint"] == 1.0

    def test_bocpd_changepoint_zero_when_none(self):
        extractor = DriftFeatureExtractor()
        analysis = _make_minimal_analysis()
        analysis["bocpd_changepoint_day"] = None
        features = extractor.extract(analysis)
        assert features["bocpd_changepoint"] == 0.0

    def test_extract_empty_dict_no_crash(self):
        """All fields default to safe floats when analysis dict is empty."""
        extractor = DriftFeatureExtractor()
        features = extractor.extract({})
        assert set(features.keys()) == set(extractor.feature_names)
        for value in features.values():
            assert np.isfinite(value)

    def test_to_dataframe_shape(self):
        extractor = DriftFeatureExtractor()
        analysis = _make_minimal_analysis()
        features = extractor.extract(analysis)
        df = extractor.to_dataframe(features)
        assert df.shape == (1, 20)
        assert list(df.columns) == extractor.feature_names

    def test_confirmation_lift_defaults_to_one(self):
        """confirmation_lift should default to 1.0 (neutral) when absent."""
        extractor = DriftFeatureExtractor()
        features = extractor.extract({})
        assert features["confirmation_lift"] == 1.0

    def test_causal_features_zero_when_causal_absent(self):
        extractor = DriftFeatureExtractor()
        analysis = _make_minimal_analysis()
        analysis["causal"] = None
        features = extractor.extract(analysis)
        assert features["causal_p_risk"] == 0.0
        assert features["causal_llr"] == 0.0
        assert features["causal_volume_change"] == 0.0
        assert features["causal_margin_change"] == 0.0


# ---------------------------------------------------------------------------
# Training data generation
# ---------------------------------------------------------------------------

class TestDriftTrainingData:
    def test_training_data_shape(self):
        from app.drift.simulator import SCENARIOS
        from app.ml.training import generate_drift_training_data

        n = 5
        df = generate_drift_training_data(n_per_scenario=n)
        # 20 features + label = 21 columns; one row per scenario × n
        assert df.shape == (len(SCENARIOS) * n, 21)

    def test_training_data_has_both_labels(self):
        from app.ml.training import generate_drift_training_data

        df = generate_drift_training_data(n_per_scenario=5)
        assert set(df["label"].unique()) == {0, 1}

    def test_training_data_risk_ratio(self):
        """6 risk scenarios + 2 benign → 75% risk rate."""
        from app.ml.training import generate_drift_training_data

        df = generate_drift_training_data(n_per_scenario=10)
        risk_rate = df["label"].mean()
        assert abs(risk_rate - 0.75) < 0.01

    def test_training_features_all_finite(self):
        from app.ml.training import generate_drift_training_data

        df = generate_drift_training_data(n_per_scenario=5)
        feature_cols = [c for c in df.columns if c != "label"]
        assert df[feature_cols].apply(lambda col: col.apply(np.isfinite)).all().all()


# ---------------------------------------------------------------------------
# Model training (slow — marked with a custom mark)
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestDriftModelTraining:
    def test_train_drift_model(self, tmp_path):
        from app.ml.training import train_drift_model

        model, metrics = train_drift_model(output_dir=tmp_path, n_per_scenario=15)

        assert metrics["roc_auc"] >= 0.70, "Model should achieve reasonable AUC on synthetic data"
        assert metrics["f1"] >= 0.70
        assert (tmp_path / "drift_v1.joblib").exists()

    def test_trained_model_case_type(self, tmp_path):
        from app.ml.training import train_drift_model
        from app.schemas.enums import CaseType

        model, _ = train_drift_model(output_dir=tmp_path, n_per_scenario=10)
        assert model.case_type == CaseType.KYC_DRIFT

    def test_trained_model_feature_count(self, tmp_path):
        from app.ml.training import train_drift_model

        model, _ = train_drift_model(output_dir=tmp_path, n_per_scenario=10)
        assert len(model.feature_extractor.feature_names) == 20
