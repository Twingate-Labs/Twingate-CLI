"""Output formatter — replaces StdAPIUtils.format_output."""

from __future__ import annotations

import json
from typing import Any, Callable

import pandas as pd


class OutputFormatter:
    """Format API results as JSON, CSV, or DataFrame and print to stdout."""

    @staticmethod
    def format_output(
        data: Any,
        output_format: str,
        transformer_func: Callable[..., pd.DataFrame],
    ) -> str:
        """Format *data* using *transformer_func* according to *output_format*.

        Args:
            data:             Raw API response (dict for show/mutate, list for paginated list).
            output_format:    "JSON", "CSV", or "DF".
            transformer_func: Callable that accepts *data* and returns a DataFrame.

        Returns:
            A string ready to be printed.
        """
        fmt = output_format.upper()
        if fmt in ("DF", "CSV"):
            df = transformer_func(data)
            if fmt == "DF":
                return df.to_string()
            return df.to_csv(index=False)
        # Default: raw JSON
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def print_output(
        data: Any,
        output_format: str,
        transformer_func: Callable[..., pd.DataFrame],
    ) -> None:
        """Format and print *data* to stdout."""
        print(OutputFormatter.format_output(data, output_format, transformer_func))
