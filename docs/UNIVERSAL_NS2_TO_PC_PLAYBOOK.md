# The Universal NS2 to PC Playbook & AI Guide

> **A complete engineering & AI prompting playbook for the "Universal NS2 to PC" Static Recompiler.**  
> **Workspace:** `C:\Games\DKB PC\Universal-NS2-to-PC`

This playbook replaces game-by-game repo forks with one unified, game-agnostic Switch 2 static recompilation engine (`Universal NS2 to PC`). It combines:
1. **TotK Recomp** (`valentderah`): Ahead-of-time ARM64-to-C lifter (`recomp/`), Horizon OS runtime, differential Unicorn testing, and Vulkan renderer.
2. **DKB / MTF / MKW Switch 2 Recomp**: NVN 2 front-end (`runtime/nvn_*.c`), Switch 2 6-core threading, `nn::codec` VP9 host decoder (`runtime/ov_codec.c`), and Ampere-to-Maxwell lowering (`runtime/nvn2_lower.cpp`).
3. **Pre-Flight Intelligence (`tools/universal_ns2_to_pc.py`)** inspired by **NotRexed's Hookshot (`nx2/`)**: Scans ExeFS + RomFS *before* lifting C so every AI model sees exact module relocations, `sdk -> app` imports, ARM64 opcode coverage, NVN 2 proc deltas, paired BNSH stages, SM86 shader opcodes, and Switch 2 `Ounc` texture hazards upfront.
4. **Cross-Emulator Breakthroughs**:
   - **Eglantine (`notsapinho/Eglantine`, commits `7dde4f15`, `77875bb6`, `a2042312`, `7ed597d6`):** Ampere SM86-to-Maxwell lowering, read-only SSBO/bindless fixes, `B10G11R11F` vertex attribute handling, and compute shared memory fixes.
   - **Fritchii (`Frizti/Fritchii` + `NX2_NOTES.md`, commits `724aede4`, `1ca9f7d5`, `2940d9fa`, `4f9b9624`):** Switch 2 `nvdrv` / `nvnflinger` display format behavior, SM86 `TEX`/`FSETP`/`SHFL` fixes, and NVN 2 service structure.
   - **Lichii & Lichii-fg (`zortos293/Lichii`, commits `bcb37c49`, `d2eaae4f`, `536853e7`, `314e1d94`, + `cirnoice9/Lichii-fg`):** `robustBufferAccess2`, `VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT` (`NS2_VK_NOOPT`) safe shader compilation for driver-hanging SM86 shaders, sparse/buffer guards, and frame generation pacing.
   - **MacNativeGames (`ly05010419/MacNativeGames`):** Horizon OS runtime, NPDM/dynamic linking, and audio renderer hardening.

---

## 1. Architecture Overview (Why One Unified Engine Works)

Instead of cloning and hardcoding `dkb.*` / `mtf.*` / `mkw.*` across 20 files, **Universal NS2 to PC** separates game-specific rules from shared subsystems:

| Subsystem | Role in Universal NS2 to PC | Key Files |
| --- | --- | --- |
| **Pre-Flight Profiler & Builder** | Scans `exefs/` + `romfs/`, builds `expected-<ver>.json`, lifts C, invokes MSYS2 Clang build | `tools/universal_ns2_to_pc.py`, `tools/build_game.py` |
| **Game Profile Registry** | Detects `rt_application_id`, weak `rt_game_short_name[]`, `rt_game_display_name[]`, and quirk flags (`GAME_QUIRK_*`) | `runtime/game_profile.h`, `runtime/game_profile.c` |
| **Unified Config & Aliases** | Primary `NS2_*` settings stored in `<short>.ini`; accepts legacy `MTF_`, `MKW_`, `DKB_`, `OOT_`, `TOTK_` aliases | `runtime/cfg.c` |
| **Live Resolution & Mode Hooks** | Syncs live `NS2_OPERATION_MODE` (`docked`/`handheld`), Horizon events `0x1e`/`0x1f`, `ov_graphics_scale()`, `OUTPUT_RES`, and `RENDER_SCALE` | `runtime/resolution.c`, `runtime/ov_system.c`, `runtime/nvn_api_obj.c`, `runtime/gfx_present.c` |
| **Midnight Glass Overlay** | Built by default (`F1` / `Back+Y`). Live toggles, Inspector Card (`[LIVE]`/`[RESTART]`/`[ENV]`), `FPS_LIMIT` (`30..240\|display`), pipeline telemetry | `runtime/ui/menu.cpp`, `runtime/ui/option_rows.cpp`, `runtime/ui/option_rows.h` |
| **Safe Shader Pipeline** | `VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT` toggle (`NS2_VK_NOOPT`) + NativeAOT Ryujinx SPIR-V translator (`*_xlate.exe/.id`) | `runtime/vk_crumbs.c`, `runtime/gfx_shader.c`, `tools/build_xlate.py` |

### Registered `GAME_QUIRK_*` Flags (`runtime/game_profile.h`)

Never scatter `if (strstr(game, "..."))` across the codebase. Add a clean flag in `runtime/game_profile.h` + `runtime/game_profile.c`:
- `GAME_QUIRK_PT_BR` — Localization / PT-BR profile handling
- `GAME_QUIRK_MTF_WORKER_ARGS` — Redirected guest worker args for Mario Tennis Fever (`0x0400D4201C6EA000`)
- `GAME_QUIRK_MKW_HEAP_FALLBACK` — Mario Kart World large heap fallback (`0x0400C3F00006E000`)
- `GAME_QUIRK_MKW_VTABLES` — Mario Kart World vtable patches
- `GAME_QUIRK_TOTK_PATCH_RES` — Switch 1 TotK-style resolution patch checks

---

## 2. Standard Bring-Up Workflow (Scan -> Init -> Build -> Probe -> Boot)

Every new Nintendo Switch 2 game follows this exact 5-step pipeline from `C:\Games\DKB PC\Universal-NS2-to-PC`:

### Step 1: Build the NativeAOT Shader Translator (once per machine/update)
```powershell
python tools\build_xlate.py
```
Outputs `build\xlate\totk_xlate.exe` + `totk_xlate.id` (and `mkw_xlate.*`). `runtime/gfx_shader.c` searches `ns2_xlate`, `mtf_xlate`, `mkw_xlate`, `dkb_xlate`, `oot_xlate`, `totk_xlate`.

### Step 2: Run the Smart Pre-Flight Scanner (`scan`)
```powershell
python tools\universal_ns2_to_pc.py scan --exefs "<path>\exefs" --romfs "<path>\romfs" --max-textures 200
```
**What `scan` catches before you write 1 line of C:**
- **Title ID & Extra Modules:** Detects `subsdk0`, `subsdk1`, etc. (`rtld`, `main`, `main.npdm`, `sdk`).
- **ELF Relocations:** Reports `DT_RELR`, `R_AARCH64_ABS64`, `R_AARCH64_GLOB_DAT`, `R_AARCH64_JUMP_SLOT`, `R_AARCH64_TLSDESC`.
- **Exact `sdk -> app` Imports:** Counts hooked vs unhooked `nn::*` namespaces (`nn::audio`, `nn::os`, `nn::movie`, `nn::async`, `nn::codec`, `nn::socket`, etc.).
- **ARM64 Lifter Coverage:** Samples distinct `.text` words directly through `recomp/lifter.py` (`Lifter(...).lift(...)`) and flags unhandled encodings immediately.
- **NVN 2 Proc Coverage:** Cross-checks game NVN string table against `nvn_procs*.inc`.
- **Shader Census & Ampere SM86 Audit:** Walks RomFS (`.bfsha`, `.sharcb`, `.bnsh`, SARC+Zstd) to count all 9 BNSH shader slots, pipeline stage pairs (e.g. `vertex+pixel`, `compute`), `>5K`-insn stall shaders, and SM86 opcodes vs `lower_to_maxwell.h`.
- **Switch 2 `Ounc` Texture & Container Audit:** Detects Switch 2 `+4` byte `Ounc` `BRTI` headers (`SurfaceFormat` at `+0x1C`, dims `<4I` at `+0x24`), `>256M` texel sparse hazards, huge arrays (`layers=46`), media streams, and monolithic archives (`CRA.` magic).

### Step 3: Initialize Game Metadata & Patch Table (`init`)
```powershell
python tools\universal_ns2_to_pc.py init --ver mygame100 --short mygame --name "My NS2 Title" --display 1.0.0 --exefs "<path>\exefs" --romfs "<path>\romfs"
```
Creates:
- `tools/data/expected-mygame100.json` (hashes + `short_name` + `display_name` + `title_id` only; zero game bytes)
- `recomp/patches-mygame100.txt` (empty patch table)

### Step 4: Lift ARM64 -> C & Compile Native PC Executable (`build`)
```powershell
python tools\universal_ns2_to_pc.py build --ver mygame100 --exefs "<path>\exefs" --romfs "<path>\romfs_or_packed"
```
(Make sure `C:\msys64\ucrt64\bin` is first on `PATH` so MSYS2 UCRT64 Clang & Ninja are used — never `cl.exe`!)

To recompile runtime C/C++ changes fast against existing lifted C:
```powershell
$env:PATH = "C:\msys64\ucrt64\bin;$env:PATH"
python tools\build_game.py --version <ver> --gen "<gen_dir>" --exefs "<exefs_dir>" --romfs "<romfs_dir>" --out "build\<ver>"
```

### Step 5: Mandatory Baseline Smoke Checks (F0 -> F5 Order)
Always run in strict layer order so you never debug F4 Vulkan bugs caused by F0/F1 failures:
```powershell
.\build\<ver>\<short>.exe --selftest        # F0: dispatch table, memory map, heap/alias, CPU caps
.\build\<ver>\<short>.exe --probe-cfg       # Config parser + ImGui option_rows test_parse()
.\build\<ver>\<short>.exe --probe-gfx-abi   # F2: NVN2 struct layouts & ABI sizes
.\build\<ver>\<short>.exe --probe-window    # F4: Vulkan swapchain, ImGui overlay open/close, vsync
$env:TOTK_GPU="null"
.\build\<ver>\<short>.exe --seconds 4       # F1: Headless Horizon OS boot (threads, FS, audren, codec)
Remove-Item Env:TOTK_GPU -ErrorAction SilentlyContinue
.\build\<ver>\<short>.exe --seconds 4       # F2-F4: Full Vulkan GPU pipeline + present check
```
Inspect `build\<ver>\logs\<short>.log` after every run! Never skip `TOTK_SHARED_FONTS` if a title calls `nn::pl::GetSharedFontSize`.

---

## 3. Switch 2 Hardware & File-Format Gotchas (Verified)

1. **BNTX `Ounc` vs `NX  ` Header Offset (+4 Bytes):**
   - Switch 2 textures (`target = "Ounc"` at `b[0x20:0x24]`) store `BRTI` `SurfaceFormat` at `+0x1C` (vs `+0x18` on Switch 1 `NX  `) and `<4I` `(width, height, depth, arrayLayers)` at `+0x24` (vs `+0x20`).
   - Do **not** blindly fall back to uncompressed RGBA8 decoding for large arrays (`layers=46`, `8192x8192`): use native BCn/ASTC Vulkan paths or CompactLayers + sparse `MapVirtual`.
2. **Switch 2 `GetCurrentGraphicsScale` Enum:**
   - Switch 2 returns enum `0..2` (`0` = handheld/conservative, `1` = balanced, `2` = docked), **not** Switch 1 `10`/`20`. `runtime/ov_system.c` maps `ov_graphics_scale()` cleanly and fires OS messages `0x1e` / `0x1f` + display resolution change events when toggled live.
3. **MSVC `cl.exe` Cannot Compile Lifted C:**
   - Generated chunks rely on GNU C extensions. Always build with MSYS2 UCRT64 Clang (`C:\msys64\ucrt64\bin\clang.exe`).
4. **Driver Shader Stalls / Miscompiles:**
   - If a game hangs or crashes inside Vulkan `vkCreateGraphicsPipelines` on a giant (`>5K`-insn) SM86 shader, toggle **Safe Shader Compile (`NS2_VK_NOOPT=1`)** in the in-game menu (`F1`) to pass `VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT` via `vk_pipeline_capture_flags()`.
5. **Repo Content Guard:**
   - Everything extracted or lifted must stay in `build/`, `generated/`, or external game folders. Always run `python tools/check_content.py` (or `--staged`) before committing.

---

## 4. Copy-Paste AI Starter Prompt (For Any Future AI Starting on This Repo)

Copy and paste this prompt when starting a new Switch 2 title or debugging F0-F5 in `C:\Games\DKB PC\Universal-NS2-to-PC`:

```text
You are working inside the "Universal NS2 to PC" static recompiler repository at:
C:\Games\DKB PC\Universal-NS2-to-PC

Read AGENTS.md and docs\UNIVERSAL_NS2_TO_PC_PLAYBOOK.md first. Follow these strict rules:

1. WORKFLOW ORDER:
   - Never guess what the game uses. First run:
     python tools\universal_ns2_to_pc.py scan --exefs "<GAME_EXEFS>" --romfs "<GAME_ROMFS>"
   - Review Title ID, extra modules (subsdk*), unhooked nn:: namespaces, NVN2 missing procs,
     ARM64 lifter unhandled count, BNSH shader stages/pairs, SM86 opcodes vs lower_to_maxwell.h,
     huge >5K shaders, and Switch 2 Ounc BNTX textures.
   - Initialize metadata with:
     python tools\universal_ns2_to_pc.py init --ver <ver> --short <short> --name "<Game Name>" --exefs "<GAME_EXEFS>" --romfs "<GAME_ROMFS>"

2. MULTI-GAME ARCHITECTURE RULES:
   - NEVER fork or hardcode a single game name across core runtime files.
   - Register Title ID quirks cleanly in runtime/game_profile.h and runtime/game_profile.c (GAME_QUIRK_*).
   - Use NS2_* primary config keys in runtime/cfg.c + runtime/ui/option_rows.cpp so live HUD controls
     (Console Mode, Output Res, Render Scale, Res Hook, Upscalers, Safe Shader Compile, FPS Limit)
     stay unified across all games.

3. BUILD & LAYERED VERIFICATION (F0 -> F5):
   - Always compile C/C++ with MSYS2 UCRT64 Clang (C:\msys64\ucrt64\bin first on PATH) and Ninja.
   - Verify after EVERY change:
     a) --selftest and --probe-cfg and --probe-gfx-abi
     b) --probe-window (verifies Vulkan swapchain + ImGui HUD overlay)
     c) TOTK_GPU=null <short>.exe --seconds 4 (F0/F1 Horizon OS bring-up & logs/<short>.log)
     d) Full Vulkan <short>.exe --seconds 4 (F2-F4 shaders, pipelines, presents)
   - If you hit SM86 shader miscompiles or NVN2/Horizon issues, consult runtime/third_party/eglantine/,
     runtime/nvn2_lower.cpp, and the cross-emulator fixes documented in docs/UNIVERSAL_NS2_TO_PC_PLAYBOOK.md.

4. REPO HYGIENE:
   - Keep all game dumps, lifted C, and binaries outside git-tracked paths.
   - Run `python tools/check_content.py` before finishing.
```

---

## 5. Crucial Switch 2 Findings & Solutions (Fast Fusion & Beyond)

### 5.1. Massive Vertex Explosions: Speculative SSBO DMA Writeback
- **Symptom:** The 3D scene shows giant skewed polygon sheets, skewed triangles, or exploded vertex geometry covering the screen, while 2D UI/HUD remains intact.
- **Root Cause:** In branching compute/graphics dispatches, `GlobalToStorage.cs` registers every candidate storage buffer expression with `BufferUsageFlags.Write` for SPIR-V validator safety. In `runtime/vk_exec_draw.c`, `ssbo_info` binds these speculative candidates with `guarded=1` (`direct_only=1`). If `vk_mem_gpu_wrote(&sp, n)` and `note_written` are called for candidate buffers, the engine schedules full-extent (`n = 120 KiB+` or pool remainder) `mbuf -> buf` GPU DMA writebacks at `vk_mem_mirror_end`. Because Windows `GetWriteWatch` only tracks host CPU writes and does not track GPU DMA writes, host memory is overwritten with stale mirror buffer bytes. This clobbers guest host RAM where subsequent draws' vertex buffers reside.
- **Solution:** Guarded storage buffer candidates (`direct_only` / `guarded`) must NEVER schedule full-extent writeback or register completion dirty ranges:
  ```c
  // runtime/vk_exec_draw.c: bind_range
  if (written && !direct_only) vk_mem_gpu_wrote(&sp, n);
  if (written) vk_usnap_drop(addr, n);

  // runtime/vk_exec_draw.c: ssbo_info
  if (written && !guarded && bi.buffer != VK_NULL_HANDLE) {
      note_written(ex, b->addr - lead, bi.range);
      ...
  }
  ```

### 5.2. Missing Volumetric Fog LUT / Black Skybox: Single-Image Fallback
- **Symptom:** Night/space or foggy courses render with a completely pitch-black skybox or missing atmospheric lighting.
- **Root Cause:** Ampere compute shaders writing to 3D image LUTs (`SUST.P` image store instructions) in NVN2 packed `c0` banks may have image handles where the computed handle byte offset does not match `nvn2_c0_part(&s->c0, 4)` partitions, resulting in `r->slot = -1`. When `r->slot` is negative, `vk_exec_draw.c` binds a 1x1 dummy black texture instead of the target 3D LUT (e.g. `lut738` `160x90x64`).
- **Solution:** When a compute shader declares exactly 1 image in its `c0` layout, fall back to slot 0 if slot resolution yielded negative:
  ```c
  // runtime/gfx_shader.c
  if (kind == GFX_RES_IMG && r->slot < 0 && s->c0.images == 1) r->slot = 0;
  ```

### 5.3. Dynamic Window Title Across Titles
- **Solution:** Rather than hardcoding titles in window creation, use `game_profile()->display_name`:
  ```c
  // runtime/gfx_window_win.c & gfx_window_sdl.c
  const char *dn = game_profile()->display_name;
  swprintf(title_w, sizeof title_w / sizeof title_w[0], L"%hs (PC Recomp)", (dn && *dn) ? dn : "Universal NS2 Title");
  ```

### 5.4. Automatic Shader Translator Deployment
- `tools/build_game.py` automatically deploys `build/xlate/totk_xlate.exe` (and `.id`) to `<out>/ns2_xlate.exe` and `ns2_xlate.id` beside the output executable so every new game build has its native shader translator ready out of the box.
