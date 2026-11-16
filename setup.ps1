# MUST HealthConnect - one-time setup on Windows.
# Run from the project folder in the VS Code terminal:
#   powershell -ExecutionPolicy Bypass -File setup.ps1
#
# What it does:
#   1. creates the virtual environment "mustvenv" (if it is not there yet)
#   2. installs Django, psycopg and python-dotenv into it
#   3. creates .env from .env.example with a fresh secret key (if .env is missing)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Assert-LastExit($what) {
    if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE). Read the error above." }
}

# Prefer the "py" launcher that the python.org installer adds; fall back to "python".
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pyExe = "py"; $pyArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pyExe = "python"; $pyArgs = @()
} else {
    throw "Python was not found. Install Python 3.12 or 3.13 from python.org and tick 'Add python.exe to PATH'."
}

if (-not (Test-Path "mustvenv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment 'mustvenv'..." -ForegroundColor Cyan
    & $pyExe @pyArgs -m venv mustvenv
    Assert-LastExit "Creating the virtual environment"
}
$venvPy = Join-Path $PSScriptRoot "mustvenv\Scripts\python.exe"
& $venvPy --version

Write-Host "Installing packages (needs internet the first time)..." -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip --quiet
Assert-LastExit "Upgrading pip"
& $venvPy -m pip install -r requirements.txt
Assert-LastExit "Installing requirements"

if (-not (Test-Path ".env")) {
    $key = (& $venvPy -c "import secrets; print(secrets.token_urlsafe(50))").Trim()
    $lines = Get-Content ".env.example" | ForEach-Object {
        if ($_ -like "DJANGO_SECRET_KEY=*") { "DJANGO_SECRET_KEY=" + $key } else { $_ }
    }
    # UTF-8 without a BOM, so python-dotenv reads the first line correctly
    [System.IO.File]::WriteAllLines((Join-Path $PSScriptRoot ".env"), [string[]]$lines)
    Write-Host "Created .env with a new secret key." -ForegroundColor Green
} else {
    Write-Host ".env already exists, left unchanged."
}

Write-Host ""
Write-Host "Setup done. Next steps:" -ForegroundColor Green
Write-Host "  1. powershell -ExecutionPolicy Bypass -File setup_db.ps1   (creates the PostgreSQL database; only once)"
Write-Host "  2. .\mustvenv\Scripts\Activate.ps1"
Write-Host "  3. python manage.py migrate"
Write-Host "  4. python manage.py seed_demo"
Write-Host "  5. python manage.py createsuperuser"
Write-Host "  6. python manage.py runserver      then open http://127.0.0.1:8000"
