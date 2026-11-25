# Windows / VS Code: first real QoO-X run

This guide is for the first setup only. QoO-X is the desktop controller; the **upstream QoO testbed is a separate project** and must be running before the API check can succeed.

## A. Check Docker

1. Install and open Docker Desktop. Wait until its engine reports that it is running.
2. Open VS Code and choose **Terminal → New Terminal** (PowerShell).
3. Run:

```powershell
docker --version
docker compose version
git --version
```

If Docker commands fail, fix Docker Desktop first.

## B. Download the actual testbed

Run this only if you have not already cloned the upstream repository:

```powershell
cd "$HOME\Downloads"
git clone https://github.com/cj-ike-kunze/ietf-126-hackathon-qoo.git
```

Now enter that repository (if already cloned, change to the existing folder):

```powershell
cd "$HOME\Downloads\ietf-126-hackathon-qoo"
```

Check that the current folder contains `docker-compose.yml` and a `scripts` folder. **Do not use the AIORI starter pack or `qoo-x` folder as the testbed path.**

## C. Start services and check the API

From the upstream testbed folder, run:

```powershell
docker compose up -d --build
docker compose ps
Invoke-RestMethod -Uri "http://localhost:9000/status" -TimeoutSec 5
```

The last command must return status data. If it does not, inspect:

```powershell
docker compose ps -a
docker compose logs --tail=100 gateway
```

- **Connection refused:** no service is listening at that address/port. Check Docker status, gateway container status, and port publishing.
- **HTTP 404:** a server answered, but not with the expected endpoint. Check whether port 9000 belongs to the correct gateway container and whether you cloned the documented upstream testbed.

## D. Point QoO-X at the correct folder

1. Start QoO-X using `qoo-x\run_qoo_x.bat`.
2. Keep Testbed API as `http://localhost:9000` unless your setup differs.
3. In **Testbed repository folder**, select `C:\Users\<your-user>\Downloads\ietf-126-hackathon-qoo` (use your actual path).
4. Click **Check connection**, then **Refresh profile lists**.
5. The folder validation expects `docker-compose.yml` and the workload script under `scripts/`.

## E. Before you call it an experiment

The upstream README documents the routed impairment workflow on Linux/macOS. Native Windows routing is not documented as supported. WSL2 may work with additional network setup, but do not assume that API connectivity means traffic passes through the emulated gateway.

Follow the upstream README's routing instructions in a supported Linux/macOS environment. Run the documented active-probe test and confirm the output shows the traffic going **via the gateway**, not `BYPASS`. If you cannot verify routing, stop and ask your faculty mentor to help run the testbed on an Ubuntu/Linux lab machine. Do not report results until the gateway path and real telemetry are verified.

## F. First test only

- Select `DASH over TCP` and scenario `S0 — Baseline`.
- Keep gateway control at `Manual`.
- Apply/verify baseline in the testbed control panel, then click **Run selected test**.
- The run should finish with exit code `0`. Verify QoO, latency, throughput and one application metric in actual output/telemetry.
- Keep missing values blank. A green status or a command exit code alone is not proof that QoO and application metrics were measured.
