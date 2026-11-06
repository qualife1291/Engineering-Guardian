# Register Engineering Guardian as a project-local read-only-source MCP server.
# Use on native Windows PowerShell, not inside WSL. Nothing is written to the app source.
[CmdletBinding()]
param(
    [Parameter(Position=0)][string]$ProjectPath = '.',
    [switch]$Yes
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'windows_common.ps1')

$guardianRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path -LiteralPath $ProjectPath -PathType Container)) {
    throw 'Project directory not found. Pass a real absolute folder path with -ProjectPath.'
}
$project = (Resolve-Path -LiteralPath $ProjectPath).Path
$python = Get-GuardianPython -GuardianRoot $guardianRoot
$entrypoint = Join-Path $guardianRoot 'scripts\guardian_mcp.py'
if (-not (Test-Path -LiteralPath $entrypoint -PathType Leaf)) {
    throw 'Guardian MCP entry point is missing.'
}
$claudeCommand = Get-Command -Name 'claude' -ErrorAction SilentlyContinue
if ($null -eq $claudeCommand) {
    throw 'Claude Code CLI was not found. Install Claude Code, open a new PowerShell window, and retry.'
}

Write-Host ''
Write-Host 'Engineering Guardian -> Claude Code (PROJECT-LOCAL)'
Write-Host ('Project : ' + $project)
Write-Host ('Guardian: ' + $guardianRoot)
Write-Host ('Python  : ' + $python)
Write-Host 'Source permissions: READ ONLY for the Guardian MCP tools.'
Write-Host 'Cache and diagnostic files are written outside the app under GUARDIAN_HOME.'
Write-Host 'Note: selected code snippets may be sent to the Claude model when requested.'
Write-Host 'Claude Code permissions for its other tools are independent of Guardian.'
Write-Host ''
if (-not $Yes) {
    $answer = Read-Host 'Register project-local MCP server? [y/N]'
    if ($answer -notmatch '^(y|yes)$') {
        Write-Host 'Cancelled; no Claude configuration changed.'
        return
    }
}

$registration = @(
    'mcp','add','--scope','local','--transport','stdio',
    'engineering-guardian','--',$python,$entrypoint,'--root',$project
)
Push-Location -LiteralPath $project
try {
    & claude @registration
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw 'Claude Code rejected the MCP registration. Check existing names using: claude mcp list'
    }
    & claude mcp list
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Write-Warning 'MCP was registered, but listing failed. Open Claude Code and inspect /mcp.'
    }
} finally {
    Pop-Location
}
Write-Host 'Done. Restart Claude Code in the target folder; use /mcp to verify the connection.'
