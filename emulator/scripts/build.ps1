# build.ps1 — configure & build the emulator on Windows (MSYS2/mingw-w64), at
# below-normal priority so the PC stays usable. Builds toernemu (the real TŒRN
# firmware, staged by firmware/build_toern.py) and ni404emu (the legacy bench).
# The simplest route is still:  python emulator/run.py --build-only
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot          # emulator/
$repo = Split-Path -Parent $root
$mingw = 'C:\msys64\mingw64\bin'
if (-not (Test-Path "$mingw\g++.exe")) {
  Write-Error "Toolchain not found. Run ./bootstrap-windows.ps1 first."
}
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { Write-Error "Python 3 not found on PATH (toernemu's CMake step runs firmware/build_toern.py)." }
$env:PATH = "$mingw;C:\msys64\usr\bin;$env:PATH"
[System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal'   # children inherit it

# TŒRN sources at the commit pinned in firmware/build_toern.py (cloned if missing; needs git).
& $python "$repo\firmware\build_toern.py" --fetch-only
if ($LASTEXITCODE -ne 0) { Write-Error "Could not get the TŒRN sources." }

$build = Join-Path $root 'build'
New-Item -ItemType Directory -Force -Path $build | Out-Null

& "$mingw\cmake.exe" -S $root -B $build -G "MinGW Makefiles" `
    -DCMAKE_BUILD_TYPE=Release -DEMU_BUILD_TOERN=ON "-DPython3_EXECUTABLE=$python"
if ($LASTEXITCODE -ne 0) { Write-Error "CMake configure failed." }

$jobs = [Math]::Max(2, [int]([Environment]::ProcessorCount / 2))
& "$mingw\cmake.exe" --build $build -j $jobs
if ($LASTEXITCODE -ne 0) { Write-Error "Build failed." }

# SDL2.dll next to the exes so they start by double-click on any machine (the mingw
# C++ runtime is linked statically).
Copy-Item "$mingw\SDL2.dll" $build -Force

$built = @('toernemu', 'ni404emu') | Where-Object { Test-Path (Join-Path $build "$_.exe") }
Write-Host ""
Write-Host ("Built: " + (($built | ForEach-Object { "$build\$_.exe" }) -join '  and  ')) -ForegroundColor Green
Write-Host "Run by double-clicking the exe, or:  ./run.ps1 [toernemu|ni404emu] [args]" -ForegroundColor Green
