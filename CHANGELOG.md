# Changelog

## MTF-ShadowRacket Alpha 0.1.3

This update pairs the complete Mario Tennis Fever 1.1.1 native runtime, internal resolution scaling, and shadow/grass fixes with faster single-pass `.nup` extraction, live progress tracking, and split `.nup` setup support. Base (…000) and update (…800) packages match automatically by title family whether stored in one `.nup` container or two sibling `.nup` files in the same folder, and built `mtf.exe` installs stay self-contained inside the install folder.

■ Major Updates

- Restored full Mario Tennis Fever 1.1.1 native runtime support (`mtf.exe`), including internal frame resolution scaling (`Original ~960p`, `720p`, `900p`, `1080p`, and `1440p`), full-precision D24 shadow handling, and Championship Turf in-game settings (`F1` / `Esc` / `Back + Y`).
- Combined base+update `.nup` extraction now merges overlays in a single pass so files replaced by the update are extracted once instead of twice.
- **MTFLauncher** streams live `.nup` extract progress, locks setup controls while unpacking, and reuses completed extractions automatically when clicking **Verify & Build mtf.exe**.
- NUP `--overlay-update` and **Browse .NUP…** match base (…000) and update (…800) packages by application title family across both single-container `.nup` archives and split base/update `.nup` files in the same folder.
- Verified ExeFS modules and `romfs-index.bin` are staged directly inside the install folder so `mtf.exe` runs self-contained.
- Hardened `.nup` file finalization and extract folder cleanup against Windows Defender and file-sharing locks (`WinError 5` / `WinError 32`).

■ Bug Fixes

- Fixed `[WinError 32]` sharing violations and stalled 0% progress bars when clicking **Verify & Build mtf.exe** while a `.nup` unpack was still in progress.
- Fixed builds producing the wrong target layout or omitting Mario Tennis Fever 1.1.1 runtime resolution, shader, and shadow fixes.
- Fixed **Browse .NUP…** leaving ExeFS missing unchanged modules such as `subsdk0` on combined base+update containers or split base/update `.nup` files in the same folder.
- Fixed NUP extraction aborting with `PermissionError` (`WinError 5`) when finalizing extracted files under Windows Defender scans.
- Fixed Launcher builds leaving `romfs-index.bin` or verified ExeFS outside the install root directory.

■ Known Issues

- Far-distance Lakitu shadows during wide camera shots can still cull early at range.
- Minor graphical and gameplay issues remain in some modes.

■ Install & Update

- **New install:** Run `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3-Full-Setup-Wizard.exe`, open **MTFLauncher**, pick your Mario Tennis Fever 1.1.1 dump folder, NUP-extracted tree, or `.nup`, click **Verify & Build mtf.exe**, and press **Play**.
- **Portable:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3-Portable-StandAlone.zip` anywhere and launch `MTFLauncher.exe`.
- **Update:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3-Update.zip` over an existing Alpha 0.1.1+ install (or use MTFLauncher's built-in updater) — your existing saves and settings remain intact.

## MTF-ShadowRacket Alpha 0.1.2

This hotfix streamlines setup for update-only and NUP-only Mario Tennis Fever 1.1.1 dumps: complete update trees verify and build without requiring a separate base folder, while base+update overlays apply automatically when both are present. MTFLauncher also checks GitLab Releases and can install updates directly.

■ Major Updates

- Update-only ExeFS and `.nup` dumps verify directly without requiring a separate base folder when all modules are present.
- `tools/extract_nup.py --overlay-update` overlays a matching-title base when present, or extracts the update package on its own.
- Clearer missing-module error messages (such as `subsdk0`) during dump verification.
- MTFLauncher checks GitLab Releases and can download and install `SteelTemple-MTF-ShadowRacket-*-Update.zip` automatically.

■ Bug Fixes

- Fixed Alpha 0.1.1 setup guidance that pointed update-only `.nup` extracts to a parent base folder.
- NUP overlay now matches the update's title ID when selecting a base package in multi-title containers.

■ Known Issues

- Far-distance Lakitu shadows during wide camera shots can still cull early at range.
- Minor graphical and gameplay issues remain in some modes.

■ Install & Update

- **New install:** Run `SteelTemple-MTF-ShadowRacket-Alpha-0.1.2-Full-Setup-Wizard.exe`, open **MTFLauncher**, pick your Mario Tennis Fever 1.1.1 dump folder, NUP-extracted tree, or `.nup`, click **Verify & Build mtf.exe**, and press **Play**.
- **Portable:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.2-Portable-StandAlone.zip` anywhere and launch `MTFLauncher.exe`.
- **Update:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.2-Update.zip` over an existing Alpha 0.1.1+ install (or use MTFLauncher's built-in updater) — your existing saves and settings remain intact.

## MTF-ShadowRacket Alpha 0.1.1

This patch improves Switch 2 dump detection and setup reliability: NUP-extracted trees and `.nup` containers are handled directly, sparse update ExeFS trees merge unchanged modules such as `subsdk0` from matching base folders, and mismatched game versions report clear diagnostics.

■ Major Updates

- Fixed dump setup so NUP-extracted trees with `updates\<version>\exefs` merge over the base ExeFS and RomFS before verification and building (covering unchanged modules such as `subsdk0`).
- Added **Browse .NUP…** in MTFLauncher to extract `.nup` containers with base + newest update overlay (`tools/extract_nup.py --overlay-update`) automatically.

■ New & Improvements

○ Setup & Dump Detection

- Auto-detects nested `[NUP]` and `*-extracted` dump folders in addition to flat `exefs` and `romfs` layouts.
- Clearer SHA-256 diagnostics when ExeFS files do not match Mario Tennis Fever **1.1.1**.

○ Default Graphics Baseline

- Fresh installs start on a balanced 1080p windowed baseline (`1920x1080` windowed, Original internal resolution, FSR enabled, Frame Generation off, 60 FPS).
- Existing `mtf.ini` files and save data are preserved across updates.

■ Bug Fixes

- Fixed setup failing with **Missing ExeFS file: …\updates\<ver>\exefs\subsdk0** on NUP-extracted trees.
- Replaced terse SHA mismatch dialogs with clearer guidance on the 1.1.1 dump requirement.

■ Known Issues

- Far-distance Lakitu shadows during wide camera shots can still cull early at range.
- Minor graphical and gameplay issues remain in some modes.

■ Install & Update

- **New install:** Run `SteelTemple-MTF-ShadowRacket-Alpha-0.1.1-Full-Setup-Wizard.exe`, open **MTFLauncher**, pick your Mario Tennis Fever 1.1.1 dump folder, NUP-extracted tree, or `.nup`, click **Verify & Build mtf.exe**, and press **Play**.
- **Portable:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.1-Portable-StandAlone.zip` anywhere and launch `MTFLauncher.exe`.
- **Update:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.1-Update.zip` over an existing install or run the Setup Wizard over it — your existing saves and settings remain intact.

## MTF-ShadowRacket Alpha 0.1.0

The first public release of MTF-ShadowRacket brings Mario Tennis Fever natively to Windows PC with the Championship Turf look across the setup wizard, launcher, and F1 settings menu, internal resolution scaling up to 1440p, and Story Mode cutscene and shadow fixes.

■ Major Updates

- Initial Alpha release (`Alpha 0.1.0`), translating Mario Tennis Fever's ARM64 code into a native Windows executable (`mtf.exe`) over Vulkan 1.3.
- Added the standalone Windows Setup Wizard (`SteelTemple-MTF-ShadowRacket-Alpha-0.1.0-Full-Setup-Wizard.exe`) and `MTFLauncher` in the Mario Tennis Fever Championship Turf theme with bundled LLVM, Ninja, and Python 3.14 so players can verify and build their dump with no external developer tools required.

■ New & Improvements

○ Graphics & Resolution

- Added internal resolution selection (`Original ~960p`, `720p`, `900p`, `1080p`, and `1440p`) with full-frame swapchain crop clamping.
- Added AMD FSR 1.0 edge sharpening, Bilinear scaling, Frame Generation modes (`off`, `msm_fg`, `fsr3_fg`, `xefg`), and colour presets (`default`, `vivid`, `clarity`).
- Added balanced out-of-the-box defaults (`1920x1080` windowed, `Original` internal resolution, `FSR`, `Frame Generation Off`, `60 FPS`) so systems start smoothly across a wide range of GPUs.

○ Settings Menu & Launcher

- Added the in-game Settings menu (**F1**, **Esc**, or **Back + Y** on controller) with Tennis Court branding and Display, Graphics, Sound, Controls, System, and Advanced categories.
- Added `MTFLauncher` featuring one-step ExeFS SHA-256 verification, RomFS packing, local `mtf.exe` compilation, Display/Graphics/Input settings, Mod & Save folder shortcuts, save backups, and a one-click Reset to Default Profile option.

○ Setup Wizard

- Added the single-file native Setup Wizard with Desktop and Start Menu shortcuts, Windows Installed Apps integration (`uninstall.exe`, no administrator rights needed), and safe updates that keep existing builds, saves, `mtf.ini`, mods, and dump files intact.

■ Bug Fixes

- Fixed Story Mode cutscenes hitching and sporadic flickering black squares caused by pipeline stalls and per-draw disk shader lookups.
- Fixed internal resolution scaling leaving black border crops or overflowing guest render pools above `1440p`.
- Fixed repeated GPU texture deswizzle lookups during texture uploads.

■ Known Issues

- Far-distance Lakitu (turtle on the cloud) shadows during wide camera shots can cull early at range and remain tracked for upcoming patch updates.
- Minor graphical and gameplay issues remain in some modes and will be addressed in subsequent patches.

■ Install & Update

- **New install:** Run `SteelTemple-MTF-ShadowRacket-Alpha-0.1.0-Full-Setup-Wizard.exe`, open **MTFLauncher**, pick your Mario Tennis Fever 1.1.1 dump (`exefs` and `romfs`), click **Verify & Build mtf.exe**, and press **Play**.
- **Portable:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.0-Portable-StandAlone.zip` anywhere and launch `MTFLauncher.exe`.
- **Update:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.0-Update.zip` over an existing folder or run the Setup Wizard over it — your existing saves and settings remain intact.
