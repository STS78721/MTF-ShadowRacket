# Changelog

All notable changes to the **SteelTempSaint Donkey Kong Bananza PC Recomp (DKB)** project are documented in this file.

---

## [Alpha 1] - 2026-11-07

### 🌟 Initial Alpha 1 Release Highlights
- **Modern Dark Jungle & Banana Gold Setup Wizard (`DKB-Setup.exe` / `Donkey-Kong-Bananza-Setup.exe`):**
  - Standalone zero-dependency PyInstaller bundle (`customtkinter` + `darkdetect` embedded) with high-res multi-mipmap `dkb.ico` icon.
  - Native unpacking support for `.nup` containers, unpacked `exefs/` + `romfs/` (or `base/exefs` + `base/romfs`) dump folders, and `.nsp` / `.xci` containers.
  - Automatic `romfs.bin` indexed image builder from loose RomFS files for instant startup and streaming.
  - 1-click deployment of NVIDIA DLSS 4.5, DLSS-NR, Streamline, Reflex, and Intel XeSS 1.3+ runtime libraries.
  - Built-in Controller UI selector (PS5 DualSense Monochrome/Color, Xbox Series Monochrome/Color, Nintendo Switch) and Desktop shortcut creator.

- **Standalone PC Launcher (`DKBLauncher.exe` - Alpha 1):**
  - Branded as **Alpha 1** (`ALPHA 1 · DKB`) with full two-way synchronization against `dkb.ini` and the in-game F1 overlay menu.
  - Added Display & Graphics controls for Upscaler (`Off`, `DLSS`, `FSR`, `XeSS`, `DLAA`), Upscaler Quality Preset, DLSS Preset (`Default`, `Preset K`, `Preset L`, `Preset M`), Frame Generation, NVIDIA Reflex (`Off`, `On`, `On + Boost`), AMD Anti-Lag 2, Render Scale, Shadow & Anisotropic Filtering, FOV (`70`–`120`), and Color Grading (`Default`, `Vivid`, `Warm`, `Cool`, `Cinema`).
  - Added Vulkan Shader Pre-Warm utility, Save Backup Vault with safety snapshots, and 1-click Mod Manager.

- **Vulkan Renderer & Cutscene Stability Fixes:**
  - **Sky, Cave Walls & Distant World Restoration (`runtime/vk_exec_draw.c`):** Fixed `light_quad_fault_skip` so that only true per-instance light quads (`count <= 6`, `>= 8` active vertex streams, all active streams having `divisor != 0`) or known faulting cutscene vertex stage origins (`cae0ef8e9fe9147f`, `a05d707357ffc917`, `c081588c78ee16f3`, `89300537d4fff15e`, `fb6e80e4f0bd1ac5`, `140a1eac75f7b5c0`, `163bd4735277403a`) are skipped on NVIDIA GPUs. Legitimate 3D world shaders with vertex input masks `0x03ff`–`0x7fff` (skybox, cave walls, distant terrain) use per-vertex streams (`divisor == 0`) and `count > 6`, so zero 3D meshes are ever skipped.
  - **Indirect Reset & Texture Write-Back Integrity (`runtime/vk_exec_draw.c`, `runtime/vk_texture.c`, `runtime/vk_backend.c`):** Restored `vk_exec_read_buffer` in `vk_exec_reset_indirect` and synchronous fence write-back limits so GPU-generated LUTs and destructible terrain indirect records never read stale guest memory.
  - **Upstream Bananza Engine Sync:**
    - Enabled native passthrough geometry shader replay by default (`NATIVE_GS=1`) so destructible terrain renders properly.
    - Integrated Ampere lowering support for RGB-mask `TXD` instructions (`lower_to_maxwell.h`) and shader translator patch `0019` (allowing code after unpredicated `CAL` instructions to run, restoring the opening tutorial wall).
    - Allowed passthrough geometry shaders to read unforwarded inputs (`runtime/gfx_shader.c`).
    - Added indexed pending GPU write tracking during shadow memory sync (`runtime/vk_memory.c`).
    - Rounded alpha-test pipeline key references to nearest `1/255` step (`runtime/vk_pipeline.c`) to eliminate per-frame pipeline rebuild stutter during fades.
    - Added mutable sRGB storage-image view support (`VK_IMAGE_CREATE_EXTENDED_USAGE_BIT` in `runtime/vk_texture.c` and format-matched storage views in `runtime/vk_exec_draw.c`).
