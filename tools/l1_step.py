import os, re, sys
sys.path.insert(0, 'tools')
import gb_cmp
from skoolkit import CSimulator
from skoolkit.simutils import A, F, B, C, D, E, H, L, SP, PC

ROOT = r'C:\projets\kirby-gb2cpc'
ROM = open(os.path.join(ROOT, 're', 'game.gb'), 'rb').read()
BIN = open(os.path.join(ROOT, 'build', 'l1', 'test.bin'), 'rb').read()
SYM = open(os.path.join(ROOT, 'build', 'l1', 'test.sym'), encoding='utf-8').read()
BANKS2_BIN = open(os.path.join(ROOT, 'build', 'l1', 'banks2.bin'), 'rb').read()
import json
ENTS = json.load(open(os.path.join(ROOT, 'build', 'l1', 'win_entries.json'), encoding='utf-8'))


def sym(name):
    m = re.search(r'^' + re.escape(name) + r':\s+EQU\s+0x([0-9A-Fa-f]+)', SYM, re.M)
    return int(m.group(1), 16) if m else None


def win_image(bank):
    img = bytearray(ROM[bank * 0x4000:(bank + 1) * 0x4000])
    for e in ENTS.get(f'{bank:02x}', []):
        m = re.search(r'^B' + f'{bank:02X}_{e:04X}' + r':\s+EQU\s+0x([0-9A-Fa-f]+)', SYM, re.M)
        if m:
            addr = int(m.group(1), 16)
            off = e - 0x4000
            img[off] = 0xC3
            img[off + 1] = addr & 0xFF
            img[off + 2] = addr >> 8
    return bytes(img)


class Tracer:
    border = 7
    t_start = None
    colour_spans = {}
    prof_ignore = 4

    def read_port(self, r, p):
        return 0xFF

    def write_port(self, r, p, v, offset=0):
        if (p & 0xFF) == 0xFE:
            mem[0x4000:0x8000] = win_image(v & 0x1F)


sim = CSimulator(bytearray(65536))
mem = sim.memory
mem[0x0200:0x0200 + len(BIN)] = BIN
mem[0xE000:0xE000 + len(BANKS2_BIN)] = BANKS2_BIN
sim.set_tracer(Tracer())
start = sym('G_3396')

trace_mem, meta, _ = gb_cmp.load_trace('level1_loop')
ref = gb_cmp.mem_matrix(trace_mem, meta)
amap = gb_cmp.addr_map(meta)
regs = sim.registers
FRAME = int(os.environ.get('FRAME', '4'))
before, after = ref[FRAME - 1], ref[FRAME]
for a in amap:
    if not (0xBFF0 <= a < 0xBFF6):
        mem[a] = int(before[amap.index(a)])
mem[0x4000:0x8000] = win_image(mem[0xFFA4] & 0x1F)
rr = meta['registers'][FRAME - 1]
for idx, val in enumerate(rr[:6]):
    regs[idx] = val
regs[6] = rr[6] & 0xFF
regs[7] = (rr[6] >> 8) & 0xFF
regs[SP] = rr[7]
regs[26] = 0

WATCH = [0xCE07, 0xCE08, 0xCE09, 0xCE0A, 0xCE0C, 0xCE0E, 0xCE12, 0xCE14, 0xCE2F, 0xCE36]


def snap():
    return bytes(mem[a] for a in WATCH)


prev = snap()
pc = start
last_pc = pc
for step in range(200000):
    last_pc = pc
    regs[PC] = pc
    sim.trace(pc, 0, 1, 0, False, None, None, None, None, None)
    pc = regs[PC]
    cur = snap()
    if cur != prev:
        print(f'etape {step} : instruction a {last_pc:04X} ecrit '
              + ' '.join(f'{a:04X}:{b:02X}' for a, b in zip(WATCH, cur) if mem[a] != before[amap.index(a)] or True))
        print('   avant :', prev.hex())
        print('   apres :', cur.hex())
        print(f'   A={regs[A]:02X} BC={regs[B]:02X}{regs[C]:02X} DE={regs[D]:02X}{regs[E]:02X} '
              f'HL={regs[H]:02X}{regs[L]:02X} SP={regs[SP]:04X}')
        bank = mem[0xFFA4] & 0x1F
        print(f'   FFA4={bank:02X} fenetre 4220:', mem[0x4220:0x4230].hex())
        want = ROM[bank*0x4000+0x220:bank*0x4000+0x230]
        print(f'   ROM banque {bank:02X}  4220:', want.hex())
        prev = cur
    if pc == start:
        print(f'tour boucle a l''etape {step}')
        break
else:
    print('pas de boucle en 200000 pas, PC', hex(pc))
