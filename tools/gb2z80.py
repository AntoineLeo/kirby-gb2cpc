"""Traduction statique de la logique GB (SM83) en Z80 pour sjasmplus.

Lit la ROM, suit le code atteint depuis CFG.ROOTS (gb_closure) et écrit
CFG.LOGIC_OUT (par défaut asm/gb/gb_logic.asm).

Principes :
- la RAM GB garde ses adresses ($C000-$DFFF, $FF80-$FFFE) : le programme
  Spectrum les réserve, donc les accès mémoire se traduisent tels quels ;
- chaque instruction SM83 donne son équivalent Z80 (identique pour
  l'essentiel ; ld [hl+], ldh, swap, rst sont réécrits) ;
- tous les sauts deviennent des JP vers des étiquettes G_xxxx (adresse GB) :
  le code traduit est plus long, un JR serait souvent hors de portée ;
- les tables des rst de saut deviennent des DW, les données en ligne des DB ;
- les appels listés dans CFG.STUBS vont vers des routines Spectrum écrites
  à la main (son, changements d'écran, VRAM...) ;
- CFG.PATCHES remplace une instruction GB par du code Z80 (réglages voulus).

Banques commutables (CFG.BANK_ENTRIES) : chaque banque est traduite dans son
propre fichier (gb_logic_bNN.asm) avec des étiquettes BNN_xxxx. Les cibles
dans la fenêtre $4000-$7FFF sont émises en adresse GB brute : à l'exécution
elles tombent sur les tramplins de l'image de banque (`jp BNN_xxxx` posés sur
les étiquettes), comme le GB exécute le code de la banque courante.

Différences SM83/Z80 à connaître (signalées par des ATTENTION) :
- rlca/rrca/rla/rra : le GB met Z à 0, le Z80 ne touche pas à Z ;
- swap : traduit pour A seulement (rrca x4 + or a) ;
- add sp,e / ld hl,sp+e / ld [a16],sp / stop : pas d'équivalent, une ligne
  ASSERT 0 fait échouer l'assemblage à l'endroit à traiter à la main.
"""
import os

import gb_closure as gc
from gbrom import CFG, ROM, instructions, cb_instructions, length, w, path, inline_len, \
    RST_JUMPTABLE, RST_INLINE_DATA

OUT = path(getattr(CFG, 'LOGIC_OUT', 'asm/gb/gb_logic.asm'))
STUB_LABEL = {a: l for a, l in CFG.STUBS.items() if l}
PATCHES = dict(getattr(CFG, 'PATCHES', {}))
CODE_PTRS = set(getattr(CFG, 'CODE_PTRS', []))
DATA_PTRS = set(getattr(CFG, 'DATA_PTRS', []))
DATA_BLOCKS = list(getattr(CFG, 'DATA_BLOCKS', []))
DATA_LABELS = set(getattr(CFG, 'DATA_LABELS', []))
BANK_ENTRIES = dict(getattr(CFG, 'BANK_ENTRIES', {}))
ROT_NO_Z = {0x07, 0x0F, 0x17, 0x1F}
NO_Z80 = {0xE8, 0xF8, 0x08, 0x10}
# Déplacement de la RAM GB (machines sans RAM en $C000/$FF80) : CFG.RAM_MAP(adresse
# GB) -> adresse cible, ou None si l'adresse n'est pas de la RAM déplacée.
RAM_MAP = getattr(CFG, 'RAM_MAP', lambda a: None)


def ram(a):
    """Adresse GB -> adresse cible (inchangée hors de la RAM déplacée)."""
    m = RAM_MAP(a)
    return a if m is None else m


def in_window(a):
    return 0x4000 <= a < 0x8000


def lab(a, bank=None):
    if bank is not None and in_window(a):
        return f'B{bank:02X}_{a:04X}'
    return f'G_{a:04X}'


class Reader:
    """Lecture ROM banque 0 ou fenêtre d'une banque commutable."""

    def __init__(self, bank=None):
        self.bank = bank

    def b(self, a):
        if self.bank is not None and in_window(a):
            return ROM[self.bank * 0x4000 + a - 0x4000]
        return ROM[a]

    def w(self, a):
        return self.b(a) | (self.b(a + 1) << 8)


def translate(bank=None, extra_roots=None):
    rd = Reader(bank)
    if bank is not None:
        roots = sorted(BANK_ENTRIES[bank])
    elif extra_roots:
        roots = dict(gc.ROOTS)
        for a in extra_roots:
            roots.setdefault(a, 'appel depuis une banque')
    else:
        roots = None
    starts, targets, tables, _, _, _, _, calls_b0 = gc.explore(bank=bank, roots=roots)
    labels = set(targets) | set(ROOTS_USED(bank, roots)) | (set() if bank is not None else CODE_PTRS)
    for ents in tables.values():
        labels |= set(ents)
    out = ['; Fichier généré par tools/gb2z80.py à partir de la ROM Game Boy.',
           '; Ne pas modifier à la main : relancer le script.', '']
    warnings = []
    raw_win = set()
    prev_end = None
    prev_falls = False
    prev_rot_no_z = False
    for pc in sorted(starts):
        if prev_falls and prev_end != pc:
            out.append(f'        jp {lab(prev_end, bank)}          ; continuité du code GB')
            labels.add(prev_end)
        if pc in labels or pc in STUB_LABEL:
            out.append(f'{lab(pc, bank)}:')
        op = rd.b(pc)
        n = length(op)
        nxt = pc + n
        m = instructions[op]
        d8 = rd.b(pc + 1) if n >= 2 else 0
        d16 = rd.w(pc + 1) if n == 3 else 0
        comment = f'; ${pc:04X}'
        falls = True
        if pc in PATCHES:
            out.append(f'        {PATCHES[pc]:30s}{comment} (réglage : {m})')
            prev_end = nxt
            prev_falls = not PATCHES[pc].startswith('jp ')
            prev_rot_no_z = False
            continue

        def target16(v):
            if v in STUB_LABEL:
                return STUB_LABEL[v]
            if in_window(v):
                raw_win.add(v)
                return f'${v:04X}'
            if v in gc.STUBS:
                warnings.append(f'{pc:04x} appel du stub sans routine {v:04x}')
            return lab(v, bank)

        if op == 0xCB:
            cbm = cb_instructions[rd.b(pc + 1)]
            if cbm.startswith('swap'):
                if cbm == 'swap a':
                    z80 = ['rrca', 'rrca', 'rrca', 'rrca', 'or a']
                else:
                    r = cbm.split()[1]
                    if r == '[hl]':
                        z80 = ['push bc', 'push af', 'ld a,(hl)', 'rrca', 'rrca',
                               'rrca', 'rrca', 'ld (hl),a', 'or a', 'pop bc',
                               'ld a,b', 'pop bc']
                    else:
                        z80 = ['push bc', 'push af', f'ld a,{r}', 'rrca', 'rrca',
                               'rrca', 'rrca', f'ld {r},a', 'or a', 'pop bc',
                               'ld a,b', 'pop bc']
            else:
                z80 = [cbm.replace('[hl]', '(hl)')]
        elif op in RST_JUMPTABLE:                            # rst de saut + table
            out.append(f'        {"call " + RST_JUMPTABLE[op]:30s}{comment}')
            out.append('        dw ' + ', '.join(lab(t, bank) for t in tables[nxt]))
            prev_end = nxt + 2 * len(tables[nxt])
            prev_falls = False
            prev_rot_no_z = False
            continue
        elif op in RST_INLINE_DATA:                          # rst + données en ligne
            cnt = inline_len(pc)
            out.append(f'        {"call " + RST_INLINE_DATA[op]:30s}{comment}')
            out.append('        db ' + ', '.join(f'${rd.b(a):02X}' for a in range(nxt, nxt + cnt)))
            prev_end = nxt + cnt
            prev_falls = True
            prev_rot_no_z = False
            continue
        elif op in NO_Z80:
            if op == 0x08:                                  # ld [a16],sp
                z80 = ['push af', 'push hl', 'ld hl,0', 'add hl,sp',
                       f'ld (${ram(d16):04X}),hl', 'pop hl', 'pop af']
            elif op == 0xF8 and d8 == 0:                    # ld hl,sp+0 -> hl=sp
                z80 = ['ld hl,0', 'add hl,sp']
                warnings.append(f'{pc:04x} ld hl,sp+0 : drapeaux GB non conservés')
            elif op == 0x10:                                # stop
                z80 = ['nop']
                warnings.append(f'{pc:04x} stop traduit en nop')
            else:
                warnings.append(f'{pc:04x} {m} : pas d\'équivalent Z80')
                z80 = [f'ASSERT 0 ; NON TRADUIT : {m}']
        elif m == 'rst vec':
            z80 = [f'call G_RST{op & 0x38:02X}']
        elif m in ('ld a,[hl+]', 'ld a,[hl-]'):
            z80 = ['ld a,(hl)', 'inc hl' if '+' in m else 'dec hl']
        elif m in ('ld [hl+],a', 'ld [hl-],a'):
            z80 = ['ld (hl),a', 'inc hl' if '+' in m else 'dec hl']
        elif m == 'ldh [a8],a':
            z80 = [f'ld (${ram(0xFF00 + d8):04X}),a']
        elif m == 'ldh a,[a8]':
            z80 = [f'ld a,(${ram(0xFF00 + d8):04X})']
        elif m == 'ld [c],a':                                # ld ($FF00+c),a
            z80 = ['push bc', f'ld b,${ram(0xFF80) >> 8:02X}', 'ld (bc),a', 'pop bc']
            warnings.append(f'{pc:04x} ld [$ff00+c],a (vérifier : registre matériel ?)')
        elif m == 'ld a,[c]':
            z80 = ['push bc', f'ld b,${ram(0xFF80) >> 8:02X}', 'ld a,(bc)', 'pop bc']
            warnings.append(f'{pc:04x} ld a,[$ff00+c] (vérifier : registre matériel ?)')
        elif m in ('ld [a16],a', 'ld a,[a16]'):
            z80 = [m.replace('[a16]', f'(${ram(d16):04X})')]
            if RAM_MAP(0xC000) is not None and RAM_MAP(d16) is None and d16 >= 0x8000:
                warnings.append(f'{pc:04x} accès RAM GB non déplacée {d16:04x}')
            if d16 < 0x4000:
                warnings.append(f'{pc:04x} accès ROM {d16:04x}')
        elif 'pc+r8' in m:
            r = d8 - 256 if d8 > 127 else d8
            t = nxt + r
            cond = m.split()[1].split(',')[0] if ',' in m else ''
            z80 = [f'jp {cond + "," if cond else ""}{lab(t, bank)}']
            falls = bool(cond)
            if prev_rot_no_z and cond in ('z', 'nz'):
                warnings.append(f'{pc:04x} saut sur Z après rotation')
        elif 'a16' in m:                                     # jp/call
            z80 = [m.replace('a16', target16(d16))]
            if m == 'jp a16':
                falls = False
        elif 'd16' in m:
            if d16 in CODE_PTRS:
                s = lab(d16, bank)
            elif d16 in DATA_PTRS:
                s = f'D_{d16:04X}'
            else:
                s = f'${ram(d16):04X}'
            z80 = [m.replace('d16', s)]
        else:
            t = m.replace('d8', f'${d8:02X}').replace('[', '(').replace(']', ')')
            parts = t.split(None, 1)
            if parts[0] in ('add', 'adc', 'sbc') and len(parts) == 2 and ',' not in parts[1]:
                t = f'{parts[0]} a,{parts[1]}'
            if t == 'reti':
                t = 'ret'
            if t == 'jp hl':
                t = 'jp (hl)'
                falls = False
            if t == 'halt':
                warnings.append(f'{pc:04x} halt (attend l\'interruption Spectrum)')
            if m in ('ld h,d8', 'ld d,d8', 'ld b,d8') and d8 < 0x40:
                warnings.append(f'{pc:04x} {m} : base de pointeur vers la ROM ${d8:02X}xx ?')
            z80 = [t]
            if m in ('ret', 'reti'):
                falls = False
        prev_rot_no_z = op in ROT_NO_Z
        for i, ins in enumerate(z80):
            out.append(f'        {ins:30s}{comment if i == 0 else ""}')
        prev_end = nxt
        prev_falls = falls
    emitted = {l.split(':')[0] for l in out if l.endswith(':')}
    missing = sorted(a for a in labels
                     if lab(a, bank) not in emitted and a not in STUB_LABEL and a not in calls_b0)
    if bank is None:
        out += data_blocks()
    out_path = OUT if bank is None else bank_out_path(bank)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    where = 'banque 0' if bank is None else f'banque {bank:02X}'
    print(f'{where} : {len(starts)} instructions GB traduites -> {out_path}')
    if missing:
        print('ÉTIQUETTES MANQUANTES :', ' '.join(f'{a:04x}' for a in missing))
    for x in warnings:
        print('ATTENTION :', x)
    return calls_b0, raw_win


def ROOTS_USED(bank, roots):
    if bank is not None:
        return set(roots)
    return set(gc.ROOTS) | set(roots or [])


def bank_out_path(bank):
    return OUT[:-4] + f'_b{bank:02x}.asm'


def data_blocks():
    """Données de la ROM lues par la logique : 'dw' = table de pointeurs vers
    d'autres données (étiquetées D_xxxx), 'db' = octets bruts."""
    if not DATA_BLOCKS:
        return []
    out = ['', '; --- Données de la ROM lues par la logique ---']
    names = set(DATA_PTRS) | DATA_LABELS
    for start, end, kind in DATA_BLOCKS:
        if kind == 'dw':
            names |= {w(a) for a in range(start, end, 2)}
    for start, end, kind in DATA_BLOCKS:
        if kind == 'dw':
            out.append(f'D_{start:04X}:')
            out.append('        dw ' + ', '.join(f'D_{w(a):04X}' for a in range(start, end, 2)))
            continue
        # Alignement sur l'adresse GB d'origine : les lectures par pointeur
        # calcule (ld h,imm / ld l,calcule) gardent leurs offsets d'octet.
        out.append(f'        defs ((${start & 0xFF:02X} - ($ & $FF)) & $FF)')
        a = start
        while a < end:
            if a in names:
                out.append(f'D_{a:04X}:')
            b = a + 1
            while b < end and b - a < 16 and b not in names:
                b += 1
            out.append('        db ' + ', '.join(f'${x:02X}' for x in ROM[a:b]))
            a = b
    return out


if __name__ == '__main__':
    import json
    calls_b0 = set()
    raw_all = {}
    for bank in sorted(BANK_ENTRIES):
        cb, raw = translate(bank=bank)
        calls_b0 |= cb
        raw_all[bank] = raw
    _, raw0 = translate(extra_roots=sorted(calls_b0))
    # Tramplins de fenetre : entrees de banque + cibles des appels/sauts directs
    # emis en adresse brute (les sauts courts gardent des etiquettes).
    manifest = {}
    for bank in sorted(BANK_ENTRIES):
        ents = set(BANK_ENTRIES[bank]) | raw_all.get(bank, set())
        manifest[f'{bank:02x}'] = sorted(ents)
    manifest['00_raw'] = sorted(raw0)
    out = os.path.join(os.path.dirname(OUT), 'win_entries.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(manifest, f)
    print(f'tramplins de fenetre -> {out}')
