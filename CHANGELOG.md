# Changelog

## Unreleased (Lakitu / far-shadow Orchid match)

■ Bug Fixes
- `InvalidateMappedRange` on pools/buffers waits for pending samples-passed reports (Orchid query-cache flush) so the guest reads real occlusion counts instead of a stale 0 that can cull far casters like Lakitu.
- Reverted f147c11 washout levers vs Orchid court stills: FORCE_UNORM depth-bias, D24→D32F bias rescale, empty OQ floor/provisional visible seed, non-precise OQ default, clamp_border brightness heuristic.

■ Known Issues
- Far Lakitu cast shadow still needs outdoor-court verify against `orchid-expected/04-serve-lakitu-shadow.png`.

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
