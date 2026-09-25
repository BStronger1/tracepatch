param([switch]$Replace)
$ErrorActionPreference = 'Stop'
$taskProject = Split-Path -Parent $PSScriptRoot
$taskEnvPath = Join-Path $taskProject '.env'
if ((Test-Path -LiteralPath $taskEnvPath) -and -not $Replace) {
    throw 'A .env file already exists. Edit it locally instead of overwriting it.'
}
Write-Host 'If Ctrl+V does not paste in this terminal, use right-click Paste. Input stays hidden.'
$taskSecureKey = Read-Host 'Paste only the DMXAPI sk- key, then press Enter (input hidden)' -AsSecureString
$taskKeyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($taskSecureKey)
try {
    $taskPlainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($taskKeyPointer).Trim()
    if ($taskPlainKey -notmatch '^sk-[A-Za-z0-9_-]{16,}$') {
        throw 'Invalid key format (masked, incomplete, or control characters). Existing configuration was not changed.'
    }
    $taskEnvText = "OPENAI_API_KEY=$taskPlainKey`nOPENAI_BASE_URL=https://www.dmxapi.cn/v1`nTRACEPATCH_MODEL=qwen3.8-flash`nTRACEPATCH_BUDGET_CNY=10`n"
    [IO.File]::WriteAllText($taskEnvPath, $taskEnvText, [Text.UTF8Encoding]::new($false))
    Write-Host 'Saved local .env (ignored by Git). No API request was made.'
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($taskKeyPointer)
    $taskPlainKey = $null
    $taskEnvText = $null
    $taskSecureKey.Dispose()
}
