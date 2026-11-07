# Donkey Kong Bananza PC Recomp (DKB): Knowledge Transfer

This document archives the core architecture, solved bugs, launcher blueprints, and hardware tuning knowledge for **Donkey Kong Bananza PC Recomp (DKB)** (`dkb-BANANAS` / `C:\DK-Bananza-Instalador\jogo`).

---

## 1. Architectural Lineage

- **Foundation:** DKB Recomp uses a static recompilation pipeline translating Switch ARM64 binaries into native Windows x86-64 with a Vulkan presentation engine.
- **Switch 2 Specialization:**
  - Targets NVN 2 (Ampere ISA / SM86).
  - Uses the `runtime/third_party/eglantine/` lowering engine for Ampere shaders.
  - Implements `runtime/ov_codec.c` for Switch 2 `nn::codec` video decoding.
- **Lifter & Testing:** Instruction translation passes differential testing against Unicorn CPU emulation to ensure register agreement.

---

## 2. Proven Vulkan & Runtime Fixes

1. **Fullscreen Startup (`runtime/gfx_window_win.c`):**
   - Implemented `g_fs_pending` flag to defer fullscreen window sizing until the Win32 message loop and Vulkan swapchain are fully instantiated, eliminating the bug where games boot windowed despite `fullscreen = 1`.
2. **Vulkan Shader Pre-Warming:**
   - Multi-threaded parallel pipeline creation via `--warm-shaders` to populate driver disk caches and eliminate runtime stutter.
3. **Descriptor Pool & VRAM Leak Protection:**
   - Fixed rapid scene transition leaks and tuned buffer reallocation thresholds to reduce PCIe bus saturation.
4. **Dynamic Resolution Scaling (DRS) & Upscalers:**
   - Decoupled master upscaler execution from AA.
   - PID-controlled anti-pumping loop based on GPU timestamp headroom queries (`vk_headroom.c`) to maintain lock-on frame rate targets (60 / 120 FPS).
5. **NVIDIA Instanced Light-Quad GPU Fault vs. 3D World Mesh Separation (`runtime/vk_exec_draw.c`):**
   - Bananza's instanced light quads fetch Location 9 across `>= 8` vertex streams where **every stream is per-instance** (`ex->pipe.vstream[stream].divisor != 0`) and `count <= 6` (4-vertex quad or 6-vertex two-triangle quad), which causes `VK_ERROR_DEVICE_LOST` (`instruction pointer (invalid)`) on NVIDIA drivers (`617.14`–`621.01`).
   - Crucially, legitimate 3D world shaders (skybox, cave walls, distant terrain) also have vertex input masks with bit 9 and bit 0 set (`0x03ff`, `0x07ff`, `0x1fff`, `0x3fff`, `0x7fff`), so checking `(used >> 9 & 1) && (used & 1)` falsely skips 3D world geometry and turns the sky and distant world black!
   - Solution: `light_quad_fault_skip` checks `count <= 6`, `active_streams >= 8`, and verifies that **every** active attribute stream has `divisor != 0` (plus the 7 known cutscene VS origins and `c0+0x530` SSBO light check). This skips 100% of faulting light quads while never touching a 3D mesh (`divisor == 0`).
6. **Indirect Reset & Texture Fence Write-Back Integrity (`runtime/vk_exec_draw.c`, `runtime/vk_texture.c`, `runtime/vk_backend.c`):**
   - `vk_exec_reset_indirect` must always read the pointer list through `vk_exec_read_buffer` (which resolves shadow/VRAM mirror state) rather than raw `memcpy` from guest VA, or destructible terrain indirect records read stale pointers.
   - Keep `WB_SMALL_DEFAULT` (64 KB) fence write-backs active and `TOTK_NX2_READ_NOWAIT` opt-in so GPU-generated LUTs and environment maps are written back before CPU reads.

---

## 3. Sony/Nixxes-Style Launcher UX Standard

1. **Clean Process Exit:** Always terminate launcher background tasks with `os._exit(0)` to prevent Tcl 9 / Tkinter memory allocator crashes on Windows.
2. **Non-Destructive Mod Management:** Folder tagging using `.disabled` extensions allows one-click mod activation without moving large RomFS directories.
3. **Safety Snapshots:** Before any save state is restored from the backup vault, an automatic safety snapshot of the active save is taken.
4. **Asynchronous Release Checking:** Non-blocking background thread queries GitHub Releases for updates without freezing UI sliders or sound effects.

---

## 4. PS5 DualSense & SDL3 Integration Blueprint

1. **Dynamic Glyphs:** Query `SDL_GetGamepadType()` to swap between PlayStation, Xbox, and Nintendo button prompts on the fly.
2. **Audio Haptics (WASAPI):** Route low-frequency tactile waveforms to DualSense voice-coil actuators on channels 3 & 4.
3. **Adaptive Triggers:** Deliver force feedback tension curves via HID output reports (`0x02` USB / `0x31` Bluetooth).
4. **HUD Telemetry:** Real-time battery percentage and charging state via `SDL_GetGamepadPowerInfo()` in the debug HUD.

---

## 5. Arrow Lake & RTX 5070 Ti Rig Optimization

- **CPU Core Affinity:** Arrow Lake (Intel Core Ultra 7 270K Plus) features 8 Lion Cove P-cores and 16 Skymont E-cores. Interconnect latency between P-cores and E-core clusters is ~55–80ns.
- **Tuning Mask:** Pin the `dkb.exe` process to Cores 0–7 (hex mask `0x0000FF`) using Process Lasso or CPU Sets to keep all game threads on the P-core ring, completely avoiding frame pacing micro-stutter.
