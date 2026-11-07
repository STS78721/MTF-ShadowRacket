# 🍌 Donkey Kong Bananza PC Recomp (DKB)
## Release Alpha 1: Modern Setup Wizard, Standalone Launcher, Multi-Vendor AI Upscalers & Cutscene/Terrain Fixes 🎮✨

Welcome to **Alpha 1** of **SteelTempSaint's Donkey Kong Bananza PC Recomp**! This initial testing release brings *Donkey Kong Bananza* (Nintendo Switch 2) to native Windows x86-64 with a custom Vulkan 1.3 renderer, a sleek Banana Gold & Jungle GUI Setup Wizard, a Sony/Nixxes-inspired standalone PC Launcher (`DKBLauncher.exe`), multi-vendor AI upscaling (NVIDIA DLSS 4.5 / Intel XeSS / AMD FSR / DLAA), native DualSense support, and critical rendering fixes for destructible terrain, skyboxes, and cutscenes.

> [!IMPORTANT]
> **Game Version Requirement: Donkey Kong Bananza Base v1.0.0**
> You must supply your own legally dumped copy of **Donkey Kong Bananza v1.0.0** (`.nup` container, unpacked `exefs` + `romfs` folder, or `.nsp`/`.xci` with keys). No copyrighted Nintendo code, assets, or keys are included in this release.

---

## 🌟 What's Included in Alpha 1

### 🎨 1. Modern Dark Jungle & Banana Gold GUI Installer (`DKB-Setup.exe`)
- **CustomTkinter 4-Step Wizard:** Clean, guided setup (`1. Legal Game Files & Keys` ➔ `2. DLSS & Controllers` ➔ `3. Controller Guide` ➔ `4. Finalize & Launch`) with full `◀ Back` and `Next ▶` synchronization.
- **Zero-Tool `.nup` & Folder Extraction:** Natively unpacks `.nup` containers and links/packs `exefs` + `romfs` directories without requiring `prod.keys` (keys are only requested if extracting encrypted `.nsp`/`.xci` files).
- **Standalone Single-File Executable:** Bundled with all Python/UI dependencies (`customtkinter`, `darkdetect`, `zstandard`, `Pillow`) and a 7-layer high-resolution Banana icon (`dkb.ico`).

### 🖥️ 2. Standalone Nixxes-Style PC Launcher (`DKBLauncher.exe` - Alpha 1)
- **Full In-Game Settings Sync:** Every setting in the launcher maps 1:1 to `dkb.ini` and the in-game `F1` overlay menu:
  - **Upscalers:** `Off`, `NVIDIA DLSS 4.5`, `AMD FSR`, `Intel XeSS`, and `DLAA` with Quality Presets and DLSS Presets (`Preset K`, `Preset L`, `Preset M`).
  - **Low Latency & Frame Gen:** `NVIDIA Reflex` (`On` / `On + Boost`), `AMD Anti-Lag 2`, and `AI Frame Generation`.
  - **Display & Color Grading:** Fullscreen/Windowed mode, Output Resolution (`720p` to `4K`), Render Scale (`50%`–`200%`), FOV (`70`–`120`), and Color Presets (`Default`, `Vivid`, `Warm`, `Cool`, `Cinema`).
- **Pre-Warm Vulkan Shaders, Save Vault & Mod Manager:** Built-in tools to pre-compile shaders, back up/restore saves safely, and toggle mods in 1 click.

### 🛠️ 3. Core Vulkan Renderer & NVIDIA Stability Fixes
- **Cutscene & Save-Load Device-Loss Fix:** Resolved NVIDIA `VK_ERROR_DEVICE_LOST` (`instruction pointer (invalid)`) crashes during save loading and the Ingot Isle Cave-In cutscenes by accurately detecting and skipping faulting per-instance light-quad draws (`count <= 6`, `divisor != 0` across all active streams) without touching any 3D meshes.
- **Full Skybox, Cave Walls & Destructible Terrain Rendering:**
  - Enabled native passthrough geometry stages by default (`NATIVE_GS=1`) so destructible terrain renders properly instead of black.
  - Restored indirect-reset buffer reads (`vk_exec_read_buffer`) and synchronous texture fence write-backs so distant environment maps, skyboxes, and terrain chunks render with full textures and lighting.
  - Integrated Ampere RGB-mask `TXD` gradient texture lowering and shader translator patch `0019` (restoring the opening tutorial wall).

### 🎮 4. Controller UI & In-Game Overlay Hotkeys
- **Selectable Button Prompts:** Choose between **PlayStation 5 DualSense**, **Xbox Series X|S**, or **Nintendo Switch** button layouts during installation or in the launcher.
- **Quick In-Game Hotkeys:**
  - **Open / Close Settings Menu:** Press **`[Select + Start]`** on controller (`Share + Options` on PS5 / `View + Menu` on Xbox) or **`[F1]` / `[Esc]`** on keyboard.
  - **Performance Telemetry HUD:** Click **`[L3 + R3]`** on controller or press **`[F10]`** on keyboard.
  - **Fullscreen Toggle:** Press **`[F11]`** or **`[Alt + Enter]`**.

---

## 📦 How to Install (For Alpha 1 Testers)

1. Download **`DKB-Setup.exe`** (or extract **`DKB-Setup.zip`** / **`Donkey-Kong-Bananza-Setup.zip`**).
2. Run **`DKB-Setup.exe`**.
3. Select your **Donkey Kong Bananza v1.0.0** dump (`.nup` file or folder containing `exefs` & `romfs`), choose your install folder (default `C:\Games\DKB PC`), pick your controller layout, and click **Install**.
4. Launch the game via the **Donkey Kong Bananza** Desktop shortcut or **`DKBLauncher.exe`**!

---

**Feedback & Bug Reports:** When reporting an issue from Alpha 1 testing, please attach `<InstallFolder>\logs\dkb.log` on our **[GitHub Issues page](https://github.com/STS78721/dkb-BANANAS/issues)**. 🍌🌴✨
