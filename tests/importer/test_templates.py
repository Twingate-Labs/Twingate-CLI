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
    assert (len(specs.networks), len(specs.groups), len(specs.devices), len(specs.resources)) == (0, 0, 0, 5)


def test_the_examples_read_as_documented():
    one, two, *typed = load(TEMPLATES).resources
    assert (one.name, one.network, one.address, one.is_visible, one.protocols["allowIcmp"]) == ("App one", "Example Network", "app1.example.com", True, False)
    assert one.protocols["tcp"] == {"policy": "RESTRICTED", "ports": [{"start": 443, "end": 443}]}
    assert one.protocols["udp"] == {"policy": "RESTRICTED", "ports": []}
    assert [(a.group, a.security_policy) for a in one.access] == [("Example Group", None)]
    assert two.protocols["tcp"]["ports"] == [{"start": 80, "end": 80}, {"start": 443, "end": 443}, {"start": 8000, "end": 8100}]
    assert two.protocols["udp"] == {"policy": "ALLOW_ALL", "ports": []}
    assert [(a.group, a.security_policy) for a in two.access] == [("Example Group", None), ("Other Group", "Strict Policy")]
    ssh, web, kube = typed
    assert (ssh.type, ssh.gateway, ssh.upstream, ssh.downstream) == ("SSH", "gateway.example.com", {"port": 22}, {"port": 22})
    assert (web.type, web.upstream, web.downstream, web.headers) == (
        "WEB_APP", {"port": 8080, "tlsMode": "VERIFY_FULL"}, {"port": 443, "tlsMode": "TLS13"}, [{"key": "X-Forwarded-Proto", "value": "https"}],
    )
    assert (kube.type, kube.cluster_ref, kube.upstream, kube.downstream) == ("KUBERNETES", "example-cluster", {"port": 6443}, {"port": 443})


def test_once_the_names_exist_in_a_tenant_every_example_would_be_created():
    api = FakeApi(
        gateways=[{"id": "GW1", "address": "gateway.example.com", "remoteNetwork": {"id": "N1", "name": "Example Network"}, "sshCA": {"id": "CA1"}}],
        networks=[{"id": "N1", "name": "Example Network"}],
        groups=[{"id": "G1", "name": "Example Group", "type": "MANUAL"}, {"id": "G2", "name": "Other Group", "type": "MANUAL"}],
        policies=[{"id": "P1", "name": "Standard Access", "policyType": "RESOURCE"}, {"id": "P2", "name": "Strict Policy", "policyType": "RESOURCE"}],
    )
    specs = load(TEMPLATES)
    rows = build_plan(specs, fetch_state(api, specs))
    assert [r.action for r in rows] == [CREATE] * 5 and all(not r.warnings for r in rows)
    assert [len(r.grants) for r in rows] == [1, 2, 1, 1, 1]
    assert [r.gateway_id for r in rows] == [None, None, "GW1", "GW1", "GW1"]


def test_with_the_placeholder_names_unchanged_nothing_is_created_on_a_real_tenant():
    specs = load(TEMPLATES)
    rows = build_plan(specs, fetch_state(FakeApi(), specs))
    assert [r.action for r in rows] == ["blocked"] * 5
