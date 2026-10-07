"""Offline helpers only: no SSH, database connection, or secret-file reads."""
import argparse
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

ENVIRONMENTS = {"dev", "aws_dev", "prod", "aws_prod"}
TARGET_COLUMNS = ("target_alias", "login_alias", "switch_method", "switch_user",
                  "environment", "policy", "role", "os")
SECRET_NAME = re.compile(r"password|passwd|credential|secret|token|(^|[_.-])id_(rsa|dsa|ecdsa|ed25519)([_.-]|$)|\.(pem|key|pfx|p12)$", re.I)


class ContractError(ValueError):
    """Messages never include source field values or SQL text."""


def parse_cfg(text, columns):
    """Fixed-width TAB records. Exact key comparison; no trimming of data."""
    if columns < 1:
        raise ContractError("invalid column count")
    if text.startswith('\ufeff'):
        text = text[1:]
    rows, seen = [], set()
    for number, line in enumerate(text.split('\n'), 1):
        # Support LF/CRLF, rejecting lone embedded CR instead of splitting it.
        if line.endswith('\r'):
            line = line[:-1]
        if line == '' or line.startswith('#'):
            continue
        if '\r' in line or '\x00' in line:
            raise ContractError('line %d: unsupported control character' % number)
        fields = line.split('\t')
        if len(fields) != columns:
            raise ContractError('line %d: wrong column count' % number)
        if not fields[0] or fields[0].strip() != fields[0]:
            raise ContractError('line %d: invalid key' % number)
        if fields[0] in seen:
            raise ContractError('line %d: duplicate key' % number)
        seen.add(fields[0])
        rows.append(fields)
    return rows


def validate_targets(rows):
    """Draft target semantics; this is a validator, not a connection resolver."""
    result = []
    for number, fields in enumerate(rows, 1):
        if len(fields) != len(TARGET_COLUMNS):
            raise ContractError('record %d: wrong column count' % number)
        r = dict(zip(TARGET_COLUMNS, fields))
        env = r['environment']
        if env not in ENVIRONMENTS or r['policy'] not in {'dev', 'prod'}:
            raise ContractError('record %d: environment/policy mismatch' % number)
        # Explicit policy stays separate. Production cannot weaken its approval floor.
        if env in {'prod', 'aws_prod'} and r['policy'] != 'prod':
            raise ContractError('record %d: production policy cannot be weakened' % number)
        for field in ('target_alias', 'login_alias'):
            if not re.fullmatch(re.escape(env) + r'_[a-zA-Z0-9]+_[a-zA-Z0-9][a-zA-Z0-9_.-]*', r[field]):
                raise ContractError('record %d: alias/environment mismatch' % number)
        if r['switch_method'] not in {'none', 'sudo', 'su'}:
            raise ContractError('record %d: invalid switch method' % number)
        if r['switch_method'] == 'none':
            if r['switch_user'] or r['target_alias'] != r['login_alias']:
                raise ContractError('record %d: inconsistent direct login' % number)
        elif not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_.-]*', r['switch_user']):
            raise ContractError('record %d: invalid switch user' % number)
        if not r['role'] or not r['os']:
            raise ContractError('record %d: missing role/OS' % number)
        result.append(r)
    return result


def read_targets(path):
    p = Path(path)
    if p.suffix != '.cfg' or SECRET_NAME.search(p.name):
        raise ContractError('not a non-secret target .cfg')
    try:
        if p.is_symlink():
            raise ContractError('symlink target config is not accepted')
        text = p.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError):
        raise ContractError('target config cannot be read as UTF-8') from None
    return validate_targets(parse_cfg(text, len(TARGET_COLUMNS)))


def inventory_roots(roots):
    """Metadata only, explicit roots, no content reads, no symlink traversal."""
    entries = []
    for root in roots:
        p = Path(os.path.abspath(root))
        try:
            mode = p.lstat().st_mode
            if stat.S_ISLNK(mode):
                entries.append({'path': str(p), 'status': 'SYMLINK_NOT_FOLLOWED'})
                continue
        except FileNotFoundError:
            entries.append({'path': str(p), 'status': 'PATH_NOT_FOUND_ON_THIS_MACHINE'})
            continue
        except OSError:
            entries.append({'path': str(p), 'status': 'ACCESS_UNAVAILABLE'})
            continue
        queue = [p]
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            entries.append({'path': str(p), 'status': 'SPECIAL_FILE_NOT_READ'})
            continue
        while queue:
            item = queue.pop()
            try:
                info = item.lstat()
                if item.is_symlink():
                    status = 'SYMLINK_NOT_FOLLOWED'
                elif item.name in {'.git', 'node_modules', '__pycache__'}:
                    status = 'EXCLUDED_DIRECTORY'
                elif SECRET_NAME.search(item.name):
                    status = 'SECRET_NAMED_CONTENT_NOT_READ'
                elif stat.S_ISDIR(info.st_mode):
                    entries.append({'path': str(item), 'status': 'DIRECTORY_METADATA_ONLY'})
                    queue.extend(sorted(item.iterdir(), reverse=True))
                    continue
                elif stat.S_ISREG(info.st_mode):
                    status = 'FILE_METADATA_ONLY'
                else:
                    status = 'SPECIAL_FILE_NOT_READ'
                entries.append({'path': str(item), 'status': status, 'size': info.st_size,
                                'mtime_ns': info.st_mtime_ns})
            except OSError:
                entries.append({'path': str(item), 'status': 'ACCESS_UNAVAILABLE'})
    return {'schema_version': 1, 'scope': 'explicit local roots only',
            'content_read': False, 'entries': entries}


def verify_evidence(text):
    """Explicit sensitive-log input; output contains counts and locations only."""
    starts, results, issues, warnings = {}, {}, [], []
    def unique_object(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError('duplicate JSON key')
            output[key] = value
        return output
    source_lines = text.split('\n')
    for line_number, line in enumerate(source_lines, 1):
        if line == '' and line_number == len(source_lines):
            continue
        try:
            record = json.loads(line, object_pairs_hook=unique_object)
            if not isinstance(record, dict):
                raise ValueError()
            eid = record['execution_id']
            if not isinstance(eid, str) or not re.fullmatch(r'[a-f0-9]{32}', eid):
                raise ValueError()
            phase = record['event']
            when = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
            if when.tzinfo is None or type(record['schema_version']) is not int or record['schema_version'] != 1:
                raise ValueError()
            if phase == 'START':
                if eid in starts or eid in results:
                    raise ValueError()
                if record['environment'] not in ENVIRONMENTS:
                    raise ValueError()
                if record['operation_kind'] not in {'DML', 'DDL', 'PLSQL', 'PRIVILEGE', 'UNKNOWN'}:
                    raise ValueError()
                for field in ('target', 'db_user', 'tool', 'version', 'sql_text'):
                    if not isinstance(record[field], str) or not record[field]:
                        raise ValueError()
                if record['sql_hash'] != hashlib.sha256(record['sql_text'].encode('utf-8')).hexdigest():
                    raise ValueError()
                starts[eid] = (record, when)
            elif phase == 'RESULT':
                if eid not in starts or eid in results:
                    raise ValueError()
                if record['status'] not in {'SUCCESS', 'ERROR', 'CANCELLED', 'OUTCOME_UNKNOWN'}:
                    raise ValueError()
                if record['transaction'] not in {'UNKNOWN', 'COMMIT_CONFIRMED', 'ROLLBACK_CONFIRMED', 'NOT_APPLICABLE'}:
                    raise ValueError()
                for field in ('affected_rows', 'oracle_error_code'):
                    if record[field] is not None and type(record[field]) is not int:
                        raise ValueError()
                if when < starts[eid][1]:
                    # Wall clock correction alone does not prove a broken event sequence.
                    warnings.append({'line': line_number, 'warning': 'WALL_CLOCK_MOVED_BACKWARD'})
                results[eid] = record
            else:
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError):
            issues.append({'line': line_number, 'issue': 'INVALID_RECORD_OR_SEQUENCE'})
    if not starts and not results and not issues:
        issues.append({'line': 0, 'issue': 'EMPTY_EVIDENCE'})
    incomplete = len(set(starts) - set(results))
    unknown_outcomes = sum(r['status'] == 'OUTCOME_UNKNOWN' for r in results.values())
    status = ('INVALID' if issues else 'INCOMPLETE' if incomplete else
              'REVIEW_REQUIRED' if unknown_outcomes or warnings else 'STRUCTURALLY_COMPLETE')
    return {'starts': len(starts), 'results': len(results),
            'incomplete': incomplete, 'unknown_outcomes': unknown_outcomes,
            'validation_status': status, 'issues': issues, 'warnings': warnings,
            'interpretation': 'START alone does not prove DB execution; RESULT SUCCESS does not imply COMMIT'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    config = sub.add_parser('validate-targets')
    config.add_argument('path')
    inventory = sub.add_parser('inventory')
    inventory.add_argument('--root', action='append', required=True)
    evidence = sub.add_parser('verify-evidence')
    evidence.add_argument('path', help='sensitive JSONL; run locally, do not paste contents to models')
    args = parser.parse_args()
    try:
        if args.command == 'validate-targets':
            data = {'valid': True, 'target_count': len(read_targets(args.path))}
        elif args.command == 'inventory':
            data = inventory_roots(args.root)
        else:
            data = verify_evidence(Path(args.path).read_text(encoding='utf-8-sig'))
        print(json.dumps(data, ensure_ascii=False))
        if data.get('issues'):
            return 1
        if data.get('incomplete'):
            return 3
        if data.get('unknown_outcomes') or data.get('warnings'):
            return 4
        return 0
    except (ContractError, OSError, UnicodeError) as exc:
        # Deliberately do not stringify arbitrary IO/Unicode exceptions.
        message = str(exc) if isinstance(exc, ContractError) else 'input cannot be read'
        print(json.dumps({'error': message}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
