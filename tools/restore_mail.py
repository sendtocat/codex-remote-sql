#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 codex-remote-sql contributors
"""Restore visible source from email bodies. Local only; never execute payloads.
Human must check root and inbox are local, non-link and non-sync beforehand.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
EXPECTED = {}
ALLOWED = {'intake/CANON_REQUIREMENTS.txt', 'intake/HANDOFF.txt',
           'intake/START_HERE.txt', 'intake/UPSTREAM_CANON.txt'}

def load_expected(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique_object)
    if not isinstance(data, dict) or not data or not set(data) <= ALLOWED:
        fail('INVALID_ALLOWLIST')
    for spec in data.values():
        if not isinstance(spec, dict) or set(spec) != {'bytes', 'parts', 'sha256'}:
            fail('INVALID_SPEC')
        if type(spec['bytes']) is not int or not 0 < spec['bytes'] <= 200000:
            fail('INVALID_SIZE')
        if not isinstance(spec['parts'], list) or not 1 <= len(spec['parts']) <= 40:
            fail('INVALID_PARTS')
        for digest in [spec['sha256']] + spec['parts']:
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                fail('INVALID_HASH')
    return data

def fail(code):
    raise ValueError(code)
def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: fail('DUPLICATE_JSON_KEY')
        result[key] = value
    return result
def parse_mail(path):
    if path.is_symlink() or not path.is_file(): fail('MAIL_NOT_REGULAR')
    raw = path.read_bytes()
    if len(raw) > 100000: fail('MAIL_TOO_LARGE')
    text = raw.decode('utf-8-sig').replace('\r\n', '\n')
    if '\r' in text or '\x00' in text: fail('INVALID_TEXT')
    lines = text.splitlines(keepends=True)
    begins = [i for i,v in enumerate(lines) if v == 'BEGIN RAW FILE\n']
    ends = [i for i,v in enumerate(lines) if v.rstrip('\n') == 'END RAW FILE']
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]: fail('INVALID_FRAMING')
    begin,end = begins[0],ends[0]
    headers = [v for v in lines[:begin] if v.startswith('TRANSFER-META ')]
    if len(headers) != 1: fail('INVALID_HEADER')
    meta = json.loads(headers[0][len('TRANSFER-META '):], object_pairs_hook=unique_object)
    keys = {'format','path','part','total','part_sha256','file_sha256','file_bytes'}
    if not isinstance(meta,dict) or set(meta) != keys or meta['format'] != 'RAW-MAIL-1': fail('INVALID_META')
    name = meta['path']
    if not isinstance(name,str) or name not in EXPECTED: fail('PATH_NOT_ALLOWED')
    spec = EXPECTED[name]
    if (type(meta['part']) is not int or type(meta['total']) is not int
        or type(meta['file_bytes']) is not int or meta['total'] != len(spec['parts'])
        or not 1 <= meta['part'] <= meta['total'] or meta['file_bytes'] != spec['bytes']
        or meta['file_sha256'] != spec['sha256']
        or meta['part_sha256'] != spec['parts'][meta['part']-1]):
        fail('META_MISMATCH')
    data = ''.join(lines[begin+1:end]).encode('utf-8')
    if hashlib.sha256(data).hexdigest() != meta['part_sha256']: fail('PART_HASH_MISMATCH')
    return name,meta['part'],data
def restore(root, mail_paths):
    root = Path(os.path.abspath(root))
    for p in [root]+list(root.parents):
        if p.is_symlink(): fail('ROOT_HAS_SYMLINK')
    if not root.is_dir(): fail('ROOT_MUST_EXIST')
    chunks = {}; name = None
    for p in mail_paths:
        item,number,data = parse_mail(p)
        if name is not None and item != name: fail('MIXED_FILES')
        if number in chunks: fail('DUPLICATE_PART')
        name = item; chunks[number] = data
    if name is None: fail('NO_PARTS')
    spec = EXPECTED[name]
    if set(chunks) != set(range(1,len(spec['parts'])+1)): fail('MISSING_PART')
    data = b''.join(chunks[i] for i in range(1,len(spec['parts'])+1))
    if len(data) != spec['bytes'] or hashlib.sha256(data).hexdigest() != spec['sha256']: fail('FILE_HASH_MISMATCH')
    target = root.joinpath(*name.split('/'))
    current = root
    for part in name.split('/')[:-1]:
        current = current/part
        if current.is_symlink(): fail('DESTINATION_HAS_SYMLINK')
        if current.exists() and not current.is_dir(): fail('DESTINATION_NOT_DIRECTORY')
    if target.exists() or target.is_symlink(): fail('REFUSE_OVERWRITE')
    # No destination writes before all content checks pass. No OS isolation claim.
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as stream: stream.write(data)
    if hashlib.sha256(target.read_bytes()).hexdigest() != spec['sha256']: fail('WRITTEN_HASH_MISMATCH')
    print('RESTORED_VERIFIED '+name)
    return target
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--expected', required=True, type=Path)
    parser.add_argument('mail',nargs='+',type=Path)
    args = parser.parse_args()
    try:
        global EXPECTED
        EXPECTED = load_expected(args.expected)
        restore(Path(args.root),args.mail)
    except (ValueError,OSError,UnicodeError,TypeError,KeyError):
        print('RESTORE_FAILED: check parts, framing, hash, paths and permissions; no payload executed.',file=sys.stderr)
        return 2
    return 0
if __name__ == '__main__': sys.exit(main())
