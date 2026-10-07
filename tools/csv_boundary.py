"""Parse an explicit UTF-8 CSV stream from PS5. No split(',') shortcuts."""
import csv
import io
import sys


def read_rows(binary_stream):
    text = io.TextIOWrapper(binary_stream, encoding='utf-8-sig', newline='')
    try:
        rows = list(csv.reader(text, strict=True))
        if rows and any(len(row) != len(rows[0]) for row in rows[1:]):
            raise csv.Error('inconsistent CSV column count')
        return rows
    finally:
        text.detach()


if __name__ == '__main__':
    # Summary only: acquired DB values may be sensitive.
    try:
        rows = read_rows(sys.stdin.buffer)
        import json
        print(json.dumps({'rows_including_header': len(rows),
                          'columns': len(rows[0]) if rows else 0}))
    except (UnicodeError, csv.Error):
        print('{"error":"INVALID_UTF8_CSV"}', file=sys.stderr)
        raise SystemExit(2)
