<#
.SYNOPSIS
    Start the Aifya Knowledge RAG service on plain Windows, with no Docker.

.DESCRIPTION
    Runs the knowledge service as an ordinary process on port 8025, which is
    where the web app's /api/knowledge proxy looks for it.

    Python is provisioned with uv whenever uv is present, so this works on a
    machine that has no system Python at all: uv downloads a private CPython
    into %APPDATA%\uv\python with no admin rights and nothing added to PATH.
    If uv is missing the script falls back to python/py from PATH.

    Everything this service owns lives under services/ai-service/knowledge:
      .venv        virtual environment for this service only
      data/files   uploaded documents (STORAGE_BACKEND=local)
      .env         configuration, copied from .env.example on first run

    The default backends configured there are all Docker-free:
      STORAGE_BACKEND=local    plain files under data/files, not MinIO
      VECTOR_BACKEND=postgres  embeddings stored in the shared PostgreSQL
      INGEST_MODE=inline       ingest inside the upload request, not Celery
      EMBEDDING_BACKEND=auto   BGE-M3 if torch is installed, else hashed

    PostgreSQL must be running first: the knowledge tables and their row-level
    security policy are shared with the api-gateway.

.PARAMETER Full
    Install requirements.txt instead of requirements-native.txt. This adds
    torch and sentence-transformers (a multi-gigabyte download) so BGE-M3 can
    produce real semantic embeddings.

.PARAMETER Port
    Port for the HTTP API. Defaults to 8025.

.PARAMETER SkipInstall
    Do not create the venv or install dependencies; just run the server.

.PARAMETER Reload
    Restart the server automatically whenever a source file changes.

.PARAMETER Docker
    Run the docker-compose services instead of the native process. Requires
    Docker Desktop to be running.

.EXAMPLE
    .\scripts\start-knowledge.ps1

.EXAMPLE
    .\scripts\start-knowledge.ps1 -Reload

.EXAMPLE
    .\scripts\start-knowledge.ps1 -Full -Port 8025
#>

[CmdletBinding()]
param(
    [switch]$Full,
    [int]$Port = 8025,
    [switch]$SkipInstall,
    [switch]$Reload,
    [switch]$Docker
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$serviceDir = Join-Path $repoRoot 'services\ai-service\knowledge'
$venvDir = Join-Path $serviceDir '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$requirements = if ($Full) { 'requirements.txt' } else { 'requirements-native.txt' }

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Note {
    param([string]$Message)
    Write-Host "    $Message" -ForegroundColor DarkGray
}

function Write-Warn {
    param([string]$Message)
    Write-Host "!!  $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "!!  $Message" -ForegroundColor Red
}

function Find-Uv {
    <#
    Locate uv. It installs outside PATH often enough that the usual install
    directories are checked explicitly.
    #>
    $command = Get-Command uv -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidates = @(
        (Join-Path $env:USERPROFILE '.local\bin\uv.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\uv\uv.exe'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\uv.exe')
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    return $null
}

function Find-Python {
    <#
    Locate a usable Python 3 interpreter for the fallback path, used only when
    uv is not available.
    #>
    $explicit = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        'C:\Python313\python.exe',
        'C:\Python312\python.exe',
        'C:\Python311\python.exe'
    )
    foreach ($candidate in $explicit) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    foreach ($name in @('python', 'python3', 'py')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    return $null
}

function Test-PortInUse {
    param([int]$Number)
    $listener = Get-NetTCPConnection -LocalPort $Number -State Listen -ErrorAction SilentlyContinue
    return [bool]$listener
}

function Assert-EnvFile {
    $envPath = Join-Path $serviceDir '.env'
    if (Test-Path -LiteralPath $envPath) { return $envPath }
    $example = Join-Path $serviceDir '.env.example'
    if (Test-Path -LiteralPath $example) {
        Copy-Item -LiteralPath $example -Destination $envPath
        Write-Note 'Created .env from .env.example - set DATABASE_URL and SECRET_KEY before use.'
        return $envPath
    }
    Write-Fail "No .env and no .env.example in $serviceDir"
    exit 1
}

function Show-Configuration {
    param([string]$EnvPath)
    Write-Step 'Effective configuration'
    foreach ($key in @(
        'APP_ENV', 'DATABASE_URL', 'STORAGE_BACKEND', 'VECTOR_BACKEND',
        'INGEST_MODE', 'EMBEDDING_BACKEND', 'MAX_FILE_SIZE_MB'
    )) {
        $line = Select-String -LiteralPath $EnvPath -Pattern "^$key=" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($line) { Write-Note $line.Line } else { Write-Note "$key=(default)" }
    }
}

if ($Docker) {
    Write-Step 'Starting the docker-compose knowledge stack'
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        Write-Fail 'docker was not found on PATH. Install Docker Desktop, or drop -Docker to run natively.'
        exit 1
    }
    & docker version --format '{{.Server.Version}}' *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail 'The Docker daemon is not running. Start Docker Desktop and wait for the whale icon to settle.'
        Write-Note 'Native mode needs none of this: re-run this script without -Docker.'
        exit 1
    }
    Push-Location $repoRoot
    try {
        & docker compose up -d postgres redis qdrant minio knowledge-service knowledge-worker
        Write-Step 'Waiting for the service to answer'
        foreach ($attempt in 1..30) {
            try {
                $health = Invoke-RestMethod -Uri "http://localhost:$Port/health" -TimeoutSec 5
                Write-Host "    $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
                break
            }
            catch {
                if ($attempt -eq 30) { Write-Fail 'The service did not answer /health within 150s. Check: docker compose logs -f knowledge-service' }
                Start-Sleep -Seconds 5
            }
        }
    }
    finally {
        Pop-Location
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $serviceDir)) {
    Write-Fail "Knowledge service directory not found: $serviceDir"
    exit 1
}

$envPath = Assert-EnvFile
Show-Configuration -EnvPath $envPath

Write-Step 'Checking prerequisites'
if (Test-PortInUse -Number 5432) {
    Write-Note 'PostgreSQL is listening on port 5432.'
}
else {
    Write-Warn 'Nothing is listening on port 5432. Start PostgreSQL first or uploads will not be stored.'
}

if (Test-PortInUse -Number $Port) {
    Write-Fail "Port $Port is already in use, so the knowledge service is probably already running."
    Write-Note "Confirm with: curl.exe http://localhost:$Port/health"
    Write-Note "Find the owner with: Get-NetTCPConnection -LocalPort $Port -State Listen"
    Write-Note 'Then stop it with:  Stop-Process -Id <PID> -Force'
    exit 1
}

$uv = Find-Uv
if ($uv) { Write-Note "uv found at $uv" }

if (-not $SkipInstall) {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        if ($uv) {
            Write-Step 'Provisioning Python 3.12 with uv'
            & $uv python install 3.12
            if ($LASTEXITCODE -ne 0) {
                Write-Fail 'uv could not install Python 3.12. Check your network connection and retry.'
                exit 1
            }
            Write-Step "Creating a virtual environment at $venvDir"
            & $uv venv --python 3.12 $venvDir
        }
        else {
            $python = Find-Python
            if (-not $python) {
                Write-Fail 'No Python 3 interpreter found, and uv is not installed.'
                Write-Note 'Install uv, which needs no admin rights: winget install --id astral-sh.uv'
                Write-Note 'Or install Python 3.12 from https://www.python.org/downloads/windows/ and tick "Add python.exe to PATH".'
                exit 1
            }
            Write-Step "Creating a virtual environment with $python"
            & $python -m venv $venvDir
        }
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
            Write-Fail 'Failed to create the virtual environment.'
            exit 1
        }
    }
    else {
        Write-Step 'Reusing the existing virtual environment'
    }

    Write-Step "Installing $requirements"
    if ($Full) { Write-Note 'This pulls torch and downloads BGE-M3 on first embedding call.' }
    if ($uv) {
        & $uv pip install --python $venvPython -r (Join-Path $serviceDir $requirements)
    }
    else {
        & $venvPython -m pip install --upgrade pip --quiet
        & $venvPython -m pip install -r (Join-Path $serviceDir $requirements)
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Dependency installation failed. Retry with: & '$venvPython' -m pip install -r '$requirements'"
        exit 1
    }
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Fail "The virtual environment is missing: $venvPython"
    Write-Note 'Run this script again without -SkipInstall so it can create it.'
    exit 1
}

Write-Step "Starting uvicorn on http://localhost:$Port"
Write-Note ("Health check: curl.exe http://localhost:$Port/health")
Write-Note 'Press Ctrl+C to stop.'

$uvicornArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', $Port)
if ($Reload) { $uvicornArgs += '--reload' }

Push-Location $serviceDir
try {
    & $venvPython @uvicornArgs
}
finally {
    Pop-Location
}