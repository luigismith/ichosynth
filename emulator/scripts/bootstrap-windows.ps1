# bootstrap-windows.ps1 — install the C++ toolchain + SDL2 needed to build the
# NI404 emulator on Windows. One-shot; safe to re-run (idempotent).
#
#   Right-click > Run with PowerShell, or:  ./bootstrap-windows.ps1
#
$ErrorActionPreference = 'Stop'

Write-Host "== NI404 emulator: Windows toolchain bootstrap ==" -ForegroundColor Cyan

# 1) MSYS2 (provides gcc, cmake, SDL2 via pacman).
if (-not (Test-Path 'C:\msys64\usr\bin\pacman.exe')) {
  Write-Host "Installing MSYS2 via winget..." -ForegroundColor Yellow
  winget install --id MSYS2.MSYS2 -e --accept-package-agreements --accept-source-agreements --disable-interactivity
} else {
  Write-Host "MSYS2 already installed." -ForegroundColor Green
}

$pacman = 'C:\msys64\usr\bin\pacman.exe'

# 2) Toolchain + SDL2.
Write-Host "Syncing package database..." -ForegroundColor Yellow
& $pacman -Sy --noconfirm

Write-Host "Installing gcc, cmake, make, SDL2 (mingw-w64)..." -ForegroundColor Yellow
& $pacman -S --needed --noconfirm `
  mingw-w64-x86_64-gcc `
  mingw-w64-x86_64-cmake `
  mingw-w64-x86_64-make `
  mingw-w64-x86_64-SDL2

Write-Host ""
Write-Host "Toolchain ready. Now build with:  ./build.ps1" -ForegroundColor Green
