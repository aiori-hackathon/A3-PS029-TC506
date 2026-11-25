"""Build application workload commands for the supplied QoO testbed."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path, PureWindowsPath

APPLICATIONS = {
    "DASH over TCP": {"kind": "command", "transport": "TCP", "args": ["bash", "./scripts/run-godash.sh", "tcp"]},
    "DASH over QUIC": {"kind": "command", "transport": "QUIC", "args": ["bash", "./scripts/run-godash.sh", "quic"]},
    "Active network probes": {"kind": "command", "transport": "ICMP/TCP", "args": ["bash", "./scripts/run-active-probes.sh", "172.29.0.20", "172.29.0.20", "3", "3"]},
    "WebRTC (manual workflow)": {"kind": "manual", "transport": "WebRTC", "args": []},
}


def windows_to_wsl_path(path: str) -> str:
    """Convert a drive-letter Windows path to the common /mnt/<drive>/ form."""
    normalized = path.replace("/", "\\")
    match = re.match(r"^([A-Za-z]):\\?(.*)$", normalized)
    if match:
        drive = match.group(1).lower()
        rest = match.group(2).replace("\\", "/").strip("/")
        return f"/mnt/{drive}/{rest}" if rest else f"/mnt/{drive}"
    return path.replace("\\", "/")


def default_command(application: str, testbed_path: str) -> str:
    definition = APPLICATIONS[application]
    if definition["kind"] == "manual":
        return ""
    path = str(Path(testbed_path).expanduser()) if testbed_path else "."
    if os.name == "nt":
        if not shutil.which("wsl.exe"):
            return ""
        wsl_path = windows_to_wsl_path(path)
        args = " ".join(definition["args"])
        return f'wsl.exe bash -lc "cd \'{wsl_path}\' && {args}"'
    args = " ".join(definition["args"])
    return f"bash -lc {shell_quote(f'cd {shell_quote(path)} && {args}')}"


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def validate_testbed_path(path: str, application: str) -> str | None:
    """Validate that the selected folder is the actual upstream testbed.

    This check intentionally runs on Windows too. Selecting the AIORI starter
    pack or the qoo-x add-on folder is not sufficient: the upstream testbed root
    must contain docker-compose.yml and scripts/run-*.sh.
    """
    if APPLICATIONS[application]["kind"] == "manual":
        return None
    if not path.strip():
        return "Choose the folder containing the supplied QoO testbed first."

    root = Path(path).expanduser()
    if not root.is_dir():
        return f"Testbed folder does not exist: {root}"
    expected = "run-godash.sh" if application.startswith("DASH") else "run-active-probes.sh"
    if not (root / "docker-compose.yml").exists():
        return f"Cannot find docker-compose.yml under {root}. Select the actual ietf-126-hackathon-qoo repository folder, not the AIORI starter-pack or qoo-x folder."
    if not (root / "scripts" / expected).is_file():
        return f"Cannot find scripts/{expected} under {root}. Select the upstream QoO testbed folder."

    if os.name == "nt":
        if not shutil.which("wsl.exe"):
            return "This Linux shell workload needs WSL. Install/enable WSL, or use a Linux/macOS testbed machine."
    return None
