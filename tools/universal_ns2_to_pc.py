"""Universal NS2 to PC: Multi-game Switch 2 static recompiler profiler, project initializer, and build driver.

Synthesizes engineering techniques across DKB Bananza, MKW-THWOMP, MTF-ShadowRacket, NotRexed Hookshot,
MacNativeGames, Fritchii (NX2_NOTES), Lichii, and Eglantine:
  - ExeFS module/NPDM/ELF64 relocation audit & exact sdk->main/subsdk* imported nn::* census
  - ARM64 instruction lifter decode coverage pre-check against recomp/lifter.py (no game output written)
  - NVN / NVN2 GetProcAddress string census against runtime/nvn_procs*.inc
  - Paired BNSH shader census across all 9 variation slots (Vertex, TCS, TES, Geometry, Pixel, Compute, Task, Mesh)
  - SM86 Ampere opcode scan vs Eglantine/Eden lower_to_maxwell.h + >5000-insn compile-stall detector
  - Switch 2 ('Ounc') & Switch 1 ('NX  ') BNTX texture format, VRAM, and >2^28 sparse-texel array detector
  - 1-command `init` and `build` workflows for bringing up new Switch 2 titles cleanly without polluting git.

Usage:
    python tools/universal_ns2_to_pc.py scan --exefs "C:\\Games\\MKW PC\\exefs" --romfs "C:\\Games\\MKW PC\\romfs"
    python tools/universal_ns2_to_pc.py init --ver mygame100 --short mygame --name "My Switch 2 Game" --exefs ... --romfs ...
    python tools/universal_ns2_to_pc.py build --ver mygame100 --exefs ... --romfs ...
"""

import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

try:
    import compression.zstd as zstd
except ImportError:
    zstd = None

try:
    import lz4.block as lz4_block
except ImportError:
    lz4_block = None

ROOT = Path(__file__).resolve().parent.parent
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
CONTROL_MAGIC = b"\x34\x12\x76\x98"
BNSH_SLOTS = (8, 16, 24, 32, 40, 48, 56, 64, 72)

RELOC_NAMES = {
    257: "R_AARCH64_ABS64",
    1024: "R_AARCH64_COPY",
    1025: "R_AARCH64_GLOB_DAT",
    1026: "R_AARCH64_JUMP_SLOT",
    1027: "R_AARCH64_RELATIVE",
    1028: "R_AARCH64_TLS_IMP_REL",
    1029: "R_AARCH64_TLS_TPREL64",
    1030: "R_AARCH64_TLS_DTPREL64",
    1031: "R_AARCH64_TLSDESC",
    1032: "R_AARCH64_IRELATIVE",
}

NVN2_STAGE_NAMES = {
    0: "vertex",
    1: "pixel",
    2: "geometry",
    3: "tess-ctl",
    4: "tess-eval",
    5: "compute",
    6: "task",
    7: "mesh",
}

BNTX_FORMAT_TYPES = {
    0x01: "R8", 0x02: "R4G4", 0x03: "R5G6B5", 0x07: "R8G8", 0x09: "R16",
    0x0B: "R8G8B8A8", 0x0C: "R10G10B10A2", 0x0F: "R16G16", 0x10: "R11G11B10F",
    0x14: "R16G16B16A16", 0x15: "R32", 0x16: "R32G32", 0x17: "R32G32B32A32",
    0x1A: "BC1", 0x1B: "BC2", 0x1C: "BC3", 0x1D: "BC4", 0x1E: "BC5", 0x1F: "BC6H", 0x20: "BC7",
    0x2D: "ASTC_4x4", 0x2E: "ASTC_5x4", 0x2F: "ASTC_5x5", 0x30: "ASTC_6x5", 0x31: "ASTC_6x6",
    0x32: "ASTC_8x5", 0x33: "ASTC_8x6", 0x34: "ASTC_8x8", 0x35: "ASTC_10x5", 0x36: "ASTC_10x6",
    0x37: "ASTC_10x8", 0x38: "ASTC_10x10", 0x39: "ASTC_12x10", 0x3A: "ASTC_12x12",
}


def bntx_fmt_name(fmt: int) -> str:
    base = BNTX_FORMAT_TYPES.get((fmt >> 8) & 0xFF, f"fmt_0x{(fmt >> 8) & 0xFF:02x}")
    sub = fmt & 0xFF
    tag = {1: "UNORM", 2: "SNORM", 3: "UINT", 4: "SINT", 5: "FLOAT", 6: "SRGB", 0xA: "UFLOAT"}.get(sub, f"0x{sub:02x}")
    return f"{base}_{tag}"


def mangled_ns(name: str) -> str:
    """Extract first two Itanium nested scopes (e.g., nn::os, nn::friends)."""
    if not name.startswith("_ZN"):
        return "(C) " + name.split("_")[0][:24]
    parts, s = [], name[3:]
    while s and len(parts) < 2:
        m = re.match(r"(\d+)", s)
        if not m:
            break
        n = int(m.group(1))
        s = s[len(m.group(1)):]
        parts.append(s[:n])
        s = s[n:]
    return "::".join(parts) or name[:28]


def load_host_knowledge() -> dict:
    supported_relocs = {257, 1025, 1026, 1027}
    loader_path = ROOT / "runtime" / "loader.c"
    if loader_path.is_file():
        txt = loader_path.read_text(encoding="utf-8", errors="ignore")
        if "R_TLSDESC" in txt or "1031" in txt:
            supported_relocs.add(1031)
        if "DT_RELR" in txt:
            supported_relocs.add("DT_RELR")

    known_nvn = {"nvnBootstrapLoader"}
    for inc in ("nvn_procs.inc", "nvn_procs_nvn2.inc"):
        p = ROOT / "runtime" / inc
        if p.is_file():
            for m in re.finditer(r"NVN_PROC\(\s*(\w+)\s*\)", p.read_text(encoding="utf-8", errors="ignore")):
                known_nvn.add(m.group(1))

    host_overrides = set()
    for cfile in (ROOT / "runtime").glob("ov_*.c"):
        txt = cfile.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'HOST_OVERRIDE\(\s*"([^"]+)"', txt):
            host_overrides.add(m.group(1))

    lowered_ops = set()
    for p in ROOT.glob("runtime/third_party/*/shader_recompiler/frontend/ampere/lower_to_maxwell.h"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"\bcase\s+0x([0-9a-fA-F]+)\s*:", txt):
            lowered_ops.add(int(m.group(1), 16))
        for m in re.finditer(r"opcode[^=\n]{0,24}==\s*0x([0-9a-fA-F]+)", txt):
            lowered_ops.add(int(m.group(1), 16))

    return {
        "relocs": supported_relocs,
        "nvn": known_nvn,
        "overrides": host_overrides,
        "lowered_ops": lowered_ops,
    }


def decode_nso_sections(path: Path) -> tuple[bytes, int, int]:
    """Decompress NSO0 image returning (image_bytes, text_off, text_size)."""
    raw = path.read_bytes()
    if raw[:4] != b"NSO0":
        return raw, 0, 0
    if lz4_block is None:
        return b"", 0, 0
    flags = struct.unpack_from("<I", raw, 0xC)[0]
    parts, cur_off = [], 0
    text_off, text_sz = 0, 0
    for i in range(3):
        file_off, mem_off, dec_size = struct.unpack_from("<III", raw, 0x10 + i * 0x10)
        comp_size = struct.unpack_from("<I", raw, 0x60 + i * 4)[0]
        if i == 0:
            text_off, text_sz = mem_off, dec_size
        if mem_off > cur_off:
            parts.append(b"\0" * (mem_off - cur_off))
        chunk = raw[file_off:file_off + comp_size]
        seg = lz4_block.decompress(chunk, uncompressed_size=dec_size) if (flags & (1 << i)) else chunk
        parts.append(seg)
        cur_off = mem_off + len(seg)
    return b"".join(parts), text_off, text_sz


def parse_elf_relocs_and_syms(img: bytes) -> tuple[collections.Counter, set[str], set[str]]:
    """Return (reloc_counts, undefined_import_syms, defined_export_syms)."""
    relocs = collections.Counter()
    undef, defd = set(), set()
    if len(img) < 0x100:
        return relocs, undef, defd
    mod0_rel = struct.unpack_from("<I", img, 4)[0]
    if mod0_rel + 0x20 <= len(img) and img[mod0_rel:mod0_rel + 4] == b"MOD0":
        dyn_off = mod0_rel + struct.unpack_from("<i", img, mod0_rel + 4)[0]
        if 0 <= dyn_off < len(img) - 16:
            dyn = {}
            pos = dyn_off
            while pos + 16 <= len(img):
                tag, val = struct.unpack_from("<qQ", img, pos)
                pos += 16
                if tag == 0:
                    break
                dyn[tag] = val
            if 0x23 in dyn and dyn[0x23] > 0:
                relocs["DT_RELR"] += int(dyn[0x23]) // 8
            for tbl_tag, sz_tag in ((7, 8), (23, 2)):
                off = dyn.get(tbl_tag)
                sz = dyn.get(sz_tag, 0)
                if off is not None and 0 <= off < len(img) and sz:
                    end = min(len(img), off + sz)
                    for r in range(off, end - 23, 24):
                        _, info, _ = struct.unpack_from("<QQq", img, r)
                        relocs[info & 0xFFFFFFFF] += 1
            strtab, symtab = dyn.get(5), dyn.get(6)
            if strtab is not None and symtab is not None and 0 <= strtab < len(img) and 0 <= symtab < len(img):
                limit = min(len(img), symtab + 96 * 24 * 1024)
                p = symtab
                while p + 24 <= limit:
                    st_name, st_info, _, st_shndx, st_val, _ = struct.unpack_from("<IBBHQQ", img, p)
                    if symtab < strtab and p >= strtab:
                        break
                    name_at = strtab + st_name
                    if name_at >= len(img):
                        break
                    nul = img.find(b"\0", name_at, min(len(img), name_at + 512))
                    if nul < 0:
                        break
                    name = img[name_at:nul].decode("ascii", "ignore")
                    if name:
                        if st_shndx == 0:
                            undef.add(name)
                        elif st_val != 0:
                            defd.add(name)
                    p += 24
    return relocs, undef, defd


def arm64_decode_coverage(mods_text: list[tuple[str, bytes]]) -> dict:
    """Check ARM64 .text words against recomp/lifter.py cleanly without invoking external disassemblers."""
    sys.path.insert(0, str(ROOT / "recomp"))
    try:
        import lifter
    except Exception:
        return {"checked": False}

    # Check ARMv8.3 PAC / LDAPR / LSE atomic instruction footprints quickly over unique .text words
    total_words = 0
    unhandled_distinct = 0
    sample_unhandled = []
    # Keep sampling bounded for speed across large 60MB binaries unless full check requested
    seen = {}
    for _, txt in mods_text:
        n = (len(txt) // 4)
        total_words += n
        step = max(1, n // 250000)
        for i in range(0, n, step):
            w = struct.unpack_from("<I", txt, i * 4)[0]
            seen[w] = seen.get(w, 0) + 1
    lifter_cls = getattr(lifter, "Lifter", None)
    if lifter_cls is None:
        return {"checked": True, "total_words": total_words, "sampled_distinct": len(seen), "unhandled_sampled": -1}
    lf = lifter_cls(0x7000000000, simd="c")
    for w in seen:
        try:
            lf.lift(w, 0x7000000000)
        except Exception:
            unhandled_distinct += 1
            if len(sample_unhandled) < 8:
                sample_unhandled.append(f"0x{w:08x}")
    return {
        "checked": True,
        "total_words": total_words,
        "sampled_distinct": len(seen),
        "unhandled_sampled": unhandled_distinct,
        "sample_hex": sample_unhandled,
    }


def extract_title_id(exefs: Path) -> str | None:
    npdm = exefs / "main.npdm"
    if not npdm.is_file():
        return None
    raw = npdm.read_bytes()
    if raw[:4] == b"META" and len(raw) >= 0x78:
        off, _ = struct.unpack_from("<II", raw, 0x70)
        if off + 0x18 <= len(raw) and raw[off:off + 4] == b"ACI0":
            return f"{struct.unpack_from('<Q', raw, off + 0x10)[0]:016X}"
    return None


def analyze_exefs(exefs: Path, knowledge: dict) -> dict:
    files = sorted(p.name for p in exefs.iterdir() if p.is_file() and not p.name.startswith("."))
    title_id = extract_title_id(exefs)
    subsdks = [f for f in files if f.startswith("subsdk")]

    reloc_totals = collections.Counter()
    unsupported_relocs = collections.Counter()
    nvn_strings = set()
    undef_by_mod = {}
    sdk_defined = set()
    mods_text = []

    nvn_re = re.compile(rb"\bnvn[A-Z][A-Za-z0-9_]{3,90}\x00")

    for mod in files:
        if mod in ("main", "sdk", "rtld") or mod.startswith("subsdk"):
            img, toff, tsz = decode_nso_sections(exefs / mod)
            if not img:
                continue
            if tsz > 0 and toff + tsz <= len(img):
                mods_text.append((mod, img[toff:toff + tsz]))
            r_cnt, undef, defd = parse_elf_relocs_and_syms(img)
            for rt, cnt in r_cnt.items():
                reloc_totals[rt] += cnt
                if rt not in knowledge["relocs"]:
                    unsupported_relocs[rt] += cnt
            if mod == "sdk":
                sdk_defined.update(defd)
            elif mod != "rtld":
                undef_by_mod[mod] = undef
            if mod in ("main", "sdk") or mod.startswith("subsdk"):
                for m in nvn_re.finditer(img):
                    nvn_strings.add(m.group(0)[:-1].decode("ascii", "ignore"))

    # Hookshot nx2/imports.py strategy: only count symbols game modules genuinely import from sdk!
    imported_from_sdk = set()
    for _, u in undef_by_mod.items():
        imported_from_sdk.update(u & sdk_defined if sdk_defined else u)

    unmatched_sdk = sorted(s for s in imported_from_sdk if s.startswith("_ZN2nn") and s not in knowledge["overrides"])
    ns_counts = collections.Counter(mangled_ns(s) for s in unmatched_sdk)

    missing_nvn = sorted(n for n in nvn_strings if n not in knowledge["nvn"])
    arm_cov = arm64_decode_coverage(mods_text)

    return {
        "title_id": title_id,
        "modules": files,
        "subsdks": subsdks,
        "relocs": {RELOC_NAMES.get(k, str(k)): v for k, v in reloc_totals.items()},
        "unsupported_relocs": {RELOC_NAMES.get(k, str(k)): v for k, v in unsupported_relocs.items()},
        "nvn_procs_found": len(nvn_strings),
        "missing_nvn_procs": missing_nvn,
        "sdk_imported_total": len(imported_from_sdk),
        "sdk_covered_host": len(imported_from_sdk & knowledge["overrides"]),
        "unmatched_nn_namespaces": dict(ns_counts.most_common(15)),
        "arm64_coverage": arm_cov,
    }


def open_romfs_reader(romfs_dir: Path):
    packed_bin = romfs_dir / "romfs.bin"
    packed_idx = romfs_dir / "index.json"
    if packed_bin.is_file() and packed_idx.is_file():
        idx = json.loads(packed_idx.read_text(encoding="utf-8"))
        entries = {r["path"]: (r["offset"], r["size"]) for r in idx["files"]}
        f = packed_bin.open("rb")

        def read_entry(path, max_bytes=None):
            off, sz = entries[path]
            n = min(sz, max_bytes) if max_bytes else sz
            f.seek(off)
            return f.read(n)

        return sorted(entries), {k: v[1] for k, v in entries.items()}, read_entry, f

    paths, sizes = [], {}
    for dp, dn, fns in os.walk(romfs_dir):
        dn.sort()
        for fn in sorted(fns):
            if fn.startswith("."):
                continue
            p = Path(dp) / fn
            rel = p.relative_to(romfs_dir).as_posix()
            paths.append(rel)
            sizes[rel] = p.stat().st_size

    def read_entry(path, max_bytes=None):
        p = romfs_dir / path
        with p.open("rb") as h:
            return h.read(max_bytes) if max_bytes else h.read()

    return paths, sizes, read_entry, None


def iter_sarc_members(data: bytes, decode_zstd, depth=0):
    if depth > 4 or data[:4] != b"SARC":
        return
    endian = "<" if data[6:8] == b"\xff\xfe" else ">"
    hdr, sz, start = struct.unpack_from(endian + "HxxII", data, 4)
    if sz != len(data) or hdr < 20 or data[hdr:hdr + 4] != b"SFAT":
        return
    cnt = struct.unpack_from(endian + "H", data, hdr + 6)[0]
    names = hdr + 12 + cnt * 16
    if data[names:names + 4] != b"SFNT":
        return
    names += 8
    for i in range(cnt):
        _, attr, lo, hi = struct.unpack_from(endian + "4I", data, hdr + 12 + i * 16)
        if attr >> 24 != 1 or hi < lo or start + hi > len(data):
            continue
        off = names + (attr & 0xFFFFFF) * 4
        nul = data.find(b"\0", off, start)
        if nul < 0:
            continue
        mname = data[off:nul].decode("utf-8", "replace")
        raw = data[start + lo:start + hi]
        if raw[:4] == ZSTD_MAGIC:
            raw = decode_zstd(raw)
            if raw is None:
                continue
        if raw[:4] == b"SARC":
            yield from iter_sarc_members(raw, decode_zstd, depth + 1)
        else:
            yield mname, raw


def analyze_romfs(romfs_dir: Path, knowledge: dict, max_textures: int = 600, dump_shaders: Path | None = None) -> dict:
    paths, sizes, read_entry, handle = open_romfs_reader(romfs_dir)
    ext_counts = collections.Counter()
    media_files, font_files, custom_packs = [], [], []
    dictionaries = {}

    if zstd is not None and "Pack/ZsDic.pack.zs" in sizes:
        try:
            dic_raw = zstd.decompress(read_entry("Pack/ZsDic.pack.zs"))
            for _, dbytes in iter_sarc_members(dic_raw, lambda x: x):
                d = zstd.ZstdDict(dbytes)
                dictionaries[d.dict_id] = d
        except Exception:
            pass

    def decode_zstd(raw: bytes) -> bytes | None:
        if zstd is None or raw[:4] != ZSTD_MAGIC:
            return raw
        try:
            info = zstd.get_frame_info(raw)
            if info.decompressed_size is not None and info.decompressed_size > (512 << 20):
                return None
            zd = dictionaries.get(info.dictionary_id) if info.dictionary_id else None
            if info.dictionary_id and zd is None:
                return None
            return zstd.decompress(raw, zstd_dict=zd)
        except Exception:
            return None

    for rel in paths:
        ext = ".".join(rel.split("/")[-1].split(".")[1:]) if "." in rel.split("/")[-1] else "(none)"
        ext_counts[ext] += 1
        low = rel.lower()
        sz = sizes[rel]
        if low.endswith((".webm", ".mp4", ".ivf")):
            media_files.append((rel, sz))
        elif low.endswith((".bfttf", ".bfotf", ".ttf", ".otf")):
            font_files.append(rel)
        elif ext == "(none)" and sz > (32 << 20):
            magic = read_entry(rel, 16)[:8]
            custom_packs.append({"path": rel, "mib": round(sz / (1 << 20), 1), "magic": magic.decode("ascii", "replace")})

    stage_counts = collections.Counter()
    pair_counts = collections.Counter()
    shader_arch = collections.Counter()
    sm86_opcodes = collections.Counter()
    huge_shaders = 0
    total_sm86_insns = 0
    seen_shader_keys = set()
    dumped_nvn2 = 0

    def inspect_bnsh(blob: bytes):
        nonlocal total_sm86_insns, dumped_nvn2, huge_shaders
        pos = 0
        while (pos := blob.find(b"BNSH\0\0\0\0", pos)) >= 0:
            if pos + 136 > len(blob):
                break
            bsize = struct.unpack_from("<I", blob, pos + 28)[0]
            bnsh = blob[pos:pos + bsize]
            pos += max(bsize, 8)
            if len(bnsh) < 136 or bnsh[96:100] != b"grsc":
                continue
            count, variations = struct.unpack_from("<IQ", bnsh, 124)
            if variations + count * 64 > len(bnsh):
                continue
            for i in range(count):
                prog_off = struct.unpack_from("<Q", bnsh, variations + i * 64 + 16)[0]
                if not prog_off or prog_off + 80 > len(bnsh):
                    continue
                prog_stages = []
                for rel_off in BNSH_SLOTS:
                    obj_off = struct.unpack_from("<Q", bnsh, prog_off + rel_off)[0]
                    if not obj_off or obj_off + 32 > len(bnsh):
                        continue
                    ctl_off, code_off, code_sz, ctl_sz = struct.unpack_from("<QQII", bnsh, obj_off + 8)
                    if ctl_off + ctl_sz > len(bnsh) or code_off + code_sz > len(bnsh):
                        continue
                    ctl = bnsh[ctl_off:ctl_off + ctl_sz]
                    code = bnsh[code_off:code_off + code_sz]
                    if ctl[:4] != CONTROL_MAGIC:
                        continue
                    key = hashlib.sha256(ctl[:min(len(ctl), 0x880)] + code[:min(len(code), 0x200000)]).hexdigest()
                    if len(ctl) >= 0x880:
                        stype = struct.unpack_from("<I", ctl, 0x714)[0]
                        stage_label = NVN2_STAGE_NAMES.get(stype, f"nvn1_{stype}")
                        prog_stages.append(stage_label)
                        if key not in seen_shader_keys:
                            seen_shader_keys.add(key)
                            shader_arch["NVN1_Maxwell"] += 1
                            stage_counts[stage_label] += 1
                    elif len(ctl) >= 0xD8:
                        nvn_type = struct.unpack_from("<H", ctl, 0x56)[0]
                        stage_label = NVN2_STAGE_NAMES.get(nvn_type, f"nvn2_{nvn_type}")
                        prog_stages.append(stage_label)
                        if key not in seen_shader_keys:
                            seen_shader_keys.add(key)
                            shader_arch["NVN2_Ampere_SM86"] += 1
                            stage_counts[stage_label] += 1
                            csize = struct.unpack_from("<I", ctl, 0x38)[0]
                            scan_end = min(len(code), csize if csize > 0 else len(code))
                            w0 = struct.unpack_from("<I", code, 0)[0] if scan_end >= 4 else 0
                            start_off = 0x80 if (w0 & 31) in (1, 2) and ((w0 >> 5) & 31) == 4 else 0
                            n_insns = max(0, (scan_end - start_off) // 16)
                            if n_insns >= 5000:
                                huge_shaders += 1
                            if dump_shaders is not None and dumped_nvn2 < 20000:
                                dump_shaders.mkdir(parents=True, exist_ok=True)
                                (dump_shaders / f"{key[:16]}.ctl").write_bytes(ctl)
                                (dump_shaders / f"{key[:16]}.bin").write_bytes(code)
                                dumped_nvn2 += 1
                            for off in range(start_off, scan_end - 15, 16):
                                lo = struct.unpack_from("<Q", code, off)[0]
                                sm86_opcodes[lo & 0xFFF] += 1
                                total_sm86_insns += 1
                if prog_stages:
                    pair_counts["+".join(prog_stages)] += 1

    tex_formats = collections.Counter()
    large_textures = []
    tex_scanned = 0
    bntx_targets = collections.Counter()
    sparse_virtual_count = 0

    def inspect_bntx(blob: bytes, src_path: str):
        nonlocal tex_scanned, sparse_virtual_count
        pos = 0
        while (pos := blob.find(b"BNTX\0\0\0\0", pos)) >= 0:
            if pos + 0x30 > len(blob):
                break
            b = blob[pos:]
            pos += 8
            target = b[0x20:0x24]
            is_ounce = target == b"Ounc"
            bntx_targets[target.decode("ascii", "replace")] += 1
            cnt, ptrs_off = struct.unpack_from("<IQ", b, 0x24)
            if cnt > 4096 or ptrs_off + cnt * 8 > len(b):
                continue
            for i in range(cnt):
                brti_off = struct.unpack_from("<Q", b, ptrs_off + i * 8)[0]
                if brti_off + 0x40 > len(b):
                    continue
                brti = b[brti_off:]
                if brti[:4] != b"BRTI":
                    continue
                fmt = struct.unpack_from("<I", brti, 0x1C if is_ounce else 0x18)[0]
                w, h, depth, arr = struct.unpack_from("<4I", brti, 0x24 if is_ounce else 0x20)
                fname = bntx_fmt_name(fmt)
                tex_formats[fname] += 1
                tex_scanned += 1
                texels = w * h * max(1, depth) * max(1, arr)
                if texels > (1 << 28):
                    sparse_virtual_count += 1
                if w >= 2048 or h >= 2048 or arr >= 8 or texels > (1 << 25):
                    large_textures.append((w, h, depth, arr, fname, src_path.split("/")[-1], texels * 4 / (1 << 30)))

    shader_files = [
        r for r in paths
        if r.startswith(("Shader/", "Effect/", "Foliage/", "Layout2Shader/", "Lib/agl/", "Lib/Terrain/", "Lib/gsys/", "UI/LayoutArchive/"))
        or "bfsha" in r.lower() or "sharcb" in r.lower() or r.lower().endswith(".bnsh")
    ]
    for rel in shader_files:
        raw = read_entry(rel)
        dec = decode_zstd(raw) if raw[:4] == ZSTD_MAGIC else raw
        if dec is None:
            continue
        if dec[:4] == b"SARC":
            for _, mbytes in iter_sarc_members(dec, decode_zstd):
                inspect_bnsh(mbytes)
        else:
            inspect_bnsh(dec)

    bntx_candidates = sorted((r for r in paths if "bntx" in r.lower()), key=lambda r: -sizes[r])
    for rel in bntx_candidates[:max_textures]:
        raw = read_entry(rel)
        dec = decode_zstd(raw) if raw[:4] == ZSTD_MAGIC else raw
        if dec is None:
            continue
        if dec[:4] == b"SARC":
            for mname, mbytes in iter_sarc_members(dec, decode_zstd):
                inspect_bntx(mbytes, f"{rel}/{mname}")
        else:
            inspect_bntx(dec, rel)

    if handle:
        handle.close()

    lowered_set = knowledge["lowered_ops"]
    known_op_insns = 0
    unknown_ops = collections.Counter()
    for op12, cnt in sm86_opcodes.items():
        if op12 in lowered_set or (op12 & 0x1FF) in lowered_set or (op12 & 0x3FF) in lowered_set:
            known_op_insns += cnt
        else:
            unknown_ops[op12] += cnt

    return {
        "total_romfs_files": len(paths),
        "custom_packs": custom_packs,
        "top_extensions": dict(ext_counts.most_common(12)),
        "shader_arch": dict(shader_arch),
        "shader_stages": dict(stage_counts),
        "shader_pipeline_pairs": dict(pair_counts.most_common(12)),
        "unique_shaders": len(seen_shader_keys),
        "huge_shaders_5k_plus": huge_shaders,
        "sm86_total_insns": total_sm86_insns,
        "sm86_distinct_op12": len(sm86_opcodes),
        "sm86_covered_pct": round(100.0 * known_op_insns / total_sm86_insns, 2) if total_sm86_insns else 0.0,
        "sm86_unmatched_top15": {f"0x{k:03x}": v for k, v in unknown_ops.most_common(15)},
        "bntx_targets": dict(bntx_targets),
        "textures_sampled": tex_scanned,
        "sparse_over_256m_texels": sparse_virtual_count,
        "texture_formats": dict(tex_formats.most_common(15)),
        "large_or_array_textures_sample": [
            {"dim": f"{w}x{h}x{d}", "layers": arr, "rgba8_gib": round(gib, 2), "format": fmt, "file": fn}
            for w, h, d, arr, fmt, fn, gib in sorted(large_textures, key=lambda t: -t[6])[:12]
        ],
        "media_count": len(media_files),
        "largest_media_mib": round(max((sz for _, sz in media_files), default=0) / (1 << 20), 1),
        "font_count": len(font_files),
    }


def build_recommendations(exefs_rep: dict | None, romfs_rep: dict | None) -> list[str]:
    recs = []
    if exefs_rep:
        if exefs_rep["subsdks"]:
            recs.append(f"[F0 Layout] Found extra modules {exefs_rep['subsdks']}; run `init` so expected-*.json includes them.")
        if exefs_rep["unsupported_relocs"]:
            recs.append(f"[F0 Loader] Unsupported ELF relocations detected: {exefs_rep['unsupported_relocs']} -> implement in runtime/loader.c.")
        cov = exefs_rep.get("arm64_coverage", {})
        if cov.get("unhandled_sampled", 0) > 0:
            recs.append(f"[F0 Lifter] Sampled {cov['unhandled_sampled']} unhandled ARM64 words (e.g. {cov['sample_hex']}) -> run tests/diff/lift.py --coverage.")
        if exefs_rep["unmatched_nn_namespaces"]:
            top_ns = ", ".join(list(exefs_rep["unmatched_nn_namespaces"].keys())[:6])
            recs.append(f"[F1 Horizon OS] Imported sdk namespaces not yet overridden ({top_ns}) -> monitor logs on TOTK_GPU=null --boot.")
        if exefs_rep["missing_nvn_procs"]:
            sample = ", ".join(exefs_rep["missing_nvn_procs"][:5])
            recs.append(f"[F2 NVN2 Procs] {len(exefs_rep['missing_nvn_procs'])} NVN proc strings missing from nvn_procs*.inc (e.g. {sample}).")
    if romfs_rep:
        if romfs_rep["custom_packs"]:
            cp = romfs_rep["custom_packs"][0]
            recs.append(f"[Setup Archive] Detected huge monolithic container '{cp['path']}' ({cp['mib']} MiB, magic '{cp['magic']}'); extract/inspect before static shader census.")
        stages = romfs_rep["shader_stages"]
        if stages.get("task", 0) or stages.get("mesh", 0):
            recs.append(f"[F3 Task/Mesh] Uses Task ({stages.get('task', 0)}) & Mesh ({stages.get('mesh', 0)}) stages -> enable/complete Mesh/ISBERD/ISBEWR/DrawMeshTasks path.")
        if stages.get("tess-ctl", 0) or stages.get("tess-eval", 0) or stages.get("geometry", 0):
            recs.append(f"[F3 Tess/Geom] Uses {stages.get('tess-ctl', 0)} TCS / {stages.get('tess-eval', 0)} TES / {stages.get('geometry', 0)} GS stages -> verify UPOPC & signed GS EXIT.")
        if romfs_rep["huge_shaders_5k_plus"]:
            recs.append(f"[F3 Compile Stall] {romfs_rep['huge_shaders_5k_plus']} massive shaders (>5K insns) -> pre-warm via --warm-shaders or use NS2_VK_NOOPT=1 if driver hangs.")
        if romfs_rep["sm86_unmatched_top15"]:
            top_ops = ", ".join(list(romfs_rep["sm86_unmatched_top15"].keys())[:6])
            recs.append(f"[F3 SM86 Opcodes] Unrecognized SM86 12-bit opcodes ({top_ops}) -> inspect with nvdisasm -b SM86 -raw and lower in lower_to_maxwell.h.")
        if romfs_rep["sparse_over_256m_texels"] or romfs_rep["large_or_array_textures_sample"]:
            recs.append(f"[F4 VRAM Guard] {romfs_rep['sparse_over_256m_texels']} textures >256M texels; keep CompactLayers ASTC->BC3 + sparse MapVirtual enabled.")
        if romfs_rep["media_count"]:
            recs.append(f"[F1 Media] {romfs_rep['media_count']} videos (up to {romfs_rep['largest_media_mib']} MiB) -> verify ov_codec.c thread count & submission events.")
        if romfs_rep["font_count"]:
            recs.append(f"[F1 Fonts] {romfs_rep['font_count']} font files -> verify nn::pl / BFTTF handling.")
    return recs


def cmd_scan(args):
    t0 = time.monotonic()
    knowledge = load_host_knowledge()
    exefs_rep = analyze_exefs(args.exefs, knowledge) if args.exefs else None
    romfs_rep = analyze_romfs(args.romfs, knowledge, args.max_textures, args.dump_shaders) if args.romfs else None
    recs = build_recommendations(exefs_rep, romfs_rep)
    elapsed = time.monotonic() - t0

    print(f"=== Universal NS2 to PC: Pre-Flight Profiler ({elapsed:.2f}s) ===")
    if exefs_rep:
        print(f"\n[ExeFS] Title ID: {exefs_rep['title_id']} | Modules: {', '.join(exefs_rep['modules'])}")
        print(f"  Relocs: {exefs_rep['relocs']}")
        if exefs_rep["unsupported_relocs"]:
            print(f"  WARNING unsupported relocs: {exefs_rep['unsupported_relocs']}")
        print(f"  SDK Imports (exact sdk->app): {exefs_rep['sdk_imported_total']} ({exefs_rep['sdk_covered_host']} already hooked)")
        print(f"  Top unhooked nn:: namespaces: {exefs_rep['unmatched_nn_namespaces']}")
        print(f"  NVN procs: {exefs_rep['nvn_procs_found']} found | {len(exefs_rep['missing_nvn_procs'])} missing")
        cov = exefs_rep["arm64_coverage"]
        if cov.get("checked"):
            print(f"  ARM64 Lifter Audit: {cov['total_words']} total .text words | sampled {cov.get('sampled_distinct', 0)} distinct | unhandled={cov.get('unhandled_sampled')}")

    if romfs_rep:
        print(f"\n[RomFS] Files: {romfs_rep['total_romfs_files']} | Unique Shaders: {romfs_rep['unique_shaders']} (5K+ insns: {romfs_rep['huge_shaders_5k_plus']})")
        print(f"  Shader arch:   {romfs_rep['shader_arch']}")
        print(f"  Shader stages: {romfs_rep['shader_stages']}")
        print(f"  Top pipeline pairs: {romfs_rep['shader_pipeline_pairs']}")
        if romfs_rep["sm86_total_insns"]:
            print(f"  SM86 insns scanned: {romfs_rep['sm86_total_insns']} ({romfs_rep['sm86_distinct_op12']} distinct op12, {romfs_rep['sm86_covered_pct']}% covered)")
            if romfs_rep["sm86_unmatched_top15"]:
                print(f"  Unknown SM86 op12s: {romfs_rep['sm86_unmatched_top15']}")
        print(f"  BNTX targets: {romfs_rep['bntx_targets']} | Textures sampled: {romfs_rep['textures_sampled']} | >256M texel sparse: {romfs_rep['sparse_over_256m_texels']}")
        print(f"  Texture formats: {romfs_rep['texture_formats']}")
        if romfs_rep["large_or_array_textures_sample"]:
            print("  Largest/Array Textures (RGBA8 uncompressed risk):")
            for item in romfs_rep["large_or_array_textures_sample"][:5]:
                print(f"    - {item['dim']} layers={item['layers']} (~{item['rgba8_gib']} GiB RGBA8) {item['format']} ({item['file']})")
        if romfs_rep["custom_packs"]:
            print(f"  Custom/Monolithic archives: {romfs_rep['custom_packs']}")
        print(f"  Media: {romfs_rep['media_count']} (max {romfs_rep['largest_media_mib']} MiB) | Fonts: {romfs_rep['font_count']}")

    print("\n=== Actionable Pre-Flight Checklist ===")
    for i, r in enumerate(recs, 1):
        print(f"  {i}. {r}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"exefs": exefs_rep, "romfs": romfs_rep, "recommendations": recs}, indent=2) + "\n", encoding="utf-8")
        print(f"\nSaved JSON report -> {args.json}")


def cmd_init(args):
    exefs = args.exefs.resolve()
    title_id = extract_title_id(exefs) or "0400000000000000"
    files = sorted(p for p in exefs.iterdir() if p.is_file() and not p.name.startswith("."))
    exp = {
        "_comment": f"{args.name} ({args.display}) ExeFS. Hashes only; no game data.",
        "short_name": args.short,
        "display_name": args.name,
        "title_id": title_id,
        "display_version": args.display,
        "exefs_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    }
    exp_path = ROOT / "tools" / "data" / f"expected-{args.ver}.json"
    exp_path.write_text(json.dumps(exp, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {exp_path} (title_id={title_id}, modules={list(exp['exefs_sha256'])})")

    patches_path = ROOT / "recomp" / f"patches-{args.ver}.txt"
    if not patches_path.exists():
        patches_path.write_text(f"# Code patches for {args.name} {args.display}.\n", encoding="utf-8")
        print(f"Created empty patch table {patches_path}")

    if args.romfs and not (args.romfs / "index.json").is_file() and args.pack_out:
        packer = ROOT / "tools" / "mtf_pack_romfs.py"
        if packer.is_file():
            subprocess.run([sys.executable, str(packer), "--dir", str(args.romfs), "--out", str(args.pack_out)], check=True)


def cmd_build(args):
    xlate = ROOT / "build" / "xlate" / ("totk_xlate.exe" if os.name == "nt" else "totk_xlate")
    if not xlate.is_file():
        print("Building shader translator (NativeAOT)...")
        subprocess.run([sys.executable, str(ROOT / "tools" / "build_xlate.py")], check=True)

    gen_dir = (args.gen or (ROOT / "generated" / args.ver)).resolve()
    out_dir = (args.out or (ROOT / "build" / args.ver)).resolve()
    patches = ROOT / "recomp" / f"patches-{args.ver}.txt"
    if not patches.exists():
        patches.write_text(f"# Auto-created patch table for {args.ver}\n", encoding="utf-8")

    mods = [p.name for p in sorted(args.exefs.iterdir()) if p.is_file() and p.name not in ("main.npdm", "rtld") and not p.name.startswith(".")]
    order = {"main": 0, "sdk": 99}
    mods.sort(key=lambda m: (order.get(m, 10), m))
    print(f"Lifting modules {mods} from {args.exefs} -> {gen_dir}...")
    subprocess.run([sys.executable, str(ROOT / "recomp" / "gen.py"),
                    "--exefs", str(args.exefs), "--out", str(gen_dir),
                    "--modules", ",".join(mods), "--patches", str(patches)], check=True)

    romfs = args.romfs
    if romfs and not (romfs / "index.json").is_file():
        packed_candidate = romfs.parent / "romfs_packed"
        if (packed_candidate / "index.json").is_file():
            romfs = packed_candidate

    cmd = [sys.executable, str(ROOT / "tools" / "build_game.py"),
           "--version", args.ver, "--gen", str(gen_dir), "--out", str(out_dir), "--exefs", str(args.exefs)]
    if romfs:
        cmd += ["--romfs", str(romfs)]
    subprocess.run(cmd, check=True)

    if xlate.is_file():
        dst_xlate = out_dir / ("ns2_xlate.exe" if os.name == "nt" else "ns2_xlate")
        shutil.copy2(xlate, dst_xlate)
        xlate_id = xlate.with_suffix(".id")
        if xlate_id.is_file():
            shutil.copy2(xlate_id, dst_xlate.with_suffix(".id"))
    subprocess.run([sys.executable, str(ROOT / "tools" / "check_content.py")], check=True)
    print(f"\nBUILD COMPLETE -> {out_dir}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Profile ExeFS & RomFS before recompilation")
    p_scan.add_argument("--exefs", type=Path)
    p_scan.add_argument("--romfs", type=Path)
    p_scan.add_argument("--max-textures", type=int, default=600)
    p_scan.add_argument("--dump-shaders", type=Path)
    p_scan.add_argument("--json", type=Path)

    p_init = sub.add_parser("init", help="Scaffold expected-*.json, patches table, and packed RomFS for a new NS2 game")
    p_init.add_argument("--ver", required=True, help="Version key, e.g. mkw180, mtf111, ns2test")
    p_init.add_argument("--short", required=True, help="Short binary name, e.g. mkw, mtf, dkb")
    p_init.add_argument("--name", required=True, help="Human-readable game name")
    p_init.add_argument("--display", default="1.0.0")
    p_init.add_argument("--exefs", type=Path, required=True)
    p_init.add_argument("--romfs", type=Path)
    p_init.add_argument("--pack-out", type=Path, help="Optional folder to pack loose RomFS into romfs.bin")

    p_bld = sub.add_parser("build", help="One-step xlate + lift + compile + link for any NS2 target")
    p_bld.add_argument("--ver", required=True)
    p_bld.add_argument("--exefs", type=Path, required=True)
    p_bld.add_argument("--romfs", type=Path)
    p_bld.add_argument("--gen", type=Path)
    p_bld.add_argument("--out", type=Path)

    args = ap.parse_args()
    if args.cmd == "scan":
        cmd_scan(args)
    elif args.cmd == "init":
        cmd_init(args)
    elif args.cmd == "build":
        cmd_build(args)


if __name__ == "__main__":
    main()
