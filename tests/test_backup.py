"""Tests for the backup engine: collecting a tenant and writing it to disk."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from tgcli import backup
from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError, TwingateThrottleError
from tgcli.queries import backup as q

from .fake_tenant import FakeTenant, PAGE, edge, many

pytestmark = pytest.mark.filterwarnings("ignore")
NOW = datetime(2026, 10, 14, 15, 30, 0, tzinfo=timezone.utc)
ALL_NESTED = [(e.key, name) for e in q.ENTITIES for name in e.nested]


def ref(i: str) -> dict:
    return {"id": i, "name": f"n-{i}"}


def tenant_with_long_lists(n: int = 5) -> FakeTenant:
    """Every nested list holds n items, more than one page of PAGE."""
    users = [edge({"id": f"u{i}", "email": f"u{i}@x.io"}) for i in range(n)]
    refs = [edge(ref(f"r{i}")) for i in range(n)]
    access = [
        edge({"__typename": "Group" if i % 2 == 0 else "ServiceAccount", "id": f"p{i}", "name": f"P{i}"},
             securityPolicy=ref("sp"), accessPolicy={"mode": "MANUAL", "durationSeconds": None},
             approvalMode="MANUAL", expiresAt=None)
        for i in range(n)
    ]
    return FakeTenant({
        "groups": [{"id": "g1", "name": "G", "users": users, "resources": refs}],
        "users": [{"id": "u1", "email": "u1@x.io", "groups": refs}],
        "resources": [{"id": "res1", "name": "R", "__typename": "NetworkResource", "access": access, "approverGroups": refs}],
        "connectors": many("c", 1),
        "remote_networks": [{"id": "rn1", "name": "RN", "connectors": refs, "resources": refs, "gateways": [edge({"id": f"gw{i}", "address": f"a{i}"}) for i in range(n)]}],
        "devices": many("d", 1),
        "service_accounts": [{
            "id": "sa1", "name": "SA", "resources": refs,
            "keys": [edge({"id": f"k{i}", "name": f"key {i}", "status": "ACTIVE"}) for i in range(n)],
        }],
        "security_policies": [{"id": "sp1", "name": "SP", "groups": refs}],
        "dns_profiles": [{"id": "dp1", "name": "DP", "groups": refs}],
        "gateways": many("gw", 1),
        "certificate_authorities": [{"id": "ca1", "name": "CA", "__typename": "SSHCertificateAuthority"}],
    })


class TestCollect:
    def test_follows_top_level_pages_to_the_end(self):
        tenant = FakeTenant({"groups": [{"id": f"g{i}", "name": "x"} for i in range(5)], "users": many("u", 3)})
        collected = backup.collect(tenant)
        assert [g["id"] for g in collected.items["groups"]] == [f"g{i}" for i in range(5)]
        assert len(collected.items["users"]) == 3 and collected.problems == []

    def test_empty_tenant(self):
        collected = backup.collect(FakeTenant({}))
        assert all(items == [] for items in collected.items.values()) and collected.problems == []

    @pytest.mark.parametrize("entity,name", ALL_NESTED)
    def test_every_nested_list_is_completed_past_the_first_page(self, entity, name):
        collected = backup.collect(tenant_with_long_lists(5))
        item = collected.items[entity][0]
        assert len(item[name]) == 5 and collected.problems == []
        assert len(item[name]) > PAGE

    @pytest.mark.parametrize("entity,name", ALL_NESTED)
    def test_nested_lists_keep_api_order_without_duplicates(self, entity, name):
        collected = backup.collect(tenant_with_long_lists(7))
        item = collected.items[entity][0]
        ids = [x["principal"]["id"] if name == "access" else x["id"] for x in item[name]]
        assert len(ids) == len(set(ids)) == 7
        source = tenant_with_long_lists(7).data[entity][0][name]
        assert ids == [(e["node"]["id"]) for e in source]

    def test_short_nested_list_needs_no_extra_request(self):
        tenant = FakeTenant({"groups": [{"id": "g1", "name": "G", "users": [edge({"id": "u1", "email": "a@b"})], "resources": []}]})
        backup.collect(tenant)
        assert not any("(id: $id)" in query for query, _ in tenant.calls)

    def test_follow_up_queries_start_from_the_first_pages_cursor(self):
        tenant = tenant_with_long_lists(5)
        backup.collect(tenant)
        follow_ups = [v for query, v in tenant.calls if "(id: $id)" in query]
        assert follow_ups and all(v["cursor"] == f"c{PAGE}" for v in follow_ups[:1])

    def test_access_edges_are_flattened_with_principal_type_and_policy(self):
        collected = backup.collect(tenant_with_long_lists(3))
        first, second, _ = collected.items["resources"][0]["access"]
        assert first == {
            "principal": {"type": "Group", "id": "p0", "name": "P0"},
            "securityPolicy": ref("sp"), "accessPolicy": {"mode": "MANUAL", "durationSeconds": None},
            "approvalMode": "MANUAL", "expiresAt": None,
        }
        assert second["principal"]["type"] == "ServiceAccount"

    @pytest.mark.parametrize(
        "typename,label",
        [("NetworkResource", "NETWORK"), ("SSHResource", "SSH"), ("WebAppResource", "WEB_APP"),
         ("KubernetesResource", "KUBERNETES"), ("FutureResource", "FutureResource")],
    )
    def test_resources_get_a_type_label_instead_of_typename(self, typename, label):
        tenant = FakeTenant({"resources": [{"id": "r", "name": "R", "__typename": typename}]})
        resource = backup.collect(tenant).items["resources"][0]
        assert resource["type"] == label and "__typename" not in resource

    def test_top_level_count_mismatch_is_reported(self):
        tenant = FakeTenant({"users": many("u", 3)})
        tenant.total_override["users"] = 4
        problems = backup.collect(tenant).problems
        assert problems == ["users: API reports 4, backed up 3"]

    def test_nested_count_mismatch_is_reported_with_the_parent(self):
        tenant = tenant_with_long_lists(5)
        tenant.nested_total_override[("groups", "users")] = 6
        problems = backup.collect(tenant).problems
        assert problems == ["groups g1 users: API reports 6, backed up 5"]

    def test_parent_deleted_mid_backup_is_a_problem_not_a_crash(self):
        tenant = tenant_with_long_lists(5)
        tenant.vanished.add("g1")
        problems = backup.collect(tenant).problems
        assert any("g1" in p and "disappeared" in p for p in problems)

    def test_repeated_cursor_is_refused_instead_of_looping(self):
        tenant = FakeTenant({"users": many("u", 6)})
        tenant.stuck_cursor = True
        with pytest.raises(backup.BackupError, match="same page cursor"):
            backup.collect(tenant)

    def test_api_errors_propagate(self):
        tenant = FakeTenant({"users": many("u", 1)})
        tenant.error = TwingateAPIError("boom")
        with pytest.raises(TwingateAPIError):
            backup.collect(tenant)

    def test_progress_is_reported_per_entity(self):
        messages: list[str] = []
        backup.collect(FakeTenant({"users": many("u", 2)}), progress=messages.append)
        assert "Reading users..." in messages and "  2 users" in messages


def collected_sample() -> backup.Collected:
    return backup.collect(tenant_with_long_lists(3))


class TestWrite:
    def write(self, tmp_path, collected=None, name="out"):
        return backup.write_backup(collected or collected_sample(), tmp_path / name, session="s1", tenant="acme", now=NOW)

    def test_writes_one_file_per_entity_plus_manifest(self, tmp_path):
        result = self.write(tmp_path)
        assert sorted(p.name for p in result.path.iterdir()) == sorted(
            [e.file for e in q.ENTITIES] + [backup.MANIFEST_FILE]
        )
        assert result.counts == {e.key: 1 for e in q.ENTITIES}
        assert not (tmp_path / "out.partial").exists()

    def test_files_hold_the_collected_data_as_json(self, tmp_path):
        collected = collected_sample()
        result = self.write(tmp_path, collected)
        assert json.loads((result.path / "groups.json").read_text()) == collected.items["groups"]
        assert json.loads((result.path / "remote-networks.json").read_text()) == collected.items["remote_networks"]

    def test_non_ascii_names_are_written_as_utf8_not_escaped(self, tmp_path):
        collected = backup.collect(FakeTenant({"users": [{"id": "u", "email": "j@x.io", "firstName": "José", "lastName": "Ñandú"}]}))
        result = self.write(tmp_path, collected)
        raw = (result.path / "users.json").read_bytes().decode("utf-8")
        assert "José" in raw and "\\u" not in raw

    def test_manifest_records_counts_checksums_and_context(self, tmp_path):
        result = self.write(tmp_path)
        manifest = json.loads((result.path / backup.MANIFEST_FILE).read_text())
        assert manifest["format"] == 1 and manifest["tenant"] == "acme" and manifest["session"] == "s1"
        assert manifest["createdAt"] == "2026-10-14T15:30:00+00:00"
        assert manifest["verification"] == {"complete": True, "problems": []}
        for entity in q.ENTITIES:
            data = (result.path / entity.file).read_bytes()
            assert manifest["files"][entity.file] == {"count": len(json.loads(data)), "sha256": hashlib.sha256(data).hexdigest()}
        assert any("Secrets are never included" in note for note in manifest["notes"])

    def test_problems_are_recorded_in_the_manifest(self, tmp_path):
        collected = collected_sample()
        collected.problems.append("users: API reports 4, backed up 3")
        result = self.write(tmp_path, collected)
        manifest = json.loads((result.path / backup.MANIFEST_FILE).read_text())
        assert manifest["verification"] == {"complete": False, "problems": ["users: API reports 4, backed up 3"]}
        assert result.problems == ["users: API reports 4, backed up 3"]

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
    def test_directory_and_files_are_private_to_the_owner(self, tmp_path):
        old = os.umask(0o000)
        try:
            result = self.write(tmp_path)
        finally:
            os.umask(old)
        assert stat.S_IMODE(result.path.stat().st_mode) == 0o700
        assert {stat.S_IMODE(p.stat().st_mode) for p in result.path.iterdir()} == {0o600}

    def test_existing_output_directory_is_refused_and_left_alone(self, tmp_path):
        (tmp_path / "out").mkdir()
        (tmp_path / "out" / "keep.txt").write_text("mine")
        with pytest.raises(backup.BackupError, match="already exists"):
            self.write(tmp_path)
        assert (tmp_path / "out" / "keep.txt").read_text() == "mine"

    def test_leftover_partial_directory_is_refused_and_left_alone(self, tmp_path):
        (tmp_path / "out.partial").mkdir()
        (tmp_path / "out.partial" / "keep.txt").write_text("mine")
        with pytest.raises(backup.BackupError, match="left over"):
            self.write(tmp_path)
        assert (tmp_path / "out.partial" / "keep.txt").read_text() == "mine"
        assert not (tmp_path / "out").exists()

    def test_missing_parent_directories_are_created(self, tmp_path):
        result = backup.write_backup(collected_sample(), tmp_path / "a" / "b" / "out", session="s", tenant="t", now=NOW)
        assert (result.path / "manifest.json").is_file()

    def test_failure_midway_leaves_neither_final_nor_partial_directory(self, tmp_path, monkeypatch):
        real, calls = backup._write_private, []

        def flaky(path, content):
            calls.append(path.name)
            if len(calls) == 3:
                raise OSError("disk full")
            real(path, content)

        monkeypatch.setattr(backup, "_write_private", flaky)
        with pytest.raises(OSError, match="disk full"):
            self.write(tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_interruption_also_cleans_up(self, tmp_path, monkeypatch):
        def interrupted(path, content):
            raise KeyboardInterrupt

        monkeypatch.setattr(backup, "_write_private", interrupted)
        with pytest.raises(KeyboardInterrupt):
            self.write(tmp_path)
        assert list(tmp_path.iterdir()) == []


class TestDefaultOutputPath:
    def test_names_the_tenant_and_a_utc_timestamp(self):
        client = SimpleNamespace(url="https://acme.twingate.com/api/graphql/")
        assert str(backup.default_output_path(client, NOW)) == "twingate-backup-acme-20261014T153000Z"

    def test_staging_hostnames_use_the_tenant_part(self):
        client = SimpleNamespace(url="https://acme.stg.opstg.com/api/graphql/")
        assert str(backup.default_output_path(client, NOW)) == "twingate-backup-acme-20261014T153000Z"

    def test_unknown_when_the_url_is_unusable(self):
        assert str(backup.default_output_path(SimpleNamespace(url=None), NOW)).startswith("twingate-backup-unknown-")


NEW_FILES = {
    "devices": "devices.json", "service_accounts": "service-accounts.json", "security_policies": "security-policies.json",
    "dns_profiles": "dns-profiles.json", "gateways": "gateways.json", "certificate_authorities": "certificate-authorities.json",
}


class TestNewTypes:
    def test_each_new_type_has_its_own_file(self):
        assert {e.key: e.file for e in q.ENTITIES if e.key in NEW_FILES} == NEW_FILES

    def test_every_new_type_is_collected_and_written(self, tmp_path):
        collected = backup.collect(tenant_with_long_lists(3))
        assert collected.problems == []
        result = backup.write_backup(collected, tmp_path / "out", session="s", tenant="t", now=NOW)
        for key, file in NEW_FILES.items():
            assert len(json.loads((result.path / file).read_text())) == 1, key

    @pytest.mark.parametrize(
        "typename,label", [("X509CertificateAuthority", "x509"), ("SSHCertificateAuthority", "ssh"), ("FutureCA", "FutureCA")]
    )
    def test_certificate_authorities_say_what_kind_they_are(self, typename, label):
        tenant = FakeTenant({"certificate_authorities": [{"id": "c", "name": "C", "__typename": typename}]})
        authority = backup.collect(tenant).items["certificate_authorities"][0]
        assert authority["type"] == label and "__typename" not in authority

    def test_dns_profiles_come_from_a_plain_list_and_still_get_all_their_groups(self):
        tenant = tenant_with_long_lists(5)
        collected = backup.collect(tenant)
        (profile,) = collected.items["dns_profiles"]
        assert len(profile["groups"]) == 5 and collected.problems == []
        listing = [query for query, _ in tenant.calls if "dnsFilteringProfiles" in query]
        assert len(listing) == 1 and "$cursor" not in listing[0]
        assert any("dnsFilteringProfile(id: $id) { id name priority fallbackMethod" in query for query, _ in tenant.calls)

    def test_a_dns_profile_deleted_between_the_list_and_its_read_is_a_problem_not_a_crash(self):
        tenant = tenant_with_long_lists(3)
        tenant.vanished.add("dp1")
        collected = backup.collect(tenant)
        assert collected.items["dns_profiles"] == []
        assert collected.problems == ["DNS profiles dp1: disappeared while it was being read"]

    def test_dns_profile_group_count_mismatch_is_reported(self):
        tenant = tenant_with_long_lists(5)
        tenant.nested_total_override[("dns_profiles", "groups")] = 9
        assert backup.collect(tenant).problems == ["DNS profiles dp1 groups: API reports 9, backed up 5"]

    ESSENTIAL = {
        "devices": "id name isTrusted activeState deviceType osName osVersion hardwareModel manufacturerName hostname username "
                   "serialNumber clientVersion internetSecurityConfiguration lastSuccessfulLoginAt lastFailedLoginAt user { id email }",
        "service_accounts": "id name createdAt updatedAt",
        "security_policies": "id name policyType createdAt updatedAt",
        "dns_profiles": "id name priority fallbackMethod allowedDomains deniedDomains contentCategoryConfig securityCategoryConfig "
                        "privacyCategoryConfig blockGambling enableSafeSearch enableGoogleSafeBrowsing blockAdsAndTrackers",
        "gateways": "id address remoteNetwork { id name } x509CA sshCA fingerprint",
        "certificate_authorities": "__typename ... on X509CertificateAuthority ... on SSHCertificateAuthority id name fingerprint",
    }

    @pytest.mark.parametrize("key,words", ESSENTIAL.items())
    def test_every_field_worth_restoring_is_selected(self, key, words):
        selected = set(q.SELECTIONS[key].replace("{", " ").replace("}", " ").split())
        for word in words.replace("{", " ").replace("}", " ").split():
            assert word in selected, f"{key} does not select {word}"

    @pytest.mark.parametrize("key", ["devices", "service_accounts", "security_policies", "dns_profiles", "gateways", "certificate_authorities"])
    def test_the_list_query_for_a_connection_follows_cursors_and_asks_for_the_total(self, key):
        entity = next(e for e in q.ENTITIES if e.key == key)
        query = q.LIST_QUERIES[key]
        if entity.paged:
            assert "after: $cursor" in query and "totalCount" in query and "hasNextPage endCursor" in query
        else:
            assert "$cursor" not in query and key in q.DETAIL_QUERIES

    @pytest.mark.parametrize("key,fields", [
        ("service_accounts", ("resources", "keys")), ("security_policies", ("groups",)), ("dns_profiles", ("groups",)),
    ])
    def test_each_nested_list_is_selected_with_its_total_and_page_info(self, key, fields):
        selection = " ".join(q.SELECTIONS[key].split())
        for field in fields:
            assert f"{field} {{ totalCount pageInfo {{ hasNextPage endCursor }} edges {{" in selection

    @pytest.mark.parametrize("key,field,words", [
        ("service_accounts", "keys", "id name status createdAt updatedAt expiresAt revokedAt"),
        ("service_accounts", "resources", "id name"),
        ("security_policies", "groups", "id name"),
        ("dns_profiles", "groups", "id name"),
    ])
    def test_nested_lists_carry_what_is_needed_to_restore_them(self, key, field, words):
        for part in words.split():
            assert part in q.NESTED_EDGES[(key, field)]

    def test_continuation_queries_exist_for_every_new_nested_list(self):
        for key, field in [("service_accounts", "resources"), ("service_accounts", "keys"), ("security_policies", "groups"), ("dns_profiles", "groups")]:
            parent = {"service_accounts": "serviceAccount", "security_policies": "securityPolicy", "dns_profiles": "dnsFilteringProfile"}[key]
            assert f"{parent}(id: $id)" in q.CONTINUATION_QUERIES[(key, field)]

    def test_service_account_keys_are_metadata_only(self):
        keys = q.SELECTIONS["service_accounts"]
        assert "token" not in keys.lower() and "secret" not in keys.lower()
        assert "status" in q.NESTED_EDGES[("service_accounts", "keys")]

    def test_no_query_asks_for_a_deprecated_or_secret_field(self):
        everything = " ".join(q.LIST_QUERIES.values()) + " ".join(q.CONTINUATION_QUERIES.values())
        for word in ("lastConnectedAt", "usageBasedAutolockDurationDays", "token", "Token"):
            assert word not in everything

    @staticmethod
    def failing_on(tenant, marker, error):
        """Make every request whose text contains ``marker`` raise ``error``."""
        real = tenant.execute

        def execute(query, variables=None):
            if marker in query:
                raise error
            return real(query, variables)

        tenant.execute = execute
        return tenant

    LISTS = {
        "devices": "query($cursor: String) { devices(", "service_accounts": "query($cursor: String) { serviceAccounts(",
        "security_policies": "query($cursor: String) { securityPolicies(", "dns_profiles": "query { dnsFilteringProfiles",
        "gateways": "query($cursor: String) { gateways(", "certificate_authorities": "query($cursor: String) { certificateAuthorities(",
    }

    @pytest.mark.parametrize("key", LISTS)
    def test_a_type_the_api_refuses_is_left_out_and_everything_else_is_still_backed_up(self, tmp_path, key):
        tenant = self.failing_on(tenant_with_long_lists(3), self.LISTS[key], TwingateAPIError("not available on this plan"))
        collected = backup.collect(tenant)
        label = next(e.label for e in q.ENTITIES if e.key == key)
        assert key in collected.unreadable and key not in collected.items
        assert all(collected.items[e.key] for e in q.ENTITIES if e.key != key), "the other types must all be read"
        assert collected.problems == [f"{label}: could not be read, so they are not in this backup (not available on this plan)"]
        result = backup.write_backup(collected, tmp_path / "out", session="s", tenant="t", now=NOW)
        file = next(e.file for e in q.ENTITIES if e.key == key)
        assert not (result.path / file).exists() and key not in result.counts
        manifest = json.loads((result.path / backup.MANIFEST_FILE).read_text())
        assert file not in manifest["files"] and manifest["verification"]["complete"] is False

    def test_the_original_five_types_still_fail_the_whole_backup(self):
        tenant = FakeTenant({"users": many("u", 1)})
        tenant.error = TwingateAPIError("boom")
        with pytest.raises(TwingateAPIError):
            backup.collect(tenant)

    @pytest.mark.parametrize("key", LISTS)
    def test_being_rate_limited_is_not_mistaken_for_an_unreadable_type(self, key):
        tenant = self.failing_on(tenant_with_long_lists(3), self.LISTS[key], TwingateThrottleError("slow down"))
        with pytest.raises(TwingateThrottleError):
            backup.collect(tenant)

    @pytest.mark.parametrize("key", LISTS)
    def test_a_failed_login_stops_the_backup_even_on_a_new_type(self, key):
        tenant = self.failing_on(tenant_with_long_lists(3), self.LISTS[key], TwingateAuthError("bad token"))
        with pytest.raises(TwingateAuthError):
            backup.collect(tenant)

    def test_manifest_notes_no_longer_claim_devices_are_missing(self, tmp_path):
        manifest = json.loads(
            (backup.write_backup(collected_sample(), tmp_path / "o", session="s", tenant="t", now=NOW).path / backup.MANIFEST_FILE).read_text()
        )
        text = " ".join(manifest["notes"])
        assert "Not included: devices" not in text and "allowlist" in text
