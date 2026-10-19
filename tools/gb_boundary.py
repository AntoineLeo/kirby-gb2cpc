"""Frontiere du portage : releve automatique des acces au materiel Game Boy.

Lit le listing (re/listing, avec adresses) et produit :
  re/boundary.json  : chaque acces classe (VRAM, OAM, joypad, son, LCD,
                      interruptions, banques, attente VBlank, SRAM...), avec
                      banque:adresse, instruction, routine englobante, appelants
                      et ecritures connues en RAM ;
  docs/frontiere.md : synthese par categorie (le detail reste dans le JSON).

Les routines englobantes viennent de re/codemap.json (entrees de routines).
Les appelants sont les `call $ADDR` du listing vers cette entree (meme banque
pour la zone commutable, banque 0 pour $0000-$3FFF).

Usage : python tools/gb_boundary.py
"""
import bisect
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

LINE_RE = re.compile(r'^(.*?)\s*;\s*\$([0-9a-fA-F]{4}):\s*\$([0-9a-fA-F]{2})')
SECTION_RE = re.compile(r'SECTION .*?(?:ROMX\[\$4000\], BANK\[\$([0-9a-fA-F]+)\]|ROM0\[\$0\])')
ADDR_RE = re.compile(r'\$([0-9a-fA-F]{4})')


def classify(addr, text):
    t = text.lower()
    if addr is not None:
        if 0x8000 <= addr <= 0x9FFF:
            return 'vram'
        if 0xFE00 <= addr <= 0xFE9F:
            return 'oam'
        if 0xFF00 <= addr <= 0xFF7F:
            if addr == 0xFF00:
                return 'joypad'
            if 0xFF10 <= addr <= 0xFF3F:
                return 'sound'
            if 0xFF40 <= addr <= 0xFF4B:
                return 'lcd'
            return 'io'
        if 0xA000 <= addr <= 0xBFFF:
            return 'sram'
    if re.search(r'\b(reti|di|ei|halt|stop)\b', t) or addr in (0xFFFF, 0xFF0F):
        return 'interruptions'
    if re.search(r'\bld\s*\[\$([0-5][0-9a-f]{3})\],\s*a', t):
        return 'banques'
    return None


def parse(listing_dir):
    routines = []
    for fn in sorted(os.listdir(listing_dir)):
        if not fn.startswith('bank_'):
            continue
        path = os.path.join(listing_dir, fn)
        bank = None
        with open(path, encoding='utf-8', errors='replace') as f:
            for line in f:
                m = SECTION_RE.search(line)
                if m:
                    bank = int(m.group(1), 16) if m.group(1) else 0
                    continue
                m = LINE_RE.match(line)
                if not m:
                    continue
                text = m.group(1).strip()
                addr = int(m.group(2), 16)
                routines.append({'bank': bank, 'addr': addr, 'text': text})
    return routines


def load_codemap():
    with open(os.path.join(ROOT, 're', 'codemap.json'), encoding='utf-8') as f:
        cm = json.load(f)
    entries = {}
    for e in cm['entries']:
        entries.setdefault(e['bank'], []).append(e['addr'])
    for b in entries:
        entries[b] = sorted(set(entries[b]))
    return entries


def enclosing(entries, bank, addr):
    c = entries.get(bank, [])
    import bisect
    i = bisect.bisect_right(c, addr) - 1
    return c[i] if i >= 0 else addr


def collect():
    ins = parse(os.path.join(ROOT, 're', 'listing'))
    entries = load_codemap()
    # appelants : cible -> liste (banque, adresse)
    callers = {}
    for x in ins:
        m = re.search(r'\bcall\s+\$([0-9a-fA-F]{4})', x['text'])
        if m:
            target = int(m.group(1), 16)
            callers.setdefault(target, []).append((x['bank'], x['addr']))
    items = []
    # ecritures RAM par banque (adresse d'instruction -> adresses ecrites)
    write_at = {}
    for y in ins:
        ws = [a for a in addr_writes(y['text']) if 0xA000 <= a <= 0xDFFF or 0xFF80 <= a <= 0xFFFE]
        if ws:
            write_at.setdefault(y['bank'], []).append((y['addr'], ws))
    for b in write_at:
        write_at[b].sort()
    for x in ins:
        text = x['text']
        low = text.lower()
        kind = None
        detail = None
        # adresse immediat dans l'instruction
        addrs = [int(a, 16) for a in ADDR_RE.findall(text)]
        for a in addrs:
            k = classify(a, text)
            if k:
                kind, detail = k, a
                break
        if not kind:
            k = classify(None, text)
            if k:
                kind, detail = k, None
        if not kind:
            # attente de l'image (lecture de LY / STAT)
            if re.search(r'\$ff44|\$ff41', low):
                if re.search(r'\bldh\s+a', low) or re.search(r'\bld\s+a', low):
                    kind, detail = 'attente_image', (0xFF44 if '$ff44' in low else 0xFF41)
        if not kind:
            continue
        bank, addr = x['bank'], x['addr']
        routine = enclosing(entries, bank, addr)
        cl = entries.get(bank, [])
        i = bisect.bisect_right(cl, routine)
        end = cl[i] if i < len(cl) else (0x4000 if bank == 0 else 0x8000)
        wl = write_at.get(bank, [])
        lo = bisect.bisect_left(wl, (routine,))
        hi = bisect.bisect_left(wl, (end,))
        writes = sorted({a for _, ws in wl[lo:hi] for a in ws})
        items.append({
            'kind': kind, 'detail': detail, 'bank': bank, 'addr': addr,
            'routine': routine, 'instruction': text,
            'callers': [f'{b:02x}:{a:04x}' for b, a in callers.get(routine, [])][:12],
            'writes': sorted(set(writes)),
        })
    return items


def addr_writes(text):
    low = text.lower()
    out = []
    for a in ADDR_RE.findall(text):
        v = int(a, 16)
        # ld [nn],a / ld [nn],sp / ldh [nn],a / ld hl,nn suivi d'ecritures
        if re.search(r'\b(ld|ldh)\s*\[\$' + a.lower() + r'\],', low):
            out.append(v)
    return out


def main():
    items = collect()
    with open(os.path.join(ROOT, 're', 'boundary.json'), 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=1)
    kinds = {}
    for it in items:
        kinds.setdefault(it['kind'], []).append(it)
    print(f'{len(items)} acces materiel releves dans {len(kinds)} categories -> re/boundary.json')
    for k, v in sorted(kinds.items()):
        print(f'  {k:14s} {len(v):5d} acces, {len(set((x["bank"], x["routine"]) for x in v))} routines')
    return 0


if __name__ == '__main__':
    sys.exit(main())

