"""
Tests for the source-adapter cost layer and carcasses (``app.sources``).

The shared contract (EntitySnapshot, PublicSignal, SnapshotDiff, diff_snapshots,
the RegistryAdapter ABC) is covered by ``test_sources_base.py``. THESE tests
cover the carcass layer added on top: the free-vs-paid registry classification,
the CostMixin metadata, and that carcass bodies fail with the right error so a
"paid, skipped on purpose" source is never mistaken for "free, not built yet".
"""

from __future__ import annotations

import pytest

from app.sources import (
    ALL_ADAPTERS,
    REGISTRY,
    SourceUnavailableError,
    catalogue,
    get_adapter,
    skipped_adapters,
    usable_adapters,
)
from app.sources.base import RegistryAdapter
from app.sources.cost import ADAPTER_SIGNAL_TYPES, AdapterStatus, CostMixin, SourceCost
from app.sources.zefix import ZefixAdapter


# --------------------------------------------------------------------------- #
# Registry classification — the core deliverable: which sources are free.      #
# --------------------------------------------------------------------------- #
class TestRegistryClassification:
    def test_ten_adapters_registered(self):
        assert len(ALL_ADAPTERS) == 10
        assert len(REGISTRY) == 10  # source_names are unique

    def test_usable_are_the_eight_free_sources(self):
        # event_registry upgraded from SKIPPED → PLANNED: hackathon key available,
        # adapter fully implemented (fetch_signals runs; returns [] when key absent).
        # Its cost is FREEMIUM, so the clean skipped⟺paid biconditional still holds.
        assert {a.source_name for a in usable_adapters()} == {
            "zefix", "gleif", "opensanctions", "gdelt",
            "event_registry", "firecrawl", "wayback", "whois",
        }

    def test_skipped_are_the_two_paid_sources(self):
        assert {a.source_name for a in skipped_adapters()} == {
            "open_corporates", "crunchbase",
        }

    def test_skipped_iff_paid_invariant(self):
        # The whole free/paid decision rests on this equivalence.
        for a in ALL_ADAPTERS:
            assert a.is_skipped() == (a.cost is SourceCost.PAID), a.source_name

    def test_planned_iff_free_or_freemium(self):
        for a in usable_adapters():
            assert a.cost in (SourceCost.FREE, SourceCost.FREEMIUM)

    def test_key_requirement_matches_cost_tier(self):
        # Fully-free sources must not need a key; the free-tier (FREEMIUM) ones
        # — OpenSanctions (hosted) and Firecrawl (cloud) — do.
        for a in ALL_ADAPTERS:
            if a.cost is SourceCost.FREE:
                assert a.requires_api_key is False, a.source_name
            elif a.cost is SourceCost.FREEMIUM:
                assert a.requires_api_key is True, a.source_name

    def test_every_adapter_has_complete_metadata(self):
        for a in ALL_ADAPTERS:
            assert a.source_name and a.display_name and a.base_url
            assert a.use_cases, a.source_name
            assert a.signal_types, a.source_name

    def test_declared_signal_types_are_known(self):
        # Every docstring claims signal_types is a subset of ADAPTER_SIGNAL_TYPES;
        # guard it so a future typo can't drift undetected.
        known = set(ADAPTER_SIGNAL_TYPES)
        for a in ALL_ADAPTERS:
            assert set(a.signal_types) <= known, (a.source_name, a.signal_types)

    def test_adapter_signal_types_superset_of_brief_five(self):
        # ADAPTER_SIGNAL_TYPES must stay a superset of the AMINA brief's five.
        from app.drift.public_intel import SIGNAL_TYPES

        assert set(SIGNAL_TYPES) <= set(ADAPTER_SIGNAL_TYPES)

    def test_get_adapter_roundtrip(self):
        assert get_adapter("zefix") is ZefixAdapter
        with pytest.raises(KeyError):
            get_adapter("does-not-exist")

    def test_catalogue_is_serializable_and_complete(self):
        cat = catalogue()
        assert len(cat) == 10
        # GLEIF is the canonical FREE / no-key source.
        gleif = next(c for c in cat if c["source_name"] == "gleif")
        assert gleif["is_free"] is True
        assert gleif["cost"] == "free"
        assert gleif["status"] == "planned"
        assert gleif["requires_api_key"] is False
        # ZEFIX is FREEMIUM: free but needs a registered Basic-auth account
        # (verified live — 401 without credentials), so is_free is False.
        zefix = next(c for c in cat if c["source_name"] == "zefix")
        assert zefix["cost"] == "freemium"
        assert zefix["requires_api_key"] is True
        assert zefix["is_free"] is False


# --------------------------------------------------------------------------- #
# Carcass behaviour — right error for the right reason. fetch is async.        #
# --------------------------------------------------------------------------- #
class TestCarcassBehaviour:
    async def test_planned_adapter_raises_not_implemented(self):
        # Free source whose carcass is not built yet — both entry points.
        # GDELT is a representative still-unbuilt PLANNED adapter (ZEFIX and
        # GLEIF are now implemented; ZEFIX without credentials degrades to
        # None/[] rather than raising — see test_zefix.py).
        from app.sources.gdelt import GdeltAdapter

        with pytest.raises(NotImplementedError):
            await GdeltAdapter().fetch("c", "Helvetia AG")
        with pytest.raises(NotImplementedError):
            await GdeltAdapter().fetch_signals("c", "Helvetia AG")

    async def test_zefix_without_credentials_degrades_quietly(self):
        # The one implemented free adapter: no account configured → graceful
        # no-op, NOT a NotImplementedError carcass.
        adapter = ZefixAdapter(username="", password="")
        assert await adapter.fetch("c", "Helvetia AG") is None
        assert await adapter.fetch_signals("c", "Helvetia AG") == []

    async def test_skipped_adapter_raises_source_unavailable(self):
        # Paid source, intentionally skipped — a DIFFERENT error type.
        for cls in skipped_adapters():
            with pytest.raises(SourceUnavailableError):
                await cls().fetch("c", "x")
            with pytest.raises(SourceUnavailableError):
                await cls().fetch_signals("c", "x")

    def test_skipped_source_unavailable_is_not_notimplemented(self):
        # Guard the distinction explicitly: SourceUnavailableError must not be a
        # NotImplementedError, or callers could not tell skip from to-do.
        assert not issubclass(SourceUnavailableError, NotImplementedError)


# --------------------------------------------------------------------------- #
# CostMixin wiring.                                                            #
# --------------------------------------------------------------------------- #
class TestCostMixin:
    def test_all_adapters_are_cost_aware_registry_adapters(self):
        for cls in ALL_ADAPTERS:
            assert issubclass(cls, CostMixin)
            assert issubclass(cls, RegistryAdapter)

    def test_record_url_defaults_to_none_then_overridable(self):
        from app.sources.firecrawl import FirecrawlAdapter

        # Firecrawl scrapes an arbitrary URL — no canonical record link.
        assert FirecrawlAdapter().record_url("x") is None
        # ZEFIX cites the company record.
        assert "CHE-9" in ZefixAdapter().record_url("CHE-9")

    def test_source_name_enforcement_still_applies_through_mixin(self):
        # The mixin must NOT bypass the base class's source_name requirement:
        # a concrete adapter that forgets source_name still fails at class
        # creation time.
        with pytest.raises(TypeError):
            class Broken(CostMixin, RegistryAdapter):
                cost = SourceCost.FREE
                status = AdapterStatus.PLANNED

                async def fetch(self, drift_id, name, **kwargs):
                    return None

                async def fetch_signals(self, drift_id, name, since_month=0, **kwargs):
                    return []


def test_registry_adapter_is_abstract():
    # The base contract cannot be instantiated directly.
    with pytest.raises(TypeError):
        RegistryAdapter()  # type: ignore[abstract]
