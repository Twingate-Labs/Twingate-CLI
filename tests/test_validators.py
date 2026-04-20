"""Tests for all validators."""

from __future__ import annotations

import pytest
import typer

from tgcli.validators.generic import parse_bool_string
from tgcli.validators.key import validate_key_expiration
from tgcli.validators.network import validate_rn_location
from tgcli.validators.protocol import (
    validate_port_range,
    validate_protocol_policy,
    validate_range_with_policy,
)
from tgcli.validators.user import validate_user_role, validate_user_state


class TestParseBoolString:
    def test_true_lowercase(self):
        assert parse_bool_string("true") is True

    def test_true_uppercase(self):
        assert parse_bool_string("TRUE") is True

    def test_true_mixed_case(self):
        assert parse_bool_string("True") is True

    def test_false_lowercase(self):
        assert parse_bool_string("false") is False

    def test_false_uppercase(self):
        assert parse_bool_string("FALSE") is False

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="(?i)invalid"):
            parse_bool_string("yes")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_bool_string("")


class TestValidateUserRole:
    @pytest.mark.parametrize("role", ["ADMIN", "DEVOPS", "SUPPORT", "MEMBER"])
    def test_valid_role_uppercase(self, role):
        assert validate_user_role(role) == role

    @pytest.mark.parametrize("role", ["admin", "devops", "support", "member"])
    def test_valid_role_lowercase_normalised(self, role):
        assert validate_user_role(role) == role.upper()

    def test_invalid_role_raises(self):
        with pytest.raises(typer.BadParameter, match="Invalid role"):
            validate_user_role("SUPERUSER")


class TestValidateUserState:
    @pytest.mark.parametrize("state", ["ACTIVE", "DISABLED"])
    def test_valid_state(self, state):
        assert validate_user_state(state) == state

    def test_invalid_state_raises(self):
        with pytest.raises(typer.BadParameter, match="Invalid state"):
            validate_user_state("SUSPENDED")


class TestValidateRnLocation:
    @pytest.mark.parametrize(
        "loc", ["AWS", "AZURE", "GOOGLE_CLOUD", "ON_PREMISE", "OTHER"]
    )
    def test_valid_location(self, loc):
        assert validate_rn_location(loc) == loc

    def test_lowercase_normalised(self):
        assert validate_rn_location("aws") == "AWS"

    def test_invalid_location_raises(self):
        with pytest.raises(typer.BadParameter, match="Invalid location"):
            validate_rn_location("DATACENTER")


class TestValidateProtocolPolicy:
    def test_allow_all(self):
        assert validate_protocol_policy("ALLOW_ALL") == "ALLOW_ALL"

    def test_restricted(self):
        assert validate_protocol_policy("RESTRICTED") == "RESTRICTED"

    def test_lowercase_normalised(self):
        assert validate_protocol_policy("allow_all") == "ALLOW_ALL"

    def test_invalid_raises(self):
        with pytest.raises(typer.BadParameter, match="Invalid policy"):
            validate_protocol_policy("DENY")


class TestValidatePortRange:
    def test_valid_single_port(self):
        result = validate_port_range("[[22, 22]]")
        assert result == [{"start": 22, "end": 22}]

    def test_valid_range(self):
        result = validate_port_range("[[443, 446]]")
        assert result == [{"start": 443, "end": 446}]

    def test_multiple_ranges(self):
        result = validate_port_range("[[22,22],[443,446]]")
        assert result == [{"start": 22, "end": 22}, {"start": 443, "end": 446}]

    def test_empty_list(self):
        result = validate_port_range("[]")
        assert result == []

    def test_invalid_json_raises(self):
        with pytest.raises(typer.BadParameter):
            validate_port_range("not-json")

    def test_start_greater_than_end_raises(self):
        with pytest.raises(typer.BadParameter, match="(?i)start port"):
            validate_port_range("[[443, 22]]")

    def test_out_of_range_port_raises(self):
        with pytest.raises(typer.BadParameter, match="65535"):
            validate_port_range("[[1, 99999]]")


class TestValidateRangeWithPolicy:
    def test_allow_all_with_empty_range_passes(self):
        validate_range_with_policy([], "ALLOW_ALL")  # should not raise

    def test_allow_all_with_nonempty_range_raises(self):
        with pytest.raises(typer.BadParameter, match="ALLOW_ALL"):
            validate_range_with_policy([{"start": 22, "end": 22}], "ALLOW_ALL")

    def test_restricted_with_range_passes(self):
        validate_range_with_policy([{"start": 22, "end": 22}], "RESTRICTED")

    def test_restricted_with_empty_range_passes(self):
        validate_range_with_policy([], "RESTRICTED")


class TestValidateKeyExpiration:
    def test_valid_zero(self):
        assert validate_key_expiration(0) == 0

    def test_valid_365(self):
        assert validate_key_expiration(365) == 365

    def test_valid_middle(self):
        assert validate_key_expiration(90) == 90

    def test_negative_raises(self):
        with pytest.raises(typer.BadParameter, match="Expiration"):
            validate_key_expiration(-1)

    def test_over_365_raises(self):
        with pytest.raises(typer.BadParameter, match="Expiration"):
            validate_key_expiration(366)
