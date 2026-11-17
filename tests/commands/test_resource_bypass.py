"""`tgcli resource bypass`: dry run by default, one update per Resource with --execute."""

from __future__ import annotations

import csv
import io
import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tgcli.client.exceptions import TwingateAPIError
from tgcli.client.session import SessionManager
from tgcli.main import app

runner = CliRunner()
SESSION = "TestSess"
OPEN = {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}}
RESTRICTED = {"allowIcmp": False, "tcp": {"policy": "RESTRICTED", "ports": [{"start": 443, "end": 443}]}, "udp": OPEN["udp"]}


@pytest.fixture(autouse=True)
def stored_session(mock_keyring):
    SessionManager.store(SESSION, "acme", "tok-test")


def resource(rid, **changes):
    base = {"__typename": "NetworkResource", "id": rid, "name": f"name-{rid}", "routingMode": "THROUGH_TWINGATE",
            "securityPolicy": {"id": "pol-1", "name": "Strict"}, "protocols": RESTRICTED}
    base.update(changes)
    return base


class FakeApi:
    """Answers reads from ``resources`` and records every write; ``refuse`` makes the update answer ok: false."""

    def __init__(self, resources, refuse=None):
        self.resources, self.refuse, self.writes = resources, refuse or {}, []

    def execute(self, query, variables=None):
        if "bypassRead" in query:
            if variables["id"] == "bad-format":
                raise TwingateAPIError("GraphQL error: {'id': ['Unable to parse global ID']}")
            return {"data": {"resource": self.resources.get(variables["id"])}}
        assert "bypassResource" in query, query
        self.writes.append(variables)
        if variables["id"] in self.refuse:
            return {"data": {"resourceUpdate": {"ok": False, "error": self.refuse[variables["id"]], "entity": None}}}
        entity = {"id": variables["id"], "name": "x", "securityPolicy": None, "routingMode": "BYPASS_TWINGATE"}
        return {"data": {"resourceUpdate": {"ok": True, "error": None, "entity": entity}}}


def run(api, *args, fmt="json"):
    with patch("tgcli.commands._common.TwingateClient") as client:
        client.return_value.execute.side_effect = api.execute
        return runner.invoke(app, ["-s", SESSION, "-f", fmt, "resource", "bypass", *args])


def rows_of(result):
    out = result.stdout
    return json.loads(out)


class TestDryRun:
    def test_nothing_is_written_without_execute(self):
        api = FakeApi({"r1": resource("r1")})
        result = run(api, "-i", "r1")
        assert result.exit_code == 0 and api.writes == []
        assert rows_of(result)[0]["status"] == "would convert"
        assert "Dry run: nothing was changed" in result.stderr and "--execute" in result.stderr

    def test_it_says_what_would_be_removed_and_what_the_resource_had(self):
        row = rows_of(run(FakeApi({"r1": resource("r1")}), "-i", "r1"))[0]
        assert "Security Policy 'Strict' is removed" in row["detail"] and "TCP is limited to 443" in row["detail"]
        assert (row["securityPolicyId"], row["securityPolicyName"], row["tcpPorts"]) == ("pol-1", "Strict", "443")

    def test_when_nothing_can_be_converted_it_says_so(self):
        result = run(FakeApi({"r1": resource("r1", routingMode="BYPASS_TWINGATE")}), "-i", "r1")
        assert result.exit_code == 0 and "Nothing to convert." in result.stderr


class TestExecute:
    def test_one_update_per_resource_clears_the_policy_and_opens_the_ports(self):
        api = FakeApi({"r1": resource("r1")})
        result = run(api, "-i", "r1", "--execute")
        assert result.exit_code == 0
        assert api.writes == [{"id": "r1", "securityPolicyId": None, "protocols": {"allowIcmp": True, "tcp": {"policy": "ALLOW_ALL", "ports": []}, "udp": {"policy": "ALLOW_ALL", "ports": []}}}]
        assert rows_of(result)[0]["status"] == "converted" and "Converted 1 of 1" in result.stderr

    def test_a_resource_with_no_policy_and_open_ports_only_has_its_routing_switched(self):
        api = FakeApi({"r1": resource("r1", securityPolicy=None, protocols=OPEN)})
        run(api, "-i", "r1", "--execute")
        assert api.writes == [{"id": "r1"}]

    def test_several_ids_by_comma_and_by_repeating_the_option_each_once(self):
        api = FakeApi({k: resource(k) for k in ("r1", "r2", "r3")})
        result = run(api, "-i", "r1,r2", "-i", "r3,r1", "--execute")
        assert [w["id"] for w in api.writes] == ["r1", "r2", "r3"] and result.exit_code == 0

    def test_already_bypass_resources_are_not_written(self):
        api = FakeApi({"r1": resource("r1", routingMode="BYPASS_TWINGATE"), "r2": resource("r2")})
        result = run(api, "-i", "r1,r2", "--execute")
        assert [w["id"] for w in api.writes] == ["r2"] and result.exit_code == 0
        assert [r["status"] for r in rows_of(result)] == ["already bypass", "converted"]

    def test_a_refusal_is_an_error_row_and_exit_1_but_the_others_are_still_converted(self):
        api = FakeApi({"r1": resource("r1"), "r2": resource("r2")}, refuse={"r1": "Bypass Resources cannot have port restrictions"})
        result = run(api, "-i", "r1,r2", "--execute")
        assert result.exit_code == 1
        rows = rows_of(result)
        assert (rows[0]["status"], rows[0]["error"]) == ("error", "Bypass Resources cannot have port restrictions")
        assert rows[1]["status"] == "converted" and "Converted 1 of 2" in result.stderr

    def test_an_answer_that_does_not_show_bypass_is_not_called_converted(self):
        class Lying(FakeApi):
            def execute(self, query, variables=None):
                reply = super().execute(query, variables)
                if "bypassResource" in query:
                    reply["data"]["resourceUpdate"]["entity"]["routingMode"] = "THROUGH_TWINGATE"
                return reply

        result = run(Lying({"r1": resource("r1")}), "-i", "r1", "--execute")
        assert result.exit_code == 1 and rows_of(result)[0]["status"] == "error"


    def test_an_answer_that_still_shows_a_policy_is_not_called_converted(self):
        class StillThere(FakeApi):
            def execute(self, query, variables=None):
                reply = super().execute(query, variables)
                if "bypassResource" in query:
                    reply["data"]["resourceUpdate"]["entity"]["securityPolicy"] = {"id": "pol-1"}
                return reply

        result = run(StillThere({"r1": resource("r1")}), "-i", "r1", "--execute")
        assert result.exit_code == 1 and rows_of(result)[0]["status"] == "error"

    def test_the_update_sends_the_routing_mode_the_policy_and_the_protocols_in_one_mutation(self):
        from tgcli.queries import resources as rq

        text = rq.BYPASS_RESOURCE
        assert text.count("resourceUpdate(") == 1
        assert "routingMode: BYPASS_TWINGATE" in text
        assert "securityPolicyId: $securityPolicyId" in text and "protocols: $protocols" in text
        assert "$securityPolicyId: ID," in text and "$protocols: ProtocolsInput" in text


class TestWhatCannotBeConverted:
    def test_a_missing_resource_and_a_typed_one_are_blocked_and_nothing_is_written(self):
        typed = resource("r2", __typename="SSHResource")
        del typed["routingMode"]
        api = FakeApi({"r1": resource("r1"), "r2": typed})
        result = run(api, "-i", "r1,r2,nope", "--execute")
        assert result.exit_code == 1
        assert [r["status"] for r in rows_of(result)] == ["converted", "blocked", "blocked"]
        assert [w["id"] for w in api.writes] == ["r1"]

    def test_an_id_the_api_cannot_parse_is_blocked_and_the_rest_carry_on(self):
        api = FakeApi({"r1": resource("r1")})
        result = run(api, "-i", "bad-format,r1")
        assert result.exit_code == 1
        assert [r["status"] for r in rows_of(result)] == ["blocked", "would convert"]
        assert "Unable to parse global ID" in result.stderr

    def test_an_empty_list_of_ids_is_refused(self):
        result = run(FakeApi({}), "-i", " , ")
        assert result.exit_code == 1 and "at least one Resource ID" in result.stderr


def test_csv_output_has_the_documented_columns():
    from tgcli.bypass import COLUMNS

    result = run(FakeApi({"r1": resource("r1")}), "-i", "r1", fmt="csv")
    assert next(csv.reader(io.StringIO(result.stdout))) == list(COLUMNS)


class TestRoutingHint:
    def test_a_refused_bypass_points_at_the_new_command(self):
        with patch("tgcli.commands._common.TwingateClient") as client:
            client.return_value.execute.return_value = {"data": {"resourceUpdate": {"ok": False, "error": "Bypass Resource cannot have a Security Policy", "entity": None}}}
            result = runner.invoke(app, ["-s", SESSION, "resource", "routing", "-i", "r1", "-m", "BYPASS_TWINGATE"])
        assert result.exit_code == 1
        assert "cannot have a Security Policy" in result.stderr and f"-s {SESSION} resource bypass -i r1" in result.stderr

    @pytest.mark.parametrize(
        "mode,error",
        [("BYPASS_TWINGATE", "Something else"), ("THROUGH_TWINGATE", "Bypass Resource cannot have a Security Policy")],
    )
    def test_other_refusals_and_the_other_direction_get_no_hint(self, mode, error):
        with patch("tgcli.commands._common.TwingateClient") as client:
            client.return_value.execute.return_value = {"data": {"resourceUpdate": {"ok": False, "error": error, "entity": None}}}
            result = runner.invoke(app, ["-s", SESSION, "resource", "routing", "-i", "r1", "-m", mode])
        assert result.exit_code == 1 and "resource bypass" not in result.stderr
