#!/bin/sh
cd "$(dirname "$0")/.."
N="${1:-7}"; OUT="${2:-build/demo/key.png}"; DSK="${3:-build/kirby-demo2.dsk}"
CAP="$LOCALAPPDATA/Caprice32/cap32-win64/cap32.exe"; TMP="$TEMP/cpcshots3"; rm -rf "$TMP"; mkdir -p "$TMP"
D=""; i=0; while [ $i -lt $N ]; do D="$D\(CAP32_DELAY)"; i=$((i+1)); done
KEYS="PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP"
CMD=$(printf 'run"game
%s%s
%s\(CAP32_SCRNSHOT)\(CAP32_EXIT)' "$D" "$KEYS" "$D")
DSKW=$(cygpath -w "$PWD/$DSK"); OUTP="$PWD/$OUT"; cd "$(dirname "$CAP")"
timeout 600 "$CAP" -O system.model=2 -O "file.sdump_dir=$(cygpath -w "$TMP")" -a "$CMD" "$DSKW" > "$TMP/log.txt" 2>&1
cp "$TMP"/screenshot_*.png "$OUTP" && echo "capture : $OUT"
