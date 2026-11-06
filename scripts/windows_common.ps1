# Shared Windows-native bootstrap. Does not install global packages or change execution policy.
Set-StrictMode -Version Latest

function Get-GuardianPython {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$GuardianRoot)

    $venvDir = Join-Path $GuardianRoot '.venv'
    $venvPython = Join-Path $venvDir 'Scripts\python.exe'
    $versionCheck = 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'

    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        & $venvPython -c $versionCheck *> $null
        if ($LASTEXITCODE -eq 0) {
            return (Resolve-Path -LiteralPath $venvPython).Path
        }
        throw 'Existing .venv uses an unsupported Python version. Rename .venv and retry.'
    }

    $candidates = @(
        @{ Name='py'; Arguments=@('-3') },
        @{ Name='python'; Arguments=@() },
        @{ Name='python3'; Arguments=@() }
    )
    foreach ($candidate in $candidates) {
        $command = Get-Command -Name $candidate.Name -ErrorAction SilentlyContinue
        if ($null -eq $command) { continue }
        $prefix = @($candidate.Arguments)
        try {
            & $command.Source @prefix -c $versionCheck *> $null
            if ($LASTEXITCODE -ne 0) { continue }
            Write-Host 'Creating isolated .venv (offline, no pip install)...'
            & $command.Source @prefix -m venv $venvDir
            if ($LASTEXITCODE -ne 0) { throw 'venv creation failed.' }
            if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
                throw 'venv Python executable was not created.'
            }
            return (Resolve-Path -LiteralPath $venvPython).Path
        } catch {
            Write-Verbose ('Python candidate failed: ' + $candidate.Name)
        }
    }
    throw 'Python 3.11+ is required. Install from https://www.python.org/downloads/windows/ and restart PowerShell.'
}
