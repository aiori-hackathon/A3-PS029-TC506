from __future__ import annotations

import unittest

from analyze_results import summarize_rows


class AnalysisTests(unittest.TestCase):
    def test_supports_qoo_x_csv_names_and_ignores_failed_rows(self):
        rows = [
            {"scenario_id": "S0", "qoo_profile": "video-call", "run_status": "WORKLOAD_OK_METRICS_REVIEW", "qoo_score": "80", "latency_ms": "20", "throughput_mbps": "10", "application_metric_value": "30"},
            {"scenario_id": "S0", "qoo_profile": "video-call", "run_status": "WORKLOAD_OK_METRICS_REVIEW", "qoo_score": "100", "latency_ms": "40", "throughput_mbps": "", "application_metric_value": ""},
            {"scenario_id": "S0", "qoo_profile": "video-call", "run_status": "FAILED", "qoo_score": "999", "latency_ms": "1", "throughput_mbps": "999", "application_metric_value": "999"},
        ]
        summary, profile_col, status_col = summarize_rows(rows)
        self.assertEqual(profile_col, "qoo_profile")
        self.assertEqual(status_col, "run_status")
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["runs"], 2)
        self.assertEqual(summary[0]["qoo_score"], 90)
        self.assertEqual(summary[0]["qoo_score_n"], 2)
        self.assertEqual(summary[0]["throughput_mbps"], 10)
        self.assertEqual(summary[0]["throughput_mbps_n"], 1)

    def test_supports_project_profile_id_schema(self):
        summary, profile_col, _ = summarize_rows([
            {"scenario_id": "S1", "profile_id": "dash", "qoo_score": "85", "run_status": "OK"}
        ])
        self.assertEqual(profile_col, "profile_id")
        self.assertEqual(summary[0]["profile"], "dash")


if __name__ == "__main__":
    unittest.main(verbosity=2)
