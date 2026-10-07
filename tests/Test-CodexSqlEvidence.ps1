#requires -Version 5.0
# Mock/local only: no SQL or SSH connection is performed.
# Run under Windows PowerShell 5 with -NoProfile, not under an agent-wide profile.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$projectRoot = Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $projectRoot 'powershell\CodexSqlEvidence.psm1') -Force
$originalEnvExists = Test-Path Env:CODEX_SQL_LOG_DIR
$originalEnv = $env:CODEX_SQL_LOG_DIR
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('codex-sql-mock-' + [Guid]::NewGuid().ToString('N'))
function Assert-True { param($Condition, [string]$Message) if (-not $Condition) { throw $Message } }
try {
    Remove-Item Env:CODEX_SQL_LOG_DIR -ErrorAction SilentlyContinue
    Assert-True ((Get-CodexSqlLogRoot) -eq 'C:\CodexSqlLog') 'fallback root'
    $env:CODEX_SQL_LOG_DIR = 'C:drive-relative-path'
    $denied = $false
    try { Get-CodexSqlLogRoot } catch { $denied = $true }
    Assert-True $denied 'drive-relative root must fail'
    $env:CODEX_SQL_LOG_DIR = $testRoot
    Assert-True ((Get-CodexSqlLogRoot) -eq $testRoot) 'environment root'
    $unicodeMock = [string][char]0x65E5 + [char]0x672C
    $sql = "update mock_table set mock_value='quote `" and tab `t and line `nnext $unicodeMock'"
    $item = Start-CodexSqlEvidence -Target dev_mock -Environment dev -DbUser mock_user -OperationKind DML -Sql $sql
    # START must be readable and durable before simulated execution begins.
    $firstBytes = [IO.File]::ReadAllBytes($item.LogPath)
    Assert-True (-not ($firstBytes.Length -ge 3 -and $firstBytes[0] -eq 239 -and $firstBytes[1] -eq 187 -and $firstBytes[2] -eq 191)) 'unexpected BOM'
    $start = Get-Content -LiteralPath $item.LogPath -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($start.event -eq 'START' -and $start.sql_text -eq $sql) 'START SQL roundtrip'
    Assert-True ($start.operation_kind -eq 'DML') 'kind'
    Complete-CodexSqlEvidence -ExecutionId $item.ExecutionId.ToUpperInvariant() -Status SUCCESS -AffectedRows 2
    $records = @(Get-Content -LiteralPath $item.LogPath -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json })
    Assert-True ($records.Count -eq 2 -and $records[1].transaction -eq 'UNKNOWN') 'RESULT must not infer COMMIT'
    Assert-True ($records[0].execution_id -ceq $records[1].execution_id) 'UUID representation must remain consistent'
    $denied = $false
    try { Complete-CodexSqlEvidence -ExecutionId $item.ExecutionId -Status SUCCESS } catch { $denied = $true }
    Assert-True $denied 'duplicate completion must fail'
    foreach ($kind in @('DDL','PLSQL','PRIVILEGE','UNKNOWN')) {
        $c = Start-CodexSqlEvidence -Target aws_dev_mock -Environment aws_dev -DbUser mock_user -OperationKind $kind -Sql 'mock statement'
        Complete-CodexSqlEvidence -ExecutionId $c.ExecutionId -Status ERROR -OracleErrorCode 942
        $r = @(Get-Content -LiteralPath $c.LogPath -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json })
        Assert-True ($r[1].oracle_error_code -eq 942) 'Oracle numeric error only'
    }
    $denied = $false
    try { Start-CodexSqlEvidence -Target dev_mock -Environment dev -DbUser mock_user -OperationKind SELECT -Sql 'select 1 from dual' } catch { $denied = $true }
    Assert-True $denied 'SELECT must be outside change evidence API'
    $denied = $false
    try { Start-CodexSqlEvidence -Target dev_mock -Environment dev -DbUser mock_user -OperationKind DDL -Sql 'create user example identified by mock_only' } catch { $denied = $true }
    Assert-True $denied 'obvious authentication SQL guard'
    # Root is deliberately an existing file to force START failure. No adapter invoked.
    $blockingFile = Join-Path $testRoot 'blocked-root'
    [IO.File]::WriteAllText($blockingFile,'mock')
    $env:CODEX_SQL_LOG_DIR = $blockingFile
    $denied = $false
    $simulatedExecutions = 0
    try {
        $c = Start-CodexSqlEvidence -Target dev_mock -Environment dev -DbUser mock_user -OperationKind DML -Sql 'mock update'
        $simulatedExecutions++
    } catch { $denied = $true }
    Assert-True ($denied -and $simulatedExecutions -eq 0) 'START failure must prevent adapter call'
    # Close the internal mock handle to inject RESULT I/O failure; never retry DB.
    $env:CODEX_SQL_LOG_DIR = $testRoot
    $c = Start-CodexSqlEvidence -Target dev_mock -Environment dev -DbUser mock_user -OperationKind DML -Sql 'mock update'
    & (Get-Module CodexSqlEvidence) { param($Id) $script:CodexSqlOpenRecords[$Id].Dispose() } $c.ExecutionId
    $denied = $false
    try { Complete-CodexSqlEvidence -ExecutionId $c.ExecutionId -Status SUCCESS } catch { $denied = $true }
    Assert-True $denied 'RESULT failure must be explicit'
    $r = @(Get-Content -LiteralPath $c.LogPath -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json })
    Assert-True ($r.Count -eq 1) 'RESULT failure preserves START'
    $c = Start-CodexSqlEvidence -Target dev_mock -Environment dev -DbUser mock_user -OperationKind DML -Sql 'mock update'
    # Interruption test: no RESULT generated, START persists after module removal.
    Remove-Module CodexSqlEvidence
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    $r = @(Get-Content -LiteralPath $c.LogPath -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json })
    Assert-True ($r.Count -eq 1 -and $r[0].event -eq 'START') 'interrupted START'
    Write-Output 'PASS: local PS5 mock assertions (no real DB/SSH)'
} finally {
    Remove-Module CodexSqlEvidence -ErrorAction SilentlyContinue
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    if ($originalEnvExists) { $env:CODEX_SQL_LOG_DIR = $originalEnv } else { Remove-Item Env:CODEX_SQL_LOG_DIR -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}
