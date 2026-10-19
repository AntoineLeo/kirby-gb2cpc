"""Comparaison niveau 1 : trace GB ancree sur la boucle (0x3396) contre le Z80.

Point de reprise stable : PC = 0x3396, une fois par trame. Le pas de logique va
de ce PC au meme PC a la trame suivante ; l'attente VBlank est remplacee par
gb_vblank (compteur + boucle VBlank 2BFD), puis la boucle se referme.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gb_cmp
from skoolkit import CSimulator
from skoolkit.simutils import A, F, B, C, D, E, H, L, SP, PC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = open(os.path.join(ROOT, 're', 'game.gb'), 'rb').read()
BIN = open(os.path.join(ROOT, 'build', 'l1', 'test.bin'), 'rb').read()
SYM = open(os.path.join(ROOT, 'build', 'l1', 'test.sym'), encoding='utf-8').read()
BANKS2_BIN = open(os.path.join(ROOT, 'build', 'l1', 'banks2.bin'), 'rb').read()


def sym(name):
    m = re.search(r'^' + re.escape(name) + r':\s+EQU\s+0x([0-9A-Fa-f]+)', SYM, re.M)
    if not m:
        raise SystemExit(f'symbole {name} absent')
    return int(m.group(1), 16)


# Tramplins de fenetre : points de dispatch (win_entries.json, produits par
# gb2z80.py) -> `jp BNN_xxxx` posé à l'entrée xxxx de l'image de la banque NN.
import json
ENTS = json.load(open(os.path.join(ROOT, 'build', 'l1', 'win_entries.json'),
                      encoding='utf-8'))
WIN_CACHE = {}


def win_image(bank):
    img = WIN_CACHE.get(bank)
    if img is None:
        img = bytearray(ROM[bank * 0x4000:(bank + 1) * 0x4000])
        for e in ENTS.get(f'{bank:02x}', []):
            m = re.search(r'^B' + f'{bank:02X}_{e:04X}' + r':\s+EQU\s+0x([0-9A-Fa-f]+)', SYM, re.M)
            if not m:
                continue
            addr = int(m.group(1), 16)
            off = e - 0x4000
            img[off] = 0xC3
            img[off + 1] = addr & 0xFF
            img[off + 2] = addr >> 8
        img = WIN_CACHE[bank] = bytes(img)
    return img


class Tracer:
    border = 7
    t_start = None
    colour_spans = {}
    prof_ignore = 4

    def read_port(self, r, p):
        return 0xFF

    def write_port(self, r, p, v, offset=0):
        if (p & 0xFF) == 0xFE:            # select_bank : placer la fenetre
            mem[0x4000:0x8000] = win_image(v & 0x1F)


sim = CSimulator(bytearray(65536))
mem = sim.memory
mem[0x0200:0x0200 + len(BIN)] = BIN
mem[0xE000:0xE000 + len(BANKS2_BIN)] = BANKS2_BIN
sim.set_tracer(Tracer())
start = sym('G_3396')
# Exclusions : tampons d'affichage (D200-D3FF), file d'entrees (D800-D81F),
# registres FF9x ombrés (DA00-DA2F, DA3E-DA45) et pile (DF00-DFFF).
compare = [a for a in range(0xC200, 0xE000)
           if not (0xD200 <= a < 0xD400 or 0xD800 <= a < 0xD820
                   or 0xDA00 <= a < 0xDA30 or 0xDA3E <= a < 0xDA46
                   or a >= 0xDF00)]
if os.environ.get('NO_STACK'):
    compare = [a for a in compare if not (0xDF00 <= a < 0xE000)]

trace_mem, meta, _ = gb_cmp.load_trace('level1_loop')
ref = gb_cmp.mem_matrix(trace_mem, meta)
amap = gb_cmp.addr_map(meta)
regs = sim.registers
mism = 0
first = []
for i in range(1, min(len(ref), int(os.environ.get('FRAMES', '60')))):
    before, after = ref[i - 1], ref[i]
    for a in amap:
        if not (0xBFF0 <= a < 0xBFF6):        # tout, sauf les marqueurs de tour
            mem[a] = int(before[amap.index(a)])
    mem[0x4000:0x8000] = win_image(mem[0xFFA4] & 0x1F)
    rr = meta['registers'][i - 1]
    for idx, val in enumerate(rr[:6]):
        regs[idx] = val
    regs[6] = rr[6] & 0xFF
    regs[7] = (rr[6] >> 8) & 0xFF
    regs[SP] = rr[7]
    regs[PC] = start
    regs[26] = 0
    run = sim.trace(start, start, 0, 2000000, False, None, None, None, None, None)
    if i <= 3: print('  fin PC', hex(regs[PC]), 'SP', hex(regs[SP]), 'trace', run)
    if regs[PC] != start:
        stack = [f'{mem[a] | (mem[a + 1] << 8):04X}' for a in range(0xDFC0, 0xDFE8, 2)]
        print(f'  ARRET tour {i} : PC {regs[PC]:04X} SP {regs[SP]:04X} trace {run} pile {stack} cible {mem[0xBFF4] | (mem[0xBFF5] << 8):04X}')
    got = [mem[a] for a in compare]
    want = [int(after[amap.index(a)]) for a in compare]
    diff = [a for a, va, vb in zip(compare, want, got) if va != vb]
    if diff:
        mism += 1
        if len(first) < 8:
            first.append((i, [(f'{a:04X}', f'{after[amap.index(a)]:02X}', f'{mem[a]:02X}')
                             for a in diff[:12]]))
    if i <= 5 or i % 10 == 0:
        print(f'trame {i}: {len(diff)} octets differents, m {mem[0xBFF0]:02x}/{mem[0xBFF1]:02x}/{mem[0xBFF2]:02x} vb {mem[0xBFF3]:02x}/{mem[0xBFF4]:02x}')
print(f'{mism} trames differentes sur {min(len(ref), int(os.environ.get("FRAMES", "60"))) - 1}')
for x in first:
    print(x)
