# Locate the Python interpreter DaVinci Resolve uses for Workspace scripts.
# Resolve does not use $PATH; it loads python.org installs from fixed locations.

function Test-ResolvePython {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    try {
        & $Path -c "import sys; sys.exit(0 if sys.version_info >= (3, 6) else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Get-ResolvePythonVersionLabel {
    param([Parameter(Mandatory)][string]$Path)
    & $Path -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
}

function Find-ResolvePython {
    if ($env:CONFORM_SIDEKICK_PYTHON) {
        if (Test-ResolvePython -Path $env:CONFORM_SIDEKICK_PYTHON) {
            return $env:CONFORM_SIDEKICK_PYTHON
        }
        throw "CONFORM_SIDEKICK_PYTHON is set but not usable: $($env:CONFORM_SIDEKICK_PYTHON)"
    }

    $candidates = [System.Collections.Generic.List[string]]::new()

    foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not $root) { continue }
        Get-ChildItem -LiteralPath $root -Directory -Filter "Python3*" -ErrorAction SilentlyContinue |
            ForEach-Object {
                $candidates.Add((Join-Path $_.FullName "python.exe"))
            }
    }

    $localRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path -LiteralPath $localRoot) {
        Get-ChildItem -LiteralPath $localRoot -Directory -Filter "Python3*" -ErrorAction SilentlyContinue |
            ForEach-Object {
                $candidates.Add((Join-Path $_.FullName "python.exe"))
            }
    }

    # Prefer newer python.org installs (Resolve tracks these install locations).
    $sorted = $candidates |
        Where-Object { Test-ResolvePython -Path $_ } |
        Sort-Object {
            $label = Get-ResolvePythonVersionLabel -Path $_
            try { [version]$label } catch { [version]"0.0" }
        } -Descending

    if ($sorted) {
        return $sorted[0]
    }

    throw @"
Could not find Resolve's Python interpreter.

Install Python from https://www.python.org/downloads/ (64-bit, "Add to PATH" optional).
Resolve loads C:\Program Files\Python3xx\ or %LOCALAPPDATA%\Programs\Python\Python3xx\, not pyenv or conda.

Or set CONFORM_SIDEKICK_PYTHON to the full path of Resolve's python.exe.
"@
}

function Install-ResolvePythonDeps {
    param(
        [Parameter(Mandatory)][string]$SourceDir,
        [switch]$SkipDeps
    )

    if ($SkipDeps) {
        Write-Host "Skipping Python dependency install (-SkipDeps)."
        return
    }

    $req = Join-Path $SourceDir "requirements-resolve.txt"
    if (-not (Test-Path -LiteralPath $req)) {
        throw "Missing dependency list: $req"
    }

    $py = Find-ResolvePython
    $ver = Get-ResolvePythonVersionLabel -Path $py
    Write-Host "Using Resolve Python: $py ($ver)"

    try {
        & $py -m pip --version *> $null
        if ($LASTEXITCODE -ne 0) { throw "pip missing" }
    } catch {
        Write-Host "pip is not available for this Python; bootstrapping with ensurepip..."
        & $py -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) {
            throw "Could not bootstrap pip for $py"
        }
    }

    Write-Host "Installing Python dependencies for Fix Odd Resolution Photos..."
    & $py -m pip install --disable-pip-version-check -r $req
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed. Try running this installer as Administrator if Python is under Program Files."
    }
    Write-Host "Python dependencies installed."
}
