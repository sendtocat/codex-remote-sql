#requires -Version 5.0
# Dedicated child process only; synthetic CSV, no database, no SSH.
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'PS5_REQUIRED' }
$root = Split-Path -Parent $PSScriptRoot
$name = [string][char]0x65E5 + [char]0x672C + [char]0x8A9E
$rows = @([pscustomobject][ordered]@{name=$name; value="a,b`t`"c`"`r`nd"})
& (Join-Path $root 'powershell\Write-CodexCsv.ps1') -Rows $rows
