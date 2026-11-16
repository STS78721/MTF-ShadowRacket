"""Synthetic dump discovery checks for launcher/mtf_dump.py (no game data)."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "launcher"))
sys.path.insert(0, str(ROOT / "tests"))
import mtf_dump as md  # noqa: E402
import nup_extract_check as nec  # noqa: E402


def write(path: Path, data: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class MtfDumpDiscoverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_flat_exefs_romfs(self) -> None:
        for name in md.EXEFS_REQUIRED:
            write(self.root / "exefs" / name, name.encode() * 8)
        write(self.root / "romfs" / "Data" / "a.bin", b"rom")
        work = self.root / "work"
        resolved = md.discover_dump(self.root, work)
        self.assertTrue((resolved.exefs / "main").is_file())
        self.assertTrue((resolved.romfs / "Data" / "a.bin").is_file())
        self.assertFalse(resolved.staged)

    def test_update_missing_subsdk0_overlays_base(self) -> None:
        base = self.root / "Mario Tennis Fever [0400D4201C6EA000][v327680]-extracted"
        for name in md.EXEFS_REQUIRED:
            write(base / "exefs" / name, f"base-{name}".encode() * 4)
        write(base / "romfs" / "keep.bin", b"keep")
        upd = base / "updates" / "327680"
        for name in ("main", "main.npdm", "rtld", "sdk"):
            write(upd / "exefs" / name, f"upd-{name}".encode() * 4)
        write(upd / "romfs" / "new.bin", b"new")
        # Intentionally no subsdk0 in update.
        work = self.root / "work"
        resolved = md.discover_dump(base, work)
        self.assertTrue(resolved.staged)
        self.assertEqual((resolved.exefs / "main").read_bytes(), b"upd-main" * 4)
        self.assertEqual((resolved.exefs / "subsdk0").read_bytes(), b"base-subsdk0" * 4)
        self.assertTrue((resolved.romfs / "keep.bin").is_file())
        self.assertTrue((resolved.romfs / "new.bin").is_file())

    def test_nested_nup_parent_folder(self) -> None:
        parent = self.root / "Mario Tennis Fever [NUP]"
        base = parent / "Mario Tennis Fever [0400D4201C6EA000][v327680]-extracted"
        for name in md.EXEFS_REQUIRED:
            write(base / "exefs" / name, b"ok")
        write(base / "romfs" / "a.bin", b"a")
        work = self.root / "work"
        resolved = md.discover_dump(parent, work)
        self.assertEqual(resolved.exefs.name, "exefs")
        self.assertTrue((resolved.exefs / "subsdk0").is_file())

    def test_update_only_complete_without_base(self) -> None:
        """Update-only trees with every ExeFS module work; no parent base required."""
        root = self.root / "extracted"
        upd = root / "updates" / "327680"
        for name in md.EXEFS_REQUIRED:
            write(upd / "exefs" / name, f"upd-{name}".encode() * 4)
        write(upd / "romfs" / "a.bin", b"a")
        resolved = md.discover_dump(root, self.root / "work")
        self.assertEqual(resolved.exefs, upd / "exefs")
        self.assertTrue((resolved.exefs / "subsdk0").is_file())
        self.assertFalse(resolved.staged)

    def test_update_only_incomplete_errors_without_requiring_parent(self) -> None:
        root = self.root / "extracted"
        upd = root / "updates" / "327680" / "exefs"
        write(upd / "main", b"main-only")
        write(upd / "sdk", b"sdk")
        write(root / "updates" / "327680" / "romfs" / "a.bin", b"a")
        with self.assertRaises(md.DumpError) as ctx:
            md.discover_dump(root, self.root / "work")
        msg = str(ctx.exception)
        self.assertIn("subsdk0", msg)
        self.assertIn("not required", msg.lower())
        self.assertNotIn("parent extracted dump", msg.lower())

    def test_hash_mismatch_message_mentions_known_prefix(self) -> None:
        got = "2846cd27dee" + "0" * 53
        want = "3557c30e0a18" + "0" * 52
        msg = md.format_hash_mismatch("main", got, want)
        self.assertIn("1.1.1", msg)
        self.assertIn("2846cd27dee", msg)
        self.assertIn("non-1.1.1", msg)

    def test_verify_exefs_hashes_ok(self) -> None:
        exefs = self.root / "exefs"
        expected = {}
        for name in md.EXEFS_REQUIRED:
            data = name.encode() * 32
            write(exefs / name, data)
            expected[name] = hashlib.sha256(data).hexdigest()
        lines = md.verify_exefs_hashes(exefs, expected)
        self.assertEqual(len(lines), 5)

    def _mtf_trees(self):
        base_tid = 0x0400D4201C6EA000
        upd_tid = base_tid | 0x800
        base_trees = {
            "exefs": {
                "main": b"base-main-bytes",
                "main.npdm": b"base-npdm-bytes",
                "rtld": b"base-rtld-bytes",
                "sdk": b"base-sdk-bytes",
                "subsdk0": b"base-subsdk0-bytes",
            },
            "romfs": {"keep.bin": b"keep", "shared.bin": b"old"},
        }
        sparse_upd_trees = {
            "exefs": {
                "main": b"upd-main-bytes",
                "main.npdm": b"upd-npdm-bytes",
                "rtld": b"upd-rtld-bytes",
                "sdk": b"upd-sdk-bytes",
            },
            "romfs": {"shared.bin": b"new", "extra.bin": b"extra"},
        }
        complete_upd_trees = {
            "exefs": {
                **sparse_upd_trees["exefs"],
                "subsdk0": b"upd-subsdk0-bytes",
            },
            "romfs": {"shared.bin": b"new", "extra.bin": b"extra"},
        }
        return base_tid, upd_tid, base_trees, sparse_upd_trees, complete_upd_trees

    def test_extract_nup_overlay_combined_base_and_sparse_update(self) -> None:
        base_tid, upd_tid, base_trees, sparse_upd_trees, _ = self._mtf_trees()
        nup_path = self.root / "combined.nup"
        nup_path.write_bytes(
            nec.build([(0, base_tid, 0, base_trees), (1, upd_tid, 327680, sparse_upd_trees)])
        )
        out_dir = self.root / "work" / "nup-extract"
        resolved = md.extract_nup_overlay(
            nup_path, out_dir, extract_script=ROOT / "tools" / "extract_nup.py", root=ROOT
        )
        self.assertEqual(md.exefs_missing(resolved.exefs), [])
        self.assertEqual((resolved.exefs / "main").read_bytes(), b"upd-main-bytes")
        self.assertEqual((resolved.exefs / "subsdk0").read_bytes(), b"base-subsdk0-bytes")
        self.assertEqual((resolved.romfs / "keep.bin").read_bytes(), b"keep")
        self.assertEqual((resolved.romfs / "shared.bin").read_bytes(), b"new")

    def test_extract_nup_overlay_complete_update_only(self) -> None:
        _, upd_tid, _, _, complete_upd_trees = self._mtf_trees()
        nup_path = self.root / "complete-update.nup"
        nup_path.write_bytes(nec.build([(1, upd_tid, 327680, complete_upd_trees)]))
        out_dir = self.root / "work" / "nup-extract"
        resolved = md.extract_nup_overlay(
            nup_path, out_dir, extract_script=ROOT / "tools" / "extract_nup.py", root=ROOT
        )
        self.assertEqual(md.exefs_missing(resolved.exefs), [])
        self.assertEqual((resolved.exefs / "main").read_bytes(), b"upd-main-bytes")
        self.assertEqual((resolved.exefs / "subsdk0").read_bytes(), b"upd-subsdk0-bytes")

    def test_extract_nup_overlay_split_nups_picking_either_file(self) -> None:
        base_tid, upd_tid, base_trees, sparse_upd_trees, _ = self._mtf_trees()
        nup_dir = self.root / "split-nups"
        nup_dir.mkdir(parents=True, exist_ok=True)
        base_nup = nup_dir / "MTF_base.nup"
        upd_nup = nup_dir / "MTF_111_update.nup"
        base_nup.write_bytes(nec.build([(0, base_tid, 0, base_trees)]))
        upd_nup.write_bytes(nec.build([(1, upd_tid, 327680, sparse_upd_trees)]))

        # Case A: pick base.nup -> finds sibling update.nup and overlays it.
        out_a = self.root / "work" / "out-a"
        res_a = md.extract_nup_overlay(
            base_nup, out_a, extract_script=ROOT / "tools" / "extract_nup.py", root=ROOT
        )
        self.assertEqual(md.exefs_missing(res_a.exefs), [])
        self.assertEqual((res_a.exefs / "main").read_bytes(), b"upd-main-bytes")
        self.assertEqual((res_a.exefs / "subsdk0").read_bytes(), b"base-subsdk0-bytes")
        self.assertEqual((res_a.romfs / "keep.bin").read_bytes(), b"keep")
        self.assertEqual((res_a.romfs / "shared.bin").read_bytes(), b"new")
        self.assertEqual((res_a.romfs / "extra.bin").read_bytes(), b"extra")

        # Case B: pick sparse update.nup -> finds sibling base.nup, extracts base first, overlays update.
        out_b = self.root / "work" / "out-b"
        res_b = md.extract_nup_overlay(
            upd_nup, out_b, extract_script=ROOT / "tools" / "extract_nup.py", root=ROOT
        )
        self.assertEqual(md.exefs_missing(res_b.exefs), [])
        self.assertEqual((res_b.exefs / "main").read_bytes(), b"upd-main-bytes")
        self.assertEqual((res_b.exefs / "subsdk0").read_bytes(), b"base-subsdk0-bytes")
        self.assertEqual((res_b.romfs / "keep.bin").read_bytes(), b"keep")
        self.assertEqual((res_b.romfs / "shared.bin").read_bytes(), b"new")
        self.assertEqual((res_b.romfs / "extra.bin").read_bytes(), b"extra")

    def test_extract_nup_overlay_base_only_without_sibling_update(self) -> None:
        base_tid, _, base_trees, _, _ = self._mtf_trees()
        base_nup = self.root / "solo-base.nup"
        base_nup.write_bytes(nec.build([(0, base_tid, 0, base_trees)]))
        out_dir = self.root / "work" / "out-base"
        res = md.extract_nup_overlay(
            base_nup, out_dir, extract_script=ROOT / "tools" / "extract_nup.py", root=ROOT
        )
        self.assertEqual(md.exefs_missing(res.exefs), [])
        self.assertEqual((res.exefs / "main").read_bytes(), b"base-main-bytes")

    def test_extract_nup_overlay_sparse_update_merges_extracted_base_folder(self) -> None:
        _, upd_tid, base_trees, sparse_upd_trees, _ = self._mtf_trees()
        folder = self.root / "mixed-folder"
        for name, data in base_trees["exefs"].items():
            write(folder / "exefs" / name, data)
        for name, data in base_trees["romfs"].items():
            write(folder / "romfs" / name, data)
        upd_nup = folder / "sparse-update.nup"
        upd_nup.write_bytes(nec.build([(1, upd_tid, 327680, sparse_upd_trees)]))
        out_dir = self.root / "work" / "out-mixed"
        res = md.extract_nup_overlay(
            upd_nup, out_dir, extract_script=ROOT / "tools" / "extract_nup.py", root=ROOT
        )
        self.assertEqual(md.exefs_missing(res.exefs), [])
        self.assertEqual((res.exefs / "main").read_bytes(), b"upd-main-bytes")
        self.assertEqual((res.exefs / "subsdk0").read_bytes(), b"base-subsdk0-bytes")
        self.assertEqual((res.romfs / "keep.bin").read_bytes(), b"keep")
        self.assertEqual((res.romfs / "shared.bin").read_bytes(), b"new")

    def test_extract_nup_overlay_sparse_update_alone_reports_missing_subsdk0(self) -> None:
        _, upd_tid, _, sparse_upd_trees, _ = self._mtf_trees()
        solo_dir = self.root / "solo-upd"
        solo_dir.mkdir(parents=True, exist_ok=True)
        upd_nup = solo_dir / "sparse-only.nup"
        upd_nup.write_bytes(nec.build([(1, upd_tid, 327680, sparse_upd_trees)]))
        out_dir = self.root / "work" / "out-err"
        with self.assertRaises(md.DumpError) as ctx:
            md.extract_nup_overlay(
                upd_nup, out_dir, extract_script=ROOT / "tools" / "extract_nup.py", root=ROOT
            )
        self.assertIn("subsdk0", str(ctx.exception))

    def test_reuse_extracted_nup_hits_and_invalidates(self) -> None:
        base_tid, upd_tid, base_trees, sparse_upd_trees, _ = self._mtf_trees()
        nup_path = self.root / "combined.nup"
        nup_path.write_bytes(
            nec.build([(0, base_tid, 0, base_trees), (1, upd_tid, 327680, sparse_upd_trees)])
        )
        out_dir = self.root / "work" / "nup-extract"
        self.assertIsNone(md.reuse_extracted_nup(nup_path, out_dir))
        res = md.extract_nup_overlay(
            nup_path, out_dir, extract_script=ROOT / "tools" / "extract_nup.py", root=ROOT
        )
        hit = md.reuse_extracted_nup(nup_path, out_dir)
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.exefs.resolve(), res.exefs.resolve())
        self.assertEqual(hit.romfs.resolve(), res.romfs.resolve())

        # Removing an ExeFS file invalidates reuse.
        saved_sub = (res.exefs / "subsdk0").read_bytes()
        (res.exefs / "subsdk0").unlink()
        self.assertIsNone(md.reuse_extracted_nup(nup_path, out_dir))
        (res.exefs / "subsdk0").write_bytes(saved_sub)
        self.assertIsNotNone(md.reuse_extracted_nup(nup_path, out_dir))

        # Changing the .nup bytes/mtime invalidates reuse.
        nup_path.write_bytes(
            nec.build([(0, base_tid, 0, base_trees), (1, upd_tid, 327681, sparse_upd_trees)])
        )
        self.assertIsNone(md.reuse_extracted_nup(nup_path, out_dir))

    def test_rmtree_retry_recovers_after_transient_winerror32(self) -> None:
        locked = self.root / "locked-dir"
        write(locked / "a.bin", b"data")
        calls = {"n": 0}
        real_rmtree = shutil.rmtree

        def flaky_rmtree(path, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                exc = PermissionError(errno.EACCES, "File in use")
                exc.winerror = 32
                raise exc
            return real_rmtree(path, *args, **kwargs)

        with mock.patch("mtf_dump.shutil.rmtree", flaky_rmtree), mock.patch("mtf_dump.time.sleep"):
            md.rmtree_retry(locked, attempts=5)
        self.assertFalse(locked.exists())
        self.assertGreaterEqual(calls["n"], 3)

    def test_extract_nup_overlay_progress_and_rmtree_lock_fallback(self) -> None:
        base_tid, upd_tid, base_trees, sparse_upd_trees, _ = self._mtf_trees()
        nup_path = self.root / "combined.nup"
        nup_path.write_bytes(
            nec.build([(0, base_tid, 0, base_trees), (1, upd_tid, 327680, sparse_upd_trees)])
        )
        out_dir = self.root / "work" / "nup-extract"
        write(out_dir / "stale.part", b"locked")
        events: list[tuple[str, int | None]] = []

        def locked_rmtree(path, *args, **kwargs):
            exc = PermissionError(errno.EACCES, "Sharing violation")
            exc.winerror = 32
            raise exc

        with mock.patch("mtf_dump.shutil.rmtree", locked_rmtree), mock.patch("mtf_dump.time.sleep"):
            res = md.extract_nup_overlay(
                nup_path,
                out_dir,
                extract_script=ROOT / "tools" / "extract_nup.py",
                root=ROOT,
                on_progress=lambda line, pct: events.append((line, pct)),
            )
        self.assertNotEqual(res.exefs.parent.resolve(), out_dir.resolve())
        self.assertTrue(res.exefs.parent.name.startswith("nup-extract-"))
        self.assertEqual(md.exefs_missing(res.exefs), [])
        self.assertTrue(any(pct is not None and 0 <= pct <= 100 for _, pct in events), events)
        # Fallback directory is also discovered by reuse_extracted_nup.
        hit = md.reuse_extracted_nup(nup_path, out_dir)
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.exefs.resolve(), res.exefs.resolve())

    def test_four_file_exefs_with_nrr_discovers_and_verifies(self) -> None:
        exefs = self.root / "exefs"
        expected = {}
        for name in md.EXEFS_CORE:
            data = name.encode() * 32
            write(exefs / name, data)
            expected[name] = hashlib.sha256(data).hexdigest()
        expected["subsdk0"] = "0" * 64
        write(self.root / "romfs" / ".nrr" / "nrr.nrr", b"NRR0" + b"\x00" * 60)
        write(self.root / "romfs" / "42", b"archive")

        resolved = md.discover_dump(self.root, self.root / "work")
        self.assertFalse((resolved.exefs / "subsdk0").exists())
        self.assertTrue(md.romfs_has_nrr(resolved.romfs))
        self.assertEqual(md.exefs_missing(resolved.exefs, romfs=resolved.romfs), [])
        self.assertTrue(any("subsdk0" in n for n in resolved.notes))

        lines = md.verify_exefs_hashes(resolved.exefs, expected, allow_missing_subsdk0=True)
        self.assertTrue(any("subsdk0: queued" in line for line in lines))

        # Packed romfs with .nrr/nrr.nrr in index.json also counts as romfs_has_nrr.
        packed = self.root / "romfs_packed"
        write(packed / "romfs.bin", b"data")
        write(packed / "index.json", json.dumps({"files": [{"path": ".nrr/nrr.nrr", "offset": 0, "size": 4}]}).encode())
        self.assertTrue(md.romfs_has_nrr(packed))

    def test_four_file_nup_with_nrr_extracts_and_reuses(self) -> None:
        base_tid, upd_tid, _, sparse_upd_trees, _ = self._mtf_trees()
        nrr_trees = {
            "exefs": sparse_upd_trees["exefs"],
            "romfs": {".nrr": {"nrr.nrr": b"NRR0" + b"\x00" * 60}, "42": b"archive"},
        }
        nup_path = self.root / "mtf-v327680.nup"
        nup_path.write_bytes(nec.build([(0, base_tid | 0x000, 327680, nrr_trees)]))
        out_dir = self.root / "work" / "nup-extract"
        res = md.extract_nup_overlay(
            nup_path, out_dir, extract_script=ROOT / "tools" / "extract_nup.py", root=ROOT
        )
        self.assertFalse((res.exefs / "subsdk0").exists())
        self.assertTrue((res.romfs / ".nrr" / "nrr.nrr").is_file())
        self.assertEqual(md.exefs_missing(res.exefs, romfs=res.romfs), [])
        hit = md.reuse_extracted_nup(nup_path, out_dir)
        self.assertIsNotNone(hit)

    def test_nro_to_nso_round_trip(self) -> None:
        t_seg = b"\x1f\x20\x03\xd5" * 16
        r_seg = b"rodata\x00\x00" * 8
        d_seg = b"\x01\x02\x03\x04" * 8
        t_off = 0x80
        r_off = t_off + len(t_seg)
        d_off = r_off + len(r_seg)
        nro = bytearray(d_off + len(d_seg))
        nro[0x10:0x14] = b"NRO0"
        struct.pack_into("<II", nro, 0x18, len(nro), 0)
        struct.pack_into("<IIIIIII", nro, 0x20, t_off, len(t_seg), r_off, len(r_seg), d_off, len(d_seg), 0x1000)
        build_id = bytes(range(32))
        nro[0x40:0x60] = build_id
        nro[t_off:t_off + len(t_seg)] = t_seg
        nro[r_off:r_off + len(r_seg)] = r_seg
        nro[d_off:d_off + len(d_seg)] = d_seg

        nso_default = md.nro_to_nso(bytes(nro))
        self.assertEqual(nso_default[:4], b"NSO0")
        self.assertEqual(nso_default[0x40:0x60], build_id)
        t0, _, ts0, _ = struct.unpack_from("<IIII", nso_default, 0x10)
        self.assertEqual(nso_default[t0:t0 + ts0], t_seg)

        # Also test matching a specific flags_hash=0 variant via want_sha256.
        hdr_noh = bytearray(0x100)
        struct.pack_into("<4sIII", hdr_noh, 0x00, b"NSO0", 0, 0, 0)
        struct.pack_into("<IIII", hdr_noh, 0x10, 0x100, t_off, len(t_seg), 0)
        struct.pack_into("<IIII", hdr_noh, 0x20, 0x100 + len(t_seg), r_off, len(r_seg), 0)
        struct.pack_into("<IIII", hdr_noh, 0x30, 0x100 + len(t_seg) + len(r_seg), d_off, len(d_seg), 0x1000)
        hdr_noh[0x40:0x60] = build_id
        struct.pack_into("<III", hdr_noh, 0x60, len(t_seg), len(r_seg), len(d_seg))
        cand0 = bytes(hdr_noh) + t_seg + r_seg + d_seg
        want = hashlib.sha256(cand0).hexdigest()
        matched = md.nro_to_nso(bytes(nro), want_sha256=want)
        self.assertEqual(hashlib.sha256(matched).hexdigest(), want)


if __name__ == "__main__":
    unittest.main()
