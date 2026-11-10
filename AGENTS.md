# Universal NS2 to PC

Unified static recompilation engine for Nintendo Switch 2 (ARM64 + NVN 2 + Ampere SM86) titles into native x86-64 Windows/Linux executables with a Vulkan renderer. Built on [TotK Recomp](docs/architecture.md), Switch 2 NVN 2 pioneer work from DKB Recomp / MTF Recomp / MKW-THWOMP, and GPU/Horizon research from Eglantine, Fritchii, Lichii, Hookshot, and MacNativeGames.

## Unified Multi-Game Architecture

- **Pre-Flight Profiler, Initializer & Builder (`tools/universal_ns2_to_pc.py`):** Always run `scan` before modifying runtime code for a new game (`python tools/universal_ns2_to_pc.py scan --exefs <exefs> --romfs <romfs>`), then `init` (writes `tools/data/expected-<ver>.json` + runs `recomp/gen.py`), and `build` (builds via `tools/build_game.py` after building `totk_xlate` with `tools/build_xlate.py`).
- **Central Game Registry (`runtime/game_profile.h`, `runtime/game_profile.c`):** Never branch core runtime files on hardcoded repo names or copy/fork the runtime per game. Register Title ID quirks (`GAME_QUIRK_*`) and inspect `game_profile()` (which reads weak `rt_game_short_name[]`, `rt_game_display_name[]`, and `rt_application_id`).
- **Config & Overlay Menu (`runtime/cfg.c`, `runtime/ui/`):** Config variables use primary `NS2_*` keys while keeping backward-compatible `MTF_`, `MKW_`, `DKB_`, `OOT_`, and `TOTK_` aliases via `unprefix()`. The Dear ImGui in-game menu (`F1` / `Back+Y`) is compiled in and enabled by default (`runtime/ui/menu.cpp`, `option_rows.cpp`), and hooks live into `ov_notify_operation_mode_changed()`, `res_apply_live()`, `NS2_RES_HOOK`, `NS2_VK_NOOPT`, upscalers, frame generation, and `FPS_LIMIT` (`30..240|display`).
- **Playbook & Cross-Emulator Guide:** [docs/UNIVERSAL_NS2_TO_PC_PLAYBOOK.md](docs/UNIVERSAL_NS2_TO_PC_PLAYBOOK.md) documents the end-to-end F0–F5 workflow, Switch 2 `Ounc` BNTX / SM86 shader profiling, and concrete fixes from Eglantine, Fritchii, Lichii, Hookshot, and MacNativeGames.

## Game content boundary

This repository is public. Game data lives outside it and every derived file stays in ignored folders.

- The user's game and key paths are in `config.local.toml` (ignored). Pass the keys file path to tools; the tools read it themselves. Key values stay out of your output, logs, commands and files.
- Everything extracted or generated goes under `build/` or `generated/`.
- Every file the code generator emits carries the marker defined as `GENERATED_MARKER` in `tools/check_content.py`.
- Run `python tools/check_content.py --staged` (or `python tools/check_content.py`) before proposing a commit.

## Reusing code

`refs/` holds optional upstream checkouts (`tools/fetch_refs.sh` recreates it). Read-only.

- Copy only MIT, BSD, ISC, zlib or Apache-2.0 code, keep its header, and add a row to `THIRD_PARTY_NOTICES.md`.
- Universal NS2 to PC is GPL-3.0-or-later as a whole (LICENSE), because it carries Eglantine's GPL Ampere lowering
  (`runtime/third_party/eglantine/`, with the owner's go-ahead). GPL-3.0-compatible code (Eden, Eglantine, Fritchii, Lichii,
  yuzu and the like) may be copied with its header kept, a row in `THIRD_PARTY_NOTICES.md` and the upstream commit. Files
  that came from TotK Recomp keep their MIT terms (`LICENSE-MIT`); a fix meant for TotK Recomp itself must not use GPL code.
- `tools/vendor/` stays byte-identical to upstream; Windows changes go in `tools/extract.py`.

## Code

- Build C/C++ with MSYS2 UCRT64 Clang (`C:\msys64\ucrt64\bin`). Generated C uses GNU extensions, so `cl.exe` is out. Call Ninja from that directory by full path or put it first on PATH.
- Python 3.10+ (Python 3.14+ / 3.15 provides stdlib `compression.zstd` for RomFS/NSZ/shader inspection; `.venv` is optional if Python packages like `lz4` / `zstandard` are installed globally).
- Generated C is never edited by hand: change the generator (`recomp/`).
- Every lifter change passes the differential tests against Unicorn ([docs/building.md](docs/building.md), "Checks"). After changing `recomp/jumptables.py`, `tests\jumptables_check.py` reports 0 disagreements on baseline binaries.
- `recomp/layout.py` alone decides module bases.
- Graphics bugs: [docs/maxwell.md](docs/maxwell.md) lists Maxwell behavior and [docs/bananza-shaders.md](docs/bananza-shaders.md) covers NVN 2 + SM86 lowering.
- For Switch 2 NVN 2 / SM86 / Horizon service issues, consult Eglantine (`runtime/third_party/eglantine/`), Fritchii (`NX2_NOTES.md`), Lichii (`Lichii` / `Lichii-fg`), Hookshot (`nx2/`), and MacNativeGames, noting hardware accuracy tradeoffs where applicable.
- Comments say what the code does and why, in words that stand on their own. Cite our code by file plus function (a line number may follow as a hint) and upstream code by project, file and function; commit hashes belong to the attribution of copied code.

## Writing

Code, comments, docs and commit messages are in English. Commit messages are plain sentences without type prefixes.
