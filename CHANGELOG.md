# Changelog

## MTF-ShadowRacket Alpha 0.1.3

MTF-ShadowRacket Alpha 0.1.3

This hotfix makes Browse .NUP… reliable for real Mario Tennis Fever 1.1.1 containers: base and update packages are matched by title family (application …000 with update …800), so unchanged ExeFS modules such as `subsdk0` are kept from the base when the update is sparse. Windows antivirus locks during extract finalize remain hardened. MTFLauncher still checks GitLab Releases and can install the latest Update.zip automatically. Personal dumps, saves, and mtf.ini stay on the PC.

■ Major Updates

- NUP `--overlay-update` matches base and update by application title family, not exact title ID, so base+update containers overlay correctly.
- Sparse update ExeFS trees keep unchanged modules (for example `subsdk0`) from the matching base package inside the same `.nup`.
- Hardened `tools/extract_nup.py` file finalize: retries when Windows briefly denies replace (common under Downloads), then falls back to copy so every ExeFS/RomFS entry is written.
- Update-only NUP / ExeFS paths remain first-class when the update package already contains every required module.

■ Bug Fixes

- Fixed Browse .NUP… leaving `work\nup-extract\exefs` missing `subsdk0` when the `.nup` held both a base (…000) and an update (…800) — exact title matching skipped the base overlay.
- Fixed Browse .NUP… / NUP extract aborting with PermissionError (WinError 5) while renaming temporary extract files onto their final names (for example `main.npdm`).

■ Known Issues

- Far-distance Lakitu shadows during wide camera shots can still cull early at range.
- Minor graphical and gameplay issues remain in some modes.

■ Install & Update

- **New install:** Run `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3-Full-Setup-Wizard.exe`, open **MTFLauncher**, pick your Mario Tennis Fever 1.1.1 dump folder, NUP-extracted tree, or `.nup`, click **Verify & Build mtf.exe**, and press **Play**.
- **Portable:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3-Portable-StandAlone.zip` anywhere and launch `MTFLauncher.exe`.
- **Update:** Apply `SteelTemple-MTF-ShadowRacket-Alpha-0.1.3-Update.zip` over an existing Alpha 0.1.1 (or later) folder, or run the Setup Wizard over it. From Alpha 0.1.2 onward, MTFLauncher can pull Update.zip from GitLab Releases automatically — open the launcher (or use Check for Updates) to pick up this build. Dumps, saves, and personal `mtf.ini` stay on the PC.

## MTF-ShadowRacket Alpha 0.1.2

MTF-ShadowRacket Alpha 0.1.2

This hotfix makes update-only and NUP-only Mario Tennis Fever 1.1.1 dumps first-class for setup: complete update trees verify and build without a separate base folder, while base+update overlays still apply when both are present. MTFLauncher checks GitLab Releases and can install the latest Update.zip automatically. Personal dumps, saves, and mtf.ini stay on the PC.

■ Major Updates

- Update-only ExeFS / NUP paths are first-class: complete update trees verify without a base folder.
- `tools/extract_nup.py --overlay-update` overlays a matching-title base when present, otherwise extracts the update alone.
- Clearer missing-module messages (e.g. `subsdk0`) that do not require a parent base dump.
- MTFLauncher checks GitLab Releases (`permalink/latest`) and auto-installs `SteelTemple-MTF-ShadowRacket-*-Update.zip` when a newer build is available.

■ Bug Fixes

- Fixed Portable Alpha 0.1.1 messaging that directed update-only setups to a parent dump after Browse .NUP… / `work\nup-extract`.
- NUP overlay now matches the update’s title ID when choosing a base package (avoids wrong-title bases in multi-game containers).

■ Known Issues

- Far-distance Lakitu shadows during wide camera shots can still cull early at range.
- Minor graphical and gameplay issues remain in some modes.

■ Install & Update

- **New install:** Run `SteelTemple-MTF-ShadowRacket-Alpha-0.1.2-Full-Setup-Wizard.exe`, open **MTFLauncher**, pick your Mario Tennis Fever 1.1.1 dump folder, NUP-extracted tree, or `.nup`, click **Verify & Build mtf.exe**, and press **Play**.
- **Portable:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.2-Portable-StandAlone.zip` anywhere and launch `MTFLauncher.exe`.
- **Update:** Apply `SteelTemple-MTF-ShadowRacket-Alpha-0.1.2-Update.zip` over an existing Alpha 0.1.1 (or later) folder, or run the Setup Wizard over it. From Alpha 0.1.2 onward, MTFLauncher can pull Update.zip from GitLab Releases automatically. Dumps, saves, and personal `mtf.ini` stay on the PC.

## MTF-ShadowRacket Alpha 0.1.1

MTF-ShadowRacket Alpha 0.1.1

This patch makes setup from real Switch 2 dumps reliable: NUP-extracted folders and `.nup` containers are understood correctly, incomplete update ExeFS trees no longer fail on missing modules like `subsdk0`, and the wrong game version is rejected with a clear message. Fresh installs stay on safe, hardware-agnostic defaults.

■ Major Updates

- Fixed dump setup so NUP-extracted trees with `updates\<version>\exefs` are merged over the base ExeFS/RomFS before verify and build (covers missing `subsdk0` and similar overlay gaps).
- Added **Browse .NUP…** in MTFLauncher: extracts your `.nup` with base + newest update overlay (`tools/extract_nup.py --overlay-update`) and fills ExeFS/RomFS automatically.

■ New & Improvements

○ Setup & Dump Detection

- Auto-detects nested `[NUP]` / `*-extracted` dump folders, not only a flat `exefs` + `romfs` pair.
- Clearer SHA-256 errors when `main` (or other ExeFS files) are not Mario Tennis Fever **1.1.1**, including guidance when an update-only path was selected.

○ Defaults & Shipping

- Reset `mtf.ini.example` to hardware-agnostic safe defaults (`1920x1080` windowed, Original internal resolution, FSR, Frame Generation Off, 60 FPS). Personal high settings are not shipped.
- Personal `mtf.ini` / other user inis stay local and are ignored by git; releases never package them.

■ Bug Fixes

- Fixed setup failing with **Missing ExeFS file: …\updates\<ver>\exefs\subsdk0** on otherwise valid NUP extracts.
- Fixed cryptic short SHA mismatch dialogs that did not explain the 1.1.1 requirement or NUP overlay path.

■ Known Issues

- Far-distance Lakitu shadows during wide camera shots can still cull early at range.
- Minor graphical and gameplay issues remain in some modes.

■ Install & Update

- **New install:** Run `SteelTemple-MTF-ShadowRacket-Alpha-0.1.1-Full-Setup-Wizard.exe`, open **MTFLauncher**, pick your Mario Tennis Fever 1.1.1 dump folder, NUP-extracted tree, or `.nup`, click **Verify & Build mtf.exe**, and press **Play**.
- **Portable:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.1-Portable-StandAlone.zip` anywhere and launch `MTFLauncher.exe`.
- **Update:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.1-Update.zip` over an existing folder or run the Setup Wizard over it. Your dump, saves, and personal `mtf.ini` stay on your PC.

Your dump, saves, and personal settings stay on your PC.

## MTF-ShadowRacket Alpha 0.1.0

MTF-ShadowRacket Alpha 0.1.0

The first public release of MTF-ShadowRacket brings Mario Tennis Fever natively to Windows PC with the Championship Turf look across the setup wizard, launcher, and F1 settings menu, working internal resolution scaling up to 1440p, and Story Mode cutscene and shadow fixes.

■ Major Updates

- Initial Alpha release (`Alpha 0.1.0`), translating Mario Tennis Fever's ARM64 code into a native Windows executable (`mtf.exe`) over Vulkan 1.3.
- Added the standalone Windows Setup Wizard (`SteelTemple-MTF-ShadowRacket-Alpha-0.1.0-Full-Setup-Wizard.exe`) and `MTFLauncher` in the Mario Tennis Fever Championship Turf theme with bundled LLVM, Ninja, and Python 3.14 so users can verify and build their dump with no external developer tools installed.

■ New & Improvements

○ Graphics & Resolution

- Added working internal resolution selection (`Original ~960p`, `720p`, `900p`, `1080p`, and `1440p`) with full-frame swapchain crop clamping.
- Added AMD FSR 1.0 edge sharpening, Bilinear scaling, Frame Generation modes (`off`, `msm_fg`, `fsr3_fg`, `xefg`), and colour presets (`default`, `vivid`, `clarity`).
- Added out-of-the-box neutral defaults (`1920x1080` windowed, `Original` internal resolution, `FSR`, `Frame Generation Off`, `60 FPS`) so systems with different GPUs start smoothly without manual configuration.

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
- **Update:** Extract `SteelTemple-MTF-ShadowRacket-Alpha-0.1.0-Update.zip` over an existing folder or run the Setup Wizard over it.

Your dump, saves, and personal settings stay on your PC.
