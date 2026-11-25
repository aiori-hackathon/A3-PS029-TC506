"""Conservative extraction of measurements from command output.

Only explicit numeric values with recognizable labels are extracted. No QoO
scores are calculated by QoO-X; missing values remain blank for later import.
"""
from __future__ import annotations

import re
from typing import Any

NUMBER = r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))"


def _first(patterns: list[str], text: str) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                continue
    return None


def parse_measurements(output: str) -> dict[str, Any]:
    """Parse known key-value styles without guessing or fabricating data."""
    qoo = _first([
        rf"\bQoO(?:\s+score)?\s*[:=]\s*{NUMBER}",
        rf"\bquality\s+of\s+outcome\s*[:=]\s*{NUMBER}",
    ], output)
    latency = _first([
        rf"\b(?:latency|RTT|round.trip.time)\s*[:=]\s*{NUMBER}\s*(?:ms|msec)?\b",
        rf"\bping\s+time\s*[:=]\s*{NUMBER}\s*ms\b",
    ], output)

    throughput = None
    throughput_match = re.search(
        rf"\b(?:throughput|download(?:\s+speed)?)\s*[:=]\s*{NUMBER}\s*(Gbps|Gbit/s|Mbps|Mbit/s|Kbps|Kbit/s)\b",
        output, flags=re.IGNORECASE | re.MULTILINE,
    )
    if throughput_match:
        throughput = float(throughput_match.group(1))
        unit = throughput_match.group(2).lower()
        if unit in ("gbps", "gbit/s"):
            throughput *= 1000
        elif unit in ("kbps", "kbit/s"):
            throughput /= 1000

    loss = _first([
        rf"\b(?:packet\s+)?loss(?:\s+percent(?:age)?)?\s*[:=]\s*{NUMBER}\s*%?(?![\w.])",
    ], output)
    jitter = _first([rf"\bjitter\s*[:=]\s*{NUMBER}\s*(?:ms|msec)?\b"], output)
    return {
        "qoo_score": qoo,
        "latency_ms": latency,
        "throughput_mbps": throughput,
        "packet_loss_percent_measured": loss,
        "jitter_ms_measured": jitter,
    }
