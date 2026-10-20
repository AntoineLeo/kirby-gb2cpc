#!/bin/sh
cd "$(dirname "$0")/.."
OUT="${1:-build/demo/shot.png}"
DSK="${2:-build/demo/demo.dsk}"
CAP="$LOCALAPPDATA/Caprice32/cap32-win64/cap32.exe"
TMP="$TEMP/cpcshots2"; rm -rf "$TMP"; mkdir -p "$TMP"
D=""; i=0; while [ $i -lt 8 ]; do D="$D\(CAP32_DELAY)"; i=$((i+1)); done
CMD=$(printf 'load"gfx.bin",&8000
%srun"code
%s\(CAP32_SCRNSHOT)\(CAP32_EXIT)' "$D" "$D")
DSKW=$(cygpath -w "$PWD/$DSK"); OUTP="$PWD/$OUT"
cd "$(dirname "$CAP")"
timeout 600 "$CAP" -O system.model=2 -O "file.sdump_dir=$(cygpath -w "$TMP")" -a "$CMD" "$DSKW" > "$TMP/log.txt" 2>&1
cp "$TMP"/screenshot_*.png "$OUTP" && echo "capture : $OUT"
