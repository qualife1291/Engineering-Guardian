# Native Windows launcher used by Start Engineering Guardian.cmd.
[CmdletBinding()]
param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
. (Join-Path $PSScriptRoot 'windows_common.ps1')
$guardianRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Get-GuardianPython -GuardianRoot $guardianRoot

Write-Host ('Python: ' + $python)
Push-Location -LiteralPath $guardianRoot
try {
    & $python -m compileall -q ucg scripts
    if ($LASTEXITCODE -ne 0) { throw 'Python compile check failed.' }
    Write-Host 'Engineering Guardian Python compile check: PASS'
    if ($CheckOnly) {
        Write-Host 'Windows bootstrap: PASS (interactive menu not started).'
        return
    }
    & $python (Join-Path $guardianRoot 'scripts\guardian_menu.py')
    if ($LASTEXITCODE -ne 0) { throw 'Guardian menu exited with an error.' }
} finally {
    Pop-Location
}
