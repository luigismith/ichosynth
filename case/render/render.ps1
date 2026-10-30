# Render del case ichosynth con Blender, senza bloccare il PC:
# priorità "sotto il normale" e 6 thread su 16.
#
#   powershell -File case/render/render.ps1                 # tutte le scene
#   powershell -File case/render/render.ps1 hero s5_window  # solo alcune
#   powershell -File case/render/render.ps1 PREVIEW hero    # anteprima veloce
param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $Scenes)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$blender = Get-ChildItem 'C:\Program Files\Blender Foundation' -Recurse -Filter blender.exe -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
if (-not $blender) { Write-Error 'Blender non trovato in C:\Program Files\Blender Foundation'; exit 1 }

python "$here\scenes.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$threads = [Math]::Max(2, [Environment]::ProcessorCount - 10)
$bargs = @('-b', '--factory-startup', '-t', "$threads", '-P', "`"$here\blender_render.py`"", '--', "`"$here\build`"", "`"$here\out`"")
if ($Scenes) { $bargs += $Scenes }
Remove-Item "$here\build\blender.log", "$here\build\blender.err" -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $blender -ArgumentList $bargs -NoNewWindow -PassThru `
    -RedirectStandardOutput "$here\build\blender.log" -RedirectStandardError "$here\build\blender.err"
if (-not $p) { Write-Error 'Blender non partito'; exit 1 }
try { $p.PriorityClass = 'BelowNormal' } catch {}
$p.WaitForExit()
Select-String -Path "$here\build\blender.log" -Pattern '\[render\]' | ForEach-Object { $_.Line }
$err = Select-String -Path "$here\build\blender.err" -Pattern 'Traceback|Error:' -SimpleMatch:$false
if ($err) { Get-Content "$here\build\blender.err" | Select-String -NotMatch 'use_nodes|DeprecationWarning' | Select-Object -Last 15; exit 1 }
exit $p.ExitCode
