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

$Dest = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

Write-Host "Installing Conform Sidekick..."
Write-Host "  From: $Source"
Write-Host "    To: $Dest"
Write-Host ""

Copy-Item -Path $Launcher -Destination $Dest -Force

$DestPkg = Join-Path $Dest "conform_sidekick"
if ((Test-Path $DestPkg) -and -not $Force) {
    Write-Host "Removing previous conform_sidekick package..."
}
if (Test-Path $DestPkg) {
    Remove-Item -Path $DestPkg -Recurse -Force
}
Copy-Item -Path $Package -Destination $Dest -Recurse -Force

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
Write-Host "Restart Resolve, or use Scripts -> Reload if your version supports it."
