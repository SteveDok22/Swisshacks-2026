"""
Tests for sources/base.py — EntitySnapshot, PublicSignal, SnapshotDiff,
diff_snapshots(), and RegistryAdapter ABC.

Covers:
- EntitySnapshot: field defaults, full construction, type correctness
- PublicSignal: with/without source_url, to_dict() shape
- SnapshotDiff: construction and field access
- diff_snapshots(): scalar field changes, list field (UBO/officer) changes,
  None-to-value and value-to-None transitions, no-change case, multiple
  simultaneous changes, severity ordering
- RegistryAdapter ABC: cannot instantiate, concrete subclass works, source_name
  enforcement, async method contract
- Integration: public_intel.py still generates valid PublicSignal objects;
  PublicSignalOut in schemas/drift.py accepts source_url
"""

from __future__ import annotations

import asyncio
import pytest
from datetime import UTC, datetime

from app.sources.base import (
    EntitySnapshot,
    PublicSignal,
    RegistryAdapter,
    SnapshotDiff,
    diff_snapshots,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap(
    customer_id: str = "drift-001",
    name: str = "Test Corp AG",
    source: str = "zefix",
    legal_form: str | None = "AG",
    jurisdiction: str | None = "CH",
    registered_address: str | None = "Bahnhofstrasse 1, Zurich",
    dissolution_status: str | None = "active",
    beneficial_owners: list[str] | None = None,
    officers: list[str] | None = None,
    raw_data: dict | None = None,
) -> EntitySnapshot:
    return EntitySnapshot(
        customer_id=customer_id,
        name=name,
        source=source,
        legal_form=legal_form,
        jurisdiction=jurisdiction,
        registered_address=registered_address,
        dissolution_status=dissolution_status,
        beneficial_owners=beneficial_owners or [],
        officers=officers or [],
        raw_data=raw_data or {},
    )


# ---------------------------------------------------------------------------
# EntitySnapshot
# ---------------------------------------------------------------------------

class TestEntitySnapshot:
    def test_required_fields_only(self):
        s = EntitySnapshot(customer_id="c-1", name="CorpX", source="zefix")
        assert s.customer_id == "c-1"
        assert s.name == "CorpX"
        assert s.source == "zefix"

    def test_defaults_are_safe(self):
        s = EntitySnapshot(customer_id="c-2", name="Y", source="gleif")
        assert s.legal_form is None
        assert s.jurisdiction is None
        assert s.registered_address is None
        assert s.dissolution_status is None
        assert s.beneficial_owners == []
        assert s.officers == []
        assert s.raw_data == {}

    def test_fetched_at_defaults_to_utc_now(self):
        before = datetime.now(UTC)
        s = EntitySnapshot(customer_id="c-3", name="Z", source="internal")
        after = datetime.now(UTC)
        assert before <= s.fetched_at <= after

    def test_explicit_fetched_at_is_preserved(self):
        t = datetime(2024, 6, 1, tzinfo=UTC)
        s = EntitySnapshot(customer_id="c-4", name="W", source="zefix", fetched_at=t)
        assert s.fetched_at == t

    def test_full_construction(self):
        s = _snap(
            beneficial_owners=["Alice AG", "Bob Holdings"],
            officers=["Jane CEO", "Max CFO"],
            raw_data={"uid": "CHE-123.456.789"},
        )
        assert s.beneficial_owners == ["Alice AG", "Bob Holdings"]
        assert s.officers == ["Jane CEO", "Max CFO"]
        assert s.raw_data["uid"] == "CHE-123.456.789"

    def test_mutable_defaults_are_independent(self):
        s1 = EntitySnapshot(customer_id="a", name="A", source="x")
        s2 = EntitySnapshot(customer_id="b", name="B", source="x")
        s1.beneficial_owners.append("Acme")
        assert s2.beneficial_owners == []


# ---------------------------------------------------------------------------
# PublicSignal
# ---------------------------------------------------------------------------

class TestPublicSignal:
    def test_without_source_url(self):
        sig = PublicSignal(
            month=5, signal_type="news", headline="Corp launches product",
            severity=0.15, source="trade press",
        )
        assert sig.source_url is None

    def test_with_source_url(self):
        sig = PublicSignal(
            month=3, signal_type="sanctions", headline="OFAC lists linked entity",
            severity=0.95, source="OFAC", source_url="https://ofac.example/entry/123",
        )
        assert sig.source_url == "https://ofac.example/entry/123"

    def test_to_dict_shape_without_url(self):
        sig = PublicSignal(month=1, signal_type="news", headline="h", severity=0.2, source="s")
        d = sig.to_dict()
        assert set(d.keys()) == {"month", "signal_type", "headline", "severity", "source", "source_url"}
        assert d["source_url"] is None

    def test_to_dict_shape_with_url(self):
        sig = PublicSignal(
            month=2, signal_type="adverse_media", headline="h",
            severity=0.8, source="Reuters", source_url="https://reuters.com/a",
        )
        d = sig.to_dict()
        assert d["source_url"] == "https://reuters.com/a"

    def test_to_dict_severity_is_rounded(self):
        sig = PublicSignal(month=0, signal_type="news", headline="h", severity=0.12345, source="s")
        assert sig.to_dict()["severity"] == pytest.approx(0.12, abs=0.005)

    def test_signal_type_values_are_free_text(self):
        for st in ("news", "sanctions", "adverse_media", "ownership_change", "funding_event"):
            sig = PublicSignal(month=0, signal_type=st, headline="h", severity=0.1, source="s")
            assert sig.signal_type == st


# ---------------------------------------------------------------------------
# SnapshotDiff
# ---------------------------------------------------------------------------

class TestSnapshotDiff:
    def test_construction(self):
        d = SnapshotDiff(
            field="name",
            old_value="OldCorp AG",
            new_value="NewCorp AG",
            drift_signal_type="name_changed",
            severity=0.7,
        )
        assert d.field == "name"
        assert d.drift_signal_type == "name_changed"
        assert d.severity == pytest.approx(0.7)

    def test_list_field_diff_has_none_placeholder(self):
        d = SnapshotDiff(
            field="beneficial_owners",
            old_value=None,
            new_value="New Owner AG",
            drift_signal_type="ubo_added",
            severity=0.6,
        )
        assert d.old_value is None
        assert d.new_value == "New Owner AG"


# ---------------------------------------------------------------------------
# diff_snapshots — core diff logic
# ---------------------------------------------------------------------------

class TestDiffSnapshotsNoChange:
    def test_identical_snapshots_return_empty_list(self):
        a = _snap()
        b = _snap()
        assert diff_snapshots(a, b) == []

    def test_both_none_fields_not_reported(self):
        a = _snap(legal_form=None, jurisdiction=None, registered_address=None, dissolution_status=None)
        b = _snap(legal_form=None, jurisdiction=None, registered_address=None, dissolution_status=None)
        assert diff_snapshots(a, b) == []

    def test_same_ubos_no_diff(self):
        a = _snap(beneficial_owners=["Alice", "Bob"])
        b = _snap(beneficial_owners=["Bob", "Alice"])  # order differs — still no diff
        assert diff_snapshots(a, b) == []

    def test_same_officers_no_diff(self):
        a = _snap(officers=["Jane CEO"])
        b = _snap(officers=["Jane CEO"])
        assert diff_snapshots(a, b) == []


class TestDiffSnapshotsScalarFields:
    def test_name_change_detected(self):
        a = _snap(name="OldCorp AG")
        b = _snap(name="NewCorp AG")
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        d = diffs[0]
        assert d.field == "name"
        assert d.drift_signal_type == "name_changed"
        assert d.old_value == "OldCorp AG"
        assert d.new_value == "NewCorp AG"
        assert d.severity == pytest.approx(0.70)

    def test_legal_form_change_detected(self):
        a = _snap(legal_form="AG")
        b = _snap(legal_form="GmbH")
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        assert diffs[0].drift_signal_type == "legal_form_changed"
        assert diffs[0].severity == pytest.approx(0.65)

    def test_jurisdiction_change_detected(self):
        a = _snap(jurisdiction="CH")
        b = _snap(jurisdiction="AE")
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        assert diffs[0].drift_signal_type == "jurisdiction_changed"
        assert diffs[0].severity == pytest.approx(0.80)

    def test_address_change_detected(self):
        a = _snap(registered_address="Zurich HQ")
        b = _snap(registered_address="Dubai Office")
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        assert diffs[0].drift_signal_type == "address_changed"
        assert diffs[0].severity == pytest.approx(0.40)

    def test_dissolution_status_change_detected(self):
        a = _snap(dissolution_status="active")
        b = _snap(dissolution_status="dissolved")
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        assert diffs[0].drift_signal_type == "dissolution_status_changed"
        assert diffs[0].severity == pytest.approx(0.90)

    def test_none_to_value_is_reported(self):
        a = _snap(legal_form=None)
        b = _snap(legal_form="AG")
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        assert diffs[0].old_value is None
        assert diffs[0].new_value == "AG"

    def test_value_to_none_is_reported(self):
        a = _snap(dissolution_status="active")
        b = _snap(dissolution_status=None)
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        assert diffs[0].old_value == "active"
        assert diffs[0].new_value is None


class TestDiffSnapshotsListFields:
    def test_ubo_added(self):
        a = _snap(beneficial_owners=["Alice"])
        b = _snap(beneficial_owners=["Alice", "Bob"])
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        assert diffs[0].drift_signal_type == "ubo_added"
        assert diffs[0].new_value == "Bob"
        assert diffs[0].old_value is None
        assert diffs[0].severity == pytest.approx(0.60)

    def test_ubo_removed(self):
        a = _snap(beneficial_owners=["Alice", "Bob"])
        b = _snap(beneficial_owners=["Alice"])
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        assert diffs[0].drift_signal_type == "ubo_removed"
        assert diffs[0].old_value == "Bob"
        assert diffs[0].new_value is None
        assert diffs[0].severity == pytest.approx(0.55)

    def test_officer_added(self):
        a = _snap(officers=[])
        b = _snap(officers=["Jane CEO"])
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        assert diffs[0].drift_signal_type == "officer_added"
        assert diffs[0].new_value == "Jane CEO"
        assert diffs[0].severity == pytest.approx(0.45)

    def test_officer_removed(self):
        a = _snap(officers=["Jane CEO", "Max CFO"])
        b = _snap(officers=["Jane CEO"])
        diffs = diff_snapshots(a, b)
        assert len(diffs) == 1
        assert diffs[0].drift_signal_type == "officer_removed"
        assert diffs[0].old_value == "Max CFO"
        assert diffs[0].severity == pytest.approx(0.40)

    def test_ubo_replacement_gives_add_and_remove(self):
        a = _snap(beneficial_owners=["Old Owner"])
        b = _snap(beneficial_owners=["New Owner"])
        diffs = diff_snapshots(a, b)
        signal_types = {d.drift_signal_type for d in diffs}
        assert signal_types == {"ubo_added", "ubo_removed"}

    def test_multiple_ubos_added(self):
        a = _snap(beneficial_owners=[])
        b = _snap(beneficial_owners=["Alice", "Bob", "Carol"])
        diffs = diff_snapshots(a, b)
        added = [d for d in diffs if d.drift_signal_type == "ubo_added"]
        assert len(added) == 3

    def test_list_field_diffs_are_sorted(self):
        # sorted() is applied to added/removed sets → deterministic output
        a = _snap(beneficial_owners=[])
        b = _snap(beneficial_owners=["Zeta Corp", "Alpha AG"])
        diffs = diff_snapshots(a, b)
        names = [d.new_value for d in diffs]
        assert names == sorted(names)


class TestDiffSnapshotsMultipleChanges:
    def test_multiple_scalar_changes_all_reported(self):
        a = _snap(name="OldCorp", jurisdiction="CH", dissolution_status="active")
        b = _snap(name="NewCorp", jurisdiction="AE", dissolution_status="dissolved")
        diffs = diff_snapshots(a, b)
        signal_types = {d.drift_signal_type for d in diffs}
        assert "name_changed" in signal_types
        assert "jurisdiction_changed" in signal_types
        assert "dissolution_status_changed" in signal_types

    def test_scalar_and_list_changes_combined(self):
        a = _snap(name="CorpA", beneficial_owners=["Alice"])
        b = _snap(name="CorpB", beneficial_owners=["Alice", "Bob"])
        diffs = diff_snapshots(a, b)
        signal_types = {d.drift_signal_type for d in diffs}
        assert "name_changed" in signal_types
        assert "ubo_added" in signal_types


# ---------------------------------------------------------------------------
# RegistryAdapter ABC
# ---------------------------------------------------------------------------

class TestRegistryAdapterABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            RegistryAdapter()  # type: ignore[abstract]

    def test_concrete_without_source_name_raises(self):
        with pytest.raises(TypeError, match="source_name"):
            class BadAdapter(RegistryAdapter):
                async def fetch(self, customer_id, name, **kwargs):
                    return None
                async def fetch_signals(self, customer_id, name, since_month=0, **kwargs):
                    return []

    def test_concrete_with_source_name_can_instantiate(self):
        class GoodAdapter(RegistryAdapter):
            source_name = "test_source"
            async def fetch(self, customer_id, name, **kwargs):
                return None
            async def fetch_signals(self, customer_id, name, since_month=0, **kwargs):
                return []

        adapter = GoodAdapter()
        assert adapter.source_name == "test_source"

    def test_fetch_returns_none_for_missing_entity(self):
        class NullAdapter(RegistryAdapter):
            source_name = "null"
            async def fetch(self, customer_id, name, **kwargs):
                return None
            async def fetch_signals(self, customer_id, name, since_month=0, **kwargs):
                return []

        async def _run():
            adapter = NullAdapter()
            result = await adapter.fetch("c-1", "Unknown Corp")
            assert result is None

        asyncio.run(_run())

    def test_fetch_returns_entity_snapshot(self):
        class StubAdapter(RegistryAdapter):
            source_name = "stub"
            async def fetch(self, customer_id, name, **kwargs):
                return EntitySnapshot(
                    customer_id=customer_id,
                    name=name,
                    source=self.source_name,
                    jurisdiction="CH",
                )
            async def fetch_signals(self, customer_id, name, since_month=0, **kwargs):
                return []

        async def _run():
            adapter = StubAdapter()
            snap = await adapter.fetch("c-2", "Test AG")
            assert isinstance(snap, EntitySnapshot)
            assert snap.source == "stub"
            assert snap.jurisdiction == "CH"

        asyncio.run(_run())

    def test_fetch_signals_returns_list(self):
        class SignalAdapter(RegistryAdapter):
            source_name = "signal_source"
            async def fetch(self, customer_id, name, **kwargs):
                return None
            async def fetch_signals(self, customer_id, name, since_month=0, **kwargs):
                return [
                    PublicSignal(
                        month=3,
                        signal_type="sanctions",
                        headline="Linked entity sanctioned",
                        severity=0.95,
                        source="OFAC",
                        source_url="https://ofac.example/entry",
                    )
                ]

        async def _run():
            adapter = SignalAdapter()
            signals = await adapter.fetch_signals("c-3", "Corp AG")
            assert len(signals) == 1
            assert signals[0].source_url == "https://ofac.example/entry"

        asyncio.run(_run())

    def test_since_month_parameter_is_accepted(self):
        received: list[int] = []

        class MonthAwareAdapter(RegistryAdapter):
            source_name = "month_source"
            async def fetch(self, customer_id, name, **kwargs):
                return None
            async def fetch_signals(self, customer_id, name, since_month=0, **kwargs):
                received.append(since_month)
                return []

        async def _run():
            adapter = MonthAwareAdapter()
            await adapter.fetch_signals("c-4", "Corp", since_month=5)

        asyncio.run(_run())
        assert received == [5]

    def test_source_name_class_variable_inherited(self):
        class BaseAdapter(RegistryAdapter):
            source_name = "shared"
            async def fetch(self, customer_id, name, **kwargs):
                return None
            async def fetch_signals(self, customer_id, name, since_month=0, **kwargs):
                return []

        class ChildAdapter(BaseAdapter):
            pass  # inherits source_name = "shared" — allowed

        assert ChildAdapter.source_name == "shared"
        adapter = ChildAdapter()
        assert adapter.source_name == "shared"


# ---------------------------------------------------------------------------
# Integration: public_intel.py still works after migration
# ---------------------------------------------------------------------------

class TestPublicIntelIntegration:
    def test_generate_signals_returns_public_signal_instances(self):
        from app.drift.public_intel import generate_signals_for_customer
        signals = generate_signals_for_customer(
            customer_id="drift-001",
            name="Viktor Antonov",
            scenario="volume_creep",
            months=18,
            drift_start_month=8,
            seed=42,
        )
        assert isinstance(signals, list)
        for s in signals:
            assert isinstance(s, PublicSignal)

    def test_generated_signals_have_source_url_attribute(self):
        from app.drift.public_intel import generate_signals_for_customer
        signals = generate_signals_for_customer(
            customer_id="drift-002",
            name="Helena Krause",
            scenario="counterparty_migration",
            months=18,
            drift_start_month=6,
            seed=7,
        )
        for s in signals:
            assert hasattr(s, "source_url")
            assert s.source_url is not None
            assert "drift-002" in s.source_url

    def test_to_dict_includes_source_url_key(self):
        from app.drift.public_intel import generate_signals_for_customer
        signals = generate_signals_for_customer(
            customer_id="drift-003",
            name="Tomas Lindqvist",
            scenario="corridor_shift",
            months=18,
            drift_start_month=7,
            seed=99,
        )
        assert signals  # at least one signal
        for s in signals:
            d = s.to_dict()
            assert "source_url" in d


class TestPublicSignalOutSchemaIntegration:
    def test_public_signal_out_accepts_source_url(self):
        from app.schemas.drift import PublicSignalOut
        out = PublicSignalOut(
            month=3,
            signal_type="sanctions",
            headline="OFAC listing",
            severity=0.95,
            source="OFAC",
            source_url="https://ofac.example/123",
        )
        assert out.source_url == "https://ofac.example/123"

    def test_public_signal_out_source_url_defaults_to_none(self):
        from app.schemas.drift import PublicSignalOut
        out = PublicSignalOut(
            month=1, signal_type="news", headline="h", severity=0.1, source="press"
        )
        assert out.source_url is None

    def test_public_signal_to_dict_maps_to_public_signal_out(self):
        from app.schemas.drift import PublicSignalOut
        sig = PublicSignal(
            month=5, signal_type="adverse_media", headline="Investigation",
            severity=0.75, source="Reuters", source_url="https://reuters.com/x",
        )
        out = PublicSignalOut(**sig.to_dict())
        assert out.month == 5
        assert out.source_url == "https://reuters.com/x"
