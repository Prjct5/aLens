<#
Runs the AutoLens M1 verification on this machine (Windows PowerShell 5.1+).

  .\scripts\windows\verify_m1.ps1 -DataDir "C:\path\to\Default Project\data"
  .\scripts\windows\verify_m1.ps1 -DataDir "C:\path\to\data" -Postgres     # needs Docker Desktop
  .\scripts\windows\verify_m1.ps1 -DataDir "C:\path\to\data" -SkipTests

Writes M1_VERIFY\tests.txt, M1_VERIFY\report.txt, M1_VERIFY\report.json
#>
param(
    [Parameter(Mandatory = $true)][string]$DataDir,
    [string]$WorkDir = ".\work",
    [string]$RunDate = "2026-01-15",
    [switch]$Postgres,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$repo = (Get-Location).Path
$report = Join-Path $repo "M1_VERIFY"
New-Item -ItemType Directory -Force -Path $report | Out-Null

function Step([string]$text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Run-Native([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "$exe $($arguments -join ' ') failed with exit code $LASTEXITCODE" }
}

$csv = Join-Path $DataDir "Egypt_Used_Cars_clean.csv"
if (-not (Test-Path -LiteralPath $csv)) { throw "Egypt_Used_Cars_clean.csv not found in $DataDir" }

Step "Python environment"
$candidates = @(@("py", "-3.12"), @("py", "-3.11"), @("python"))
$pyExe = $null
$pyPre = @()
foreach ($c in $candidates) {
    $exe = $c[0]
    $pre = @()
    if ($c.Count -gt 1) { $pre = @($c[1..($c.Count - 1)]) }
    try {
        $ver = & $exe @($pre + @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")) 2>$null
        if ($LASTEXITCODE -eq 0 -and [version]$ver -ge [version]"3.11") { $pyExe = $exe; $pyPre = $pre; break }
    } catch { }
}
if (-not $pyExe) { throw "Python 3.11 or newer is required (install from python.org and tick 'Add to PATH')." }
$venvPython = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Run-Native $pyExe ($pyPre + @("-m", "venv", ".venv"))
}
Run-Native $venvPython @("-m", "pip", "install", "--quiet", "--upgrade", "pip")
Run-Native $venvPython @("-m", "pip", "install", "--quiet", "-e", ".[dev,api,pipelines,scraping,linkage,warehouse]")

if (-not $SkipTests) {
    Step "Lint and tests (output saved to M1_VERIFY\tests.txt)"
    $testLog = Join-Path $report "tests.txt"
    $ErrorActionPreference = "Continue"
    & $venvPython -m ruff check . 2>&1 | Tee-Object -FilePath $testLog
    & $venvPython -m mypy src/autolens/common src/autolens/api 2>&1 | Tee-Object -FilePath $testLog -Append
    & $venvPython -m pytest tests/unit tests/contract tests/integration/test_m1_golden.py tests/integration/test_archive_replay_status.py tests/integration/test_vehicle_id_stability.py -p no:cacheprovider 2>&1 | Tee-Object -FilePath $testLog -Append
    $ErrorActionPreference = "Stop"
}

if ($Postgres) {
    Step "Starting PostgreSQL and MinIO (Docker)"
    if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
    Run-Native "docker" @("compose", "-f", "docker/docker-compose.yml", "--env-file", ".env", "up", "-d", "postgres", "minio", "minio-init")
    Write-Host "waiting for PostgreSQL ..."
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        & docker compose -f docker/docker-compose.yml --env-file .env exec -T postgres pg_isready -U autolens -d autolens 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 3
    }
    if (-not $ready) { throw "PostgreSQL did not become ready" }
    Start-Sleep -Seconds 8
}

Step "Running M1 stages on $DataDir"
$verifyArgs = @("scripts/m1/verify_m1.py", "--data-dir", $DataDir, "--work-dir", $WorkDir, "--run-date", $RunDate, "--report-dir", $report)
if ($Postgres) { $verifyArgs += "--postgres" }
Run-Native $venvPython $verifyArgs

Step "Done"
Write-Host "Upload these files to the chat:"
Get-ChildItem $report | ForEach-Object { Write-Host "  $($_.FullName)" }
