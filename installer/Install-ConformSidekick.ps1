# Install Conform Sidekick into DaVinci Resolve (Windows).
# Run from the extracted release folder (same directory as "Conform Sidekick.py").

param(
    [switch]$Force,
    [switch]$SkipDeps
)

$ErrorActionPreference = "Stop"
$Source = $PSScriptRoot
. (Join-Path $Source "Find-ResolvePython.ps1")
$Launcher = Join-Path $Source "Conform Sidekick.py"
$Package = Join-Path $Source "conform_sidekick"

if (-not (Test-Path $Launcher)) {
    Write-Error @"
Could not find 'Conform Sidekick.py' in:
  $Source

Extract the release ZIP first, then run this installer from that folder.
"@
}

$Utility = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
$Support = Join-Path $env:APPDATA "Conform Sidekick"
$SupportPkg = Join-Path $Support "conform_sidekick"

New-Item -ItemType Directory -Force -Path $Utility | Out-Null
New-Item -ItemType Directory -Force -Path $Support | Out-Null

Write-Host "Installing Conform Sidekick..."
Write-Host "  Launcher -> $Utility"
Write-Host "  Package  -> $SupportPkg"
Write-Host ""

Copy-Item -Path $Launcher -Destination $Utility -Force

# Upgrade from older installs that put the package under Utility/.
$LegacyPkg = Join-Path $Utility "conform_sidekick"
if (Test-Path $LegacyPkg) {
    Write-Host "Removing legacy package from Utility/..."
    Remove-Item -Path $LegacyPkg -Recurse -Force
}
$LegacyHelpers = Join-Path $Utility "helpers"
if (Test-Path $LegacyHelpers) {
    Remove-Item -Path $LegacyHelpers -Recurse -Force
}

if (Test-Path $SupportPkg) {
    Write-Host "Updating conform_sidekick package..."
    Remove-Item -Path $SupportPkg -Recurse -Force
}
Copy-Item -Path $Package -Destination $SupportPkg -Recurse -Force

Write-Host ""
try {
    Install-ResolvePythonDeps -SourceDir $Source -SkipDeps:$SkipDeps
} catch {
    Write-Warning @"
Could not install Python dependencies: $($_.Exception.Message)
Fix Odd Resolution Photos needs Pillow in Resolve's Python.
Re-run with -SkipDeps if deps are already installed, or install manually (see INSTALL.txt).
"@
}

Write-Host ""
Write-Host "Done. In Resolve: Workspace -> Scripts -> Utility -> Conform Sidekick"
Write-Host "Close and re-open the script if needed; restart Resolve if changes do not appear."
