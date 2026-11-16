"""Synthetic dump discovery checks for launcher/mtf_dump.py (no game data)."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
