# Data

Keep two levels:
- `raw/` - untouched exports from the experiment system
- `processed/` - cleaned tables used for charts

Recommended CSV columns:
`experiment_id, timestamp, profile_id, scenario_id, delay_ms, jitter_ms, packet_loss_percent, qoo_score, latency_ms, throughput_mbps, application_metric_name, application_metric_value, notes`
