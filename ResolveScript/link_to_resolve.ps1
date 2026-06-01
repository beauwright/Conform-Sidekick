# Dev install: link launcher into Resolve's Utility folder and package into
# Application Support (outside the Scripts tree so only one menu entry appears).
#
#   .\link_to_resolve.ps1

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$utility = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
$support = Join-Path $env:APPDATA "Conform Sidekick"

if (-not (Test-Path $utility)) {
    New-Item -ItemType Directory -Force -Path $utility | Out-Null
}
if (-not (Test-Path $support)) {
    New-Item -ItemType Directory -Force -Path $support | Out-Null
}

function Link-Junction($dest, $target) {
    if (Test-Path $dest) {
        $item = Get-Item $dest -Force
        if ($item.LinkType -eq "Junction" -and $item.Target -eq $target) {
            Write-Host "OK  $dest -> $target"
            return
        }
        Remove-Item $dest -Force -Recurse
    }
    New-Item -ItemType Junction -Path $dest -Target $target -Force | Out-Null
    Write-Host "LINK $dest -> $target"
}

function Link-HardFile($dest, $target) {
    if (Test-Path $dest) { Remove-Item $dest -Force }
    New-Item -ItemType HardLink -Path $dest -Target $target -Force | Out-Null
    Write-Host "LINK $dest -> $target"
}

# Remove legacy dev/install layout under Utility/.
$legacyPkg = Join-Path $utility "conform_sidekick"
if (Test-Path $legacyPkg) {
    Write-Host "Removing legacy Utility\conform_sidekick..."
    Remove-Item $legacyPkg -Force -Recurse
}
$legacyHelpers = Join-Path $utility "helpers"
if (Test-Path $legacyHelpers) {
    Remove-Item $legacyHelpers -Force -Recurse
}

Link-HardFile (Join-Path $utility "Conform Sidekick.py") (Join-Path $src "Conform Sidekick.py")
Link-Junction (Join-Path $support "conform_sidekick") (Join-Path $src "conform_sidekick")

$helpersSrc = Join-Path $src "helpers"
if (Test-Path $helpersSrc) {
    Link-Junction (Join-Path $support "helpers") $helpersSrc
}

Write-Host ""
Write-Host "Launcher: $utility\Conform Sidekick.py"
Write-Host "Package:  $support\conform_sidekick"
Write-Host "Launch:   Workspace -> Scripts -> Utility -> Conform Sidekick"
