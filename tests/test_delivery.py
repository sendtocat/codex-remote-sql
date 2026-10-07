# SPDX-License-Identifier: MIT
"""Delivery regression checks: corruption must stop before payload writes."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import restore_mail as mail
from verify_package import verify


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'out'
        self.out.mkdir()
        self.name = 'intake/HANDOFF.txt'
        self.payload = '架空の引継ぎ\n'.encode()
        self.digest = hashlib.sha256(self.payload).hexdigest()
        mail.EXPECTED = {self.name: {'bytes': len(self.payload), 'parts': [self.digest], 'sha256': self.digest}}

    def body(self, name=None, payload=None):
        meta = dict(format='RAW-MAIL-1', path=name or self.name, part=1, total=1,
                    part_sha256=self.digest, file_sha256=self.digest, file_bytes=len(self.payload))
        p = self.root / 'message.txt'
        p.write_text('TRANSFER-META ' + json.dumps(meta) + '\nBEGIN RAW FILE\n' +
                     (self.payload if payload is None else payload).decode() + 'END RAW FILE\n')
        return p

    def restore(self, *paths):
        with contextlib.redirect_stdout(io.StringIO()):
            return mail.restore(self.out, paths)

    def test_roundtrip_bom_crlf(self):
        p = self.body()
        p.write_bytes(b'\xef\xbb\xbf' + p.read_bytes().replace(b'\n', b'\r\n'))
        self.assertEqual(self.restore(p).read_bytes(), self.payload)

    def test_corruption_stops_without_write(self):
        with self.assertRaises(ValueError):
            self.restore(self.body(payload=b'corrupted\n'))
        self.assertEqual(list(self.out.iterdir()), [])

    def test_traversal_rejected(self):
        with self.assertRaises(ValueError):
            self.restore(self.body(name='../outside.txt'))

    def test_duplicate_and_missing_rejected(self):
        p = self.body()
        with self.assertRaises(ValueError):
            self.restore(p, p)
        mail.EXPECTED[self.name]['parts'].append(self.digest)
        with self.assertRaises(ValueError):
            self.restore(p)

    def test_overwrite_rejected(self):
        p = self.body()
        self.restore(p)
        with self.assertRaises(ValueError):
            self.restore(p)

    def test_destination_link_rejected(self):
        (self.out / 'intake').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.restore(self.body())

    def test_bad_manifest_path_rejected(self):
        p = self.root / 'manifest.json'
        p.write_text(json.dumps({'../outside.txt': mail.EXPECTED[self.name]}))
        with self.assertRaises(ValueError):
            mail.load_expected(p)

    def test_package_manifest_detects_tampering(self):
        (self.out / 'file.txt').write_bytes(self.payload)
        (self.out / 'PACKAGE_MANIFEST.json').write_text(json.dumps([
            dict(path='file.txt', bytes=len(self.payload), sha256=self.digest)]))
        self.assertEqual(verify(self.out), 1)
        (self.out / 'file.txt').write_bytes(b'bad')
        with self.assertRaises(ValueError):
            verify(self.out)


if __name__ == '__main__':
    unittest.main()
