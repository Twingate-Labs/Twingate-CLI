"""Device trust by serial number: loading, planning, applying. Only devices that have already registered can be changed."""

from __future__ import annotations

import json

import pytest

from tests.importer.fake_api import FakeApi
from tgcli.client.exceptions import TwingateAPIError
from tgcli.importer.apply import apply_plan, write_count
from tgcli.importer.load import DeviceSpec, LoadError, Specs, load, load_file
from tgcli.importer.plan import BLOCKED, EXISTS, SKIP, UPDATE, build_plan
from tgcli.importer.state import fetch_state


def dev(serial, trusted=True, state="ACTIVE", user="ann@x.com", id=None):
    return {"id": id or f"D-{serial}-{user}-{state}", "serialNumber": serial, "isTrusted": trusted, "activeState": state, "user": {"email": user}}


def spec(serial, trusted=True, source=None):
    return DeviceSpec(source=source or f"d:{serial}", serial=serial, trusted=trusted)


def run(api, *specs, execute=False):
    s = Specs(devices=list(specs))
    rows = build_plan(s, fetch_state(api, s))
    if execute:
        api.requests.clear()
        apply_plan(api, rows)
    return rows


class TestLoad:
    def test_csv(self, tmp_path):
        f = tmp_path / "devices.csv"
        f.write_text("serial_number,trusted\nABC123,false\nDEF456,\nGHI789,yes\n", encoding="utf-8")
        assert [(d.serial, d.trusted, d.problems) for d in load_file(f, "devices")] == [("ABC123", False, []), ("DEF456", True, []), ("GHI789", True, [])]

    def test_the_trusted_column_is_optional_and_means_trusted(self, tmp_path):
        f = tmp_path / "devices.csv"
        f.write_text("serial_number\nABC123\n", encoding="utf-8")
        assert [(d.serial, d.trusted) for d in load_file(f, "devices")] == [("ABC123", True)]

    def test_json_uses_the_apis_field_names(self, tmp_path):
        f = tmp_path / "devices.json"
        f.write_text(json.dumps([{"serialNumber": " ABC123 ", "isTrusted": False}, {"serial_number": "DEF456", "trusted": "no"}]), encoding="utf-8")
        assert [(d.serial, d.trusted) for d in load_file(f, "devices")] == [("ABC123", False), ("DEF456", False)]

    @pytest.mark.parametrize("text,problem", [
        ("serial_number,trusted\n,true\n", "has no serial number"),
        ("serial_number,trusted\nABC,maybe\n", "trusted 'maybe' is not true or false"),
    ])
    def test_bad_rows_are_kept_with_their_problem(self, tmp_path, text, problem):
        f = tmp_path / "devices.csv"
        f.write_text(text, encoding="utf-8")
        (d,) = load_file(f, "devices")
        assert any(problem in p for p in d.problems)

    def test_a_row_without_a_serial_is_labelled_clearly(self):
        assert spec("").name == "(no serial number)"

    def test_unknown_and_missing_columns_stop_the_load(self, tmp_path):
        f = tmp_path / "devices.csv"
        f.write_text("serial,trusted\nA,true\n", encoding="utf-8")
        with pytest.raises(LoadError, match="column.*serial.*Columns for devices"):
            load_file(f, "devices")

    def test_a_folder_picks_up_devices_alongside_the_rest(self, tmp_path):
        (tmp_path / "devices.csv").write_text("serial_number\nA\n", encoding="utf-8")
        (tmp_path / "groups.json").write_text("[]", encoding="utf-8")
        specs = load(tmp_path)
        assert [d.serial for d in specs.devices] == ["A"] and specs.files == ["groups.json", "devices.csv"]


class TestState:
    def test_serials_are_asked_for_as_written_upper_and_lower_case_and_matched_ignoring_case(self):
        api = FakeApi(devices=[dev("ABC123")])
        state = fetch_state(api, Specs(devices=[spec("abc123")]))
        asked = next(v["names"] for q, v in api.lookups if "devices(" in q)
        assert asked == ["ABC123", "abc123"] and list(state.devices) == ["abc123"]

    def test_no_devices_in_the_file_means_no_device_lookup(self):
        api = FakeApi(devices=[dev("A")])
        fetch_state(api, Specs())
        assert api.requests == []


class TestPlan:
    def test_an_untrusted_device_is_trusted(self):
        (row,) = run(FakeApi(devices=[dev("ABC", trusted=False)]), spec("ABC"))
        assert (row.action, row.detail) == (UPDATE, "make 1 device trusted") and len(row.device_ids) == 1

    def test_a_trusted_device_is_untrusted(self):
        (row,) = run(FakeApi(devices=[dev("ABC", trusted=True)]), spec("ABC", trusted=False))
        assert (row.action, row.detail) == (UPDATE, "make 1 device untrusted")

    def test_a_device_already_in_the_state_asked_for_is_left_alone(self):
        (row,) = run(FakeApi(devices=[dev("ABC", trusted=True)]), spec("ABC"))
        assert row.action == EXISTS and row.device_ids == [] and "already trusted" in row.detail

    def test_the_serial_is_matched_ignoring_case(self):
        (row,) = run(FakeApi(devices=[dev("ABC", trusted=False)]), spec("abc"))
        assert row.action == UPDATE

    def test_a_serial_nobody_has_registered_yet_is_skipped_with_the_way_to_pre_trust_it(self):
        (row,) = run(FakeApi(), spec("NEW"))
        assert row.action == SKIP and "no device with this serial number has registered" in row.detail and "tgcli device snumber add" in row.detail

    def test_archived_devices_are_never_changed(self):
        (row,) = run(FakeApi(devices=[dev("ABC", trusted=False, state="ARCHIVED")]), spec("ABC"))
        assert row.action == SKIP and "only archived devices" in row.detail

    def test_archived_registrations_are_ignored_next_to_a_live_one(self):
        api = FakeApi(devices=[dev("ABC", trusted=False, state="ARCHIVED"), dev("ABC", trusted=False)])
        (row,) = run(api, spec("ABC"))
        assert row.action == UPDATE and len(row.device_ids) == 1 and row.detail.endswith("; 1 archived device ignored")

    def test_blocked_devices_are_changed_like_active_ones(self):
        (row,) = run(FakeApi(devices=[dev("ABC", trusted=False, state="BLOCKED")]), spec("ABC"))
        assert row.action == UPDATE

    def test_trusting_a_serial_shared_by_several_users_is_blocked(self):
        api = FakeApi(devices=[dev("0", trusted=False, user="ann@x.com"), dev("0", trusted=False, user="bob@x.com")])
        (row,) = run(api, spec("0"))
        assert row.action == BLOCKED and "2 devices belonging to 2 different users" in row.detail and "updateTrust -i" in row.detail

    def test_untrusting_a_shared_serial_is_allowed_because_that_only_narrows_access(self):
        api = FakeApi(devices=[dev("0", user="ann@x.com"), dev("0", user="bob@x.com")])
        (row,) = run(api, spec("0", trusted=False))
        assert row.action == UPDATE and len(row.device_ids) == 2

    def test_one_users_devices_with_the_same_serial_are_all_changed(self):
        api = FakeApi(devices=[dev("ABC", trusted=False, id="D1"), dev("ABC", trusted=False, id="D2"), dev("ABC", trusted=True, id="D3")])
        (row,) = run(api, spec("ABC"))
        assert row.action == UPDATE and row.device_ids == ["D1", "D2"]

    def test_a_serial_twice_blocks_the_second_even_in_another_case(self):
        rows = run(FakeApi(devices=[dev("ABC", trusted=False)]), spec("ABC"), spec("abc", trusted=False))
        assert [r.action for r in rows] == [UPDATE, BLOCKED] and "same serial number as d:ABC" in rows[1].detail

    def test_a_row_with_problems_is_blocked(self):
        bad = spec("")
        bad.problems = ["has no serial number"]
        (row,) = run(FakeApi(), bad)
        assert row.action == BLOCKED and row.name == "(no serial number)"


class TestApply:
    def test_every_matching_device_is_changed_and_nothing_else(self):
        api = FakeApi(devices=[dev("ABC", trusted=False, id="D1"), dev("ABC", trusted=False, id="D2"), dev("OTHER", trusted=False, id="D3")])
        (row,) = run(api, spec("ABC"), execute=True)
        assert row.status == "updated" and row.id == "D1, D2" and not row.error
        assert [(n, v) for n, v in api.writes] == [("importDeviceTrust", {"id": "D1", "isTrusted": True}), ("importDeviceTrust", {"id": "D2", "isTrusted": True})]
        assert {d["id"]: d["isTrusted"] for d in api.devices} == {"D1": True, "D2": True, "D3": False}

    def test_untrusting(self):
        api = FakeApi(devices=[dev("ABC", trusted=True, id="D1")])
        run(api, spec("ABC", trusted=False), execute=True)
        assert api.devices[0]["isTrusted"] is False

    def test_running_it_again_finds_nothing_to_do(self):
        api = FakeApi(devices=[dev("ABC", trusted=False)])
        run(api, spec("ABC"), execute=True)
        (again,) = run(api, spec("ABC"), execute=True)
        assert again.status == "exists" and api.writes == []

    def test_a_change_the_api_accepts_but_does_not_apply_is_an_error(self):
        api = FakeApi(devices=[dev("ABC", trusted=False, id="D1")])
        api.ignore_trust = True
        (row,) = run(api, spec("ABC"), execute=True)
        assert row.status == "error" and "still untrusted" in row.error and "changed 0 of 1 devices" in row.error

    def test_the_other_direction_is_checked_too(self):
        api = FakeApi(devices=[dev("ABC", trusted=True, id="D1")])
        api.ignore_trust = True
        (row,) = run(api, spec("ABC", trusted=False), execute=True)
        assert row.status == "error" and "still trusted" in row.error

    def test_a_failure_part_way_says_how_far_it_got(self):
        api = FakeApi(devices=[dev("ABC", trusted=False, id="D1"), dev("ABC", trusted=False, id="D2")])
        api.fail["importDeviceTrust"] = lambda v: "nope" if v["id"] == "D2" else None
        (row,) = run(api, spec("ABC"), execute=True)
        assert row.status == "error" and row.error.startswith("changed 1 of 2 devices, then: nope") and "Run the import again" in row.error
        api.fail.clear()
        (again,) = run(api, spec("ABC"), execute=True)
        assert again.status == "updated" and api.devices[1]["isTrusted"] is True

    def test_an_api_error_is_recorded_not_raised(self):
        api = FakeApi(devices=[dev("ABC", trusted=False)])
        api.raise_on["importDeviceTrust"] = TwingateAPIError("HTTP 500")
        (row,) = run(api, spec("ABC"), execute=True)
        assert row.status == "error" and "HTTP 500" in row.error

    def test_rows_with_nothing_to_do_send_nothing(self):
        api = FakeApi(devices=[dev("ABC", trusted=True, state="ARCHIVED")])
        rows = run(api, spec("ABC"), spec("NEW"), execute=True)
        assert api.writes == [] and [r.status for r in rows] == ["skipped", "skipped"]

    def test_the_write_count_is_one_per_device(self):
        api = FakeApi(devices=[dev("A", trusted=False, id="D1"), dev("A", trusted=False, id="D2"), dev("B", trusted=False, id="D3")])
        rows = run(api, spec("A"), spec("B"))
        assert write_count(rows) == 3
        apply_plan(api, rows)
        assert len(api.writes) == 3
