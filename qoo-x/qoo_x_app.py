from __future__ import annotations

import csv
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from qoo_x.api_client import QoOTestbedClient, TestbedAPIError, extract_names
from qoo_x.commands import APPLICATIONS, default_command, validate_testbed_path
from qoo_x.runner import ExperimentRunner
from qoo_x.store import ExperimentStore

APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"
SCENARIO_PATH = APP_ROOT / "qoo_x" / "scenarios.json"
CONFIG_PATH = APP_ROOT / "config.json"
DEFAULT_CONFIG = {
    "api_base_url": "http://localhost:9000",
    "testbed_path": "",
    "gateway_control_mode": "manual",
    "custom_payload_keys": {
        "delay_ms": "delay_ms",
        "jitter_ms": "jitter_ms",
        "packet_loss_percent": "loss_percent",
    },
    "command_timeout_seconds": 600,
    "control_panel_url": "http://localhost:8080",
    "grafana_url": "http://localhost:3000",
}


class QoOXDesktop:
    BG = "#f3f6fb"
    NAVY = "#13213c"
    BLUE = "#1d4ed8"
    GREEN = "#12805c"
    RED = "#b42318"
    TEXT = "#1e293b"
    MUTED = "#64748b"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("QoO-X | Application Quality Lab")
        self.root.geometry("1180x820")
        self.root.minsize(970, 700)
        self.root.configure(bg=self.BG)
        self.store = ExperimentStore(DATA_DIR)
        self.runner = ExperimentRunner(APP_ROOT, self.store)
        self.config = self._load_config()
        self.scenarios = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
        self.scenario_by_label = {self._scenario_label(s): s for s in self.scenarios}
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.running = False
        self.api_connected = False
        self.last_status: object = None
        self.gateway_profiles: list[str] = []
        self.qoo_profiles: list[str] = []
        self._setup_style()
        self._build_ui()
        self._load_results()
        self._poll_events()
        self._set_status("Not connected", "muted")
        self.root.after(250, self._test_connection_async)

    @staticmethod
    def _scenario_label(scenario: dict) -> str:
        return f"{scenario['id']}  |  {scenario['name']}  ({scenario['delay_ms']} ms delay, {scenario['jitter_ms']} ms jitter, {scenario['packet_loss_percent']}% loss)"

    def _load_config(self) -> dict:
        if not CONFIG_PATH.exists():
            CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
            return dict(DEFAULT_CONFIG)
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            result = dict(DEFAULT_CONFIG)
            result.update(loaded)
            # Repair a known old local config where Grafana accidentally pointed
            # to the gateway API (port 9000) instead of Grafana (port 3000).
            if result.get("grafana_url", "").rstrip("/") == result.get("api_base_url", "").rstrip("/"):
                result["grafana_url"] = DEFAULT_CONFIG["grafana_url"]
            return result
        except (OSError, json.JSONDecodeError):
            return dict(DEFAULT_CONFIG)

    def _save_config(self) -> None:
        try:
            self.config.update({
                "api_base_url": self.api_url_var.get().strip().rstrip("/"),
                "testbed_path": self.path_var.get().strip(),
                "gateway_control_mode": self.control_mode_var.get(),
                "command_timeout_seconds": int(self.timeout_var.get()),
                "repeat_count": int(self.repeat_var.get()),
                "control_panel_url": self.control_url_var.get().strip(),
                "grafana_url": self.grafana_url_var.get().strip(),
            })
            try:
                mapping = json.loads(self.payload_keys_var.get())
                if not isinstance(mapping, dict):
                    raise ValueError("Payload field mapping must be a JSON object.")
                self.config["custom_payload_keys"] = mapping
            except (json.JSONDecodeError, ValueError) as exc:
                messagebox.showerror("Invalid payload mapping", str(exc))
                return
            CONFIG_PATH.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
            self._append_log(f"Saved settings to {CONFIG_PATH}")
            messagebox.showinfo("Settings saved", "Settings saved locally. They are not uploaded anywhere.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not save settings", str(exc))

    def _setup_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=self.BG)
        style.configure("Card.TFrame", background="white", relief="flat")
        style.configure("TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.BG, foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=self.NAVY, foreground="white", font=("Segoe UI", 19, "bold"))
        style.configure("Subtitle.TLabel", background=self.NAVY, foreground="#dbeafe", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="white", foreground=self.NAVY, font=("Segoe UI", 11, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8))
        style.configure("TButton", padding=(8, 5))
        style.configure("Treeview", rowheight=27, font=("Segoe UI", 9), background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(13, 8), font=("Segoe UI", 10, "bold"))
        style.configure("TEntry", padding=5)
        style.configure("TCombobox", padding=5)

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=self.NAVY, height=105)
        header.pack(fill="x")
        header.pack_propagate(False)
        brand = tk.Frame(header, bg=self.NAVY)
        brand.pack(side="left", fill="y", padx=24, pady=14)
        ttk.Label(brand, text="QoO-X", style="Title.TLabel").pack(anchor="w")
        ttk.Label(brand, text="Application Quality Lab  •  AIORI-3 / PS-029", style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))
        self.status_pill = tk.Label(header, text="● NOT CONNECTED", bg="#334155", fg="white", font=("Segoe UI", 9, "bold"), padx=12, pady=8)
        self.status_pill.pack(side="right", padx=22, pady=32)

        note = tk.Frame(self.root, bg="#e8efff", padx=18, pady=10)
        note.pack(fill="x", padx=18, pady=(14, 8))
        tk.Label(note, text="MEASURE, DON’T GUESS", bg="#e8efff", fg="#1e40af", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(note, text="QoO-X controls one selected application at a time. It does not invent a QoO formula; blank metrics stay blank until measured or imported from the supplied testbed.", bg="#e8efff", fg="#334155", font=("Segoe UI", 9), wraplength=1100, justify="left").pack(anchor="w", pady=(2, 0))

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self.test_tab = ttk.Frame(self.notebook, padding=12)
        self.results_tab = ttk.Frame(self.notebook, padding=12)
        self.settings_tab = ttk.Frame(self.notebook, padding=12)
        self.help_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.test_tab, text="Single-App Test")
        self.notebook.add(self.results_tab, text="Results & Logs")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.help_tab, text="How to Use")
        self._build_test_tab()
        self._build_results_tab()
        self._build_settings_tab()
        self._build_help_tab()

    def _build_test_tab(self) -> None:
        outer = ttk.Frame(self.test_tab)
        outer.pack(fill="both", expand=True)
        left_shell = ttk.Frame(outer)
        left_shell.pack(side="left", fill="y", padx=(0, 12))
        left_canvas = tk.Canvas(left_shell, width=485, bg=self.BG, highlightthickness=0, borderwidth=0)
        left_scrollbar = ttk.Scrollbar(left_shell, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        left_canvas.pack(side="left", fill="y", expand=False)
        left_scrollbar.pack(side="right", fill="y")
        left = ttk.Frame(left_canvas)
        left_window = left_canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>", lambda _event: left_canvas.configure(scrollregion=left_canvas.bbox("all")))
        left_canvas.bind("<Configure>", lambda event: left_canvas.itemconfigure(left_window, width=event.width))
        left_canvas.bind("<MouseWheel>", lambda event: left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        left_canvas.bind("<Button-4>", lambda _event: left_canvas.yview_scroll(-1, "units"))
        left_canvas.bind("<Button-5>", lambda _event: left_canvas.yview_scroll(1, "units"))

        right = ttk.Frame(outer)
        right.pack(side="left", fill="both", expand=True)

        card = tk.Frame(left, bg="white", highlightbackground="#dbe3ef", highlightthickness=1, padx=15, pady=13)
        card.pack(fill="x", pady=(0, 10))
        ttk.Label(card, text="Experiment setup", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 12))

        self.api_url_var = tk.StringVar(value=self.config.get("api_base_url", DEFAULT_CONFIG["api_base_url"]))
        self.path_var = tk.StringVar(value=self.config.get("testbed_path", ""))
        self.app_var = tk.StringVar(value="DASH over TCP")
        self.scenario_var = tk.StringVar(value=self._scenario_label(self.scenarios[0]))
        self.qoo_profile_var = tk.StringVar(value="(detect active and record it)")
        self.control_mode_var = tk.StringVar(value=self.config.get("gateway_control_mode", DEFAULT_CONFIG["gateway_control_mode"]))
        self.gateway_profile_var = tk.StringVar(value="")
        self.command_var = tk.StringVar(value="")
        self.timeout_var = tk.StringVar(value=str(self.config.get("command_timeout_seconds", 600)))
        self.repeat_var = tk.StringVar(value=str(self.config.get("repeat_count", 1)))

        self._form_row(card, "Testbed API", self.api_url_var, width=35)
        api_buttons = ttk.Frame(card)
        api_buttons.pack(fill="x", pady=(1, 10))
        ttk.Button(api_buttons, text="Check connection", command=self._test_connection_async).pack(side="left")
        ttk.Button(api_buttons, text="Open control panel", command=lambda: self._open_url(self.config.get("control_panel_url", "http://localhost:8080"))).pack(side="left", padx=(6, 0))
        ttk.Label(card, text="Testbed repository folder", style="Muted.TLabel").pack(anchor="w")
        path_row = ttk.Frame(card)
        path_row.pack(fill="x", pady=(3, 10))
        ttk.Entry(path_row, textvariable=self.path_var, width=32).pack(side="left", fill="x", expand=True)
        ttk.Button(path_row, text="Browse", command=self._browse_path).pack(side="left", padx=(5, 0))

        self._combo_row(card, "Application workload", self.app_var, list(APPLICATIONS.keys()), self._on_app_changed)
        self._combo_row(card, "Network scenario", self.scenario_var, list(self.scenario_by_label.keys()))
        self.qoo_profile_combo = self._combo_row(card, "QoO profile", self.qoo_profile_var, ["(detect active and record it)"])
        self._combo_row(card, "Gateway control", self.control_mode_var, ["custom", "profile", "manual"], self._on_control_mode_changed)
        self.gateway_profile_combo = self._combo_row(card, "Existing gateway profile", self.gateway_profile_var, [""])
        ttk.Label(card, text="Workload command (review before running)", style="Muted.TLabel").pack(anchor="w", pady=(8, 2))
        ttk.Entry(card, textvariable=self.command_var, width=54).pack(fill="x")
        ttk.Label(card, text="Timeout (seconds)", style="Muted.TLabel").pack(anchor="w", pady=(8, 2))
        ttk.Entry(card, textvariable=self.timeout_var, width=12).pack(anchor="w")
        ttk.Label(card, text="Repeats per scenario (1–5)", style="Muted.TLabel").pack(anchor="w", pady=(8, 2))
        ttk.Entry(card, textvariable=self.repeat_var, width=12).pack(anchor="w")

        button_row = ttk.Frame(left)
        button_row.pack(fill="x", pady=(2, 8))
        self.run_button = ttk.Button(button_row, text="▶  Run selected test", style="Primary.TButton", command=self._run_selected)
        self.run_button.pack(fill="x", pady=(0, 6))
        self.all_button = ttk.Button(button_row, text="Run all 6 scenarios for this app", command=self._run_all)
        self.all_button.pack(fill="x", pady=(0, 6))
        ttk.Button(button_row, text="Refresh profile lists", command=self._refresh_profiles_async).pack(fill="x")
        ttk.Label(left, text="Important: tests can change network conditions.", style="Muted.TLabel", wraplength=310, justify="left").pack(anchor="w", pady=(5, 0))

        log_card = tk.Frame(right, bg="white", highlightbackground="#dbe3ef", highlightthickness=1, padx=12, pady=12)
        log_card.pack(fill="both", expand=True)
        log_head = ttk.Frame(log_card)
        log_head.pack(fill="x")
        ttk.Label(log_head, text="Live run log", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(log_head, text="Clear view", command=self._clear_log).pack(side="right")
        self.log_box = ScrolledText(log_card, wrap="word", font=("Consolas", 9), bg="#0f172a", fg="#e2e8f0", insertbackground="white", relief="flat", padx=11, pady=10)
        self.log_box.pack(fill="both", expand=True, pady=(10, 0))
        self.log_box.insert("end", "Welcome to QoO-X.\n1) Start the supplied QoO testbed.\n2) Check connection.\n3) Select ONE application and one scenario.\n4) Run it, then attach real telemetry values in Results & Logs.\n")
        self.log_box.configure(state="disabled")
        self._on_app_changed()
        self._on_control_mode_changed()

    def _form_row(self, parent, label, variable, width=32):
        ttk.Label(parent, text=label, style="Muted.TLabel").pack(anchor="w")
        ttk.Entry(parent, textvariable=variable, width=width).pack(fill="x", pady=(3, 9))

    def _combo_row(self, parent, label, variable, values, callback=None):
        ttk.Label(parent, text=label, style="Muted.TLabel").pack(anchor="w", pady=(4, 2))
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=48)
        combo.pack(fill="x", pady=(0, 4))
        if callback:
            combo.bind("<<ComboboxSelected>>", lambda _event: callback())
        return combo

    def _build_results_tab(self) -> None:
        head = ttk.Frame(self.results_tab)
        head.pack(fill="x", pady=(0, 8))
        ttk.Label(head, text="Recorded experiments", font=("Segoe UI", 13, "bold")).pack(side="left")
        ttk.Button(head, text="Refresh", command=self._load_results).pack(side="right", padx=(5, 0))
        ttk.Button(head, text="Export CSV…", command=self._export_csv).pack(side="right", padx=(5, 0))
        ttk.Button(head, text="Edit real measurements…", command=self._edit_selected_result).pack(side="right", padx=(5, 0))
        ttk.Button(head, text="Open log", command=self._open_selected_log).pack(side="right", padx=(5, 0))
        columns = ("id", "timestamp", "application", "scenario", "status", "qoo", "latency", "throughput", "app_metric")
        self.results_tree = ttk.Treeview(self.results_tab, columns=columns, show="headings", selectmode="browse")
        labels = {"id":"Experiment ID", "timestamp":"UTC time", "application":"Application", "scenario":"Scenario", "status":"Run status", "qoo":"QoO", "latency":"Latency ms", "throughput":"Mbps", "app_metric":"Application metric"}
        widths = {"id":125, "timestamp":140, "application":155, "scenario":125, "status":190, "qoo":65, "latency":85, "throughput":80, "app_metric":150}
        for col in columns:
            self.results_tree.heading(col, text=labels[col])
            self.results_tree.column(col, width=widths[col], minwidth=55, anchor="w")
        self.results_tree.pack(fill="both", expand=True)
        self.results_tree.bind("<Double-1>", lambda _event: self._edit_selected_result())
        ttk.Label(self.results_tab, text="A successful command does not automatically mean all metrics were captured. Empty cells mean 'not measured/imported yet', not zero.", style="Muted.TLabel", wraplength=1000).pack(anchor="w", pady=(9, 0))

    def _build_settings_tab(self) -> None:
        frame = ttk.Frame(self.settings_tab)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Integration settings", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(frame, text="The settings are stored in config.json on this computer. Nothing is sent elsewhere except local API requests you trigger.", style="Muted.TLabel", wraplength=960).pack(anchor="w", pady=(0, 12))

        self.control_url_var = tk.StringVar(value=self.config.get("control_panel_url", "http://localhost:8080"))
        self.grafana_url_var = tk.StringVar(value=self.config.get("grafana_url", "http://localhost:3000"))
        self.payload_keys_var = tk.StringVar(value=json.dumps(self.config.get("custom_payload_keys", DEFAULT_CONFIG["custom_payload_keys"]), separators=(",", ":")))
        self._form_row(frame, "Control panel URL", self.control_url_var, 60)
        self._form_row(frame, "Grafana URL", self.grafana_url_var, 60)
        ttk.Label(frame, text="POST /custom JSON key mapping (JSON object)").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.payload_keys_var).pack(fill="x", pady=(3, 5))
        ttk.Label(frame, text='Default: {"delay_ms":"delay_ms","jitter_ms":"jitter_ms","packet_loss_percent":"loss_percent"}', style="Muted.TLabel", wraplength=1000).pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="Important integration note", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 3))
        ttk.Label(frame, text="The upstream QoO testbed README documents POST /custom, but does not document the request-body field names. QoO-X uses the configurable mapping above. Verify it against the actual gateway route in the testbed source before collecting final results. If the API returns an error, the workload will not start and the failed attempt will be logged.", wraplength=1020, justify="left").pack(anchor="w")
        ttk.Button(frame, text="Save settings", style="Primary.TButton", command=self._save_config).pack(anchor="w", pady=(16, 0))

    def _build_help_tab(self) -> None:
        content = ScrolledText(self.help_tab, wrap="word", font=("Segoe UI", 10), bg="white", relief="flat", padx=18, pady=16)
        content.pack(fill="both", expand=True)
        help_text = """QOО-X QUICK START — PS-029

BEFORE YOU START
• Run the supplied QoO testbed first. QoO-X is a desktop controller/client, not a replacement for the supplied QoO scoring engine.
• For real measurements, use the actual gateway-routed path. A normal Internet speed test is not a substitute for the challenge testbed.
• The Linux/macOS workload commands need a working shell and the supplied repository's scripts. On Windows the app calls WSL for these shell scripts.

ONE EXPERIMENT
1. Keep the API URL at http://localhost:9000 unless your testbed uses another address.
2. Select the folder containing the supplied testbed repository.
3. Click Check connection and Refresh profile lists.
4. Select one workload (DASH over TCP is a good first automated test), one scenario and the mentor-approved QoO profile.
5. Select Custom shaping API only after you have confirmed the gateway's POST /custom request-body keys. Otherwise select Manual (apply scenario in control panel first), or choose an existing gateway profile that actually represents the intended impairment.
6. Review the command. Click Run selected test. Check the Live run log and exit code.
7. Open Results & Logs. If telemetry is available in Grafana/InfluxDB but not printed by the script, click Edit real measurements and type/import only the measured numbers. Do not invent values.
8. Repeat the same conditions for the other approved application profile/workload.

THE SIX DEFAULT SCENARIOS
S0 Baseline: 0 ms delay, 0 ms jitter, 0% packet loss.
S1 Low delay: 50 ms delay only.
S2 High delay: 100 ms delay only.
S3 Low jitter: 20 ms jitter only.
S4 High jitter: 50 ms jitter only.
S5 Packet loss: 1% packet loss only.
Values are starting points. Follow mentor approval and testbed-supported ranges.

INTERPRETATION
QoO-X never computes or estimates QoO scores. It calls the supplied QoO profile/scoring engine and records a score only if one is explicitly present in command output or entered from the actual telemetry. Keep raw logs for each experiment. Use identical scenario conditions when comparing profiles.

KNOWN LIMITS OF THIS VERSION
• Gateway custom-shaping payload fields are configurable because the README doesn't specify the body schema.
• DASH scripts may write metrics to telemetry/exports rather than print them. Blank metrics require importing the actual values from the testbed output.
• WebRTC requires a real sender/receiver browser session and is marked manual; bootstrapping the session alone is not a completed WebRTC measurement.
• The app does not install Docker, change operating-system routes, or alter global network settings automatically.

TROUBLESHOOTING
• API unreachable: start the testbed, then check http://localhost:9000/status.
• 'BYPASS' path: follow the upstream routing/WireGuard setup instructions before measuring.
• No new dashboard points: confirm traffic passes through gateway; inspect collector logs.
• API rejected /custom: inspect the gateway route and update the field mapping in Settings, or use a verified existing gateway profile.
• Workload non-zero exit: read the full log under data/logs/; the app records the failure rather than pretending it passed.

REFERENCE
Upstream testbed: https://github.com/cj-ike-kunze/ietf-126-hackathon-qoo
AIORI-3 guidelines: https://portal.aiori.in/aiori-3/hackathon-guideline/
"""
        content.insert("1.0", help_text)
        content.configure(state="disabled")

    def _set_status(self, label: str, tone: str = "muted") -> None:
        colors = {"muted": "#334155", "good": self.GREEN, "bad": self.RED, "warn": "#a16207"}
        self.status_pill.configure(text=f"● {label.upper()}", bg=colors.get(tone, "#334155"))

    def _append_log(self, message: str) -> None:
        if not hasattr(self, "log_box"):
            return
        self.log_box.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"\n[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _api(self) -> QoOTestbedClient:
        base = self.api_url_var.get().strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise ValueError("Testbed API must start with http:// or https://")
        return QoOTestbedClient(base, timeout=5)

    def _test_connection_async(self) -> None:
        if self.running:
            return
        self._set_status("Checking API…", "warn")
        base = self.api_url_var.get().strip().rstrip("/")
        threading.Thread(target=self._connection_worker, args=(base,), daemon=True).start()

    def _connection_worker(self, base: str) -> None:
        try:
            client = QoOTestbedClient(base, timeout=5)
            status = client.get_status()
            gateways = extract_names(client.get_gateway_profiles())
            qoo = extract_names(client.get_qoo_profiles())
            self.events.put(("connection_ok", {"status": status, "gateway_profiles": gateways, "qoo_profiles": qoo}))
        except Exception as exc:
            self.events.put(("connection_error", str(exc)))

    def _refresh_profiles_async(self) -> None:
        self._test_connection_async()

    def _process_connection_ok(self, data: dict) -> None:
        self.api_connected = True
        self.last_status = data["status"]
        self.gateway_profiles = data["gateway_profiles"]
        self.qoo_profiles = data["qoo_profiles"]
        self._set_status("Testbed connected", "good")
        self._append_log("Testbed API connection successful.")
        self._append_log("Gateway profiles: " + (", ".join(self.gateway_profiles) if self.gateway_profiles else "none detected"))
        self._append_log("QoO profiles: " + (", ".join(self.qoo_profiles) if self.qoo_profiles else "none detected"))
        qoo_values = ["(detect active and record it)"] + self.qoo_profiles
        self._set_combo_values("QoO profile", qoo_values)
        self._set_combo_values("Existing gateway profile", [""] + self.gateway_profiles)
        self._append_log("Status payload: " + json.dumps(self.last_status, ensure_ascii=False))

    def _set_combo_values(self, label: str, values: list[str]) -> None:
        for child in self.test_tab.winfo_children():
            pass
        # Keep direct widget references to the two profile comboboxes for updates.
        if label == "QoO profile" and hasattr(self, "qoo_profile_combo"):
            self.qoo_profile_combo.configure(values=values)
            if self.qoo_profile_var.get() not in values:
                self.qoo_profile_var.set(values[0])
        elif label == "Existing gateway profile" and hasattr(self, "gateway_profile_combo"):
            self.gateway_profile_combo.configure(values=values)
            if self.gateway_profile_var.get() not in values:
                self.gateway_profile_var.set(values[0])

    def _on_app_changed(self) -> None:
        app = self.app_var.get()
        if app in APPLICATIONS:
            self.command_var.set(default_command(app, self.path_var.get().strip()))
        if app == "WebRTC (manual workflow)":
            self._append_log("WebRTC uses sender/receiver browser workflow. Select DASH over TCP for your first automated end-to-end test.")

    def _on_control_mode_changed(self) -> None:
        mode = self.control_mode_var.get()
        if mode == "custom":
            self._append_log("Gateway control set to Custom shaping API. Confirm the request-body schema before use.")
        elif mode == "profile":
            self._append_log("Gateway control set to Existing gateway profile. Select a profile that actually matches the chosen scenario.")
        elif mode == "manual":
            self._append_log("Gateway control set to Manual. Apply the selected scenario in the supplied control panel before running.")

    def _browse_path(self) -> None:
        selected = filedialog.askdirectory(title="Select supplied QoO testbed repository")
        if selected:
            self.path_var.set(selected)
            self._on_app_changed()

    def _current_scenario(self) -> dict:
        return self.scenario_by_label[self.scenario_var.get()]

    def _run_selected(self) -> None:
        self._start_run(all_scenarios=False)

    def _run_all(self) -> None:
        if not messagebox.askyesno("Run all six scenarios?", "This will run the selected application six times and may change lab network conditions. Continue only if this is your isolated testbed."):
            return
        self._start_run(all_scenarios=True)

    def _start_run(self, all_scenarios: bool) -> None:
        if self.running:
            messagebox.showwarning("Experiment running", "Wait for the current run to finish before starting another.")
            return
        app_name = self.app_var.get()
        if app_name == "WebRTC (manual workflow)":
            messagebox.showinfo("WebRTC workflow", "WebRTC requires a live sender/receiver browser session. Use the supplied run-webrtc-demo.sh workflow and record the actual receiver stats. This button does not count a setup as a completed application test.")
            return
        try:
            api = self._api()
            timeout = int(self.timeout_var.get())
            if timeout < 1:
                raise ValueError("Timeout must be at least 1 second.")
            repeats = int(self.repeat_var.get())
            if not 1 <= repeats <= 5:
                raise ValueError("Repeat count must be between 1 and 5.")
            mapping = json.loads(self.payload_keys_var.get()) if hasattr(self, "payload_keys_var") else self.config.get("custom_payload_keys", DEFAULT_CONFIG["custom_payload_keys"])
            if not isinstance(mapping, dict):
                raise ValueError("Custom payload mapping must be a JSON object.")
        except (ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("Check settings", str(exc))
            return

        if self.control_mode_var.get() == "profile" and not self.gateway_profile_var.get().strip():
            messagebox.showerror("Gateway profile required", "Choose an existing gateway profile, or switch to Custom shaping API / Manual.")
            return
        mode = self.control_mode_var.get()
        if all_scenarios and mode != "custom":
            messagebox.showerror("Automatic sweep needs verified API shaping", "Run all six scenarios is available only with Custom shaping API after you verify the POST /custom JSON schema. In Manual/Existing profile mode, run one scenario at a time and change the impairment/profile before each run.")
            return
        if mode == "custom":
            if not messagebox.askyesno("Apply lab impairment", "QoO-X will send the selected delay/jitter/loss settings to POST /custom. Continue only after confirming the endpoint's expected JSON field names in the supplied gateway source."):
                return
        elif mode == "manual":
            scenario = self._current_scenario()
            confirmation = (
                "Before continuing, apply this scenario in the supplied testbed control panel:\n\n"
                f"{scenario['id']} — {scenario['name']}\n"
                f"Delay: {scenario['delay_ms']} ms\n"
                f"Jitter: {scenario['jitter_ms']} ms\n"
                f"Packet loss: {scenario['packet_loss_percent']}%\n\n"
                "Have you applied and verified these settings?"
            )
            if not messagebox.askyesno("Confirm manual impairment", confirmation):
                return
        elif mode == "profile":
            if not messagebox.askyesno("Confirm gateway profile", f"QoO-X will switch to gateway profile '{self.gateway_profile_var.get()}'. Make sure this existing profile implements the selected scenario '{self._current_scenario()['id']} {self._current_scenario()['name']}'. Continue?"):
                return

        command = self.command_var.get().strip()
        if not command:
            messagebox.showerror("Command required", "The workload command is empty. Select an application and testbed folder.")
            return
        path_issue = validate_testbed_path(self.path_var.get().strip(), app_name)
        if path_issue:
            messagebox.showerror("Testbed folder / shell problem", path_issue)
            return
        self._save_config_silently()
        scenarios = self.scenarios if all_scenarios else [self._current_scenario()]
        args = {
            "api": api,
            "app_name": app_name,
            "scenarios": scenarios,
            "qoo_profile": self.qoo_profile_var.get(),
            "testbed_path": self.path_var.get().strip(),
            "command": command,
            "control_mode": self.control_mode_var.get(),
            "gateway_profile": self.gateway_profile_var.get().strip(),
            "key_map": mapping,
            "timeout": timeout,
            "repeats": repeats,
        }
        self.running = True
        self.run_button.configure(state="disabled")
        self.all_button.configure(state="disabled")
        self._set_status("Experiment running", "warn")
        self._append_log(f"Starting {'all six scenarios' if all_scenarios else 'selected scenario'} for {app_name}.")
        threading.Thread(target=self._run_worker, kwargs=args, daemon=True).start()

    def _save_config_silently(self) -> None:
        try:
            self.config.update({
                "api_base_url": self.api_url_var.get().strip().rstrip("/"),
                "testbed_path": self.path_var.get().strip(),
                "gateway_control_mode": self.control_mode_var.get(),
                "command_timeout_seconds": int(self.timeout_var.get()),
                "repeat_count": int(self.repeat_var.get()),
                "control_panel_url": getattr(self, "control_url_var", tk.StringVar(value=DEFAULT_CONFIG["control_panel_url"])).get(),
                "grafana_url": getattr(self, "grafana_url_var", tk.StringVar(value=DEFAULT_CONFIG["grafana_url"])).get(),
            })
            self.config["custom_payload_keys"] = json.loads(self.payload_keys_var.get())
            CONFIG_PATH.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    def _run_worker(self, **args) -> None:
        try:
            total = len(args["scenarios"]) * args["repeats"]
            run_index = 0
            for repeat_index in range(1, args["repeats"] + 1):
                for scenario in args["scenarios"]:
                    run_index += 1
                    self.events.put(("log", f"\n=== Run {run_index}/{total} | repeat {repeat_index}/{args['repeats']} | {scenario['id']} / {scenario['name']} ==="))
                    try:
                        row = self.runner.run_one(
                            api=args["api"], app_name=args["app_name"], scenario=scenario,
                            qoo_profile=args["qoo_profile"], testbed_path=args["testbed_path"],
                            command=args["command"], control_mode=args["control_mode"],
                            gateway_profile=args["gateway_profile"], key_map=args["key_map"],
                            timeout_seconds=args["timeout"],
                            log_callback=lambda message: self.events.put(("log", message)),
                        )
                    except Exception as exc:
                        self.events.put(("log", f"Unhandled run error: {exc}"))
                        continue
                    row["repeat_index"] = repeat_index
                    self.store.update(row["experiment_id"], {"repeat_index": repeat_index})
                    self.events.put(("row_done", row))
        finally:
            self.events.put(("run_finished", None))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "connection_ok":
                    self._process_connection_ok(payload)
                elif kind == "connection_error":
                    self.api_connected = False
                    self._set_status("API unavailable", "bad")
                    self._append_log("Connection failed: " + str(payload))
                elif kind == "log":
                    self._append_log(str(payload))
                elif kind == "row_done":
                    self._load_results()
                elif kind == "run_finished":
                    self.running = False
                    self.run_button.configure(state="normal")
                    self.all_button.configure(state="normal")
                    self._set_status("Testbed connected" if self.api_connected else "Check API", "good" if self.api_connected else "warn")
                    self._append_log("Run sequence finished. Review the status and measured fields under Results & Logs.")
        except queue.Empty:
            pass
        self.root.after(150, self._poll_events)

    def _load_results(self) -> None:
        if not hasattr(self, "results_tree"):
            return
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        for row in self.store.rows():
            app_metric = ""
            if row.get("application_metric_name") or row.get("application_metric_value"):
                app_metric = f"{row.get('application_metric_name','')}: {row.get('application_metric_value','')}"
            values = (
                row.get("experiment_id", ""), row.get("timestamp_utc", ""), row.get("application", ""),
                f"{row.get('scenario_id','')} {row.get('scenario_name','')}", row.get("run_status", ""),
                row.get("qoo_score", ""), row.get("latency_ms", ""), row.get("throughput_mbps", ""), app_metric,
            )
            self.results_tree.insert("", "end", iid=row.get("experiment_id", None), values=values)

    def _selected_result(self) -> dict | None:
        selected = self.results_tree.selection()
        if not selected:
            messagebox.showinfo("Select a result", "Select an experiment row first.")
            return None
        experiment_id = selected[0]
        return next((row for row in self.store.rows() if row.get("experiment_id") == experiment_id), None)

    def _open_selected_log(self) -> None:
        row = self._selected_result()
        if row and row.get("log_path"):
            path = Path(row["log_path"])
            if path.exists():
                try:
                    if sys.platform.startswith("win"):
                        os.startfile(str(path))  # type: ignore[attr-defined]
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", str(path)])
                    else:
                        subprocess.Popen(["xdg-open", str(path)])
                except OSError as exc:
                    messagebox.showerror("Could not open log", str(exc))
            else:
                messagebox.showerror("Log missing", f"Log file not found: {path}")

    def _edit_selected_result(self) -> None:
        row = self._selected_result()
        if not row:
            return
        popup = tk.Toplevel(self.root)
        popup.title("Attach real measurements")
        popup.geometry("470x440")
        popup.transient(self.root)
        popup.grab_set()
        frame = ttk.Frame(popup, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"Experiment {row.get('experiment_id')}", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Enter only values observed in testbed telemetry/output. Leave unknown values blank.", wraplength=420, style="Muted.TLabel").pack(anchor="w", pady=(5, 12))
        vars_ = {}
        fields = [
            ("QoO score (from supplied engine)", "qoo_score"),
            ("Latency (ms)", "latency_ms"),
            ("Throughput (Mbps)", "throughput_mbps"),
            ("Measured packet loss (%)", "packet_loss_percent_measured"),
            ("Measured jitter (ms)", "jitter_ms_measured"),
            ("Application metric name", "application_metric_name"),
            ("Application metric value", "application_metric_value"),
            ("Measurement source / notes", "measurement_source"),
        ]
        for label, key in fields:
            ttk.Label(frame, text=label).pack(anchor="w", pady=(4, 0))
            var = tk.StringVar(value=row.get(key, ""))
            vars_[key] = var
            ttk.Entry(frame, textvariable=var).pack(fill="x", pady=(2, 1))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        def save() -> None:
            changes = {}
            for _, key in fields:
                value = vars_[key].get().strip()
                if key not in ("application_metric_name", "measurement_source") and value:
                    try:
                        float(value)
                    except ValueError:
                        messagebox.showerror("Invalid number", f"{key} must be numeric or blank.", parent=popup)
                        return
                changes[key] = value
            self.store.update(row["experiment_id"], changes)
            self._load_results()
            popup.destroy()
        ttk.Button(buttons, text="Save measurements", style="Primary.TButton", command=save).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=popup.destroy).pack(side="left", padx=(8, 0))

    def _export_csv(self) -> None:
        destination = filedialog.asksaveasfilename(title="Export QoO-X results", defaultextension=".csv", filetypes=[("CSV file", "*.csv")], initialfile=f"qoo_x_results_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
        if not destination:
            return
        try:
            shutil.copy2(self.store.csv_path, destination)
            messagebox.showinfo("Export complete", f"Results exported to:\n{destination}")
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))

    @staticmethod
    def _open_url(url: str) -> None:
        if url and url.startswith(("http://", "https://")):
            webbrowser.open(url)


def main() -> None:
    root = tk.Tk()
    app = QoOXDesktop(root)
    root.mainloop()


if __name__ == "__main__":
    main()
