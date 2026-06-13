# build.ps1 — configure & build the NI404 emulator on Windows (MSYS2/mingw-w64).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot          # emulator/
$mingw = 'C:\msys64\mingw64\bin'
if (-not (Test-Path "$mingw\g++.exe")) {
  Write-Error "Toolchain not found. Run ./bootstrap-windows.ps1 first."
}
$env:PATH = "$mingw;C:\msys64\usr\bin;$env:PATH"

$build = Join-Path $root 'build'
New-Item -ItemType Directory -Force -Path $build | Out-Null

& "$mingw\cmake.exe" -S $root -B $build -G "MinGW Makefiles" `
    -DCMAKE_BUILD_TYPE=Release
if ($LASTEXITCODE -ne 0) { Write-Error "CMake configure failed." }

& "$mingw\cmake.exe" --build $build -j
if ($LASTEXITCODE -ne 0) { Write-Error "Build failed." }

# Copy the runtime DLLs next to the exe so it launches by double-click on any
# machine (without the mingw bin on PATH). libgcc/libstdc++ are static-linked,
# but ship them too as belt-and-suspenders along with SDL2 + winpthread.
foreach ($dll in 'SDL2.dll','libwinpthread-1.dll','libstdc++-6.dll','libgcc_s_seh-1.dll') {
  Copy-Item "$mingw\$dll" $build -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Built: $build\ni404emu.exe  and  $build\toernemu.exe" -ForegroundColor Green
Write-Host "Run by double-clicking the exe, or:  ./run.ps1 [ni404emu|toernemu]" -ForegroundColor Green
