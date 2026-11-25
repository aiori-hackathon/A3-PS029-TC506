"""CSV experiment store with stable columns and safe, explicit blanks."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

COLUMNS = [
    "experiment_id", "timestamp_utc", "repeat_index", "application", "transport", "qoo_profile",
    "profile_parameters_json", "scenario_id", "scenario_name", "configured_delay_ms", "configured_jitter_ms",
    "configured_packet_loss_percent", "gateway_control", "gateway_profile",
    "run_status", "exit_code", "qoo_score", "latency_ms", "throughput_mbps",
    "packet_loss_percent_measured", "jitter_ms_measured", "application_metric_name",
    "application_metric_value", "measurement_source", "log_path", "error_message",
]


class ExperimentStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)
        self.csv_path = self.data_dir / "results.csv"
        if not self.csv_path.exists():
            self._write_rows([])

    def _read_rows(self) -> list[dict[str, str]]:
        if not self.csv_path.exists():
            return []
        with self.csv_path.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            return [{key: (value or "") for key, value in row.items()} for row in reader]

    def _write_rows(self, rows: list[dict[str, Any]]) -> None:
        temp = self.csv_path.with_suffix(".csv.tmp")
        with temp.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") if row.get(key) is not None else "" for key in COLUMNS})
        temp.replace(self.csv_path)

    def add(self, row: dict[str, Any]) -> None:
        rows = self._read_rows()
        rows.append(row)
        self._write_rows(rows)

    def update(self, experiment_id: str, changes: dict[str, Any]) -> bool:
        rows = self._read_rows()
        found = False
        for row in rows:
            if row.get("experiment_id") == experiment_id:
                for key, value in changes.items():
                    if key in COLUMNS:
                        row[key] = "" if value is None else str(value)
                found = True
                break
        if found:
            self._write_rows(rows)
        return found

    def rows(self) -> list[dict[str, str]]:
        return list(reversed(self._read_rows()))

    def write_log(self, experiment_id: str, content: str) -> Path:
        path = self.data_dir / "logs" / f"{experiment_id}.log"
        path.write_text(content, encoding="utf-8", errors="replace")
        return path

    def export_json(self, destination: Path) -> None:
        destination.write_text(json.dumps(self._read_rows(), indent=2), encoding="utf-8")
