"""
Feature extractor for AMINA social engineering / fraud cases.

Features chosen based on AMINA's published research:
"Human and operational vulnerabilities now represent the dominant
attack surface for institutional crypto participants."

We extract signals from THREE dimensions:
1. Behavioral: how does this request differ from client's baseline?
2. Contextual: is the channel/timing/destination unusual?
3. Linguistic: does the request show urgency, secrecy, pressure?

Voice features (deepfake detection) are a planned extension for when
we integrate librosa / Resemblyzer. For now we work with metadata.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from app.ml.base import FeatureExtractor
from app.schemas.case import Case


class SocialEngineeringFeatureExtractor(FeatureExtractor):
    """Extract features for voice/transaction social engineering detection."""
    
    feature_names: list[str] = [
        # === Amount features ===
        "amount_chf_log",              # Log of requested amount
        "amount_vs_typical_ratio",      # Ratio vs client's typical amount
        
        # === Temporal features ===
        "hour_of_day",                 # 0-23
        "hour_deviation_from_typical",  # How far from typical hours
        "is_weekend",                  # 0 or 1
        "is_outside_business_hours",   # 0 or 1
        
        # === Destination features ===
        "destination_is_whitelisted",   # 0 or 1 (highest signal!)
        "destination_country_risk",     # 0-1 (country risk score)
        "destination_is_new",          # 0 or 1
        
        # === Linguistic features (from transcript) ===
        "urgency_signals",             # Count of "now", "immediately", "urgent"
        "secrecy_signals",             # Count of "don't tell", "between us"
        "pressure_signals",            # Count of "deal", "waiting", "lost"
        "transcript_length",           # Words in transcript
        
        # === Client profile ===
        "client_aum_log",              # Log of AUM
        "client_is_pep",               # 0 or 1
        "days_since_last_review",      # Days
    ]
    
    feature_labels: dict[str, str] = {
        "amount_chf_log": "Transaction amount magnitude",
        "amount_vs_typical_ratio": "Amount is {value:.1f}x client's typical transaction",
        "hour_of_day": "Request submitted at hour {value:.0f}",
        "hour_deviation_from_typical": "{value:.1f} hours outside typical activity window",
        "is_weekend": "Request on weekend" if "{value}" == "1" else "Weekday request",
        "is_outside_business_hours": "Outside business hours (CH 8am-6pm)",
        "destination_is_whitelisted": "Destination wallet whitelisted",
        "destination_country_risk": "Destination country risk score: {value:.2f}",
        "destination_is_new": "First-time destination wallet",
        "urgency_signals": "{value:.0f} urgency markers in transcript",
        "secrecy_signals": "{value:.0f} secrecy markers in transcript",
        "pressure_signals": "{value:.0f} pressure tactics detected",
        "transcript_length": "Transcript: {value:.0f} words",
        "client_aum_log": "Client AUM tier",
        "client_is_pep": "Client is a Politically Exposed Person",
        "days_since_last_review": "{value:.0f} days since last compliance review",
    }
    
    # Country risk scores (simplified — in production this would come from a feed)
    COUNTRY_RISK: dict[str, float] = {
        "CH": 0.05, "DE": 0.08, "FR": 0.08, "AT": 0.10,
        "IT": 0.15, "ES": 0.18, "GB": 0.12,
        "US": 0.20, "SG": 0.25, "HK": 0.30,
        "AE": 0.35, "CN": 0.55, "RU": 0.85,
    }
    
    URGENCY_WORDS: set[str] = {
        "now", "immediately", "urgent", "quickly", "fast",
        "asap", "right away", "this minute", "without delay",
    }
    
    SECRECY_WORDS: set[str] = {
        "don't tell", "between us", "confidential", "secret",
        "no one", "private matter", "personal",
    }
    
    PRESSURE_WORDS: set[str] = {
        "deal", "waiting", "lost", "opportunity", "miss",
        "now or never", "partner is", "client is",
    }
    
    def extract(
        self,
        case: Case,
        client_context: dict | None = None,
    ) -> dict[str, float]:
        """Extract all features for one case."""
        data = case.context.data
        ctx = client_context or {}
        
        # === Amount (multi-source resolution for cross-case-type compatibility) ===
        # Different case types use different field names. We resolve to a single
        # canonical amount so the same extractor can handle social_engineering
        # (requested_amount_chf), xrpl_transaction (amount), and
        # investment_recommendation (no amount, use AUM-based proxy).
        amount = float(
            data.get("requested_amount_chf")
            or data.get("amount")
            or 0
        )
        typical_amount = float(ctx.get("typical_amount", max(amount * 0.1, 50_000)))
        
        # === Temporal (multi-source) ===
        call_ts_str = (
            data.get("call_timestamp")
            or data.get("tx_timestamp")
            or ""
        )
        try:
            call_ts = datetime.fromisoformat(call_ts_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            call_ts = datetime.utcnow()
        
        hour = call_ts.hour
        is_weekend = 1.0 if call_ts.weekday() >= 5 else 0.0
        typical_hours = ctx.get("typical_hours", list(range(8, 19)))
        
        if typical_hours:
            hour_deviation = min(
                abs(hour - h) for h in typical_hours
            )
        else:
            hour_deviation = 0.0
        
        is_outside_bh = 1.0 if hour < 8 or hour > 18 else 0.0
        
        # === Destination (multi-source) ===
        dest_wallet = (
            data.get("destination_wallet")
            or data.get("to_address")
            or ""
        )
        whitelist = ctx.get("whitelist_wallets", [])
        is_whitelisted = 1.0 if dest_wallet in whitelist else 0.0
        
        # XRPL-specific: counterparty already whitelisted/sanctioned flags
        if data.get("counterparty_whitelisted"):
            is_whitelisted = 1.0
        
        dest_country = data.get("destination_country", "CH")
        country_risk = self.COUNTRY_RISK.get(dest_country, 0.5)
        
        # Boost country risk if sanctions hit or mixer proximity
        if data.get("sanctions_match"):
            country_risk = 1.0
        elif data.get("mixer_proximity_hops", 99) <= 3:
            country_risk = max(country_risk, 0.9)
        
        is_new_destination = 1.0 if not is_whitelisted else 0.0
        
        # === Linguistic ===
        transcript = (data.get("transcript_excerpt") or "").lower()
        urgency = sum(1 for w in self.URGENCY_WORDS if w in transcript)
        secrecy = sum(1 for w in self.SECRECY_WORDS if w in transcript)
        pressure = sum(1 for w in self.PRESSURE_WORDS if w in transcript)
        transcript_length = float(len(transcript.split()))
        
        # === Client profile ===
        client_aum = float(ctx.get("aum_chf", 1_000_000))
        is_pep = 1.0 if ctx.get("is_pep") else 0.0
        days_since_review = float(ctx.get("days_since_review", 90))
        
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
            "transcript_length": transcript_length,
            "client_aum_log": float(np.log1p(client_aum)),
            "client_is_pep": is_pep,
            "days_since_last_review": days_since_review,
        }
