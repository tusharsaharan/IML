param(
    [Parameter(Mandatory=$true)][string]$State,
    [ValidateSet('check','run')][string]$Mode = 'check'
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'kaggle_command.ps1') `
    -Script (Join-Path $PSScriptRoot 'overnight_monitor.py') `
    -ScriptArguments @($Mode, '--state', $State)
exit $LASTEXITCODE
