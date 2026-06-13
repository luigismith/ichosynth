# run.ps1 — launch a built emulator.  Usage:  ./run.ps1 [ni404emu|toernemu] [args]
$root = Split-Path -Parent $PSScriptRoot
$target = 'ni404emu'
if ($args.Count -ge 1 -and ($args[0] -eq 'ni404emu' -or $args[0] -eq 'toernemu')) {
  $target = $args[0]; $args = $args[1..($args.Count - 1)]
}
$exe = Join-Path $root "build\$target.exe"
if (-not (Test-Path $exe)) { Write-Error "Not built yet. Run ./build.ps1 first." }
# DLLs are copied next to the exe by build.ps1; add mingw to PATH as a fallback.
$env:PATH = "C:\msys64\mingw64\bin;$env:PATH"
& $exe @args
