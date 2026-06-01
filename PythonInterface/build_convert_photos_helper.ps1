# Build the odd-resolution image helper (Windows).
# Output: dist/convert_photos_helper-x86_64-pc-windows-msvc.exe
# Copy that file into ResolveScript/helpers/ beside your installed Conform Sidekick.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Error "pyinstaller not found. Run: pip install -r requirements.txt"
}

New-Item -ItemType Directory -Force -Path dist | Out-Null

pyinstaller convert_photos_cli.py `
    --onefile `
    --clean `
    --name convert_photos_helper-x86_64-pc-windows-msvc.exe

Write-Host ""
Write-Host "Built: dist/convert_photos_helper-x86_64-pc-windows-msvc.exe"
Write-Host "Copy into: ResolveScript/helpers/ (next to Conform Sidekick.py)"
