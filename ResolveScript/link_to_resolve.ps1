# Dev install: junction/hardlink ResolveScript into Resolve's Utility folder.
# Run once (or after cloning). Requires an elevated shell only if Utility is protected.
#
#   .\link_to_resolve.ps1

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$utility = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"

if (-not (Test-Path $utility)) {
    New-Item -ItemType Directory -Force -Path $utility | Out-Null
}

function Link-Junction($name, $target) {
    $dest = Join-Path $utility $name
    if (Test-Path $dest) {
        $item = Get-Item $dest -Force
        if ($item.LinkType -eq "Junction" -and $item.Target -eq $target) {
            Write-Host "OK  $name -> $target"
            return
        }
        Remove-Item $dest -Force -Recurse
    }
    New-Item -ItemType Junction -Path $dest -Target $target -Force | Out-Null
    Write-Host "LINK $name -> $target"
}

function Link-HardFile($name, $target) {
    $dest = Join-Path $utility $name
    if (Test-Path $dest) { Remove-Item $dest -Force }
    New-Item -ItemType HardLink -Path $dest -Target $target -Force | Out-Null
    Write-Host "LINK $name -> $target"
}

Link-HardFile "Conform Sidekick.py" (Join-Path $src "Conform Sidekick.py")
Link-Junction "conform_sidekick" (Join-Path $src "conform_sidekick")
Link-Junction "helpers" (Join-Path $src "helpers")

Write-Host ""
Write-Host "Installed to: $utility"
Write-Host "Launch: Workspace -> Scripts -> Utility -> Conform Sidekick"
