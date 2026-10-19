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
BIN = open(os.path.join(ROOT, 'build', 'room', 'test.bin'), 'rb').read()
SYM = open(os.path.join(ROOT, 'build', 'room', 'test.sym'), encoding='utf-8').read()


def sym(name):
    m = re.search(r'^' + re.escape(name) + r':\s+EQU\s+0x([0-9A-Fa-f]+)', SYM, re.M)
    if not m:
        raise SystemExit(f'symbole {name} absent')
    return int(m.group(1), 16)


class Tracer:
    border = 7
    t_start = None
    colour_spans = {}
    prof_ignore = 4

    def read_port(self, r, p):
        return 0xFF

    def write_port(self, r, p, v, offset=0):
        pass


sim = CSimulator(bytearray(65536))
mem = sim.memory
mem[0x0200:0x0200 + len(BIN)] = BIN
sim.set_tracer(Tracer())
start = sym('G_11C6')
bank = int(os.environ.get('BANK', '1F'), 16)
compare = [a for a in range(0xC200, 0xE000) if not (0xDA00 <= a < 0xDA30 or 0xDA3E <= a < 0xDA46 or a >= 0xDFD0)]
if os.environ.get('NO_STACK'):
    compare = [a for a in compare if not (0xDF00 <= a < 0xE000)]

trace_mem, meta, _ = gb_cmp.load_trace('room_loop')
ref = gb_cmp.mem_matrix(trace_mem, meta)
amap = gb_cmp.addr_map(meta)
regs = sim.registers
mism = 0
first = []
for i in range(1, min(len(ref), int(os.environ.get('FRAMES', '300')))):
    before, after = ref[i - 1], ref[i]
    mem[0x4000:0x8000] = ROM[7 * 0x4000:8 * 0x4000]
    for a in amap:
        if not (0xA000 <= a < 0xC000):
            mem[a] = int(before[amap.index(a)])
    rr = meta['registers'][i - 1]
    for idx, val in enumerate(rr[:6]):
        regs[idx] = val
    regs[6] = rr[6] & 0xFF
    regs[7] = (rr[6] >> 8) & 0xFF
    regs[SP] = rr[7]
    regs[PC] = start
    regs[26] = 0
    sim.trace(start, start, 0, 2000000, False, None, None, None, None, None)
    if i <= 3: print('  fin PC', hex(regs[PC]), 'SP', hex(regs[SP]))
    print('  PC',hex(regs[PC]),'C000',mem[0xC000:0xC008].hex(),'C100',mem[0xC100:0xC108].hex(),'VRAM',len(set(mem[0x8000:0xA000])),'nonzero',sum(1 for b in mem[0x8000:0xA000] if b))
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
