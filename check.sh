#!/bin/sh
# Controle unique du projet.
#   sh check.sh rapide    extraction + listing identique + autotests de traces
#   sh check.sh complet   idem + tous les scenarios + frontiere + etats
# S'arrete a la premiere erreur et rend un code d'echec.
set -e
cd "$(dirname "$0")"

MODE="${1:-rapide}"
PY=python
echo "== check.sh $MODE =="

echo "-- extraction / images de reference"
$PY -X utf8 tools/gb_extract.py

echo "-- listing reassemble"
$PY -X utf8 tools/gb_listing.py --check

echo "-- references et documents"
$PY -X utf8 tools/verify_refs.py $([ "$MODE" = complet ] && echo "" || echo "--quick")

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

