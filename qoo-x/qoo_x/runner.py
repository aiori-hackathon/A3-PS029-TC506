"""One-workload experiment runner; no QoO scoring is implemented here."""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .api_client import QoOTestbedClient, TestbedAPIError, extract_profile_name
from .commands import APPLICATIONS, default_command, validate_testbed_path
from .metrics import parse_measurements
from .store import ExperimentStore


class ExperimentError(RuntimeError):
    pass


class ExperimentRunner:
    def __init__(self, app_root: Path, store: ExperimentStore):
        self.app_root = Path(app_root)
        self.store = store

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _check_api_response(response: Any, action: str) -> None:
        if isinstance(response, dict):
            if response.get("ok") is False or response.get("success") is False or response.get("error"):
                detail = response.get("error") or response.get("message") or response
                raise ExperimentError(f"{action} was rejected by the API: {detail}")

    @staticmethod
    def build_custom_payload(scenario: dict[str, Any], key_map: dict[str, str]) -> dict[str, Any]:
        canonical = {
            "delay_ms": scenario["delay_ms"],
            "jitter_ms": scenario["jitter_ms"],
            "packet_loss_percent": scenario["packet_loss_percent"],
        }
        payload: dict[str, Any] = {}
        for canonical_key, actual_key in key_map.items():
            if canonical_key in canonical and isinstance(actual_key, str) and actual_key:
                payload[actual_key] = canonical[canonical_key]
        return payload

    def run_one(
        self,
        *, api: QoOTestbedClient,
        app_name: str,
        scenario: dict[str, Any],
        qoo_profile: str,
        testbed_path: str,
        command: str,
        control_mode: str,
        gateway_profile: str,
        key_map: dict[str, str],
        timeout_seconds: int,
        log_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        log_parts: list[str] = []

        def log(message: str) -> None:
            log_parts.append(message)
            if log_callback:
                log_callback(message)

        if app_name not in APPLICATIONS:
            raise ExperimentError(f"Unknown application: {app_name}")
        if APPLICATIONS[app_name]["kind"] == "manual":
            raise ExperimentError("WebRTC needs a browser sender/receiver session; use the manual workflow tab in the guide rather than treating setup as a completed test.")
        path_error = validate_testbed_path(testbed_path, app_name)
        if path_error:
            raise ExperimentError(path_error)
        if not command.strip():
            raise ExperimentError("The application command is empty. Choose an application workload first.")

        experiment_id = "QX-" + uuid.uuid4().hex[:10].upper()
        log(f"Experiment ID: {experiment_id}")
        log(f"Started UTC: {self._iso_now()}")
        log(f"Application: {app_name}")
        log(f"Scenario: {scenario['id']} - {scenario['name']}")
        row: dict[str, Any] = {
            "experiment_id": experiment_id,
            "timestamp_utc": self._iso_now(),
            "application": app_name,
            "transport": APPLICATIONS[app_name]["transport"],
            "qoo_profile": qoo_profile,
            "profile_parameters_json": "",
            "scenario_id": scenario["id"],
            "scenario_name": scenario["name"],
            "configured_delay_ms": scenario["delay_ms"],
            "configured_jitter_ms": scenario["jitter_ms"],
            "configured_packet_loss_percent": scenario["packet_loss_percent"],
            "gateway_control": control_mode,
            "gateway_profile": gateway_profile,
            "run_status": "STARTED",
            "exit_code": "",
            "qoo_score": "",
            "latency_ms": "",
            "throughput_mbps": "",
            "packet_loss_percent_measured": "",
            "jitter_ms_measured": "",
            "application_metric_name": "",
            "application_metric_value": "",
            "measurement_source": "",
            "log_path": "",
            "error_message": "",
        }
        self.store.add(row)

        try:
            log("\n[1/4] Checking testbed API…")
            status = api.get_status()
            log("API status: " + json.dumps(status, ensure_ascii=False))

            if control_mode == "custom":
                payload = self.build_custom_payload(scenario, key_map)
                log("\n[2/4] Applying impairment via POST /custom with payload:")
                log(json.dumps(payload, indent=2))
                response = api.apply_custom_impairment(payload)
                log("Gateway response: " + json.dumps(response, ensure_ascii=False))
                self._check_api_response(response, "Applying custom impairment")
            elif control_mode == "profile":
                if not gateway_profile:
                    raise ExperimentError("Select an existing gateway profile or choose Custom shaping API.")
                log(f"\n[2/4] Applying existing gateway profile: {gateway_profile}")
                response = api.apply_gateway_profile(gateway_profile)
                log("Gateway response: " + json.dumps(response, ensure_ascii=False))
                self._check_api_response(response, "Applying gateway profile")
            elif control_mode == "manual":
                log("\n[2/4] Manual control selected. Ensure you applied the scenario in the testbed control panel before starting this test.")
            else:
                raise ExperimentError(f"Unknown gateway control mode: {control_mode}")

            if qoo_profile and qoo_profile not in ("(detect active and record it)", "(leave active profile unchanged)"):
                log(f"\n[3/4] Reading and loading QoO profile: {qoo_profile}")
                profile_config = api.get_qoo_profile(qoo_profile)
                self._check_api_response(profile_config, "Reading QoO profile parameters")
                row["profile_parameters_json"] = json.dumps(profile_config, ensure_ascii=False, sort_keys=True)
                log("QoO profile parameters snapshot: " + json.dumps(profile_config, ensure_ascii=False))
                profile_response = api.load_qoo_profile(qoo_profile)
                log("QoO profile load response: " + json.dumps(profile_response, ensure_ascii=False))
                self._check_api_response(profile_response, "Loading QoO profile")
            else:
                log("\n[3/4] Detecting and recording the active QoO profile.")
                active_response = api.get_active_qoo_profile()
                active_name = extract_profile_name(active_response)
                row["qoo_profile"] = active_name or "(active profile not confirmed)"
                if active_name:
                    try:
                        profile_config = api.get_qoo_profile(active_name)
                        row["profile_parameters_json"] = json.dumps(profile_config, ensure_ascii=False, sort_keys=True)
                        log("Active QoO profile: " + active_name)
                        log("QoO profile parameters snapshot: " + json.dumps(profile_config, ensure_ascii=False))
                    except TestbedAPIError as profile_error:
                        row["profile_parameters_json"] = json.dumps({"active_profile_response": active_response, "parameter_lookup_error": str(profile_error)}, ensure_ascii=False, sort_keys=True)
                        log("WARNING: active profile name was detected but its parameter JSON could not be fetched: " + str(profile_error))
                else:
                    row["profile_parameters_json"] = json.dumps({"active_profile_response": active_response}, ensure_ascii=False, sort_keys=True)
                    log("WARNING: could not extract the active profile name. Check the log and record the profile manually before using this run in the report.")

            log("\n[4/4] Starting workload command:")
            log(command)
            cwd = str(Path(testbed_path).expanduser()) if os.name != "nt" else None
            started = time.monotonic()
            process = subprocess.Popen(
                command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
            output_lines: list[str] = []

            def stream_output() -> None:
                if process.stdout is None:
                    return
                try:
                    for line in process.stdout:
                        output_lines.append(line)
                        log("[workload] " + line.rstrip("\r\n"))
                finally:
                    process.stdout.close()

            reader = threading.Thread(target=stream_output, daemon=True)
            reader.start()
            try:
                exit_code = process.wait(timeout=max(1, int(timeout_seconds)))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                reader.join(timeout=2)
                raise subprocess.TimeoutExpired(command, timeout_seconds, output="".join(output_lines))
            reader.join(timeout=2)
            duration = time.monotonic() - started
            stdout = "".join(output_lines)
            log(f"\nExit code: {exit_code}; runtime: {duration:.2f} seconds")
            parsed = parse_measurements(stdout)
            row.update(parsed)
            row["exit_code"] = exit_code
            row["run_status"] = "WORKLOAD_OK_METRICS_REVIEW" if exit_code == 0 else "WORKLOAD_FAILED"
            if not any(parsed.get(key) is not None for key in ("qoo_score", "latency_ms", "throughput_mbps")):
                log("\nNOTE: The command did not print recognizable QoO/latency/throughput values. Those fields remain blank; import/enter real measurements from the testbed telemetry before reporting results.")
            if exit_code != 0:
                row["error_message"] = f"Application command returned exit code {exit_code}. See log."
        except subprocess.TimeoutExpired as exc:
            log(f"\nERROR: Workload exceeded timeout ({timeout_seconds}s).")
            if exc.stdout:
                log(str(exc.stdout))
            row["run_status"] = "TIMEOUT"
            row["error_message"] = f"Workload exceeded {timeout_seconds} seconds."
        except (TestbedAPIError, ExperimentError, OSError, ValueError) as exc:
            log(f"\nERROR: {exc}")
            row["run_status"] = "FAILED"
            row["error_message"] = str(exc)
        finally:
            log("\nFinished UTC: " + self._iso_now())
            log_path = self.store.write_log(experiment_id, "\n".join(log_parts))
            row["log_path"] = str(log_path)
            self.store.update(experiment_id, row)

        return row
