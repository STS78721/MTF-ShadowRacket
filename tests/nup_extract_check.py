"""tools/extract_nup.py against synthetic NUP containers; no game data.

Builds small containers in memory (raw files, zstd files when a zstd backend exists, an empty file, nested folders,
a base and an update package) and checks listing, extraction, the SHA-256 checks and the refusal of unsafe names.

Run: python tests/nup_extract_check.py
"""
import contextlib
import errno
import hashlib
import io
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import extract_nup as nup  # noqa: E402

NO_DIR = 0xFFFFFFFF


def zstd_compress(data):
    """Compress with whichever backend extract_nup would decompress with; None when there is none."""
    z = nup.Zstd()
    if z.kind == 'compression.zstd':
        return z._mod.compress(data)
    if z.kind == 'zstandard':
        return z._mod.ZstdCompressor().compress(data)
    if z.kind == 'zstd program':
        return subprocess.run([z.exe, '-c', '-q'], input=data, capture_output=True, check=True).stdout
    return None


def build(packages, use_zstd=False):
    """packages: list of (kind, title_id, version, {'exefs': tree, 'romfs': tree}); a tree is {name: bytes | tree}."""
    dirs, files, children, pool = [], [], [], bytearray()
    blobs = []

    def name_ref(name):
        raw = name.encode()
        off = len(pool)
        pool.extend(raw)
        return off, len(raw)

    def add_dir(name, tree):
        index = len(dirs)
        dirs.append(None)
        kids = []
        for child_name, value in tree.items():
            if isinstance(value, dict):
                kids.append(('d', add_dir(child_name, value)))
            else:
                kids.append(('f', add_file(child_name, value)))
        first = len(children)
        children.extend(kids)
        dirs[index] = (name_ref(name), first, len(kids))
        return index

    def add_file(name, data):
        index = len(files)
        codec, payload = 0, data
        if use_zstd and data and name.endswith('.z'):
            compressed = zstd_compress(data)
            if compressed is not None:
                codec, payload = 1, compressed
        files.append([name_ref(name), len(data), payload, codec, hashlib.sha256(data).digest(), 0, 0])
        return index

    records = []
    for kind, title_id, version, trees in packages:
        exefs = add_dir('exefs', trees.get('exefs', {})) if 'exefs' in trees else NO_DIR
        romfs = add_dir('romfs', trees.get('romfs', {})) if 'romfs' in trees else NO_DIR
        root = add_dir('root', {})
        records.append((title_id, root, exefs, romfs, version, kind))

    toc_size = (nup.TOC_HEADER_SIZE + len(records) * nup.PACKAGE_SIZE + len(dirs) * nup.DIR_SIZE +
                len(files) * nup.FILE_SIZE + len(children) * 4 + len(pool))
    blob_offset = (nup.SUPER_SIZE + toc_size + 15) & ~15
    blob = bytearray()
    for f in files:
        if f[1] == 0:
            continue
        f[5] = blob_offset + len(blob)
        f[6] = len(f[2])
        blob.extend(f[2])
        blob.extend(b'\0' * (-len(blob) % 16))

    toc = bytearray()
    pool_offset = toc_size - len(pool)
    toc += struct.pack('<IIQQQQQ', nup.TOC_MAGIC, len(records), len(dirs), len(files), pool_offset, len(pool), 0)
    for title_id, root, exefs, romfs, version, kind in records:
        toc += struct.pack('<QIIIIBBHIQI20s', title_id, root, exefs, romfs, version, kind, 0, 0, 0, 0, 0, bytes(20))
    for (name_off, name_len), first, count in dirs:
        toc += struct.pack('<IIIIQ', name_off, name_len, first, count, 0)
    for (name_off, name_len), size, _payload, codec, sha, ext_off, ext_size in files:
        toc += struct.pack('<IIQQQ32sBBH12s', name_off, name_len, size, ext_off, ext_size, sha, codec, 0, 0,
                           bytes(12))
    for kind_, index in children:
        toc += struct.pack('<I', index if kind_ == 'd' else len(dirs) + index)
    toc += pool
    assert len(toc) == toc_size

    file_size = blob_offset + len(blob)
    sb = struct.pack('<4sHHQQ32sQQII16s32s', b'NUP\x01', nup.SUPER_SIZE, 1, nup.SUPER_SIZE, toc_size,
                     hashlib.sha256(toc).digest(), blob_offset, file_size, len(records), 0, bytes(16), bytes(32))
    assert len(sb) == nup.SUPER_SIZE
    out = bytearray(sb + toc)
    out.extend(b'\0' * (blob_offset - len(out)))
    out.extend(blob)
    assert len(out) == file_size
    return bytes(out)


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = nup.main([str(a) for a in args])
    return code, out.getvalue(), err.getvalue()


MAIN = bytes(range(256)) * 40
NPDM = b'META' + bytes(60)
BIG = (b'rock ' * 5000) + bytes(range(50))
# Full-width Nintendo-style IDs so BASE_TITLE_ID_MASK family checks stay distinct in tests.
TID_A = 0x0100AAAA00000000
TID_B = 0x0100BBBB00000000
BASE_TREES = {
    'exefs': {'main': MAIN, 'main.npdm': NPDM},
    'romfs': {'a.bin': b'alpha' * 100, 'empty.bin': b'', 'sub': {'b.bin': b'beta', 'deep': {'c.bin': b'c' * 33}},
              'big.z': BIG},
}
UPDATE_TREES = {'exefs': {'main': MAIN[::-1]}, 'romfs': {'a.bin': b'updated', 'new.bin': b'new'}}


class ExtractNupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, data, name='game.nup'):
        path = self.dir / name
        path.write_bytes(data)
        return path

    def test_list(self):
        path = self.write(build([(0, TID_A, 0, BASE_TREES), (1, TID_A, 65536, UPDATE_TREES)]))
        code, out, _ = run(path, '--list')
        self.assertEqual(code, 0)
        self.assertIn('2 package(s)', out)
        self.assertIn('base', out)
        self.assertIn('update', out)
        self.assertIn('exefs: 2 files', out)

    def test_extract_base(self):
        path = self.write(build([(0, TID_A, 0, BASE_TREES), (1, TID_A, 65536, UPDATE_TREES)]))
        out_dir = self.dir / 'out'
        code, out, err = run(path, '--out', out_dir, '--quiet')
        self.assertEqual(code, 0, err)
        self.assertEqual((out_dir / 'exefs' / 'main').read_bytes(), MAIN)
        self.assertEqual((out_dir / 'exefs' / 'main.npdm').read_bytes(), NPDM)
        self.assertEqual((out_dir / 'romfs' / 'a.bin').read_bytes(), b'alpha' * 100)
        self.assertEqual((out_dir / 'romfs' / 'empty.bin').read_bytes(), b'')
        self.assertEqual((out_dir / 'romfs' / 'sub' / 'deep' / 'c.bin').read_bytes(), b'c' * 33)
        self.assertEqual((out_dir / 'romfs' / 'big.z').read_bytes(), BIG)
        self.assertFalse(list(out_dir.rglob('*.part')))
        # The update package was not touched.
        self.assertFalse((out_dir / 'romfs' / 'new.bin').exists())

    def test_zstd_files(self):
        if zstd_compress(b'x') is None:
            self.skipTest('no zstd backend (compression.zstd, zstandard or a zstd program)')
        path = self.write(build([(0, TID_A, 0, BASE_TREES)], use_zstd=True))
        with contextlib.closing(nup.Nup(path)) as parsed:
            codecs = {parsed.files[i][0]: parsed.files[i][5] for i in range(len(parsed.files))}
        self.assertEqual(codecs['big.z'], 1)
        out_dir = self.dir / 'out'
        code, _, err = run(path, '--out', out_dir, '--quiet')
        self.assertEqual(code, 0, err)
        self.assertEqual((out_dir / 'romfs' / 'big.z').read_bytes(), BIG)

    def test_overlay_update(self):
        path = self.write(build([(0, TID_A, 0, BASE_TREES), (1, TID_A, 65536, UPDATE_TREES)]))
        out_dir = self.dir / 'out'
        code, _, err = run(path, '--out', out_dir, '--overlay-update', '--quiet')
        self.assertEqual(code, 0, err)
        self.assertEqual((out_dir / 'romfs' / 'a.bin').read_bytes(), b'updated')
        self.assertEqual((out_dir / 'romfs' / 'new.bin').read_bytes(), b'new')
        self.assertEqual((out_dir / 'romfs' / 'sub' / 'deep' / 'c.bin').read_bytes(), b'c' * 33)
        self.assertEqual((out_dir / 'exefs' / 'main').read_bytes(), MAIN[::-1])
        self.assertEqual((out_dir / 'exefs' / 'main.npdm').read_bytes(), NPDM)

    def test_overlay_update_only_nup_without_base(self):
        path = self.write(build([(1, TID_A, 65536, UPDATE_TREES)]))
        out_dir = self.dir / 'out'
        code, out, err = run(path, '--out', out_dir, '--overlay-update')
        self.assertEqual(code, 0, err)
        self.assertIn('update-only', out.lower())
        self.assertEqual((out_dir / 'exefs' / 'main').read_bytes(), MAIN[::-1])
        self.assertEqual((out_dir / 'romfs' / 'a.bin').read_bytes(), b'updated')
        self.assertFalse((out_dir / 'exefs' / 'main.npdm').exists())

    def test_atomic_replace_retries_access_denied(self):
        # Simulate Windows Defender briefly locking dest (WinError 5) then succeeding.
        dest = self.dir / 'locked.bin'
        src = self.dir / 'src.bin'
        src.write_bytes(b'payload')
        dest.write_bytes(b'old')
        calls = {'n': 0}
        orig = os.replace

        def flaky_replace_win(a, b):
            calls['n'] += 1
            if calls['n'] < 3:
                exc = OSError(errno.EACCES, 'Access is denied')
                exc.winerror = 5
                raise exc
            return orig(a, b)

        with mock.patch('extract_nup.os.replace', flaky_replace_win):
            nup.atomic_replace(src, dest, attempts=5)
        self.assertEqual(dest.read_bytes(), b'payload')
        self.assertFalse(src.exists())
        self.assertGreaterEqual(calls['n'], 3)

    def test_atomic_replace_copy_fallback(self):
        dest = self.dir / 'locked2.bin'
        src = self.dir / 'src2.bin'
        src.write_bytes(b'payload2')
        dest.write_bytes(b'old2')

        def always_denied(a, b):
            exc = OSError(errno.EACCES, 'Access is denied')
            exc.winerror = 5
            raise exc

        with mock.patch('extract_nup.os.replace', always_denied):
            nup.atomic_replace(src, dest, attempts=3)
        self.assertEqual(dest.read_bytes(), b'payload2')
        self.assertFalse(src.exists())

    def test_extract_overwrites_existing_dest(self):
        path = self.write(build([(0, TID_A, 0, BASE_TREES)]))
        out_dir = self.dir / 'out'
        (out_dir / 'exefs').mkdir(parents=True)
        (out_dir / 'exefs' / 'main.npdm').write_bytes(b'stale-locked-target')
        code, _, err = run(path, '--out', out_dir, '--quiet')
        self.assertEqual(code, 0, err)
        self.assertEqual((out_dir / 'exefs' / 'main.npdm').read_bytes(), NPDM)

    def test_overlay_matches_update_title_base(self):
        # Wrong-title base first must not be used; matching-title base supplies main.npdm.
        other = {'exefs': {'main': b'wrong-title-main'}, 'romfs': {'x.bin': b'x'}}
        path = self.write(build([
            (0, TID_B, 0, other),
            (0, TID_A, 0, BASE_TREES),
            (1, TID_A, 65536, UPDATE_TREES),
        ]))
        out_dir = self.dir / 'out'
        code, _, err = run(path, '--out', out_dir, '--overlay-update', '--quiet')
        self.assertEqual(code, 0, err)
        self.assertEqual((out_dir / 'exefs' / 'main').read_bytes(), MAIN[::-1])
        self.assertEqual((out_dir / 'exefs' / 'main.npdm').read_bytes(), NPDM)
        self.assertFalse((out_dir / 'romfs' / 'x.bin').exists())

    def test_overlay_matches_base_title_family_when_update_uses_800(self):
        """Real dumps use update title …800 vs base …000; exact match misses base and drops subsdk0."""
        base_tid = 0x0400D4201C6EA000  # Mario Tennis Fever application
        update_tid = base_tid | 0x800  # 0400D4201C6EA800
        wrong = {'exefs': {'main': b'wrong', 'subsdk0': b'wrong-sub'}, 'romfs': {'x.bin': b'x'}}
        base_trees = {
            'exefs': {
                'main': MAIN,
                'main.npdm': NPDM,
                'rtld': b'rtld-base',
                'sdk': b'sdk-base',
                'subsdk0': b'subsdk0-from-base',
            },
            'romfs': {'keep.bin': b'keep', 'a.bin': b'old'},
        }
        # Sparse update: no subsdk0 (unchanged module stays on base only).
        update_trees = {
            'exefs': {
                'main': MAIN[::-1],
                'main.npdm': NPDM,
                'rtld': b'rtld-upd',
                'sdk': b'sdk-upd',
            },
            'romfs': {'a.bin': b'updated', 'new.bin': b'new'},
        }
        path = self.write(build([
            (0, 0x04003F40232DE000, 0, wrong),
            (0, base_tid, 0, base_trees),
            (1, update_tid, 327680, update_trees),
        ]))
        out_dir = self.dir / 'out'
        code, out, err = run(path, '--out', out_dir, '--overlay-update')
        self.assertEqual(code, 0, err)
        self.assertIn('base+update overlay', out.lower())
        self.assertIn('title family 0400d4201c6ea000', out.lower())
        self.assertEqual((out_dir / 'exefs' / 'main').read_bytes(), MAIN[::-1])
        self.assertEqual((out_dir / 'exefs' / 'subsdk0').read_bytes(), b'subsdk0-from-base')
        self.assertEqual((out_dir / 'exefs' / 'rtld').read_bytes(), b'rtld-upd')
        self.assertEqual((out_dir / 'romfs' / 'keep.bin').read_bytes(), b'keep')
        self.assertEqual((out_dir / 'romfs' / 'a.bin').read_bytes(), b'updated')
        self.assertFalse((out_dir / 'romfs' / 'x.bin').exists())
        self.assertNotEqual((out_dir / 'exefs' / 'subsdk0').read_bytes(), b'wrong-sub')

    def test_overlay_single_pass_skips_superseded_base_blobs(self):
        base_tid = 0x0400D4201C6EA000
        update_tid = base_tid | 0x800
        base_trees = {
            'exefs': {'main': MAIN, 'main.npdm': NPDM, 'rtld': b'rtld-b', 'sdk': b'sdk-b', 'subsdk0': b'sub-b'},
            'romfs': {'keep.bin': b'keep', 'shared.bin': b'old-shared'},
        }
        update_trees = {
            'exefs': {'main': MAIN[::-1], 'main.npdm': NPDM, 'rtld': b'rtld-u', 'sdk': b'sdk-u'},
            'romfs': {'shared.bin': b'new-shared', 'extra.bin': b'extra'},
        }
        path = self.write(build([(0, base_tid, 0, base_trees), (1, update_tid, 327680, update_trees)]))
        out_dir = self.dir / 'out_single_pass'
        calls = []
        real_extract_file = nup.extract_file

        def spy_extract_file(n, z, idx, dest, verify):
            calls.append((str(dest), n.files[idx][0], idx))
            return real_extract_file(n, z, idx, dest, verify)

        with mock.patch('extract_nup.extract_file', spy_extract_file):
            code, out, err = run(path, '--out', out_dir, '--overlay-update')
        self.assertEqual(code, 0, err)
        dests = [c[0] for c in calls]
        self.assertEqual(len(dests), len(set(dests)), f'superseded files extracted twice: {calls}')
        self.assertEqual(len(calls), 8)  # 5 exefs + 3 romfs extracted exactly once
        self.assertIn('exefs: 5/5 files', out)
        self.assertIn('romfs: 3/3 files', out)
        self.assertEqual((out_dir / 'exefs' / 'main').read_bytes(), MAIN[::-1])
        self.assertEqual((out_dir / 'exefs' / 'subsdk0').read_bytes(), b'sub-b')
        self.assertEqual((out_dir / 'romfs' / 'shared.bin').read_bytes(), b'new-shared')
        self.assertEqual((out_dir / 'romfs' / 'keep.bin').read_bytes(), b'keep')

    def test_package_by_index_and_only(self):
        path = self.write(build([(0, TID_A, 0, BASE_TREES), (1, TID_A, 65536, UPDATE_TREES)]))
        out_dir = self.dir / 'out'
        code, _, err = run(path, '--out', out_dir, '--package', '1', '--only', 'romfs', '--quiet')
        self.assertEqual(code, 0, err)
        self.assertEqual((out_dir / 'romfs' / 'a.bin').read_bytes(), b'updated')
        self.assertFalse((out_dir / 'exefs').exists())

    def test_resume_skips_existing(self):
        path = self.write(build([(0, TID_A, 0, BASE_TREES)]))
        out_dir = self.dir / 'out'
        self.assertEqual(run(path, '--out', out_dir, '--quiet')[0], 0)
        code, out, _ = run(path, '--out', out_dir, '--quiet')
        self.assertEqual(code, 0)
        self.assertIn('already there', out)

    def test_preexisting_part_symlink_is_not_followed(self):
        path = self.write(build([(0, TID_A, 0, {'exefs': {'main': MAIN}})]))
        out_dir = self.dir / 'out' / 'exefs'
        out_dir.mkdir(parents=True)
        outside = self.write(b'outside sentinel', 'outside.txt')
        link = out_dir / 'main.part'
        try:
            link.symlink_to(outside)
        except OSError as e:
            if sys.platform == 'win32' and getattr(e, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege unavailable; run this original case on POSIX')
            raise
        with contextlib.closing(nup.Nup(path)) as parsed:
            nup.extract_tree(parsed, None, parsed.packages[0], 'exefs', out_dir, True, True)
        self.assertEqual(outside.read_bytes(), b'outside sentinel')
        self.assertTrue(link.is_symlink())
        self.assertEqual((out_dir / 'main').read_bytes(), MAIN)

    def test_part_named_entry_and_file_both_survive_resume(self):
        expected = {'foo.part': b'legitimate archive part file', 'foo': b'different final bytes'}
        path = self.write(build([(0, TID_A, 0, {'exefs': expected})]))
        out_dir = self.dir / 'out' / 'exefs'
        with contextlib.closing(nup.Nup(path)) as parsed:
            self.assertEqual([parts for parts, _ in parsed.package_files(parsed.packages[0], 'exefs')],
                             [('foo.part',), ('foo',)])
            first = nup.extract_tree(parsed, None, parsed.packages[0], 'exefs', out_dir, True, True)
            self.assertEqual(first, (2, sum(map(len, expected.values())), 0))
            for name, data in expected.items():
                self.assertEqual((out_dir / name).read_bytes(), data)
                self.assertEqual(nup._hash(out_dir / name), hashlib.sha256(data).digest())
            resumed = nup.extract_tree(parsed, None, parsed.packages[0], 'exefs', out_dir, True, True)
            self.assertEqual(resumed, (2, sum(map(len, expected.values())), 2))
            self.assertEqual({p.name: p.read_bytes() for p in out_dir.iterdir()}, expected)

    def test_hash_failure_preserves_existing_final_and_stale_parts(self):
        data = bytearray(build([(0, TID_A, 0, {'exefs': {'main': MAIN}})]))
        data[-5] ^= 0xff
        path = self.write(data)
        out_dir = self.dir / 'out' / 'exefs'
        out_dir.mkdir(parents=True)
        expected = {'main': b'old final', 'main.part': b'stale partial', 'other.part': b'unrelated data'}
        for name, value in expected.items():
            (out_dir / name).write_bytes(value)
        with contextlib.closing(nup.Nup(path)) as parsed:
            with self.assertRaisesRegex(nup.NupError, 'SHA-256'):
                nup.extract_tree(parsed, None, parsed.packages[0], 'exefs', out_dir, True, True)
        self.assertEqual({p.name: p.read_bytes() for p in out_dir.iterdir()}, expected)

    def test_stream_failure_removes_only_its_created_temp(self):
        path = self.write(build([(0, TID_A, 0, {'exefs': {'main': MAIN}})]))
        out_dir = self.dir / 'out' / 'exefs'
        out_dir.mkdir(parents=True)
        expected = {'main.part': b'stale partial', 'other.part': b'unrelated data'}
        for name, value in expected.items():
            (out_dir / name).write_bytes(value)

        class FailingRead:
            """Original I/O fault after a real container byte; no OS permission failure."""
            def __init__(self, source):
                self.source = source
                self.reads = 0

            def seek(self, offset):
                return self.source.seek(offset)

            def read(self, size):
                self.reads += 1
                if self.reads == 1:
                    return self.source.read(1)
                raise OSError('synthetic container read failure')

            def close(self):
                self.source.close()

        with contextlib.closing(nup.Nup(path)) as parsed:
            parsed.f = FailingRead(parsed.f)
            with self.assertRaisesRegex(OSError, 'synthetic container read failure'):
                nup.extract_tree(parsed, None, parsed.packages[0], 'exefs', out_dir, True, True)
        self.assertEqual({p.name: p.read_bytes() for p in out_dir.iterdir()}, expected)

    def test_publish_failure_preserves_unrelated_files(self):
        path = self.write(build([(0, TID_A, 0, {'exefs': {'main': MAIN}})]))
        out_dir = self.dir / 'out' / 'exefs'
        out_dir.mkdir(parents=True)
        expected = {'main': b'old final', 'main.part': b'stale partial', 'other.part': b'unrelated data'}
        for name, value in expected.items():
            (out_dir / name).write_bytes(value)
        with contextlib.closing(nup.Nup(path)) as parsed:
            with mock.patch.object(nup.os, 'replace', side_effect=OSError('synthetic publish failure')):
                with self.assertRaisesRegex(nup.NupError, 'synthetic publish failure'):
                    nup.extract_tree(parsed, None, parsed.packages[0], 'exefs', out_dir, True, True)
        self.assertEqual({p.name: p.read_bytes() for p in out_dir.iterdir()}, expected)

    def test_corrupt_file_is_refused(self):
        data = bytearray(build([(0, TID_A, 0, {'exefs': {'main': MAIN}})]))
        data[-5] ^= 0xFF   # inside the last extent (main)
        path = self.write(bytes(data))
        out_dir = self.dir / 'out'
        code, _, err = run(path, '--out', out_dir, '--quiet')
        self.assertEqual(code, 1)
        self.assertIn('SHA-256', err)
        self.assertFalse((out_dir / 'exefs' / 'main').exists())
        self.assertFalse(list(out_dir.rglob('*.part')))
        code, _, err = run(path, '--out', out_dir, '--quiet', '--no-verify')
        self.assertEqual(code, 0, err)

    def test_corrupt_toc_is_refused(self):
        data = bytearray(build([(0, TID_A, 0, BASE_TREES)]))
        data[nup.SUPER_SIZE + 0x10] ^= 0x01
        code, _, err = run(self.write(bytes(data)), '--list')
        self.assertEqual(code, 1)
        self.assertIn('table of contents', err)

    def test_truncated_file_is_refused(self):
        data = build([(0, TID_A, 0, BASE_TREES)])
        code, _, err = run(self.write(data[:-40]), '--list')
        self.assertEqual(code, 1)

    def test_not_a_nup(self):
        code, _, err = run(self.write(b'PFS0' + bytes(0x200)), '--list')
        self.assertEqual(code, 1)
        self.assertIn('not a NUP', err)

    def test_unsafe_names_are_refused(self):
        for bad in ('..', 'a/b', 'a\\b', 'c:x'):
            path = self.write(build([(0, TID_A, 0, {'exefs': {bad: b'x'}})]), name='bad.nup')
            out_dir = self.dir / 'out'
            code, _, err = run(path, '--out', out_dir, '--quiet')
            self.assertEqual(code, 1, bad)
            self.assertIn('unsafe name', err)
            self.assertFalse((self.dir / 'x').exists())
            shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
