# MKW Recomp

[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)
[![Content guard](https://github.com/STS78721/MKW-THWOMP/actions/workflows/content-guard.yml/badge.svg?branch=main)](https://github.com/STS78721/MKW-THWOMP/actions/workflows/content-guard.yml)
[![Stars](https://img.shields.io/github/stars/STS78721/MKW-THWOMP?style=flat)](https://github.com/STS78721/MKW-THWOMP/stargazers)
[![Help wanted](https://img.shields.io/github/issues/STS78721/MKW-THWOMP/help%20wanted?label=help%20wanted)](https://github.com/STS78721/MKW-THWOMP/issues?q=is%3Aopen+label%3A%22help+wanted%22)
[![Discussions](https://img.shields.io/github/discussions/STS78721/MKW-THWOMP)](https://github.com/STS78721/MKW-THWOMP/discussions)

**MKW Recomp** is a static recompilation of *Mario Kart World* (Nintendo Switch 2, 2025) into a native Windows
x86-64 application with a Vulkan renderer. There is no emulator at run time: the game's ARM64 code is translated to C
ahead of time and compiled into one executable, and its graphics calls are answered by a host implementation of
NVN 2. It is built on [TotK Recomp](https://github.com/valentderah/totk-pc-recomp) and the [DKB Recomp](https://github.com/sagaopc/dkb-pc-recomp) Switch 2 work.

As far as we know, this is the first public static recompilation of Mario Kart World.

> [!IMPORTANT]
> **No game files are included, and none ever will be.** You need your own copy of *Mario Kart World*, dumped
> from your own console. Instructions for obtaining those files will not be provided. There are no downloadable
> builds: everyone builds from their own dump.

## Status

**Not playable yet.** The game boots, initializes Horizon OS services, advances through the intro sequence, renders
3D graphics with Ampere shaders lowered to Maxwell SPIR-V, but has graphical issues (lighting/textures and render pipeline).

| Phase | | State |
| --- | --- | --- |
| F0 CPU | ✅ | `main` and `sdk` lift with no unsupported instruction (ARMv8.3 pointer authentication and `LDAPR` added). All functions translate cleanly to C. |
| F1 OS | ✅ | Boots on Horizon host with Switch 2 differences: RomFS, save, audio, controller, system memory mapping. |
| F2 NVN 2 | ✅ | NVN 2 entry points answered; the game loop runs. Command buffer calls accepted and executed. |
| F3 Shaders | ✅ | Ampere shader stages go through Ampere-to-Maxwell lowering (`ISBERD`, `ISBEWR`, `SUST.D.2D` extended support) and translator to SPIR-V. |
| F4 Vulkan | ✅ | The intro and 3D scenes render. Massive 8K ASTC texture arrays auto-fallback to BC3 compression to fit within VRAM. |
| F5 Playable | 🚧 | In progress: Graphical issues, track lighting, in-race physics and gameplay controls. |

## How it works

```mermaid
flowchart LR
    subgraph offline["At build time, on your PC"]
        exefs["Your dump: main + sdk<br/>(ARM64)"] --> lifter["Lifter<br/>recomp/"] --> c["C code"] --> clang["Clang"] --> exe["mkw.exe"]
    end
    subgraph runtime["At run time"]
        exe --> host["Horizon host<br/>threads, files, audio, input"]
        exe --> nvn["NVN 2 front end<br/>runtime/nvn_*"] --> vk["Vulkan back end"]
        sass["Ampere shaders"] --> lower["Eglantine lowering<br/>Ampere → Maxwell"] --> xlate["Translator<br/>tools/xlate"] --> spirv["SPIR-V"] --> vk
    end
```

The longer version is in [docs/architecture.md](docs/architecture.md) (shared with TotK Recomp) and
[docs/bananza-shaders.md](docs/bananza-shaders.md) (the NVN 2 shader work).

## How to help

Each open problem is a separate, well-bounded job with its own issue. Pick one, say in the issue that you are on it,
and keep each pull request to one topic.

**No code needed**, only your PC and your own copy of the game:

- **Test on your GPU.** Runs on AMD, Intel and different NVIDIA cards, with logs, show what breaks there.
- **Graphical issue debugging**: Report visual differences, missing render targets, or shader issues with log output.

**Code** ([help wanted](https://github.com/STS78721/MKW-THWOMP/issues?q=is%3Aopen+label%3A%22help+wanted%22)):

- **Texture & lighting shaders**: Investigate remaining black surfaces and material render states.
- **NVN 2 entry points**: Complete recording of new Switch 2 NVN 2 command buffer calls.

Your first contribution, step by step:

1. Build from your own dump ([Building from source](#building-from-source)).
2. Run it and note how far it gets on your machine.
3. Report your findings in Issues or Discussions.

Before you open a pull request, read [CONTRIBUTING.md](CONTRIBUTING.md). Its hard rule: nothing that came out of the
game goes into the repository, not in commits, issues or pull requests. Run `python tools/check_content.py --staged`
before committing; CI runs the same check. Questions go to
[Discussions](https://github.com/STS78721/MKW-THWOMP/discussions). Everyone taking part follows the
[code of conduct](CODE_OF_CONDUCT.md).

## Building from source

The toolchain is based on MSYS2 UCRT64 Clang, Ninja, Python 3.10+ and the .NET SDK for the shader translator. With the ExeFS and RomFS from your own dump:

```powershell
.venv\Scripts\python tools\build_xlate.py
.venv\Scripts\python recomp\gen.py --exefs <exefs> --out generated\mkw180 --modules main,sdk
.venv\Scripts\python tools\mkw_expected.py --exefs <exefs> --name mkw180 --display 1.8.0
.venv\Scripts\python tools\mkw_pack_romfs.py --dir <romfs folder> --out build\extracted\mkw180\romfs
.venv\Scripts\python tools\build_game.py --version mkw180 --expected tools\data\expected-mkw180.json --exefs <exefs> --romfs build\extracted\mkw180\romfs
```

Everything the build writes stays under `build\` and `generated\`, which git ignores. Running and testing logs are stored in `logs/mkw.log`.

## FAQ

**Can I play it?** Not yet. The intro renders with graphical issues and work is underway to reach full gameplay. Follow the Issues and Discussions.

**Will there be a download?** No. The executable is made from the game's own code, so it cannot be shared. Everyone
builds it from their own dump.

**Which version of the game?** Base 1.8.0 (Title ID `0400C3F00006E000`).

**Linux?** The recompilation toolchain supports Linux; testing on Linux with native Vulkan is welcome.

**Why GPL?** The shader lowering comes from Eglantine (Eden Emulator Project), which is GPL. Files that came from TotK
Recomp keep their MIT terms.

**How is AI used?** Portions of the code and documentation are written with AI coding assistance, as in TotK
Recomp, and checked by running the game and tests. AI-assisted pull requests are welcome; you are
responsible for having read and run them.

## Credits and origin

MKW Recomp is built on [TotK Recomp](https://github.com/valentderah/totk-pc-recomp) (*Tears of the Kingdom*, Switch 1)
by valentderah and contributors, and [DKB Recomp](https://github.com/sagaopc/dkb-pc-recomp) by Lucas-blip-png, sagaopc, sostenesfreitas and contributors. It uses Eglantine's Ampere shader
lowering (GPL-3.0-or-later, `runtime/third_party/eglantine/`) and Ryujinx's shader translator (MIT, vendored with
MacNativeGames' patches), plus the other projects in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The whole is
under [LICENSE](LICENSE).

- [TotK Recomp](https://github.com/valentderah/totk-pc-recomp) by valentderah, the base of everything here, and the
  projects it builds on: [LAS Recomp](https://github.com/peiikai/LASRecomp),
  [MacNativeGames](https://github.com/ly05010419/MacNativeGames), [nxnative](https://github.com/seedds/nxnative),
  [SavageWindRecomp](https://github.com/Revivedx/SavageWindRecomp), [Ryujinx](https://github.com/Ryujinx/Ryujinx),
  [deko3d](https://github.com/devkitPro/deko3d), [hactool](https://github.com/SciresM/hactool) and the rest listed in
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- [DKB Recomp](https://github.com/sagaopc/dkb-pc-recomp) for the Switch 2 NVN 2 and Ampere shader foundation.
- [Eglantine](https://git.eden-emu.dev/Franseven/PokeDinner-a-Eglantine-Fork) (Eden Emulator Project) for the
  Ampere-to-Maxwell shader lowering and its Switch 2 notes, and [Mesa NAK](https://gitlab.freedesktop.org/mesa/mesa)
  for the SM70+ encodings both build on.
- [libvpx](https://chromium.googlesource.com/webm/libvpx) for the movies.
- [Switchbrew](https://switchbrew.org) for the Switch 2 `GetInfo` ids, and the Switch homebrew community.

## License

MKW Recomp as a whole is under the [GNU GPL v3 or later](LICENSE), because it includes Eglantine's GPL Ampere shader
lowering (`runtime/third_party/eglantine/`). The files that came from TotK Recomp keep their
[MIT License](LICENSE-MIT); third-party code keeps its own license ([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).
The license grants nothing for Nintendo's game.

MKW Recomp is an independent, non-commercial fan project, not affiliated with or endorsed by Nintendo. *Mario Kart
World* and *Nintendo Switch 2* are trademarks of Nintendo.
