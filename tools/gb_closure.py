"""Code GB atteint depuis les routines de logique du jeu (CFG.ROOTS).

C'est la « fermeture » à traduire en Z80 : tout ce qui est appelé depuis les
racines, sauf les adresses remplacées par du code Spectrum (CFG.STUBS).
Lancé seul, affiche ce qu'il faut régler avant de traduire :
  - appels vers les stubs ;
  - accès au matériel GB ($FF00-$FF7F, VRAM, OAM) : à remplacer (stub, patch) ;
  - immédiats 16 bits < $8000 : pointeurs possibles vers la ROM, à classer en
    CODE_PTRS / DATA_PTRS / constantes ;
  - instructions sans équivalent Z80 direct.

explore(bank, roots) explore une banque commutable : la fenêtre $4000-$7FFF
lit les octets de la banque demandée, les sauts intra-fenêtre restent dans la
banque, les cibles < $4000 sont rendues comme « appels banque 0 » (à explorer
séparément).
"""
from gbrom import CFG, ROM, instructions, cb_instructions, length, \
    RST_JUMPTABLE, RST_INLINE_DATA, TABLE_LEN, JUMPS16, JUMPS8, ENDS

ROOTS = dict(CFG.ROOTS)
STUBS = dict(CFG.STUBS)
SWITCHABLE_STUB = getattr(CFG, 'SWITCHABLE_STUB', None)
CODE_PTRS = list(getattr(CFG, 'CODE_PTRS', []))


def explore(bank=None, roots=None):
    starts, targets, calls_to_stub = set(), set(), {}
    hw, imm16, special = [], [], []
    calls_b0 = set()
    tables = {}

    def b(a):
        if bank is not None and 0x4000 <= a < 0x8000:
            return ROM[bank * 0x4000 + a - 0x4000]
        return ROM[a]

    def ww(a):
        return b(a) | (b(a + 1) << 8)

    todo = list(ROOTS if roots is None else roots) + ([] if bank is not None else CODE_PTRS)
    while todo:
        pc = todo.pop()
        while True:
            if pc in starts or pc in STUBS:
                break
            if bank is not None and not (0x4000 <= pc < 0x8000):
                if pc < 0x4000:
                    calls_b0.add(pc)
                break
            if not (0 <= pc < 0x8000):
                break
            op = b(pc)
            m = instructions[op]
            n = length(op)
            starts.add(pc)
            nxt = pc + n
            if op in RST_JUMPTABLE:
                ents = []
                a = nxt
                lim = TABLE_LEN.get(nxt, 99)
                while len(ents) < lim:
                    t = ww(a)
                    if not (0x0150 <= t < 0x8000) or a in starts:
                        break
                    ents.append(t)
                    a += 2
                    if a in targets:
                        break
                tables[nxt] = ents
                for t in ents:
                    targets.add(t)
                    todo.append(t)
                break
            if op in RST_INLINE_DATA:
                pc = nxt + 1 + b(nxt)
                continue
            if op == 0xE9:
                special.append((pc, 'jp hl'))
                break
            if op in (0xE0, 0xF0):                   # ldh : registres matériels ?
                a = 0xFF00 + b(pc + 1)
                if a < 0xFF80:
                    hw.append((pc, m, a))
            if op in (0xE2, 0xF2):
                special.append((pc, m))
            if op == 0xCB and (b(pc + 1) & 0xF8) == 0x30:
                special.append((pc, cb_instructions[b(pc + 1)]))
            if op in (0xE8, 0xF8, 0x08, 0x10, 0x27, 0x76):
                special.append((pc, m))
            if 'd16' in m or 'a16' in m:
                v = ww(pc + 1)
                if op in JUMPS16:
                    if v in STUBS:
                        calls_to_stub.setdefault(v, []).append(pc)
                    elif bank is None and 0x4000 <= v < 0x8000:
                        # fenetre : code d'une autre banque (ou tramplin)
                        calls_to_stub.setdefault(v, []).append(pc)
                    else:
                        targets.add(v)
                        todo.append(v)
                else:
                    if 0x8000 <= v < 0xA000 or 0xFE00 <= v < 0xFF80:
                        hw.append((pc, m, v))
                    if v < 0x8000:
                        imm16.append((pc, m, v))
            if op in JUMPS8:
                r = b(pc + 1)
                t = pc + 2 + (r - 256 if r > 127 else r)
                targets.add(t)
                todo.append(t)
            if op in ENDS or op in (0xC7, 0xFF):
                break
            pc = nxt
    return starts, targets, tables, calls_to_stub, hw, imm16, special, calls_b0


if __name__ == '__main__':
    starts, targets, tables, stubs, hw, imm16, special, _ = explore()
    code_bytes = sum(length(ROM[a]) for a in starts)
    print(f'{len(starts)} instructions, {code_bytes} octets de code GB')
    print('appels remplacés :', {hex(k): [hex(x) for x in v] for k, v in stubs.items()})
    print('matériel GB :')
    for pc, m, a in hw:
        print(f'  {pc:04x}  {m}  -> {a:04x}')
    print('immédiats 16 bits < $8000 :')
    for pc, m, v in imm16:
        tag = 'code' if v in starts else ''
        print(f'  {pc:04x}  {m:14s} {v:04x} {tag}')
    print('instructions spéciales :')
    for s in special:
        print(f'  {s[0]:04x}  {s[1]}')
