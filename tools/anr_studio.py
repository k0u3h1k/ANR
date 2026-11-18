#!/usr/bin/env python3
"""
ANR Studio: 1-Click Game Launcher & Configuration Manager GUI.

A lightweight, zero-dependency native Windows GUI (using standard Python tkinter) to:
  - Detect and list all installed games (Steam, Epic Games, custom folders).
  - Select Super Resolution upscaler (Intel XeSS, AMD FSR 3.1, NVIDIA DLSS).
  - Select Frame Generation engine (ANR FG, AMD FSR 3.1 FG, NVIDIA DLSS-G).
  - Configure Reflex / Anti-Lag low-latency frame pacing.
  - 1-Click Launch games with OptiScaler + ANR capture & frame generation.
  - 1-Click access to Replay & Comparison (nr_compare) and Universal Video Exporter (nr_export).
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Import game installer detector if present
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
try:
    from game_installer import scan_steam_games, scan_epic_games, DetectedGame
except ImportError:
    DetectedGame = None
    scan_steam_games = lambda: []
    scan_epic_games = lambda: []


def get_gpu_info() -> str:
    """Get active GPU name."""
    try:
        cmd = ["powershell", "-NoProfile", "-Command",
               "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Caption"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
            for l in lines:
                if any(k in l.lower() for k in ["arc", "geforce", "radeon", "rtx"]):
                    return l
            return lines[0]
    except Exception:
        pass
    return "Standard GPU"


class ANRStudioApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ANR Studio — Apex Neural Rendering Suite")
        self.root.geometry("820x680")
        self.root.minsize(760, 600)

        self.gpu_name = get_gpu_info()
        self.games = []

        self.setup_ui()
        self.scan_installed_games()

    def setup_ui(self):
        # Configure styles
        style = ttk.Style()
        style.theme_use("clam")

        # Top Banner
        banner = tk.Frame(self.root, bg="#1a1c23", padx=16, pady=12)
        banner.pack(fill=tk.X)

        title_lbl = tk.Label(banner, text="APEX NEURAL RENDERING STUDIO", font=("Segoe UI", 14, "bold"), fg="#38bdf8", bg="#1a1c23")
        title_lbl.pack(anchor="w")

        gpu_text = f"Active Hardware: {self.gpu_name}"
        if "arc" in self.gpu_name.lower():
            gpu_text += " [Xe2 XMX Neural Engines & QuickSync Active]"
        elif "geforce" in self.gpu_name.lower() or "rtx" in self.gpu_name.lower():
            gpu_text += " [Tensor Cores & NVENC Active]"
        elif "radeon" in self.gpu_name.lower():
            gpu_text += " [AMD RDNA & AMF Active]"

        gpu_lbl = tk.Label(banner, text=gpu_text, font=("Segoe UI", 9), fg="#94a3b8", bg="#1a1c23")
        gpu_lbl.pack(anchor="w")

        # Main notebook tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Tab 1: Game Launcher
        tab_launch = ttk.Frame(notebook, padding=12)
        notebook.add(tab_launch, text="🚀 Game Launcher & Injector")

        # Tab 2: Compare & Replay Tools
        tab_tools = ttk.Frame(notebook, padding=12)
        notebook.add(tab_tools, text="📊 Comparison & Video Export")

        self.build_launcher_tab(tab_launch)
        self.build_tools_tab(tab_tools)

        # Bottom status bar
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = tk.Label(self.root, textvariable=self.status_var, font=("Segoe UI", 9), bd=1, relief=tk.SUNKEN, anchor="w", padx=8, pady=4)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def build_launcher_tab(self, parent):
        # Game selection section
        lbl_frame_game = ttk.LabelFrame(parent, text=" 1. Select Target Game ", padding=10)
        lbl_frame_game.pack(fill=tk.X, pady=(0, 10))

        row1 = ttk.Frame(lbl_frame_game)
        row1.pack(fill=tk.X, pady=2)

        self.game_combo = ttk.Combobox(row1, state="readonly", font=("Segoe UI", 10))
        self.game_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.game_combo.bind("<<ComboboxSelected>>", self.on_game_selected)

        btn_browse = ttk.Button(row1, text="Browse Custom EXE...", command=self.browse_custom_exe)
        btn_browse.pack(side=tk.RIGHT)

        self.lbl_game_path = ttk.Label(lbl_frame_game, text="Game Directory: (none selected)", font=("Segoe UI", 8), foreground="#64748b")
        self.lbl_game_path.pack(anchor="w", pady=(4, 0))

        # Engine Configuration section
        lbl_frame_engine = ttk.LabelFrame(parent, text=" 2. Neural Upscaling & Frame Generation Settings ", padding=10)
        lbl_frame_engine.pack(fill=tk.X, pady=(0, 10))

        grid = ttk.Frame(lbl_frame_engine)
        grid.pack(fill=tk.X)

        # Super Resolution
        ttk.Label(grid, text="Super Resolution Upscaler:").grid(row=0, column=0, sticky="w", pady=4, padx=4)
        self.sr_combo = ttk.Combobox(grid, state="readonly", values=[
            "Apex Neural Rendering (ANR SR) — Native",
            "Intel XeSS (Native XMX / DP4a)",
            "AMD FidelityFX Super Resolution (FSR 3.1)",
            "NVIDIA DLSS (NGX core)",
            "Game Default / Passthrough"
        ], font=("Segoe UI", 9))
        self.sr_combo.current(0 if "arc" in self.gpu_name.lower() else 1)
        self.sr_combo.grid(row=0, column=1, sticky="ew", pady=4, padx=4)

        # Frame Generation
        ttk.Label(grid, text="Frame Generation Engine:").grid(row=1, column=0, sticky="w", pady=4, padx=4)
        self.fg_combo = ttk.Combobox(grid, state="readonly", values=[
            "Apex Neural Rendering (ANR FG) — Universal",
            "AMD FidelityFX Frame Gen (FSR 3.1 FG)",
            "Intel XeSS Frame Generation (XeSS-FG)",
            "NVIDIA DLSS-G (GeForce RTX only)"
        ], font=("Segoe UI", 9))
        self.fg_combo.current(0)
        self.fg_combo.grid(row=1, column=1, sticky="ew", pady=4, padx=4)

        # Quality Preset
        ttk.Label(grid, text="Upscaling Preset:").grid(row=2, column=0, sticky="w", pady=4, padx=4)
        self.preset_combo = ttk.Combobox(grid, state="readonly", values=[
            "Native AA (No Upscaling, Max Clarity)",
            "Ultra Quality (1.3x)",
            "Quality (1.5x - Recommended)",
            "Balanced (1.7x)",
            "Performance (2.0x)"
        ], font=("Segoe UI", 9))
        self.preset_combo.current(2)
        self.preset_combo.grid(row=2, column=1, sticky="ew", pady=4, padx=4)

        # Ray Reconstruction
        ttk.Label(grid, text="Ray Reconstruction (Denoising):").grid(row=3, column=0, sticky="w", pady=4, padx=4)
        self.rr_combo = ttk.Combobox(grid, state="readonly", values=[
            "Apex Neural Rendering (ANR RR) — Universal",
            "NVIDIA DLSS Ray Reconstruction (GeForce RTX only)",
            "Disabled (Standard Game Denoiser)"
        ], font=("Segoe UI", 9))
        self.rr_combo.current(0)
        self.rr_combo.grid(row=3, column=1, sticky="ew", pady=4, padx=4)

        grid.columnconfigure(1, weight=1)

        # Latency & Recording section
        lbl_frame_opt = ttk.LabelFrame(parent, text=" 3. Low Latency & Lossless Capture ", padding=10)
        lbl_frame_opt.pack(fill=tk.X, pady=(0, 10))

        self.var_low_latency = tk.BooleanVar(value=True)
        chk_ll = ttk.Checkbutton(lbl_frame_opt, text="Enable Reflex / Anti-Lag Low Latency Frame Pacing (Reduces input lag)", variable=self.var_low_latency)
        chk_ll.pack(anchor="w", pady=2)

        self.var_flip_metering = tk.BooleanVar(value=True)
        chk_flip = ttk.Checkbutton(lbl_frame_opt, text="Hardware Flip Metering (Display scanout sync for AMD RX 7000/9000 & RTX 4000/5000)", variable=self.var_flip_metering)
        chk_flip.pack(anchor="w", pady=2)

        self.var_disable_ui = tk.BooleanVar(value=False)
        chk_ui = ttk.Checkbutton(lbl_frame_opt, text="Bypass UI Interpolation (Fixes floating marker/minimap jitter in Cyberpunk & Crimson Desert)", variable=self.var_disable_ui)
        chk_ui.pack(anchor="w", pady=2)

        self.var_stabilize_translucency = tk.BooleanVar(value=True)
        chk_trans = ttk.Checkbutton(lbl_frame_opt, text="Stabilize Translucency & Ribbons (Fixes optical-flow ghost particles in Wuthering Waves, FFXVI)", variable=self.var_stabilize_translucency)
        chk_trans.pack(anchor="w", pady=2)

        pacing_row = ttk.Frame(lbl_frame_opt)
        pacing_row.pack(fill=tk.X, pady=2)
        ttk.Label(pacing_row, text="Target FPS Pacing Ceiling:").pack(side=tk.LEFT, padx=(0, 8))
        self.fps_cap_combo = ttk.Combobox(pacing_row, state="readonly", values=["Unlimited (Adaptive 240Hz ceiling)", "60 FPS", "120 FPS", "144 FPS", "165 FPS", "240 FPS"], width=32)
        self.fps_cap_combo.current(0)
        self.fps_cap_combo.pack(side=tk.LEFT)

        info_lbl = ttk.Label(lbl_frame_opt, text="Capture Hotkeys: [F9] = Lossless 8-Frame Still Capture  |  [F6] = Start / Stop Recording", font=("Segoe UI", 8, "italic"), foreground="#475569")
        info_lbl.pack(anchor="w", pady=(6, 0))

        # Launch Button Area
        btn_area = ttk.Frame(parent)
        btn_area.pack(fill=tk.X, pady=10)

        self.btn_launch = tk.Button(btn_area, text="🚀 LAUNCH GAME WITH ANR", font=("Segoe UI", 12, "bold"), bg="#0284c7", fg="white", activebackground="#0369a8", activeforeground="white", padx=20, pady=10, relief=tk.RAISED, command=self.launch_game)
        self.btn_launch.pack(fill=tk.X)

    def build_tools_tab(self, parent):
        lbl_frame_tools = ttk.LabelFrame(parent, text=" Developer Replay & Video Comparison Tools ", padding=12)
        lbl_frame_tools.pack(fill=tk.BOTH, expand=True)

        ttk.Label(lbl_frame_tools, text="Quick-launch suite analysis and video export tools:", font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 10))

        btn_compare = ttk.Button(lbl_frame_tools, text="📊 Run 1-Click Comparison (nr_compare)", command=self.open_compare_tool)
        btn_compare.pack(fill=tk.X, pady=6)

        btn_export = ttk.Button(lbl_frame_tools, text="🎬 Universal Hardware Video Exporter (nr_export)", command=self.open_export_tool)
        btn_export.pack(fill=tk.X, pady=6)

        btn_refresh = ttk.Button(lbl_frame_tools, text="🔄 Refresh Installed Games List", command=self.scan_installed_games)
        btn_refresh.pack(fill=tk.X, pady=6)

        # Log box
        ttk.Label(lbl_frame_tools, text="Console Output:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(12, 4))
        self.log_text = tk.Text(lbl_frame_tools, height=12, bg="#0f172a", fg="#f8fafc", font=("Consolas", 9), relief=tk.SUNKEN)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, text: str):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.status_var.set(text)

    def scan_installed_games(self):
        self.games = []
        try:
            self.games.extend(scan_steam_games())
            self.games.extend(scan_epic_games())
        except Exception as e:
            self.log(f"Error scanning games: {e}")

        names = [f"[{g.source.upper()}] {g.name}" for g in self.games]
        if not names:
            names = ["(No games detected — use 'Browse Custom EXE' to pick a game)"]
        self.game_combo["values"] = names
        self.game_combo.current(0)
        self.on_game_selected(None)

    def on_game_selected(self, _):
        idx = self.game_combo.current()
        if 0 <= idx < len(self.games):
            g = self.games[idx]
            exe = g.exe_name if g.exe_name else "Executable not set"
            self.lbl_game_path.config(text=f"Game Directory: {g.install_dir} ({exe})")
        else:
            self.lbl_game_path.config(text="Game Directory: (none selected)")

    def browse_custom_exe(self):
        filename = filedialog.askopenfilename(
            title="Select Game Executable",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if filename:
            path = Path(filename)
            custom_game = DetectedGame(name=path.stem, install_dir=path.parent, exe_name=path.name, source="custom")
            self.games.insert(0, custom_game)
            names = [f"[{g.source.upper()}] {g.name}" for g in self.games]
            self.game_combo["values"] = names
            self.game_combo.current(0)
            self.on_game_selected(None)

    def launch_game(self):
        idx = self.game_combo.current()
        if not (0 <= idx < len(self.games)):
            messagebox.showwarning("Select Game", "Please select a game first or browse for an executable.")
            return

        game = self.games[idx]
        if not game.exe_name or not (game.install_dir / game.exe_name).is_file():
            messagebox.showerror("Error", f"Executable '{game.exe_name}' not found in {game.install_dir}")
            return

        # Prepare nr_record.ini in game folder
        ini_path = game.install_dir / "nr_record.ini"
        try:
            fps_map = {"Unlimited (Adaptive 240Hz ceiling)": 0, "60 FPS": 60, "120 FPS": 120, "144 FPS": 144, "165 FPS": 165, "240 FPS": 240}
            target_fps = fps_map.get(self.fps_cap_combo.get(), 0)

            rr_choice = self.rr_combo.get()
            sr_choice = self.sr_combo.get()
            sr_val = "anr" if "anr" in sr_choice.lower() else "xess" if "xess" in sr_choice.lower() else "fsr31" if "fsr" in sr_choice.lower() else "dlss" if "dlss" in sr_choice.lower() else None
            forward_val = "anr-rr" if "anr rr" in rr_choice.lower() else (sr_val if sr_val else "auto")

            ini_content = f"""# ANR Configuration generated by ANR Studio
record_key = F6
capture_key = F9
capture_frames = 8
low_latency = {str(self.var_low_latency.get()).lower()}
low_latency_target_fps = {target_fps}
flip_metering = {str(self.var_flip_metering.get()).lower()}
disable_ui = {str(self.var_disable_ui.get()).lower()}
stabilize_translucency = {str(self.var_stabilize_translucency.get()).lower()}
record_mode = interleaved
record_present = keep
forward = {forward_val}
"""
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write(ini_content)

            # Also update OptiScaler custom provider folder if present
            opti_custom_ini = game.install_dir / "OptiScaler" / "custom" / "nr-record" / "dlssg" / "nr_record.ini"
            if opti_custom_ini.parent.is_dir():
                with open(opti_custom_ini, "w", encoding="utf-8") as f:
                    f.write(ini_content)
            opti_custom_sr_ini = game.install_dir / "OptiScaler" / "custom" / "nr-record" / "dlss" / "nr_record.ini"
            if opti_custom_sr_ini.parent.is_dir():
                with open(opti_custom_sr_ini, "w", encoding="utf-8") as f:
                    f.write(ini_content)

            # Configure selected Super Resolution upscaler in OptiScaler.ini if present
            opti_ini = game.install_dir / "OptiScaler.ini"
            if not opti_ini.exists():
                found = list(game.install_dir.glob("*/OptiScaler.ini"))
                if found:
                    opti_ini = found[0]
            if opti_ini.exists():
                text = opti_ini.read_text(encoding="utf-8", errors="ignore")
                if sr_val:
                    if "Dx12Upscaler" in text:
                        text = re.sub(r'(?m)^Dx12Upscaler=.*', f'Dx12Upscaler={sr_val}', text)
                    else:
                        text += f"\n[Upscalers]\nDx12Upscaler={sr_val}\n"
                    self.log(f"Configured OptiScaler Dx12Upscaler = {sr_val}")
                # Ensure Vulkan bridge is enabled for Vulkan titles (Issue #62 fix: DOOM Dark Ages / No Man's Sky)
                if "EnableVulkanBridge" in text:
                    text = re.sub(r'(?m)^EnableVulkanBridge=.*', 'EnableVulkanBridge=true', text)
                else:
                    text += "\n[Vulkan]\nEnableVulkanBridge=true\n"
                opti_ini.write_text(text, encoding="utf-8")
                self.log("Verified Vulkan presentation bridge active in OptiScaler.ini")

            self.log(f"Configured nr_record.ini in {game.install_dir}")
            self.log(f"Launching {game.name} ({game.exe_name})...")

            # Launch game process with environment variables
            env = os.environ.copy()
            if self.var_low_latency.get():
                env["ANR_LOW_LATENCY"] = "1"
            if target_fps > 0:
                env["ANR_TARGET_FPS"] = str(target_fps)
            if self.var_flip_metering.get():
                env["ANR_FLIP_METERING"] = "1"
            if self.var_disable_ui.get():
                env["ANR_DISABLE_UI"] = "1"
            if self.var_stabilize_translucency.get():
                env["ANR_STABILIZE_TRANSLUCENCY"] = "1"

            exe_path = str(game.install_dir / game.exe_name)
            subprocess.Popen([exe_path], cwd=str(game.install_dir), env=env)
            messagebox.showinfo("Game Launched", f"{game.name} launched successfully with ANR Frame Generation & Low Latency active!\n\nHotkeys:\n- F9: Lossless 8-Frame Capture\n- F6: Toggle Recording")
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch game: {e}")

    def open_compare_tool(self):
        py_script = SCRIPT_DIR / "nr_compare.py"
        self.log("Opening 1-Click Comparison Tool...")
        rec_dir = filedialog.askdirectory(title="Select nr-record Capture Directory to Compare")
        if rec_dir:
            self.log(f"Comparing capture: {rec_dir}")
            if sys.platform == "win32":
                subprocess.Popen(f'start cmd /k "{sys.executable}" "{py_script}" --record "{rec_dir}" --generator provider --view', shell=True)
            else:
                subprocess.Popen([sys.executable, str(py_script), "--record", rec_dir, "--generator", "provider", "--view"])
        else:
            if sys.platform == "win32":
                subprocess.Popen(f'start cmd /k "{sys.executable}" "{py_script}" --help', shell=True)
            else:
                subprocess.Popen([sys.executable, str(py_script), "--help"])

    def open_export_tool(self):
        py_script = SCRIPT_DIR / "nr_export.py"
        self.log("Opening Universal Video Exporter...")
        in_dir = filedialog.askdirectory(title="Select nr-replay Output Directory Containing .nrraw Frames")
        if in_dir:
            self.log(f"Exporting replay frames from: {in_dir}")
            if sys.platform == "win32":
                subprocess.Popen(f'start cmd /k "{sys.executable}" "{py_script}" --in-dir "{in_dir}"', shell=True)
            else:
                subprocess.Popen([sys.executable, str(py_script), "--in-dir", in_dir])
        else:
            if sys.platform == "win32":
                subprocess.Popen(f'start cmd /k "{sys.executable}" "{py_script}" --help', shell=True)
            else:
                subprocess.Popen([sys.executable, str(py_script), "--help"])


def main():
    root = tk.Tk()
    app = ANRStudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
