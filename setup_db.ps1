# MUST HealthConnect - create the PostgreSQL database and roles (Windows).
# Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File setup_db.ps1
#
# It finds psql.exe (even if it is not on PATH), then runs docs/setup.sql as the
# "postgres" superuser. You will be asked for the postgres password you chose
# when you installed PostgreSQL. Safe to run again: existing things are skipped.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$psql = $null
$onPath = Get-Command psql -ErrorAction SilentlyContinue
if ($onPath) {
    $psql = $onPath.Source
} else {
    # Default install folder of the EDB installer: C:\Program Files\PostgreSQL\<version>\bin
    $found = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
        Sort-Object { [int]($_.Directory.Parent.Name -replace '\D', '') } -Descending |
        Select-Object -First 1  
    if ($found) { $psql = $found.FullName }
}
if (-not $psql) {
    throw "psql.exe was not found. Install PostgreSQL from postgresql.org (EDB installer), or add its bin folder to PATH."
}

Write-Host "Using $psql" -ForegroundColor Cyan
Write-Host "Enter the password of the 'postgres' user when asked." -ForegroundColor Cyan
& $psql -U postgres -h localhost -p 5432 -f "docs\setup.sql"
if ($LASTEXITCODE -ne 0) {
    throw "psql failed. Check the postgres password and that the PostgreSQL service is running (services.msc)."
}

Write-Host ""
Write-Host "Database ready. Next: .\mustvenv\Scripts\Activate.ps1, then python manage.py migrate" -ForegroundColor Green
