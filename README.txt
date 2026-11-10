================================================================================
  DONKEY KONG BANANZA PC RECOMP (DKB) - ALPHA RELEASE
  High-Performance Static Recompilation for Native Windows x86-64
================================================================================

1. LEGAL NOTICE & CLEAN-ROOM COMPLIANCE:
   -----------------------------------------------------------------------------
   This software is an independent static recompilation project.
   In strict compliance with Nintendo copyright laws and clean-room recompilation
   rules:
   • NO proprietary Nintendo game code, ExeFS binaries, NPDM files, RomFS assets,
     keys, or firmware files are distributed with this software.
   • All game assets and code must be extracted directly from YOUR OWN legally
     obtained copy of Donkey Kong Bananza for Nintendo Switch 2 (Base v1.0.0).
   • The setup wizard unpacks the assets on your local PC from your legitimate
     .nup container, .nsp / .xci dump, or dumped game folder.

2. SYSTEM REQUIREMENTS:
   -----------------------------------------------------------------------------
   • OS:        Windows 10 / 11 64-bit
   • CPU:       x86-64 processor with AVX2 support
   • GPU:       Vulkan 1.3 capable GPU (NVIDIA RTX / GTX 10-series+, AMD RDNA / GCN,
                Intel Arc) with updated graphics drivers
   • Memory:    16 GB RAM minimum
   • Storage:   ~30 GB free storage on target install drive

3. HOW TO INSTALL:
   -----------------------------------------------------------------------------
   1. Run 'DKB-Setup.exe' (or 'Donkey-Kong-Bananza-Setup.exe').
   2. Select your legally dumped game source:
      - .nup container (recommended — unpacked natively with zero tools)
      - .nsp / .xci file (requires your console prod.keys)
      - Folder containing 'romfs' and 'exefs' directories
   3. Choose your desired install location (e.g. C:\Games\DKB PC).
   4. Configure your preferred options:
      - Multi-Vendor AI Upscalers (NVIDIA DLSS 4.5, DLSS-NR, Intel XeSS, AMD FSR)
      - Low Latency Modes (NVIDIA Reflex, AMD Anti-Lag 2, Intel XeLL)
      - Controller Glyphs (PlayStation 5 DualSense, Xbox Series X|S, Switch)
      - 1-Click Desktop Shortcut
   5. Click "Install" and wait for the wizard to complete.

4. LAUNCHING & IN-GAME CONTROLS:
   -----------------------------------------------------------------------------
   Launch the game using the desktop shortcut or 'DKBLauncher.exe' inside the
   installation folder.
   
   • In-Game Settings Menu:
     - Keyboard:   Press [F1] or [Esc]
     - Controller: Press [Select + Start] simultaneously
                   (PS: [Share] + [Options] | Xbox: [View] + [Menu])
   • Performance HUD (FPS / Frametime / VRAM):
     - Keyboard:   Press [F10] to cycle overlay modes
     - Controller: Click [L3 + R3] simultaneously
   • Fullscreen Toggle:
     - Keyboard:   Press [F11] or [Alt + Enter]

5. TROUBLESHOOTING & LOGS:
   -----------------------------------------------------------------------------
   • Installation logs: %TEMP%\dkb-setup.log
   • Game runtime logs: <InstallFolder>\logs\totk.log (and totk.1.log to totk.4.log)
   • Black screen / instant exit on start:
     Ensure your graphics driver is updated and supports Vulkan 1.3.
     Verify that your dump contains a valid 'exefs/main.npdm' and 'romfs/'.

================================================================================
