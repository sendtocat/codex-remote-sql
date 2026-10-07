"""Office-only PS5 byte-boundary check with synthetic data. No SSH/DB."""
import io
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if str(root) != '/mnt/c/for_agent/myssh_and_db/candidate-v0.1.1':
    raise SystemExit('NOT_RUN: PROJECT_PATH_MISMATCH')
exe = Path('/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')
if not exe.is_file():
    raise SystemExit('NOT_RUN: WINDOWS_PS_NOT_AVAILABLE')
sys.path.insert(0, str(root / 'tools'))
from csv_boundary import read_rows

try:
    result = subprocess.run(
        [str(exe), '-NoLogo', '-NoProfile', '-NonInteractive', '-File',
         r'C:\for_agent\myssh_and_db\candidate-v0.1.1\tests\Emit-MockCsv.ps1'],
        cwd=root, capture_output=True, timeout=30, check=False)
except subprocess.TimeoutExpired:
    raise SystemExit('FAIL: PS5_TIMEOUT')
except OSError:
    raise SystemExit('NOT_RUN: WINDOWS_PS_LAUNCH_FAILED')
if result.returncode != 0:
    raise SystemExit('FAIL: PS5_PROCESS_FAILED')
if result.stderr.strip():
    raise SystemExit('FAIL: UNEXPECTED_STDERR')
try:
    rows = read_rows(io.BytesIO(result.stdout))
except Exception:
    raise SystemExit('FAIL: CSV_DECODE_FAILED')
expected = [['name', 'value'], ['日本語', 'a,b\t"c"\r\nd']]
if rows != expected:
    raise SystemExit('FAIL: CSV_CONTENT_MISMATCH')
print('CSV_BOUNDARY_PASS: synthetic PS5 -> UTF-8 bytes -> WSL/Python')
