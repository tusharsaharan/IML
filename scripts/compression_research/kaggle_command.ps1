param(
    [Parameter(Mandatory=$true)][string]$Script,
    [string[]]$ScriptArguments = @(),
    [string]$CredentialPath = "$env:LOCALAPPDATA\Temp\opencode\iml-kaggle-token.dpapi"
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$secret = (Get-Content -LiteralPath $CredentialPath -Raw).Trim() | ConvertTo-SecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $env:KAGGLE_API_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    & "$root\.venv\Scripts\python.exe" $Script @ScriptArguments
    $result = $LASTEXITCODE
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    Remove-Item Env:KAGGLE_API_TOKEN -ErrorAction SilentlyContinue
}
exit $result
