"""
Synthetic data generation + model training.

This is YOUR PP5 PATTERN applied to AMINA social engineering:
- Generate balanced synthetic data with realistic distributions
- Use SMOTE-like balancing (we'll add real SMOTE on Day 11)
- Train XGBoost with sensible defaults (Optuna optimization on Day 11)
- Save model to disk

Run via CLI:
    python -m app.ml.training train-social-engineering
"""

from __future__ import annotations

from pathlib import Path

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

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.base import RiskModel
from app.ml.extractors import SocialEngineeringFeatureExtractor
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
    # for tree-based models. Optuna tuning will come on Day 11.
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


# === CLI entry point ===
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "train-social-engineering":
        model, metrics = train_social_engineering_model()
        print("\n=== Training metrics ===")
        print(f"Accuracy: {metrics['accuracy']:.3f}")
        print(f"F1 score: {metrics['f1']:.3f}")
        print(f"ROC-AUC:  {metrics['roc_auc']:.3f}")
        print(f"\nModel saved to: {settings.model_dir}/social_engineering_v1.joblib")
    else:
        print("Usage:")
        print("  python -m app.ml.training train-social-engineering")
