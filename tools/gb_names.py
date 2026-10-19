"""Fichier de noms unique + conversion vers le .sym lu par mgbdis.

Le fichier de noms (re/names.txt) est la seule source de noms. Format :
    banque:adresse<TAB>nom<TAB>commentaire sur une ligne
    # commentaire
Exemple :
    00:0150<TAB>Reset<TAB>entree apres le saut du vecteur $0100
    00:0159<TAB>VBlank<TAB>suite du vecteur $0040 (registres sauves)

On n'y met que ce qui est sur : vecteurs, point d'entree, routines lues dans
le code appelant. Les hypotheses vont dans docs/frontiere.md, pas ici.

gb_names.py produit re/game.sym (blocs .code/.data de re/codemap.json +
etiquettes), lu par mgbdis. Les plages de code non executees restent du code
potentiel et sont signalees dans codemap.json.

Usage : python tools/gb_names.py [--names re/names.txt] [--out re/game.sym]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read_names(path):
    names = []
    if not os.path.exists(path):
        return names
    with open(path, encoding='utf-8') as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) < 2:
                print(f'{path}:{n}: ligne ignoree (attendu banque:adresse<TAB>nom)', file=sys.stderr)
                continue
            bank_addr, name = parts[0].strip(), parts[1].strip()
            comment = parts[2].strip() if len(parts) > 2 else ''
            bank_s, _, addr_s = bank_addr.partition(':')
            try:
                bank, addr = int(bank_s, 16), int(addr_s, 16)
            except ValueError:
                print(f'{path}:{n}: adresse invalide {bank_addr}', file=sys.stderr)
                continue
            names.append({'bank': bank, 'addr': addr, 'name': name, 'comment': comment})
    return names


def make_sym(codemap, names, out):
    by_bank = {b['bank']: b for b in codemap['banks']}
    label_map = {(n['bank'], n['addr']): n['name'] for n in names}
    lines = [
        '; genere par tools/gb_names.py depuis re/codemap.json et re/names.txt',
        '; blocs .code/.data par banque (mgbdis)',
    ]
    for bank in sorted(by_bank):
        b = by_bank[bank]
        ranges = []
        for lo, hi in b['code']:
            ranges.append((lo, hi, 'code'))
        # donnees = complement dans la fenetre de la banque
        lo0, hi0 = (0x0000, 0x4000) if bank == 0 else (0x4000, 0x8000)
        a = lo0
        for lo, hi in b['code']:
            if a < lo:
                ranges.append((a, lo, 'data'))
            a = max(a, hi)
        if a < hi0:
            ranges.append((a, hi0, 'data'))
        for lo, hi, kind in sorted(ranges):
            lines.append(f'{bank:02x}:{lo:04x} .{kind}:{hi - lo:x}')
        for (nb, na), name in sorted(label_map.items()):
            if nb == bank:
                lines.append(f'{bank:02x}:{na:04x} {name}')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return len(names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--codemap', default=os.path.join(ROOT, 're', 'codemap.json'))
    ap.add_argument('--names', default=os.path.join(ROOT, 're', 'names.txt'))
    ap.add_argument('--out', default=os.path.join(ROOT, 're', 'game.sym'))
    args = ap.parse_args()
    with open(args.codemap, encoding='utf-8') as f:
        codemap = json.load(f)
    names = read_names(args.names)
    n = make_sym(codemap, names, args.out)
    print(f'{n} noms -> {os.path.relpath(args.out, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
