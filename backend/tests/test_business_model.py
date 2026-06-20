"""
Tests for the business-model drift comparator (``app.drift.business_model``).

These run fully offline and never load model2vec: every comparison injects a
``FakeEmbedder`` that maps known texts to fixed vectors, so the suite exercises
the comparator's logic (thresholding, severity, caching, graceful degradation)
without a model download or any network. The one place the real default backend
is touched, it is monkeypatched to the unavailable path.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.drift import business_model as bm
from app.drift.business_model import (
    BUSINESS_MODEL_DISTANCE_THRESHOLD,
    CachedEmbedding,
    compare_business_model,
    cosine_distance,
    text_fingerprint,
)

# Both snapshot texts must clear the _MIN_TEXT_CHARS (50) guard.
_ONBOARDING = "Helvetia Trading AG is a boutique import and export consultancy based in Zug."
_PIVOTED = "HelvetiaX is a regulated cryptocurrency exchange offering token swaps and custody."


class FakeEmbedder:
    """Deterministic embedder: returns a fixed vector per known text, counts calls."""

    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._mapping = mapping
        self.encoded: list[list[str]] = []

    def encode(self, texts: list[str]) -> np.ndarray:
        self.encoded.append(list(texts))
        return np.array([self._mapping[t] for t in texts], dtype=float)


def _orthogonal_embedder() -> FakeEmbedder:
    """Onboarding ⟂ current → cosine distance 1.0 (well above threshold)."""
    return FakeEmbedder({_ONBOARDING: [1.0, 0.0, 0.0], _PIVOTED: [0.0, 1.0, 0.0]})


# --------------------------------------------------------------------------- #
# Pure math helpers                                                            #
# --------------------------------------------------------------------------- #
class TestCosineDistance:
    def test_identical_vectors_zero_distance(self):
        v = np.array([0.2, 0.5, 0.9])
        assert cosine_distance(v, v) == pytest.approx(0.0, abs=1e-9)

    def test_orthogonal_vectors_unit_distance(self):
        assert cosine_distance(np.array([1.0, 0.0]), np.array([0.0, 1.0])) == pytest.approx(1.0)

    def test_opposite_vectors_max_distance(self):
        assert cosine_distance(np.array([1.0, 0.0]), np.array([-1.0, 0.0])) == pytest.approx(2.0)

    def test_zero_norm_degrades_to_unit_distance(self):
        # A degenerate (all-zero) embedding must not produce a NaN.
        assert cosine_distance(np.zeros(3), np.array([1.0, 2.0, 3.0])) == 1.0

    def test_non_finite_degrades_to_unit_distance(self):
        # A NaN/inf component must read as "different" (1.0), never slip the
        # clamp to a spurious 0.0 "identical".
        assert cosine_distance(np.array([np.nan, 1.0]), np.array([1.0, 0.0])) == 1.0
        assert cosine_distance(np.array([np.inf, 1.0]), np.array([1.0, 0.0])) == 1.0


class TestFingerprint:
    def test_stable_and_distinct(self):
        assert text_fingerprint("abc") == text_fingerprint("abc")
        assert text_fingerprint("abc") != text_fingerprint("abd")


# --------------------------------------------------------------------------- #
# Comparison — change / no-change                                             #
# --------------------------------------------------------------------------- #
class TestComparison:
    def test_large_distance_emits_signal(self):
        result = compare_business_model(
            "drift-009", "Helvetia Trading AG", _ONBOARDING, _PIVOTED,
            month=8, embedder=_orthogonal_embedder(), source_url="https://helvetia.example",
        )
        assert result.is_change is True
        assert result.skipped is False
        assert result.distance == pytest.approx(1.0)
        sig = result.signal
        assert sig is not None
        assert sig.signal_type == "business_model_change"
        assert sig.month == 8
        assert sig.source_url == "https://helvetia.example"
        # severity = clip(0.20 + 1.30 * 1.0, 0, 0.95) = 0.95
        assert sig.severity == pytest.approx(0.95)
        assert "Helvetia Trading AG" in sig.headline

    def test_small_distance_no_signal(self):
        embedder = FakeEmbedder({_ONBOARDING: [1.0, 0.0, 0.0], _PIVOTED: [1.0, 0.02, 0.0]})
        result = compare_business_model(
            "drift-009", "Helvetia Trading AG", _ONBOARDING, _PIVOTED, embedder=embedder,
        )
        assert result.is_change is False
        assert result.signal is None
        assert result.skipped is False
        assert result.distance < BUSINESS_MODEL_DISTANCE_THRESHOLD

    def test_distance_exactly_at_threshold_fires(self):
        # cos = 1 - 0.35 = 0.65 between two unit vectors → distance == threshold.
        theta = np.arccos(0.65)
        embedder = FakeEmbedder({
            _ONBOARDING: [1.0, 0.0],
            _PIVOTED: [float(np.cos(theta)), float(np.sin(theta))],
        })
        result = compare_business_model(
            "drift-009", "Helvetia Trading AG", _ONBOARDING, _PIVOTED, embedder=embedder,
        )
        assert result.distance == pytest.approx(BUSINESS_MODEL_DISTANCE_THRESHOLD, abs=1e-9)
        assert result.is_change is True

    def test_severity_follows_exact_formula_when_not_saturating(self):
        # At the threshold distance 0.35: severity = 0.20 + 1.30 * 0.35 = 0.655.
        theta = np.arccos(0.65)
        embedder = FakeEmbedder({
            _ONBOARDING: [1.0, 0.0],
            _PIVOTED: [float(np.cos(theta)), float(np.sin(theta))],
        })
        result = compare_business_model(
            "drift-009", "Helvetia Trading AG", _ONBOARDING, _PIVOTED, embedder=embedder,
        )
        assert result.signal is not None
        assert result.signal.severity == pytest.approx(0.655, abs=1e-6)

    def test_severity_capped_for_opposite_vectors(self):
        # Opposite vectors → distance 2.0 → raw 0.20 + 1.30*2.0 = 2.8, which MUST
        # clip to 0.95 so PublicSignal's [0,1] severity contract never raises.
        embedder = FakeEmbedder({_ONBOARDING: [1.0, 0.0], _PIVOTED: [-1.0, 0.0]})
        result = compare_business_model(
            "drift-009", "Helvetia Trading AG", _ONBOARDING, _PIVOTED, embedder=embedder,
        )
        assert result.distance == pytest.approx(2.0)
        assert result.signal is not None
        assert result.signal.severity == 0.95  # contract upheld, no exception


# --------------------------------------------------------------------------- #
# Graceful degradation                                                        #
# --------------------------------------------------------------------------- #
class TestDegradation:
    @pytest.mark.parametrize("wb,cur", [
        ("", _PIVOTED),
        (_ONBOARDING, ""),
        ("too short", _PIVOTED),
        ("a" * 49, _PIVOTED),  # one char under the _MIN_TEXT_CHARS (50) boundary
        (None, None),
    ])
    def test_empty_or_short_text_skips(self, wb, cur):
        embedder = _orthogonal_embedder()
        result = compare_business_model("drift-009", "X", wb, cur, embedder=embedder)
        assert result.skipped is True
        assert result.skipped_reason == "empty_text"
        assert result.signal is None
        # No embedding attempted when a side is unusable.
        assert embedder.encoded == []

    def test_exactly_min_chars_is_not_skipped(self):
        # Exactly at the boundary (50 chars) → proceeds to embedding, not skipped.
        wb = "a" * 50
        embedder = FakeEmbedder({wb: [1.0, 0.0, 0.0], _PIVOTED: [0.0, 1.0, 0.0]})
        result = compare_business_model("drift-009", "X", wb, _PIVOTED, embedder=embedder)
        assert result.skipped is False
        assert embedder.encoded != []

    def test_degenerate_embedding_skips_no_false_positive(self):
        # A model emitting NaN/inf must degrade to a skip, NOT a max-severity
        # signal (cosine_distance would otherwise fall back to 1.0 ≥ threshold).
        embedder = FakeEmbedder({_ONBOARDING: [float("nan"), 1.0], _PIVOTED: [0.0, 1.0]})
        result = compare_business_model(
            "drift-009", "Helvetia Trading AG", _ONBOARDING, _PIVOTED, embedder=embedder,
        )
        assert result.skipped is True
        assert result.skipped_reason == "degenerate_embedding"
        assert result.signal is None
        # Degenerate vectors are NOT returned for persistence (next scan re-embeds).
        assert result.wayback_embedding is None
        assert result.current_embedding is None

    def test_zero_norm_embedding_skips_no_false_positive(self):
        # An all-zero (finite) embedding — e.g. empty/OOV text — would slip past a
        # bare isfinite() guard and let cosine_distance return its 1.0 sentinel,
        # firing a max-severity false positive. It must degrade to a skip.
        embedder = FakeEmbedder({_ONBOARDING: [0.0, 0.0], _PIVOTED: [1.0, 2.0]})
        result = compare_business_model(
            "drift-009", "Helvetia Trading AG", _ONBOARDING, _PIVOTED, embedder=embedder,
        )
        assert result.skipped is True
        assert result.skipped_reason == "degenerate_embedding"
        assert result.signal is None
        assert result.wayback_embedding is None
        assert result.current_embedding is None

    def test_no_embedder_available_skips(self, monkeypatch):
        # Default backend unavailable (model2vec missing) and none injected.
        monkeypatch.setattr(bm, "_get_default_embedder", lambda: None)
        result = compare_business_model("drift-009", "X", _ONBOARDING, _PIVOTED)
        assert result.skipped is True
        assert result.skipped_reason == "no_embedder"
        assert result.signal is None


@pytest.fixture
def reset_embedder_globals():
    """Isolate the process-wide default-embedder memo across tests."""
    bm._default_embedder = None
    bm._default_embedder_missing = False
    yield
    bm._default_embedder = None
    bm._default_embedder_missing = False


class TestDefaultEmbedderResolution:
    """Exercises the lazy/memoised default model2vec backend resolution."""

    def test_missing_package_latches_and_then_skips(self, monkeypatch, reset_embedder_globals):
        class _Missing:
            def encode(self, texts):
                raise ImportError("No module named 'model2vec'")

        monkeypatch.setattr(bm, "Model2VecEmbedder", lambda *a, **k: _Missing())
        # First resolution latches the missing state.
        assert bm._get_default_embedder() is None
        assert bm._default_embedder_missing is True
        # The comparator (no injected embedder) now degrades to a clean skip.
        result = compare_business_model("drift-009", "X", _ONBOARDING, _PIVOTED)
        assert result.skipped_reason == "no_embedder"

    def test_transient_failure_is_not_latched(self, monkeypatch, reset_embedder_globals):
        # A non-import failure (e.g. first-run download hiccup) must NOT disable
        # detection process-wide — a later scan is allowed to retry.
        class _Flaky:
            def encode(self, texts):
                raise RuntimeError("transient download failure")

        monkeypatch.setattr(bm, "Model2VecEmbedder", lambda *a, **k: _Flaky())
        assert bm._get_default_embedder() is None
        assert bm._default_embedder_missing is False


# --------------------------------------------------------------------------- #
# Re-embedding cache                                                          #
# --------------------------------------------------------------------------- #
class TestCache:
    def test_fresh_run_returns_embeddings_for_persistence(self):
        result = compare_business_model(
            "drift-009", "Helvetia Trading AG", _ONBOARDING, _PIVOTED,
            embedder=_orthogonal_embedder(),
        )
        assert result.wayback_embedding is not None
        assert result.current_embedding is not None
        assert result.wayback_embedding.fingerprint == text_fingerprint(_ONBOARDING)
        assert result.current_embedding.fingerprint == text_fingerprint(_PIVOTED)
        assert result.wayback_embedding.vector == [1.0, 0.0, 0.0]

    def test_matching_cache_is_reused_not_re_embedded(self):
        embedder = _orthogonal_embedder()
        wb_cache = CachedEmbedding(text_fingerprint(_ONBOARDING), [1.0, 0.0, 0.0])
        cur_cache = CachedEmbedding(text_fingerprint(_PIVOTED), [0.0, 1.0, 0.0])
        result = compare_business_model(
            "drift-009", "Helvetia Trading AG", _ONBOARDING, _PIVOTED,
            embedder=embedder, wayback_cache=wb_cache, current_cache=cur_cache,
        )
        # Both sides served from cache → embedder never called.
        assert embedder.encoded == []
        assert result.is_change is True
        assert result.wayback_embedding is wb_cache
        assert result.current_embedding is cur_cache

    def test_stale_cache_is_ignored_and_re_embedded(self):
        embedder = _orthogonal_embedder()
        # Fingerprint belongs to different text → must be discarded.
        stale = CachedEmbedding("deadbeef", [9.0, 9.0, 9.0])
        result = compare_business_model(
            "drift-009", "Helvetia Trading AG", _ONBOARDING, _PIVOTED,
            embedder=embedder, wayback_cache=stale,
        )
        # Wayback side re-embedded (stale), current side embedded (no cache).
        assert [_ONBOARDING] in embedder.encoded
        assert result.wayback_embedding is not None
        assert result.wayback_embedding.vector == [1.0, 0.0, 0.0]
        assert result.wayback_embedding.fingerprint == text_fingerprint(_ONBOARDING)
