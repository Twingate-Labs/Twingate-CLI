"""Tests for device commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError, TwingateAuthError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"
TOKEN = "tok-test"


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", TOKEN)


def _make_list_response(edges):
    return {
        "data": {
            "devices": {
                "edges": edges,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }


def _make_mutation_response(mutation_key, entity=None):
    return {
        "data": {
            mutation_key: {
                "ok": True,
                "error": None,
                "entity": entity or {"id": "dev-1", "name": "Test Device", "isTrusted": True, "activeState": "ACTIVE"},
            }
        }
    }


class TestDeviceList:
    def test_list_exits_zero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.paginate.return_value = [
                [{"node": {"id": "dev-1", "name": "Laptop", "isTrusted": True, "osName": "macOS", "deviceType": "LAPTOP", "activeState": "ACTIVE", "lastFailedLoginAt": None, "lastSuccessfulLoginAt": None, "lastConnectedAt": None, "osVersion": "14.0", "hardwareModel": "MBP", "hostname": "host", "username": "u", "serialNumber": "SN1", "user": {"firstName": "A", "lastName": "B", "email": "a@b.com"}, "clientVersion": "1.0", "manufacturerName": "Apple", "internetSecurityConfiguration": "MACHINE_KEY"}}]
            ]
            result = runner.invoke(app, ["-s", SESSION, "device", "list"])
        assert result.exit_code == 0

    def test_list_no_session_exits_nonzero(self, mock_keyring):
        result = runner.invoke(app, ["device", "list"])
        assert result.exit_code != 0

    def test_list_auth_error_exits_nonzero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.paginate.side_effect = TwingateAuthError("Bad token")
            result = runner.invoke(app, ["-s", SESSION, "device", "list"])
        assert result.exit_code != 0

    def test_list_csv_format(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.paginate.return_value = [
                [{"node": {"id": "dev-1", "name": "Laptop", "isTrusted": True, "osName": "macOS", "deviceType": "LAPTOP", "activeState": "ACTIVE", "lastFailedLoginAt": None, "lastSuccessfulLoginAt": None, "lastConnectedAt": None, "osVersion": "14.0", "hardwareModel": "MBP", "hostname": "host", "username": "u", "serialNumber": "SN1", "user": {"firstName": "A", "lastName": "B", "email": "a@b.com"}, "clientVersion": "1.0", "manufacturerName": "Apple", "internetSecurityConfiguration": "MACHINE_KEY"}}]
            ]
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "device", "list"])
        assert result.exit_code == 0


def _edge(device_id):
    return {"node": {"id": device_id, "name": device_id, "isTrusted": True, "osName": "macOS", "deviceType": "LAPTOP", "activeState": "ACTIVE", "lastFailedLoginAt": None, "lastSuccessfulLoginAt": None, "lastConnectedAt": None, "osVersion": "14.0", "hardwareModel": "MBP", "hostname": "host", "username": "u", "serialNumber": "SN1", "user": {"firstName": "A", "lastName": "B", "email": "a@b.com"}, "clientVersion": "1.0", "manufacturerName": "Apple", "internetSecurityConfiguration": "NONE"}}


def _sent_variables(mock_instance):
    """Variables the CLI sent for the first page of the paginated query."""
    _query, make_vars, _key = mock_instance.paginate.call_args.args
    return make_vars("0")


class TestDeviceListFilters:
    def _invoke(self, args, pages=None):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.paginate.return_value = pages if pages is not None else [[_edge("dev-1")]]
            result = runner.invoke(app, ["-s", SESSION, *args])
        return result, mock_instance

    def test_no_filter_sends_no_filter_variable(self):
        result, inst = self._invoke(["device", "list"])
        assert result.exit_code == 0
        assert "filter" not in _sent_variables(inst)

    def test_trusted(self):
        result, inst = self._invoke(["device", "list", "--trusted"])
        assert result.exit_code == 0
        assert _sent_variables(inst)["filter"] == {"isTrusted": {"eq": True}}

    def test_untrusted(self):
        _, inst = self._invoke(["device", "list", "--untrusted"])
        assert _sent_variables(inst)["filter"] == {"isTrusted": {"eq": False}}

    def test_state_is_case_insensitive_and_repeatable(self):
        _, inst = self._invoke(["device", "list", "--state", "active", "--state", "BLOCKED"])
        assert _sent_variables(inst)["filter"] == {"activeState": {"in": ["ACTIVE", "BLOCKED"]}}

    def test_invalid_state_rejected_before_any_api_call(self):
        result, inst = self._invoke(["device", "list", "--state", "NOPE"])
        assert result.exit_code != 0
        inst.paginate.assert_not_called()

    def test_serial_number_and_user_id(self):
        _, inst = self._invoke(["device", "list", "--serial-number", "SN9", "--user-id", "u1", "--user-id", "u2"])
        assert _sent_variables(inst)["filter"] == {"serialNumber": {"eq": "SN9"}, "userId": {"in": ["u1", "u2"]}}

    def test_filters_combine(self):
        _, inst = self._invoke(["device", "list", "--trusted", "--state", "ACTIVE"])
        assert _sent_variables(inst)["filter"] == {"isTrusted": {"eq": True}, "activeState": {"in": ["ACTIVE"]}}


class TestDeviceListIds:
    def _invoke(self, args, pages):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = pages
            return runner.invoke(app, ["-s", SESSION, *args])

    def test_idsonly_json_spans_pages(self):
        result = self._invoke(["device", "list", "-i"], [[_edge("a")], [_edge("b")]])
        assert result.exit_code == 0
        assert json.loads(result.output) == ["a", "b"]

    def test_idsonly_csv(self):
        result = self._invoke(["-f", "csv", "device", "list", "-i"], [[_edge("a"), _edge("b")]])
        assert result.output.split() == ["id", "a", "b"]

    def test_idsonly_respects_filter(self):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.paginate.return_value = [[_edge("a")]]
            runner.invoke(app, ["-s", SESSION, "device", "list", "-i", "--untrusted"])
            assert _sent_variables(MockClient.return_value)["filter"] == {"isTrusted": {"eq": False}}

    @pytest.mark.parametrize("content", ["a\nb\n", "a,b", "['a', 'b']", "a, b\n"])
    def test_fileofids_accepts_common_file_layouts(self, tmp_path, content):
        f = tmp_path / "ids.txt"
        f.write_text(content)
        result = self._invoke(["device", "list", "-l", str(f)], [[_edge("a"), _edge("b")]])
        assert result.exit_code == 0
        assert json.loads(result.output) == {"new": [], "missing": []}

    def test_fileofids_reports_new_and_missing(self, tmp_path):
        f = tmp_path / "ids.txt"
        f.write_text("b\nghost\n")
        result = self._invoke(["device", "list", "-l", str(f)], [[_edge("a"), _edge("b")]])
        assert json.loads(result.output) == {"new": ["a"], "missing": ["ghost"]}

    def test_fileofids_csv(self, tmp_path):
        f = tmp_path / "ids.txt"
        f.write_text("ghost")
        result = self._invoke(["-f", "csv", "device", "list", "-l", str(f)], [[_edge("a")]])
        assert result.output.split() == ["id,status", "a,new", "ghost,missing"]

    def test_fileofids_missing_file_exits_nonzero(self, tmp_path):
        result = self._invoke(["device", "list", "-l", str(tmp_path / "nope.txt")], [[_edge("a")]])
        assert result.exit_code != 0

    def test_fileofids_and_idsonly_are_exclusive(self, tmp_path):
        f = tmp_path / "ids.txt"
        f.write_text("a")
        result = self._invoke(["device", "list", "-l", str(f), "-i"], [[_edge("a")]])
        assert result.exit_code != 0


class TestDeviceShow:
    def test_show_exits_zero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.execute.return_value = {
                "data": {
                    "device": {
                        "id": "dev-1",
                        "name": "Laptop",
                        "isTrusted": True,
                        "osName": "macOS",
                        "deviceType": "LAPTOP",
                        "activeState": "ACTIVE",
                        "lastFailedLoginAt": None,
                        "lastSuccessfulLoginAt": None,
                        "lastConnectedAt": None,
                        "osVersion": "14.0",
                        "hardwareModel": "MBP",
                        "hostname": "host",
                        "username": "u",
                        "serialNumber": "SN1",
                        "user": {"firstName": "A", "lastName": "B", "email": "a@b.com"},
                        "clientVersion": "1.0",
                        "manufacturerName": "Apple",
                        "internetSecurityConfiguration": "MACHINE_KEY",
                    }
                }
            }
            result = runner.invoke(app, ["-s", SESSION, "device", "show", "-i", "dev-1"])
        assert result.exit_code == 0
        assert "MACHINE_KEY" in result.output

    def test_show_requires_id(self, mock_keyring):
        result = runner.invoke(app, ["-s", SESSION, "device", "show"])
        assert result.exit_code != 0


class TestDeviceUpdateTrust:
    def test_update_trust_true(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.execute.return_value = _make_mutation_response("deviceUpdate")
            result = runner.invoke(
                app, ["-s", SESSION, "device", "updateTrust", "-l", "dev-1", "-t", "True"]
            )
        assert result.exit_code == 0

    def test_update_trust_invalid_bool(self, mock_keyring):
        result = runner.invoke(
            app, ["-s", SESSION, "device", "updateTrust", "-l", "dev-1", "-t", "maybe"]
        )
        assert result.exit_code != 0


class TestDeviceBlock:
    def test_block_exits_zero(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.execute.return_value = _make_mutation_response("deviceBlock")
            result = runner.invoke(app, ["-s", SESSION, "device", "block", "-i", "dev-1"])
        assert result.exit_code == 0


class TestDeviceUnarchive:
    def test_unarchive_sends_id_and_shows_result(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            inst = MockClient.return_value
            inst.execute.return_value = _make_mutation_response("deviceUnarchive")
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "device", "unarchive", "-i", "dev-1"])
        assert result.exit_code == 0
        query, variables = inst.execute.call_args.args
        assert "deviceUnarchive(id: $deviceID)" in query and variables == {"deviceID": "dev-1"}
        assert "dev-1" in result.output and "ACTIVE" in result.output

    def test_unarchive_reports_api_error(self, mock_keyring):
        with patch("tgcli.commands._common.TwingateClient") as MockClient:
            MockClient.return_value.execute.return_value = {
                "data": {"deviceUnarchive": {"ok": False, "error": "Device does not exist", "entity": None}}
            }
            result = runner.invoke(app, ["-s", SESSION, "-f", "csv", "device", "unarchive", "-i", "dev-1"])
        assert "False" in result.output and "does not exist" in result.output

    def test_unarchive_requires_id(self, mock_keyring):
        assert runner.invoke(app, ["-s", SESSION, "device", "unarchive"]).exit_code != 0
