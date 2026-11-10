# Universal NS2 to PC

[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)

**Universal NS2 to PC** is a unified static recompilation engine for Nintendo Switch 2 titles (ARM64 + NVN 2 + Ampere SM86) into native x86-64 PC applications with a Vulkan 1.3 renderer. Instead of interpreting instructions at runtime, each game's `rtld`, `main`, `subsdk*`, and `sdk` binaries are lifted ahead-of-time to C, linked against a multi-game Horizon OS + NVN 2 host runtime, and configured with a modern Dear ImGui in-game overlay hooked live into resolution scaling, Docked/Handheld console state, upscalers, frame generation, and safe shader compile paths.

> [!IMPORTANT]
> **No game files or keys are included, and none ever will be.** You need your own copy dumped from your own console. Every executable is compiled locally from your own dump.

## What makes Universal NS2 to PC different

- **Single Shared Engine (`runtime/game_profile.c`):** No per-game repo forks. Title IDs (`rt_application_id`), short names (`<short>.exe`, `<short>.ini`, `logs/<short>.log`), and per-title quirk flags live in one central profile table.
- **Smart Pre-Flight Profiler (`tools/universal_ns2_to_pc.py scan`):** Before lifting or compiling C, scans `exefs/` and `romfs/` for ELF relocations (`DT_RELR`, `TLSDESC`), exact `sdk -> main/subsdk*` `nn::*` imports, ARM64 `recomp/lifter.py` decode coverage, NVN 2 proc coverage, all 9 BNSH shader slots + pipeline stage pairs, Ampere `SM86` opcodes vs `lower_to_maxwell.h`, >5K-insn stall shaders, Switch 2 `Ounc` `BNTX` textures / 256M-texel sparse hazards, and monolithic `CRA.` packs.
- **One-Command Initialize & Build:** `init` generates `tools/data/expected-<ver>.json` and lifts ARM64->C (`recomp/gen.py`); `build` compiles `<short>.exe` with MSYS2 UCRT64 Clang + Ninja.
- **Default Midnight Glass Overlay (`F1` / `Back+Y`):** Built into every binary by default with live hooks for `NS2_OPERATION_MODE` (`docked` / `handheld` + OS events `0x1e`/`0x1f` + display resolution change notification), live `NS2_OUTPUT_RES` / `NS2_RENDER_SCALE` / FSR / FXAA / SMAA / RCAS / SMRS upscaling, `NS2_RES_HOOK` toggle, `NS2_VK_NOOPT` safe shader compile flag, `FPS_LIMIT` (`30..240` + `display`), and live pipeline telemetry.

## Workflow (Scan -> Init -> Build -> Test)

```powershell
# 1. Build the NativeAOT SPIR-V translator once
python tools\build_xlate.py

# 2. Pre-flight inspect any NS2 game dump before lifting C
python tools\universal_ns2_to_pc.py scan --exefs "C:\Games\MyGame\exefs" --romfs "C:\Games\MyGame\romfs"

# 3. Generate expected metadata and lift ARM64 -> C
python tools\universal_ns2_to_pc.py init --ver mygame100 --short mygame --name "My NS2 Game" --exefs "C:\Games\MyGame\exefs" --romfs "C:\Games\MyGame\romfs"

# 4. Compile native PC binary
python tools\universal_ns2_to_pc.py build --ver mygame100 --exefs "C:\Games\MyGame\exefs" --romfs "C:\Games\MyGame\romfs"

# 5. Run baseline smoke checks before debugging F0-F5
build\mygame100\mygame.exe --selftest
build\mygame100\mygame.exe --probe-loader
build\mygame100\mygame.exe --probe-gfx-abi
build\mygame100\mygame.exe --probe-window
$env:TOTK_GPU="null"; build\mygame100\mygame.exe --boot --seconds 5
```

Or check everything via the [AI & Developer Playbook](docs/UNIVERSAL_NS2_TO_PC_PLAYBOOK.md).

## Content Guard & Layout

Everything extracted or generated goes under `build/` or `generated/`, which git ignores. Run `python tools/check_content.py` (or `--staged`) before committing to ensure zero game assets, keys, or build artifacts enter git.

## Credits, Acknowledgments & Ecosystem Foundations

Universal NS2 to PC builds directly on pioneering open-source static recompilation and Switch 2 emulation work:

### Static Recompilation Foundations
- **[TotK Recomp](https://github.com/valentderah/totk-pc-recomp)** by **valentderah**: Core ahead-of-time ARM64-to-C lifter, Horizon OS runtime, Unicorn differential test harness, and Vulkan renderer.
- **[DKB Recomp](https://github.com/sagaopc/dkb-pc-recomp)** / **Lucas-blip-png** / **sostenesfreitas**: First Switch 2 NVN 2 static recompilation port, `nn::codec` decoder, and Ampere lowering integration.
- **[MKW Recomp](https://github.com/STS78721/MKW-THWOMP)** & **[MTF Recomp](https://github.com/STS78721/MTF-ShadowRacket)**: Multi-module Switch 2 boots, 6-core Horizon synchronization, and NVN 2 texture/pipeline fixes.
- **[Hookshot](https://github.com/NotRexed)** by **NotRexed**: Rapid Switch 2 bring-up methodology (`nx2/` shader census, NVN proc auditing, hot-function splits, import classification, and `lower_test`).
- **[MacNativeGames](https://github.com/ly05010419/MacNativeGames)** by **ly05010419**: Horizon runtime, NPDM/linker improvements, and audio/pipeline architecture.
- **[LAS Recomp](https://github.com/peiikai/LASRecomp)** & **[SavageWindRecomp](https://github.com/Revivedx/SavageWindRecomp)**: AArch64 SIMD/FP and Vulkan rendering breakthroughs.

### Switch 2 GPU, Shader Translation & Emulator Research
- **[Eglantine](https://git.eden-emu.dev/Franseven/PokeDinner-a-Eglantine-Fork)** / **[notsapinho/Eglantine](https://github.com/notsapinho/Eglantine)**: Ampere-to-Maxwell SM86 lowering, SSBO read-only / bindless fixes, vertex format `B10G11R11F` & compute shared memory lowering, and `Ounc` texture insights.
- **[Fritchii](https://github.com/Frizti/Fritchii)** (`NX2_NOTES.md`): Switch 2 `nvdrv` / `nvnflinger` display format, SM86 `TEX`/`FSETP`/`SHFL` fixes, and NVN2 service layout notes.
- **[Lichii](https://github.com/zortos293/Lichii)** & **[Lichii-fg](https://github.com/cirnoice9/Lichii-fg)**: NVN2 Vulkan `robustBufferAccess2`, `vk::PipelineCreateFlagBits::eDisableOptimization`, sparse/buffer fixes, and frame generation pacing research.
- **[Mesa NAK](https://gitlab.freedesktop.org/mesa/mesa)**, **[Ryujinx](https://github.com/Ryujinx/Ryujinx)**, **[deko3d](https://github.com/devkitPro/deko3d)**, **[hactool](https://github.com/SciresM/hactool)**, **Atmosphère**, **Switchbrew**, **SDL3**, **VMA**, **Dear ImGui**, **libvpx**, **libopus**, and **zstd**.

## License

Universal NS2 to PC as a whole is under the [GNU GPL v3 or later](LICENSE) (because it carries GPL Ampere shader lowering under `runtime/third_party/eglantine/`). Files inherited from TotK Recomp keep their [MIT License](LICENSE-MIT); third-party libraries keep their respective licenses ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)). Independent non-commercial research project, not affiliated with Nintendo.
