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
- **Community-Guided Development:** Built for players, with players—featuring a Sony/Nixxes-inspired standalone launcher (`DKBLauncher.exe`) and a 1-click setup wizard (`DKB-Setup.exe`).

---

## 🎮 What Makes Alpha 1 Unique (Feature Highlights)

### 🖥️ Standalone Nixxes/Sony-Style PC Launcher (`DKBLauncher.exe`)
* **Synchronized In-Game Settings:** Configure Display, Upscaler (DLSS 4.5 / XeSS / FSR / DLAA), Low Latency (Reflex / Anti-Lag 2), Frame Generation, Frame Pacing (30 / 60 / 120 / Unlimited FPS), Audio, and Controller Glyphs before or during play.
* **Pre-Warm Vulkan Shaders:** 1-click multi-threaded shader and pipeline library pre-compilation into the GPU driver cache.
* **Pre-Flight Startup Protection:** Automatically verifies `exefs/main.npdm` and `romfs/` before launching, with a 1-click *Open Game Folder* prompt if missing.
* **Save Backup Vault & Mod Manager:** Instant timestamped save snapshots with pre-restore safety backups and 1-click `.disabled` mod toggling.

### ⚡ Multi-Vendor AI Upscalers & Low-Latency Pipeline
* **NVIDIA DLSS 4.5 & DLAA:** Native NGX / Streamline integration with selectable presets (`Preset K`, `Preset L`, `Preset M`) and character motion-vector masking.
* **Intel XeSS 1.3+ & AMD FSR:** Cross-vendor hardware-accelerated upscaling and frame generation (`libxess.dll`, `libxess_fg.dll`).
* **NVIDIA Reflex & AMD Anti-Lag 2:** Hardware-synchronized low-latency frame pacing (`On` / `On + Boost`) for responsive platforming and combat.

### 🛠️ Engine & Shader Breakthroughs (Alpha 1)
* **NVIDIA Cutscene & Save-Load Fault Prevention:** Intelligent per-instance light-quad guard in `runtime/vk_exec_draw.c` that skips faulting 10-stream instanced light quads (`count <= 6`, all streams `divisor != 0`) while preserving 100% of 3D world meshes, skyboxes, cave walls, and destructible terrain.
* **Destructible Terrain & Opening Wall Restoration:** Enabled native passthrough geometry stages by default (`NATIVE_GS=1`), added Ampere RGB-mask `TXD` lowering in `lower_to_maxwell.h`, and integrated translator patch `0019` so instructions following unpredicated `CAL` calls execute properly.
* **Native Switch 2 Video Cutscenes (`nn::codec`):** Hardware-accelerated VP9 video decoding (`runtime/ov_codec.c`) for seamless guide movies and story cutscenes.
* **Indexed Shadow Memory Sync:** Fast binary-searched union of pending GPU writes during shadow memory synchronization (`runtime/vk_memory.c`) and sRGB mutable storage image views (`runtime/vk_texture.c`).

---

## 📥 Quick Start & Installation (Alpha 1)

### 🎮 Option A: Modern All-In-One Setup Wizard (Recommended)
1. Download **`DKB-Setup.exe`** (or **`Donkey-Kong-Bananza-Setup.exe`** / `.zip`).
2. Launch the setup executable (**DKB PC Recomp - Setup (Alpha 1)**).
3. Select your legally dumped **Donkey Kong Bananza v1.0.0** source:
   - **`.nup` container** (unpacked natively with zero external tools or keys required),
   - **Unpacked dump folder** containing `exefs/` and `romfs/` (or `base/exefs` and `base/romfs`), or
   - **`.nsp` / `.xci` container** (with your console `prod.keys`).
4. Choose your target installation directory (default: `C:\Games\DKB PC`), select your preferred controller prompt style (**PS5 DualSense**, **Xbox Series X|S**, or **Nintendo Switch**), and click **Install & Launch**!

### 📂 Expected Game Directory Layout
```text
C:\Games\DKB PC\
├── dkb.exe                <-- Recompiled Native x86-64 Game Engine
├── DKBLauncher.exe        <-- Standalone PC Launcher (Alpha 1)
├── dkb.ini                <-- Synchronized Game & Graphics Configuration
├── SDL3.dll, nvngx_dlss.dll, libxess.dll, etc.
├── exefs/                 <-- Contains main.npdm (from your v1.0.0 dump)
└── romfs/                 <-- Contains romfs.bin or unpacked game assets
```

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

*DKB Recomp is an independent, non-commercial fan project and is not affiliated with or endorsed by Nintendo. Donkey Kong Bananza and Nintendo Switch 2 are trademarks of Nintendo.*
