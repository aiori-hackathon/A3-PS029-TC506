from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from qoo_x.api_client import QoOTestbedClient, extract_names
from qoo_x.commands import validate_testbed_path, windows_to_wsl_path
from qoo_x.metrics import parse_measurements
from qoo_x.runner import ExperimentError, ExperimentRunner
from qoo_x.store import ExperimentStore


class FakeHandler(BaseHTTPRequestHandler):
    requests_seen = []

    def do_GET(self):
        if self.path == "/status":
            body = {"active_profile": "video-call", "ok": True}
        elif self.path == "/profiles":
            body = ["baseline", "delay-50"]
        elif self.path == "/qoo-profiles":
            body = {"profiles": [{"name": "video-call"}, {"name": "video-stream"}]}
        elif self.path == "/qoo-active-profile":
            body = {"active_profile": "video-call"}
        elif self.path.startswith("/qoo-profiles/"):
            body = {"name": self.path.rsplit("/", 1)[-1], "parameters": {"rtt_threshold_ms": 100, "packet_loss_threshold_percent": 1}}
        else:
            self.send_error(404)
            return
        self._json(200, body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        self.requests_seen.append((self.path, payload))
        self._json(200, {"ok": True, "path": self.path})

    def _json(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class CoreTests(unittest.TestCase):
    def test_extract_profile_names(self):
        self.assertEqual(extract_names(["z", {"name": "a"}, {"id": "b"}]), ["a", "b", "z"])
        self.assertEqual(extract_names({"profiles": [{"name": "one"}]}), ["one"])

    def test_parse_measurements_only_when_present(self):
        result = parse_measurements("QoO score: 82.5\nRTT: 33 ms\nThroughput: 1.25 Gbps\npacket loss: 0.5%\njitter: 8 ms")
        self.assertEqual(result["qoo_score"], 82.5)
        self.assertEqual(result["latency_ms"], 33.0)
        self.assertEqual(result["throughput_mbps"], 1250.0)
        self.assertEqual(result["packet_loss_percent_measured"], 0.5)
        self.assertEqual(result["jitter_ms_measured"], 8.0)
        blank = parse_measurements("test finished without printed metrics")
        self.assertIsNone(blank["qoo_score"])
        self.assertIsNone(blank["latency_ms"])

    def test_store_add_and_update(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ExperimentStore(Path(temp))
            store.add({"experiment_id": "QX-1", "run_status": "STARTED", "qoo_score": ""})
            self.assertTrue(store.update("QX-1", {"run_status": "OK", "qoo_score": 88}))
            self.assertEqual(store.rows()[0]["run_status"], "OK")
            self.assertEqual(store.rows()[0]["qoo_score"], "88")

    def test_windows_path_conversion(self):
        self.assertEqual(windows_to_wsl_path(r"C:\Users\Student\qoo-testbed"), "/mnt/c/Users/Student/qoo-testbed")

    def test_wrong_testbed_folder_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            # An empty folder such as the AIORI starter pack must not be accepted
            # as the upstream testbed just because WSL is installed.
            error = validate_testbed_path(temp, "DASH over TCP")
            self.assertIn("docker-compose.yml", error or "")

    def test_testbed_folder_requires_workload_script(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
            (root / "scripts").mkdir()
            error = validate_testbed_path(temp, "DASH over TCP")
            self.assertIn("run-godash.sh", error or "")

    def test_api_error_response_is_not_treated_as_success(self):
        with self.assertRaises(ExperimentError):
            ExperimentRunner._check_api_response({"ok": False, "error": "invalid field"}, "Apply impairment")

    def test_api_integration_and_runner(self):
        FakeHandler.requests_seen.clear()
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = QoOTestbedClient(f"http://127.0.0.1:{server.server_port}")
            self.assertTrue(client.get_status()["ok"])
            self.assertIn("baseline", extract_names(client.get_gateway_profiles()))
            self.assertIn("video-call", extract_names(client.get_qoo_profiles()))
            with tempfile.TemporaryDirectory() as temp:
                temp_path = Path(temp)
                (temp_path / "docker-compose.yml").write_text("services: {}", encoding="utf-8")
                (temp_path / "scripts").mkdir()
                (temp_path / "scripts" / "run-godash.sh").write_text("#!/bin/sh\necho 'QoO score: 91'\necho 'Latency: 20 ms'\necho 'Throughput: 15 Mbps'\n", encoding="utf-8")
                with tempfile.TemporaryDirectory() as data_dir:
                    store = ExperimentStore(Path(data_dir))
                    runner = ExperimentRunner(Path(temp), store)
                    row = runner.run_one(
                        api=client,
                        app_name="DASH over TCP",
                        scenario={"id":"S0", "name":"Baseline", "delay_ms":0, "jitter_ms":0, "packet_loss_percent":0},
                        qoo_profile="video-call",
                        testbed_path=temp,
                        command="printf 'QoO score: 91\\nLatency: 20 ms\\nThroughput: 15 Mbps\\n'",
                        control_mode="custom",
                        gateway_profile="",
                        key_map={"delay_ms":"delay_ms", "jitter_ms":"jitter_ms", "packet_loss_percent":"loss_percent"},
                        timeout_seconds=10,
                    )
                    self.assertEqual(row["run_status"], "WORKLOAD_OK_METRICS_REVIEW")
                    self.assertEqual(row["qoo_score"], 91.0)
                    self.assertEqual(row["latency_ms"], 20.0)
                    self.assertEqual(row["throughput_mbps"], 15.0)
                    self.assertIn("rtt_threshold_ms", row["profile_parameters_json"])
                    self.assertTrue(Path(row["log_path"]).exists())
            self.assertTrue(any(path == "/custom" for path, _ in FakeHandler.requests_seen))
            self.assertTrue(any(path == "/qoo-profiles/load/video-call" for path, _ in FakeHandler.requests_seen))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
