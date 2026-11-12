# Eglantine Ampere lowering (GPL-3.0-or-later)

`shader_recompiler/frontend/ampere/lower_to_maxwell.h`, `program_capture.h`, and `geometry_exit.h` originate from
Eglantine (an Eden-derived Switch 2 emulator) at the commit in `UPSTREAM_COMMIT`. Copyright 2026 Eden Emulator
Project, GPL-3.0-or-later; their encoding reference is Mesa NAK's `sm70_encode.rs` (MIT, Copyright 2022 Collabora,
Ltd.).

They rewrite Switch 2 (Ampere, SM86) shader code as Maxwell instructions, which the shader translator this project
already uses can take. `common/common_types.h` is ours: the fixed-width type names the headers expect.

Merged upstream & local extensions:
- `Orchid` commits `8837379` / `88fdb54` (GPL-3.0-or-later): 64-bit constant-buffer loads (`0x625` `IMAD.WIDE` addend
  and `0xab9` `ULDC.64`) at unsigned offsets `>= 0x8000` emit two 32-bit `MOV c[bank][offset]` reads rather than
  `LDC.64` (whose 16-bit offset is signed on Maxwell).
- `Orchid` commit `cf66896` (GPL-3.0-or-later): `program_capture.h` treats unpredicated `CALL.REL.NOINC` (`0x7944`) as
  a real subroutine call so post-`EXIT` library subroutines capture through `RET`.
- Local extensions: `0x927` (`ISBEWR`) no-op, `0xb07` constant-buffer `FRND.F32`, and pure-Maxwell `MUFU.TANH`
  (`operation == 9` lowered via `EX2` + `RCP` into scratch `R249..R252`) so unmodified Maxwell decoders translate `TANH`
  without custom IR opcodes.

Because these files are GPL-3.0-or-later, this repository is distributed under GPL-3.0-or-later (see `LICENSE`).
