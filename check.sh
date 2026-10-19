#!/bin/sh
# Controle unique du projet.
#   sh check.sh rapide    construction + comparaison logique niveau 1 (600 tours)
#   sh check.sh complet   idem + tous les scenarios + frontiere + etats
# S'arrete a la premiere erreur et rend un code d'echec.
set -e
cd "$(dirname "$0")"

MODE="${1:-rapide}"
PY=python
export GB2ZX_CONFIG="$(pwd)/_cfg_l1.py"
echo "== check.sh $MODE =="

echo "-- extraction / images de reference"
$PY -X utf8 tools/gb_extract.py

echo "-- listing reassemble"
$PY -X utf8 tools/gb_listing.py --check

echo "-- references et documents"
$PY -X utf8 tools/verify_refs.py $([ "$MODE" = complet ] && echo "" || echo "--quick")

echo "-- traduction multi-banques"
$PY -X utf8 tools/gb2z80.py

echo "-- banc d'essai niveau 1"
sjasmplus --nologo --msg=war --sym=build/l1/test.sym build/l1/test.asm

echo "-- comparaison logique niveau 1 (600 tours)"
if $PY -X utf8 tools/l1_cmp.py 2>&1 | tee /tmp/l1_cmp.log | grep -qE "^0 trames differentes sur"; then
    echo "   OK : 0 trames differentes"
else
    echo "   ECART niveau 1 (detail dans /tmp/l1_cmp.log)"
    exit 1
fi

echo "-- traces (comparaison GB contre GB)"
$PY -X utf8 tools/gb_cmp.py self boot
$PY -X utf8 tools/gb_cmp.py self fileselect
$PY -X utf8 tools/gb_cmp.py self level1
$PY -X utf8 tools/gb_cmp.py selftest level1
if [ "$MODE" = complet ]; then
    $PY -X utf8 tools/gb_cmp.py self level1_actions
    echo "-- frontiere"
    $PY -X utf8 tools/gb_boundary.py
    echo "-- carte code/donnees"
    $PY -X utf8 tools/gb_codemap.py >/dev/null
    echo "-- listing regenere apres la carte"
    $PY -X utf8 tools/gb_listing.py
fi

echo "== OK ($MODE) =="
