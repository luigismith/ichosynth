<#
  ichosynth - one-shot dev-environment setup (Windows / PowerShell)
  -------------------------------------------------------------------------
  Installs the Teensy core + every library the firmware needs, patches
  ResamplingReader.h, and compile-checks the sketch. Safe to re-run.

      powershell -ExecutionPolicy Bypass -File scripts\setup-dev-env.ps1
      powershell -ExecutionPolicy Bypass -File scripts\setup-dev-env.ps1 -NoBuild

  Requires arduino-cli (https://arduino.github.io/arduino-cli/). Install with:
      winget install ArduinoSA.CLI
  Do NOT use the Arduino IDE from the Microsoft Store - it is incompatible
  with Teensy.
  -------------------------------------------------------------------------
#>
param([switch]$NoBuild)

$ErrorActionPreference = 'Stop'

$RepoRoot  = Split-Path -Parent $PSScriptRoot
$TeensyUrl = 'https://www.pjrc.com/teensy/package_teensy_index.json'
$Fqbn      = 'teensy:avr:teensy41:usb=serialmidi16'   # Teensy 4.1, USB = Serial + MIDIx16

# registry libraries (exact names). FastLED is PINNED to 3.9.10 - newer 3.10.x
# break on the Teensy WS2812Serial controller path used by this firmware.
$RegistryLibs = @(
  'FastLED@3.9.10',
  'Mapf',
  'Switch',                  # avdweb_Switch (button gestures)
  'Adafruit SSD1306',        # OLED (only needed if OLED_ENABLED, harmless otherwise)
  'Adafruit GFX Library'
)
# The two newdigate libraries are developed together and must come from the SAME
# source - the registry copies are version-skewed against each other (missing
# AudioPlaySdResmp / playRaw / triggerReload). Install both from GitHub HEAD, in
# this order (teensy-polyphony depends on teensy-variable-playback).
$GitLibs = @(
  'https://github.com/newdigate/teensy-variable-playback.git',  # AudioPlayArrayResmp + ResamplingReader.h
  'https://github.com/newdigate/teensy-polyphony.git'           # TeensyPolyphony (arraysampler)
)
# NOTE: WS2812Serial, Encoder, Audio, Wire, SD, EEPROM ship with the Teensy core.

function Say ($m){ Write-Host "`n==> $m" -ForegroundColor Cyan }
function Ok  ($m){ Write-Host "   OK $m"  -ForegroundColor Green }
function Warn($m){ Write-Host "   !  $m"  -ForegroundColor Yellow }

if (-not (Get-Command arduino-cli -ErrorAction SilentlyContinue)) {
  Write-Host 'arduino-cli not found. Install it first:'
  Write-Host '  winget install ArduinoSA.CLI'
  exit 1
}
Ok ("arduino-cli " + (arduino-cli version | Select-Object -First 1))

Say 'Configuring arduino-cli (Teensy board URL + git installs)'
arduino-cli config init --overwrite *> $null
arduino-cli config set library.enable_unsafe_install true | Out-Null
try   { arduino-cli config add board_manager.additional_urls $TeensyUrl *> $null }
catch { arduino-cli config set board_manager.additional_urls $TeensyUrl *> $null }
Ok 'config ready'

Say 'Installing the Teensy core (teensy:avr)'
arduino-cli core update-index | Out-Null
arduino-cli core install teensy:avr
Ok 'Teensy core installed'

Say 'Installing registry libraries'
arduino-cli lib update-index | Out-Null
arduino-cli lib install @RegistryLibs
Ok 'registry libraries installed'

Say 'Installing libraries from GitHub (named in the project README)'
# Remove any registry copies first so we don't end up with two libraries that
# both provide TeensyPolyphony.h / the variable-playback headers (duplicate
# library = header conflict). The registry copies are also version-skewed.
arduino-cli lib uninstall 'TeensyAudioSampler' 'TeensyVariablePlayback' 2>$null
foreach ($url in $GitLibs) {
  Write-Host "   $url"
  arduino-cli lib install --git-url $url
}
Ok 'GitHub libraries installed'

Say 'Patching ResamplingReader.h (prevents nullptr crashes)'
$LibDir = Join-Path ((arduino-cli config get directories.user).Trim()) 'libraries'
$Src    = Join-Path $RepoRoot '_DOCS\ResamplingReader.h'
# folder name differs by install source (TeensyVariablePlayback vs teensy-variable-playback)
$Target = Get-ChildItem -Path $LibDir -Recurse -Filter 'ResamplingReader.h' -ErrorAction SilentlyContinue |
          Where-Object { $_.FullName -match 'variable.?playback' } | Select-Object -First 1
if ((Test-Path $Src) -and $Target) {
  Copy-Item -Force $Src $Target.FullName
  Ok ("patched " + $Target.FullName)
} else {
  Warn 'could not patch (src or target missing) - patch manually: see manual cap. 8.3'
}

if (-not $NoBuild) {
  Say 'Compile-check (Teensy 4.1, USB = Serial + MIDIx16)'
  # arduino-cli requires the main .ino to match the sketch folder name, so we
  # compile a temp copy named soundpauli_ni404\ (the repo folder name differs).
  $Tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("ichosynth_" + [System.Guid]::NewGuid().ToString('N').Substring(0,8))
  $Sketch = Join-Path $Tmp 'soundpauli_ni404'
  New-Item -ItemType Directory -Force -Path $Sketch | Out-Null
  Copy-Item (Join-Path $RepoRoot '*.ino') $Sketch
  Copy-Item (Join-Path $RepoRoot '*.h')   $Sketch
  arduino-cli compile -b $Fqbn $Sketch
  if ($LASTEXITCODE -eq 0) { Ok 'COMPILE OK - firmware builds cleanly' }
  else { Warn 'compile failed - see the errors above'; exit 1 }
  Remove-Item -Recurse -Force $Tmp
}

Say 'Done. Open soundpauli_ni404.ino in Arduino IDE and upload to your Teensy 4.1.'
