"""Synthetic dump discovery checks for launcher/mtf_dump.py (no game data)."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "launcher"))
import mtf_dump as md  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
