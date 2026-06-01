# Install Conform Sidekick into DaVinci Resolve (Windows).
# Run from the extracted release folder (same directory as "Conform Sidekick.py").

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Source = $PSScriptRoot
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

$HelpersSrc = Join-Path $Source "helpers"
$HelpersDest = Join-Path $Dest "helpers"
if (Test-Path $HelpersSrc) {
    New-Item -ItemType Directory -Force -Path $HelpersDest | Out-Null
    Get-ChildItem $HelpersSrc -File | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $HelpersDest -Force
    }
    Write-Host "  Image helper installed."
} else {
    Write-Warning "  No helpers/ folder in this package (odd-res conversion may need Pillow in Resolve)."
}

Write-Host ""
Write-Host "Done. In Resolve: Workspace -> Scripts -> Utility -> Conform Sidekick"
Write-Host "Restart Resolve, or use Scripts -> Reload if your version supports it."
