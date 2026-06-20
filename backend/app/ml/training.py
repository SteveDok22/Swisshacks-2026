"""
Synthetic data generation + model training.

Covers two models:
  social_engineering_v1  — AMINA social engineering / fraud cases
  drift_v1               — KYC drift detection (20-dim feature vector from engine layers)

Run via CLI:
    python -m app.ml.training train-social-engineering
    python -m app.ml.training train-drift
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from app.core.config import (
    DRIFT_INTERNAL_ACCUMULATED_WEIGHT,
    DRIFT_INTERNAL_VELOCITY_WEIGHT,
    settings,
)
from app.core.logging import get_logger
from app.ml.base import RiskModel
from app.ml.extractors import DriftFeatureExtractor, SocialEngineeringFeatureExtractor
from app.schemas.enums import CaseType

logger = get_logger(__name__)


def generate_synthetic_social_engineering_data(
    n_samples: int = 5000,
    fraud_rate: float = 0.15,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Generate realistic synthetic data for AMINA social engineering.
    
    Design philosophy: we want the model to learn realistic patterns,
    not memorize coincidences. So we generate:
    - "Normal" cases: requests during business hours, to whitelisted wallets,
      reasonable amounts, no linguistic red flags
    - "Fraudulent" cases: off-hours, new destinations, high amounts,
      urgency/secrecy/pressure language
    - "Edge cases": some normal-looking fraud, some suspicious-looking legit
      (so model can't just use one feature)
    
    Why this matters for the demo:
    - SHAP explanations will reflect REAL signals (not data artifacts)
    - The compliance officer demo will feel believable
    """
    rng = np.random.default_rng(random_state)
    
    n_fraud = int(n_samples * fraud_rate)
    n_legit = n_samples - n_fraud
    
    samples = []
    
    # === Generate legitimate cases ===
    for _ in range(n_legit):
        # Most legit: small-to-medium amounts during business hours
        is_high_value = rng.random() < 0.1  # 10% are high-value but legit
        
        amount = (
            rng.lognormal(mean=14.5, sigma=1.2)  # ~CHF 2M median
            if is_high_value
            else rng.lognormal(mean=11.0, sigma=1.0)  # ~CHF 60K median
        )
        
        hour = int(rng.choice(range(8, 19), p=_business_hours_weights()))
        is_weekend = 1.0 if rng.random() < 0.05 else 0.0  # Rare weekend
        
        # Whitelisted destination is normal
        is_whitelisted = 1.0 if rng.random() < 0.85 else 0.0
        
        # Low-risk countries
        country_risk = rng.beta(2, 8) * 0.4
        
        # Minimal linguistic markers
        urgency = float(rng.poisson(0.3))
        secrecy = float(rng.poisson(0.1))
        pressure = float(rng.poisson(0.2))
        
        samples.append(_make_sample(
            amount=amount,
            typical_amount=amount * rng.uniform(0.5, 1.5),
            hour=hour,
            is_weekend=is_weekend,
            is_whitelisted=is_whitelisted,
            country_risk=country_risk,
            urgency=urgency,
            secrecy=secrecy,
            pressure=pressure,
            transcript_length=rng.integers(20, 200),
            # Wider AUM range to cover HNW clients (up to CHF 100M+)
            client_aum=rng.lognormal(15.5, 1.5),
            is_pep=1.0 if rng.random() < 0.05 else 0.0,
            days_since_review=rng.integers(7, 180),
            label=0,
        ))
    
    # === Generate fraudulent cases ===
    for _ in range(n_fraud):
        # Fraud profile: larger amounts, off-hours, new destinations
        
        amount = rng.lognormal(mean=14.0, sigma=1.5)  # Often large
        
        # Off-hours skewed
        if rng.random() < 0.7:
            hour = int(rng.choice([0, 1, 2, 3, 4, 5, 6, 7, 20, 21, 22, 23]))
        else:
            hour = int(rng.choice(range(8, 19)))  # Sometimes business hours too
        
        is_weekend = 1.0 if rng.random() < 0.4 else 0.0  # More weekend
        
        # New destination more likely
        is_whitelisted = 1.0 if rng.random() < 0.15 else 0.0
        
        # Higher-risk countries more common
        country_risk = rng.beta(3, 3) * 0.8 + 0.2
        
        # Linguistic markers MUCH higher
        urgency = float(rng.poisson(2.5))
        secrecy = float(rng.poisson(1.2))
        pressure = float(rng.poisson(2.0))
        
        samples.append(_make_sample(
            amount=amount,
            typical_amount=amount * rng.uniform(0.05, 0.3),  # Much larger than typical
            hour=hour,
            is_weekend=is_weekend,
            is_whitelisted=is_whitelisted,
            country_risk=country_risk,
            urgency=urgency,
            secrecy=secrecy,
            pressure=pressure,
            transcript_length=rng.integers(50, 500),
            # Wider AUM range for fraud targets
            client_aum=rng.lognormal(16.0, 1.5),
            is_pep=1.0 if rng.random() < 0.15 else 0.0,
            days_since_review=rng.integers(30, 365),
            label=1,
        ))
    
    df = pd.DataFrame(samples)
    return df.sample(frac=1, random_state=random_state).reset_index(drop=True)


def _business_hours_weights() -> list[float]:
    """Weights peaking around 10am-3pm."""
    hours = list(range(8, 19))
    weights = [1.0, 2.0, 3.0, 3.5, 3.0, 2.5, 3.0, 3.5, 2.5, 1.5, 1.0]
    total = sum(weights)
    return [w / total for w in weights]


def _make_sample(
    *,
    amount: float,
    typical_amount: float,
    hour: int,
    is_weekend: float,
    is_whitelisted: float,
    country_risk: float,
    urgency: float,
    secrecy: float,
    pressure: float,
    transcript_length: int,
    client_aum: float,
    is_pep: float,
    days_since_review: int,
    label: int,
) -> dict:
    """Build a single training sample with all features."""
    
    # Compute derived features same way extractor does
    typical_hours = list(range(8, 19))
    hour_deviation = min(abs(hour - h) for h in typical_hours)
    is_outside_bh = 1.0 if hour < 8 or hour > 18 else 0.0
    is_new_destination = 1.0 if is_whitelisted < 0.5 else 0.0
    
    return {
        "amount_chf_log": float(np.log1p(amount)),
        "amount_vs_typical_ratio": (
            amount / max(typical_amount, 1) if typical_amount > 0 else 1.0
        ),
        "hour_of_day": float(hour),
        "hour_deviation_from_typical": float(hour_deviation),
        "is_weekend": is_weekend,
        "is_outside_business_hours": is_outside_bh,
        "destination_is_whitelisted": is_whitelisted,
        "destination_country_risk": country_risk,
        "destination_is_new": is_new_destination,
        "urgency_signals": float(urgency),
        "secrecy_signals": float(secrecy),
        "pressure_signals": float(pressure),
        "transcript_length": float(transcript_length),
        "client_aum_log": float(np.log1p(client_aum)),
        "client_is_pep": is_pep,
        "days_since_last_review": float(days_since_review),
        "label": label,
    }


def train_social_engineering_model(
    output_dir: Path | None = None,
    n_samples: int = 5000,
) -> tuple[RiskModel, dict]:
    """
    Train the AMINA social engineering model end-to-end.
    
    Returns:
        (trained_model, metrics_dict)
    """
    output_dir = output_dir or Path(settings.model_dir)
    
    logger.info("training_started", model="social_engineering_v1", n_samples=n_samples)
    
    # === 1. Generate synthetic data ===
    df = generate_synthetic_social_engineering_data(n_samples=n_samples)
    logger.info(
        "synthetic_data_generated",
        total=len(df),
        fraud_count=int(df["label"].sum()),
        fraud_rate=float(df["label"].mean()),
    )
    
    # === 2. Train/test split ===
    feature_cols = [c for c in df.columns if c != "label"]
    X = df[feature_cols]
    y = df["label"]
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # === 3. Train XGBoost ===
    # PP5 lesson: scale_pos_weight handles class imbalance better than SMOTE
    # for tree-based models. Optuna tuning is a planned enhancement.
    pos_weight = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=pos_weight,
        random_state=42,
        eval_metric="logloss",
        n_jobs=-1,
    )
    
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )
    
    # === 4. Evaluate ===
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "classification_report": classification_report(
            y_test, y_pred, output_dict=True
        ),
    }
    
    logger.info(
        "training_completed",
        accuracy=round(metrics["accuracy"], 3),
        f1=round(metrics["f1"], 3),
        roc_auc=round(metrics["roc_auc"], 3),
    )
    
    # === 5. Wrap in RiskModel ===
    extractor = SocialEngineeringFeatureExtractor()
    risk_model = RiskModel(
        name="social_engineering_v1",
        version="0.1.0",
        case_type=CaseType.SOCIAL_ENGINEERING,
        feature_extractor=extractor,
        model=model,
    )
    
    # === 6. Save ===
    model_path = output_dir / "social_engineering_v1.joblib"
    risk_model.save(model_path)
    
    return risk_model, metrics


def _analyze_customer_for_training(
    cust: Any,
    cohort_cv: float = 0.30,
) -> dict:
    """
    Run the drift analysis pipeline on a SyntheticCustomer without
    needing a live DriftEngine (no contagion graph, no public signals).

    Used exclusively during model training to build the feature matrix.
    Public-risk and contagion are fixed at 0 — the model learns from the
    internal engine layers, which are fully deterministic.
    """
    from app.drift.bocpd import BOCPD, standardize
    from app.drift.causal import causal_assessment
    from app.drift.dormancy import assess_dormancy
    from app.drift.public_intel import PublicIntelResult, confirmation_lift
    from app.drift.stability import assess_stability
    from app.drift.velocity import compute_drift_series

    ds = compute_drift_series(cust.metric_windows())
    latest_velocity = ds.velocity[-1] if ds.velocity else 0.0
    max_velocity = max(ds.velocity) if ds.velocity else 0.0
    final_drift = ds.drift_bits[-1] if ds.drift_bits else 0.0

    daily = standardize(cust.daily_volume_series())
    bres = BOCPD(hazard=1 / 500).run(daily)
    cp_day = bres.detected_changepoints[0] if bres.detected_changepoints else None
    cp_month = cust.day_to_month(cp_day) if cp_day is not None else None

    if cp_month is not None:
        internal_peak_month = cp_month
    elif ds.velocity:
        internal_peak_month = ds.windows[int(np.argmax(ds.velocity))]
    else:
        internal_peak_month = None

    vel_norm = min(max_velocity / 3.0, 1.0)
    drift_norm = min(final_drift / 20.0, 1.0)
    internal_risk = min(
        DRIFT_INTERNAL_VELOCITY_WEIGHT * vel_norm
        + DRIFT_INTERNAL_ACCUMULATED_WEIGHT * drift_norm,
        1.0,
    )

    # No live public signals during offline training
    pi = PublicIntelResult()
    lift = confirmation_lift(
        pi.public_risk, internal_risk, pi.peak_signal_month, internal_peak_month
    )

    causal = causal_assessment(cust.causal_windows())
    stability = assess_stability(
        cust.monthly_volume,
        cohort_cv,
        counterparty_monthly=cust.counterparty_risk,
        corridor_monthly=cust.corridor_risk,
        public_risk=0.0,
    )
    dormancy = assess_dormancy(cust.monthly_volume)

    return {
        "latest_velocity": latest_velocity,
        "max_velocity": max_velocity,
        "final_drift": final_drift,
        "bocpd_changepoint_day": cp_day,
        "internal_risk": internal_risk,
        "propagated_risk": 0.0,
        "public_risk": 0.0,
        "confirmation_lift": lift,
        "causal": causal,
        "stability": stability,
        "dormancy": dormancy,
    }


# Scenarios flagged as risk (label=1); everything else is label=0.
_DRIFT_RISK_SCENARIOS = frozenset(
    {"volume_creep", "counterparty_migration", "corridor_shift", "combined", "dormancy_break", "suspicious_stability"}
)


def generate_drift_training_data(
    n_per_scenario: int = 30,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic drift training data.

    For each scenario, create ``n_per_scenario`` synthetic customers with
    varied seeds (different noise realizations), run the standalone analysis
    pipeline, extract the 20-dim feature vector, and label by scenario type.

    Labels:
        1 — risk scenarios (volume_creep, counterparty_migration,
            corridor_shift, combined, dormancy_break, suspicious_stability)
        0 — benign / stable (stable, benign_expansion)
    """
    from app.drift.simulator import SCENARIOS, generate_customer
    from app.drift.stability import cohort_volatility

    extractor = DriftFeatureExtractor()

    # Build a reference cohort once for a stable cohort_cv estimate
    stable_custs = [
        generate_customer(f"ref-{i}", f"Ref {i}", "stable", seed=1000 + i)
        for i in range(10)
    ]
    ref_cv = cohort_volatility([c.monthly_volume for c in stable_custs])

    rows: list[dict] = []
    rng = np.random.default_rng(random_state)
    base_seeds = rng.integers(0, 100_000, size=n_per_scenario)

    for scenario in SCENARIOS:
        label = 1 if scenario in _DRIFT_RISK_SCENARIOS else 0
        for i, seed in enumerate(base_seeds):
            cust = generate_customer(
                drift_id=f"train-{scenario}-{i}",
                name=f"Training {scenario} {i}",
                scenario=scenario,
                seed=int(seed),
            )
            analysis = _analyze_customer_for_training(cust, cohort_cv=ref_cv)
            features = extractor.extract(analysis)
            rows.append({**features, "label": label})

    df = pd.DataFrame(rows)
    return df.sample(frac=1, random_state=random_state).reset_index(drop=True)


def train_drift_model(
    output_dir: Path | None = None,
    n_per_scenario: int = 30,
) -> tuple[RiskModel, dict]:
    """
    Train the drift XGBoost model end-to-end.

    Returns:
        (trained_model, metrics_dict)
    """
    output_dir = output_dir or Path(settings.model_dir)

    logger.info("training_started", model="drift_v1", n_per_scenario=n_per_scenario)

    df = generate_drift_training_data(n_per_scenario=n_per_scenario)
    logger.info(
        "drift_training_data_generated",
        total=len(df),
        risk_count=int(df["label"].sum()),
        risk_rate=float(df["label"].mean()),
    )

    feature_cols = [c for c in df.columns if c != "label"]
    X = df[feature_cols]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pos_weight = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=pos_weight,
        random_state=42,
        eval_metric="logloss",
        n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "classification_report": classification_report(y_test, y_pred, output_dict=True),
    }
    logger.info(
        "drift_training_completed",
        accuracy=round(metrics["accuracy"], 3),
        f1=round(metrics["f1"], 3),
        roc_auc=round(metrics["roc_auc"], 3),
    )

    extractor = DriftFeatureExtractor()
    risk_model = RiskModel(
        name="drift_v1",
        version="0.1.0",
        case_type=CaseType.KYC_DRIFT,
        feature_extractor=extractor,
        model=model,
    )

    model_path = output_dir / "drift_v1.joblib"
    risk_model.save(model_path)
    return risk_model, metrics


# === CLI entry point ===
if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "train-social-engineering":
        model, metrics = train_social_engineering_model()
        print("\n=== Social Engineering Training metrics ===")
        print(f"Accuracy: {metrics['accuracy']:.3f}")
        print(f"F1 score: {metrics['f1']:.3f}")
        print(f"ROC-AUC:  {metrics['roc_auc']:.3f}")
        print(f"\nModel saved to: {settings.model_dir}/social_engineering_v1.joblib")
    elif cmd == "train-drift":
        model, metrics = train_drift_model()
        print("\n=== Drift Training metrics ===")
        print(f"Accuracy: {metrics['accuracy']:.3f}")
        print(f"F1 score: {metrics['f1']:.3f}")
        print(f"ROC-AUC:  {metrics['roc_auc']:.3f}")
        print(f"\nModel saved to: {settings.model_dir}/drift_v1.joblib")
    else:
        print("Usage:")
        print("  python -m app.ml.training train-social-engineering")
        print("  python -m app.ml.training train-drift")
