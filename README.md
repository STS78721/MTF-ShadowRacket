# MTF-ShadowRacket (`Alpha 0.1.0`)

[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)

**Mario Tennis Fever** (Nintendo Switch 2) running natively on Windows PC as a static recompilation — **not an emulator**. Built on **Universal NS2 to PC** (`STS78721/MTF-ShadowRacket`).

> [!IMPORTANT]
> **No copyrighted game files, keys, saves, or personal settings are included.**
> Every client starts on a clean zero-config default profile (`1920x1080` windowed, `original` internal `~960p`, FSR Upscaler, Frame Gen Off, 60 FPS) and compiles `mtf.exe` locally from their own Nintendo Switch 2 dump of **Mario Tennis Fever 1.1.1**.

---

## Highlights (`Alpha 0.1.0`)

- **Native ARM64-to-x86-64 Recompilation:** `rtld`, `main`, `subsdk0`, and `sdk` are lifted ahead of time to native C and linked against a Horizon OS + NVN 2 Vulkan 1.3 runtime.
- **Native Windows Setup Wizard & MTFLauncher:** One-step **Mario Tennis Fever Championship Turf** Setup Wizard (`SteelTemple-MTF-ShadowRacket-Alpha-0.1.0-Full-Setup-Wizard.exe`) with HKCU install/uninstall, Desktop & Start Menu shortcuts, bundled LLVM-MinGW / Ninja / Python 3.14 toolchain, SHA-256 dump verification, and mod/save backup management.
- **True Internal Resolution Scaling:** Supports `original` (`1706x960`), `720p` (`1280x720`), `900p` (`1600x900`), `1080p` (`1920x1080`), and `1440p` (`2560x1440`) cleanly without black-bar cropping or guest memory corruption — switchable in `MTFLauncher` or live/on restart inside the in-game **F1 Settings Menu**.
- **Clean Client Defaults (`recomp-defaults`):** Never bundles developer `.ini` overrides or saves; weak and high-end GPUs alike boot into a neutral baseline profile and can scale upward safely.
- **Smooth Shaders & Story Mode Fixes:** Pre-indexed SPIR-V shader cache lookups, bounded pipeline wait budgets, and cached ASTC GPU deswizzle toggles eliminate Story Mode cutscene stalls and flickering shadow squares.
- **Controller & Display Ready:** Supports Xbox, DualSense, Switch / Switch 2 Pro controllers, Keyboard, FSR / Bilinear / SMRS upscaling, Frame Generation modes (`off`, `msm_fg`, `fsr3_fg`, `xefg`), and Tennis Court UI theme.

---

## Quick Start (End Users)

1. Download **`SteelTemple-MTF-ShadowRacket-Alpha-0.1.0-Full-Setup-Wizard.exe`** (or extract **`Portable-StandAlone.zip`**).
2. Run the Setup Wizard and choose an install folder (for example `C:\Games\Mario Tennis Fever PC`).
3. Open **MTFLauncher** -> **SETUP FROM DUMP** tab.
4. Select your dumped **Mario Tennis Fever 1.1.1** `exefs/` and `romfs/` folders and click **VERIFY & BUILD MTF.EXE**.
5. Press **PLAY MARIO TENNIS FEVER**. Press **F1** (or `Back + Y` on controller) anytime in-game for the Settings overlay.

---

## Building From Source (Developers)

```powershell
# 1. Verify zero copyrighted assets or build artifacts in repo
python tools\check_content.py

# 2. Lift ExeFS modules (Mario Tennis Fever 1.1.1) with MTF patches
.venv\Scripts\python.exe recomp\gen.py --exefs "<dump>\exefs" --out generated\mtf111 --patches recomp\patches-mtf111.txt

# 3. Pack RomFS
.venv\Scripts\python.exe tools\mtf_pack_romfs.py --dir "<dump>\romfs" --out build\extracted\mtf111\romfs

# 4. Build mtf.exe cleanly
.venv\Scripts\python.exe tools\build_game.py --version mtf111 --gen generated\mtf111 --exefs "<dump>\exefs" --romfs build\extracted\mtf111\romfs

# 5. Build the full MTF-ShadowRacket release package (Wizard EXE + Portable Zip + Update Zip)
.venv\Scripts\python.exe tools\build_mtf_release.py
```

### Release Versioning Policy

The single source of truth for the release string is [`VERSION`](VERSION). Every release updates:
- [`VERSION`](VERSION) & [`launcher/mtf_version.txt`](launcher/mtf_version.txt) (propagated into **MTFLauncher**, **Setup Wizard**, Windows Installed Apps, and **in-game F1 Menu**)
- [`README.md`](README.md) & [`CHANGELOG.md`](CHANGELOG.md)

---

## Credits & Licensing

Built on open-source Nintendo Switch / Switch 2 static recompilation and Vulkan research by **[MKW-THWOMP](https://github.com/STS78721/MKW-THWOMP)**, **Universal NS2 to PC**, **Eglantine** (Ampere SM86 lowering), **Ryujinx**, **MacNativeGames**, **SDL3**, **Dear ImGui**, **Vulkan Memory Allocator (VMA)**, **libopus**, **libvpx**, **dav1d**, **zstd**, and **FidelityFX FSR**.

Licensed under the [GNU GPL v3 or later](LICENSE) with MIT/permissive third-party notices in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Independent non-commercial research project, not affiliated with Nintendo.
