# codex-remote-sql — candidate components v0.1.2

[日本語 / Japanese](README_JA.md) · [Offline procedure (Japanese)](docs/OFFLINE_START_JA.md)

MIT-licensed experimental components for a shared SSH/Oracle tool design.
Python standard-library components validate tab-separated target settings,
collect metadata for explicitly selected local roots, parse CSV, and validate
SQL change-evidence JSONL. Windows PowerShell 5 candidate components write SQL
evidence and UTF-8 CSV bytes. This is **not a complete SSH or Oracle executor**.
Resolver, approval enforcement and complete credential/secret controls are not implemented.

## Local synthetic tests

From the repository root, with an existing Python 3 installation:

```sh
python3 -B -m unittest discover -s tests -p test_contracts.py -v
python3 -B -m unittest discover -s tests -p test_delivery.py -v
```

The maintainer's Linux environment passed 39 contract tests and 8 delivery tests.
Windows PowerShell 5 execution and real SSH/Oracle integration are **not verified**.
To test the synthetic logger on an allowed Windows PowerShell 5 environment:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -File tests/Test-CodexSqlEvidence.ps1
```

The CSV byte-boundary check requires WSL2, Windows PowerShell 5 interop and a
Windows-local shared drive containing the repository:

```sh
python3 -B tests/test_ps5_csv_boundary.py
```

It derives the Windows fixture path using `wslpath`, rather than requiring a
particular workplace directory. Missing runtime/interop is NOT_RUN, never PASS.
Do not bypass execution policy or install extra runtimes to make these checks pass.
The logger test uses its own temporary directory and fake SQL, without a database.

## Offline delivery

Download a **commit-pinned source ZIP** from this public repository, extract it
to a new local directory, and verify its files using `tools/verify_package.py`.
`PACKAGE_MANIFEST.json` lists every distributed file except itself. Compare its
SHA-256 to a separately supplied expected value before running the verifier.
The verifier detects listed-file corruption; it is not an authenticity or OS-isolation boundary.

`tools/restore_mail.py` restores optional private intake snapshots from raw email
bodies using a separately supplied expected manifest. It permits four fixed
intake paths, checks all chunks before writing, refuses overwrites and does not
execute restored content. Email content and the expected manifest must both be
checked by the recipient. It does not detect Windows junctions or synchronization
destinations; the operator must check these. Private snapshots are not included here.

`reports/RETURN_REPORT_TEMPLATE.html` is a static four-page Japanese summary
template. Fill a local copy and confirm the actual print preview stays within four
A4 pages; overflow is possible. It has no external resources, forms or scripts.

## Limits and contribution

The logger persists the supplied SQL text. Its basic rejection of some secret-like
strings is **not complete secret redaction**. Do not use business SQL, credentials,
real hosts or production logs in the included fixtures, issue reports or pull requests.
Passing mock tests does not authorize database access or production installation.
Use explicit file paths during evaluation; no PATH/profile/module installation is required.

For public generic improvements, create a branch, run the relevant local tests,
open a pull request, review the diff and validation, and merge it. Keep private
deployment configuration outside this repository. Releases, automated CI and
complete integration coverage are not currently provided.

See [LICENSE](LICENSE). Documentation language does not change the MIT license.
