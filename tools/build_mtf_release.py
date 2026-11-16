"""Build the clean MTF-ShadowRacket Windows release package (MKW-THWOMP style).

Emits into build/release-mtf/:
  1. SteelTemple-MTF-ShadowRacket-<ver>-Full-Setup-Wizard.exe
  2. SteelTemple-MTF-ShadowRacket-<ver>-Portable-StandAlone.zip
  3. SteelTemple-MTF-ShadowRacket-<ver>-Update.zip

Follows strict allowlist staging:
  - Zero copyrighted game files (exefs/, romfs/, generated/, spirv/)
  - Zero developer INI/profile/logs/shader-cache state
  - Zero DKB or TotK icons, binaries, or release assets
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_content  # noqa: E402

MKW_CACHE = Path(r"C:\Games\MKW PC\upstream-mkw-recomp\build")
MSYS_UCRT = Path(r"C:\msys64\ucrt64")

LLVM_BIN = {
    "clang.exe", "clang++.exe", "clang-23.exe", "ld.lld.exe", "llvm-ar.exe", "llvm-ranlib.exe",
    "llvm-nm.exe", "llvm-objdump.exe", "llvm-objcopy.exe", "llvm-strip.exe", "llvm-readobj.exe",
    "llvm-dlltool.exe", "llvm-rc.exe", "llvm-cvtres.exe", "llvm-windres.exe", "llvm-wrapper.exe",
    "mingw32-common.cfg", "x86_64-w64-windows-gnu.cfg", "x86_64-pc-windows-gnu.cfg",
    "x86_64-w64-mingw32-clang.exe", "x86_64-w64-mingw32-clang++.exe",
    "libLLVM-23.dll", "libclang-cpp.dll", "libc++.dll", "libunwind.dll",
    "libwinpthread-1.dll", "libffi-8.dll",
}
LLVM_SKIP_DIRS = {"aarch64-w64-mingw32", "armv7-w64-mingw32", "i686-w64-mingw32", "busybox", "python", "share"}
LLVM_SKIP_SUFFIXES = {".idl", ".tlb"}

TOOLS_FILES = [
    "build_game.py",
    "build_shaders.py",
    "check_content.py",
    "extract_nup.py",
    "hostmem.py",
    "make_romfs_patches.py",
    "mtf_pack_romfs.py",
    "pack_shader_cache.py",
    "prepare_shaders.py",
    "romfs_index.py",
    "shader_census.py",
    "shader_list.py",
]

MAGIC = b"MTFSRCV1"


def read_version() -> str:
    p = ROOT / "VERSION"
    if p.is_file():
        return p.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return "Alpha 0.1.1"


def version_slug(ver: str) -> str:
    return "-".join(ver.split())


def run(cmd: list[str | Path], **kw) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def clean_env(*path_dirs: Path) -> dict[str, str]:
    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    keep = {
        "SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "USERPROFILE",
        "LOCALAPPDATA", "APPDATA", "COMSPEC", "PATHEXT", "NUMBER_OF_PROCESSORS",
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in keep}
    env["PATH"] = os.pathsep.join([*(str(p) for p in path_dirs), rf"{sys_root}\System32", sys_root])
    return env


def copy_tree(src: Path, dst: Path, skip=lambda _rel: False) -> None:
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if p.is_dir() or skip(rel.as_posix()):
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)


def build_launcher() -> Path:
    pyinstaller = ROOT / ".venv" / "Scripts" / "pyinstaller.exe"
    if not pyinstaller.is_file():
        sys.exit(f"Missing PyInstaller at {pyinstaller}")
    run([pyinstaller, ROOT / "MTFLauncher.spec", "--noconfirm"], cwd=ROOT)
    exe = ROOT / "dist" / "MTFLauncher.exe"
    if not exe.is_file():
        sys.exit("PyInstaller did not produce dist/MTFLauncher.exe")
    return exe


def stage_python(stage: Path) -> Path:
    dl = MKW_CACHE / "dist" / "dl"
    py_tar = next(iter(sorted(dl.glob("cpython-3.14*-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"))), None)
    if not py_tar:
        sys.exit(f"Missing cached standalone Python 3.14 tarball in {dl}")
    py_dst = stage / "python"
    with tarfile.open(py_tar) as tf:
        tf.extractall(stage, filter="tar")
    if not (py_dst / "python.exe").is_file():
        sys.exit(f"Expected python.exe in {py_dst}")

    # Install numpy & lz4 wheels directly into site-packages (pure wheel extraction, offline safe)
    site_pkg = py_dst / "Lib" / "site-packages"
    site_pkg.mkdir(parents=True, exist_ok=True)
    for pattern in ("numpy-*.whl", "lz4-*.whl"):
        whls = sorted(dl.glob(pattern))
        if not whls:
            sys.exit(f"Missing cached wheel matching {pattern} in {dl}")
        with zipfile.ZipFile(whls[-1]) as zf:
            for member in zf.infolist():
                if member.filename.endswith("/") or member.filename.startswith("bin/"):
                    continue
                zf.extract(member, site_pkg)

    # Remove unneeded pip/ensurepip/test caches if present
    for junk in ("include", "libs", "Scripts", "tcl"):
        jdir = py_dst / junk
        if jdir.is_dir():
            shutil.rmtree(jdir, ignore_errors=True)
    for pycache in py_dst.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)

    r = subprocess.run(
        [
            str(py_dst / "python.exe"),
            "-I",
            "-c",
            "from compression import zstd; import numpy, lz4.block; "
            "print('python OK:', numpy.__version__)",
        ],
        env=clean_env(py_dst),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        sys.exit(f"Staged Python verification failed:\n{r.stderr}")
    print(" ", r.stdout.strip())
    return py_dst


def stage_llvm(stage: Path) -> Path:
    src = MKW_CACHE / "win" / "llvm-mingw"
    if not (src / "bin" / "clang.exe").is_file():
        sys.exit(f"Missing cached llvm-mingw in {src}")
    dst = stage / "llvm"

    def skip(rel: str) -> bool:
        top = rel.split("/")[0]
        if top in LLVM_SKIP_DIRS:
            return True
        if top == "bin":
            return rel not in {f"bin/{n}" for n in LLVM_BIN}
        if top == "lib":
            if rel.startswith("lib/clang/") and "/include/" in rel:
                return False
            return not rel.endswith("/lib/windows/libclang_rt.builtins-x86_64.a")
        return Path(rel).suffix.lower() in LLVM_SKIP_SUFFIXES or rel.startswith("include/ddk/")

    copy_tree(src, dst, skip)
    return dst


def ensure_standalone_ninja(dest_exe: Path) -> None:
    """Fetch pinned standalone ninja-win.zip (zero MSYS2 DLL dependencies) into toolchain/release-dl."""
    url = "https://github.com/ninja-build/ninja/releases/download/v1.13.2/ninja-win.zip"
    want_sha = "07fc8261b42b20e71d1720b39068c2e14ffcee6396b76fb7a795fb460b78dc65"
    dl = ROOT / "toolchain" / "release-dl"
    dl.mkdir(parents=True, exist_ok=True)
    zip_path = dl / "ninja-win.zip"
    if zip_path.is_file():
        got = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if got != want_sha:
            zip_path.unlink()
    if not zip_path.is_file():
        print(f"Downloading standalone ninja v1.13.2 -> {zip_path}", flush=True)
        data = urllib.request.urlopen(url, timeout=60).read()
        got = hashlib.sha256(data).hexdigest()
        if got != want_sha:
            sys.exit(f"ninja-win.zip sha256 mismatch: got {got}, expected {want_sha}")
        zip_path.write_bytes(data)
    with zipfile.ZipFile(zip_path) as zf:
        dest_exe.write_bytes(zf.read("ninja.exe"))
    r = subprocess.run([str(dest_exe), "--version"], env=clean_env(dest_exe.parent), capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Standalone ninja.exe failed check:\n{r.stderr}")
    print("  ninja OK:", r.stdout.strip())


def stage_deps_and_bin(stage: Path) -> None:
    deps_src = MKW_CACHE / "win" / "deps"
    deps_dst = stage / "runtime" / "deps"
    if not (deps_src / "lib" / "libSDL3.dll.a").is_file():
        sys.exit(f"Missing cached Windows deps in {deps_src}")

    copy_tree(deps_src / "include", deps_dst / "include")
    (deps_dst / "lib").mkdir(parents=True, exist_ok=True)
    for lib_name in ("libSDL3.dll.a", "libopus.dll.a", "libvpx.a", "libvulkan-1.dll.a", "libzstd.a"):
        shutil.copy2(deps_src / "lib" / lib_name, deps_dst / "lib" / lib_name)

    # dav1d (AV1 video decoding used by Universal-NS2-to-PC runtime)
    dav_lib = MSYS_UCRT / "lib" / "libdav1d.a"
    dav_inc = MSYS_UCRT / "include" / "dav1d"
    if not dav_lib.is_file() or not dav_inc.is_dir():
        sys.exit(f"Missing MSYS2 dav1d static library/headers at {MSYS_UCRT}")
    shutil.copy2(dav_lib, deps_dst / "lib" / "libdav1d.a")
    copy_tree(dav_inc, deps_dst / "include" / "dav1d")

    (deps_dst / "bin").mkdir(parents=True, exist_ok=True)
    for dll in ("SDL3.dll", "libopus-0.dll"):
        shutil.copy2(deps_src / "bin" / dll, deps_dst / "bin" / dll)

    b = stage / "bin"
    b.mkdir(parents=True, exist_ok=True)
    ensure_standalone_ninja(b / "ninja.exe")
    for dll in ("SDL3.dll", "libopus-0.dll"):
        shutil.copy2(deps_src / "bin" / dll, b / dll)
    for font_name in ("Roboto-Medium.ttf", "LICENSE-Roboto.txt"):
        shutil.copy2(ROOT / "runtime" / "ui" / "fonts" / font_name, b / font_name)

    xlate_cand = [
        (ROOT / "build" / "xlate" / "ns2_xlate.exe", ROOT / "build" / "xlate" / "ns2_xlate.id"),
        (Path(r"C:\Games\MTF PC\build\mtf111\ns2_xlate.exe"), Path(r"C:\Games\MTF PC\build\mtf111\ns2_xlate.id")),
        (ROOT / "build" / "xlate" / "totk_xlate.exe", ROOT / "build" / "xlate" / "totk_xlate.id"),
    ]
    x_exe, x_id = next(((e, i) for e, i in xlate_cand if e.is_file()), (None, None))
    if not x_exe:
        sys.exit("Missing ns2_xlate.exe / totk_xlate.exe")
    shutil.copy2(x_exe, b / "ns2_xlate.exe")
    if x_id and x_id.is_file():
        shutil.copy2(x_id, b / "ns2_xlate.id")


def stage_sources_and_runtime_lib(stage: Path, llvm: Path, gen_dir: Path, lib_work: Path) -> None:
    rt_src = ROOT / "runtime"
    rt_dst = stage / "runtime"

    # Build libmtfrt.a cleanly using staged llvm & staged deps so ABI matches 100%
    if lib_work.exists():
        shutil.rmtree(lib_work)
    lib_work.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            ROOT / "tools" / "build_game.py",
            "--make-runtime-lib",
            "--version",
            "mtf111",
            "--gen",
            gen_dir,
            "--out",
            lib_work,
            "--toolchain",
            llvm,
            "--deps",
            rt_dst / "deps",
            "--ninja",
            stage / "bin" / "ninja.exe",
        ]
    )
    # build_game.py --make-runtime-lib currently emits libtotkrt.a; ship as libmtfrt.a for MTFLauncher.
    built_lib = next(
        (p for p in (lib_work / "libmtfrt.a", lib_work / "libtotkrt.a") if p.is_file()),
        None,
    )
    if built_lib is None:
        sys.exit(f"Expected libmtfrt.a or libtotkrt.a in {lib_work} from --make-runtime-lib")
    shutil.copy2(built_lib, rt_dst / "libmtfrt.a")

    # Stage runtime headers, INSTALL_SIDE C sources, MTF resources, and shaders (NO totk/dkb icons or .rc!)
    keep_names = {"romfs.c", "patches.c", "ov_zstd.c", "mtf.rc", "mtf.manifest", "mtf.ico", "mtf.png", "mtf_ball.png"}
    for p in sorted(rt_src.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(rt_src)
        rel_posix = rel.as_posix()
        if rel_posix.startswith(("deps/", "__pycache__/")):
            continue
        if rel_posix.startswith("shaders/"):
            pass
        elif rel_posix.startswith("third_party/"):
            if p.suffix.lower() not in {".h", ".hpp", ".inc", ".txt", ".md"} and "LICENSE" not in p.name:
                continue
        elif p.suffix.lower() not in {".h", ".inc"} and p.name not in keep_names:
            continue
        out = rt_dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)

    # recomp/ (MTF patches only)
    recomp_dst = stage / "recomp"
    for p in sorted((ROOT / "recomp").rglob("*")):
        if p.is_dir() or "__pycache__" in p.parts:
            continue
        if p.name.startswith("patches-") and p.name != "patches-mtf111.txt":
            continue
        if p.suffix.lower() not in {".py", ".txt", ".md"}:
            continue
        rel = p.relative_to(ROOT / "recomp")
        out = recomp_dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)

    # tools/ (MTF scripts & expected-mtf111.json only)
    tools_dst = stage / "tools"
    tools_dst.mkdir(parents=True, exist_ok=True)
    for name in TOOLS_FILES:
        src = ROOT / "tools" / name
        if src.is_file():
            shutil.copy2(src, tools_dst / name)
    (tools_dst / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tools" / "data" / "expected-mtf111.json", tools_dst / "data" / "expected-mtf111.json")
    vendor_mng = ROOT / "tools" / "vendor" / "macnativegames"
    if vendor_mng.is_dir():
        copy_tree(vendor_mng, tools_dst / "vendor" / "macnativegames", lambda r: "__pycache__" in r)

    # Root docs/icons/config template (NEVER mtf.ini!)
    shutil.copy2(ROOT / "mtf.ini.example", stage / "mtf.ini.example")
    shutil.copy2(ROOT / "runtime" / "mtf.ico", stage / "mtf.ico")
    (stage / "VERSION").write_text(read_version() + "\n", encoding="utf-8")
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", stage / "THIRD_PARTY_NOTICES.md")

    # Licenses
    lic_dst = stage / "licenses"
    lic_dst.mkdir(parents=True, exist_ok=True)
    llvm_lic = MKW_CACHE / "win" / "llvm-mingw" / "LICENSE.TXT"
    if llvm_lic.is_file():
        shutil.copy2(llvm_lic, lic_dst / "llvm-mingw-LICENSE.TXT")
    fsr_lic = ROOT / "runtime" / "shaders" / "ffx" / "LICENSE.txt"
    if fsr_lic.is_file():
        shutil.copy2(fsr_lic, lic_dst / "FidelityFX-FSR-LICENSE.txt")


def verify_clean_stage(stage: Path) -> None:
    forbidden_names = {
        "mtf.ini", "dkb.ini", "totk.ini", "mkw.ini",
        "dkb.exe", "totk.exe", "mkw.exe", "dkblauncher.exe",
        "dkb.ico", "totk.ico", "dkb.rc", "totk.rc", "totk_xlate.exe",
    }
    forbidden_parts = {"exefs", "romfs", "romfs_packed", "generated", "spirv", "profile", "save", "logs", "shader-cache"}
    bad: list[str] = []
    file_count = 0
    for p in sorted(stage.rglob("*")):
        if not p.is_file():
            continue
        file_count += 1
        rel = p.relative_to(stage)
        rel_posix = rel.as_posix()
        parts_low = {part.lower() for part in rel.parts[:-1]}
        hit_dirs = parts_low & forbidden_parts
        if hit_dirs == {"profile"} and rel_posix.startswith("llvm/lib/clang/"):
            hit_dirs = set()
        if hit_dirs:
            bad.append(f"{rel_posix}: forbidden runtime/game directory segment ({sorted(hit_dirs)})")
        name_low = p.name.lower()
        if name_low in forbidden_names or name_low.endswith((".save", ".nsp", ".xci", ".nca")):
            bad.append(f"{rel.as_posix()}: forbidden file name {p.name}")
        for prob in check_content.problems_for(p, allow_large=True):
            bad.append(f"{rel.as_posix()}: {prob}")
    if bad:
        sys.exit("Release stage validation FAILED:\n" + "\n".join(bad[:50]))
    print(f"verify_clean_stage: {file_count} files passed check_content + allowlist rules (zero dev INI/game files).")


def compile_setup_stub(work: Path) -> Path:
    sdl_static = MKW_CACHE / "win" / "sdl-static"
    deps = MKW_CACHE / "win" / "deps"
    llvm_bin = MKW_CACHE / "win" / "llvm-mingw" / "bin"
    cxx = llvm_bin / "x86_64-w64-mingw32-clang++.exe"
    windres = llvm_bin / "x86_64-w64-mingw32-windres.exe"
    if not (sdl_static / "lib" / "libSDL3.a").is_file():
        sys.exit(f"Missing static SDL3 at {sdl_static}")

    rc_dir = work / "rc"
    rc_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "runtime" / "mtf.ico", rc_dir / "mtf.ico")
    shutil.copy2(ROOT / "runtime" / "mtf.manifest", rc_dir / "mtf.manifest")
    rc = rc_dir / "setup.rc"
    rc.write_text('1 ICON "mtf.ico"\n1 24 "mtf.manifest"\n', encoding="utf-8")
    res = work / "setup.res.o"
    run([windres, "-O", "coff", "-I", rc_dir, rc, "-o", res])

    imgui = ROOT / "runtime" / "third_party" / "imgui"
    mkw_imgui = MKW_CACHE.parent / "runtime" / "third_party" / "imgui"
    backends = imgui if (imgui / "backends" / "imgui_impl_sdl3.cpp").is_file() else mkw_imgui
    srcs = [
        ROOT / "tools" / "installer_mtf" / "installer.cpp",
        imgui / "imgui.cpp",
        imgui / "imgui_draw.cpp",
        imgui / "imgui_tables.cpp",
        imgui / "imgui_widgets.cpp",
        backends / "backends" / "imgui_impl_sdl3.cpp",
        backends / "backends" / "imgui_impl_sdlrenderer3.cpp",
    ]
    stub = work / "setup-stub.exe"
    run(
        [
            cxx,
            "-std=c++20",
            "-O2",
            "-mwindows",
            "-static",
            "-DUNICODE",
            f"-I{sdl_static / 'include'}",
            f"-I{imgui}",
            f"-I{backends}",
            f"-I{deps / 'include'}",
            *srcs,
            res,
            "-o",
            stub,
            f"-L{sdl_static / 'lib'}",
            "-lSDL3",
            deps / "lib" / "libzstd.a",
            "-lsetupapi",
            "-lwinmm",
            "-limm32",
            "-lversion",
            "-lole32",
            "-loleaut32",
            "-luuid",
            "-lgdi32",
            "-luser32",
            "-lshell32",
            "-ladvapi32",
            "-lcfgmgr32",
        ]
    )
    return stub


def pack_setup_with_py314(py314: Path, stub: Path, stage: Path, out_exe: Path, ver: str, level: int) -> None:
    """Use staged Python 3.14's built-in compression.zstd module to pack MTFSRCV1 payload cleanly."""
    script = (
        "import struct, sys\n"
        "from pathlib import Path\n"
        "from compression import zstd\n"
        "stub, stage, out_exe, ver, lvl = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4].encode(), int(sys.argv[5])\n"
        "MAGIC = b'MTFSRCV1'\n"
        "files = sorted(p for p in stage.rglob('*') if p.is_file())\n"
        "total = sum(p.stat().st_size for p in files)\n"
        "out_exe.parent.mkdir(parents=True, exist_ok=True)\n"
        "with out_exe.open('wb') as f:\n"
        "    f.write(stub.read_bytes())\n"
        "    off = f.tell()\n"
        "    f.write(MAGIC + struct.pack('<IQI', len(files), total, len(ver)) + ver)\n"
        "    for i, p in enumerate(files):\n"
        "        rel = p.relative_to(stage).as_posix().encode()\n"
        "        comp = zstd.compress(p.read_bytes(), level=lvl)\n"
        "        f.write(struct.pack('<H', len(rel)) + rel + struct.pack('<QQ', p.stat().st_size, len(comp)) + comp)\n"
        "        if i % 300 == 0:\n"
        "            print(f'  pack {i}/{len(files)} {rel.decode()}', flush=True)\n"
        "    f.write(struct.pack('<Q', off) + MAGIC)\n"
        "print(f'{out_exe}: {len(files)} files ({total/2**20:.1f} MiB -> {out_exe.stat().st_size/2**20:.1f} MiB)')\n"
    )
    run([py314 / "python.exe", "-I", "-c", script, stub, stage, out_exe, ver, str(level)], env=clean_env(py314))


def write_release_zips(stage: Path, out_dir: Path, slug: str) -> None:
    files = sorted(p for p in stage.rglob("*") if p.is_file())
    for kind in ("Portable-StandAlone", "Update"):
        out_zip = out_dir / f"SteelTemple-MTF-ShadowRacket-{slug}-{kind}.zip"
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for p in files:
                info = zipfile.ZipInfo("MTF-ShadowRacket/" + p.relative_to(stage).as_posix(), (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, p.read_bytes(), compresslevel=6)
        print(f"{out_zip}: {out_zip.stat().st_size / 2**20:.1f} MiB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "release-mtf")
    ap.add_argument("--gen", type=Path, default=Path(r"C:\Games\MTF PC\generated\mtf111"),
                    help="Lifted MTF layout directory used solely to compile libmtfrt.a headers (not bundled)")
    ap.add_argument("--level", type=int, default=19, help="zstd compression level for Full-Setup-Wizard (default 19)")
    ap.add_argument("--skip-launcher-build", action="store_true", help="Reuse existing dist/MTFLauncher.exe")
    args = ap.parse_args()

    t0 = time.time()
    ver = read_version()
    slug = version_slug(ver)
    out_dir = args.out.resolve()
    stage = out_dir / "stage" / "MTF-ShadowRacket"
    work = out_dir / "work"
    shutil.rmtree(stage, ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
    stage.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    launcher_exe = (ROOT / "dist" / "MTFLauncher.exe") if args.skip_launcher_build else build_launcher()
    if not launcher_exe.is_file():
        launcher_exe = build_launcher()
    shutil.copy2(launcher_exe, stage / "MTFLauncher.exe")

    py314 = stage_python(stage)
    llvm = stage_llvm(stage)
    stage_deps_and_bin(stage)
    stage_sources_and_runtime_lib(stage, llvm, args.gen.resolve(), work / "libbuild")
    verify_clean_stage(stage)

    stub = compile_setup_stub(work / "stubbuild")
    setup_exe = out_dir / f"SteelTemple-MTF-ShadowRacket-{slug}-Full-Setup-Wizard.exe"
    pack_setup_with_py314(py314, stub, stage, setup_exe, ver, args.level)
    write_release_zips(stage, out_dir, slug)
    print(f"Done in {time.time() - t0:.1f} s -> {out_dir}")


if __name__ == "__main__":
    main()
