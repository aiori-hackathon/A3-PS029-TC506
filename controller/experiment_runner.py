"""Minimal PS-029 experiment runner scaffold.

This version is intentionally safe: it defaults to --dry-run so a beginner can
see the sequence before making API calls. Map the scenario/profile names to the
supplied QoO testbed after the base stack is working.
"""
from __future__ import annotations
import argparse, json, pathlib, time, uuid
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENARIO_DIR = ROOT / "scenarios"

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_scenarios():
    return [json.loads(p.read_text()) for p in sorted(SCENARIO_DIR.glob("*.json"))]

def run(dry_run: bool = True):
    profiles = ["PROFILE_A", "PROFILE_B"]
    for profile in profiles:
        for scenario in load_scenarios():
            experiment_id = "EXP-" + uuid.uuid4().hex[:8].upper()
            print(f"\n{experiment_id} | {profile} | {scenario['id']} | {scenario['name']}")
            print(f"impairment = delay={scenario['delay_ms']}ms, jitter={scenario['jitter_ms']}ms, loss={scenario['packet_loss_percent']}%")
            if dry_run:
                print("DRY RUN: reset -> load profile -> apply impairment -> run app -> collect -> save")
            else:
                # TODO: call the supplied QoO gateway/profile APIs here after
                # you have verified the exact testbed endpoints and profile names.
                print("RUN MODE: implement your verified testbed calls here.")
            time.sleep(0.1)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="run mode; still requires verified API mapping")
    args = ap.parse_args()
    run(dry_run=not args.run)
