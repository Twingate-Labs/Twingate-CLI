"""The per-row CSV report an import writes, for a dry run and a real run alike."""

from __future__ import annotations

import csv
from pathlib import Path

COLUMNS = ("kind", "name", "status", "detail", "warnings", "error", "id", "source")


def write_report(path: Path, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([
                row.kind, row.name, row.status, row.detail, "; ".join(row.warnings), row.error, row.id, row.spec.source,
            ])
