#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify extracted files against a separately checked package manifest."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def verify(root):
    root = Path(root)
    manifest = root / 'PACKAGE_MANIFEST.json'
    if root.is_symlink() or manifest.is_symlink():
        raise ValueError('LINK')
    entries = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(entries, list) or not entries:
        raise ValueError('EMPTY_MANIFEST')
    seen = set()
    for entry in entries:
        name = entry['path']
        path = PurePosixPath(name)
        if (not isinstance(name, str) or path.is_absolute() or '\\' in name
                or ':' in name or '..' in path.parts or name != str(path)
                or name in seen or name == 'PACKAGE_MANIFEST.json'):
            raise ValueError('PATH')
        seen.add(name)
        target = root
        for part in path.parts:
            target = target / part
            if target.is_symlink():
                raise ValueError('LINK')
        data = target.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('HASH')
    return len(entries)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    try:
        count = verify(args.root)
    except (OSError, ValueError, KeyError, TypeError):
        print('PACKAGE_VERIFY_FAILED')
        raise SystemExit(2)
    print('PACKAGE_FILES_VERIFIED: ' + str(count))
