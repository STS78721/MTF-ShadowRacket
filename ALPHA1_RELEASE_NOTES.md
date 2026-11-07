## 🍌 Alpha 1b: Cross-Vendor Cutscene Stability (AMD RDNA 4 / NVIDIA / Intel), Native 30/60 FPS Timing Cap & Smart RomFS Packer ⚡

<p align="center">
  <img src="https://raw.githubusercontent.com/STS78721/dkb-BANANAS/bananza/launcher/launcher_showcase.png" alt="SteelTemple DKB Standalone Launcher" width="90%">
</p>

Welcome to **Alpha 1b**, our community-verified hotfix & inaugural public testing release of the **SteelTempSaint Donkey Kong Bananza PC Recomp (DKB)**!

Modeled directly after our flagship **SteelTempSaint ToTK Recomp** architecture and modern PlayStation/Nixxes PC ports, this release transforms *Donkey Kong Bananza* (Nintendo Switch 2) into a native Windows x86-64 Vulkan 1.3 application—complete with a sleek Banana Gold & Jungle Setup Wizard, our standalone `DKBLauncher.exe`, multi-vendor AI upscaling (NVIDIA DLSS 4.5 / Intel XeSS 1.3 / AMD FSR / DLAA), NVIDIA Reflex & Anti-Lag 2, and all pre-tested fixes for cutscenes, skyboxes, and destructible terrain.

---

### 🔥 What's New in Patch Alpha 1b (Community Tester Hotfix)

* **🛡️ Cross-Vendor Cutscene Light-Quad Fault Guard (`runtime/vk_exec_draw.c`):**
  * Extended the NVN 2 instanced light-quad fault guard (`light_quad_fault_skip`) across **all GPU vendors (AMD RDNA 4 / RX 9070 XT / Radeon 890M, NVIDIA RTX, and Intel Arc)** instead of only NVIDIA (`0x10de`), resolving the `vkQueueSubmit2` device-lost crash during the opening cutscene on AMD RDNA GPUs.
* **⏱️ Strict 30 / 60 FPS Native Timing Cap (`runtime/frame_rate.c`, `runtime/cfg.c`, `runtime/ui/menu.cpp`, `launcher/DKBLauncher.py`):**
  * Restricted the Frame Rate Limit in the runtime, in-game `F1` menu, and `DKBLauncher.exe` to **30 FPS** and **60 FPS** (and automatically clamps legacy `120` / `display` settings in `dkb.ini` to **60 FPS**).
  * Fixes game speed-up and prevents the `"Golden Bananas?!"` intro transition screen from stalling on 120 Hz+ configurations.
* **📦 Automatic Loose RomFS Packer & Smart Dump Folder Resolution (`installer/modern_gui.py`, `launcher/DKBLauncher.py`):**
  * Fixed automatic packing of loose `romfs/` files into `romfs/romfs.bin` during setup and added a 1-click prompt in `DKBLauncher.exe` to auto-pack loose `romfs/` files on launch.
  * Added smart dump folder detection (automatically resolves parent folders, `exefs/` or `romfs/` subfolders, and `.nup` containers) and strict post-install verification for `exefs/main`, `exefs/sdk`, and `romfs/romfs.bin`.

---

### 🌟 Core Pre-Tested Features in Alpha 1 / 1b

#### 1. 🛠️ Pre-Tested NVIDIA Cutscene & Save-Load Stability (`runtime/vk_exec_draw.c`)
* **Eliminated `VK_ERROR_DEVICE_LOST` (`instruction pointer (invalid)`) Crashes:** Fixed the GPU device loss that occurred on NVIDIA drivers (`617.14`–`621.01`) during save loading and the *Ingot Isle Cave-In* cutscenes.
* **Precision Per-Instance Light-Quad Filter (`light_quad_fault_skip`):** Accurately distinguishes faulting 10-stream instanced light quads (`count <= 6`, `>= 8` active vertex streams, all active streams `divisor != 0`) and 7 cutscene vertex stage origins (`cae0ef8e9fe9147f`, `a05d707357ffc917`, `c081588c78ee16f3`, `89300537d4fff15e`, `fb6e80e4f0bd1ac5`, `140a1eac75f7b5c0`, `163bd4735277403a`) from 3D geometry.
* **100% 3D World, Skybox & Distant Terrain Preservation:** Legitimate 3D world shaders that use vertex attribute masks `0x03ff`–`0x7fff` (skybox, cave walls, distant terrain) use per-vertex streams (`divisor == 0`) and `count > 6`, ensuring **zero 3D world meshes are ever skipped** and preventing the black-sky/black-background regression.

#### 2. ⛰️ Pre-Tested World Textures, Destructible Terrain & Upstream Engine Sync
* **Native Passthrough Geometry Shaders On by Default (`NATIVE_GS=1`):** Replays lowered native passthrough geometry stages through the portable path by default so destructible terrain renders with full geometry and materials instead of black.
* **Opening Wall & Gradient Texture Lowering (Upstream PR #78 / #81 / #82):**
  * Integrated Ampere lowering support for 3-channel RGB-mask `TXD` gradient texture instructions (`lower_to_maxwell.h`).
  * Added shader translator patch `0019` so code following an unpredicated `CAL` instruction remains reachable, restoring the opening tutorial wall.
  * Allowed passthrough geometry shaders to read unforwarded inputs (`runtime/gfx_shader.c`).
* **Indirect Reset & Texture Fence Write-Back Integrity (`runtime/vk_exec_draw.c`, `runtime/vk_texture.c`, `runtime/vk_backend.c`):**
  * Restored `vk_exec_read_buffer` in `vk_exec_reset_indirect` so destructible terrain indirect-reset pointer lists always resolve shadow/VRAM mirror memory instead of reading stale guest VAs.
  * Preserved synchronous 64 KB fence write-backs (`WB_SMALL_DEFAULT`) and added mutable sRGB storage-image views (`VK_IMAGE_CREATE_EXTENDED_USAGE_BIT`) so GPU-generated LUTs and distant environment maps never read back stale zeros.
* **Indexed Shadow Memory Sync & Alpha-Ref Pipeline Keying:**
  * Binary-searched union of pending GPU writes during shadow memory synchronization (`runtime/vk_memory.c`).
  * Rounded alpha-test pipeline key references to nearest `1/255` step (`runtime/vk_pipeline.c`) to eliminate per-frame pipeline compilation stutter during fades.

#### 3. 🖥️ Standalone Nixxes/Sony-Style PC Launcher (`DKBLauncher.exe` - Alpha 1)
* **Full 1:1 In-Game Settings Synchronization:** Every setting in `DKBLauncher.exe` synchronizes directly with `dkb.ini` and the in-game `F1` overlay menu:
  * **Upscalers:** `Off`, `NVIDIA DLSS 4.5`, `AMD FSR`, `Intel XeSS 1.3`, and `DLAA` with Quality Presets (`Ultra Performance` to `Native AA`) and DLSS Presets (`Default`, `Preset K`, `Preset L`, `Preset M`).
  * **Low Latency & Frame Generation:** `NVIDIA Reflex` (`Off`, `On`, `On + Boost`), `AMD Anti-Lag 2`, and `AI Frame Generation`.
  * **Display, Pacing & Color Grading:** Fullscreen/Windowed mode, Output Resolution (`720p` to `4K`), Render Scale (`50%`–`200%`), Frame Rate Limit (`30` / `60` / `120` / `Unlimited`), FOV (`70`–`120`), and Color Presets (`Default`, `Vivid`, `Warm`, `Cool`, `Cinema`).
* **Pre-Warm Vulkan Shaders:** 1-click multi-threaded shader and pipeline library pre-compilation into your GPU driver cache.
* **Save Backup Vault & 1-Click Mod Manager:** Create timestamped save snapshots (`profile-dkb100/backups/save_<timestamp>/`) with automatic pre-restore safety backups, and toggle mods in `mods/` on or off in one click.

#### 4. 🎨 Modern Dark Jungle & Banana Gold Setup Wizard (`DKB-Setup.exe`)
* **Standalone Zero-Dependency Executable:** Compiled with all Python/UI dependencies (`customtkinter`, `darkdetect`, `zstandard`, `Pillow`) embedded—fixing the `ModuleNotFoundError: No module named 'customtkinter'` startup error on clean machines.
* **Native `.nup` & Unpacked Dump Support:** Unpacks `.nup` containers natively and links/packs `exefs/` + `romfs/` (or `base/exefs` + `base/romfs`) folders without requiring `prod.keys` (`prod.keys` is only requested for encrypted `.nsp` / `.xci` files).
* **Selectable Controller UI Prompts & Desktop Shortcut:** Choose between **PlayStation 5 DualSense**, **Xbox Series X|S**, or **Nintendo Switch** button glyphs and create a 1-click Desktop shortcut with the multi-resolution Banana icon (`dkb.ico`).

---

### 📦 Downloads & Installation

Choose one of the packages below:

1. **`SteelTemple-DKB-Alpha1b-Full-Setup-Wizard.exe`** (~442 MB) *(or **`DKB-Setup.zip`**)* — **[Recommended Interactive Installer]**
   * Interactive 4-step Windows Setup Wizard that unpacks/links your game dump, deploys `DKBLauncher.exe`, `dkb.exe`, pre-warmed shader caches, and multi-vendor AI upscaler SDKs (DLSS 4.5, XeSS 1.3, Reflex), configures controller prompts, and creates your Desktop shortcut.

2. **`SteelTemple-DKB-Alpha1b-Portable-StandAlone.zip`** (~445 MB) — **[Zero-Install Portable Package]**
   * Pre-packaged, zero-install standalone environment. Includes `DKBLauncher.exe`, `dkb.exe`, pre-warmed shader/pipeline caches, and all vendor upscaler DLLs.
   * Simply extract to any folder (e.g. `C:\Games\DKB PC`), copy your dumped **`romfs/`** and **`exefs/`** (from Base v1.0.0) into the folder, and run `DKBLauncher.exe`.

3. **`SteelTemple-DKB-Alpha1b-Update.zip`** (~100 MB) — **[Drop-In Engine & Launcher Update]**
   * Lightweight update containing the latest `dkb.exe`, `DKBLauncher.exe`, core DLLs, and `CONTROLLER_GUIDE.txt` for existing installations. Extract over your game folder and overwrite when prompted. Preserves your save files and `dkb.ini`.

> [!IMPORTANT]
> **Game Files Required:** Like all static recompilations, you must provide your legitimately dumped Nintendo Switch 2 game assets (**Donkey Kong Bananza Base v1.0.0**): both **`romfs/`** and **`exefs/`** (containing `main.npdm`) must sit inside your game directory (or be extracted from your `.nup` dump by the Setup Wizard). No copyrighted Nintendo assets or keys are included.

---

### 🎮 In-Game Controls & Overlay Hotkeys

* **Open / Close In-Game Settings Menu:** Press **`[Select + Start]`** on controller (`Share + Options` on PS5 / `View + Menu` on Xbox) or **`[F1]` / `[Esc]`** on keyboard.
* **Cycle Performance Telemetry HUD (FPS / Frame Time / VRAM):** Click **`[L3 + R3]`** on controller or press **`[F10]`** on keyboard.
* **Toggle Fullscreen / Windowed:** Press **`[F11]`** or **`[Alt + Enter]`**.

---

**Feedback & Bug Reports:** When reporting an issue from Alpha 1 testing, please attach `<InstallFolder>\logs\dkb.log` on our **[GitHub Issues page](https://github.com/STS78721/dkb-BANANAS/issues)**. 🍌🌴✨
