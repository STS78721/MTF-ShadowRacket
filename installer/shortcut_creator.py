"""Desktop shortcut creator for MTF ShadowRacket (Mario Tennis Fever PC Recompiled)."""

import os
import subprocess


def create_desktop_shortcut(game_dir: str, shortcut_name: str = "MTF ShadowRacket", target_exe: str = None) -> bool:
    """Creates a Windows desktop shortcut pointing to MTFLauncher.exe (or mtf.exe) in game_dir."""
    try:
        desktop_dir = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
        if not os.path.exists(desktop_dir):
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")

        shortcut_path = os.path.join(desktop_dir, f"{shortcut_name}.lnk")

        # Prefer MTFLauncher.exe if present
        if target_exe:
            chosen_exe = os.path.join(game_dir, target_exe)
        elif os.path.isfile(os.path.join(game_dir, "MTFLauncher.exe")):
            chosen_exe = os.path.join(game_dir, "MTFLauncher.exe")
        elif os.path.isfile(os.path.join(game_dir, "..", "MTFLauncher.exe")):
            chosen_exe = os.path.abspath(os.path.join(game_dir, "..", "MTFLauncher.exe"))
        else:
            chosen_exe = os.path.join(game_dir, "mtf.exe")

        icon_path = os.path.join(game_dir, "mtf.ico")
        if not os.path.exists(icon_path):
            icon_path = chosen_exe

        ps_script = f"""
        $ws = New-Object -ComObject WScript.Shell
        $s = $ws.CreateShortcut('{shortcut_path}')
        $s.TargetPath = '{chosen_exe}'
        $s.WorkingDirectory = '{game_dir}'
        $s.IconLocation = '{icon_path},0'
        $s.Description = 'Play Mario Tennis Fever PC (MTF ShadowRacket)'
        $s.Save()
        """

        res = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                             capture_output=True, text=True, timeout=10)
        return res.returncode == 0 and os.path.exists(shortcut_path)
    except Exception as e:
        print(f"Error creating shortcut: {e}")
        return False
