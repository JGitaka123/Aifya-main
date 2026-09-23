<#
.SYNOPSIS
    Diagnose the WhatsApp (Green API) channel used by the Communication Hub.

.DESCRIPTION
    Reads WA_INSTANCE_ID / WA_ACCESS_TOKEN from services/api-gateway/.env and asks
    Green API two questions, printing the RAW reply to each:

      1. getStateInstance - is the instance linked and authorized? Costs nothing,
         sends nothing. A state other than "authorized" means every send fails.
      2. sendMessage - only for the numbers passed with -SendTo. The raw JSON body
         is printed so the exact rejection reason is visible instead of the API
         generic "provider rejected this message".

.PARAMETER EnvFile
    Path to the .env file. Defaults to services/api-gateway/.env beside this script.

.PARAMETER SendTo
    One or more recipient numbers to test, in any Kenyan format (0712345678,
    +254712345678, 254712345678). Each test sends one real WhatsApp message.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\check-whatsapp.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\check-whatsapp.ps1 -SendTo 0115955244,0711112386
    (quote the numbers if you run it from a PowerShell prompt, so the leading
    zero is not read as a number: -SendTo "0115955244","0711112386")
#>
[CmdletBinding()]
param(
    [string]   $EnvFile,
    [string[]] $SendTo = @()
)

$ErrorActionPreference = 'Stop'

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

function Get-GreenHost {
    param([string] $InstanceId)
    if ($InstanceId.StartsWith("1100")) { return "https://api.green-api.com" }
    return ("https://" + $InstanceId.Substring(0, 4) + ".api.green-api.com")
}

function ConvertTo-ChatId {
    param([string] $Number)
    $d = ($Number -replace "[^0-9]", "")
    if ($d.Length -eq 10 -and $d.StartsWith("0")) { $d = "254" + $d.Substring(1) }
    elseif ($d.Length -eq 9 -and ($d.StartsWith("7") -or $d.StartsWith("1"))) { $d = "254" + $d }
    if ($d -match "^254[17]\d{8}$") { return ($d + "@c.us") }
    return ""
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

$instanceId = $cfg['WA_INSTANCE_ID']
$token      = $cfg['WA_ACCESS_TOKEN']
$phoneId    = $cfg['WA_PHONE_NUMBER_ID']

Write-Host ""
Write-Host "WhatsApp (Green API) channel check" -ForegroundColor Cyan
Write-Host "  env file       : $EnvFile"
Write-Host "  WA_INSTANCE_ID : " -NoNewline
if ([string]::IsNullOrWhiteSpace($instanceId)) { Write-Host "MISSING" -ForegroundColor Red } else { Write-Host $instanceId -ForegroundColor Green }
Write-Host "  WA_ACCESS_TOKEN: " -NoNewline
if ([string]::IsNullOrWhiteSpace($token)) { Write-Host "MISSING" -ForegroundColor Red } else { Write-Host ("present, {0} chars" -f $token.Length) -ForegroundColor Green }
Write-Host "  WA_PHONE_NUMBER_ID: " -NoNewline
if ([string]::IsNullOrWhiteSpace($phoneId)) { Write-Host "(not set - that is fine for Green API, it is only used by Meta Cloud)" } else { Write-Host $phoneId }

if ([string]::IsNullOrWhiteSpace($instanceId) -or [string]::IsNullOrWhiteSpace($token)) {
    Write-Host "Green API needs both WA_INSTANCE_ID and WA_ACCESS_TOKEN." -ForegroundColor Red
    exit 2
}

$greenHost = Get-GreenHost $instanceId
$stateUrl  = "$greenHost/waInstance$instanceId/getStateInstance/$token"
$sendBase  = "$greenHost/waInstance$instanceId/sendMessage/$token"
Write-Host "  resolved host  : $greenHost"
Write-Host ""

Write-Host "1) Instance state"
try {
    $state = Invoke-RestMethod -Uri $stateUrl -Method Get -TimeoutSec 30
    Write-Host ("   " + ($state | ConvertTo-Json -Compress))
    if ($state.stateInstance -eq "authorized") {
        Write-Host "   OK - the instance is linked and can send." -ForegroundColor Green
    } else {
        Write-Host ("   NOT READY - state is " + $state.stateInstance + ". Open the Green API console, scan the QR") -ForegroundColor Yellow
        Write-Host "   code for this instance, and confirm WhatsApp is still logged in there." -ForegroundColor Yellow
    }
} catch {
    Write-Host ("   FAILED: " + (Get-ErrorBody $_)) -ForegroundColor Red
}

# -File mode hands a comma-separated value through as ONE string, so split it.
$targets = @()
foreach ($entry in $SendTo) {
    foreach ($piece in ($entry -split ",")) {
        if (-not [string]::IsNullOrWhiteSpace($piece)) { $targets += $piece.Trim() }
    }
}

if ($targets.Count -eq 0) {
    Write-Host ""
    Write-Host "Add -SendTo <number> to test a real send and see the raw reply." -ForegroundColor DarkGray
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host "2) Test sends"
foreach ($number in $targets) {
    $chatId = ConvertTo-ChatId $number
    if ([string]::IsNullOrEmpty($chatId)) {
        Write-Host ("   {0}" -f $number)
        Write-Host "     SKIPPED - not a recognisable Kenyan mobile number (expected 07xxxxxxxx or 01xxxxxxxx)." -ForegroundColor Yellow
        continue
    }
    $body = @{ chatId = $chatId; message = "Aifya WhatsApp connectivity test" } | ConvertTo-Json
    Write-Host ""
    Write-Host ("   {0}  ->  chatId {1}" -f $number, $chatId)
    try {
        $reply = Invoke-RestMethod -Uri $sendBase -Method Post -TimeoutSec 30 -ContentType "application/json" -Body $body
        Write-Host ("     RAW REPLY: " + ($reply | ConvertTo-Json -Compress)) -ForegroundColor Green
        if ($reply.idMessage) { Write-Host "     ACCEPTED by Green API." -ForegroundColor Green }
        else { Write-Host "     No idMessage - Green API did not queue this message." -ForegroundColor Yellow }
    } catch {
        Write-Host ("     REJECTED: " + (Get-ErrorBody $_)) -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Reading the result:"
Write-Host "  code 401 / 403            the token is wrong or the instance is not yours"
Write-Host "  notAuthorized             the instance needs its QR code scanned again"
Write-Host "  no idMessage, 200 OK      Green API accepted the call but queued nothing"
Write-Host "  a bad-number style error  that recipient has no WhatsApp account"
Write-Host ""
