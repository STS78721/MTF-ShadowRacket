"""Mario Tennis Fever dump discovery for MTFLauncher.

Resolves plain ExeFS/RomFS folders, NUP-extracted trees (base + updates/<ver>),
and optional .nup containers into a complete 1.1.1 ExeFS + RomFS pair without
shipping or accepting the wrong game silently.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

EXEFS_REQUIRED = ("main", "main.npdm", "rtld", "sdk", "subsdk0")
MTF_TITLE_ID = "0400D4201C6EA000"
MTF_DISPLAY = "1.1.1"
MAX_WALK_DEPTH = 6

# Known wrong / alternate ExeFS main prefixes -> human hint (prefix only; never full dumps).
KNOWN_MAIN_HINTS: dict[str, str] = {
    # Reported by users picking base / incomplete NUP update trees instead of 1.1.1.
    "2846cd27dee": "looks like a base or non-1.1.1 main (not Mario Tennis Fever 1.1.1)",
}


@dataclass
class DumpResolve:
    exefs: Path
    romfs: Path
    notes: list[str] = field(default_factory=list)
    staged: bool = False
    source: str = "folder"


class DumpError(RuntimeError):
    """User-facing dump resolution / verification failure."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_expected_mtf(root: Path, resource_bases: list[Path] | None = None) -> dict[str, str]:
    candidates = [
        root / "tools" / "data" / "expected-mtf111.json",
        root.parent / "tools" / "data" / "expected-mtf111.json",
    ]
    for base in resource_bases or []:
        candidates.append(base / "tools" / "data" / "expected-mtf111.json")
        candidates.append(base / "expected-mtf111.json")
    for cand in candidates:
        if cand.is_file():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
                hashes = data.get("exefs_sha256") or {}
                if hashes:
                    return {str(k): str(v).lower() for k, v in hashes.items()}
            except Exception:
                pass
    # Keep in sync with tools/data/expected-mtf111.json (64-hex digests).
    return {
        "main": "3557c30e0a18e15aedd62f94be66b64de9e31632ed6da250c2f8c2c0ec271171",
        "main.npdm": "6171756a59bf3322620b7f8fe907b51cfe925b14109248cec40cdaea11b62945",
        "rtld": "f3a05703aadc0eabecb1af71522e9be358d797f2b4489028d09c41fe220ebd7c",
        "sdk": "e8a2c5852508f330663d8ad639d4c20609e636c1bc6d5fcf7b01cd4bd3e0428f",
        "subsdk0": "3cf8c4dbaccaf1ed35295b64eb7698863577ca9b8d88e5ef13d360fa713b0d8e",
    }


def is_exefs_dir(path: Path) -> bool:
    return path.is_dir() and (path / "main").is_file()


def is_romfs_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if (path / "romfs.bin").is_file() and (path / "index.json").is_file():
        return True
    if (path / "romfs_packed").is_dir():
        return False
    try:
        for child in path.iterdir():
            if child.name.startswith("."):
                continue
            return True
    except OSError:
        return False
    return False


def exefs_present(path: Path) -> list[str]:
    return [name for name in EXEFS_REQUIRED if (path / name).is_file()]


def exefs_missing(path: Path) -> list[str]:
    return [name for name in EXEFS_REQUIRED if not (path / name).is_file()]


def _depth_of(path: Path, root: Path) -> int:
    try:
        return len(path.relative_to(root).parts)
    except ValueError:
        return 99


def _iter_dirs(root: Path, max_depth: int = MAX_WALK_DEPTH):
    root = root.resolve()
    if not root.is_dir():
        return
    stack: list[tuple[Path, int]] = [(root, 0)]
    seen: set[Path] = set()
    while stack:
        cur, depth = stack.pop()
        try:
            key = cur.resolve()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        yield cur, depth
        if depth >= max_depth:
            continue
        try:
            kids = sorted(cur.iterdir(), key=lambda p: p.name.lower(), reverse=True)
        except OSError:
            continue
        for child in kids:
            name = child.name.lower()
            if not child.is_dir():
                continue
            if name in {"work", "generated", "build", "profile", "logs", "shader-cache",
                        ".git", "__pycache__", "llvm", "python", "bin", "obj"}:
                continue
            stack.append((child, depth + 1))


def find_exefs_candidates(root: Path) -> list[Path]:
    found: list[Path] = []
    for d, _depth in _iter_dirs(root):
        if d.name.lower() == "exefs" and is_exefs_dir(d):
            found.append(d)
        elif is_exefs_dir(d) and d != root:
            # Flattened dumps sometimes put NSO files directly in a titled folder.
            if any((d / n).is_file() for n in ("sdk", "subsdk0", "rtld", "main.npdm")):
                found.append(d)
    if is_exefs_dir(root):
        found.insert(0, root)
    # Prefer complete trees, then shallower paths, then higher update version in path.
    def sort_key(p: Path):
        missing = len(exefs_missing(p))
        ver = _version_from_path(p)
        return (missing, _depth_of(p, root), -(ver or -1), str(p).lower())

    uniq: list[Path] = []
    seen: set[Path] = set()
    for p in sorted(found, key=sort_key):
        try:
            key = p.resolve()
        except OSError:
            key = p
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def find_romfs_candidates(root: Path) -> list[Path]:
    found: list[Path] = []
    for d, _depth in _iter_dirs(root):
        low = d.name.lower()
        if low in {"romfs_packed", "romfs"} and is_romfs_dir(d):
            found.append(d)
    if is_romfs_dir(root) and root.name.lower() in {"romfs", "romfs_packed"}:
        found.insert(0, root)

    def sort_key(p: Path):
        packed = (p / "romfs.bin").is_file() and (p / "index.json").is_file()
        ver = _version_from_path(p)
        # Prefer packed, then shallower, then higher update version.
        return (0 if packed else 1, _depth_of(p, root), -(ver or -1), str(p).lower())

    uniq: list[Path] = []
    seen: set[Path] = set()
    for p in sorted(found, key=sort_key):
        try:
            key = p.resolve()
        except OSError:
            key = p
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


_VER_RE = re.compile(r"(?:^|[\\/])updates[\\/](\d+)(?:[\\/]|$)", re.I)
_VTAG_RE = re.compile(r"\[v(\d+)\]", re.I)


def _version_from_path(path: Path) -> int | None:
    text = str(path)
    m = _VER_RE.search(text)
    if m:
        return int(m.group(1))
    m = _VTAG_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def _is_under_updates(path: Path) -> bool:
    return any(part.lower() == "updates" for part in path.parts)


def find_update_exefs(root: Path) -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    for cand in find_exefs_candidates(root):
        if not _is_under_updates(cand):
            continue
        ver = _version_from_path(cand)
        if ver is None:
            continue
        out.append((ver, cand))
    out.sort(key=lambda t: t[0], reverse=True)
    return out


def find_base_exefs(root: Path, update_exefs: Path | None = None) -> Path | None:
    update_key = None
    if update_exefs is not None:
        try:
            update_key = update_exefs.resolve()
        except OSError:
            update_key = update_exefs
    for cand in find_exefs_candidates(root):
        try:
            key = cand.resolve()
        except OSError:
            key = cand
        if update_key is not None and key == update_key:
            continue
        if _is_under_updates(cand):
            continue
        return cand
    # Sibling / parent of updates/<ver>
    if update_exefs is not None:
        for parent in update_exefs.parents:
            if parent.name.lower() == "updates":
                base_root = parent.parent
                for name in ("exefs", "base/exefs", "program/exefs", "programs/exefs"):
                    p = base_root.joinpath(*name.split("/"))
                    if is_exefs_dir(p):
                        return p
                break
    return None


def find_matching_romfs(exefs: Path, root: Path) -> Path | None:
    # Prefer a romfs next to this exefs, then updates/<ver>/romfs, then any under root.
    sibling = exefs.parent / "romfs_packed"
    if is_romfs_dir(sibling):
        return sibling
    sibling = exefs.parent / "romfs"
    if is_romfs_dir(sibling):
        return sibling
    ver = _version_from_path(exefs)
    if ver is not None:
        for parent in exefs.parents:
            if parent.name.lower() == "updates":
                packed = parent / str(ver) / "romfs_packed"
                raw = parent / str(ver) / "romfs"
                if is_romfs_dir(packed):
                    return packed
                if is_romfs_dir(raw):
                    return raw
                break
    cands = find_romfs_candidates(root)
    return cands[0] if cands else None


def find_base_romfs(root: Path, update_romfs: Path | None = None) -> Path | None:
    update_key = None
    if update_romfs is not None:
        try:
            update_key = update_romfs.resolve()
        except OSError:
            update_key = update_romfs
    for cand in find_romfs_candidates(root):
        try:
            key = cand.resolve()
        except OSError:
            key = cand
        if update_key is not None and key == update_key:
            continue
        if _is_under_updates(cand):
            continue
        return cand
    if update_romfs is not None:
        for parent in update_romfs.parents:
            if parent.name.lower() == "updates":
                base_root = parent.parent
                for name in ("romfs_packed", "romfs", "base/romfs", "program/romfs"):
                    p = base_root.joinpath(*name.split("/"))
                    if is_romfs_dir(p):
                        return p
                break
    return None


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def merge_exefs(base: Path | None, update: Path, dest: Path) -> Path:
    """Overlay update ExeFS on base (when present). Update wins for shared names."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if base is not None and base.resolve() != update.resolve():
        for name in EXEFS_REQUIRED:
            src = base / name
            if src.is_file():
                _copy_file(src, dest / name)
    for name in EXEFS_REQUIRED:
        src = update / name
        if src.is_file():
            _copy_file(src, dest / name)
    # Copy any extra ExeFS siblings (safety; build only needs the five required).
    for src in update.iterdir():
        if src.is_file() and not (dest / src.name).exists():
            _copy_file(src, dest / src.name)
    return dest


def merge_romfs(base: Path | None, update: Path, dest: Path) -> Path:
    """Overlay update RomFS on base. Skips packed->loose conversion; copies trees."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    def copy_tree(src: Path) -> None:
        if (src / "romfs.bin").is_file() and (src / "index.json").is_file():
            _copy_file(src / "romfs.bin", dest / "romfs.bin")
            _copy_file(src / "index.json", dest / "index.json")
            return
        for dirpath, dirnames, filenames in os.walk(src):
            rel = Path(dirpath).relative_to(src)
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.startswith("."):
                    continue
                s = Path(dirpath) / name
                d = dest / rel / name
                _copy_file(s, d)

    if base is not None and base.resolve() != update.resolve():
        copy_tree(base)
    copy_tree(update)
    return dest


def _nested_extracted_roots(root: Path) -> list[Path]:
    """If the user picked a `[NUP]` parent, prefer nested `*-extracted` children."""
    roots = [root]
    try:
        kids = list(root.iterdir())
    except OSError:
        return roots
    extracted = [
        p for p in kids
        if p.is_dir() and ("extracted" in p.name.lower() or MTF_TITLE_ID.lower() in p.name.lower())
    ]
    # Also one more nesting level used by some dumpsters: `[NUP]/<title> ...-extracted`
    for p in kids:
        if not p.is_dir():
            continue
        if "[nup]" in p.name.lower() or p.name.lower().endswith("[nup]"):
            try:
                for c in p.iterdir():
                    if c.is_dir() and ("extracted" in c.name.lower() or MTF_TITLE_ID.lower() in c.name.lower()):
                        extracted.append(c)
            except OSError:
                pass
    for p in extracted:
        if p not in roots:
            roots.append(p)
    return roots


def discover_dump(root: Path, work_dir: Path) -> DumpResolve:
    """Resolve a dump root into complete ExeFS + RomFS paths (may stage merges under work_dir)."""
    if not root.is_dir():
        raise DumpError(f"Dump path is not a folder: {root}")

    notes: list[str] = []
    search_roots = _nested_extracted_roots(root)

    update_pairs: list[tuple[int, Path, Path]] = []  # ver, exefs, search_root
    for sr in search_roots:
        for ver, exefs in find_update_exefs(sr):
            update_pairs.append((ver, exefs, sr))
    update_pairs.sort(key=lambda t: t[0], reverse=True)

    chosen_exefs: Path | None = None
    chosen_romfs: Path | None = None
    base_exefs: Path | None = None
    base_romfs: Path | None = None
    staged = False
    search_root = search_roots[0]

    if update_pairs:
        ver, upd_exefs, search_root = update_pairs[0]
        notes.append(f"Found NUP-style update ExeFS at updates/{ver}/exefs.")
        base_exefs = find_base_exefs(search_root, upd_exefs)
        missing = exefs_missing(upd_exefs)
        if missing and base_exefs is None:
            raise DumpError(
                f"Update ExeFS at {upd_exefs} is missing {', '.join(missing)}. "
                "NUP update packages often omit unchanged modules (for example subsdk0). "
                "Select the parent extracted dump folder that also contains the base ExeFS, "
                "or extract the .nup with tools/extract_nup.py --overlay-update."
            )
        if missing or (base_exefs is not None and base_exefs.resolve() != upd_exefs.resolve()):
            if base_exefs is not None:
                notes.append(f"Overlaying update ExeFS onto base ExeFS ({base_exefs}).")
            dest = work_dir / "merged-exefs"
            chosen_exefs = merge_exefs(base_exefs, upd_exefs, dest)
            staged = True
            still = exefs_missing(chosen_exefs)
            if still:
                raise DumpError(
                    f"Merged ExeFS is still missing {', '.join(still)}. "
                    "The dump does not contain a complete Mario Tennis Fever program."
                )
        else:
            chosen_exefs = upd_exefs

        upd_romfs = find_matching_romfs(upd_exefs, search_root)
        base_romfs = find_base_romfs(search_root, upd_romfs)
        if upd_romfs is None and base_romfs is None:
            raise DumpError(
                f"Could not find a RomFS folder near {upd_exefs}. "
                "Expected romfs or romfs_packed beside ExeFS or under the dump root."
            )
        if (
            upd_romfs is not None
            and base_romfs is not None
            and base_romfs.resolve() != upd_romfs.resolve()
            and not ((upd_romfs / "romfs.bin").is_file() and (upd_romfs / "index.json").is_file())
        ):
            notes.append(f"Overlaying update RomFS onto base RomFS ({base_romfs}).")
            dest = work_dir / "merged-romfs"
            chosen_romfs = merge_romfs(base_romfs, upd_romfs, dest)
            staged = True
        else:
            chosen_romfs = upd_romfs or base_romfs
    else:
        # Flat / already-merged dump.
        for sr in search_roots:
            cands = find_exefs_candidates(sr)
            if not cands:
                continue
            # Prefer a complete ExeFS.
            complete = [c for c in cands if not exefs_missing(c)]
            chosen_exefs = complete[0] if complete else cands[0]
            search_root = sr
            break
        if chosen_exefs is None:
            raise DumpError(
                f"No ExeFS (main) found under {root}. "
                "Select a folder containing exefs/main, an extracted NUP tree, or a .nup file."
            )
        miss = exefs_missing(chosen_exefs)
        if miss:
            raise DumpError(
                f"ExeFS at {chosen_exefs} is missing {', '.join(miss)}. "
                "Mario Tennis Fever 1.1.1 needs main, main.npdm, rtld, sdk, and subsdk0."
            )
        chosen_romfs = find_matching_romfs(chosen_exefs, search_root)
        if chosen_romfs is None:
            for sr in search_roots:
                cands = find_romfs_candidates(sr)
                if cands:
                    chosen_romfs = cands[0]
                    break
        if chosen_romfs is None:
            raise DumpError(f"Found ExeFS at {chosen_exefs} but no RomFS folder nearby.")

    assert chosen_exefs is not None and chosen_romfs is not None
    notes.append(f"Using ExeFS: {chosen_exefs}")
    notes.append(f"Using RomFS: {chosen_romfs}")
    return DumpResolve(exefs=chosen_exefs, romfs=chosen_romfs, notes=notes, staged=staged, source="folder")


def find_extract_nup(root: Path, resource_bases: list[Path] | None = None) -> Path | None:
    candidates = [
        root / "tools" / "extract_nup.py",
        root.parent / "tools" / "extract_nup.py",
    ]
    for base in resource_bases or []:
        candidates.append(base / "tools" / "extract_nup.py")
        candidates.append(base / "extract_nup.py")
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def extract_nup_overlay(
    nup_path: Path,
    out_dir: Path,
    *,
    python: Path | str | None = None,
    extract_script: Path | None = None,
    root: Path | None = None,
) -> DumpResolve:
    """Extract a .nup with base+newest-update overlay into out_dir/exefs + romfs."""
    if not nup_path.is_file():
        raise DumpError(f".nup file not found: {nup_path}")
    if nup_path.suffix.lower() != ".nup":
        raise DumpError(f"Expected a .nup container, got: {nup_path.name}")
    script = extract_script or (find_extract_nup(root) if root else None)
    if script is None:
        raise DumpError(
            "tools/extract_nup.py is missing from this install; cannot unpack .nup automatically. "
            "Extract with: python tools/extract_nup.py <game>.nup --out <dir> --overlay-update"
        )
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    py = str(python or sys.executable)
    cmd = [py, str(script), str(nup_path), "--out", str(out_dir), "--overlay-update"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise DumpError(f"NUP extract failed: {detail or f'exit {proc.returncode}'}")
    exefs = out_dir / "exefs"
    romfs = out_dir / "romfs"
    if not is_exefs_dir(exefs) or not is_romfs_dir(romfs):
        raise DumpError(
            f"NUP extract did not produce exefs/ and romfs/ under {out_dir}. "
            "Check that the container includes Mario Tennis Fever base + update packages."
        )
    notes = [
        f"Extracted {nup_path.name} with base + newest update overlay.",
        f"Using ExeFS: {exefs}",
        f"Using RomFS: {romfs}",
    ]
    # Soft title check from extract listing is not available here; SHA verify is authoritative.
    return DumpResolve(exefs=exefs, romfs=romfs, notes=notes, staged=True, source="nup")


def format_hash_mismatch(fname: str, got: str, want: str) -> str:
    hint = ""
    for prefix, text in KNOWN_MAIN_HINTS.items():
        if fname == "main" and got.lower().startswith(prefix):
            hint = f" Hint: {text}."
            break
    return (
        f"SHA-256 mismatch for {fname}: got {got[:16]}…, expected {want[:16]}… "
        f"(Mario Tennis Fever {MTF_DISPLAY} is required; title {MTF_TITLE_ID})."
        f"{hint} "
        "If you selected an updates/<ver>/exefs folder from a NUP extract, pick the parent "
        "extracted dump (so base + update can be merged) or open the .nup with Browse .NUP…"
    )


def verify_exefs_hashes(exefs: Path, expected: dict[str, str]) -> list[str]:
    """Verify required ExeFS hashes. Raises DumpError with a clear message on failure."""
    lines: list[str] = []
    missing = [name for name in expected if not (exefs / name).is_file()]
    if missing:
        raise DumpError(
            f"Missing ExeFS file(s) under {exefs}: {', '.join(missing)}. "
            "Mario Tennis Fever 1.1.1 needs main, main.npdm, rtld, sdk, and subsdk0. "
            "NUP update-only trees often omit unchanged modules — select the parent dump "
            "folder or extract with --overlay-update."
        )
    for fname, want in sorted(expected.items()):
        fpath = exefs / fname
        got = sha256_file(fpath)
        if got.lower() != want.lower():
            raise DumpError(format_hash_mismatch(fname, got.lower(), want.lower()))
        lines.append(f"{fname}: OK ({got[:12]}…)")
    return lines
