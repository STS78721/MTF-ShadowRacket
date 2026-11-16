"""MTF ShadowRacket — Mario Tennis Fever PC Recompiled Launcher & Setup Hub."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk


APP_TITLE = "MTF ShadowRacket"
APP_SUBTITLE = "Mario Tennis Fever  ·  Native Windows PC Recompilation"
DEFAULT_VERSION = "Alpha 0.1.0"

# Championship Turf & Optic Yellow-Green palette (matches runtime/ui/theme.h THEME_TENNIS)
C_BG_DEEP = "#08120C"
C_BG = "#0C1A11"
C_PANEL = "#122418"
C_RAISED = "#183021"
C_RAISED_HOVER = "#1E3E29"
C_LINE = "#3A6648"
C_LINE_BRIGHT = "#5C926D"
C_TEXT = "#F6FAF4"
C_TEXT_SOFT = "#BEDAC4"
C_TEXT_DIM = "#86A890"
C_OPTIC = "#CCF22A"
C_OPTIC_HOVER = "#DAFA48"
C_OPTIC_DOWN = "#A8CE1E"
C_OPTIC_TEXT = "#0C1A11"
C_OK = "#5BC98A"
C_WARN = "#ECA046"
C_BAD = "#F47064"


def resource_base() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def read_app_version() -> str:
    for base in (app_dir(), resource_base(), resource_base().parent):
        for name in ("VERSION", "mtf_version.txt"):
            p = base / name
            if p.is_file():
                txt = p.read_text(encoding="utf-8", errors="ignore").strip()
                if txt:
                    return txt.splitlines()[0].strip()
    return DEFAULT_VERSION


def find_icon_ico() -> Path | None:
    for p in (
        app_dir() / "mtf.ico",
        app_dir() / "assets" / "mtf.ico",
        app_dir() / "runtime" / "mtf.ico",
        resource_base() / "assets" / "mtf.ico",
        resource_base() / "mtf.ico",
        app_dir().parent / "runtime" / "mtf.ico",
    ):
        if p.is_file():
            return p
    return None


def find_icon_png() -> Path | None:
    for p in (
        app_dir() / "runtime" / "mtf.png",
        resource_base() / "assets" / "mtf.png",
        resource_base() / "mtf.png",
        app_dir().parent / "runtime" / "mtf.png",
    ):
        if p.is_file():
            return p
    return None


def find_ball_png() -> Path | None:
    for p in (
        app_dir() / "runtime" / "mtf_ball.png",
        resource_base() / "assets" / "mtf_ball.png",
        resource_base() / "mtf_ball.png",
        app_dir().parent / "runtime" / "mtf_ball.png",
    ):
        if p.is_file():
            return p
    return None


def set_windows_app_id() -> None:
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SteelTemple.MTF.ShadowRacket")
        except Exception:
            pass


def parse_ini(path: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path or not path.is_file():
        return values
    try:
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = raw.strip()
            if not s or s.startswith(("#", ";", "[")) or "=" not in s:
                continue
            k, v = s.split("=", 1)
            values[k.strip().lower()] = v.split("#", 1)[0].split(";", 1)[0].strip()
    except OSError:
        pass
    return values


INI_SECTIONS: list[tuple[str, set[str]]] = [
    ("graphics", {"resolution", "aniso"}),
    (
        "display",
        {
            "fullscreen",
            "window_size",
            "output_res",
            "vk_present",
            "upscaler",
            "sharpness",
            "fg_mode",
            "perf_overlay",
            "color_preset",
        },
    ),
    ("frame rate", {"fps_limit"}),
    ("input", {"pad_layout", "stick_deadzone"}),
    ("audio", {"volume"}),
    ("performance", {"pipe_skip", "pipe_prebuild"}),
]


def save_ini_settings(path: Path, updates: dict[str, str]) -> None:
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True) if path.is_file() else []
    for key, value in updates.items():
        k_low = key.casefold()
        sec = next((s for s, keys in INI_SECTIONS if k_low in keys), "")
        replaced = False
        if sec:
            active = ""
            for i, line in enumerate(lines):
                s = line.strip()
                if s.startswith("[") and s.endswith("]"):
                    active = s[1:-1].casefold()
                    continue
                if active != sec or s.startswith(("#", ";")) or "=" not in line:
                    continue
                if line.split("=", 1)[0].strip().casefold() == k_low:
                    lines[i] = f"{key} = {value}\n"
                    replaced = True
                    break
            if not replaced:
                sec_idx = next(
                    (i for i, l in enumerate(lines) if l.strip().casefold() == f"[{sec}]"),
                    -1,
                )
                if sec_idx >= 0:
                    lines.insert(sec_idx + 1, f"{key} = {value}\n")
                else:
                    if lines and lines[-1].strip():
                        lines.append("\n")
                    lines.append(f"[{sec}]\n")
                    lines.append(f"{key} = {value}\n")
        else:
            for i, line in enumerate(lines):
                s = line.lstrip()
                if s.startswith(("#", ";", "[")) or "=" not in line:
                    continue
                if line.split("=", 1)[0].strip().casefold() == k_low:
                    lines[i] = f"{key} = {value}\n"
                    replaced = True
                    break
            if not replaced:
                lines.append(f"{key} = {value}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".ini.tmp")
    tmp.write_text("".join(lines), encoding="utf-8")
    tmp.replace(path)


def clean_default_settings() -> dict[str, str]:
    """Safe, hardware-agnostic baseline defaults matching runtime/cfg.c."""
    return {
        "resolution": "original",
        "output_res": "1920x1080",
        "window_size": "1920x1080",
        "fullscreen": "0",
        "upscaler": "fsr",
        "sharpness": "80",
        "fg_mode": "off",
        "vk_present": "mailbox",
        "fps_limit": "60",
        "perf_overlay": "off",
        "aniso": "16",
        "color_preset": "default",
        "pad_layout": "auto",
        "stick_deadzone": "8",
        "volume": "100",
        "pipe_skip": "any",
        "pipe_prebuild": "1",
    }


def detect_gpu_name() -> str:
    if os.name != "nt":
        return "Vulkan Host GPU"
    try:
        r = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress",
            ],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout.strip())
            names = [data] if isinstance(data, str) else list(data)
            names = [n for n in names if n]
            if names:
                names.sort(key=lambda n: (not any(k in n.lower() for k in ("nvidia", "geforce", "amd", "radeon")), n))
                return names[0]
    except Exception:
        pass
    return "Vulkan GPU (Auto)"


def resolve_root_dir() -> Path:
    root = app_dir()
    if (root / "mtf.exe").is_file() or (root / "tools" / "build_game.py").is_file():
        return root
    if (root.parent / "tools" / "build_game.py").is_file():
        return root.parent
    return root


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_expected_mtf(root: Path) -> dict[str, str]:
    for cand in (
        root / "tools" / "data" / "expected-mtf111.json",
        resource_base() / "tools" / "data" / "expected-mtf111.json",
        root.parent / "tools" / "data" / "expected-mtf111.json",
    ):
        if cand.is_file():
            try:
                return json.loads(cand.read_text(encoding="utf-8")).get("exefs_sha256", {})
            except Exception:
                pass
    return {
        "main": "3557c30e0a18e15aedd62f94be66b64de9e31632ed6da250c2f8c2c0ec271171",
        "main.npdm": "6171756a59bf3322620b7f8fe907b51cfe925b14109248cec40cdaea11b62945",
        "rtld": "f3a05703aadc0eabecb1af71522e9be358d797f2b4489028d09c41fe220ebd7c",
        "sdk": "e8a2c5852508f330663d8ad639d4c20609e36c1bc6d5fcf7b01cd4bd3e0428f",
        "subsdk0": "3cf8c4dbaccaf1ed35295b64eb7698863577ca9b8d88e5ef13d360fa713b0d8e",
    }


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]


def create_shortcut(game_dir: Path, name: str = "MTF ShadowRacket") -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Windows shortcuts are only available on Windows."
    try:
        desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
        lnk = desktop / f"{name}.lnk"
        target = game_dir / ("MTFLauncher.exe" if (game_dir / "MTFLauncher.exe").is_file() else "mtf.exe")
        ico = find_icon_ico() or target
        ps = (
            "$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{str(lnk).replace(chr(39), chr(39)*2)}'); "
            f"$s.TargetPath = '{str(target).replace(chr(39), chr(39)*2)}'; "
            f"$s.WorkingDirectory = '{str(game_dir).replace(chr(39), chr(39)*2)}'; "
            f"$s.IconLocation = '{str(ico).replace(chr(39), chr(39)*2)},0'; "
            "$s.Description = 'Play Mario Tennis Fever PC (MTF ShadowRacket)'; "
            "$s.Save()"
        )
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode == 0 and lnk.is_file():
            return True, str(lnk)
        return False, r.stderr.strip() or "Could not create desktop shortcut."
    except Exception as exc:
        return False, str(exc)


class MTFLauncherApp(tk.Tk):
    def __init__(self, initial_tab: str = "play", shot_path: str = "") -> None:
        super().__init__()
        self.root_dir = resolve_root_dir()
        self.version = read_app_version()
        self.shot_path = shot_path
        self.gpu_name = "Checking GPU..."

        self.title(f"{APP_TITLE} {self.version} — Mario Tennis Fever PC")
        self.geometry("1040x700")
        self.minsize(920, 620)
        self.configure(bg=C_BG)

        self._icon_photo = None
        self._hero_photo = None
        self._ball_photo = None
        self._apply_window_icon()
        self._configure_ttk_styles()

        self.vars: dict[str, tk.StringVar] = {}
        defaults = clean_default_settings()
        for k, v in defaults.items():
            self.vars[k] = tk.StringVar(value=v)

        self.dump_root_var = tk.StringVar()
        self.exefs_var = tk.StringVar()
        self.romfs_var = tk.StringVar()
        self.shortcut_var = tk.BooleanVar(value=True)
        self.setup_status_var = tk.StringVar(value="Select your Mario Tennis Fever 1.1.1 ExeFS & RomFS folders to build mtf.exe locally.")
        self.setup_running = False
        self.current_tab = initial_tab

        self._build_layout()
        self._load_ini_into_vars()
        self._refresh_status_cards()
        self.select_tab(initial_tab)

        threading.Thread(target=self._probe_gpu_async, daemon=True).start()
        if self.shot_path:
            self.after(450, self._capture_shot_and_exit)

    def _apply_window_icon(self) -> None:
        ico = find_icon_ico()
        if ico and os.name == "nt":
            try:
                self.iconbitmap(default=str(ico))
            except Exception:
                pass
        png = find_icon_png() or ico
        if png and png.is_file():
            try:
                im = Image.open(png).convert("RGBA")
                self._icon_photo = ImageTk.PhotoImage(im.resize((48, 48), Image.Resampling.LANCZOS))
                self._hero_photo = ImageTk.PhotoImage(im.resize((72, 72), Image.Resampling.LANCZOS))
                self.iconphoto(True, self._icon_photo)
            except Exception:
                pass
        ball = find_ball_png()
        if ball and ball.is_file():
            try:
                bim = Image.open(ball).convert("RGBA")
                self._ball_photo = ImageTk.PhotoImage(bim.resize((82, 82), Image.Resampling.LANCZOS))
            except Exception:
                pass

    def _configure_ttk_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("MTF.TCombobox", fieldbackground=C_RAISED, background=C_RAISED, foreground=C_TEXT,
                        bordercolor=C_LINE, arrowcolor=C_OPTIC, selectbackground=C_RAISED_HOVER,
                        selectforeground=C_OPTIC, padding=5)
        style.map("MTF.TCombobox", fieldbackground=[("readonly", C_RAISED)], foreground=[("readonly", C_TEXT)])
        style.configure("MTF.Horizontal.TProgressbar", troughcolor=C_BG_DEEP, background=C_OPTIC,
                        bordercolor=C_LINE, lightcolor=C_OPTIC, darkcolor=C_OPTIC_DOWN, thickness=12)

    def _probe_gpu_async(self) -> None:
        name = detect_gpu_name()
        self.after(0, lambda: self._set_gpu_label(name))

    def _set_gpu_label(self, name: str) -> None:
        self.gpu_name = name
        if hasattr(self, "gpu_label"):
            self.gpu_label.configure(text=name)

    def _ini_path(self) -> Path:
        return self.root_dir / "mtf.ini"

    def _exe_path(self) -> Path:
        return self.root_dir / ("mtf.exe" if os.name == "nt" else "mtf")

    def _mods_dir(self) -> Path:
        return self.root_dir / "mods"

    def _profile_dir(self) -> Path:
        return self.root_dir / "profile"

    def _logs_dir(self) -> Path:
        return self.root_dir / "logs"

    def _load_ini_into_vars(self) -> None:
        defaults = clean_default_settings()
        ini = parse_ini(self._ini_path())
        for k, d in defaults.items():
            self.vars[k].set(ini.get(k, d))

    def _build_layout(self) -> None:
        # Top Championship Court Banner
        banner = tk.Canvas(self, height=116, bg=C_BG_DEEP, highlightthickness=0)
        banner.pack(fill=tk.X, side=tk.TOP)
        self.banner = banner
        banner.bind("<Configure>", self._draw_banner)

        # Navigation strip
        nav = tk.Frame(self, bg=C_PANEL, height=46, highlightbackground=C_LINE, highlightthickness=1)
        nav.pack(fill=tk.X, side=tk.TOP)
        nav.pack_propagate(False)
        self.nav_buttons: dict[str, tk.Button] = {}
        tabs = [
            ("play", "PLAY"),
            ("setup", "SETUP FROM DUMP"),
            ("settings", "GRAPHICS & INPUT"),
            ("mods", "MODS & SAVES"),
        ]
        for key, label in tabs:
            btn = tk.Button(
                nav,
                text=label,
                command=lambda k=key: self.select_tab(k),
                font=("Segoe UI", 9, "bold"),
                bg=C_PANEL,
                fg=C_TEXT_SOFT,
                activebackground=C_RAISED_HOVER,
                activeforeground=C_OPTIC,
                bd=0,
                padx=18,
                pady=10,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT)
            self.nav_buttons[key] = btn

        self.profile_badge = tk.Label(
            nav,
            text="",
            font=("Segoe UI", 8, "bold"),
            bg=C_RAISED,
            fg=C_OPTIC,
            padx=10,
            pady=4,
        )
        self.profile_badge.pack(side=tk.RIGHT, padx=14, pady=9)

        # Content container
        self.body = tk.Frame(self, bg=C_BG)
        self.body.pack(fill=tk.BOTH, expand=True, padx=22, pady=18)

        self.pages: dict[str, tk.Frame] = {
            "play": self._build_play_page(),
            "setup": self._build_setup_page(),
            "settings": self._build_settings_page(),
            "mods": self._build_mods_page(),
        }

        # Footer strip
        foot = tk.Frame(self, bg=C_BG_DEEP, height=34)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        tk.Label(
            foot,
            text=f"MTF ShadowRacket  ·  {self.version}  ·  No copyrighted game assets included",
            font=("Segoe UI", 8),
            fg=C_TEXT_DIM,
            bg=C_BG_DEEP,
        ).pack(side=tk.LEFT, padx=16)
        tk.Label(
            foot,
            text=f"Folder: {self.root_dir}",
            font=("Segoe UI", 8),
            fg=C_TEXT_DIM,
            bg=C_BG_DEEP,
        ).pack(side=tk.RIGHT, padx=16)

    def _draw_banner(self, _event=None) -> None:
        c = self.banner
        c.delete("all")
        w = max(900, c.winfo_width())
        h = c.winfo_height()
        # Turf court stripes
        stripe_w = 56
        for i in range(0, w + stripe_w, stripe_w):
            col = "#0C1B12" if (i // stripe_w) % 2 == 0 else "#0E2116"
            c.create_rectangle(i, 0, i + stripe_w, h, fill=col, outline="")
        # Diagonal court baseline & net accent lines
        c.create_line(0, h - 18, w, h - 18, fill=C_LINE, width=2)
        c.create_line(w - 310, 0, w - 210, h, fill=C_LINE_BRIGHT, width=2)
        c.create_line(w - 190, 0, w - 90, h, fill=C_OPTIC, width=2)

        # Crisp 3D tennis ball emblem on right
        bx, by = w - 110, 56
        if self._ball_photo is not None:
            c.create_oval(bx - 30, by + 28, bx + 30, by + 40, fill="#050D08", outline="")
            c.create_image(bx, by, image=self._ball_photo)

        x_text = 26
        if self._hero_photo is not None:
            c.create_image(62, 58, image=self._hero_photo)
            x_text = 116
        c.create_text(x_text, 38, anchor="w", text=APP_TITLE, font=("Segoe UI", 22, "bold"), fill=C_TEXT)
        c.create_text(
            x_text + 2,
            70,
            anchor="w",
            text=f"{APP_SUBTITLE}  ·  {self.version}",
            font=("Segoe UI", 10),
            fill=C_OPTIC,
        )

    def select_tab(self, key: str) -> None:
        self.current_tab = key
        for k, page in self.pages.items():
            if k == key:
                page.pack(fill=tk.BOTH, expand=True)
            else:
                page.pack_forget()
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(bg=C_RAISED_HOVER, fg=C_OPTIC)
            else:
                btn.configure(bg=C_PANEL, fg=C_TEXT_SOFT)

    def _card(self, parent: tk.Misc, title: str, padx: int = 16, pady: int = 14) -> tk.Frame:
        outer = tk.Frame(parent, bg=C_PANEL, highlightbackground=C_LINE, highlightthickness=1, padx=padx, pady=pady)
        if title:
            tk.Label(outer, text=title, font=("Segoe UI", 10, "bold"), fg=C_OPTIC, bg=C_PANEL).pack(anchor="w", pady=(0, 8))
        return outer

    def _accent_btn(self, parent: tk.Misc, text: str, cmd, width: int = 18) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            font=("Segoe UI", 10, "bold"),
            bg=C_OPTIC,
            fg=C_OPTIC_TEXT,
            activebackground=C_OPTIC_HOVER,
            activeforeground=C_OPTIC_TEXT,
            bd=0,
            padx=16,
            pady=9,
            width=width,
            cursor="hand2",
        )

    def _plain_btn(self, parent: tk.Misc, text: str, cmd, width: int = 16) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            font=("Segoe UI", 9, "bold"),
            bg=C_RAISED,
            fg=C_TEXT,
            activebackground=C_RAISED_HOVER,
            activeforeground=C_OPTIC,
            bd=0,
            padx=14,
            pady=8,
            width=width,
            cursor="hand2",
        )

    def _build_play_page(self) -> tk.Frame:
        page = tk.Frame(self.body, bg=C_BG)

        top = self._card(page, "MATCH READINESS")
        top.pack(fill=tk.X, pady=(0, 14))
        self.build_state_lbl = tk.Label(top, text="", font=("Segoe UI", 11, "bold"), fg=C_TEXT, bg=C_PANEL)
        self.build_state_lbl.pack(anchor="w")
        self.build_hint_lbl = tk.Label(top, text="", font=("Segoe UI", 9), fg=C_TEXT_SOFT, bg=C_PANEL, wraplength=880, justify="left")
        self.build_hint_lbl.pack(anchor="w", pady=(4, 12))

        cta_row = tk.Frame(top, bg=C_PANEL)
        cta_row.pack(fill=tk.X)
        self.play_btn = self._accent_btn(cta_row, "PLAY MARIO TENNIS FEVER", self.launch_game, width=26)
        self.play_btn.pack(side=tk.LEFT)
        self.goto_setup_btn = self._plain_btn(cta_row, "OPEN DUMP SETUP", lambda: self.select_tab("setup"), width=20)
        self.goto_setup_btn.pack(side=tk.LEFT, padx=(10, 0))
        self._plain_btn(cta_row, "CREATE DESKTOP SHORTCUT", self.on_create_shortcut, width=24).pack(side=tk.RIGHT)

        grid = tk.Frame(page, bg=C_BG)
        grid.pack(fill=tk.BOTH, expand=True)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        c1 = self._card(grid, "ACTIVE HARDWARE & PROFILE")
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self._kv_row(c1, "Graphics Adapter", "", attr="gpu_label")
        self._kv_row(c1, "Config File", "", attr="ini_state_label")
        self._kv_row(c1, "Internal Resolution", "", attr="res_summary_label")
        self._kv_row(c1, "Display / Upscaler", "", attr="upscaler_summary_label")
        self._kv_row(c1, "Frame Generation", "", attr="fg_summary_label")

        c2 = self._card(grid, "CLEAN CLIENT DEFAULTS")
        c2.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        notes = [
            ("Zero-Config Baseline", "Starts cleanly at 1920x1080 Windowed, Original internal (~960p), FSR sharpness 80, Frame Gen Off, 60 FPS."),
            ("Internal Scaling Ready", "Supports Original (~960p), 720p, 900p, 1080p, and 1440p — switch cleanly anytime before launch or in-game (F1)."),
            ("No Personal Settings Bundled", "Your mtf.ini and saves stay strictly local on your PC; updates never overwrite them."),
            ("Controls", "Supports Xbox, DualSense, Nintendo Switch / Switch 2 Pro controllers, plus Keyboard."),
        ]
        for head, body in notes:
            tk.Label(c2, text=head, font=("Segoe UI", 9, "bold"), fg=C_TEXT, bg=C_PANEL).pack(anchor="w", pady=(2, 0))
            tk.Label(c2, text=body, font=("Segoe UI", 8), fg=C_TEXT_DIM, bg=C_PANEL, wraplength=410, justify="left").pack(anchor="w", pady=(1, 6))

        return page

    def _kv_row(self, parent: tk.Misc, key: str, value: str, attr: str) -> None:
        row = tk.Frame(parent, bg=C_PANEL)
        row.pack(fill=tk.X, pady=4)
        tk.Label(row, text=key, font=("Segoe UI", 9), fg=C_TEXT_DIM, bg=C_PANEL).pack(side=tk.LEFT)
        lbl = tk.Label(row, text=value, font=("Segoe UI", 9, "bold"), fg=C_TEXT, bg=C_PANEL)
        lbl.pack(side=tk.RIGHT)
        setattr(self, attr, lbl)

    def _build_setup_page(self) -> tk.Frame:
        page = tk.Frame(self.body, bg=C_BG)

        card = self._card(page, "ONE-STEP SETUP FROM YOUR MARIO TENNIS FEVER 1.1.1 DUMP")
        card.pack(fill=tk.X, pady=(0, 12))
        tk.Label(
            card,
            text="No copyrighted game data is shipped with MTF ShadowRacket. Select your dumped Switch 2 ExeFS and RomFS folders "
            "(or a single dump folder containing both) to verify hashes, pack RomFS, lift ARM64 modules, and compile mtf.exe locally.",
            font=("Segoe UI", 9),
            fg=C_TEXT_SOFT,
            bg=C_PANEL,
            wraplength=920,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        self._path_picker(card, "Dump Folder (auto-detects exefs + romfs):", self.dump_root_var, self._pick_dump_root)
        self._path_picker(card, "ExeFS Folder (main, rtld, sdk, subsdk0):", self.exefs_var, self._pick_exefs)
        self._path_picker(card, "RomFS Folder (raw dump or romfs_packed):", self.romfs_var, self._pick_romfs)

        opt_row = tk.Frame(card, bg=C_PANEL)
        opt_row.pack(fill=tk.X, pady=(8, 6))
        tk.Checkbutton(
            opt_row,
            text="Create 'MTF ShadowRacket' Desktop shortcut after build",
            variable=self.shortcut_var,
            bg=C_PANEL,
            fg=C_TEXT,
            activebackground=C_PANEL,
            activeforeground=C_OPTIC,
            selectcolor=C_BG_DEEP,
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT)
        self.build_btn = self._accent_btn(opt_row, "VERIFY & BUILD MTF.EXE", self.start_dump_setup, width=24)
        self.build_btn.pack(side=tk.RIGHT)

        prog_card = self._card(page, "BUILD PROGRESS & LOG")
        prog_card.pack(fill=tk.BOTH, expand=True)
        tk.Label(prog_card, textvariable=self.setup_status_var, font=("Segoe UI", 9, "bold"), fg=C_TEXT, bg=C_PANEL).pack(anchor="w", pady=(0, 6))
        self.setup_prog = ttk.Progressbar(prog_card, style="MTF.Horizontal.TProgressbar", maximum=100, value=0)
        self.setup_prog.pack(fill=tk.X, pady=(0, 8))
        self.setup_log = tk.Text(
            prog_card,
            height=11,
            bg=C_BG_DEEP,
            fg=C_TEXT_SOFT,
            insertbackground=C_OPTIC,
            relief=tk.FLAT,
            font=("Consolas", 9),
        )
        self.setup_log.pack(fill=tk.BOTH, expand=True)
        return page

    def _path_picker(self, parent: tk.Misc, label: str, var: tk.StringVar, cmd) -> None:
        row = tk.Frame(parent, bg=C_PANEL)
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text=label, width=38, anchor="w", font=("Segoe UI", 9), fg=C_TEXT_DIM, bg=C_PANEL).pack(side=tk.LEFT)
        tk.Entry(row, textvariable=var, bg=C_BG_DEEP, fg=C_TEXT, insertbackground=C_OPTIC, relief=tk.FLAT,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8), ipady=5)
        self._plain_btn(row, "Browse...", cmd, width=10).pack(side=tk.RIGHT)

    def _pick_dump_root(self) -> None:
        d = filedialog.askdirectory(title="Select Mario Tennis Fever Dump Root Folder")
        if not d:
            return
        self.dump_root_var.set(d)
        p = Path(d)
        if (p / "exefs").is_dir():
            self.exefs_var.set(str(p / "exefs"))
        if (p / "romfs_packed").is_dir():
            self.romfs_var.set(str(p / "romfs_packed"))
        elif (p / "romfs").is_dir():
            self.romfs_var.set(str(p / "romfs"))

    def _pick_exefs(self) -> None:
        d = filedialog.askdirectory(title="Select ExeFS Folder (main, main.npdm, rtld, sdk, subsdk0)")
        if d:
            self.exefs_var.set(d)

    def _pick_romfs(self) -> None:
        d = filedialog.askdirectory(title="Select RomFS or Packed RomFS Folder")
        if d:
            self.romfs_var.set(d)

    def _build_settings_page(self) -> tk.Frame:
        page = tk.Frame(self.body, bg=C_BG)

        cols = tk.Frame(page, bg=C_BG)
        cols.pack(fill=tk.BOTH, expand=True)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        left = self._card(cols, "DISPLAY & RESOLUTION")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self._combo_row(left, "Internal Resolution", "resolution", ["original", "720", "900", "1080", "1440"],
                        hint="original = 1706x960 (default). Higher values use more GPU fillrate.")
        self._combo_row(left, "Output / Window Size", "output_res",
                        ["1280x720", "1600x900", "1920x1080", "2560x1440", "3840x2160"])
        self._combo_row(left, "Window Mode", "fullscreen", ["0", "1"], hint="0 = Windowed, 1 = Fullscreen")
        self._combo_row(left, "Upscaler", "upscaler", ["fsr", "bilinear", "off", "smrs"])
        self._combo_row(left, "FSR Sharpness (0-100)", "sharpness", ["0", "40", "60", "80", "90", "100"])
        self._combo_row(left, "V-Sync / Present", "vk_present", ["mailbox", "fifo", "immediate"])

        right = self._card(cols, "PERFORMANCE, COLOR & INPUT")
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self._combo_row(right, "Frame Generation", "fg_mode", ["off", "msm_fg", "fsr3_fg", "xefg"])
        self._combo_row(right, "FPS Limit", "fps_limit", ["60", "30"])
        self._combo_row(right, "Color Preset", "color_preset", ["default", "vivid", "clarity"])
        self._combo_row(right, "Perf Overlay", "perf_overlay", ["off", "fps", "full"])
        self._combo_row(right, "Anisotropic Filtering", "aniso", ["game", "4", "8", "16"])
        self._combo_row(right, "Controller Button Layout", "pad_layout", ["auto", "nintendo", "xbox", "xbox_prompts"])

        bar = tk.Frame(page, bg=C_PANEL, highlightbackground=C_LINE, highlightthickness=1, padx=16, pady=12)
        bar.pack(fill=tk.X, pady=(12, 0))
        self._plain_btn(bar, "RESET TO DEFAULT PROFILE", self.on_reset_defaults, width=25).pack(side=tk.LEFT)
        self._accent_btn(bar, "SAVE SETTINGS", self.on_save_settings, width=18).pack(side=tk.RIGHT)
        self._plain_btn(bar, "RELOAD", self._reload_settings_ui, width=12).pack(side=tk.RIGHT, padx=(0, 10))
        return page

    def _combo_row(self, parent: tk.Misc, label: str, key: str, values: list[str], hint: str = "") -> None:
        wrap = tk.Frame(parent, bg=C_PANEL)
        wrap.pack(fill=tk.X, pady=4)
        top = tk.Frame(wrap, bg=C_PANEL)
        top.pack(fill=tk.X)
        tk.Label(top, text=label, font=("Segoe UI", 9, "bold"), fg=C_TEXT, bg=C_PANEL).pack(side=tk.LEFT)
        cb = ttk.Combobox(top, textvariable=self.vars[key], values=values, state="readonly", style="MTF.TCombobox", width=18)
        cb.pack(side=tk.RIGHT)
        if hint:
            tk.Label(wrap, text=hint, font=("Segoe UI", 8), fg=C_TEXT_DIM, bg=C_PANEL).pack(anchor="w")

    def _build_mods_page(self) -> tk.Frame:
        page = tk.Frame(self.body, bg=C_BG)

        c_top = self._card(page, "GAME & DATA FOLDERS")
        c_top.pack(fill=tk.X, pady=(0, 12))
        row = tk.Frame(c_top, bg=C_PANEL)
        row.pack(fill=tk.X)
        self._plain_btn(row, "Game Folder", lambda: open_folder(self.root_dir), width=16).pack(side=tk.LEFT)
        self._plain_btn(row, "Saves / Profile", lambda: open_folder(self._profile_dir()), width=16).pack(side=tk.LEFT, padx=8)
        self._plain_btn(row, "Mods Folder", lambda: open_folder(self._mods_dir()), width=16).pack(side=tk.LEFT)
        self._plain_btn(row, "Logs Folder", lambda: open_folder(self._logs_dir()), width=16).pack(side=tk.LEFT, padx=8)

        c_bak = self._card(page, "SAVE BACKUP VAULT")
        c_bak.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            c_bak,
            text="Create a timestamped snapshot of your profile/save folder before installing updates or testing mods.",
            font=("Segoe UI", 9),
            fg=C_TEXT_SOFT,
            bg=C_PANEL,
        ).pack(anchor="w", pady=(0, 8))
        self.bak_list = tk.Listbox(c_bak, bg=C_BG_DEEP, fg=C_TEXT, selectbackground=C_RAISED_HOVER,
                                   selectforeground=C_OPTIC, highlightthickness=1, highlightbackground=C_LINE,
                                   font=("Consolas", 9), activestyle="none")
        self.bak_list.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        brow = tk.Frame(c_bak, bg=C_PANEL)
        brow.pack(fill=tk.X)
        self._accent_btn(brow, "CREATE SAVE SNAPSHOT", self.on_create_backup, width=22).pack(side=tk.LEFT)
        self._plain_btn(brow, "REFRESH LIST", self._refresh_backups, width=14).pack(side=tk.RIGHT)
        self._refresh_backups()
        return page

    def _refresh_backups(self) -> None:
        self.bak_list.delete(0, tk.END)
        bdir = self._profile_dir() / "backups"
        if bdir.is_dir():
            snaps = sorted((p.name for p in bdir.iterdir() if p.is_dir()), reverse=True)
            for s in snaps:
                self.bak_list.insert(tk.END, s)
        if self.bak_list.size() == 0:
            self.bak_list.insert(tk.END, "No save snapshots yet.")

    def on_create_backup(self) -> None:
        save_dir = self._profile_dir() / "save"
        if not save_dir.is_dir() or not any(save_dir.iterdir()):
            messagebox.showinfo(APP_TITLE, "No save data found yet under profile/save.", parent=self)
            return
        stamp = datetime.now().strftime("save_%Y%m%d_%H%M%S")
        dst = self._profile_dir() / "backups" / stamp
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(save_dir, dst)
        self._refresh_backups()
        messagebox.showinfo(APP_TITLE, f"Created save backup:\n{dst}", parent=self)

    def _refresh_status_cards(self) -> None:
        exe = self._exe_path()
        ready = exe.is_file()
        ini_exists = self._ini_path().is_file()

        if ready:
            self.build_state_lbl.configure(text="Ready for Match Play  (mtf.exe found)", fg=C_OK)
            self.build_hint_lbl.configure(text=f"Executable: {exe}. Press PLAY below to launch Mario Tennis Fever natively.")
            self.play_btn.configure(state=tk.NORMAL)
        else:
            self.build_state_lbl.configure(text="Setup Required  (no game files included)", fg=C_WARN)
            self.build_hint_lbl.configure(
                text="Open SETUP FROM DUMP to point MTF ShadowRacket at your dumped Mario Tennis Fever 1.1.1 ExeFS & RomFS folders."
            )
            self.play_btn.configure(state=tk.DISABLED)

        if ini_exists:
            self.profile_badge.configure(text="CUSTOM mtf.ini ACTIVE")
            self.ini_state_label.configure(text="mtf.ini (custom)", fg=C_OPTIC)
        else:
            self.profile_badge.configure(text="DEFAULT PROFILE ACTIVE")
            self.ini_state_label.configure(text="Clean Defaults (no mtf.ini)", fg=C_OK)

        self.res_summary_label.configure(text=self.vars["resolution"].get())
        self.upscaler_summary_label.configure(text=f"{self.vars['output_res'].get()} · {self.vars['upscaler'].get().upper()}")
        self.fg_summary_label.configure(text=self.vars["fg_mode"].get())

    def _reload_settings_ui(self) -> None:
        self._load_ini_into_vars()
        self._refresh_status_cards()

    def on_save_settings(self) -> None:
        updates = {k: self.vars[k].get().strip() for k in clean_default_settings()}
        if updates["resolution"] == "original":
            # Ensure output window size also stays synchronized if left untouched
            updates["window_size"] = updates["output_res"]
        else:
            updates["window_size"] = updates["output_res"]
        save_ini_settings(self._ini_path(), updates)
        self._refresh_status_cards()
        messagebox.showinfo(APP_TITLE, f"Saved settings to {self._ini_path().name}.", parent=self)

    def on_reset_defaults(self) -> None:
        if self._ini_path().is_file():
            try:
                self._ini_path().unlink()
            except OSError as exc:
                messagebox.showerror(APP_TITLE, f"Could not delete mtf.ini: {exc}", parent=self)
                return
        self._load_ini_into_vars()
        self._refresh_status_cards()
        messagebox.showinfo(
            APP_TITLE,
            "Restored the clean Zero-Config Default Profile (removed custom mtf.ini).",
            parent=self,
        )

    def on_create_shortcut(self) -> None:
        ok, info = create_shortcut(self.root_dir)
        if ok:
            messagebox.showinfo(APP_TITLE, f"Created Desktop shortcut:\n{info}", parent=self)
        else:
            messagebox.showwarning(APP_TITLE, info, parent=self)

    def launch_game(self) -> None:
        exe = self._exe_path()
        if not exe.is_file():
            self.select_tab("setup")
            return
        try:
            subprocess.Popen([str(exe)], cwd=str(self.root_dir))
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Failed to start {exe.name}:\n{exc}", parent=self)

    def _log_setup(self, msg: str) -> None:
        self.setup_log.insert(tk.END, msg.rstrip() + "\n")
        self.setup_log.see(tk.END)

    def start_dump_setup(self) -> None:
        if self.setup_running:
            return
        exefs = Path(self.exefs_var.get().strip())
        romfs = Path(self.romfs_var.get().strip())
        if not exefs.is_dir() or not romfs.is_dir():
            messagebox.showwarning(APP_TITLE, "Please select both ExeFS and RomFS folders first.", parent=self)
            return
        self.setup_running = True
        self.build_btn.configure(state=tk.DISABLED)
        self.setup_log.delete("1.0", tk.END)
        self.setup_prog.configure(value=5)
        threading.Thread(target=self._run_setup_worker, args=(exefs, romfs), daemon=True).start()

    def _find_setup_python(self) -> Path:
        for cand in (
            self.root_dir / "python" / "python.exe",
            self.root_dir / "setup" / "python" / "python.exe",
            self.root_dir / ".venv" / "Scripts" / "python.exe",
        ):
            if cand.is_file():
                return cand
        return Path(sys.executable)

    def _run_step(self, cmd: list[str], env: dict[str, str], pct_start: int, pct_end: int) -> None:
        self.after(0, lambda: self._log_setup("+ " + " ".join(cmd)))
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.root_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert proc.stdout is not None
        lines = 0
        for line in proc.stdout:
            lines += 1
            text = line.rstrip()
            prog = min(pct_end, pct_start + int((pct_end - pct_start) * min(1.0, lines / 60.0)))
            self.after(0, lambda t=text, p=prog: (self._log_setup(t), self.setup_prog.configure(value=p)))
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"Step failed with exit code {rc}: {' '.join(cmd[:3])}")

    def _run_setup_worker(self, exefs: Path, romfs: Path) -> None:
        try:
            self.after(0, lambda: self.setup_status_var.set("1/4 Verifying Mario Tennis Fever 1.1.1 ExeFS hashes..."))
            expected = load_expected_mtf(self.root_dir)
            for fname, want in sorted(expected.items()):
                fpath = exefs / fname
                if not fpath.is_file():
                    raise RuntimeError(f"Missing ExeFS file: {fpath}")
                got = sha256_file(fpath)
                if got != want:
                    raise RuntimeError(f"SHA-256 mismatch for {fname}: got {got[:12]}..., expected {want[:12]}... "
                                       "(Mario Tennis Fever 1.1.1 is required).")
            self.after(0, lambda: (self._log_setup("ExeFS SHA-256 verification passed (5/5 files matched)."),
                                   self.setup_prog.configure(value=18)))

            py = self._find_setup_python()
            env = dict(os.environ)
            for d in (self.root_dir / "python", self.root_dir / "llvm" / "bin", self.root_dir / "bin"):
                if d.is_dir():
                    env["PATH"] = str(d) + os.pathsep + env.get("PATH", "")

            # Step 2: RomFS pack or use already packed folder
            packed_romfs = self.root_dir / "romfs_packed"
            if (romfs / "index.json").is_file() and (romfs / "romfs.bin").is_file():
                packed_romfs = romfs
                self.after(0, lambda: (self._log_setup(f"Using pre-packed RomFS at {romfs}"),
                                       self.setup_prog.configure(value=40)))
            elif (packed_romfs / "index.json").is_file() and (packed_romfs / "romfs.bin").is_file():
                self.after(0, lambda: (self._log_setup(f"Using existing packed RomFS at {packed_romfs}"),
                                       self.setup_prog.configure(value=40)))
            else:
                self.after(0, lambda: self.setup_status_var.set("2/4 Packing Mario Tennis Fever RomFS..."))
                packer = self.root_dir / "tools" / "mtf_pack_romfs.py"
                self._run_step([str(py), str(packer), "--dir", str(romfs), "--out", str(packed_romfs)], env, 20, 42)

            # Step 3: Lift ExeFS ARM64 -> C
            gen_dir = self.root_dir / "work" / "generated" / "mtf111"
            if (gen_dir / "layout.json").is_file():
                self.after(0, lambda: (self._log_setup(f"Reusing existing lifted C in {gen_dir}"),
                                       self.setup_prog.configure(value=62)))
            else:
                self.after(0, lambda: self.setup_status_var.set("3/4 Lifting ARM64 code to native C..."))
                gen_script = self.root_dir / "recomp" / "gen.py"
                patches = self.root_dir / "recomp" / "patches-mtf111.txt"
                self._run_step(
                    [str(py), str(gen_script), "--exefs", str(exefs), "--out", str(gen_dir), "--patches", str(patches)],
                    env,
                    44,
                    66,
                )

            # Step 4: Compile & link mtf.exe into clean work/build/mtf111 then place finished runtime files at root
            self.after(0, lambda: self.setup_status_var.set("4/4 Compiling & linking mtf.exe..."))
            build_script = self.root_dir / "tools" / "build_game.py"
            build_out = self.root_dir / "work" / "build" / "mtf111"
            build_out.mkdir(parents=True, exist_ok=True)
            cmd = [
                str(py),
                str(build_script),
                "--version",
                "mtf111",
                "--gen",
                str(gen_dir),
                "--out",
                str(build_out),
                "--exefs",
                str(exefs),
                "--romfs",
                str(packed_romfs),
                "--profile",
                str(self._profile_dir()),
            ]
            rt_lib = self.root_dir / "runtime" / "libmtfrt.a"
            if rt_lib.is_file():
                cmd += ["--runtime", str(self.root_dir / "runtime"), "--runtime-lib", str(rt_lib)]
            llvm_dir = self.root_dir / "llvm"
            if llvm_dir.is_dir():
                cmd += ["--toolchain", str(llvm_dir), "--deps", str(self.root_dir / "runtime" / "deps")]
            ninja_bin = self.root_dir / "bin" / "ninja.exe"
            if ninja_bin.is_file():
                cmd += ["--ninja", str(ninja_bin)]
            self._run_step(cmd, env, 68, 96)

            for fname in (
                "mtf.exe",
                "SDL3.dll",
                "libopus-0.dll",
                "libiconv-2.dll",
                "ns2_xlate.exe",
                "ns2_xlate.id",
                "Roboto-Medium.ttf",
                "LICENSE-Roboto.txt",
            ):
                src = build_out / fname
                if src.is_file():
                    shutil.copy2(src, self.root_dir / fname)

            if self.shortcut_var.get():
                create_shortcut(self.root_dir)

            self.after(
                0,
                lambda: (
                    self.setup_prog.configure(value=100),
                    self.setup_status_var.set("Setup complete! mtf.exe is ready to play."),
                    self._refresh_status_cards(),
                    self.select_tab("play"),
                    messagebox.showinfo(APP_TITLE, "Mario Tennis Fever PC setup finished cleanly! Press PLAY to start.", parent=self),
                ),
            )
        except Exception as exc:
            err = str(exc)
            self.after(
                0,
                lambda: (
                    self.setup_status_var.set(f"Setup failed: {err}"),
                    self._log_setup(f"ERROR: {err}"),
                    messagebox.showerror(APP_TITLE, err, parent=self),
                ),
            )
        finally:
            self.setup_running = False
            self.after(0, lambda: self.build_btn.configure(state=tk.NORMAL))

    def _capture_shot_and_exit(self) -> None:
        try:
            self.update_idletasks()
            self.update()
            out_path = Path(self.shot_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                hwnd = self.winfo_id()
                # Parent top-level HWND for decorated frame
                parent_hwnd = ctypes.windll.user32.GetParent(hwnd) or hwnd
                rect = (ctypes.c_long * 4)()
                ctypes.windll.user32.GetWindowRect(parent_hwnd, rect)
                w = max(1, int(rect[2] - rect[0]))
                h = max(1, int(rect[3] - rect[1]))
                hdc_win = ctypes.windll.user32.GetWindowDC(parent_hwnd)
                hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc_win)
                hbmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc_win, w, h)
                old = ctypes.windll.gdi32.SelectObject(hdc_mem, hbmp)
                ctypes.windll.user32.PrintWindow(parent_hwnd, hdc_mem, 2)  # PW_RENDERFULLCONTENT
                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                        ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32),
                        ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32),
                    ]
                bmi = BITMAPINFOHEADER()
                bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bmi.biWidth = w
                bmi.biHeight = -h
                bmi.biPlanes = 1
                bmi.biBitCount = 32
                bmi.biCompression = 0
                buf = (ctypes.c_ubyte * (w * h * 4))()
                ctypes.windll.gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bmi), 0)
                ctypes.windll.gdi32.SelectObject(hdc_mem, old)
                ctypes.windll.gdi32.DeleteObject(hbmp)
                ctypes.windll.gdi32.DeleteDC(hdc_mem)
                ctypes.windll.user32.ReleaseDC(parent_hwnd, hdc_win)
                img = Image.frombuffer("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, 1)
                img.save(out_path)
            else:
                from PIL import ImageGrab
                x, y, w, h = self.winfo_rootx(), self.winfo_rooty(), self.winfo_width(), self.winfo_height()
                ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(out_path)
        finally:
            self.after(40, self.destroy)


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--tab", default="play", choices=["play", "setup", "settings", "mods"])
    ap.add_argument("--shot", default="", help="Capture launcher window screenshot and exit")
    ap.add_argument("--check", action="store_true", help="Verify clean startup & exit")
    args = ap.parse_args()

    set_windows_app_id()
    app = MTFLauncherApp(initial_tab=args.tab, shot_path=args.shot)
    if args.check:
        app.update_idletasks()
        app.destroy()
        print("MTFLauncher check: OK")
        return 0
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
