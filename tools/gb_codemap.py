"""Carte code/donnees de la ROM, par banque, pour mgbdis et la couverture.

Methode :
  1. graines = points d'entree surs (vecteurs, $0100, $0150) et cibles de
     sauts/appels relevees par mgbdis dans chaque banque ;
  2. trace recursive SM83 depuis chaque graine, en suivant appels, sauts et
     branchements conditionnels, arret sur ret/jp/stop ;
  3. les octets atteints sont du code, le reste des donnees ; un chevauchement
     d'instructions est signale et laisse en zone incertaine.

Sortie :
  re/codemap.json      plages .code/.data par banque, entrees de routines,
                       zones incertaines
  re/coverage_map.json entrees de routines a poser en hooks dans gb_sim.py

Usage : python tools/gb_codemap.py [--listing re/listing] [--out re/codemap.json]
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gbrom import instructions, length, jr_target  # noqa: E402

LABEL_RE = re.compile(r'^(?:Call|Jump)_([0-9a-f]{3})_([0-9a-f]{4}):')
JUMP16 = (0xC3, 0xC2, 0xCA, 0xCD, 0xC4, 0xCC, 0xD2, 0xDA, 0xD4, 0xDC)
CALL16 = (0xCD, 0xC4, 0xCC, 0xD4, 0xDC)
JUMP8 = (0x18, 0x20, 0x28, 0x30, 0x38)
ENDS = (0xC3, 0xC9, 0x18, 0xD9)


def labels(listing_dir, banks):
    """Cibles relevees par mgbdis : (toutes, cibles d'appel)."""
    seeds = {b: set() for b in range(banks)}
    calls = {b: set() for b in range(banks)}
    for b in range(banks):
        path = os.path.join(listing_dir, f'bank_{b:03x}.asm')
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8', errors='replace') as f:
            for line in f:
                m = LABEL_RE.match(line)
                if m:
                    bank = int(m.group(1), 16)
                    addr = int(m.group(2), 16)
                    if 0 <= bank < banks:
                        seeds[bank].add(addr)
                        if line.startswith('Call_'):
                            calls[bank].add(addr)
    return seeds, calls


def trace_bank(rom, bank, seeds, call_seeds):
    """Octets de code (masque) et entrees de routines executees statiquement.

    Banque 0 : region fixe 0000-3FFF. Banques >0 : region commutable 4000-7FFF.
    Les hooks de couverture ne vont que sur des debuts de routines (cible de
    call ou vecteur), jamais au milieu d'une instruction.
    """
    base = bank * 0x4000
    data = rom[base:base + 0x4000]
    lo, hi = (0x0000, 0x4000) if bank == 0 else (0x4000, 0x8000)

    def byte(a):
        return data[a if bank == 0 else a - 0x4000]

    code = bytearray(0x8000)          # adresses logiques 0000-7FFF
    starts = set()
    seeds = {a for a in seeds if lo <= a < hi}
    entries = {a for a in call_seeds if lo <= a < hi}
    uncertain = []
    todo = list(seeds)
    while todo:
        pc = todo.pop()
        while lo <= pc < hi:
            if pc in starts:
                break
            if code[pc]:
                # deja trace : chevauchement seulement si ce n'est pas un debut
                uncertain.append(pc)
                break
            op = byte(pc)
            if op not in instructions or instructions[op].startswith('ILLEGAL'):
                uncertain.append(pc)
                break
            n = length(op)
            if pc + n > hi:
                uncertain.append(pc)
                break
            starts.add(pc)
            for i in range(n):
                code[pc + i] = 1
            nxt = pc + n
            if op == 0xCB:
                pc = nxt
                continue
            if op in JUMP16:
                t = byte(pc + 1) | (byte(pc + 2) << 8)
                if lo <= t < hi:
                    todo.append(t)
                    if op in CALL16:
                        entries.add(t)
                if op == 0xC3:
                    break
            if op in JUMP8:
                r = byte(pc + 1)
                t = pc + 2 + (r - 256 if r > 127 else r)
                if lo <= t < hi:
                    entries.add(t)
                    todo.append(t)
                if op == 0x18:
                    break
            if op == 0xC9 or op == 0xD9:
                break
            pc = nxt
    ranges = []
    a = lo
    while a < hi:
        if code[a]:
            b = a
            while b < hi and code[b]:
                b += 1
            ranges.append([a, b])
            a = b
        else:
            a += 1
    # une entree n'est retenue que si elle tombe sur un debut d'instruction
    entries = {a for a in entries if a in starts}
    return ranges, sorted(entries), sorted(set(uncertain))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=os.path.join(ROOT, 're', 'game.gb'))
    ap.add_argument('--listing', default=os.path.join(ROOT, 're', 'listing'))
    ap.add_argument('--out', default=os.path.join(ROOT, 're', 'codemap.json'))
    ap.add_argument('--seeds', default=os.path.join(ROOT, 're', 'seeds.json'))
    ap.add_argument('--raw-listing', help='listing mgbdis sans .sym, pour fabriquer les graines')
    args = ap.parse_args()
    rom = open(args.rom, 'rb').read()
    banks = len(rom) // 16384
    if args.raw_listing:
        seeds, calls = labels(args.raw_listing, banks)
        os.makedirs(os.path.dirname(args.seeds), exist_ok=True)
        with open(args.seeds, 'w', encoding='utf-8') as f:
            json.dump({'seeds': {b: sorted(v) for b, v in seeds.items()},
                       'calls': {b: sorted(v) for b, v in calls.items()}}, f)
        print(f'graines -> {os.path.relpath(args.seeds, ROOT)} '
              f'({sum(len(v) for v in seeds.values())} cibles)')
        return 0
    if os.path.exists(args.seeds):
        with open(args.seeds, encoding='utf-8') as f:
            raw = json.load(f)
        seeds = {int(k): set(v) for k, v in raw['seeds'].items()}
        call_seeds = {int(k): set(v) for k, v in raw['calls'].items()}
    else:
        seeds, call_seeds = labels(args.listing, banks)
    safe = {0: {0x0040, 0x0048, 0x0050, 0x0058, 0x0060, 0x0100, 0x0150}}
    result = {'banks': [], 'entries': [], 'uncertain': []}
    for b in range(banks):
        s = set(seeds.get(b, ())) | set(safe.get(b, ()))
        c = set(call_seeds.get(b, ())) | set(safe.get(b, ()))
        if b > 0:
            s = {a for a in s if 0x4000 <= a < 0x8000}
            c = {a for a in c if 0x4000 <= a < 0x8000}
        else:
            # zone des vecteurs : seuls les vecteurs sont du code sur
            s = {a for a in s if a >= 0x0150} | set(safe.get(b, ()))
            c = {a for a in c if a >= 0x0150} | set(safe.get(b, ()))
        ranges, entries, uncertain = trace_bank(rom, b, s, c)
        result['banks'].append({'bank': b, 'code': ranges,
                                'code_bytes': sum(e - s for s, e in ranges)})
        result['entries'] += [{'bank': b, 'addr': a} for a in entries]
        if uncertain:
            result['uncertain'].append({'bank': b, 'addrs': uncertain[:200],
                                        'count': len(uncertain)})
        print(f'banque {b:02x} : {sum(e - s for s, e in ranges):5d} octets de code, '
              f'{len(entries):4d} entrees, {len(uncertain)} incertitudes')
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=1)
    cov = os.path.join(os.path.dirname(args.out), 'coverage_map.json')
    entries = list({(e['bank'], e['addr']) for e in result['entries']})
    entries.sort()
    with open(cov, 'w', encoding='utf-8') as f:
        json.dump([{'bank': b, 'addr': a} for b, a in entries], f, indent=0)
    print(f'-> {os.path.relpath(args.out, ROOT)} ({len(result["entries"])} entrees)')
    print(f'-> {os.path.relpath(cov, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
