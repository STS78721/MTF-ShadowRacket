## 🍌 Alpha 1c: Upstream Engine Integration, SPIR-V FMZ Cutscene Fix, Driver Fault Dumper & 1-Click Auto-Updater ⚡

<p align="center">
  <img src="https://raw.githubusercontent.com/STS78721/dkb-BANANAS/bananza/launcher/launcher_showcase.png" alt="SteelTemple DKB Standalone Launcher" width="90%">
</p>

Welcome to **Alpha 1c**, the latest community testing release of the **SteelTempSaint Donkey Kong Bananza PC Recomp (DKB)**!

Modeled directly after our flagship **SteelTempSaint ToTK Recomp** architecture and modern PlayStation/Nixxes PC ports, this release transforms *Donkey Kong Bananza* (Nintendo Switch 2) into a native Windows x86-64 Vulkan 1.3 application—complete with a sleek Banana Gold & Jungle Setup Wizard, our standalone `DKBLauncher.exe`, multi-vendor AI upscaling (NVIDIA DLSS 4.5 / Intel XeSS 1.3 / AMD FSR / DLAA), NVIDIA Reflex & Anti-Lag 2, and all pre-tested fixes for cutscenes, skyboxes, and destructible terrain.

---

### 🔥 What's New in Alpha 1c

* **🛡️ SPIR-V Fused-Multiply-Zero (FMZ) Hardware Emulation (`runtime/vk_pipeline.c`, `runtime/cfg.c`):**
  * Implemented an automatic SPIR-V instruction rewriter for 32-bit float `OpFMul` and GLSL.std.450 `Fma` instructions so that `0 * x = 0` holds strictly even when `x` is `±Infinity` or `NaN` (matching NVIDIA Ampere/Ada/Blackwell hardware FMZ behavior).
  * Enabled by default for all vertex stages (`DKB_FMZ=vertex`), resolving the infamous Issue #75 device lost crash during the end-of-tutorial cutscene on NVIDIA GeForce RTX GPUs mathematically without dropping visual passes!
  * Added configurable controls via `TOTK_FMZ=0/vertex/all` and bisection mask `TOTK_FMZ_SEL=<mask:val>`.
* **🔍 Live GPU Diagnostics & Driver Fault Dumps (`runtime/vk_device.c`, `runtime/vk_crumbs.c`, `runtime/vk_pipeline.c`):**
  * Integrated `VK_NV_device_diagnostic_checkpoints` and `VK_EXT_device_address_binding_report` under `DKB_GPU_CHECKPOINTS=1`.
  * Automatically dumps driver binary fault data directly to `logs/dkb-fault-<time>.bin` on `VK_ERROR_DEVICE_LOST` for zero-guesswork troubleshooting.
  * Added stage origin filter diagnostics (`DKB_SKIP_VS` / `DKB_SKIP_FS`), SPIR-V bytecode dumper (`DKB_DUMP_SPV=1`), and hot shader overriding (`DKB_SPV_OVERRIDE=<hash>:<path.spv>`).
* **⚡ Vulkan Pipeline & Command Recorder Optimizations (`runtime/vk_rec.c`, `runtime/vk_pipeline.c`):**
  * Command ring buffer `head` and `tail` pointers are now cache-line aligned (`alignas(64)`) to eliminate multi-threaded CPU cache ping-pong / false sharing.
  * Added batch recording support (`TOTK_REC_BATCH`) for lower CPU submission overhead.
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

- **`SteelTemple-DKB-Alpha1c-Update.zip`** (`~98 MB`): Lightweight 1-click drop-in update package. If you already have Alpha 1 or 1b installed, simply click **Check for Updates** in `DKBLauncher.exe` to auto-update in 1 click, or extract this archive over your game directory!
- **`SteelTemple-DKB-Alpha1c-Portable-StandAlone.zip`** (`~403 MB`): Full standalone zero-install PC package. Extract to `C:\Games\DKB PC` (or any directory), copy your legally dumped `exefs/` and `romfs/` files, and launch `DKBLauncher.exe`!
- **`SteelTemple-DKB-Alpha1c-Full-Setup-Wizard.exe`** (`~435 MB`) / **`DKB-Setup.zip`**: All-in-one graphical installer with `.nup` container unpacking, loose RomFS indexing, desktop shortcut creation, and controller prompt selection.
