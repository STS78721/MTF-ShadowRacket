# Acknowledgments & Special Thanks

**Mario Tennis Fever PC Recompilation (MTF Recomp)** exists thanks to the dedicated research, tools, code, and insights of many pioneers in the console reverse engineering and emulation communities. We extend our deepest gratitude to everyone below:

---

## 🏛️ Static Recompilation Pioneers
- **[TotK Recomp](https://github.com/valentderah/totk-pc-recomp)** – **Valiantsin Dzerakh (valentderah)** & contributors  
  For architecting the static recompilation engine, the Horizon OS user-space host, differential CPU instruction testing against Unicorn, and the Vulkan graphics execution framework.
- **[DKB Recomp](https://github.com/Lucas-blip-png/dkb-pc-recomp)** – **Lucas-blip-png**, **[sagaopc](https://github.com/sagaopc/dkb-pc-recomp)**, **[sostenesfreitas](https://github.com/sostenesfreitas/dkb-pc-recomp)** & contributors  
  For pioneering the first public Nintendo Switch 2 static recompilation, implementing hundreds of NVN 2 API entry points, adapting the Ampere shader pipeline, and proving Switch 2 recompilation on native PC hardware.
- **[MKW Recomp](https://github.com/STS78721/MKW-THWOMP)** – **STS78721**  
  For pioneering research into multi-core Horizon OS guest threading, Switch 2 NVN 2 texture formats, and PC recompilation pipelines.
- **[LAS Recomp](https://github.com/peiikai/LASRecomp)** – **Peiikai**  
  For the original AArch64 ARM64-to-C lifter architecture, SIMD vector lowerings, and foundational Vulkan format mappings.
- **[MacNativeGames](https://github.com/ly05010419/MacNativeGames)** – **ly05010419** & contributors  
  For core Horizon runtime services, NPDM loading, audio renderers, and native host integration.
- **[SavageWindRecomp](https://github.com/Revivedx/SavageWindRecomp)** – **Revivedx** & contributors  
  For Switch recompilation optimizations, performance monitors, and memory synchronization techniques.
- **[nxnative](https://github.com/seedds/nxnative)** – **seedds**  
  For early research into native Switch execution on PC.

---

## 🎨 GPU Reverse Engineering, Shaders & Emulation
- **[Eglantine / Eden Emulator Project](https://git.eden-emu.dev/Franseven/PokeDinner-a-Eglantine-Fork)** – **Franseven** & the Eden team  
  For the Ampere-to-Maxwell shader lowering compiler (`lower_to_maxwell.h`) and groundbreaking Switch 2 GPU architectural documentation.
- **[Mesa NAK](https://gitlab.freedesktop.org/mesa/mesa)** – **Faith Ekstrand** and Collabora  
  For the open-source SM70+ (Volta, Turing, Ampere) instruction encoding models and hardware execution research.
- **[Ryujinx](https://github.com/Ryujinx/Ryujinx)** – The Ryujinx Team  
  For the reference Maxwell/SPIR-V shader recompiler and translator.
- **[deko3d](https://github.com/devkitPro/deko3d)** – **FinCS** & the **devkitPro** team  
  For low-level hardware documentation, NVN structures, and homebrew graphics libraries.

---

## ⚙️ Horizon OS, Reverse Engineering & File Formats
- **[Atmosphère](https://github.com/Atmosphere-NX/Atmosphere)** & **[hactool](https://github.com/SciresM/hactool)** – **SciresM** & the Reswitched Team  
  For documentation of Nintendo Switch file systems (PFS0, RomFS, ExeFS, NPDM) and system architecture.
- **[Switchbrew](https://switchbrew.org)** & The Switch Homebrew Community  
  For maintaining the exhaustive encyclopedia of system calls, IPC commands, and service interfaces.

---

## 📦 Core Libraries & Ecosystem
- **[The Khronos Group](https://www.khronos.org/vulkan/)** – Vulkan 1.3 specification and ecosystem.
- **[Simple DirectMedia Layer (SDL3)](https://libsdl.org)** – **Sam Lantinga** & contributors (cross-platform windowing, controller input, and audio).
- **[Vulkan Memory Allocator (VMA)](https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator)** – **Adam Sawicki** and **AMD / GPUOpen** (GPU memory management).
- **[libvpx](https://chromium.googlesource.com/webm/libvpx)** – The **WebM Project / Google** (VP9 movie decoding).
- **[libopus](https://opus-codec.org/)** – **Xiph.Org Foundation**, Mozilla, Skype (Opus audio decoding).
- **[Zstandard (zstd)](https://github.com/facebook/zstd)** – **Yann Collet** and Meta (high-performance compression).

---

## 🎾 Community & Early Hardware Testers
- Thank you to all early community members, testers across NVIDIA GeForce, AMD Radeon, and Intel Arc GPUs, and everyone reporting logs, submitting pull requests, and advancing the frontier of Nintendo Switch 2 static recompilation on PC!
