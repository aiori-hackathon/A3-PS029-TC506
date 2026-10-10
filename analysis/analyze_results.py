"""Summarize PS-029 results from either the project schema or QoO-X CSV.

Uses Python's standard library only. The script never calculates a QoO score;
it averages only actual numeric values already present in the input CSV.
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Iterable

METRICS = (
    ("qoo_score", "QoO"),
    ("latency_ms", "Latency ms"),
    ("throughput_mbps", "Throughput Mbps"),
    ("application_metric_value", "App metric"),
)
FAILED_STATUSES = {"FAILED", "WORKLOAD_FAILED", "TIMEOUT", "CANCELLED", "STARTED"}
PROFILE_COLUMNS = ("profile_id", "qoo_profile", "profile", "profile_name")
SCENARIO_COLUMNS = ("scenario_id", "scenario")
STATUS_COLUMNS = ("run_status", "status")


def _first_present(columns: set[str], options: Iterable[str]) -> str | None:
    return next((name for name in options if name in columns), None)


def _number(value: object) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        result = float(str(value).strip())
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


def summarize_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], str, str | None]:
    """Return grouped results, selected profile column, and status column."""
    if not rows:
        raise ValueError("The CSV has no data rows.")
    columns = set().union(*(row.keys() for row in rows))
    profile_col = _first_present(columns, PROFILE_COLUMNS)
    scenario_col = _first_present(columns, SCENARIO_COLUMNS)
    status_col = _first_present(columns, STATUS_COLUMNS)
    if profile_col is None:
        raise ValueError("Missing profile column. Expected one of: " + ", ".join(PROFILE_COLUMNS))
    if scenario_col is None:
        raise ValueError("Missing scenario column. Expected one of: " + ", ".join(SCENARIO_COLUMNS))

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        status = (row.get(status_col, "") if status_col else "").strip().upper()
        if status in FAILED_STATUSES:
            continue
        scenario = (row.get(scenario_col, "") or "").strip()
        profile = (row.get(profile_col, "") or "").strip()
        if scenario and profile:
            groups[(scenario, profile)].append(row)

    summary: list[dict[str, object]] = []
    for (scenario, profile), group_rows in sorted(groups.items()):
        result: dict[str, object] = {
            "scenario_id": scenario,
            "profile": profile,
            "runs": len(group_rows),
        }
        for key, _label in METRICS:
            numbers = [n for row in group_rows if (n := _number(row.get(key))) is not None]
            result[key] = mean(numbers) if numbers else None
            result[key + "_n"] = len(numbers)
        summary.append(result)
    return summary, profile_col, status_col


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="CSV exported by QoO-X or prepared in data/raw/")
    args = parser.parse_args()
    if not args.csv.is_file():
        raise SystemExit(f"CSV file not found: {args.csv}")
    try:
        with args.csv.open("r", newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        summary, profile_col, status_col = summarize_rows(rows)
    except (OSError, csv.Error, ValueError) as exc:
        raise SystemExit(f"Cannot analyse CSV: {exc}") from exc

    print(f"Input: {args.csv}")
    print(f"Profile column: {profile_col}" + (f" | status column: {status_col}" if status_col else ""))
    if not summary:
        print("No non-failed experiment rows were found. This is expected for a CSV containing only failed runs.")
        print("Run the testbed successfully and export real measurements before drawing conclusions.")
        return 0

    headers = ["Scenario", "Profile", "Runs", "QoO mean (n)", "Latency ms mean (n)", "Throughput Mbps mean (n)", "App metric mean (n)"]
    print("\t".join(headers))
    for row in summary:
        values = [str(row["scenario_id"]), str(row["profile"]), str(row["runs"])]
        for key, _label in METRICS:
            val = row[key]
            values.append(f"{val:.3f} ({row[key + '_n']})" if isinstance(val, (int, float)) else f"— (0)")
        print("\t".join(values))
    print("\nMeans are calculated only from numeric values already in the CSV; QoO-X does not calculate QoO.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
