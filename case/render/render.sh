#!/usr/bin/env bash
# Render del case ichosynth con Blender su macOS/Linux, senza bloccare il computer:
# priorità bassa (nice 10) e pochi thread. Su Windows usa render.ps1.
#
#   case/render/render.sh                  # tutte le scene
#   case/render/render.sh hero s05_matrix  # solo alcune
#   case/render/render.sh PREVIEW hero     # anteprima veloce
#
# Blender: $BLENDER, altrimenti /Applications/Blender.app (macOS), altrimenti `blender` sul PATH.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

blender="${BLENDER:-}"
if [ -z "$blender" ] && [ -x /Applications/Blender.app/Contents/MacOS/Blender ]; then
  blender=/Applications/Blender.app/Contents/MacOS/Blender
fi
[ -z "$blender" ] && blender="$(command -v blender || true)"
[ -z "$blender" ] && { echo "Blender non trovato: installalo o imposta BLENDER=/percorso/blender" >&2; exit 1; }

python3 "$here/scenes.py"

cpus="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
threads=$(( cpus > 12 ? cpus - 10 : 2 ))
mkdir -p "$here/build" "$here/out"
rm -f "$here/build/blender.log" "$here/build/blender.err"
rc=0
nice -n 10 "$blender" -b --factory-startup -t "$threads" -P "$here/blender_render.py" -- \
  "$here/build" "$here/out" "$@" >"$here/build/blender.log" 2>"$here/build/blender.err" || rc=$?
grep '\[render\]' "$here/build/blender.log" || true
if grep -qE 'Traceback|Error:' "$here/build/blender.err"; then
  grep -vE 'use_nodes|DeprecationWarning' "$here/build/blender.err" | tail -n 15
  exit 1
fi
exit "$rc"
