<#
.SYNOPSIS
    Verify the Africa's Talking credentials held in the API gateway .env.

.DESCRIPTION
    Reads AT_API_KEY / AT_USERNAME / AT_SANDBOX from services/api-gateway/.env and
    asks Africa's Talking to authenticate them against the account endpoint, which
    returns the airtime balance. A successful call proves both the API key and the
    username are correct WITHOUT sending any SMS.

    The username is the value most often wrong: the literal sandbox username is only
    valid on the sandbox host, and an account created with an email address often
    uses that email as its username. Both are tried automatically.

.PARAMETER EnvFile
    Path to the .env file. Defaults to services/api-gateway/.env beside this script.

.PARAMETER Username
    Extra username candidates to try, on top of the automatic ones.

.PARAMETER SendTo
    Send one real SMS to this E.164 number (for example +254712345678) using the
    first username that authenticated. Costs airtime.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\check-africastalking.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\check-africastalking.ps1 -SendTo +254712345678
#>
[CmdletBinding()]
param(
    [string]   $EnvFile,
    [string[]] $Username = @(),
    [string]   $SendTo
)

$ErrorActionPreference = 'Stop'

$prodBase    = 'https://api.africastalking.com'
$sandboxBase = 'https://api.sandbox.africastalking.com'

function Get-DotEnvMap {
    param([string] $Path)
    $map = @{}
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
            $map[$matches[1]] = $matches[2].Trim()
        }
    }
    return $map
}

function Get-ErrorBody {
    param($ErrorRecord)
    if ($ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) {
        return $ErrorRecord.ErrorDetails.Message
    }
    $response = $ErrorRecord.Exception.Response
    if ($null -ne $response) {
        try {
            $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
            return $reader.ReadToEnd()
        } catch { }
    }
    return $ErrorRecord.Exception.Message
}

function Test-AtUsername {
    param([string] $BaseUrl, [string] $ApiKey, [string] $User)
    $uri = "$BaseUrl/version1/user?username=$([uri]::EscapeDataString($User))"
    try {
        $result = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 30 -Headers @{ apiKey = $ApiKey; Accept = "application/json" }
        $balance = ""
        if ($result -and $result.UserData) { $balance = $result.UserData.balance }
        return [pscustomobject]@{ Ok = $true; Detail = "balance $balance"; Error = "" }
    } catch {
        return [pscustomobject]@{ Ok = $false; Detail = ""; Error = (Get-ErrorBody $_) }
    }
}

function Send-AtTestSms {
    param([string] $BaseUrl, [string] $ApiKey, [string] $User, [string] $To, [string] $From)
    $body = @{ username = $User; to = $To; message = "Aifya SMS connectivity test" }
    if ($From) { $body["from"] = $From }
    $uri = "$BaseUrl/version1/messaging"
    return Invoke-RestMethod -Uri $uri -Method Post -TimeoutSec 30 -Headers @{ apiKey = $ApiKey; Accept = "application/json" } -Body $body
}

if (-not $EnvFile) {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $EnvFile = Join-Path $repoRoot "services\api-gateway\.env"
}
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Write-Host "Cannot find .env at: $EnvFile" -ForegroundColor Red
    exit 2
}
$EnvFile = (Resolve-Path -LiteralPath $EnvFile).Path
$cfg = Get-DotEnvMap $EnvFile

$apiKey    = $cfg['AT_API_KEY']
$senderId  = $cfg['AT_SENDER_ID']
$inEnv     = $cfg['AT_USERNAME']
$sandboxIn = ($cfg['AT_SANDBOX'] -eq 'true')

Write-Host ""
Write-Host "Africa's Talking credential check" -ForegroundColor Cyan
Write-Host "  env file     : $EnvFile"
Write-Host "  AT_API_KEY   : " -NoNewline
if ([string]::IsNullOrWhiteSpace($apiKey)) { Write-Host "MISSING" -ForegroundColor Red } else { Write-Host ("present, {0} chars" -f $apiKey.Length) -ForegroundColor Green }
Write-Host "  AT_USERNAME  : " -NoNewline
if ([string]::IsNullOrWhiteSpace($inEnv)) { Write-Host "EMPTY" -ForegroundColor Red } else { Write-Host $inEnv -ForegroundColor Yellow }
Write-Host "  AT_SANDBOX   : $sandboxIn"
Write-Host "  AT_SENDER_ID : " -NoNewline
if ([string]::IsNullOrWhiteSpace($senderId)) { Write-Host "(none, the default shortcode is used)" } else { Write-Host $senderId }
Write-Host ""

if ([string]::IsNullOrWhiteSpace($apiKey)) {
    Write-Host "Set AT_API_KEY in the .env before running this check." -ForegroundColor Red
    exit 2
}

$candidates = New-Object System.Collections.ArrayList
function Add-Candidate {
    param([string] $Value, [string] $Why)
    if ([string]::IsNullOrWhiteSpace($Value)) { return }
    if ($Value -match '^(your_|change_me|replace_with|placeholder|dummy|todo)') { return }
    foreach ($existing in $candidates) { if ($existing.Value -eq $Value) { return } }
    [void]$candidates.Add([pscustomobject]@{ Value = $Value; Why = $Why })
}

Add-Candidate $inEnv "AT_USERNAME from the .env"
Add-Candidate "sandbox" "the sandbox username"
if ($cfg['SMTP_USERNAME']) {
    $mail = $cfg['SMTP_USERNAME']
    Add-Candidate $mail "the account email address"
    Add-Candidate ($mail.Split("@")[0]) "the email address without the domain"
}
foreach ($extra in $Username) { Add-Candidate $extra "supplied with -Username" }

$working = $null
Write-Host "Probing $($candidates.Count) username candidate(s) against both hosts..."
Write-Host ""
foreach ($candidate in $candidates) {
    foreach ($base in @($prodBase, $sandboxBase)) {
        if ($base -eq $prodBase) { $label = "live   " } else { $label = "sandbox" }
        $outcome = Test-AtUsername -BaseUrl $base -ApiKey $apiKey -User $candidate.Value
        if ($outcome.Ok) {
            Write-Host ("  PASS  {0}  username={1}  -> {2}" -f $label, $candidate.Value, $outcome.Detail) -ForegroundColor Green
            if (-not $working) {
                $working = [pscustomobject]@{ Username = $candidate.Value; Base = $base; IsSandbox = ($base -eq $sandboxBase) }
            }
        } else {
            $short = $outcome.Error
            if ($short.Length -gt 140) { $short = $short.Substring(0, 140) + "..." }
            Write-Host ("  FAIL  {0}  username={1}  -> {2}" -f $label, $candidate.Value, $short) -ForegroundColor DarkGray
        }
    }
}

Write-Host ""
if (-not $working) {
    Write-Host "No candidate authenticated." -ForegroundColor Red
    Write-Host "Open the Africa's Talking dashboard - the API username sits next to the API key - then re-run:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\check-africastalking.ps1 -Username YOUR-USERNAME" -ForegroundColor Yellow
    exit 1
}

Write-Host "WORKING CREDENTIALS - put these two lines in the .env" -ForegroundColor Green
Write-Host ("  AT_USERNAME={0}" -f $working.Username)
Write-Host ("  AT_SANDBOX={0}" -f $working.IsSandbox.ToString().ToLower())

if ($SendTo) {
    Write-Host ""
    Write-Host "Sending one test SMS to $SendTo ..."
    try {
        $send = Send-AtTestSms -BaseUrl $working.Base -ApiKey $apiKey -User $working.Username -To $SendTo -From $senderId
        $recipients = $send.SMSMessageData.Recipients
        if ($recipients -and $recipients.Count -gt 0) {
            Write-Host ("  status: {0} (code {1})" -f $recipients[0].status, $recipients[0].statusCode) -ForegroundColor Green
            Write-Host ("  message id: {0}" -f $recipients[0].messageId)
        } else {
            Write-Host ("  unexpected response: " + ($send | ConvertTo-Json -Depth 6 -Compress)) -ForegroundColor Yellow
        }
    } catch {
        Write-Host ("  send failed: " + (Get-ErrorBody $_)) -ForegroundColor Red
        if ($senderId) {
            Write-Host ("  If the error blames the sender ID, blank AT_SENDER_ID and retry - the ID must be registered on the account: " + $senderId) -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "Restart the API after editing the .env:"
$apiDir = Split-Path -Parent $EnvFile
Write-Host ("  cd /d " + $apiDir)
Write-Host "  uv run uvicorn app.main:app --reload --port 8000"
Write-Host ""
