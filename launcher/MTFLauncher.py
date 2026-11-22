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
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from mtf_dump import (
    DumpError,
    EXEFS_REQUIRED,
    discover_dump,
    extract_nup_overlay,
    find_extract_nup,
    load_expected_mtf as load_expected_mtf_dump,
    nro_to_nso,
    reuse_extracted_nup,
    rmtree_retry,
    romfs_has_nrr,
    sha256_file,
    verify_exefs_hashes,
)


APP_TITLE = "MTF ShadowRacket"
APP_SUBTITLE = "Mario Tennis Fever  ·  Native Windows PC Recompilation"
DEFAULT_VERSION = "Alpha 0.1.4"
GITHUB_URL = "https://github.com/STS78721/MTF-ShadowRacket"
RELEASES_URL = GITHUB_URL + "/releases"
RELEASES_API_URL = "https://api.github.com/repos/STS78721/MTF-ShadowRacket/releases/latest"
RELEASES_LIST_API_URL = "https://api.github.com/repos/STS78721/MTF-ShadowRacket/releases?per_page=10"
UPDATE_SKIP_TOP = {
    "exefs",
    "romfs",
    "romfs_packed",
    "generated",
    "spirv",
    "profile",
    "save",
    "logs",
    "shader-cache",
    "work",
    "mods",
}

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
                txt = p.read_text(encoding="utf-8-sig", errors="ignore").strip()
                if txt:
                    return txt.splitlines()[0].strip()
    return DEFAULT_VERSION


def version_tuple(ver: str) -> tuple[tuple[int, ...], str]:
    m = re.search(r"(\d+(?:\.\d+)+)(?:([a-z])(?![a-z]))?", str(ver or "").strip().lower())
    if not m:
        return ((), "")
    nums = tuple(int(x) for x in m.group(1).split("."))
    return (nums, m.group(2) or "")


def is_same_version(ver1: str, ver2: str) -> bool:
    def norm(v: str) -> str:
        v = re.sub(r"^v", "", str(v or "").strip().lower())
        return re.sub(r"[^a-z0-9]", "", v)

    return norm(ver1) == norm(ver2)


def is_up_to_date(local_ver: str, remote_tag: str) -> bool:
    if is_same_version(local_ver, remote_tag):
        return True
    lv, rv = version_tuple(local_ver), version_tuple(remote_tag)
    return bool(lv[0] and rv[0] and lv >= rv)


def _find_update_asset(release: dict) -> tuple[str | None, str | None]:
    tag = (release.get("tag_name") or "").strip()
    raw_assets = release.get("assets") or []
    assets = raw_assets.get("links") or [] if isinstance(raw_assets, dict) else raw_assets
    tag_clean = tag.replace("-", "").replace(".", "")
    candidates = [
        f"SteelTemple-MTF-ShadowRacket-{tag}-Update.zip",
        f"SteelTemple-MTF-ShadowRacket-{tag_clean}-Update.zip",
        f"SteelTemple-MTF-ShadowRacket-Update-{tag}.zip",
    ]
    asset = next(
        (
            item
            for item in assets
            for cand in candidates
            if item.get("name", "").casefold() == cand.casefold()
        ),
        None,
    )
    if not asset:
        asset = next(
            (
                item
                for item in assets
                if "update" in item.get("name", "").lower() and item.get("name", "").lower().endswith(".zip")
            ),
            None,
        )
    if not asset:
        return (None, None)
    return (asset.get("name"), asset.get("browser_download_url") or asset.get("url"))


def select_latest_release(releases: list[dict]) -> dict | None:
    """Pick newest non-draft release across regular releases and pre-releases."""
    candidates = [r for r in (releases or []) if isinstance(r, dict) and not r.get("draft")]
    if not candidates:
        return None

    def rank(idx_rel: tuple[int, dict]) -> tuple:
        idx, rel = idx_rel
        tag = (rel.get("tag_name") or "").strip()
        name = (rel.get("name") or "").strip()
        ver = version_tuple(tag)
        if not ver[0]:
            ver = version_tuple(name)
        _, asset_url = _find_update_asset(rel)
        return (bool(ver[0]), ver, 1 if asset_url else 0, -idx)

    return max(enumerate(candidates), key=rank)[1]


def find_running_mtf_processes(root: Path) -> list[dict]:
    if os.name != "nt":
        return []
    target = str((root / "mtf.exe").resolve()).replace("'", "''")
    command = (
        f"$target = '{target}'; "
        "$items = @(Get-CimInstance Win32_Process -Filter \\\"Name='mtf.exe'\\\" -ErrorAction SilentlyContinue | "
        "Where-Object { $_.ExecutablePath -and "
        "[String]::Equals([IO.Path]::GetFullPath($_.ExecutablePath), $target, "
        "[StringComparison]::OrdinalIgnoreCase) } | "
        "Select-Object ProcessId, ExecutablePath); "
        "if ($items.Count -eq 1) { $items[0] | ConvertTo-Json -Compress } "
        "else { $items | ConvertTo-Json -Compress }"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            return []
        output = result.stdout.strip()
        if not output or output == "null":
            return []
        parsed = json.loads(output)
        if isinstance(parsed, dict):
            return [{"pid": parsed.get("ProcessId"), "path": parsed.get("ExecutablePath")}]
        if isinstance(parsed, list):
            return [
                {"pid": item.get("ProcessId"), "path": item.get("ExecutablePath")}
                for item in parsed
                if isinstance(item, dict)
            ]
    except Exception:
        pass
    return []


def game_process_warning(root: Path, action: str) -> str | None:
    processes = find_running_mtf_processes(root)
    if not processes:
        return None
    details = []
    for process in processes:
        label = []
        if process.get("pid") is not None:
            label.append(f"PID {process['pid']}")
        if process.get("path"):
            label.append(str(process["path"]))
        details.append(" - ".join(label) if label else "mtf.exe")
    return "Mario Tennis Fever (mtf.exe) is currently running:\n" + "\n".join(details) + f"\n\nClose the game before {action}."


def _win_long_path(path: Path) -> Path:
    """Prefix deep Windows paths with \\\\?\\ so file operations never hit the 260-char MAX_PATH limit."""
    p = Path(path)
    if os.name != "nt":
        return p
    raw = str(p.resolve(strict=False))
    if raw.startswith("\\\\?\\"):
        return Path(raw)
    if len(raw) < 240:
        return Path(raw)
    if raw.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + raw[2:])
    return Path("\\\\?\\" + raw)


def _is_updater_pid_alive(pid: int) -> bool:
    if pid <= 0 or os.name != "nt":
        return False
    try:
        r = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"$p = Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue; if ($p -and $p.ProcessName -match 'powershell|pwsh') {{ 'ALIVE' }}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return r.returncode == 0 and "ALIVE" in (r.stdout or "")
    except Exception:
        return False


def cleanup_stale_update_dirs(root: Path) -> int:
    """Remove leftover .mtf-update-* staging folders and temp swap files when no updater is active."""
    root = Path(root)
    if not root.is_dir():
        return 0
    lock_file = root / "logs" / ".mtf-update-active.pid"
    if lock_file.is_file():
        try:
            pid = int(lock_file.read_text(encoding="utf-8", errors="ignore").strip() or "0")
            if _is_updater_pid_alive(pid):
                return 0
        except Exception:
            pass
        try:
            lock_file.unlink(missing_ok=True)
        except OSError:
            pass

    removed = 0
    try:
        entries = list(root.iterdir())
    except OSError:
        return 0
    for entry in entries:
        name = entry.name
        if entry.is_dir() and name.startswith(".mtf-update-"):
            try:
                rmtree_retry(_win_long_path(entry))
                removed += 1
            except Exception:
                shutil.rmtree(_win_long_path(entry), ignore_errors=True)
                if not entry.exists():
                    removed += 1
        elif entry.is_file() and (".update-old" in name or name.endswith(".update-new")):
            try:
                entry.unlink(missing_ok=True)
                removed += 1
            except OSError:
                pass
    return removed


def extract_update_archive(
    archive_path: Path,
    stage_dir: Path,
    existing_root: Path | None = None,
) -> list[str]:
    """Stage safe files from the official MTF Update.zip (flat or MTF-ShadowRacket/ nested).

    When existing_root is provided, validates the full archive (including CRC and required MTFLauncher.exe)
    and only stages files that are missing or differ from existing_root so updates apply in seconds.
    """
    archive_path, stage_dir = Path(archive_path), Path(stage_dir)
    existing_base = Path(existing_root).resolve() if existing_root is not None else None
    selected: dict[str, tuple[tuple[str, ...], zipfile.ZipInfo]] = {}
    with zipfile.ZipFile(archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"Update archive CRC check failed for {bad_member}.")
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            path = Path(name)
            parts = path.parts
            if parts and parts[0].casefold() == "mtf-shadowracket":
                parts = parts[1:]
            if not parts or path.is_absolute() or ".." in parts:
                raise ValueError(f"Unexpected path in update archive: {info.filename}")
            top = parts[0].casefold()
            if top in UPDATE_SKIP_TOP or top.startswith("."):
                continue
            if parts[-1].casefold() in {"mtf.ini", ".ds_store"}:
                continue
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"Symbolic links are not allowed in updates: {info.filename}")
            # Empty files (e.g. Python package markers) are allowed.
            key = "/".join(parts).casefold()
            if key in selected:
                raise ValueError(f"Duplicate update file: {info.filename}")
            selected[key] = (parts, info)

        launcher_keys = [k for k in selected if k.endswith("mtflauncher.exe")]
        if not launcher_keys:
            raise ValueError("Update archive is missing required binary: MTFLauncher.exe.")
        if selected[launcher_keys[0]][1].file_size < 1024 * 1024:
            raise ValueError("Update launcher executable is unexpectedly small.")

        written: list[str] = []
        for _key, (parts, info) in selected.items():
            rel = Path(*parts)
            data = archive.read(info)
            if existing_base is not None:
                cur = _win_long_path(existing_base / rel)
                try:
                    if cur.is_file() and cur.stat().st_size == len(data) and cur.read_bytes() == data:
                        continue
                except OSError:
                    pass
            target = _win_long_path(stage_dir / rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            written.append(rel.as_posix())
        return written


def build_update_relauncher_script(
    game_dir: Path,
    stage_dir: Path,
    title: str,
    pid: int = 0,
    restart: bool = True,
    silent: bool = False,
    tag: str = "",
) -> str:
    def ps_quote(value: object) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    game_path = ps_quote(Path(game_dir).resolve())
    stage_path = ps_quote(Path(stage_dir).resolve())
    title_text = ps_quote(title)
    tag_text = ps_quote(tag or title)
    wait_pid_line = f"Wait-Process -Id {int(pid)} -Timeout 20 -ErrorAction SilentlyContinue" if pid and pid > 0 else ""
    msg_err = (
        ""
        if silent
        else (
            "try {\n"
            "        Add-Type -AssemblyName System.Windows.Forms\n"
            "        [System.Windows.Forms.MessageBox]::Show(\n"
            "            ('Update failed and changes were rolled back:' + [Environment]::NewLine + $errMsg + [Environment]::NewLine + [Environment]::NewLine + 'See logs\\update.log for details.'),\n"
            "            'MTF ShadowRacket — Update Failed',\n"
            "            [System.Windows.Forms.MessageBoxButtons]::OK,\n"
            "            [System.Windows.Forms.MessageBoxIcon]::Error,\n"
            "            [System.Windows.Forms.MessageBoxDefaultButton]::Button1,\n"
            "            [System.Windows.Forms.MessageBoxOptions]::DefaultDesktopOnly\n"
            "        ) | Out-Null\n"
            "    } catch {}\n"
        )
    )
    restart_block = (
        "    if ([System.IO.File]::Exists($targetLauncherLP)) {\n"
        "        Start-Process -FilePath $targetLauncher -WorkingDirectory $game\n"
        "    }\n"
        if restart
        else ""
    )
    return f"""$ErrorActionPreference = 'Stop'
$tStart = Get-Date
$game = {game_path}
$stage = {stage_path}
$title = {title_text}
$tag = {tag_text}

function ConvertTo-LongPath([string]$p) {{
    $full = [System.IO.Path]::GetFullPath($p)
    if ($full.StartsWith('\\\\?\\')) {{ return $full }}
    if ($full.StartsWith('\\\\')) {{ return '\\\\?\\UNC\\' + $full.Substring(2) }}
    return '\\\\?\\' + $full
}}

$gameLP = (ConvertTo-LongPath $game).TrimEnd('\\')
$stageLP = (ConvertTo-LongPath $stage).TrimEnd('\\')
$rollbackLP = $stageLP + '\\_rollback'
$targetLauncher = Join-Path $game 'MTFLauncher.exe'
$targetLauncherFull = [System.IO.Path]::GetFullPath($targetLauncher)
$targetLauncherLP = ConvertTo-LongPath $targetLauncher
$logDirLP = $gameLP + '\\logs'
$logFileLP = $logDirLP + '\\update.log'
$doneFileLP = $logDirLP + '\\update_done.json'
$failFileLP = $logDirLP + '\\update_failed.json'
$lockFileLP = $logDirLP + '\\.mtf-update-active.pid'
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

function Write-UpdateLog([string]$msg) {{
    try {{
        [System.IO.Directory]::CreateDirectory($logDirLP) | Out-Null
        $line = '[' + (Get-Date -Format 's') + '] ' + $msg + [Environment]::NewLine
        [System.IO.File]::AppendAllText($logFileLP, $line, $utf8NoBom)
    }} catch {{}}
}}

function Remove-StageDir {{
    for ($try = 1; $try -le 8; $try++) {{
        try {{
            if ([System.IO.Directory]::Exists($stageLP)) {{
                [System.IO.Directory]::Delete($stageLP, $true)
            }}
            break
        }} catch {{
            Start-Sleep -Milliseconds 250
        }}
    }}
}}

Write-UpdateLog ('Updater started (PID ' + $PID + '): ' + $title)
try {{
    [System.IO.Directory]::CreateDirectory($logDirLP) | Out-Null
    [System.IO.File]::WriteAllText($lockFileLP, [string]$PID, $utf8NoBom)
}} catch {{}}

$changed = [System.Collections.Generic.List[string]]::new()
$appliedCount = 0
$failed = $false
$errMsg = ''

try {{
    [System.IO.Directory]::CreateDirectory($rollbackLP) | Out-Null
    {wait_pid_line}
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {{
        $stillRunning = $false
        foreach ($proc in @([System.Diagnostics.Process]::GetProcessesByName('MTFLauncher'))) {{
            try {{
                $pPath = $proc.MainModule.FileName
                if ($pPath -and [String]::Equals([System.IO.Path]::GetFullPath($pPath), $targetLauncherFull, [StringComparison]::OrdinalIgnoreCase)) {{
                    $stillRunning = $true
                    break
                }}
            }} catch {{
                try {{
                    $cim = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $proc.Id) -ErrorAction SilentlyContinue
                    if ($cim -and $cim.ExecutablePath -and [String]::Equals([System.IO.Path]::GetFullPath($cim.ExecutablePath), $targetLauncherFull, [StringComparison]::OrdinalIgnoreCase)) {{
                        $stillRunning = $true
                        break
                    }}
                }} catch {{}}
            }} finally {{
                try {{ $proc.Dispose() }} catch {{}}
            }}
        }}
        if (-not $stillRunning) {{ break }}
        Start-Sleep -Milliseconds 200
    }}
    Start-Sleep -Milliseconds 200

    $prefixLen = $stageLP.Length + 1
    foreach ($src in [System.IO.Directory]::EnumerateFiles($stageLP, '*', [System.IO.SearchOption]::AllDirectories)) {{
        $rel = $src.Substring($prefixLen)
        if ($rel.StartsWith('_rollback\\', [System.StringComparison]::OrdinalIgnoreCase)) {{ continue }}
        $name = [System.IO.Path]::GetFileName($src)
        if ($name.EndsWith('.tmp') -or $name.EndsWith('.update-new') -or $name.Contains('.update-old')) {{ continue }}
        if (-not $rel.Contains('\\') -and $name.EndsWith('.zip', [System.StringComparison]::OrdinalIgnoreCase)) {{ continue }}

        $dst = $gameLP + '\\' + $rel
        $bak = $rollbackLP + '\\' + $rel
        $dstDir = [System.IO.Path]::GetDirectoryName($dst)
        $bakDir = [System.IO.Path]::GetDirectoryName($bak)
        if ($bakDir) {{ [System.IO.Directory]::CreateDirectory($bakDir) | Out-Null }}
        if ($dstDir) {{ [System.IO.Directory]::CreateDirectory($dstDir) | Out-Null }}

        $newFile = $dst + '.update-new'
        $backedUp = $false
        $tracked = $false
        for ($attempt = 1; $attempt -le 20; $attempt++) {{
            $oldFile = $dst + '.update-old'
            $movedOld = $false
            try {{
                if (-not $backedUp -and [System.IO.File]::Exists($dst)) {{
                    [System.IO.File]::Copy($dst, $bak, $true)
                    $backedUp = $true
                }}
                if (-not $tracked) {{
                    $changed.Add($rel)
                    $tracked = $true
                }}
                if ([System.IO.File]::Exists($newFile)) {{ [System.IO.File]::Delete($newFile) }}
                [System.IO.File]::Copy($src, $newFile, $true)
                if ([System.IO.File]::Exists($oldFile)) {{
                    try {{ [System.IO.File]::Delete($oldFile) }} catch {{ $oldFile = $dst + '.update-old-' + $attempt }}
                }}
                if ([System.IO.File]::Exists($dst)) {{
                    [System.IO.File]::Move($dst, $oldFile)
                    $movedOld = $true
                }}
                [System.IO.File]::Move($newFile, $dst)
                if ($movedOld -and [System.IO.File]::Exists($oldFile)) {{
                    try {{ [System.IO.File]::Delete($oldFile) }} catch {{}}
                }}
                break
            }} catch {{
                if ($movedOld -and -not [System.IO.File]::Exists($dst) -and [System.IO.File]::Exists($oldFile)) {{
                    try {{ [System.IO.File]::Move($oldFile, $dst) }} catch {{}}
                }}
                if ([System.IO.File]::Exists($newFile)) {{
                    try {{ [System.IO.File]::Delete($newFile) }} catch {{}}
                }}
                if ($attempt -ge 20) {{ throw }}
                Start-Sleep -Milliseconds 250
            }}
        }}
        $appliedCount++
    }}

    $elapsed = [Math]::Round(((Get-Date) - $tStart).TotalSeconds, 2)
    Write-UpdateLog ('Applied ' + $appliedCount + ' files cleanly in ' + $elapsed + 's.')
    try {{ if ([System.IO.File]::Exists($failFileLP)) {{ [System.IO.File]::Delete($failFileLP) }} }} catch {{}}
    try {{
        $doneJson = (@{{ title = $title; tag = $tag; applied = $appliedCount; ts = (Get-Date -Format 's') }} | ConvertTo-Json -Compress)
        [System.IO.File]::WriteAllText($doneFileLP, $doneJson, $utf8NoBom)
    }} catch {{}}
    Remove-StageDir
{restart_block}}} catch {{
    $failed = $true
    $errMsg = $_.Exception.Message
    Write-UpdateLog ('ERROR: ' + $errMsg + ' (rolling back ' + $changed.Count + ' files)')
    for ($i = $changed.Count - 1; $i -ge 0; $i--) {{
        $rel = $changed[$i]
        $dst = $gameLP + '\\' + $rel
        $bak = $rollbackLP + '\\' + $rel
        try {{
            if ([System.IO.File]::Exists($bak)) {{ [System.IO.File]::Copy($bak, $dst, $true) }}
            elseif ([System.IO.File]::Exists($dst)) {{ [System.IO.File]::Delete($dst) }}
        }} catch {{}}
        foreach ($suf in @('.update-new', '.update-old')) {{
            try {{ if ([System.IO.File]::Exists($dst + $suf)) {{ [System.IO.File]::Delete($dst + $suf) }} }} catch {{}}
        }}
    }}
    try {{
        $failJson = (@{{ title = $title; tag = $tag; error = $errMsg; ts = (Get-Date -Format 's') }} | ConvertTo-Json -Compress)
        [System.IO.File]::WriteAllText($failFileLP, $failJson, $utf8NoBom)
    }} catch {{}}
    Remove-StageDir
    {msg_err}}} finally {{
    try {{ if ([System.IO.File]::Exists($lockFileLP)) {{ [System.IO.File]::Delete($lockFileLP) }} }} catch {{}}
    if ($PSCommandPath -and [System.IO.File]::Exists($PSCommandPath)) {{
        try {{ [System.IO.File]::Delete($PSCommandPath) }} catch {{}}
    }}
}}
if ($failed) {{ exit 1 }}
"""


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
        for raw in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
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
    lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines(keepends=True) if path.is_file() else []
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
        "aniso": "game",
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


def load_expected_mtf(root: Path) -> dict[str, str]:
    return load_expected_mtf_dump(root, resource_bases=[resource_base(), resource_base().parent])


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
    def __init__(self, initial_tab: str = "play", shot_path: str = "", skip_update_check: bool = False) -> None:
        super().__init__()
        self.root_dir = resolve_root_dir()
        self.version = read_app_version()
        self.shot_path = shot_path
        self._skip_update_check = skip_update_check
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
        self.refresh_running = False
        self._last_nup_extract: tuple[Path, Path, Path] | None = None
        self.current_tab = initial_tab
        self.latest_release: dict | None = None
        self.release_check_active = False
        self.update_in_progress = False
        self._auto_installing = False
        self.auto_install_updates = True

        self._build_layout()
        self._load_ini_into_vars()
        self._refresh_status_cards()
        self.select_tab(initial_tab)
        self._recent_update_done = self._consume_update_done_marker()
        if self._recent_update_done:
            done_title = self._recent_update_done.get("title") or self.version
            self.update_status.config(text=f"Updated to {done_title} cleanly.", fg=C_OK)

        threading.Thread(target=self._probe_gpu_async, daemon=True).start()
        if self.shot_path:
            self.after(450, self._capture_shot_and_exit)
        else:
            self.after(250, self._auto_refresh_existing_build)
            self.after(1500, lambda: threading.Thread(target=cleanup_stale_update_dirs, args=(self.root_dir,), daemon=True).start())
            if not getattr(self, "_skip_update_check", False):
                self.after(700, self.check_for_updates)

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

        upd = tk.Frame(top, bg=C_PANEL)
        upd.pack(fill=tk.X, pady=(14, 0))
        self.update_status = tk.Label(
            upd,
            text="Checking GitHub Releases…",
            font=("Segoe UI", 9),
            fg=C_TEXT_DIM,
            bg=C_PANEL,
            wraplength=880,
            justify="left",
        )
        self.update_status.pack(anchor="w")
        btn_row = tk.Frame(upd, bg=C_PANEL)
        btn_row.pack(fill=tk.X, pady=(6, 0))
        self.update_action_btn = self._accent_btn(btn_row, "INSTALL UPDATE", self.apply_latest_update, width=18)
        self.release_btn = self._plain_btn(btn_row, "VIEW RELEASE NOTES", self.open_latest_release, width=20)
        self._plain_btn(btn_row, "CHECK FOR UPDATES", self.check_for_updates, width=18).pack(side=tk.LEFT)
        # Hidden until an update is available / notes needed
        self.update_action_btn.pack_forget()
        self.release_btn.pack_forget()

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
            ("Internal Scaling Ready", "Supports Original (~960p), 720p, 900p, 1080p, 1440p, and 2160p (4K) — switch cleanly anytime before launch or in-game (F1)."),
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
            text="No copyrighted game data is shipped with MTF ShadowRacket. Select your dumped Switch 2 ExeFS and RomFS folders, "
            "a NUP-extracted dump tree (update alone or base + updates\\<ver>), or a .nup container. Setup verifies Mario Tennis Fever 1.1.1 "
            "SHA-256 hashes, packs RomFS, lifts ARM64 modules, and compiles mtf.exe locally.",
            font=("Segoe UI", 9),
            fg=C_TEXT_SOFT,
            bg=C_PANEL,
            wraplength=920,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        dump_row = tk.Frame(card, bg=C_PANEL)
        dump_row.pack(fill=tk.X, pady=3)
        tk.Label(
            dump_row,
            text="Dump Folder / .NUP (auto-detect):",
            width=38,
            anchor="w",
            font=("Segoe UI", 9),
            fg=C_TEXT_DIM,
            bg=C_PANEL,
        ).pack(side=tk.LEFT)
        tk.Entry(
            dump_row,
            textvariable=self.dump_root_var,
            bg=C_BG_DEEP,
            fg=C_TEXT,
            insertbackground=C_OPTIC,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8), ipady=5)
        self.folder_btn = self._plain_btn(dump_row, "Folder...", self._pick_dump_root, width=9)
        self.folder_btn.pack(side=tk.RIGHT, padx=(4, 0))
        self.nup_btn = self._plain_btn(dump_row, ".NUP...", self._pick_nup_file, width=8)
        self.nup_btn.pack(side=tk.RIGHT)
        self.exefs_browse_btn = self._path_picker(card, "ExeFS Folder (main, main.npdm, rtld, sdk):", self.exefs_var, self._pick_exefs)
        self.romfs_browse_btn = self._path_picker(card, "RomFS Folder (raw dump or romfs_packed):", self.romfs_var, self._pick_romfs)

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

    def _path_picker(self, parent: tk.Misc, label: str, var: tk.StringVar, cmd) -> tk.Button:
        row = tk.Frame(parent, bg=C_PANEL)
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text=label, width=38, anchor="w", font=("Segoe UI", 9), fg=C_TEXT_DIM, bg=C_PANEL).pack(side=tk.LEFT)
        tk.Entry(row, textvariable=var, bg=C_BG_DEEP, fg=C_TEXT, insertbackground=C_OPTIC, relief=tk.FLAT,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8), ipady=5)
        btn = self._plain_btn(row, "Browse...", cmd, width=10)
        btn.pack(side=tk.RIGHT)
        return btn

    def _set_setup_busy(self, busy: bool) -> None:
        self.setup_running = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for attr in ("folder_btn", "nup_btn", "exefs_browse_btn", "romfs_browse_btn", "build_btn"):
            btn = getattr(self, attr, None)
            if btn is not None:
                btn.configure(state=state)

    def _apply_dump_resolve(self, resolved, *, log: bool = True, update_status: bool = True) -> None:
        self.exefs_var.set(str(resolved.exefs))
        self.romfs_var.set(str(resolved.romfs))
        if log:
            for note in resolved.notes:
                self._log_setup(note)
        if update_status:
            self.setup_status_var.set("Dump paths resolved. Click VERIFY & BUILD MTF.EXE when ready.")

    def _pick_dump_root(self) -> None:
        if self.setup_running:
            return
        d = filedialog.askdirectory(title="Select Mario Tennis Fever Dump Root / NUP-extracted Folder")
        if not d:
            return
        self.dump_root_var.set(d)
        try:
            work = self.root_dir / "work" / "dump-resolve"
            work.mkdir(parents=True, exist_ok=True)
            resolved = discover_dump(Path(d), work)
            self.setup_log.delete("1.0", tk.END)
            self._apply_dump_resolve(resolved)
        except DumpError as exc:
            messagebox.showerror(APP_TITLE, str(exc), parent=self)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not auto-detect dump folders:\n{exc}", parent=self)

    def _resolve_or_extract_nup(
        self,
        nup: Path,
        *,
        exefs_hint: str = "",
        pct_lo: int = 2,
        pct_hi: int = 99,
    ):
        nup_out = self.root_dir / "work" / "nup-extract"
        resolved = reuse_extracted_nup(nup, nup_out)
        if resolved is None and exefs_hint:
            cand_parent = Path(exefs_hint).parent
            if cand_parent.name.startswith("nup-extract"):
                resolved = reuse_extracted_nup(nup, cand_parent)
        if resolved is not None:
            self.after(0, lambda: self._log_setup("Reusing extracted NUP tree (no re-extract needed)."))
            return resolved

        self.after(
            0,
            lambda name=nup.name: self.setup_status_var.set(
                f"Extracting {name} (base+update if present, else update alone)…"
            ),
        )

        def on_progress(line: str, pct: int | None) -> None:
            def _ui() -> None:
                self._log_setup(line)
                if pct is not None:
                    p = pct_lo + int((pct_hi - pct_lo) * max(0, min(100, pct)) / 100)
                    self.setup_prog.configure(value=p)
                    self.setup_status_var.set(f"Extracting {nup.name}… {pct}%")

            self.after(0, _ui)

        script = find_extract_nup(self.root_dir, resource_bases=[resource_base(), resource_base().parent])
        return extract_nup_overlay(
            nup,
            nup_out,
            python=self._find_setup_python(),
            extract_script=script,
            root=self.root_dir,
            on_progress=on_progress,
        )

    def _pick_nup_file(self) -> None:
        if self.setup_running:
            return
        path = filedialog.askopenfilename(
            title="Select Mario Tennis Fever .NUP Container",
            filetypes=[("NX Package (NUP)", "*.nup"), ("All files", "*.*")],
        )
        if not path:
            return
        nup = Path(path)
        self.dump_root_var.set(str(nup))
        self.setup_log.delete("1.0", tk.END)
        self._set_setup_busy(True)
        self.setup_prog.configure(value=2)
        self.setup_status_var.set(f"Extracting {nup.name} (base+update if present, else update alone)…")
        self.update_idletasks()

        def worker() -> None:
            try:
                resolved = self._resolve_or_extract_nup(nup, pct_lo=2, pct_hi=99)
                self._last_nup_extract = (nup.resolve(), resolved.exefs.resolve(), resolved.romfs.resolve())
                self.after(
                    0,
                    lambda r=resolved: (
                        self.setup_prog.configure(value=100),
                        self._apply_dump_resolve(r),
                    ),
                )
            except Exception as exc:
                err = str(exc)
                self.after(
                    0,
                    lambda e=err: (
                        self.setup_prog.configure(value=0),
                        self.setup_status_var.set(f"NUP extract failed: {e}"),
                        self._log_setup(f"ERROR: {e}"),
                        messagebox.showerror(APP_TITLE, e, parent=self),
                    ),
                )
            finally:
                self.after(0, lambda: self._set_setup_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _pick_exefs(self) -> None:
        if self.setup_running:
            return
        d = filedialog.askdirectory(title="Select ExeFS Folder (main, main.npdm, rtld, sdk)")
        if d:
            self.exefs_var.set(d)

    def _pick_romfs(self) -> None:
        if self.setup_running:
            return
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
        self._combo_row(left, "Internal Resolution", "resolution", ["original", "720", "900", "1080", "1440", "2160"],
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
        dump_root = self.dump_root_var.get().strip()
        exefs_txt = self.exefs_var.get().strip()
        romfs_txt = self.romfs_var.get().strip()

        has_root = bool(dump_root and Path(dump_root).exists())
        has_pair = bool(exefs_txt and romfs_txt and Path(exefs_txt).is_dir() and Path(romfs_txt).is_dir())
        if not has_root and not has_pair:
            messagebox.showwarning(
                APP_TITLE,
                "Please select a dump folder / .nup, or both ExeFS and RomFS folders first.",
                parent=self,
            )
            return

        self.setup_log.delete("1.0", tk.END)
        self._set_setup_busy(True)
        self.setup_prog.configure(value=2)
        self.setup_status_var.set("Resolving Mario Tennis Fever 1.1.1 dump...")
        threading.Thread(
            target=self._run_setup_worker,
            args=(dump_root, exefs_txt, romfs_txt),
            daemon=True,
        ).start()

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

    def _build_game_cmd(
        self,
        py: Path,
        *,
        gen_dir: Path,
        build_out: Path,
        exefs: Path,
        packed_romfs: Path,
        expected_path: Path | None = None,
    ) -> list[str]:
        cmd = [
            str(py),
            str(self.root_dir / "tools" / "build_game.py"),
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
        if expected_path is not None:
            cmd += ["--expected", str(expected_path)]
        rt_lib = self.root_dir / "runtime" / "libmtfrt.a"
        if rt_lib.is_file():
            cmd += ["--runtime", str(self.root_dir / "runtime"), "--runtime-lib", str(rt_lib)]
        llvm_dir = self.root_dir / "llvm"
        if llvm_dir.is_dir():
            cmd += ["--toolchain", str(llvm_dir), "--deps", str(self.root_dir / "runtime" / "deps")]
        ninja_bin = self.root_dir / "bin" / "ninja.exe"
        if ninja_bin.is_file():
            cmd += ["--ninja", str(ninja_bin)]
        return cmd

    def _synthesize_subsdk0(
        self,
        py: Path,
        env: dict[str, str],
        exefs: Path,
        packed_romfs: Path,
        expected: dict[str, str],
    ) -> None:
        self.after(0, lambda: (
            self.setup_status_var.set("2.5/4 Synthesizing subsdk0 module from RomFS (.nrr)..."),
            self._log_setup("ExeFS has no subsdk0; capturing runtime NRO0 from RomFS .nrr..."),
        ))
        pre_gen_dir = self.root_dir / "work" / "generated" / "mtf111-prenro"
        pre_build_out = self.root_dir / "work" / "build" / "mtf111-prenro"
        rmtree_retry(pre_gen_dir) if pre_gen_dir.exists() else None
        rmtree_retry(pre_build_out) if pre_build_out.exists() else None
        pre_gen_dir.mkdir(parents=True, exist_ok=True)
        pre_build_out.mkdir(parents=True, exist_ok=True)

        try:
            pre_patches = pre_build_out / "patches-mtf111-prenro.txt"
            pre_patches.write_text("# Pre-NRO capture pass\n", encoding="utf-8")
            pre_exp = {
                "short_name": "mtf",
                "display_name": "Mario Tennis Fever",
                "title_id": "0400D4201C6EA000",
                "display_version": "1.1.1",
                "exefs_sha256": {k: v for k, v in expected.items() if k != "subsdk0"},
            }
            pre_exp_path = pre_build_out / "expected-mtf111-prenro.json"
            pre_exp_path.write_text(json.dumps(pre_exp, indent=2) + "\n", encoding="utf-8")

            gen_script = self.root_dir / "recomp" / "gen.py"
            self._run_step(
                [
                    str(py),
                    str(gen_script),
                    "--exefs",
                    str(exefs),
                    "--out",
                    str(pre_gen_dir),
                    "--modules",
                    "main,sdk",
                    "--patches",
                    str(pre_patches),
                ],
                env,
                42,
                48,
            )
            self._run_step(
                self._build_game_cmd(
                    py,
                    gen_dir=pre_gen_dir,
                    build_out=pre_build_out,
                    exefs=exefs,
                    packed_romfs=packed_romfs,
                    expected_path=pre_exp_path,
                ),
                env,
                48,
                55,
            )

            pre_exe = pre_build_out / ("mtf.exe" if os.name == "nt" else "mtf")
            bin_dir = self.root_dir / "bin"
            if bin_dir.is_dir():
                for dll in bin_dir.glob("*.dll"):
                    dst = pre_build_out / dll.name
                    if not dst.is_file():
                        shutil.copy2(dll, dst)

            tmp_nro = pre_build_out / "captured_runtime.nro"
            tmp_nro.unlink(missing_ok=True)
            cap_env = dict(env)
            cap_env["TOTK_GPU"] = "null"
            cap_env["NS2_DUMP_NRO"] = str(tmp_nro)
            self.after(0, lambda: self._log_setup(f"+ {pre_exe} --seconds 15 (TOTK_GPU=null)"))
            try:
                proc = subprocess.run(
                    [str(pre_exe), "--seconds", "15"],
                    cwd=str(pre_build_out),
                    env=cap_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("Headless subsdk0 capture timed out after 90s.") from exc
            if proc.stdout and proc.stdout.strip():
                tail = "\n".join(proc.stdout.strip().splitlines()[-12:])
                self.after(0, lambda t=tail: self._log_setup(t))
            if not tmp_nro.is_file():
                raise RuntimeError(
                    "Headless pre-pass did not capture a runtime NRO for subsdk0. "
                    "Verify RomFS includes .nrr/nrr.nrr and retry."
                )

            want_sub = expected.get("subsdk0")
            nso_bytes = nro_to_nso(tmp_nro.read_bytes(), want_sha256=want_sub)
            (exefs / "subsdk0").write_bytes(nso_bytes)
            verify_lines = verify_exefs_hashes(exefs, expected, allow_missing_subsdk0=False)
            for line in verify_lines:
                self.after(0, lambda t=line: self._log_setup(t))
            self.after(0, lambda: (
                self._log_setup("Synthesized & verified subsdk0 (5/5 ExeFS SHA-256 hashes matched)."),
                self.setup_prog.configure(value=56),
            ))
        finally:
            shutil.rmtree(pre_gen_dir, ignore_errors=True)
            shutil.rmtree(pre_build_out, ignore_errors=True)

    def _run_setup_worker(self, dump_root: str, exefs_txt: str, romfs_txt: str) -> None:
        try:
            # Resolve dump root / .nup off the Tkinter UI thread.
            resolve_root: Path | None = None
            if dump_root:
                resolve_root = Path(dump_root)
            elif exefs_txt:
                exefs_path = Path(exefs_txt)
                if any(part.lower() == "updates" for part in exefs_path.parts):
                    for parent in exefs_path.parents:
                        if parent.name.lower() == "updates":
                            resolve_root = parent.parent
                            break

            if resolve_root is not None:
                resolved = None
                if resolve_root.is_file() and resolve_root.suffix.lower() == ".nup":
                    try:
                        resolved = self._resolve_or_extract_nup(
                            resolve_root,
                            exefs_hint=exefs_txt,
                            pct_lo=2,
                            pct_hi=16,
                        )
                    except DumpError as exc:
                        raise RuntimeError(str(exc)) from exc
                    self._last_nup_extract = (
                        resolve_root.resolve(),
                        resolved.exefs.resolve(),
                        resolved.romfs.resolve(),
                    )
                    self.after(0, lambda: self.setup_prog.configure(value=16))
                elif resolve_root.is_dir():
                    work = self.root_dir / "work" / "dump-resolve"
                    work.mkdir(parents=True, exist_ok=True)
                    try:
                        resolved = discover_dump(resolve_root, work)
                    except DumpError as exc:
                        raise RuntimeError(str(exc)) from exc

                if resolved is not None:
                    self.after(0, lambda r=resolved: self._apply_dump_resolve(r, log=True, update_status=False))
                    exefs_txt = str(resolved.exefs)
                    romfs_txt = str(resolved.romfs)

            exefs = Path(exefs_txt)
            romfs = Path(romfs_txt)
            if not exefs.is_dir() or not romfs.is_dir():
                raise RuntimeError("Please select a dump folder / .nup, or both ExeFS and RomFS folders first.")

            self.after(0, lambda: self.setup_status_var.set("1/4 Verifying Mario Tennis Fever 1.1.1 ExeFS hashes..."))
            expected = load_expected_mtf(self.root_dir)
            allow_missing_sub = romfs_has_nrr(romfs)
            try:
                lines = verify_exefs_hashes(exefs, expected, allow_missing_subsdk0=allow_missing_sub)
            except DumpError as exc:
                raise RuntimeError(str(exc)) from exc
            for line in lines:
                self.after(0, lambda t=line: self._log_setup(t))
            verified_msg = (
                "ExeFS SHA-256 verification passed (5/5 files matched)."
                if (exefs / "subsdk0").is_file()
                else "Core ExeFS SHA-256 verification passed (4/4 core modules; subsdk0 queued from RomFS .nrr)."
            )
            self.after(0, lambda m=verified_msg: (self._log_setup(m), self.setup_prog.configure(value=18)))

            # Keep rt_default_exefs inside self.root_dir/exefs so portable installs stay self-contained.
            local_exefs = self.root_dir / "exefs"
            if exefs.resolve() != local_exefs.resolve():
                local_exefs.mkdir(parents=True, exist_ok=True)
                keep_files = {p.name for p in exefs.iterdir() if p.is_file()}
                local_sub = local_exefs / "subsdk0"
                want_sub = expected.get("subsdk0", "").lower()
                if (
                    "subsdk0" not in keep_files
                    and local_sub.is_file()
                    and want_sub
                    and sha256_file(local_sub).lower() == want_sub
                ):
                    keep_files.add("subsdk0")
                for old in list(local_exefs.iterdir()):
                    if old.is_file() and old.name not in keep_files:
                        old.unlink(missing_ok=True)
                copied: set[str] = set()
                for name in EXEFS_REQUIRED:
                    src = exefs / name
                    if src.is_file():
                        shutil.copy2(src, local_exefs / name)
                        copied.add(name)
                for src in exefs.iterdir():
                    if src.is_file() and src.name not in copied:
                        shutil.copy2(src, local_exefs / src.name)
                exefs = local_exefs
                self.after(
                    0,
                    lambda p=str(exefs): (
                        self.exefs_var.set(p),
                        self._log_setup(f"Staged verified ExeFS into {p}"),
                    ),
                )

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

            # Step 2.5: Capture & wrap runtime subsdk0 when absent from raw ExeFS dump
            if not (exefs / "subsdk0").is_file():
                self._synthesize_subsdk0(py, env, exefs, packed_romfs, expected)

            # Step 3: Lift ExeFS ARM64 -> C
            gen_dir = self.root_dir / "work" / "generated" / "mtf111"
            gen_ready = (
                (gen_dir / "layout.json").is_file()
                and (gen_dir / "patches.h").is_file()
                and all(
                    (gen_dir / m / "manifest.json").is_file() and (gen_dir / m / f"{m}_table.c").is_file()
                    for m in ("main", "subsdk0", "sdk")
                )
            )
            if gen_ready:
                self.after(0, lambda: (self._log_setup(f"Reusing existing lifted C in {gen_dir}"),
                                       self.setup_prog.configure(value=66)))
            else:
                self.after(0, lambda: self.setup_status_var.set("3/4 Lifting ARM64 code to native C..."))
                gen_script = self.root_dir / "recomp" / "gen.py"
                patches = self.root_dir / "recomp" / "patches-mtf111.txt"
                self._run_step(
                    [str(py), str(gen_script), "--exefs", str(exefs), "--out", str(gen_dir), "--patches", str(patches)],
                    env,
                    56,
                    68,
                )

            # Step 4: Compile & link mtf.exe into clean work/build/mtf111 then place finished runtime files at root
            self.after(0, lambda: self.setup_status_var.set("4/4 Compiling & linking mtf.exe..."))
            build_out = self.root_dir / "work" / "build" / "mtf111"
            build_out.mkdir(parents=True, exist_ok=True)
            cmd = self._build_game_cmd(
                py,
                gen_dir=gen_dir,
                build_out=build_out,
                exefs=exefs,
                packed_romfs=packed_romfs,
            )
            self._run_step(cmd, env, 68, 96)

            for fname in (
                "mtf.exe",
                "romfs-index.bin",
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
                elif fname in ("Roboto-Medium.ttf", "LICENSE-Roboto.txt"):
                    fallback = self.root_dir / "bin" / fname
                    if fallback.is_file() and not (self.root_dir / fname).is_file():
                        shutil.copy2(fallback, self.root_dir / fname)
            for patch_dir in ("romfs-patches", "romfs-patches-xbox"):
                src_dir = build_out / patch_dir
                dst_dir = self.root_dir / patch_dir
                if src_dir.is_dir():
                    shutil.rmtree(dst_dir, ignore_errors=True)
                    shutil.copytree(src_dir, dst_dir)

            if self.shortcut_var.get():
                create_shortcut(self.root_dir)
            self._write_runtime_stamp()

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
                lambda e=err: (
                    self.setup_prog.configure(value=0),
                    self.setup_status_var.set(f"Setup failed: {e}"),
                    self._log_setup(f"ERROR: {e}"),
                    messagebox.showerror(APP_TITLE, e, parent=self),
                ),
            )
        finally:
            self.after(0, lambda: self._set_setup_busy(False))

    def _runtime_stamp(self) -> str:
        rt_lib = self.root_dir / "runtime" / "libmtfrt.a"
        if not rt_lib.is_file():
            return ""
        lib_hash = hashlib.sha256(rt_lib.read_bytes()).hexdigest()[:16]
        xlate_id = self.root_dir / "bin" / "ns2_xlate.id"
        xlate_txt = xlate_id.read_text(encoding="utf-8", errors="ignore").strip() if xlate_id.is_file() else ""
        return f"{self.version}|{rt_lib.stat().st_size}|{lib_hash}|{xlate_txt}"

    def _resolve_packed_romfs(self) -> Path | None:
        direct = self.root_dir / "romfs_packed"
        if (direct / "romfs.bin").is_file():
            return direct
        mods_c = self.root_dir / "work" / "build" / "mtf111" / "modules.c"
        if mods_c.is_file():
            txt = mods_c.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r'rt_default_romfs\[\]\s*=\s*"([^"]+)"', txt)
            if m:
                cand = Path(m.group(1).replace("\\\\", "\\"))
                if (cand / "romfs.bin").is_file():
                    return cand
        return None

    def _runtime_stamp_path(self) -> Path:
        return self.root_dir / "work" / "build" / "mtf111" / ".mtf_runtime_stamp"

    def _write_runtime_stamp(self) -> None:
        stamp = self._runtime_stamp()
        if not stamp:
            return
        sp = self._runtime_stamp_path()
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(stamp + "\n", encoding="utf-8")

    def _sync_staged_bin_files(self) -> None:
        if not self._exe_path().is_file():
            return
        src_exe = self.root_dir / "bin" / "ns2_xlate.exe"
        src_id = self.root_dir / "bin" / "ns2_xlate.id"
        if not src_exe.is_file() or not src_id.is_file():
            return
        dst_exe = self.root_dir / "ns2_xlate.exe"
        dst_id = self.root_dir / "ns2_xlate.id"
        try:
            src_bytes = src_id.read_bytes()
            if not dst_id.is_file() or not dst_exe.is_file() or dst_id.read_bytes() != src_bytes:
                shutil.copy2(src_exe, dst_exe)
                shutil.copy2(src_id, dst_id)
        except OSError:
            pass

    def _auto_refresh_existing_build(self) -> None:
        self._sync_staged_bin_files()
        if self.setup_running or self.refresh_running or self.update_in_progress:
            return
        exe = self._exe_path()
        exefs = self.root_dir / "exefs"
        packed_romfs = self._resolve_packed_romfs()
        gen_dir = self.root_dir / "work" / "generated" / "mtf111"
        rt_lib = self.root_dir / "runtime" / "libmtfrt.a"
        if not (
            exe.is_file()
            and exefs.is_dir()
            and packed_romfs is not None
            and (gen_dir / "layout.json").is_file()
            and rt_lib.is_file()
        ):
            return
        want_stamp = self._runtime_stamp()
        if not want_stamp:
            return
        stamp_path = self._runtime_stamp_path()
        have_stamp = stamp_path.read_text(encoding="utf-8", errors="ignore").strip() if stamp_path.is_file() else ""
        stale = (have_stamp != want_stamp) or (rt_lib.stat().st_mtime > exe.stat().st_mtime + 1.0)
        if not stale:
            return
        if game_process_warning(self.root_dir, "updating mtf.exe") is not None:
            return
        self.refresh_running = True
        self.play_btn.configure(state=tk.DISABLED)
        self.build_state_lbl.configure(text=f"Updating mtf.exe for {self.version}…", fg=C_WARN)
        threading.Thread(
            target=self._run_refresh_worker,
            args=(exefs, packed_romfs, gen_dir, want_stamp),
            daemon=True,
        ).start()

    def _run_refresh_worker(self, exefs: Path, packed_romfs: Path, gen_dir: Path, want_stamp: str) -> None:
        err: str | None = None
        try:
            py = self._find_setup_python()
            env = dict(os.environ)
            for d in (self.root_dir / "python", self.root_dir / "llvm" / "bin", self.root_dir / "bin"):
                if d.is_dir():
                    env["PATH"] = str(d) + os.pathsep + env.get("PATH", "")
            build_out = self.root_dir / "work" / "build" / "mtf111"
            build_out.mkdir(parents=True, exist_ok=True)
            cmd = self._build_game_cmd(
                py,
                gen_dir=gen_dir,
                build_out=build_out,
                exefs=exefs,
                packed_romfs=packed_romfs,
            )
            proc = subprocess.run(
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
            if proc.returncode != 0:
                tail = "\n".join((proc.stdout or "").strip().splitlines()[-8:])
                raise RuntimeError(f"Runtime update build failed (exit {proc.returncode}):\n{tail}")
            for fname in ("mtf.exe", "ns2_xlate.exe", "ns2_xlate.id", "SDL3.dll", "libopus-0.dll"):
                src = build_out / fname
                if src.is_file():
                    shutil.copy2(src, self.root_dir / fname)
            self._sync_staged_bin_files()
            stamp_path = self._runtime_stamp_path()
            stamp_path.parent.mkdir(parents=True, exist_ok=True)
            stamp_path.write_text(want_stamp + "\n", encoding="utf-8")
        except Exception as exc:
            err = str(exc)
        finally:
            self.after(0, lambda e=err: self._finish_refresh_worker(e))

    def _finish_refresh_worker(self, err: str | None) -> None:
        self.refresh_running = False
        self._refresh_status_cards()
        if err:
            self.build_hint_lbl.configure(text=err.splitlines()[0], fg=C_BAD)
        else:
            self.build_hint_lbl.configure(text=f"Updated {self._exe_path().name} to {self.version}. Press PLAY to launch.")

    def check_for_updates(self) -> None:
        if getattr(self, "release_check_active", False) or getattr(self, "update_in_progress", False):
            return
        self.release_check_active = True
        self.update_action_btn.pack_forget()
        self.release_btn.pack_forget()
        self.update_status.config(text="Checking GitHub Releases…", fg=C_TEXT_DIM)
        threading.Thread(target=self._check_release_worker, daemon=True).start()

    def _check_release_worker(self) -> None:
        try:
            headers = {"Accept": "application/vnd.github+json", "User-Agent": "MTFLauncher"}
            data: dict | None = None
            try:
                req = urllib.request.Request(RELEASES_LIST_API_URL, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as r:
                    releases = json.loads(r.read().decode("utf-8"))
                if isinstance(releases, list):
                    if not releases:
                        self.after(
                            0,
                            lambda: self._show_release_result(
                                self.version, f"Your MTF ShadowRacket is up to date ({self.version}).", RELEASES_URL, None, None
                            ),
                        )
                        return
                    data = select_latest_release(releases)
                    if data is None:
                        self.after(
                            0,
                            lambda: self._show_release_result(
                                self.version, f"Your MTF ShadowRacket is up to date ({self.version}).", RELEASES_URL, None, None
                            ),
                        )
                        return
            except Exception:
                data = None
            if data is None:
                req = urllib.request.Request(RELEASES_API_URL, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as r:
                    data = json.loads(r.read().decode("utf-8"))
            tag = (data.get("tag_name") or "").strip()
            title = (data.get("name") or tag or "Latest MTF ShadowRacket release").strip()
            page = data.get("html_url") or (f"{GITHUB_URL}/releases/tag/{tag}" if tag else RELEASES_URL)
            if not tag:
                raise ValueError("The latest release did not include a version tag.")
            asset_name, asset_url = _find_update_asset(data)
            self.after(0, lambda: self._show_release_result(tag, title, page, asset_url, asset_name))
        except Exception as exc:
            detail = str(exc)
            if "404" in detail or "Not Found" in detail:
                self.after(
                    0,
                    lambda: self._show_release_result(
                        self.version, f"Your MTF ShadowRacket is up to date ({self.version}).", RELEASES_URL, None, None
                    ),
                )
            else:
                self.after(0, lambda: self._show_release_error("Update check failed: " + detail))

    def _update_done_marker_path(self) -> Path:
        return self._logs_dir() / "update_done.json"

    def _update_failed_marker_path(self) -> Path:
        return self._logs_dir() / "update_failed.json"

    def _consume_update_done_marker(self) -> dict | None:
        p = self._update_done_marker_path()
        if not p.is_file():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig", errors="ignore"))
        except Exception:
            data = None
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
        return data if isinstance(data, dict) else None

    def _read_update_failed_marker(self) -> dict | None:
        p = self._update_failed_marker_path()
        if not p.is_file():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig", errors="ignore"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _clear_update_failed_marker(self) -> None:
        try:
            self._update_failed_marker_path().unlink(missing_ok=True)
        except OSError:
            pass

    def _write_update_failed_marker(self, tag: str, title: str, error: str) -> None:
        try:
            p = self._update_failed_marker_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            payload = {"tag": tag, "title": title, "error": error, "ts": datetime.now().isoformat(timespec="seconds")}
            p.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass

    def _show_release_error(self, message: str) -> None:
        self.release_check_active = False
        self.update_status.config(text=message, fg=C_BAD)

    def _show_release_result(
        self, tag: str, title: str, page: str, asset_url: str | None = None, asset_name: str | None = None
    ) -> None:
        self.release_check_active = False
        self.latest_release = {
            "tag": tag,
            "title": title,
            "page": page,
            "asset_url": asset_url,
            "asset_name": asset_name,
        }
        clean_title = title.split(":", 1)[0].strip()
        if (
            is_up_to_date(self.version, tag)
            or is_same_version(self.version, clean_title)
            or (not version_tuple(tag)[0] and is_up_to_date(self.version, clean_title))
        ):
            self._clear_update_failed_marker()
            if getattr(self, "_recent_update_done", None):
                self.update_status.config(
                    text=f"Updated cleanly — MTF ShadowRacket is up to date ({self.version})", fg=C_OK
                )
            else:
                self.update_status.config(text=f"Your MTF ShadowRacket is up to date ({self.version})", fg=C_OK)
            self.update_action_btn.pack_forget()
            self.release_btn.pack_forget()
            return
        if not asset_url:
            self.update_status.config(text=f"Update found ({clean_title}), but Update.zip is missing.", fg=C_WARN)
            self.update_action_btn.pack_forget()
            self.release_btn.config(text="VIEW RELEASE NOTES")
            self.release_btn.pack(side=tk.LEFT, padx=(10, 0))
            return
        failed = self._read_update_failed_marker()
        if failed and (failed.get("tag") or "").casefold() == tag.casefold():
            err_preview = str(failed.get("error") or "see logs\\update.log").splitlines()[0][:120]
            self.update_status.config(
                text=f"Previous auto-update to {clean_title} failed ({err_preview}) — click INSTALL UPDATE to retry.",
                fg=C_BAD,
            )
            self.update_action_btn.config(state=tk.NORMAL, text="INSTALL UPDATE")
            self.update_action_btn.pack(side=tk.LEFT, padx=(10, 0))
            self.release_btn.config(text="VIEW RELEASE NOTES")
            self.release_btn.pack(side=tk.LEFT, padx=(10, 0))
            return
        if self.auto_install_updates:
            self.update_status.config(text=f"Update available: {clean_title} — installing…", fg=C_WARN)
            self.update_action_btn.config(state=tk.DISABLED, text="AUTO-INSTALLING…")
            self.update_action_btn.pack(side=tk.LEFT, padx=(10, 0))
            self.release_btn.config(text="VIEW RELEASE NOTES")
            self.release_btn.pack(side=tk.LEFT, padx=(10, 0))
            self.after(400, lambda: self.apply_latest_update(auto=True))
        else:
            self.update_status.config(text=f"Update available: {clean_title}", fg=C_WARN)
            self.update_action_btn.config(state=tk.NORMAL, text="INSTALL UPDATE")
            self.update_action_btn.pack(side=tk.LEFT, padx=(10, 0))
            self.release_btn.config(text="VIEW RELEASE NOTES")
            self.release_btn.pack(side=tk.LEFT, padx=(10, 0))

    def open_latest_release(self) -> None:
        url = self.latest_release["page"] if (self.latest_release and self.latest_release.get("page")) else RELEASES_URL
        webbrowser.open(url)

    def apply_latest_update(self, auto: bool = False) -> None:
        if (
            getattr(self, "update_in_progress", False)
            or getattr(self, "refresh_running", False)
            or getattr(self, "setup_running", False)
            or not self.latest_release
        ):
            return
        warning = game_process_warning(self.root_dir, "applying a launcher/game update")
        if warning:
            self.update_action_btn.config(state=tk.NORMAL, text="INSTALL UPDATE")
            self.update_status.config(text="Close Mario Tennis Fever (mtf.exe) before installing the update.", fg=C_WARN)
            if not auto:
                messagebox.showwarning("Close the Game First", warning, parent=self)
            return
        title = self.latest_release.get("title", "MTF ShadowRacket Update")
        if not auto and not messagebox.askyesno(
            "Install MTF ShadowRacket Update",
            f"Download and install {title} now?\n\nThis updates MTFLauncher and toolchain files. "
            "Your dump, saves, and personal mtf.ini stay local.",
            parent=self,
        ):
            return
        if not self.latest_release.get("asset_url") or not self.latest_release.get("asset_name"):
            self.update_status.config(text="Update.zip download URL is missing.", fg=C_BAD)
            return
        if not auto:
            self._clear_update_failed_marker()
        self.update_in_progress = True
        self._auto_installing = bool(auto)
        self.update_action_btn.config(state=tk.DISABLED, text="DOWNLOADING UPDATE…")
        self.update_status.config(text="Connecting to GitHub Releases…", fg=C_TEXT_DIM)
        threading.Thread(target=self._download_update_worker, args=(self.latest_release.copy(),), daemon=True).start()

    def _download_update_worker(self, release: dict) -> None:
        stage = None
        try:
            target = self.root_dir
            target.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix=".mtf-update-", dir=str(target)))
            archive_path = stage / release["asset_name"]
            request = urllib.request.Request(
                release["asset_url"],
                headers={"User-Agent": "MTFLauncher", "Accept": "application/octet-stream"},
            )
            with urllib.request.urlopen(request, timeout=120) as response, archive_path.open("wb") as output:
                total = int(response.headers.get("Content-Length", "0") or 0)
                downloaded = 0
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    output.write(block)
                    downloaded += len(block)
                    if total:
                        percent = min(100, downloaded * 100 // total)
                        self._set_update_status(f"Downloading update… {percent}%", C_TEXT_DIM)
            self._set_update_status("Validating & staging update files…", C_TEXT_DIM)
            files = extract_update_archive(archive_path, stage, existing_root=target)
            archive_path.unlink(missing_ok=True)
            if not files:
                shutil.rmtree(_win_long_path(stage), ignore_errors=True)
                self.after(0, lambda: self._update_already_applied(release))
                return
            self.after(0, lambda: self._update_ready(release, stage, files))
        except Exception as exc:
            if stage:
                shutil.rmtree(_win_long_path(stage), ignore_errors=True)
            detail = str(exc)
            if getattr(self, "_auto_installing", False):
                self._write_update_failed_marker(
                    release.get("tag", ""),
                    release.get("title", "MTF ShadowRacket Update"),
                    detail,
                )
            self.after(0, lambda: self._update_failed(detail))

    def _update_already_applied(self, release: dict) -> None:
        self.update_in_progress = False
        self._clear_update_failed_marker()
        self.version = read_app_version()
        self.update_status.config(text=f"Your MTF ShadowRacket is up to date ({self.version})", fg=C_OK)
        self.update_action_btn.pack_forget()
        self.release_btn.pack_forget()

    def _set_update_status(self, text: str, color: str) -> None:
        try:
            self.after(0, lambda: self.update_status.config(text=text, fg=color))
        except tk.TclError:
            pass

    def _update_failed(self, detail: str) -> None:
        self.update_in_progress = False
        self.update_action_btn.config(state=tk.NORMAL, text="INSTALL UPDATE")
        self.update_status.config(text=f"Update failed:\n{detail[:160]}", fg=C_BAD)

    def _update_ready(self, release: dict, stage: Path, files: list[str]) -> None:
        title = release.get("title", "MTF ShadowRacket Update")
        tag = release.get("tag", "")
        auto = getattr(self, "_auto_installing", False)
        if not auto and not messagebox.askyesno(
            "Update Ready",
            f"{title} is downloaded and verified ({len(files)} updated file(s)).\n\n"
            "Install it now? The launcher will close, apply the files, and restart automatically.",
            parent=self,
        ):
            shutil.rmtree(_win_long_path(stage), ignore_errors=True)
            self.update_in_progress = False
            self.update_action_btn.config(state=tk.NORMAL, text="INSTALL UPDATE")
            self.update_status.config(text="Update downloaded; installation cancelled.", fg=C_TEXT_DIM)
            return
        try:
            self.update_status.config(text=f"Applying {title}… restarting launcher.", fg=C_WARN)
            self.update_idletasks()
            self.withdraw()
            self._start_update_relauncher(stage, title, tag=tag)
            os._exit(0)
        except Exception as exc:
            try:
                self.deiconify()
            except Exception:
                pass
            shutil.rmtree(_win_long_path(stage), ignore_errors=True)
            if auto:
                self._write_update_failed_marker(tag, title, str(exc))
            self._update_failed(str(exc))

    def _start_update_relauncher(self, stage: Path, title: str, tag: str = "") -> None:
        script = build_update_relauncher_script(
            self.root_dir, stage, title, pid=os.getpid(), restart=True, silent=False, tag=tag
        )
        temp_dir = Path(tempfile.gettempdir())
        script_path = temp_dir / f"mtf-update-{stage.name}.ps1"
        # UTF-8 with BOM ensures Windows PowerShell 5.1 parses non-ASCII/accented paths reliably.
        script_path.write_text(script, encoding="utf-8-sig")
        # IMPORTANT: Do NOT use DETACHED_PROCESS with powershell.exe — Windows PowerShell 5.1
        # silently exits with code 0 without running the script when no console is attached.
        # CREATE_NO_WINDOW allocates a hidden console so the script runs reliably with no popup window.
        flags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        proc = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
                str(script_path),
            ],
            cwd=str(temp_dir),
            creationflags=flags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.05)
        rc = proc.poll()
        if rc is not None and rc != 0:
            raise RuntimeError(f"Updater helper exited immediately with code {rc}.")

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
    app = MTFLauncherApp(initial_tab=args.tab, shot_path=args.shot, skip_update_check=args.check)
    if args.check:
        app.update_idletasks()
        app.destroy()
        print("MTFLauncher check: OK")
        return 0
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
