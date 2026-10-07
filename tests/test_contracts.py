import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common_contracts import (ContractError, inventory_roots, parse_cfg,
                              read_targets, validate_targets, verify_evidence)
from csv_boundary import read_rows


def records(sql="update demo set value='日本語,\"quoted\"\nnext\tline'", kind='DML'):
    eid = 'a' * 32
    start = {'schema_version': 1, 'event': 'START', 'execution_id': eid,
             'timestamp': '2026-10-07T16:30:00Z', 'environment': 'aws_dev',
             'target': 'aws_dev_mock', 'db_user': 'mock_user',
             'tool': 'mock_logger', 'version': '0.1.1-fixture',
             'operation_kind': kind, 'sql_text': sql,
             'sql_hash': hashlib.sha256(sql.encode('utf-8')).hexdigest()}
    result = {'schema_version': 1, 'event': 'RESULT', 'execution_id': eid,
              'timestamp': '2026-10-07T16:30:01Z', 'status': 'SUCCESS',
              'affected_rows': None, 'oracle_error_code': None,
              'transaction': 'UNKNOWN'}
    return start, result


def lines(*items):
    return '\n'.join(json.dumps(i, ensure_ascii=False) for i in items) + '\n'


class ConfigTests(unittest.TestCase):
    def test_comments_and_data_hash(self):
        self.assertEqual(parse_cfg('# comment\n\nkey\tvalue#data\n', 2), [['key', 'value#data']])

    def test_bom_crlf_empty_field(self):
        self.assertEqual(parse_cfg('\ufeffkey\t\r\n', 2), [['key', '']])

    def test_no_whitespace_comment_silently_ignored(self):
        with self.assertRaises(ContractError):
            parse_cfg(' #comment\n', 2)

    def test_duplicate_key(self):
        with self.assertRaises(ContractError):
            parse_cfg('key\ta\nkey\tb\n', 2)

    def test_extra_tabs_not_ignored(self):
        with self.assertRaises(ContractError):
            parse_cfg('key\ta\tb', 2)

    def test_embedded_cr_rejected(self):
        with self.assertRaises(ContractError):
            parse_cfg('key\tval\rue', 2)

    def test_errors_do_not_print_values(self):
        with self.assertRaises(ContractError) as ctx:
            parse_cfg('sensitive-key\tsensitive-value\textra', 2)
        self.assertNotIn('sensitive', str(ctx.exception))

    def test_examples(self):
        path = Path(__file__).resolve().parents[1] / 'examples' / 'targets.example.cfg'
        self.assertEqual(len(read_targets(path)), 3)

    def test_policy_environment_disagreement(self):
        with self.assertRaises(ContractError):
            validate_targets([['prod_dbux6_a','prod_dbux6_a','none','','prod','dev','DBUX6','Solaris']])

    def test_dev_environment_accepts_stricter_policy(self):
        rows=[['dev_dbux6_a','dev_dbux6_a','none','','dev','prod','DBUX6','unknown']]
        self.assertEqual(validate_targets(rows)[0]['policy'], 'prod')

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ContractError):
            validate_targets([['dev_dbux6_a','dev_dbux6_a','none','','dev','invalid','DBUX6','unknown']])

    def test_alias_environment_disagreement(self):
        with self.assertRaises(ContractError):
            validate_targets([['aws_dev_dbux6_a','dev_dbux6_a','sudo','a','aws_dev','dev','DBUX6','Linux']])

    def test_switch_not_inferred(self):
        with self.assertRaises(ContractError):
            validate_targets([['dev_dbux6_a','dev_dbux6_a','none','b','dev','dev','DBUX6','unknown']])

    def test_secret_named_config_refused_without_read(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('must not read')):
            with self.assertRaises(ContractError):
                read_targets('myssh-passwords.cfg')

    def test_symlink_target_config_not_read(self):
        with tempfile.TemporaryDirectory() as folder:
            secret = Path(folder)/'myssh-passwords.cfg'
            secret.write_text('mock secret only')
            link = Path(folder)/'targets.cfg'
            link.symlink_to(secret)
            with patch.object(Path, 'read_text', side_effect=AssertionError('must not read')):
                with self.assertRaises(ContractError):
                    read_targets(link)


class InventoryTests(unittest.TestCase):
    def test_metadata_only_and_secret_exclusion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'helper.sh').write_text('do not read me')
            (root/'myssh-passwords.cfg').write_text('mock secret only')
            (root/'password-cache').mkdir()
            (root/'password-cache'/'child').write_text('mock only')
            (root/'.git').mkdir()
            (root/'.git'/'config').write_text('mock')
            with patch.object(Path, 'read_text', side_effect=AssertionError('no content reads')), \
                 patch.object(Path, 'read_bytes', side_effect=AssertionError('no content reads')):
                output = inventory_roots([root])
            states = {Path(e['path']).name:e['status'] for e in output['entries']}
            self.assertEqual(states['helper.sh'], 'FILE_METADATA_ONLY')
            self.assertEqual(states['myssh-passwords.cfg'], 'SECRET_NAMED_CONTENT_NOT_READ')
            self.assertNotIn('child', states)
            self.assertNotIn('config', states)
            self.assertFalse(output['content_read'])

    def test_symlink_outside_root_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'root'
            root.mkdir()
            (Path(folder)/'outside').mkdir()
            (Path(folder)/'outside'/'should-not-appear').write_text('mock')
            (root/'link').symlink_to(Path(folder)/'outside', target_is_directory=True)
            output = inventory_roots([root])
            self.assertTrue(any(e['status']=='SYMLINK_NOT_FOLLOWED' for e in output['entries']))
            self.assertFalse(any('should-not-appear' in e['path'] for e in output['entries']))

    def test_missing_is_scoped_to_machine(self):
        with tempfile.TemporaryDirectory() as folder:
            output = inventory_roots([Path(folder)/'missing'])
            self.assertEqual(output['entries'][0]['status'], 'PATH_NOT_FOUND_ON_THIS_MACHINE')

    def test_access_failure(self):
        with patch.object(Path, 'stat', side_effect=PermissionError):
            output = inventory_roots(['restricted-root'])
        self.assertEqual(output['entries'][0]['status'], 'ACCESS_UNAVAILABLE')


class EvidenceTests(unittest.TestCase):
    def test_roundtrip_sql_quote_tab_newline_unicode(self):
        a,b = records()
        text=lines(a,b)
        self.assertEqual(json.loads(text.splitlines()[0])['sql_text'], a['sql_text'])
        result=verify_evidence(text)
        self.assertEqual((result['starts'], result['results'], result['incomplete']), (1,1,0))
        self.assertEqual(result['issues'], [])

    def test_interrupted_start_retained(self):
        a,_=records()
        output=verify_evidence(lines(a))
        self.assertEqual(output['incomplete'],1)
        self.assertEqual(output['issues'],[])

    def test_result_without_start_is_not_accepted(self):
        _,b=records()
        self.assertTrue(verify_evidence(lines(b))['issues'])

    def test_duplicate_result(self):
        a,b=records()
        self.assertTrue(verify_evidence(lines(a,b,b))['issues'])

    def test_invalid_hash(self):
        a,_=records()
        a['sql_text']+='changed'
        self.assertTrue(verify_evidence(lines(a))['issues'])

    def test_truncated_line_is_reported(self):
        a,_=records()
        result=verify_evidence(lines(a)+'{"event":')
        self.assertEqual(result['incomplete'],1)
        self.assertEqual(result['issues'][0]['line'],2)

    def test_select_excluded(self):
        a,_=records(kind='SELECT')
        self.assertTrue(verify_evidence(lines(a))['issues'])

    def test_unknown_is_logged(self):
        a,b=records(kind='UNKNOWN')
        self.assertEqual(verify_evidence(lines(a,b))['issues'],[])

    def test_clock_correction_requires_review_not_corruption_claim(self):
        a,b=records()
        b['timestamp']='2026-10-07T16:29:59Z'
        result=verify_evidence(lines(a,b))
        self.assertEqual(result['issues'], [])
        self.assertEqual(result['validation_status'], 'REVIEW_REQUIRED')
        self.assertTrue(result['warnings'])

    def test_empty_evidence_is_invalid(self):
        self.assertEqual(verify_evidence('')['validation_status'], 'INVALID')

    def test_missing_start_metadata_is_invalid(self):
        a,_=records()
        del a['target']
        self.assertTrue(verify_evidence(lines(a))['issues'])

    def test_duplicate_json_property_is_invalid(self):
        a,_=records()
        text=json.dumps(a)[:-1]+',"event":"START"}\n'
        self.assertTrue(verify_evidence(text)['issues'])

    def test_boolean_schema_version_is_invalid(self):
        a,_=records()
        a['schema_version']=True
        self.assertTrue(verify_evidence(lines(a))['issues'])

    def test_unknown_db_outcome_requires_review(self):
        a,b=records()
        b['status']='OUTCOME_UNKNOWN'
        result=verify_evidence(lines(a,b))
        self.assertEqual(result['unknown_outcomes'],1)
        self.assertEqual(result['validation_status'],'REVIEW_REQUIRED')

    def test_evidence_cli_exit_codes(self):
        a,b=records()
        cases=[(lines(a,b),0),(lines(a),3),('',1)]
        b['status']='OUTCOME_UNKNOWN'
        cases.append((lines(a,b),4))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'mock.runtime.jsonl'
            for contents,expected in cases:
                path.write_text(contents,encoding='utf-8')
                result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'tools/common_contracts.py'),'verify-evidence',str(path)],capture_output=True,text=True)
                self.assertEqual(result.returncode,expected)
                self.assertNotIn(a['sql_text'],result.stdout+result.stderr)

    def test_summary_does_not_expose_sql(self):
        a,b=records()
        self.assertNotIn(a['sql_text'],json.dumps(verify_evidence(lines(a,b))))


class CsvTests(unittest.TestCase):
    def test_utf8_csv_bom_crlf_quotes_embedded_newline(self):
        rows=[['name','value'],['日本語','a,b\t"c"\r\nd']]
        output=io.StringIO(newline='')
        csv.writer(output,lineterminator='\r\n').writerows(rows)
        self.assertEqual(read_rows(io.BytesIO(output.getvalue().encode('utf-8-sig'))),rows)

    def test_bad_utf8_rejected(self):
        with self.assertRaises(UnicodeError):
            read_rows(io.BytesIO(b'\xff'))

    def test_unclosed_quote_rejected(self):
        with self.assertRaises(csv.Error):
            read_rows(io.BytesIO(b'"never closed'))

    def test_wrong_column_count_rejected(self):
        with self.assertRaises(csv.Error):
            read_rows(io.BytesIO(b'a,b\nonly_one\n'))


if __name__=='__main__':
    unittest.main()
