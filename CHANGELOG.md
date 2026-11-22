# Changelog

## MTF-ShadowRacket Alpha 0.1.4

This update fixes the persistent blue/cyan tint ("blue filter") seen across 3D courts and characters on end-user release installs, and fixes **MTFLauncher**'s built-in auto-updater so future releases download, apply, clean up, and restart reliably.

■ Major Updates

- Implemented single-invocation explicit `gl_Layer` (`0x64`) lowering in `ns2_xlate` and quad-to-triangle promotion for native passthrough geometry shaders in Vulkan draw execution and pipeline validation, restoring accurate 64-slice 3D atmospheric fog LUT generation on every GPU and clean release install.
- Rebuilt **MTFLauncher**'s self-updater with reliable hidden PowerShell execution, UTF-8 BOM script handling for accented paths, Windows long-path (`\\?\`) support, delta staging, atomic file swaps with lock retries and rollback, `logs\update.log` diagnostics, automatic stale `.mtf-update-*` cleanup, and anti-loop failure recovery.

■ Bug Fixes

- Fixed the blue/cyan color filter over courts, stadiums, and characters on clean release installs where the 3D aerial-perspective fog LUT geometry shader was previously skipped on quad draws, causing slice 0 to be overwritten by far-horizon sky blue.
- Fixed **MTFLauncher**'s auto-updater silently exiting without applying downloaded files and accumulating leftover `.mtf-update-*` folders on each launch.
- Fixed the updater skipping `_`-prefixed bundled Python files (`__init__.py`, `_*.pyd`) and failing on deeply nested or accented install folders.
- Hardened **MTFLauncher**'s automatic `mtf.exe` and `ns2_xlate.exe` runtime refresh after updates by hashing `runtime/libmtfrt.a` and syncing `bin/ns2_xlate.*` consistently.

■ Known Issues

- Minor graphical and gameplay issues remain in some modes.

■ Install & Update

- **New install:** Run `SteelTemple-MTF-ShadowRacket-Alpha-0.1.4-Full-Setup-Wizard.exe`, open **MTFLauncher**, pick your Mario Tennis Fever 1.1.1 dump folder, NUP-extracted tree, or `.nup`, click **Verify & Build mtf.exe**, and press **Play**.
- **Portable:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.4-Portable-StandAlone.zip` anywhere and launch `MTFLauncher.exe`.
- **Update from Alpha 0.1.3b or earlier:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.4-Update.zip` over your existing install folder once (or run the `Alpha 0.1.4` Setup Wizard) so the fixed `MTFLauncher.exe` is in place — your dump, saves, and personal `mtf.ini` remain intact, **MTFLauncher** refreshes `mtf.exe` and `ns2_xlate.exe` automatically on launch, and future releases will auto-update cleanly.

## MTF-ShadowRacket Alpha 0.1.3b — AMD Hotfix

This hotfix resolves shadow cascade rendering issues on AMD Radeon GPUs and fresh installs without bundled caches, restores true native `2160p (4K)` internal resolution without bottom-screen corruption, eliminates the brief black square around Mario when entering the court, and fixes default `Frame Generation = Off` handling as well as non-English locale fallbacks. Existing Alpha 0.1.2+ installs automatically update `mtf.exe` and `ns2_xlate.exe` on launcher startup after applying `Update.zip`.

■ Major Updates

- Implemented full 16-invocation `ViewportMask` geometry shader multicast (`ViewportIndex` + `Layer`) in `ns2_xlate` and Vulkan pipeline validation so cascaded court, stadium, and character shadows render accurately on AMD Radeon GPUs and cold shader-cache installs.
- Added AMD `D24`-on-`D32_SFLOAT` constant shadow depth-bias rescaling on GPUs without `VK_EXT_depth_bias_control`.
- Restored native `2160p (4K)` internal resolution (`3840x2160` swapchain and max-framebuffer promotion) in both the in-game Graphics menu (`F1`) and **MTFLauncher**.
- Added automatic fast `mtf.exe` and `ns2_xlate.exe` runtime refresh in **MTFLauncher** on launch after installing an `Update.zip`.

■ Bug Fixes

- Fixed missing or collapsed shadow cascades on AMD GPUs and fresh installs, including lowered passthrough geometry shader cache matching.
- Fixed the brief black square around Mario on court entry by far-clearing un-owned `1024x1024` guest-memory shadow targets before first use.
- Fixed cold shader-compile hitches and audio crackle on court entry by pre-warming `ns2_xlate` asynchronously at boot and increasing default audio prefill to `35 ms`.
- Fixed `Frame Generation = Off` (`fg_mode = off` and zero-config fresh profiles) still engaging Super Motion.
- Fixed `nn::vi::QueryDisplayBufferMaxResolution` stack corruption and `2560x1440` swapchain clamping that corrupted the lower portion of the frame at `2160p`.
- Fixed Windows Russian locale (`ru-RU`) falling back to mixed Japanese UI text instead of `en-US`.

■ Known Issues

- Minor graphical and gameplay issues remain in some modes.

■ Install & Update

- **New install:** Run `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3b-Full-Setup-Wizard.exe`, open **MTFLauncher**, pick your Mario Tennis Fever 1.1.1 dump folder, NUP-extracted tree, or `.nup`, click **Verify & Build mtf.exe**, and press **Play**.
- **Portable:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3b-Portable-StandAlone.zip` anywhere and launch `MTFLauncher.exe`.
- **Update:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3b-Update.zip` over an existing Alpha 0.1.1+ install (or use **MTFLauncher**'s built-in auto-updater) — your existing dump, saves, and personal `mtf.ini` remain intact, and **MTFLauncher** refreshes `mtf.exe` automatically on startup.

## MTF-ShadowRacket Alpha 0.1.3

This update pairs the complete Mario Tennis Fever 1.1.1 native runtime, internal resolution scaling, and world-locked character/court shadows with automatic runtime `subsdk0` module synthesis, faster single-pass `.nup` extraction, live progress tracking, and split `.nup` setup support. Standard 4-file ExeFS dumps and `.nup` packages (with RomFS `.nrr`), combined containers, and sibling base/update `.nup` pairs all verify and build seamlessly into self-contained installs.

■ Major Updates

- Restored full Mario Tennis Fever 1.1.1 native runtime support (`mtf.exe`), including internal frame resolution scaling (`Original ~960p`, `720p`, `900p`, `1080p`, and `1440p`), full-precision D24 shadow handling, and Championship Turf in-game settings (`F1` / `Esc` / `Back + Y`).
- Restored missing Lakitu, far-player, umpire chair, bench, and sideline shadows across Stadium Court, Outdoor Practice, and Academy Lobby via SPIR-V `Layer = ViewportIndex` cascade injection, synchronized occlusion query readbacks, and viewport swizzle tracking.
- **MTFLauncher** now automatically synthesizes `subsdk0` from standard 4-file ExeFS + RomFS `.nrr` dumps and `.nup` containers during setup — no separate `subsdk0` extraction step required.
- Combined base+update `.nup` extraction merges overlays in a single pass so files replaced by the update are extracted once instead of twice, while **MTFLauncher** streams live progress, locks setup controls while unpacking, and reuses completed extractions automatically.
- NUP `--overlay-update` and **Browse .NUP…** match base (…000) and update (…800) packages by application title family across both single-container `.nup` archives and split base/update `.nup` files in the same folder.
- Verified ExeFS modules and `romfs-index.bin` are staged directly inside the install folder so `mtf.exe` runs self-contained.
- Hardened `.nup` file finalization and extract folder cleanup against Windows Defender and file-sharing locks (`WinError 5` / `WinError 32`).

■ Bug Fixes

- Fixed far-distance Lakitu, opponent, umpire chair, and sideline shadows culling early or collapsing onto a single cascade (`SetViewportSwizzles` Y-flip polarity, `FORCE_UNORM` depth bias, `InvalidateMappedRange` occlusion query sync, non-precise OQ defaults with empty-report floor, `clamp_border` depth heuristic, and SPIR-V `BuiltIn Layer = BuiltIn ViewportIndex` injection).
- Fixed changing `Internal resolution` (`1440p`, *after restart*) in the `F1` Settings menu cropping the live frame before restarting; `--shot` PNG captures now also write opaque alpha cleanly.
- Fixed setup failing with `missing subsdk0` on standard Mario Tennis Fever 1.1.1 dumps and `.nup` packages where `subsdk0` is unpacked at runtime from RomFS `.nrr`.
- Fixed `[WinError 32]` sharing violations and stalled 0% progress bars when clicking **Verify & Build mtf.exe** while a `.nup` unpack was still in progress.
- Fixed builds producing the wrong target layout or omitting Mario Tennis Fever 1.1.1 runtime resolution, shader, and shadow fixes.
- Fixed NUP extraction aborting with `PermissionError` (`WinError 5`) when finalizing extracted files under Windows Defender scans.
- Fixed Launcher builds leaving `romfs-index.bin` or verified ExeFS outside the install root directory.

■ Known Issues

- Minor graphical and gameplay issues remain in some modes.

■ Install & Update

- **New install:** Run `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3-Full-Setup-Wizard.exe`, open **MTFLauncher**, pick your Mario Tennis Fever 1.1.1 dump folder, NUP-extracted tree, or `.nup`, click **Verify & Build mtf.exe**, and press **Play**.
- **Portable:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3-Portable-StandAlone.zip` anywhere and launch `MTFLauncher.exe`.
- **Update:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3-Update.zip` over an existing Alpha 0.1.1+ install (or use MTFLauncher's built-in updater) — your existing saves and settings remain intact.

## MTF-ShadowRacket Alpha 0.1.2

This hotfix streamlines setup for update-only and NUP-only Mario Tennis Fever 1.1.1 dumps: complete update trees verify and build without requiring a separate base folder, while base+update overlays apply automatically when both are present. MTFLauncher also checks GitHub Releases and can install updates directly.

■ Major Updates

- Update-only ExeFS and `.nup` dumps verify directly without requiring a separate base folder when all modules are present.
- `tools/extract_nup.py --overlay-update` overlays a matching-title base when present, or extracts the update package on its own.
- Clearer missing-module error messages (such as `subsdk0`) during dump verification.
- MTFLauncher checks GitHub Releases and can download and install `SteelTemple-MTF-ShadowRacket-*-Update.zip` automatically.

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
