"""examples/import is what people copy to start an import, so it must always load and match the importer's columns."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tests.importer.fake_api import FakeApi
from tgcli.importer.load import CSV_COLUMNS, KINDS, load
from tgcli.importer.plan import CREATE, build_plan
from tgcli.importer.state import fetch_state

TEMPLATES = Path(__file__).resolve().parents[2] / "examples" / "import"


@pytest.mark.parametrize("kind", KINDS)
def test_each_template_has_exactly_the_columns_the_importer_reads(kind):
    with open(TEMPLATES / f"{kind}.csv", newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == list(CSV_COLUMNS[kind])


def test_the_whole_folder_loads_without_a_single_problem():
    specs = load(TEMPLATES)
    assert sorted(specs.files) == sorted(f"{kind}.csv" for kind in KINDS)
    assert all(not item.problems for item in specs.networks + specs.groups + specs.resources + specs.devices)


def test_only_the_resource_examples_have_rows_so_a_copy_cannot_create_anything_else():
    specs = load(TEMPLATES)
    assert (len(specs.networks), len(specs.groups), len(specs.devices), len(specs.resources)) == (0, 0, 0, 2)


def test_the_examples_read_as_documented():
    one, two = load(TEMPLATES).resources
    assert (one.name, one.network, one.address, one.is_visible, one.protocols["allowIcmp"]) == ("App one", "Example Network", "app1.example.com", True, False)
    assert one.protocols["tcp"] == {"policy": "RESTRICTED", "ports": [{"start": 443, "end": 443}]}
    assert one.protocols["udp"] == {"policy": "RESTRICTED", "ports": []}
    assert [(a.group, a.security_policy) for a in one.access] == [("Example Group", None)]
    assert two.protocols["tcp"]["ports"] == [{"start": 80, "end": 80}, {"start": 443, "end": 443}, {"start": 8000, "end": 8100}]
    assert two.protocols["udp"] == {"policy": "ALLOW_ALL", "ports": []}
    assert [(a.group, a.security_policy) for a in two.access] == [("Example Group", None), ("Other Group", "Strict Policy")]


def test_once_the_names_exist_in_a_tenant_both_examples_would_be_created():
    api = FakeApi(
        networks=[{"id": "N1", "name": "Example Network"}],
        groups=[{"id": "G1", "name": "Example Group", "type": "MANUAL"}, {"id": "G2", "name": "Other Group", "type": "MANUAL"}],
        policies=[{"id": "P1", "name": "Standard Access", "policyType": "RESOURCE"}, {"id": "P2", "name": "Strict Policy", "policyType": "RESOURCE"}],
    )
    specs = load(TEMPLATES)
    rows = build_plan(specs, fetch_state(api, specs))
    assert [r.action for r in rows] == [CREATE, CREATE] and all(not r.warnings for r in rows)
    assert [len(r.grants) for r in rows] == [1, 2]


def test_with_the_placeholder_names_unchanged_nothing_is_created_on_a_real_tenant():
    specs = load(TEMPLATES)
    rows = build_plan(specs, fetch_state(FakeApi(), specs))
    assert [r.action for r in rows] == ["blocked", "blocked"]
