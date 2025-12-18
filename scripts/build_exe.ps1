$ErrorActionPreference = "Stop"

# Build a PyInstaller onedir executable of gearrec.
# Outputs to dist/gearrec-<os>-<arch>/gearrec.exe

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Venv = Join-Path $Root ".venv-build"

python -m venv $Venv
& "$Venv\Scripts\Activate.ps1"

pip install --upgrade pip
$Editable = "$Root`[dev]"
pip install -e $Editable

pytest

pyinstaller "$Root/packaging/pyinstaller/gearrec.spec"

$OSName = python -c "import platform; print(platform.system().lower())"
$Arch = python -c "import platform; print(platform.machine().lower())"

$SourceDir = Join-Path $Root "dist/gearrec"
$TargetDir = Join-Path $Root "dist/gearrec-$OSName-$Arch"
if (Test-Path $TargetDir) { Remove-Item -Recurse -Force $TargetDir }
if (Test-Path $SourceDir) { Move-Item $SourceDir $TargetDir }
$RootExe = Join-Path $Root "dist/gearrec.exe"
if (Test-Path $RootExe) {
    $TargetExe = Join-Path $TargetDir "gearrec.exe"
    if (Test-Path $TargetExe) {
        Remove-Item $RootExe
    } else {
        Move-Item $RootExe $TargetExe
    }
}

Write-Host "Build complete. See dist/ for output:"
Get-ChildItem "$Root/dist"
