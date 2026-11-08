# 🍌 SteelTempSaint's Donkey Kong Bananza PC Recomp 🎮⚡
### *Transforming Donkey Kong Bananza into a Flagship Modern PC Experience*

[![Latest Release](https://img.shields.io/github/v/release/STS78721/dkb-BANANAS?label=Latest%20Release&color=brightgreen)](https://github.com/STS78721/dkb-BANANAS/releases/latest)
[![Release Date](https://img.shields.io/github/release-date/STS78721/dkb-BANANAS?color=blue)](https://github.com/STS78721/dkb-BANANAS/releases/latest)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x86--64-informational)](https://github.com/STS78721/dkb-BANANAS)
[![Renderer](https://img.shields.io/badge/Renderer-Vulkan%201.3-red)](https://github.com/STS78721/dkb-BANANAS)
[![DualSense](https://img.shields.io/badge/Controller-PS5%20DualSense%20Native-blueviolet)](https://github.com/STS78721/dkb-BANANAS)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)
[![Community Feedback](https://img.shields.io/badge/Community-Feedback%20Welcome-orange)](https://github.com/STS78721/dkb-BANANAS/issues)

> [!IMPORTANT]
> **No copyrighted game files are included.** You need your own legally obtained copy of *Donkey Kong Bananza* (Nintendo Switch 2, Base **v1.0.0** `ExeFS` / `RomFS` or `.nup` container), dumped from your own console. No Nintendo binaries, ROMs, or cryptographic keys are distributed with this repository.

---

## 🌟 Our Vision: What We Want to Achieve

**SteelTempSaint's Donkey Kong Bananza PC Recomp (DKB)** is an enthusiast-driven, high-performance static recompilation of *Donkey Kong Bananza* (Nintendo Switch 2, 2025) into a native Windows x86-64 application with a Vulkan 1.3 renderer. There is no emulator at run time: all 180,061 ARM64 functions (`main` + `sdk`) are translated ahead-of-time into C, and Switch 2 NVN 2 (Ampere SM86) graphics calls and shaders are lowered and executed natively on your PC GPU.

Our goal is to **elevate *Donkey Kong Bananza* into a native, flagship PC experience** that harnesses modern PC hardware:
- **Next-Gen Tactile Immersion:** Native PlayStation 5 DualSense integration with 4-channel audio-driven voice-coil haptics, adaptive trigger tension for terrain smashing and rolling dashes, and real-time controller battery telemetry.
- **State-of-the-Art Rendering & Upscaling:** Multi-vendor AI upscaling hub featuring **NVIDIA DLSS 4.5 / DLSS-NR**, **Intel XeSS 1.3+**, **AMD FSR**, and **DLAA**, paired with ultra-low latency **NVIDIA Reflex** (`VK_NV_low_latency2`) and **AMD Anti-Lag 2**.
- **Destructible World Fidelity:** Full native passthrough geometry shader support (`NATIVE_GS=1`), Ampere RGB-mask `TXD` gradient texture lowering, and instanced light-quad fault protection for rock-solid stability across NVIDIA RTX, AMD RDNA, and Intel Arc GPUs.
- **A Completely Community-Guided Project:** Built for players, with players—featuring a Sony/Nixxes-inspired standalone launcher (`DKBLauncher.exe`) and a 1-click setup wizard (`DKB-Setup.exe`).

---

## 🎮 What Makes This Build Unique (Alpha 1 Feature Highlights)

### 🕹️ Sony PlayStation 5 DualSense & Native Controller Integration
* **4-Channel Haptic Streaming & Tactile Feedback:** Real-time audio-driven vibration and DualSense trigger rumble support (`rumble_triggers`, `rumble_strength`).
* **Selectable Button Prompt Layouts:** Switch effortlessly between **PlayStation 5 DualSense** (Monochrome & Color), **Xbox Series X|S** (Monochrome & Color), and **Nintendo Switch** button prompts (`pad_layout`).
* **Full In-Game Controller Overlay Navigation:** Open and control the entire Recomp settings menu with **`[Select + Start]`** and toggle the performance HUD with **`[L3 + R3]`** without touching a keyboard.

### 🖥️ Standalone Nixxes/Sony-Style PC Launcher (`DKBLauncher.exe`)
<p align="center">
  <img src="https://raw.githubusercontent.com/STS78721/dkb-BANANAS/bananza/launcher/launcher_showcase.png" alt="SteelTemple DKB Standalone Launcher" width="90%">
</p>

* **Synchronized In-Game Settings:** Configure Display, Upscaler (`Off`, `DLSS 4.5`, `FSR`, `XeSS`, `DLAA`), Upscaler Quality Preset, DLSS Preset (`Preset K`, `Preset L`, `Preset M`), Low Latency (`NVIDIA Reflex` / `AMD Anti-Lag 2`), Frame Generation, Frame Pacing (`30` / `60` / `120` / `Unlimited` FPS), FOV (`70`–`120`), Color Grading (`Default`, `Vivid`, `Warm`, `Cool`, `Cinema`), Audio, and Controller Glyphs before or during play.
* **Pre-Warm Vulkan Shaders:** 1-click multi-threaded shader and pipeline library pre-compilation directly into your GPU driver cache.
* **Pre-Flight Startup Protection:** Automatically verifies `exefs/main.npdm` and `romfs/` before launching, with a 1-click *Open Game Folder* prompt if missing.
* **Save Backup Vault & Mod Manager:** Instant timestamped save snapshots (`profile-dkb100/backups/save_<timestamp>/`) with pre-restore safety backups and 1-click `.disabled` mod toggling.

### ⚡ Upstream Bananza Engine Sync & Pre-Tested Alpha 1 Fixes
* **NVIDIA Cutscene & Save-Load Device-Loss Fix (`runtime/vk_exec_draw.c`):** Resolved `VK_ERROR_DEVICE_LOST` (`instruction pointer (invalid)`) crashes when loading saves and during the Ingot Isle Cave-In cutscenes by accurately identifying faulting per-instance light-quad draws (`count <= 6`, `>= 8` active streams, all active streams `divisor != 0`) plus 7 cutscene vertex stage origins—while preserving 100% of 3D world meshes, skyboxes, cave walls, and distant terrain (`0x03ff`–`0x7fff` per-vertex shaders).
* **Destructible Terrain & Opening Wall Restoration:**
  - Enabled native passthrough geometry stages by default (`NATIVE_GS=1`) so destructible terrain renders with full geometry and materials instead of black.
  - Integrated Ampere RGB-mask `TXD` gradient texture lowering (`lower_to_maxwell.h`) and shader translator patch `0019` (allowing instructions after unpredicated `CAL` calls to run, restoring the opening tutorial wall).
  - Allowed passthrough geometry shaders to read unforwarded inputs (`runtime/gfx_shader.c`).
* **Indirect Reset & Texture Fence Write-Back Integrity (`runtime/vk_exec_draw.c`, `runtime/vk_texture.c`, `runtime/vk_backend.c`):**
  - Enforced `vk_exec_read_buffer` in `vk_exec_reset_indirect` so destructible terrain indirect-reset pointer lists always resolve shadow/VRAM mirror memory cleanly.
  - Maintained synchronous 64 KB fence write-backs (`WB_SMALL_DEFAULT`) and sRGB mutable storage image views (`VK_IMAGE_CREATE_EXTENDED_USAGE_BIT`) so GPU-generated LUTs and distant environment maps never read stale zeros.
* **Indexed Shadow Memory Sync & Alpha-Test Key Rounding:**
  - Binary-searched union of pending GPU writes during shadow memory synchronization (`runtime/vk_memory.c`).
  - Rounded alpha-test pipeline key references to nearest `1/255` step (`runtime/vk_pipeline.c`) to eliminate per-frame pipeline compilation stutter during camera/scene fades.

---

## 📥 Quick Start & Downloads

Grab the latest prebuilt packages from our **[Latest Release (Alpha 1f)](https://github.com/STS78721/dkb-BANANAS/releases/tag/Alpha-1f)**:

### 🛠️ 1. All-In-One Setup Wizard (Recommended for New Players)
👉 **Download: [`SteelTemple-DKB-Alpha1f-Full-Setup-Wizard.exe`](https://github.com/STS78721/dkb-BANANAS/releases/download/Alpha-1f/SteelTemple-DKB-Alpha1f-Full-Setup-Wizard.exe)** *(or [`DKB-Setup.zip`](https://github.com/STS78721/dkb-BANANAS/releases/download/Alpha-1f/DKB-Setup.zip))*
1. Run the setup executable (**DKB PC Recomp - Setup (Alpha 1f)**).
2. Select your legally dumped **Donkey Kong Bananza v1.0.0** source:
   - **`.nup` container** (unpacked natively with zero external tools or keys required),
   - **Unpacked dump folder** containing `exefs/` and `romfs/` (or `base/exefs` and `base/romfs`), or
   - **`.nsp` / `.xci` container** (with your console `prod.keys`).
3. Choose your target installation directory (default: `C:\Games\DKB PC`), pick your preferred controller prompt style (**PS5 DualSense**, **Xbox Series X|S**, or **Nintendo Switch**), and click **Install & Launch**!

---

### 🎮 2. Portable Standalone Package (Zero-Install Zip)
👉 **Download: [`SteelTemple-DKB-Alpha1f-Portable-StandAlone.zip`](https://github.com/STS78721/dkb-BANANAS/releases/download/Alpha-1f/SteelTemple-DKB-Alpha1f-Portable-StandAlone.zip)**
1. Extract the archive into your chosen game folder (e.g. `C:\Games\DKB PC`).
   - *Includes `DKBLauncher.exe`, `dkb.exe`, `SDL3.dll`, pre-warmed shader/pipeline caches, and Nodix Super Motion SMRS / Frame Generation.*
2. Copy **both** your dumped **`exefs`** and **`romfs`** folders (from your legally owned Base v1.0.0 dump) directly into this folder:
   ```text
   C:\Games\DKB PC\
   ├── dkb.exe                <-- Recompiled Native x86-64 Game Engine
   ├── DKBLauncher.exe        <-- Standalone PC Launcher (Alpha 1f)
   ├── dkb.ini                <-- Synchronized Game & Graphics Configuration
   ├── SDL3.dll, libopus-0.dll, etc.
   ├── exefs/                 <-- Contains main, sdk, main.npdm (from your v1.0.0 dump)
   └── romfs/                 <-- Contains romfs.bin or unpacked game assets
   ```
3. Launch **`DKBLauncher.exe`** to configure graphics, pre-warm shaders, and hit **PLAY**!

---

### ⚡ 3. Upgrading Existing Builds (Drop-in Update)
👉 **Download: [`SteelTemple-DKB-Alpha1f-Update.zip`](https://github.com/STS78721/dkb-BANANAS/releases/download/Alpha-1f/SteelTemple-DKB-Alpha1f-Update.zip)** (~100 MB)
1. Extract and overwrite files directly into your existing game directory (`C:\Games\DKB PC`).
2. Preserves all your save files (`profile-dkb100/save`), custom `dkb.ini` configuration, and mods.

---

## 🎮 In-Game Controls & Overlay Shortcuts

| Action | Controller Shortcut | Keyboard Shortcut |
| :--- | :--- | :--- |
| **Open / Close In-Game Settings Menu** | **Select + Start** (`Share + Options` on PS5 / `View + Menu` on Xbox) | **`F1`** or **`Esc`** |
| **Cycle Performance Overlay (FPS / VRAM)** | **L3 + R3** (Click Left Stick + Right Stick together) | **`F10`** |
| **Toggle Fullscreen / Windowed** | — | **`F11`** or **`Alt + Enter`** |

---

## 🛠️ Credits & Acknowledgments

- **[Lucas-blip-png/dkb-pc-recomp](https://github.com/Lucas-blip-png/dkb-pc-recomp)** & **[TotK Recomp](https://github.com/valentderah/totk-pc-recomp)** by valentderah — Core static recompilation architecture, Horizon OS host, and NVN 2 / Vulkan backend.
- **[Eglantine](https://git.eden-emu.dev/Franseven/PokeDinner-a-Eglantine-Fork)** (Eden Emulator Project) & **[Mesa NAK](https://gitlab.freedesktop.org/mesa/mesa)** — Switch 2 Ampere (SM86) to Maxwell shader lowering.
- **[GRAnimated/DKBananza](https://github.com/GRAnimated/DKBananza)** — Function symbols and reverse-engineering research.
- **NVIDIA, Intel & AMD** — DLSS 4.5, Streamline, Reflex, XeSS, and FidelityFX Super Resolution SDKs.
- **SteelTemple Community & Alpha Testers** — Testing, logs, and feedback!

---

## 📜 License

DKB Recomp is distributed under the **[GNU GPL v3 or later](LICENSE)** (incorporating Eglantine's GPL Ampere shader lowering in `runtime/third_party/eglantine/`). Files originating from TotK Recomp retain their **[MIT License](LICENSE-MIT)**; third-party notices are detailed in **[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)**.

*Thank you to all contributors, testers, and players building the ultimate Donkey Kong Bananza PC experience!* 🍌🌴✨
