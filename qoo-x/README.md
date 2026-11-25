# QoO-X Desktop — AIORI-3 PS-029

**QoO-X is a desktop experiment controller and single-application test runner for the supplied QoO testbed.** It is designed to help a student select one workload, select one network impairment scenario, run that workload, keep a raw log, and record real measurements.

> **Important:** QoO-X does not implement or invent the QoO scoring mathematics. The supplied QoO engine remains the scoring authority. Empty metric fields mean “not captured yet,” never zero.

## What works in this version

- Desktop GUI built with Python's standard-library Tkinter.
- Connectivity check for the testbed API (`/status`).
- Loads gateway profiles (`/profiles`) and QoO profiles (`/qoo-profiles`) from the testbed.
- Reads QoO profile parameter JSON using `/qoo-profiles/<name>` and loads the selected profile using `/qoo-profiles/load/<name>`; if using the active profile, attempts to detect it through `/qoo-active-profile` and stores a profile-parameter snapshot.
- Applies a selected existing gateway profile using `/profile/<name>`, or calls `/custom` with an editable field mapping, or leaves impairment control to the operator.
- Runs one selected workload: DASH/TCP, DASH/QUIC, or active network probes. WebRTC is explicitly marked as a manual sender/receiver workflow because merely starting it would not constitute a completed WebRTC measurement.
- Can run one chosen scenario or all six scenarios for one selected workload; repeat each scenario 1–5 times.
- Records experiment metadata, command output, exit code, failures/timeouts, and a per-run log.
- Conservatively parses metrics only when a known labelled value appears in command output.
- Lets the user attach measurements actually observed in Grafana/InfluxDB or the supplied testbed output.
- Exports CSV results and includes unit tests + GitHub Actions workflow.
- Uses only Python standard-library modules; no `pip install` is required.

## Architecture

```text
QoO-X Desktop (Tkinter)
  ├── Testbed API client ── GET /status, /profiles, /qoo-profiles
  │                     ├─ POST /profile/<name>
  │                     ├─ POST /qoo-profiles/load/<name>
  │                     └─ POST /custom
  ├── Workload runner ───── scripts/run-godash.sh tcp|quic
  │                     └─ scripts/run-active-probes.sh ...
  └── Experiment store ─── data/results.csv + data/logs/<experiment>.log
                              │
                              └── Real metrics can be attached from testbed telemetry
```

## 1. Requirements

- Python 3.10 or newer.
- Tkinter (included in the standard Python installer on Windows and generally available on Linux/macOS; some Linux systems package it separately as `python3-tk`).
- The supplied QoO testbed repository and its Docker prerequisites for real measurements.
- On Windows, WSL is required to run the supplied `.sh` workload scripts. For the smoothest first run, the testbed can also run directly on Linux.

## 2. Start the supplied QoO testbed first

This project intentionally does **not** copy or replace the upstream QoO scoring engine. Follow the actual upstream setup and OS-specific routing instructions:

<https://github.com/cj-ike-kunze/ietf-126-hackathon-qoo>

A typical Linux/macOS shell flow from the upstream repository is:

```bash
docker compose up -d --build
docker compose ps
```

Then complete the gateway-routing setup for your operating system as described by the upstream README. Verify the target traffic actually crosses the gateway before collecting measurements. A successful GUI connection alone does **not** prove the test traffic is shaped.

The README lists the local control panel at `http://localhost:8080`, Grafana at `http://localhost:3000`, and Gateway API at `http://localhost:9000` in the standard setup. Your configuration may differ.

## 3. Launch QoO-X

### Windows

1. Unzip this folder to a simple location, e.g. `C:\Projects\QoO-X-Desktop`.
2. Install Python 3.10+ from python.org and enable the Python launcher/PATH options.
3. Double-click `run_qoo_x.bat` or run from PowerShell:

```powershell
py qoo_x_app.py
```

4. Install/enable WSL if the testbed scripts will run through WSL. Docker Desktop alone does not guarantee the scripts will run correctly; follow the upstream routing instructions as well.

### Linux

```bash
python3 qoo_x_app.py
```

If Tkinter is missing, install the OS package (for Debian/Ubuntu: `sudo apt install python3-tk`).

### macOS

```bash
python3 qoo_x_app.py
```

Use a Python distribution that includes Tkinter.

## 4. First test: DASH over TCP

For exact Windows/VS Code commands, see `../docs/WINDOWS_FIRST_RUN.md`.

### If the app says “API unavailable”

That message means QoO-X could not contact the separate upstream gateway service; it does not mean the Tkinter window failed. Use the actual `ietf-126-hackathon-qoo` repository as the testbed. The selected folder must contain **both** `docker-compose.yml` and `scripts/run-godash.sh` (or `scripts/run-active-probes.sh` for active probes). Do not select the AIORI starter-pack folder or this `qoo-x/` add-on folder.

From a terminal in the upstream testbed folder, start the services with `docker compose up -d --build`, then inspect them with `docker compose ps`. Verify `http://localhost:9000/status` responds. “Connection refused” usually means no service is listening on that port; HTTP 404 means something responded, but it did not serve that endpoint (check the running containers and port mapping). If it fails, inspect `docker compose logs --tail=100 gateway`.

The upstream README documents Linux/macOS routing, not a guaranteed native-Windows setup. For experiments, follow the upstream routing instructions on a supported Linux/macOS host. WSL2 can be explored, but confirm that test traffic actually traverses the gateway before reporting measurements.

1. Start the supplied testbed and complete its routing setup.
2. Open QoO-X. The API defaults to `http://localhost:9000`.
3. Click **Check connection**. If it fails, fix the testbed first.
4. Select the folder containing the supplied testbed repository (the folder with `scripts/` and `docker-compose.yml`).
5. Click **Refresh profile lists** and review the discovered gateway/QoO profiles.
6. Select `DASH over TCP`, scenario `S0 Baseline`, and the mentor-approved QoO profile.
7. For the first run, keep **Manual** gateway control and apply the baseline from the testbed control panel. This avoids guessing the `/custom` request format. For Manual/Existing gateway profile mode, run one scenario at a time and confirm the selected condition is already applied. After you verify the exact JSON request schema in the upstream gateway source, choose **Custom shaping API** to enable the automated six-scenario sweep.
8. Review the workload command. It invokes the upstream script through Bash; on Windows, QoO-X invokes the script through WSL after checking the selected Windows folder contains the required upstream files.
9. Click **Run selected test**, then read the live log and check the exit code.
10. Inspect Grafana / exported artifacts for real values. In **Results & Logs**, select the run and click **Edit real measurements** to attach values not printed by the workload script.
11. Repeat using `S1`…`S5` and then repeat the same scenarios for the second approved application profile/workload.

## 5. Why `/custom` field mapping is configurable

The public upstream README documents `POST /custom` as the custom shaping endpoint but does not specify its JSON request-body field names. QoO-X therefore supplies an editable mapping in **Settings**. Before final experiments, verify the body schema against the actual `gateway` route in your checked-out version. Do not assume the default mapping is correct for every revision. If the endpoint rejects the request, QoO-X records the error and will not start the workload for that experiment.

## 6. Default scenarios

| ID | Delay | Jitter | Packet loss | Goal |
|---|---:|---:|---:|---|
| S0 | 0 ms | 0 ms | 0% | Baseline |
| S1 | 50 ms | 0 ms | 0% | Delay sensitivity |
| S2 | 100 ms | 0 ms | 0% | Higher delay sensitivity |
| S3 | 0 ms | 20 ms | 0% | Jitter sensitivity |
| S4 | 0 ms | 50 ms | 0% | Higher jitter sensitivity |
| S5 | 0 ms | 0 ms | 1% | Packet-loss sensitivity |

These are starting values; confirm that the mentor approves them and that the testbed supports them. Apply one impairment type at a time. Use the same settings for both profiles.

## 7. Result files

- `data/results.csv`: one row per experiment, including repeat index, scenario/profile metadata, a JSON snapshot of the QoO profile parameters, status, parsed/attached metrics, and log path.
- `data/logs/<experiment-id>.log`: complete QoO-X-run log and workload output.

The CSV contains both *configured impairments* and *measured network metrics*. They are different fields. Do not report configured delay as measured latency. Do not write a synthetic QoO score into measured fields. Record the dashboard/measurement source in the measurement-source field when attaching values.

## 8. Run tests

No dependency installation is needed:

```bash
python -m unittest discover -s tests -v
python -m compileall -q qoo_x qoo_x_app.py tests
```

## 9. GitHub collaboration

This code is the **QoO-X add-on**, not a replacement for the required AIORI team repository template. Put these files into your AIORI team-code repository (for example, a `qoo-x/` folder or the repository root, as your mentor prefers). Do not overwrite the AIORI template or remove their required submission files. Commit after tests pass, push, and ask a teammate/mentor to clone the repository and follow this README on another machine.

## 10. Known limitations (be honest in the report)

- The exact `/custom` request schema must be checked in the supplied testbed source; the app intentionally makes it editable. The default control mode is Manual until that is verified.
- Some workload scripts may write QoO/app metrics into InfluxDB/Grafana or exported files rather than stdout. This version records their output and supports explicit manual attachment, but does not guess the correct Influx query for every upstream configuration.
- WebRTC remains a guided manual workflow in this release because sender/receiver setup and receiver statistics need to be verified in a live browser session.
- The application does not install Docker, configure OS routes, or manipulate system-wide traffic on its own.

## References

- QoO testbed: <https://github.com/cj-ike-kunze/ietf-126-hackathon-qoo>
- AIORI-3 guideline: <https://portal.aiori.in/aiori-3/hackathon-guideline/>
- IETF QoO activity: <https://wiki.ietf.org/en/meeting/126/hackathon>
