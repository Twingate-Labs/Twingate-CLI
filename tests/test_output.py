"""Tests for OutputFormatter."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from tgcli.output.formatter import OutputFormatter


def _identity_transformer(data) -> pd.DataFrame:
    """Simple transformer: wrap a list of dicts in a DataFrame."""
    if isinstance(data, list):
        rows = []
        for page in data:
            for edge in page:
                rows.append(edge.get("node", edge))
        return pd.DataFrame(rows)
    return pd.DataFrame([data])


class TestFormatOutput:
    def test_json_format_returns_json_string(self):
        data = {"data": {"id": "r1"}}
        result = OutputFormatter.format_output(data, "JSON", _identity_transformer)
        parsed = json.loads(result)
        assert parsed["data"]["id"] == "r1"

    def test_csv_format_calls_transformer(self):
        data = [[{"node": {"id": "r1", "name": "Res1"}}]]
        result = OutputFormatter.format_output(data, "CSV", _identity_transformer)
        assert "id" in result
        assert "r1" in result

    def test_df_format_returns_string(self):
        data = [[{"node": {"id": "r1", "name": "Res1"}}]]
        result = OutputFormatter.format_output(data, "DF", _identity_transformer)
        assert "r1" in result

    def test_case_insensitive_format(self):
        data = {"id": "r1"}
        result_upper = OutputFormatter.format_output(data, "JSON", _identity_transformer)
        result_lower = OutputFormatter.format_output(data, "json", _identity_transformer)
        assert result_upper == result_lower

    def test_print_output_prints_to_stdout(self, capsys):
        data = {"id": "r1"}
        OutputFormatter.print_output(data, "JSON", _identity_transformer)
        captured = capsys.readouterr()
        assert "r1" in captured.out

    def test_csv_has_no_index_column(self):
        data = [[{"node": {"id": "r1", "name": "Res1"}}]]
        result = OutputFormatter.format_output(data, "CSV", _identity_transformer)
        # CSV should not have a numeric index column
        lines = result.strip().splitlines()
        headers = lines[0].split(",")
        assert headers[0] != ""  # not an empty index column
        assert "0" not in headers  # no numeric index header

    def test_default_format_is_json(self):
        data = {"key": "value"}
        result = OutputFormatter.format_output(data, "UNKNOWN_FMT", _identity_transformer)
        parsed = json.loads(result)
        assert parsed["key"] == "value"
