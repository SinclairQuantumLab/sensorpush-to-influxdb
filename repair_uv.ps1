param(
    [switch]$ReinstallManagedPython
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$env:UV_CACHE_DIR = Join-Path $projectRoot ".uv-cache"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot ".uv-python"
$env:UV_LINK_MODE = "copy"

Write-Host "Project root: $projectRoot"
Write-Host "UV_CACHE_DIR=$env:UV_CACHE_DIR"
Write-Host "UV_PYTHON_INSTALL_DIR=$env:UV_PYTHON_INSTALL_DIR"
Write-Host "UV_LINK_MODE=$env:UV_LINK_MODE"
Write-Host ""

if ($ReinstallManagedPython -and (Test-Path -LiteralPath $env:UV_PYTHON_INSTALL_DIR)) {
    $resolvedPythonDir = (Resolve-Path -LiteralPath $env:UV_PYTHON_INSTALL_DIR).Path
    Write-Host "Removing existing managed Python at $resolvedPythonDir"
    Remove-Item -LiteralPath $resolvedPythonDir -Recurse -Force
}

if (Test-Path -LiteralPath ".venv") {
    $resolvedVenv = (Resolve-Path -LiteralPath ".venv").Path
    Write-Host "Removing existing virtual environment at $resolvedVenv"
    Remove-Item -LiteralPath $resolvedVenv -Recurse -Force
}

Write-Host "Installing project-local managed Python 3.14..."
uv python install 3.14 --managed-python --install-dir $env:UV_PYTHON_INSTALL_DIR

Write-Host ""
Write-Host "Syncing project environment..."
uv sync --managed-python

Write-Host ""
Write-Host "uv repair complete."
Write-Host "To keep using this local setup in the current shell:"
Write-Host '$env:UV_CACHE_DIR = "$PWD\.uv-cache"'
Write-Host '$env:UV_PYTHON_INSTALL_DIR = "$PWD\.uv-python"'
Write-Host '$env:UV_LINK_MODE = "copy"'
