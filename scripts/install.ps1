# Windows: install QuoteSight into .venv, then ask the setup questions.
# Run from the QuoteSight folder:  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = if ($env:PYTHON) { $env:PYTHON } else { "py" }
& $py -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10 or newer is needed'"
Write-Host "Installing (a few minutes, about 2 GB)..."
& $py -m venv .venv
& .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
# With an NVIDIA GPU, install the CUDA build of torch first for faster indexing: https://pytorch.org/get-started/locally/
& .venv\Scripts\python.exe -m pip install --quiet -e .
& .venv\Scripts\quotesight.exe setup
Write-Host ""
Write-Host "Done. Double-click Start.bat in this folder to build the index and open the board."
