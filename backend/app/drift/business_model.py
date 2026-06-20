"""
Business-model drift comparator (Use cases 9, 10).

WHAT IT DOES
    Detects a *silent business-model pivot* by comparing a customer's website
    text at KYC onboarding (the Wayback snapshot) against its current content
    (the Firecrawl snapshot). Both texts are embedded with a small, offline
    sentence embedder; a large cosine distance between the two vectors means the
    public-facing business has materially changed — e.g. a "boutique
    consultancy" that now reads as a crypto exchange (Centra Tech pattern).

    distance ≥ ``BUSINESS_MODEL_DISTANCE_THRESHOLD`` (0.35) →
        ``PublicSignal(signal_type="business_model_change")``

    Severity follows the architecture-doc formula:
        ``clip(0.20 + 1.30 × cosine_distance, 0.0, 0.95)``

EMBEDDER  →  model2vec static embeddings (pure NumPy, no torch)
    ``minishlab/potion-base-8M`` is a static distillation of a MiniLM-class
    sentence transformer: inference is a token-embedding average in NumPy, so it
    needs neither torch nor onnxruntime and the ~30 MB model bundles into the
    image for a genuinely offline comparison. The embedder is loaded lazily and
    memoised module-wide (one model load per process).

GRACEFUL DEGRADATION
    This module mirrors the adapters' "degrade, never raise" philosophy. When
    either side's text is empty/too short, or model2vec is not installed, or the
    model fails to load, the comparator returns a *skipped* result with no signal
    and a machine-readable ``skipped_reason`` — it never raises into the scan.

RE-EMBEDDING CACHE
    Embedding is the only non-trivial cost here. The comparator accepts optional
    previously-computed embeddings (keyed by a text fingerprint) and reuses them
    only when the fingerprint still matches the supplied text; it always returns
    the embeddings it ended up using so the caller can persist them. The future
    aggregator stores these in ``EntitySnapshotDB.raw_data`` (the ORM column the
    ROADMAP refers to as ``extra``) to skip re-embedding on re-scan.

DEPENDENCY RULE
    Like everything under ``drift/``, this module does NOT import ``app.db`` or
    any source adapter. Texts (and any cached embeddings) are injected by the
    caller, which keeps the comparator a pure function and unit-testable without
    an ORM, a network, or even the model installed (tests inject a fake embedder).
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.core.logging import get_logger
from app.sources.base import PublicSignal

logger = get_logger(__name__)

__all__ = [
    "BUSINESS_MODEL_DISTANCE_THRESHOLD",
    "WEBSITE_COMPARISON_SOURCE",
    "BusinessModelComparison",
    "CachedEmbedding",
    "Embedder",
    "Model2VecEmbedder",
    "compare_business_model",
    "cosine_distance",
    "text_fingerprint",
]

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# model2vec static model — pure-NumPy inference, ~30 MB, fully offline once cached.
_MODEL_NAME = "minishlab/potion-base-8M"

# Cosine-distance threshold above which the business model is considered changed.
# Sourced from ROADMAP / docs (UC 9). Distance is 1 - cosine_similarity, so it
# lies in [0, 2]; 0.35 is "materially different topic", not mere copy edits.
BUSINESS_MODEL_DISTANCE_THRESHOLD = 0.35

# Severity = clip(base + slope × distance, 0, cap) — see source-integration-architecture.md §5.
_SEVERITY_BASE = 0.20
_SEVERITY_SLOPE = 1.30
_SEVERITY_CAP = 0.95

# Below this many characters a snapshot carries too little signal to embed
# meaningfully (an error page, a cookie wall, an empty Wayback capture). The
# comparator skips rather than emit a distance computed from noise.
_MIN_TEXT_CHARS = 50

# Human-readable provenance stamped on every business-model-change signal. Public
# so the public-intel aggregator can recognise *website-derived* pivot signals and
# corroborate them against *news-derived* ones (Event Registry / GDELT) for UC 10.
WEBSITE_COMPARISON_SOURCE = "website comparison (Wayback↔Firecrawl)"
# Internal alias kept so existing references read naturally at the emit site.
_SIGNAL_SOURCE = WEBSITE_COMPARISON_SOURCE


# ---------------------------------------------------------------------------
# Embedder abstraction
# ---------------------------------------------------------------------------

class Embedder(Protocol):
    """Anything that turns a batch of texts into a 2-D float embedding matrix.

    The contract is deliberately tiny so tests can inject a trivial fake and the
    production backend (model2vec) can be swapped for onnxruntime/MiniLM later
    without touching the comparator.
    """

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return an ``(len(texts), dim)`` float array of embeddings."""
        ...


class Model2VecEmbedder:
    """Default embedder — model2vec static embeddings (no torch, no network at run time).

    The underlying ``StaticModel`` is loaded lazily on first ``encode`` so that
    importing this module is cheap and so a missing/oversized model surfaces as a
    handled skip rather than an import-time crash.
    """

    def __init__(self, model_name: str = _MODEL_NAME) -> None:
        self._model_name = model_name
        self._model: object | None = None
        # Instance lock so a single embedder shared across threads loads once.
        self._load_lock = threading.Lock()

    def _load(self) -> object:
        if self._model is None:
            with self._load_lock:
                if self._model is None:  # re-check under the lock
                    from model2vec import StaticModel  # local import: optional dependency

                    self._model = StaticModel.from_pretrained(self._model_name)
                    logger.info("business_model_embedder_loaded", model=self._model_name)
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        model = self._load()
        # StaticModel.encode returns an (n, dim) float32 ndarray.
        return np.asarray(model.encode(texts), dtype=np.float64)  # type: ignore[attr-defined]


# Process-wide memoised default embedder, guarded by a lock so two concurrent
# first-use scans don't both pay the ~30 MB model load. ``_default_embedder_missing``
# latches ONLY when the package is genuinely absent (an unrecoverable state until
# the 'embeddings' extra is installed and the process restarts). A *transient*
# failure (e.g. a first-run download hiccup or a brief OOM) is logged but NOT
# latched, so a later scan can retry rather than disabling detection process-wide.
_default_embedder: Model2VecEmbedder | None = None
_default_embedder_missing = False
_embedder_lock = threading.Lock()


def _get_default_embedder() -> Embedder | None:
    """Return the memoised model2vec embedder, or ``None`` if it cannot be used.

    A ``None`` return is the signal-free degraded path: model2vec is an optional
    dependency, so absence is expected and must not raise. Absence (the package
    is not installed) is latched and logged once; a transient load failure is
    logged and retried on the next scan.
    """
    global _default_embedder, _default_embedder_missing
    # Fast paths without taking the lock.
    if _default_embedder is not None:
        return _default_embedder
    if _default_embedder_missing:
        return None
    with _embedder_lock:
        # Re-check inside the lock — another thread may have just loaded it.
        if _default_embedder is not None:
            return _default_embedder
        if _default_embedder_missing:
            return None
        try:
            embedder = Model2VecEmbedder()
            # Force the model load now so a missing dependency / download failure
            # surfaces here rather than mid-comparison.
            embedder.encode(["probe"])
            _default_embedder = embedder
            return embedder
        except ImportError as exc:
            # model2vec genuinely not installed → latch; nothing will change
            # until the 'embeddings' extra is added and the process restarts.
            _default_embedder_missing = True
            logger.warning(
                "business_model_embedder_missing",
                model=_MODEL_NAME,
                error=str(exc),
                hint="install the 'embeddings' extra to enable semantic website-drift detection",
            )
            return None
        except Exception as exc:  # noqa: BLE001 - transient: degrade but allow retry
            logger.warning(
                "business_model_embedder_load_failed",
                model=_MODEL_NAME,
                error=str(exc),
                hint="will retry on the next scan",
            )
            return None


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine distance ``1 - cos(a, b)`` clamped to ``[0.0, 2.0]``.

    A zero-norm or non-finite vector (degenerate embedding) yields the neutral
    orthogonal distance of ``1.0`` — "no measurable similarity" (NOT the true
    maximum of ``2.0``, which is reserved for genuinely opposite vectors) —
    rather than a divide-by-zero or a NaN that would silently read as "identical"
    (since every
    NaN comparison is False, an un-guarded NaN slips through the clamp as 1.0 → a
    spurious distance of 0.0). Guarding here keeps a bad embedding visible as
    "different", never as a false match.
    """
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0 or not np.isfinite(na) or not np.isfinite(nb):
        return 1.0
    similarity = float(np.dot(a, b) / (na * nb))
    # Float error can push this a hair outside [-1, 1]; clamp before subtracting.
    similarity = max(-1.0, min(1.0, similarity))
    return 1.0 - similarity


def text_fingerprint(text: str) -> str:
    """Stable SHA-256 hex digest of ``text`` — the re-embedding cache key.

    The caller persists ``(fingerprint, vector)`` alongside the snapshot and may
    reuse the vector only while the fingerprint still matches the current text.

    Note: ``compare_business_model`` fingerprints the *stripped* text it actually
    embeds, so a cache hit on re-scan is automatic as long as reads flow back
    through that function. A caller computing its own key for raw (unstripped)
    text would see a mismatch and harmlessly re-embed — fingerprint the same
    normalised text the comparator embeds if you cache-key independently.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CachedEmbedding:
    """A previously-computed embedding plus the fingerprint of the text it covers.

    Reused by ``compare_business_model`` only when ``fingerprint`` matches the
    fingerprint of the text passed in for the same side, so a stale cache from an
    earlier, different snapshot is never silently trusted.
    """

    fingerprint: str
    vector: list[float]


@dataclass(frozen=True)
class BusinessModelComparison:
    """Outcome of one Wayback↔Firecrawl business-model comparison.

    ``signal`` is populated only when ``is_change`` is true. ``wayback_embedding``
    / ``current_embedding`` always carry the embeddings actually used (freshly
    computed or reused) so the caller can persist them for the next scan; they are
    ``None`` only on a skipped comparison. ``skipped_reason`` is machine-readable:
    ``"empty_text"`` | ``"no_embedder"`` | ``"degenerate_embedding"`` | ``None`` (compared).
    """

    drift_id: str
    name: str
    distance: float
    is_change: bool
    signal: PublicSignal | None
    wayback_embedding: CachedEmbedding | None = None
    current_embedding: CachedEmbedding | None = None
    skipped_reason: str | None = None

    @property
    def skipped(self) -> bool:
        return self.skipped_reason is not None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _resolve_embedding(
    text: str,
    cached: CachedEmbedding | None,
    embedder: Embedder,
) -> CachedEmbedding:
    """Reuse ``cached`` when its fingerprint still matches ``text``, else re-embed."""
    fingerprint = text_fingerprint(text)
    if cached is not None and cached.fingerprint == fingerprint:
        return cached
    vector = embedder.encode([text])[0]
    return CachedEmbedding(fingerprint=fingerprint, vector=[float(x) for x in vector])


def _severity_for(distance: float) -> float:
    # The 0.0 lower bound is defensive only: callers reach this via
    # ``distance >= threshold`` (≥ 0.35 by default) and cosine distance is
    # non-negative, so the realistic floor is ~0.655. The clamp guards a
    # hypothetical negative ``threshold`` override, never normal operation.
    return float(np.clip(_SEVERITY_BASE + _SEVERITY_SLOPE * distance, 0.0, _SEVERITY_CAP))


def compare_business_model(
    drift_id: str,
    name: str,
    wayback_text: str | None,
    current_text: str | None,
    *,
    month: int = 0,
    embedder: Embedder | None = None,
    wayback_cache: CachedEmbedding | None = None,
    current_cache: CachedEmbedding | None = None,
    source_url: str | None = None,
    threshold: float = BUSINESS_MODEL_DISTANCE_THRESHOLD,
) -> BusinessModelComparison:
    """Compare onboarding vs current website text and flag a business-model pivot.

    Parameters
    ----------
    drift_id, name:
        Customer identifiers carried onto the result for routing/citation.
    wayback_text:
        Onboarding-era website text (``WaybackAdapter`` ``raw_data["website_text"]``).
    current_text:
        Current website text (``FirecrawlAdapter`` ``raw_data["website_text"]``).
    month:
        Scan month stamped on the emitted ``PublicSignal`` (default 0). Callers
        should pass the current scan month so confirmation-lift can time-align it.
    embedder:
        Embedder to use. Defaults to the memoised model2vec backend; tests inject
        a fake. When ``None`` and model2vec is unavailable, the comparison is
        skipped (``skipped_reason="no_embedder"``).
    wayback_cache, current_cache:
        Optional embeddings from a previous scan; reused only while their
        fingerprint matches the corresponding text. The returned comparison
        always carries the embeddings actually used, for persistence.
    source_url:
        Citation link for the signal (e.g. the current website URL).
    threshold:
        Distance at/above which a change fires (default 0.35).

    Returns
    -------
    BusinessModelComparison — never raises for missing text or a missing model.
    """
    # --- Guard: both sides need enough text to embed meaningfully. ---
    wb = (wayback_text or "").strip()
    cur = (current_text or "").strip()
    if len(wb) < _MIN_TEXT_CHARS or len(cur) < _MIN_TEXT_CHARS:
        logger.info(
            "business_model_skipped",
            drift_id=drift_id,
            reason="empty_text",
            wayback_chars=len(wb),
            current_chars=len(cur),
        )
        return BusinessModelComparison(
            drift_id=drift_id,
            name=name,
            distance=0.0,
            is_change=False,
            signal=None,
            skipped_reason="empty_text",
        )

    # --- Resolve the embedder (default model2vec; may be unavailable). ---
    active = embedder if embedder is not None else _get_default_embedder()
    if active is None:
        return BusinessModelComparison(
            drift_id=drift_id,
            name=name,
            distance=0.0,
            is_change=False,
            signal=None,
            skipped_reason="no_embedder",
        )

    # --- Embed (reusing cached vectors where the text is unchanged). ---
    wb_emb = _resolve_embedding(wb, wayback_cache, active)
    cur_emb = _resolve_embedding(cur, current_cache, active)

    wb_vec = np.asarray(wb_emb.vector, dtype=np.float64)
    cur_vec = np.asarray(cur_emb.vector, dtype=np.float64)
    # A model emitting NaN/inf (corrupt weights, tokenizer overflow) — or an
    # all-zero vector (empty/OOV text) — would make cosine_distance fall back to
    # its 1.0 sentinel, which is ≥ threshold and would fire a MAX-severity false
    # positive. Degrade to a skip instead, and do NOT return the embeddings (so the
    # bad vectors are never cached and the next scan re-embeds), honouring the
    # "never emit a signal from noise" contract.
    degenerate = (
        not np.isfinite(wb_vec).all()
        or not np.isfinite(cur_vec).all()
        or float(np.linalg.norm(wb_vec)) == 0.0
        or float(np.linalg.norm(cur_vec)) == 0.0
    )
    if degenerate:
        logger.warning("business_model_degenerate_embedding", drift_id=drift_id)
        return BusinessModelComparison(
            drift_id=drift_id,
            name=name,
            distance=0.0,
            is_change=False,
            signal=None,
            skipped_reason="degenerate_embedding",
        )

    distance = cosine_distance(wb_vec, cur_vec)
    is_change = distance >= threshold

    signal: PublicSignal | None = None
    if is_change:
        severity = _severity_for(distance)
        signal = PublicSignal(
            month=month,
            signal_type="business_model_change",
            headline=(
                f"Website content for {name} shifted materially since onboarding "
                f"(cosine distance {distance:.2f})"
            ),
            severity=severity,
            source=_SIGNAL_SOURCE,
            source_url=source_url,
        )

    logger.info(
        "business_model_compared",
        drift_id=drift_id,
        distance=round(distance, 4),
        is_change=is_change,
        reused_wayback=wb_emb is wayback_cache,
        reused_current=cur_emb is current_cache,
    )

    return BusinessModelComparison(
        drift_id=drift_id,
        name=name,
        distance=distance,
        is_change=is_change,
        signal=signal,
        wayback_embedding=wb_emb,
        current_embedding=cur_emb,
        skipped_reason=None,
    )
