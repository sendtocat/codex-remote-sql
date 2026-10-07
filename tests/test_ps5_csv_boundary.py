"""Office-only PS5 byte-boundary check with synthetic data. No SSH/DB."""
import io
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
exe = Path('/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')
if not exe.is_file():
    raise SystemExit('NOT_RUN: WINDOWS_PS_NOT_AVAILABLE')
try:
    emitter = subprocess.run(['wslpath', '-w', str(root / 'tests/Emit-MockCsv.ps1')],
                             capture_output=True, text=True, timeout=5, check=True).stdout.strip()
except (OSError, subprocess.SubprocessError):
    raise SystemExit('NOT_RUN: WSLPATH_UNAVAILABLE')
# Use a Windows-local shared drive, not a UNC WSL path.
if len(emitter) < 3 or not emitter[0].isalpha() or emitter[1:3] != ':\\':
    raise SystemExit('NOT_RUN: WINDOWS_SHARED_DRIVE_REQUIRED')
sys.path.insert(0, str(root / 'tools'))
from csv_boundary import read_rows

try:
    result = subprocess.run(
        [str(exe), '-NoLogo', '-NoProfile', '-NonInteractive', '-File',
         emitter],
        cwd=root, capture_output=True, timeout=30, check=False)
except subprocess.TimeoutExpired:
    raise SystemExit('FAIL: PS5_TIMEOUT')
except OSError:
    raise SystemExit('NOT_RUN: WINDOWS_PS_LAUNCH_FAILED')
if result.returncode == 3:
    raise SystemExit('NOT_RUN: WINDOWS_POWERSHELL_5_REQUIRED')
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
