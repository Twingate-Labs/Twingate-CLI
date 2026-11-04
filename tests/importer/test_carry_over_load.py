"""Reading service accounts, certificate authorities, Gateways, DNS profiles and approver groups, and the certificate files a CA is made from."""

from __future__ import annotations

import csv
import json

import pytest

from tests.importer.ca_material import pem, ssh_fingerprint, ssh_key, x509_fingerprint
from tgcli.importer.cafiles import normalize, read_ca_files, read_one
from tgcli.importer.load import CSV_COLUMNS, LoadError, load, load_file


def dump(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def csv_file(path, header, *rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


class TestServiceAccounts:
    def test_a_backup_record_gives_its_name_and_how_many_keys_it_lists(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "service-accounts.json", [{"id": "1", "name": "ci", "keys": [{"id": "k1"}, {"id": "k2"}], "resources": []}]), "service-accounts")
        assert (spec.name, spec.keys, spec.problems) == ("ci", 2, [])

    def test_a_record_without_a_name_is_kept_as_a_problem(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "service-accounts.json", [{"id": "1"}]), "service-accounts")
        assert spec.problems == ["has no name"]

    def test_a_csv_is_one_name_per_row(self, tmp_path):
        specs = load_file(csv_file(tmp_path / "service-accounts.csv", ["name"], ["ci"], ["deploy"]), "service-accounts")
        assert [s.name for s in specs] == ["ci", "deploy"] and specs[0].source == "service-accounts.csv row 2"


class TestCertificateAuthorities:
    def test_a_backup_record_gives_name_type_and_fingerprint(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "certificate-authorities.json", [{"id": "1", "name": "Root", "type": "x509", "fingerprint": "ab:cd"}]), "certificate-authorities")
        assert (spec.name, spec.type, spec.fingerprint, spec.problems) == ("Root", "x509", "ab:cd", [])

    def test_a_type_that_is_neither_x509_nor_ssh_is_a_problem(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "certificate-authorities.json", [{"name": "Root", "type": "pgp"}]), "certificate-authorities")
        assert spec.problems == ["type 'pgp' is not x509 or ssh"]

    def test_a_ca_cannot_be_a_csv(self, tmp_path):
        with pytest.raises(LoadError, match="must be a .json file"):
            load_file(csv_file(tmp_path / "certificate-authorities.csv", ["name"]), "certificate-authorities")


class TestGateways:
    RECORD = {"id": "1", "address": "gw.example.com", "remoteNetwork": {"id": "N", "name": "HQ"},
              "x509CA": {"id": "C1", "name": "Root", "fingerprint": "aa"}, "sshCA": {"id": "C2", "name": "Shell", "fingerprint": "bb"}}

    def test_a_backup_record_keeps_both_certificate_authority_references(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "gateways.json", [self.RECORD]), "gateways")
        assert (spec.address, spec.network, spec.name) == ("gw.example.com", "HQ", "gw.example.com") and spec.problems == []
        assert spec.x509_ca == {"name": "Root", "fingerprint": "aa"} and spec.ssh_ca == {"name": "Shell", "fingerprint": "bb"}

    def test_the_ssh_authority_is_optional_but_the_x509_one_is_not(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "gateways.json", [{**self.RECORD, "sshCA": None}]), "gateways")
        assert spec.ssh_ca == {} and spec.problems == []
        (spec,) = load_file(dump(tmp_path / "gateways.json", [{**self.RECORD, "x509CA": None}]), "gateways")
        assert any("X.509 certificate authority" in p for p in spec.problems)

    @pytest.mark.parametrize("missing, message", [("address", "has no address"), ("remoteNetwork", "has no Remote Network")])
    def test_what_a_gateway_cannot_do_without_is_a_problem(self, tmp_path, missing, message):
        (spec,) = load_file(dump(tmp_path / "gateways.json", [{**self.RECORD, missing: None}]), "gateways")
        assert message in spec.problems

    def test_a_csv_names_the_authorities(self, tmp_path):
        (spec,) = load_file(csv_file(tmp_path / "gateways.csv", CSV_COLUMNS["gateways"], ["gw.example.com", "HQ", "Root", ""]), "gateways")
        assert spec.problems == [] and spec.x509_ca == {"name": "Root", "fingerprint": ""} and spec.ssh_ca == {}


class TestDnsProfiles:
    RECORD = {
        "id": "1", "name": "Kids", "priority": 3, "fallbackMethod": "AUTO", "allowedDomains": ["a.com", "a.com", " b.com "], "deniedDomains": [],
        "contentCategoryConfig": {"blockGambling": True, "extra": "ignored"}, "securityCategoryConfig": None,
        "privacyCategoryConfig": {"blockAdsAndTrackers": False}, "groups": [{"id": "G1", "name": "Eng"}, {"id": "G1", "name": "Eng"}, {"id": "G2", "name": "Ops"}],
    }

    def test_a_backup_record_keeps_what_it_states(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "dns-profiles.json", [self.RECORD]), "dns-profiles")
        assert spec.problems == [] and (spec.name, spec.priority, spec.fallback_method) == ("Kids", 3.0, "AUTO")
        assert spec.allowed_domains == ["a.com", "b.com"] and spec.denied_domains == []
        assert spec.categories == {"contentCategoryConfig": {"blockGambling": True}, "privacyCategoryConfig": {"blockAdsAndTrackers": False}}
        assert spec.groups == ["Eng", "Ops"]

    @pytest.mark.parametrize("change, message", [
        ({"name": ""}, "has no name"), ({"priority": "high"}, "priority 'high' is not a number"), ({"priority": True}, "priority 'True' is not a number"),
        ({"allowedDomains": "a.com"}, "allowedDomains must be a list of domain names"), ({"deniedDomains": [1]}, "deniedDomains must be a list of domain names"),
    ])
    def test_a_value_that_cannot_be_used_is_a_problem(self, tmp_path, change, message):
        (spec,) = load_file(dump(tmp_path / "dns-profiles.json", [{**self.RECORD, **change}]), "dns-profiles")
        assert message in spec.problems

    def test_a_profile_that_states_nothing_but_its_name_has_no_settings(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "dns-profiles.json", [{"name": "Plain"}]), "dns-profiles")
        assert (spec.priority, spec.fallback_method, spec.allowed_domains, spec.denied_domains, spec.categories, spec.groups) == (None, None, None, None, {}, [])


class TestApproverGroups:
    def record(self, **extra):
        return {"type": "NETWORK", "name": "Wiki", "remoteNetwork": {"name": "HQ"}, "address": {"value": "wiki.internal"}, **extra}

    def test_names_come_from_a_backups_approver_groups_without_repeats(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "resources.json", [self.record(approverGroups=[{"id": "1", "name": "A"}, {"id": "2", "name": "B"}, {"id": "3", "name": "A"}])]), "resources")
        assert spec.approver_groups == ["A", "B"] and "approvers" in spec.given and spec.notes == []

    def test_an_empty_list_states_that_nobody_approves_and_a_missing_one_states_nothing(self, tmp_path):
        (empty, absent) = load_file(dump(tmp_path / "resources.json", [self.record(approverGroups=[]), self.record(name="Other")]), "resources")
        assert "approvers" in empty.given and "approvers" not in absent.given

    def test_an_approver_without_a_name_is_a_problem(self, tmp_path):
        (spec,) = load_file(dump(tmp_path / "resources.json", [self.record(approverGroups=[{"id": "1"}])]), "resources")
        assert "an approver group has no name" in spec.problems

    def test_a_csv_cell_lists_them_and_a_blank_one_states_nothing(self, tmp_path):
        header = ["name", "network", "address", "approver_groups"]
        (one, two) = load_file(csv_file(tmp_path / "resources.csv", header, ["Wiki", "HQ", "w.internal", "A;B;A"], ["Other", "HQ", "o.internal", ""]), "resources")
        assert one.approver_groups == ["A", "B"] and "approvers" in one.given
        assert two.approver_groups == [] and "approvers" not in two.given


class TestFolders:
    def test_a_backup_folder_reads_every_new_file_and_counts_what_it_leaves_out(self, tmp_path):
        dump(tmp_path / "manifest.json", {})
        dump(tmp_path / "service-accounts.json", [{"name": "ci"}])
        dump(tmp_path / "certificate-authorities.json", [{"name": "Root", "type": "x509", "fingerprint": "aa"}])
        dump(tmp_path / "gateways.json", [{"address": "g", "remoteNetwork": {"name": "HQ"}, "x509CA": {"name": "Root"}}])
        dump(tmp_path / "dns-profiles.json", [{"name": "Kids"}])
        dump(tmp_path / "users.json", [{"email": "a@x.com"}, {"email": "b@x.com"}])
        dump(tmp_path / "connectors.json", [])
        dump(tmp_path / "devices.json", [{"serialNumber": "S"}])
        dump(tmp_path / "security-policies.json", [1, 2, 3])
        specs = load(tmp_path)
        assert [len(x) for x in (specs.service_accounts, specs.certificate_authorities, specs.gateways, specs.dns_profiles)] == [1, 1, 1, 1]
        assert specs.counts == {"users.json": 2, "connectors.json": 0, "devices.json": 1, "security-policies.json": 3}

    def test_a_count_that_cannot_be_read_is_none_not_a_crash(self, tmp_path):
        dump(tmp_path / "manifest.json", {})
        dump(tmp_path / "groups.json", [{"name": "Eng"}])
        (tmp_path / "users.json").write_text("{not json", encoding="utf-8")
        assert load(tmp_path).counts == {"users.json": None}

    @pytest.mark.parametrize("content", ['{"a": 1}', "5", "null", '"text"'])
    def test_a_backup_file_that_is_not_a_list_has_no_count_and_does_not_crash(self, tmp_path, content):
        dump(tmp_path / "manifest.json", {})
        dump(tmp_path / "groups.json", [{"name": "Eng"}])
        (tmp_path / "users.json").write_text(content, encoding="utf-8")
        assert load(tmp_path).counts == {"users.json": None}

    def test_a_single_file_is_recognised_by_its_name(self, tmp_path):
        assert load(csv_file(tmp_path / "service-accounts.csv", ["name"], ["ci"])).service_accounts[0].name == "ci"
        assert load(dump(tmp_path / "dns-profiles.json", [{"name": "K"}])).dns_profiles[0].name == "K"

    def test_a_json_only_kind_as_csv_is_refused_with_a_reason(self, tmp_path):
        csv_file(tmp_path / "dns-profiles.csv", ["name"], ["K"])
        with pytest.raises(LoadError, match="dns-profiles.csv must be a .json file"):
            load(tmp_path)

    def test_the_error_for_an_unknown_file_name_says_which_are_json_only(self, tmp_path):
        with pytest.raises(LoadError, match=r"certificate-authorities.json, dns-profiles.json are JSON only"):
            load(dump(tmp_path / "nope.json", []))


class TestFingerprints:
    @pytest.mark.parametrize("written, plain", [
        ("SHA256:ABCDEF", "ABCDEF"), ("sha256:abc+/=", "abc+/"), ("AB:CD:EF:01", "abcdef01"), ("A" * 64, "a" * 64), ("  SHA-1: 0a:0b ", "0a0b"), (None, ""), ("", ""),
    ])
    def test_normalize(self, written, plain):
        assert normalize(written) == plain

    def test_a_certificate_has_the_sha256_hex_of_its_der_bytes(self, tmp_path):
        path = tmp_path / "ca.pem"
        path.write_text(pem("a"))
        found, problem = read_one(path)
        assert problem is None and found.kind == "x509" and normalize(x509_fingerprint("a")) in found.fingerprints
        assert normalize("SHA256:" + x509_fingerprint("a").upper()) in found.fingerprints  # however the tenant writes it

    def test_an_ssh_key_has_the_ssh_keygen_fingerprint(self, tmp_path):
        path = tmp_path / "ca.pub"
        path.write_text(ssh_key("a"))
        found, problem = read_one(path)
        assert problem is None and found.kind == "ssh" and normalize(ssh_fingerprint("a")) in found.fingerprints

    def test_the_comment_on_a_key_does_not_change_its_fingerprint(self, tmp_path):
        one, two = tmp_path / "1.pub", tmp_path / "2.pub"
        one.write_text(ssh_key("a", "first"))
        two.write_text(ssh_key("a", "second"))
        assert read_one(one)[0].fingerprints == read_one(two)[0].fingerprints

    def test_a_different_certificate_has_a_different_fingerprint(self, tmp_path):
        (tmp_path / "a.pem").write_text(pem("a"))
        (tmp_path / "b.pem").write_text(pem("b"))
        files = read_ca_files(tmp_path)
        assert files.match(x509_fingerprint("a"))[0].path.endswith("a.pem") and len(files.match(x509_fingerprint("a"))) == 1
        assert files.match("0" * 64) == [] and files.match(None) == [] and files.match("") == []

    def test_a_match_can_be_limited_to_the_kind(self, tmp_path):
        (tmp_path / "a.pem").write_text(pem("a"))
        files = read_ca_files(tmp_path)
        assert files.match(x509_fingerprint("a"), "x509") and files.match(x509_fingerprint("a"), "ssh") == []


class TestReadingFiles:
    def test_a_private_key_is_refused_and_never_kept(self, tmp_path):
        (tmp_path / "ca.key").write_text("-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n" + pem("a"))
        files = read_ca_files(tmp_path)
        assert files.files == [] and len(files.problems) == 1 and "holds a private key" in files.problems[0]

    def test_a_certificate_bundle_with_a_private_key_is_refused_too(self, tmp_path):
        path = tmp_path / "bundle.pem"
        path.write_text(pem("a") + "-----BEGIN RSA PRIVATE KEY-----\nAAAA\n-----END RSA PRIVATE KEY-----\n")
        assert read_one(path)[0] is None and "private key" in read_one(path)[1]

    def test_other_files_in_a_folder_are_not_worth_a_line_but_a_named_file_that_is_no_use_is(self, tmp_path):
        (tmp_path / "notes.txt").write_text("hello")
        (tmp_path / ".hidden").write_text(pem("a"))
        assert read_ca_files(tmp_path).files == [] and read_ca_files(tmp_path).problems == []
        assert "is neither a PEM certificate nor an SSH public key" in read_ca_files(tmp_path / "notes.txt").problems[0]

    def test_a_file_that_is_too_big_or_not_valid_base64_is_not_used(self, tmp_path):
        big = tmp_path / "big.pem"
        big.write_text("x" * (300 * 1024))
        assert "too big" in read_one(big)[1]
        bad = tmp_path / "bad.pem"
        bad.write_text("-----BEGIN CERTIFICATE-----\n!!!not base64!!!\n-----END CERTIFICATE-----\n")
        assert "not valid PEM" in read_one(bad)[1]
        badkey = tmp_path / "bad.pub"
        badkey.write_text("ssh-ed25519 !!!!\n")
        assert read_one(badkey)[0] is None

    def test_a_certificate_with_stray_characters_inside_is_not_decoded_by_ignoring_them(self, tmp_path):
        path = tmp_path / "odd.pem"
        path.write_text("-----BEGIN CERTIFICATE-----\nQUJD!REVG\n-----END CERTIFICATE-----\n")
        found, problem = read_one(path)
        assert found is None and "not valid PEM" in problem

    def test_an_unreadable_file_is_reported(self, tmp_path):
        assert "cannot be read" in read_one(tmp_path / "missing.pem")[1]

    def test_a_folder_is_read_in_name_order(self, tmp_path):
        (tmp_path / "b.pem").write_text(pem("b"))
        (tmp_path / "a.pem").write_text(pem("a"))
        assert [f.path.rsplit("/", 1)[1] for f in read_ca_files(tmp_path).files] == ["a.pem", "b.pem"]

    def test_the_content_sent_is_the_file_text_without_surrounding_blank_space(self, tmp_path):
        (tmp_path / "ca.pem").write_text("\n\n" + pem("a") + "\n\n")
        assert read_ca_files(tmp_path).files[0].content == pem("a").strip()
