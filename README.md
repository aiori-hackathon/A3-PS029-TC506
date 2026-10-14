# AIORI-3 PS-029 - QoO-X (Team CoderScythe)

**Problem:** PS-029 Application-Oriented Network Quality Evaluation Using QoO.
**Solution:** QoO-X, a reproducible experiment and comparison layer around the supplied IETF QoO testbed. We do not change the QoO mathematics.

- Team code: A3-PS029-TC506
- Team leader: Satyam Raj - Team member: Pranaba Ballav - Faculty mentor: Dr. Subhayu Ghosh
- Team introduction video: (https://youtu.be/RHU6t69ZPPs?si=cLAVkb7L_mWn_S9U)

## What we do
Two mentor-approved application profiles (WebRTC and DASH) are tested under six controlled scenarios (delay, jitter, loss). We record QoO, latency, throughput and at least one application metric, then compare both profiles under identical conditions.

## Repository structure
| Folder | Purpose |
|---|---|
| `Proposed-structure-hackathon.pdf` | Step 5 proposal |
| `profiles/` | The two application profile notes (need mentor approval) |
| `scenarios/` | S0-S5 impairment definitions (JSON) |
| `controller/` | Experiment runner scaffold (dry-run by default) |
| `analysis/` | Results comparison script |
| `data/raw`, `data/processed` | Untouched exports and cleaned tables |
| `docs/` | Methodology, results, next steps |
| `qoo-x/` | QoO-X Desktop app (Tkinter, tests, own README) |
| `video/` | Team video link and template |

## How to run
See `qoo-x/README.md` and the beginner-friendly `docs/WINDOWS_FIRST_RUN.md`. On Windows, the QoO-X desktop window can run natively, but the supplied testbed's network-routing instructions are written for Linux/macOS. Use a supported Linux environment for real impairment tests; WSL2 may require extra network troubleshooting and is not guaranteed by the upstream README.

From the repository root, run the app checks:

```bash
cd qoo-x
python -m compileall -q qoo_x qoo_x_app.py tests
python -m unittest discover -s tests -v
```

After copying reviewed real results to `data/raw/`, return to the repository root (run `cd ..` if your terminal is still inside `qoo-x/`) and summarize a CSV with:

```bash
python analysis/analyze_results.py data/raw/YOUR_REAL_RESULTS.csv
```

The analysis script uses only Python's standard library. Results in `docs/results.md` come only from real runs. No secrets or unredacted machine-specific paths are committed.
