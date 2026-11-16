# Changelog

All notable changes to **[STS78721/MTF-ShadowRacket](https://github.com/STS78721/MTF-ShadowRacket)** (**Mario Tennis Fever PC**) are documented in this file.

---

## [Alpha 0.1.0] - 2026-11-16

### First Public MTF-ShadowRacket Release Package (`Alpha 0.1.0`)

- **Unified Version Branding Everywhere (`Alpha 0.1.0`):**
  - Displays `Alpha 0.1.0` across [`VERSION`](VERSION), **MTFLauncher** window title/banner/footer, the **Setup Wizard** (`Full-Setup-Wizard.exe`) & Windows Apps entry, the **in-game F1 Settings Menu**, [`README.md`](README.md), and [`CHANGELOG.md`](CHANGELOG.md).
- **Working Internal Resolution Scaling (`NS2_RESOLUTION`):**
  - Hooked Mario Tennis Fever's frame dimension descriptor (`subsdk0` `0x125eb98` + `f_700205e8fc` wrapper in `runtime/resolution.c`) and clamped swapchain/crop extents cleanly in `runtime/nvn_api_obj.c`.
  - Unlocked verified internal resolutions: **Original (`1706x960`)**, **720p (`1280x720`)**, **900p (`1600x900`)**, **1080p (`1920x1080`)**, and **1440p (`2560x1440`)**, clamping out unsupported `2160p` guest pool overflows.
- **Story Mode Shadows & Cutscene Stability:**
  - Defaulted `PIPE_SKIP="any"` (`runtime/cfg.c`) and bounded pipeline wait budgets in `runtime/vk_exec_draw.c` (`300 ms` fullscreen/depth wait budget, `150 ms` one-shot cap) to eliminate Story Mode flickering shadow squares and cutscene stalls.
  - Added in-memory prepared SPIR-V index in `runtime/gfx_shader.c` (`bsearch`) replacing hot per-draw disk stat calls, plus `cfg_version()`-cached `NS2_GPU_DESWIZZLE` lookups in `runtime/vk_astc.c`.
- **Mario Tennis Fever Championship Turf Setup Wizard & Launcher:**
  - Added native standalone SDL3 + Dear ImGui + zstd Setup Wizard (`tools/installer_mtf/installer.cpp`) with animated Championship Turf stripes, court chalk lines, bouncing optic-yellow tennis ball backdrop, custom `mtf.ico` / `mtf.png` branding, HKCU install/uninstall, Desktop & Start Menu shortcuts (`MTF ShadowRacket.lnk`), and update-safe install manifests.
  - Built themed **MTFLauncher** (`launcher/MTFLauncher.py`) featuring one-step ExeFS SHA-256 verification, RomFS packing (`mtf_pack_romfs.py`), ARM64->C lifting (`recomp/gen.py`), standalone LLVM+Ninja compilation (`build_game.py` -> `mtf.exe`), Display/Resolution/Input settings editor, Mod & Save Backup tools, and **Reset to Default Profile**.
- **Clean Zero-Config Client Defaults (`recomp-defaults`):**
  - Strictly excludes developer `.ini` files, saves, shader caches, game assets (`exefs/`, `romfs/`, `generated/`, `spirv/`), and non-MTF assets from release artifacts.
  - Defaults `mtf.ini.example` and first-run `runtime/cfg.c` to safe baseline defaults (`1920x1080` windowed, `original` ~960p internal, `fsr`, `sharpness = 80`, `fg_mode = off`, `color_preset = default`, `fps_limit = 60`, `pipe_skip = any`).
  - Added explicit MTF detection in `tools/build_game.py` so installing into any user-chosen folder name (e.g. `Mario Tennis Fever PC`) still links `-Wl,--wrap,f_700205e8fc`, `mtf.rc`/`mtf.ico`, `mtf.map`, and `ns2_xlate.exe`.
