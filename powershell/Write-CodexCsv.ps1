#requires -Version 5.0
# Candidate UTF-8 byte output boundary for a dedicated powershell.exe process.
# This writes stdout bytes directly, not PowerShell pipeline objects.
param([Parameter(Mandatory=$true)][AllowEmptyCollection()][object[]]$Rows)
$ErrorActionPreference = 'Stop'
$encoding = New-Object System.Text.UTF8Encoding -ArgumentList @($false, $true)
$writer = New-Object System.IO.StreamWriter -ArgumentList @([Console]::OpenStandardOutput(), $encoding, 4096, $true)
try {
    $Rows | ConvertTo-Csv -NoTypeInformation | ForEach-Object { $writer.WriteLine([string]$_) }
    $writer.Flush()
} finally {
    $writer.Dispose()
}
