"""The per-row CSV report an import writes, for a dry run and a real run alike."""

from __future__ import annotations

import csv
from pathlib import Path

COLUMNS = ("kind", "name", "status", "detail", "warnings", "error", "id", "source")


NOT_CARRIED = "not carried over"


def write_report(path: Path, rows: list, notices: tuple = ()) -> None:
    """One line per row, then one per thing the backup holds that an import cannot carry over (kind and status say so)."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([
                row.kind, row.name, row.status, row.detail, "; ".join(row.warnings), row.error, row.id, row.spec.source,
            ])
        for notice in notices:
            writer.writerow([NOT_CARRIED, notice.what, NOT_CARRIED, notice.detail, "", "", "", notice.source])
