#requires -Version 5.0
# Additive logging component only. No Oracle provider or DB executor is installed.
# Not PS5-tested in Work. Mock tests alone do not qualify this for deployment.
# Data use also requires reviewed resolver/approval/secret controls and integration tests.
Set-StrictMode -Version 2.0
$script:CodexSqlOpenRecords = @{}
$script:CodexSqlUtf8 = New-Object System.Text.UTF8Encoding -ArgumentList @($false, $true)
$ExecutionContext.SessionState.Module.OnRemove = {
    foreach ($stream in $script:CodexSqlOpenRecords.Values) { $stream.Dispose() }
    $script:CodexSqlOpenRecords.Clear()
}

function Write-CodexSqlRecord {
    param($Stream, $Record)
    $json = ConvertTo-Json -InputObject $Record -Depth 8 -Compress
    $bytes = $script:CodexSqlUtf8.GetBytes($json + "`n")
    $Stream.Write($bytes, 0, $bytes.Length)
    $Stream.Flush($true)
}

function Get-CodexSqlLogRoot {
    if (Test-Path Env:CODEX_SQL_LOG_DIR) {
        $root = $env:CODEX_SQL_LOG_DIR
        if ([string]::IsNullOrWhiteSpace($root)) { throw 'SQL_LOG_ROOT_EMPTY' }
    } else {
        $root = 'C:\CodexSqlLog'
    }
    if (-not [System.IO.Path]::IsPathRooted($root)) { throw 'SQL_LOG_ROOT_NOT_ABSOLUTE' }
    $pathRoot = [System.IO.Path]::GetPathRoot($root)
    if ($pathRoot -match '^[A-Za-z]:$' -or $pathRoot -eq '\' -or $pathRoot -eq '/') { throw 'SQL_LOG_ROOT_NOT_FULLY_QUALIFIED' }
    return $root
}

function Start-CodexSqlEvidence {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$Target,
        [Parameter(Mandatory=$true)][ValidateSet('dev','aws_dev','prod','aws_prod')][string]$Environment,
        [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$DbUser,
        [Parameter(Mandatory=$true)][ValidateSet('DML','DDL','PLSQL','PRIVILEGE','UNKNOWN')][string]$OperationKind,
        [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$Sql
    )
    # Draft fail-closed guard for obvious authentication SQL. Not a secret scanner.
    # Credential-setting SQL must use a separately reviewed flow; never log passwords.
    if ($Sql -match '(?i)\bidentified\s+by\b|\bpassword\b') { throw 'SQL_AUTH_SECRET_REVIEW_REQUIRED' }
    $root = Get-CodexSqlLogRoot
    $eid = [Guid]::NewGuid().ToString('N')
    $stream = $null
    $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hashBytes = $hashAlgorithm.ComputeHash($script:CodexSqlUtf8.GetBytes($Sql))
        $hash = [BitConverter]::ToString($hashBytes).Replace('-','').ToLowerInvariant()
    } finally { $hashAlgorithm.Dispose() }
    try {
        $directory = [System.IO.Path]::Combine($root, $Environment.ToLowerInvariant())
        [void][System.IO.Directory]::CreateDirectory($directory)
        $path = [System.IO.Path]::Combine($directory, $eid + '.runtime.jsonl')
        $stream = New-Object System.IO.FileStream -ArgumentList @(
            $path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
        $record = [ordered]@{
            schema_version = 1
            event = 'START'
            timestamp = [DateTime]::UtcNow.ToString('o')
            execution_id = $eid
            environment = $Environment.ToLowerInvariant()
            target = $Target
            db_user = $DbUser
            operation_kind = $OperationKind.ToUpperInvariant()
            sql_text = $Sql
            sql_hash = $hash
            tool = 'CodexSqlEvidence'
            version = '0.1.1-candidate'
        }
        Write-CodexSqlRecord -Stream $stream -Record $record
        $script:CodexSqlOpenRecords[$eid] = $stream
        # No SQL/credentials in the returned descriptor.
        return [pscustomobject]@{ ExecutionId = $eid; LogPath = $path }
    } catch {
        if ($null -ne $stream) { $stream.Dispose() }
        throw 'SQL_LOG_START_FAILED_EXECUTION_MUST_NOT_BEGIN'
    }
}

function Complete-CodexSqlEvidence {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{32}$')][string]$ExecutionId,
        [Parameter(Mandatory=$true)][ValidateSet('SUCCESS','ERROR','CANCELLED','OUTCOME_UNKNOWN')][string]$Status,
        [Nullable[long]]$AffectedRows = $null,
        [Nullable[int]]$OracleErrorCode = $null,
        [ValidateSet('UNKNOWN','COMMIT_CONFIRMED','ROLLBACK_CONFIRMED','NOT_APPLICABLE')][string]$Transaction = 'UNKNOWN'
    )
    $ExecutionId = $ExecutionId.ToLowerInvariant()
    if (-not $script:CodexSqlOpenRecords.ContainsKey($ExecutionId)) { throw 'SQL_LOG_UNKNOWN_OR_COMPLETED_EXECUTION' }
    $stream = $script:CodexSqlOpenRecords[$ExecutionId]
    try {
        $record = [ordered]@{
            schema_version = 1
            event = 'RESULT'
            timestamp = [DateTime]::UtcNow.ToString('o')
            execution_id = $ExecutionId
            status = $Status.ToUpperInvariant()
            affected_rows = $AffectedRows
            oracle_error_code = $OracleErrorCode
            transaction = $Transaction.ToUpperInvariant()
        }
        Write-CodexSqlRecord -Stream $stream -Record $record
    } catch {
        # Do not retry the DB request. An exception here does not undo a DB change.
        throw 'SQL_LOG_RESULT_FAILED_DB_OUTCOME_REQUIRES_RECONCILIATION'
    } finally {
        $stream.Dispose()
        $script:CodexSqlOpenRecords.Remove($ExecutionId)
    }
}

Export-ModuleMember -Function Start-CodexSqlEvidence, Complete-CodexSqlEvidence, Get-CodexSqlLogRoot
