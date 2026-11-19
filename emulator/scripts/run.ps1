# run.ps1 — launch a built emulator.  Usage:  ./run.ps1 [toernemu|ni404emu] [args]
# Default: toernemu (the real TŒRN firmware). Build first with ./build.ps1.
$root = Split-Path -Parent $PSScriptRoot
$target = 'toernemu'
if ($args.Count -ge 1 -and ($args[0] -eq 'ni404emu' -or $args[0] -eq 'toernemu')) {
  $target = $args[0]; $args = $args[1..($args.Count - 1)]
}
$exe = Join-Path $root "build\$target.exe"
if (-not (Test-Path $exe)) { Write-Error "Not built yet. Run ./build.ps1 first." }
# SDL2.dll is copied next to the exe by build.ps1; add mingw to PATH as a fallback.
$env:PATH = "C:\msys64\mingw64\bin;$env:PATH"
& $exe @args
