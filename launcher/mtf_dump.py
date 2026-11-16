"""Mario Tennis Fever dump discovery for MTFLauncher.

Resolves plain ExeFS/RomFS folders, NUP-extracted trees (base + updates/<ver>),
and optional .nup containers into a complete 1.1.1 ExeFS + RomFS pair without
shipping or accepting the wrong game silently.
"""

from __future__ import annotations

import errno
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

EXEFS_REQUIRED = ("main", "main.npdm", "rtld", "sdk", "subsdk0")
MTF_TITLE_ID = "0400D4201C6EA000"
MTF_DISPLAY = "1.1.1"
MAX_WALK_DEPTH = 6
NUP_READY_NAME = ".nup-ready.json"

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
        # Simple rule: base present → overlay; otherwise work from the update alone.
        # Emulators/testers often have update-only trees — a separate base folder is optional.
        if base_exefs is not None and (
            missing or base_exefs.resolve() != upd_exefs.resolve()
        ):
            notes.append(f"Overlaying update ExeFS onto base ExeFS ({base_exefs}).")
            dest = work_dir / "merged-exefs"
            chosen_exefs = merge_exefs(base_exefs, upd_exefs, dest)
            staged = True
        else:
            if base_exefs is None and missing:
                notes.append(
                    "No base ExeFS beside this update; using the update ExeFS alone."
                )
            chosen_exefs = upd_exefs
        still = exefs_missing(chosen_exefs)
        if still:
            raise DumpError(
                f"ExeFS is missing {', '.join(still)} under {chosen_exefs}. "
                "Mario Tennis Fever 1.1.1 needs main, main.npdm, rtld, sdk, and subsdk0. "
                "If your .nup includes a base package, use Browse .NUP… (base+update overlay). "
                "Update-only dumps work when the update ExeFS already contains every module — "
                "a separate base dump folder is not required."
            )

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


def _load_extract_nup_mod(script: Path):
    """Load tools/extract_nup.py dynamically so NUP header inspection shares its parser."""
    spec = importlib.util.spec_from_file_location("_mtf_extract_nup_mod", script)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _inspect_nup_packages(mod, nup_path: Path) -> list[tuple[int, int, int, int]]:
    """Return [(index, kind, title_id, version)] from a NUP container header."""
    nup = mod.Nup(nup_path)
    try:
        return [(p.index, p.kind, p.title_id, p.version) for p in nup.packages]
    finally:
        nup.close()


def _find_sibling_nup(
    mod,
    nup_path: Path,
    *,
    want_kind: int,
    title_id: int,
) -> tuple[Path, tuple[int, int, int, int], list[tuple[int, int, int, int]]] | None:
    """Scan sibling *.nup files in nup_path.parent for want_kind in the same title family."""
    target = nup_path.resolve()
    matches: list[tuple[int, str, Path, tuple[int, int, int, int], list[tuple[int, int, int, int]]]] = []
    for cand in sorted(nup_path.parent.glob("*.nup")):
        try:
            if not cand.is_file() or cand.resolve() == target:
                continue
            pkgs = _inspect_nup_packages(mod, cand)
        except Exception:
            continue
        matched = [p for p in pkgs if p[1] == want_kind and mod.same_title_family(p[2], title_id)]
        if not matched:
            continue
        best = max(matched, key=lambda p: p[3])
        matches.append((best[3], cand.name.lower(), cand, best, pkgs))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1]))
    _, _, cand, best, pkgs = matches[0]
    return cand, best, pkgs


def _pick_mtf_preferred(mod, pkgs: list[tuple[int, int, int, int]], kind: int) -> tuple[int, int, int, int]:
    """Choose the matching-kind package (preferring MTF's title family, then highest version)."""
    cands = [p for p in pkgs if p[1] == kind]
    mtf_tid = int(MTF_TITLE_ID, 16)
    mtf_cands = [p for p in cands if mod.same_title_family(p[2], mtf_tid)]
    pool = mtf_cands or cands
    return max(pool, key=lambda p: p[3])


_PROGRESS_RE = re.compile(
    r"^\s*(exefs|romfs):\s*(\d+)/(\d+)\s+files,\s*([\d.]+)\s+of\s+([\d.]+)\s+GB",
    re.I,
)
_FILES_RE = re.compile(r"^\s*(exefs|romfs):\s*(\d+)/(\d+)\s+files", re.I)


def _is_win_lock_error(exc: OSError) -> bool:
    winerr = getattr(exc, "winerror", None)
    return winerr in (5, 32) or exc.errno in (errno.EACCES, errno.EPERM, errno.EBUSY)


def rmtree_retry(path: Path, attempts: int = 8) -> None:
    """Remove directory tree, retrying transient Windows WinError 5/32 locks."""
    if not path.exists():
        return
    delay = 0.05
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except OSError as exc:
            if not _is_win_lock_error(exc) or attempt + 1 >= attempts:
                raise
            time.sleep(delay)
            delay = min(delay * 2.0, 0.5)


def _prepare_clean_out_dir(out_dir: Path) -> Path:
    """Clear out_dir with lock retries; fall back to a sibling folder if AV/indexer keeps a handle."""
    if out_dir.exists():
        try:
            rmtree_retry(out_dir)
        except OSError as exc:
            if not _is_win_lock_error(exc):
                raise
            stamp = int(time.time())
            for idx in range(100):
                suffix = f"{stamp}" if idx == 0 else f"{stamp}-{idx}"
                alt = out_dir.with_name(f"{out_dir.name}-{suffix}")
                if not alt.exists():
                    out_dir = alt
                    break
            else:
                raise DumpError(
                    f"Could not clear temporary NUP extract folder under {out_dir.parent}: {exc}"
                ) from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _write_nup_ready(nup_path: Path, out_dir: Path, exefs: Path, romfs: Path) -> None:
    st = nup_path.stat()
    payload = {
        "nup": str(nup_path.resolve()),
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "exefs": str(exefs.resolve()),
        "romfs": str(romfs.resolve()),
    }
    ready = out_dir / NUP_READY_NAME
    tmp = out_dir / f"{NUP_READY_NAME}.tmp"
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(ready)


def _check_nup_ready_dir(nup_path: Path, cand_dir: Path) -> DumpResolve | None:
    ready = cand_dir / NUP_READY_NAME
    if not ready.is_file() or not nup_path.is_file():
        return None
    try:
        data = json.loads(ready.read_text(encoding="utf-8"))
        st = nup_path.stat()
        if (
            data.get("nup") != str(nup_path.resolve())
            or data.get("size") != st.st_size
            or data.get("mtime_ns") != st.st_mtime_ns
        ):
            return None
    except Exception:
        return None
    exefs = Path(data.get("exefs") or (cand_dir / "exefs"))
    romfs = Path(data.get("romfs") or (cand_dir / "romfs"))
    if not is_exefs_dir(exefs) or exefs_missing(exefs) or not is_romfs_dir(romfs):
        return None
    return DumpResolve(
        exefs=exefs,
        romfs=romfs,
        notes=[
            f"Reusing extracted NUP tree for {nup_path.name} (no re-extract needed).",
            f"Using ExeFS: {exefs}",
            f"Using RomFS: {romfs}",
        ],
        staged=True,
        source="nup",
    )


def reuse_extracted_nup(nup_path: Path, out_dir: Path) -> DumpResolve | None:
    """Return an existing verified NUP extract under out_dir (or sibling fallback) if fresh."""
    hit = _check_nup_ready_dir(nup_path, out_dir)
    if hit is not None:
        return hit
    if out_dir.parent.is_dir():
        siblings = sorted(
            (p for p in out_dir.parent.glob(f"{out_dir.name}-*") if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )
        for sib in siblings:
            hit = _check_nup_ready_dir(nup_path, sib)
            if hit is not None:
                return hit
    return None


def _parse_extract_progress(line: str) -> int | None:
    m = _PROGRESS_RE.match(line)
    if m:
        which = m.group(1).lower()
        n, total = int(m.group(2)), max(1, int(m.group(3)))
        done_gb, total_gb = float(m.group(4)), float(m.group(5))
        frac = (done_gb / total_gb) if total_gb > 0.0 else (n / total)
        frac = max(0.0, min(1.0, frac))
        return (1 + int(4 * frac)) if which == "exefs" else (5 + int(93 * frac))
    m2 = _FILES_RE.match(line)
    if m2:
        which = m2.group(1).lower()
        n, total = int(m2.group(2)), max(1, int(m2.group(3)))
        frac = max(0.0, min(1.0, n / total))
        return (1 + int(4 * frac)) if which == "exefs" else (5 + int(93 * frac))
    return None


def _scaled_progress(
    on_progress: Callable[[str, int | None], None] | None,
    lo: int,
    hi: int,
) -> Callable[[str, int | None], None] | None:
    if on_progress is None:
        return None

    def _cb(line: str, pct: int | None) -> None:
        scaled = None if pct is None else lo + int((hi - lo) * max(0, min(100, pct)) / 100)
        on_progress(line, scaled)

    return _cb


def _run_extract_nup(
    py: str,
    script: Path,
    nup_path: Path,
    out_dir: Path,
    *,
    overlay_update: bool = False,
    package: str | None = None,
    on_progress: Callable[[str, int | None], None] | None = None,
) -> str:
    cmd = [py, str(script), str(nup_path), "--out", str(out_dir)]
    if overlay_update:
        cmd.append("--overlay-update")
    elif package is not None:
        cmd.extend(["--package", str(package)])
    lines: list[str] = []
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ) as proc:
        assert proc.stdout is not None
        for raw in proc.stdout:
            text = raw.rstrip("\r\n")
            lines.append(text)
            if on_progress is not None and text.strip():
                on_progress(text, _parse_extract_progress(text))
        rc = proc.wait()
    combined = "\n".join(lines)
    if rc != 0:
        detail = combined.strip()
        raise DumpError(f"NUP extract failed: {detail or f'exit {rc}'}")
    return combined


def _merge_missing_from_extracted_base(search_root: Path, out_dir: Path, exefs: Path, romfs: Path) -> bool:
    """Fill missing ExeFS/RomFS entries from an extracted base folder beside a sparse update .nup."""
    out_key = out_dir.resolve()

    def _outside_out(p: Path) -> bool:
        rp = p.resolve()
        return rp != out_key and out_key not in rp.parents and not _is_under_updates(p)

    base_exefs = next((c for c in find_exefs_candidates(search_root) if _outside_out(c)), None)
    base_romfs = next((c for c in find_romfs_candidates(search_root) if _outside_out(c)), None)
    merged = False
    if base_exefs is not None:
        exefs.mkdir(parents=True, exist_ok=True)
        for name in EXEFS_REQUIRED:
            src = base_exefs / name
            dst = exefs / name
            if src.is_file() and not dst.is_file():
                _copy_file(src, dst)
                merged = True
        for src in base_exefs.iterdir():
            dst = exefs / src.name
            if src.is_file() and not dst.exists():
                _copy_file(src, dst)
                merged = True
    if base_romfs is not None:
        if not is_romfs_dir(romfs):
            if (base_romfs / "romfs.bin").is_file() and (base_romfs / "index.json").is_file():
                _copy_file(base_romfs / "romfs.bin", romfs / "romfs.bin")
                _copy_file(base_romfs / "index.json", romfs / "index.json")
                merged = True
            else:
                for dirpath, dirnames, filenames in os.walk(base_romfs):
                    rel = Path(dirpath).relative_to(base_romfs)
                    dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                    for name in filenames:
                        if not name.startswith("."):
                            _copy_file(Path(dirpath) / name, romfs / rel / name)
                            merged = True
        elif not ((base_romfs / "romfs.bin").is_file() and (base_romfs / "index.json").is_file()):
            for dirpath, dirnames, filenames in os.walk(base_romfs):
                rel = Path(dirpath).relative_to(base_romfs)
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for name in filenames:
                    if name.startswith("."):
                        continue
                    dst = romfs / rel / name
                    if not dst.exists():
                        _copy_file(Path(dirpath) / name, dst)
                        merged = True
    return merged


def extract_nup_overlay(
    nup_path: Path,
    out_dir: Path,
    *,
    python: Path | str | None = None,
    extract_script: Path | None = None,
    root: Path | None = None,
    on_progress: Callable[[str, int | None], None] | None = None,
) -> DumpResolve:
    """Extract a .nup: base+update (same container or sibling split .nup) when present, else standalone."""
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

    py = str(python or sys.executable)
    mod = _load_extract_nup_mod(script)
    pkgs: list[tuple[int, int, int, int]] | None = None
    if mod is not None:
        try:
            pkgs = _inspect_nup_packages(mod, nup_path)
        except Exception:
            pkgs = None

    actual_out_dir = _prepare_clean_out_dir(out_dir)
    exefs = actual_out_dir / "exefs"
    romfs = actual_out_dir / "romfs"
    mode = "base + update overlay"

    has_base = bool(pkgs and any(p[1] == 0 for p in pkgs))
    has_update = bool(pkgs and any(p[1] == 1 for p in pkgs))

    if mod is not None and pkgs and has_base and not has_update:
        # Case A: user selected a base-only .nup; check sibling *.nup for a matching-family update.
        base_pkg = _pick_mtf_preferred(mod, pkgs, 0)
        base_arg = "base" if sum(1 for p in pkgs if p[1] == 0) == 1 else str(base_pkg[0])
        sibling = _find_sibling_nup(mod, nup_path, want_kind=1, title_id=base_pkg[2])
        if sibling is not None:
            sib_upd_path, _sib_upd_pkg, _sib_pkgs = sibling
            _run_extract_nup(
                py, script, nup_path, actual_out_dir, package=base_arg,
                on_progress=_scaled_progress(on_progress, 0, 60),
            )
            # Keep actual_out_dir intact so the sibling update overlays directly onto the base files.
            _run_extract_nup(
                py, script, sib_upd_path, actual_out_dir, overlay_update=True,
                on_progress=_scaled_progress(on_progress, 60, 100),
            )
            mode = f"base ({nup_path.name}) + sibling update ({sib_upd_path.name})"
        else:
            _run_extract_nup(py, script, nup_path, actual_out_dir, package=base_arg, on_progress=on_progress)
            mode = "base only (no sibling update .nup found)"
    else:
        combined = _run_extract_nup(
            py, script, nup_path, actual_out_dir, overlay_update=True, on_progress=on_progress
        )
        update_only = "update-only" in combined.lower()
        if update_only:
            mode = "update alone (no base package in this .nup)"
        # Case B: sparse update-only .nup missing modules (e.g. subsdk0) or missing RomFS.
        if (
            update_only
            and mod is not None
            and pkgs
            and (not is_exefs_dir(exefs) or not is_romfs_dir(romfs) or bool(exefs_missing(exefs)))
        ):
            upd_pkg = _pick_mtf_preferred(mod, pkgs, 1)
            upd_arg = "update" if sum(1 for p in pkgs if p[1] == 1) == 1 else str(upd_pkg[0])
            sibling = _find_sibling_nup(mod, nup_path, want_kind=0, title_id=upd_pkg[2])
            if sibling is not None:
                sib_base_path, sib_base_pkg, sib_pkgs = sibling
                sib_base_arg = "base" if sum(1 for p in sib_pkgs if p[1] == 0) == 1 else str(sib_base_pkg[0])
                actual_out_dir = _prepare_clean_out_dir(actual_out_dir)
                exefs = actual_out_dir / "exefs"
                romfs = actual_out_dir / "romfs"
                _run_extract_nup(
                    py, script, sib_base_path, actual_out_dir, package=sib_base_arg,
                    on_progress=_scaled_progress(on_progress, 0, 60),
                )
                _run_extract_nup(
                    py, script, nup_path, actual_out_dir, package=upd_arg,
                    on_progress=_scaled_progress(on_progress, 60, 100),
                )
                mode = f"sibling base ({sib_base_path.name}) + update ({nup_path.name})"
            elif _merge_missing_from_extracted_base(nup_path.parent, actual_out_dir, exefs, romfs):
                mode = "extracted base folder + update overlay"

    if not is_exefs_dir(exefs) or not is_romfs_dir(romfs):
        raise DumpError(
            f"NUP extract did not produce exefs/ and romfs/ under {actual_out_dir}. "
            "The container needs a Mario Tennis Fever program package (update alone is fine)."
        )
    missing = exefs_missing(exefs)
    if missing:
        raise DumpError(
            f"NUP extract under {exefs} is missing {', '.join(missing)}. "
            "Mario Tennis Fever 1.1.1 needs main, main.npdm, rtld, sdk, and subsdk0. "
            "Browse .NUP… overlays a matching-title base (…000) onto the update (…800) when "
            "both are in the same container or sibling .nup files in the same folder; a standalone "
            "update-only .nup must already include every ExeFS module."
        )
    _write_nup_ready(nup_path, actual_out_dir, exefs, romfs)
    notes = [
        f"Extracted {nup_path.name} ({mode}).",
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
        "Use Browse .NUP… on your .nup (base+update when both exist, update alone otherwise), "
        "or point Dump Folder at a complete 1.1.1 ExeFS. A separate base dump is optional."
    )


def verify_exefs_hashes(exefs: Path, expected: dict[str, str]) -> list[str]:
    """Verify required ExeFS hashes. Raises DumpError with a clear message on failure."""
    lines: list[str] = []
    missing = [name for name in expected if not (exefs / name).is_file()]
    if missing:
        raise DumpError(
            f"Missing ExeFS file(s) under {exefs}: {', '.join(missing)}. "
            "Mario Tennis Fever 1.1.1 needs main, main.npdm, rtld, sdk, and subsdk0. "
            "Update/NUP-only dumps are fine when those modules are present; if a base package "
            "exists in the same .nup, Browse .NUP… overlays it automatically. "
            "A separate base dump folder is not required."
        )
    for fname, want in sorted(expected.items()):
        fpath = exefs / fname
        got = sha256_file(fpath)
        if got.lower() != want.lower():
            raise DumpError(format_hash_mismatch(fname, got.lower(), want.lower()))
        lines.append(f"{fname}: OK ({got[:12]}…)")
    return lines
