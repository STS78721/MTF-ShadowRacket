## 🍌 Alpha 1d: Super Motion Frame Generation, Lazy Memory Pools, Upstream Engine Sync & Vendor Upscaler Stack ⚡

<p align="center">
  <img src="https://raw.githubusercontent.com/STS78721/dkb-BANANAS/bananza/launcher/launcher_showcase.png" alt="SteelTemple DKB Standalone Launcher" width="90%">
</p>

Welcome to **Alpha 1d**, the latest community testing release of the **SteelTempSaint Donkey Kong Bananza PC Recomp (DKB)**!

Modeled directly after our flagship **SteelTempSaint ToTK Recomp** architecture and modern PlayStation/Nixxes PC ports, this release transforms *Donkey Kong Bananza* (Nintendo Switch 2) into a native Windows x86-64 Vulkan 1.3 application—complete with a sleek Banana Gold & Jungle Setup Wizard, our standalone `DKBLauncher.exe`, multi-vendor AI upscaling (NVIDIA DLSS 4.5 / Intel XeSS 1.3 / AMD FSR 3.1 / DLAA), Super Motion Frame Generation, NVIDIA Reflex & Anti-Lag 2, and all pre-tested fixes for cutscenes, skyboxes, and destructible terrain.

---

### 🔥 What's New in Alpha 1d

* **⚡ Super Motion Frame Generation Pipeline Fixes (`runtime/gfx_present.c`):**
  * Decoupled `DKB_FG_MODE` (`dlss_fg`, `fsr3_fg`, `xefg`, `msm_fg`) from legacy `frame_gen = 0` configuration blocks so Frame Generation engages reliably across all hardware tiers.
  * Active generator and multiplier badges now display accurately in the in-game performance overlay (`[DLSS FG 3x] 143 FPS (Base 60)`).
* **🏎️ Lazy Memory Pool Imports & Fence Waits (`runtime/vk_memory.c`):**
  * Ported `TOTK_POOL_LAZY=1` and `TOTK_HOST_PROPS_CACHE=1` from upstream, deferring guest memory imports to first GPU use and cutting guest-memory import time by up to 95%.
  * Defaulted `TOTK_POOL_FINI_WAIT=fence` to eliminate queue idle stalls during level transitions.
* **🛡️ Pipeline Capacity & Geometry Shader Guards (`runtime/vk_pipeline.c`, `runtime/vk_exec_draw.c`):**
  * Added `maxPerStageDescriptorSamplers` capacity validation (`push_fits`) and geometry stage support guards (`vk_geometry_supported`).
  * Preserved voxel varyings on AMD GPUs and lowered 12 Ampere compute and texture fetching stages for native Ampere instruction compatibility.
* **🎯 DLSS Pipeline Decoupling & Depth Sanitization (`runtime/nvn_api_dlss.c`, `runtime/vk_dlaa.c`):**
  * Decoupled depth buffer copying from camera motion vector generation so depth memory is guaranteed clean and valid.
  * Removed inverted depth flags and added automatic 1:1 DLAA mode resolution scaling.
  * Restored camera reprojection VP locking across uniform banks `c4` and `c8`.
* **🎨 Anti-Aliasing & Ambient Occlusion Stack (`runtime/vk_smaa.c`, `runtime/vk_ao.c`):**
  * Integrated Subpixel Morphological Anti-Aliasing (SMAA 1x) with automatic bypass during native DLAA/DLSS.
  * Added SSAO / HBAO ambient occlusion compute pipelines with in-game overlay and launcher controls.
  * Explicitly declared `StorageImageReadWithoutFormat` capability for unknown-format storage images.
* **🌐 Portuguese Locale Normalization (`runtime/locale.c`):**
  * Automatically maps base Portuguese `pt` locale code to `pt-BR` for Bananza.
* **🔄 1-Click Seamless In-Place Auto-Updater (`launcher/DKBLauncher.py`):**
  * Standalone launcher now automatically detects online updates from `STS78721/dkb-BANANAS`.
  * 1-click update: downloads, verifies SHA-256 integrity, extracts in-place, and relaunches seamlessly without manual file manipulation!
* **🛡️ 100% Core Proprietary Features Preserved:**
  * Retained AMD RX 9070 XT 1 MiB zero dummy buffer & full range SSBO binding (`ZERO_BYTES 1048576u`) in `vk_exec_draw.c` to prevent hardware page faults at `0x1000`.
  * Retained 1500ms fence wait (`ONESHOT_WAIT_MS 1500u`) preventing Windows 2s TDR driver resets on long shader compilations.
  * Retained AMD recorder default 0 for stutter-free command dispatch.
  * Retained NVIDIA DLSS 4.5 Super Resolution, DLAA, Reflex Low Latency 2.
  * Retained Intel XeSS 1.3 Super Resolution, XeLL Low Latency, and Frame Generation.
  * Retained Sony DualSense native adaptive triggers, haptic feedback, and audio haptics.
  * Retained F10 Real-Time Performance HUD & in-game menu.

---

### 📥 Downloads & Installation

- **`SteelTemple-DKB-Alpha1d-Update.zip`** (`~100 MB`): Lightweight 1-click drop-in update package. If you already have Alpha 1, 1b, or 1c installed, simply click **Check for Updates** in `DKBLauncher.exe` to auto-update in 1 click, or extract this archive over your game directory!
- **`SteelTemple-DKB-Alpha1d-Portable-StandAlone.zip`** (`~522 MB`): Full standalone zero-install PC package. Extract to `C:\Games\DKB PC` (or any directory), copy your legally dumped `exefs/` and `romfs/` files, and launch `DKBLauncher.exe`!
- **`SteelTemple-DKB-Alpha1d-Full-Setup-Wizard.exe`** (`~463 MB`) / **`DKB-Setup.zip`**: All-in-one graphical installer with `.nup` container unpacking, loose RomFS indexing, desktop shortcut creation, and controller prompt selection.
