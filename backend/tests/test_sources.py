"""
Unit tests for the source-adapter scaffolding (``app.sources``).

These cover the *carcass* contract, not real network behaviour (there is none
yet): the shared diff fundamentals, the canonical snapshot, the free-vs-paid
registry classification, and that carcass bodies fail with the right error so a
"paid, skipped on purpose" source is never mistaken for "free, not built yet".
"""

from __future__ import annotations

import pytest

from app.drift.public_intel import PublicSignal
from app.sources import (
    ALL_ADAPTERS,
    REGISTRY,
    EntitySnapshot,
    SourceUnavailableError,
    catalogue,
    get_adapter,
    skipped_adapters,
    usable_adapters,
)
from app.sources.base import AdapterStatus, RegistryAdapter, SourceCost
from app.sources.zefix import ZefixAdapter


def _snapshot(**overrides) -> EntitySnapshot:
    """A baseline Swiss-company snapshot; override fields to model a change."""
    base = {
        "entity_id": "CHE-123.456.789",
        "source_id": "zefix",
        "legal_name": "Helvetia Trading AG",
        "legal_form": "AG",
        "jurisdiction": "CH-ZH",
        "registered_address": "Bahnhofstrasse 1, 8001 Zürich",
        "status": "ACTIVE",
        "owners": ["Anna Muster"],
        "domain": "helvetia-trading.ch",
    }
    base.update(overrides)
    return EntitySnapshot(**base)


# --------------------------------------------------------------------------- #
# Registry classification — the core deliverable: which sources are free.      #
# --------------------------------------------------------------------------- #
class TestRegistryClassification:
    def test_ten_adapters_registered(self):
        assert len(ALL_ADAPTERS) == 10
        assert len(REGISTRY) == 10  # source_ids are unique

    def test_usable_are_the_seven_free_sources(self):
        assert {a.source_id for a in usable_adapters()} == {
            "zefix", "gleif", "opensanctions", "gdelt",
            "firecrawl", "wayback", "whois",
        }

    def test_skipped_are_the_three_paid_sources(self):
        assert {a.source_id for a in skipped_adapters()} == {
            "open_corporates", "event_registry", "crunchbase",
        }

    def test_skipped_iff_paid_invariant(self):
        # The whole free/paid decision rests on this equivalence.
        for a in ALL_ADAPTERS:
            assert (a.status is AdapterStatus.SKIPPED) == (a.cost is SourceCost.PAID), (
                a.source_id
            )

    def test_planned_iff_free_or_freemium(self):
        for a in usable_adapters():
            assert a.cost in (SourceCost.FREE, SourceCost.FREEMIUM)

    def test_freemium_sources_require_a_key(self):
        # OpenSanctions (hosted) and Firecrawl (cloud) are the free-tier ones
        # that still need a key; the fully-free ones must not.
        for a in ALL_ADAPTERS:
            if a.cost is SourceCost.FREE:
                assert a.requires_api_key is False, a.source_id

    def test_every_adapter_has_complete_metadata(self):
        for a in ALL_ADAPTERS:
            assert a.source_id and a.display_name and a.base_url
            assert a.use_cases, a.source_id
            assert a.signal_types, a.source_id

    def test_get_adapter_roundtrip(self):
        assert get_adapter("zefix") is ZefixAdapter
        with pytest.raises(KeyError):
            get_adapter("does-not-exist")

    def test_catalogue_is_serializable_and_complete(self):
        cat = catalogue()
        assert len(cat) == 10
        zefix = next(c for c in cat if c["source_id"] == "zefix")
        assert zefix["is_free"] is True
        assert zefix["cost"] == "free"
        assert zefix["status"] == "planned"


# --------------------------------------------------------------------------- #
# Carcass behaviour — right error for the right reason.                        #
# --------------------------------------------------------------------------- #
class TestCarcassBehaviour:
    def test_planned_adapter_fetch_raises_not_implemented(self):
        # Free source, simply not built yet.
        with pytest.raises(NotImplementedError):
            ZefixAdapter().fetch("CHE-123.456.789")

    def test_skipped_adapter_fetch_raises_source_unavailable(self):
        # Paid source, intentionally skipped — a DIFFERENT error type.
        for cls in skipped_adapters():
            with pytest.raises(SourceUnavailableError):
                cls().fetch("anything")

    def test_skipped_source_unavailable_is_not_notimplemented(self):
        # Guard the distinction explicitly: SourceUnavailableError must not be a
        # NotImplementedError, or callers could not tell skip from to-do.
        assert not issubclass(SourceUnavailableError, NotImplementedError)

    def test_fetch_and_diff_on_skipped_fails_fast(self):
        cls = get_adapter("crunchbase")
        with pytest.raises(SourceUnavailableError):
            cls().fetch_and_diff("x", _snapshot())


# --------------------------------------------------------------------------- #
# Generic diff fundamentals — base-class behaviour, no network.               #
# --------------------------------------------------------------------------- #
class TestGenericDiff:
    def test_no_change_yields_no_signals(self):
        a = ZefixAdapter()
        assert a.diff(_snapshot(), _snapshot()) == []

    def test_name_change_emits_name_change_signal(self):
        a = ZefixAdapter()
        signals = a.diff(_snapshot(), _snapshot(legal_name="Helvetia Capital AG"))
        assert len(signals) == 1
        sig = signals[0]
        assert isinstance(sig, PublicSignal)
        assert sig.signal_type == "name_change"
        assert sig.severity == 0.85
        assert sig.raw_evidence == {
            "field": "legal_name",
            "old": "Helvetia Trading AG",
            "new": "Helvetia Capital AG",
        }
        # Citation URL is filled from the adapter's entity_url().
        assert sig.source_url and "CHE-123.456.789" in sig.source_url

    def test_multiple_field_changes_each_emit_a_signal(self):
        a = ZefixAdapter()
        current = _snapshot(
            legal_form="GmbH",
            jurisdiction="CH-ZG",
            status="IN_LIQUIDATION",
        )
        types = {s.signal_type for s in a.diff(_snapshot(), current)}
        assert types == {"legal_form_change", "jurisdiction_change", "status_change"}

    def test_none_field_is_never_a_change(self):
        # A source that does not report a field (None) must not fabricate a diff.
        a = ZefixAdapter()
        baseline = _snapshot(domain=None)
        current = _snapshot(domain="new-domain.ch")  # None -> value is not a change
        assert all(s.signal_type != "domain_change" for s in a.diff(baseline, current))

    def test_added_owner_emits_ownership_change(self):
        a = ZefixAdapter()
        current = _snapshot(owners=["Anna Muster", "Boris Newman"])
        signals = a.diff(_snapshot(), current)
        assert len(signals) == 1
        assert signals[0].signal_type == "ownership_change"
        assert signals[0].raw_evidence["added"] == "Boris Newman"

    def test_removed_owner_is_not_an_added_owner_signal(self):
        a = ZefixAdapter()
        current = _snapshot(owners=[])  # owner dropped, none added
        assert a.diff(_snapshot(), current) == []

    def test_month_is_propagated_to_signals(self):
        a = ZefixAdapter()
        signals = a.diff(_snapshot(), _snapshot(legal_name="X AG"), month=7)
        assert signals[0].month == 7


# --------------------------------------------------------------------------- #
# Snapshot model.                                                             #
# --------------------------------------------------------------------------- #
class TestEntitySnapshot:
    def test_to_dict_roundtrips_core_fields(self):
        snap = _snapshot()
        d = snap.to_dict()
        assert d["entity_id"] == "CHE-123.456.789"
        assert d["legal_form"] == "AG"
        assert d["owners"] == ["Anna Muster"]
        assert "fetched_at" in d  # ISO timestamp present

    def test_defaults_are_safe(self):
        snap = EntitySnapshot(entity_id="x", source_id="gleif")
        assert snap.owners == []
        assert snap.raw == {}
        assert snap.legal_name is None


def test_registry_adapter_is_abstract():
    # The base contract cannot be instantiated directly.
    with pytest.raises(TypeError):
        RegistryAdapter()  # type: ignore[abstract]
