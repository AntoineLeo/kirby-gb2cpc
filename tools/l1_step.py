"""Pas-a-pas d'une trame du banc d'essai niveau 1.

Injection de l'etat "avant" de la trace level1_loop (memoire + registres), puis
une boucle de jeu complete passee instruction a instruction (sim.trace 1 pas).
Journalise :
  - les ecritures des champs de script (WATCH) ;
  - les commandes de script (entrees G_2C65 / G_2F56) avec l'octet lu et le slot ;
  - l'argument calcule par G_2D34/G_2D3F (valeur rechargee en CE52+B) ;
  - l'etat final vs trace "apres" (resume des ecarts).

FRAME=n dans l'environnement (defaut 4).
"""
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

WATCH = [0xCE07, 0xCE08, 0xCE09, 0xCE0A, 0xCE0C, 0xCE0E, 0xCE12, 0xCE14, 0xCE3A, 0xCE2F, 0xCE36,
         0xCE52, 0xCE53, 0xCE54, 0xCE55, 0xCE56, 0xCE57, 0xCE58, 0xCE59,
         0xCE6A, 0xCE6B, 0xCE6C, 0xCE6D, 0xCE6E, 0xCE6F,
         0xCE72, 0xCE73, 0xCE74, 0xCE75, 0xCE76, 0xCE77, 0xCE78, 0xCE79, 0xCE7A, 0xCE7B]

# Entrees de script : PC GB -> type d'evenement.
EVENTS = {}
for nm, tag in [('G_2C65', 'cmd'), ('G_2C64', 'cmd+1'), ('G_2D34', 'arg'), ('G_2D56', 'argw'),
                ('G_2F4B', 'chain'), ('G_2F56', 'chcmd'), ('G_2E77', 'ff-main'),
                ('G_3022', 'ff-chain'), ('G_2E8B', 'sub'), ('G_2EAA', 'subrd'),
                ('G_302D', 'sub2'), ('G_2D3F', 'argtbl')]:
    v = sym(nm)
    if v is not None:
        EVENTS[v] = tag


def snap():
    return bytes(mem[a] for a in WATCH)


def ev_line(tag, step, pc):
    de = (regs[D] << 8) | regs[E]
    b = regs[B]
    if tag in ('cmd', 'cmd+1', 'chcmd', 'chain', 'sub', 'sub2', 'subrd'):
        return (f'[{step:5d}] {tag:7s} B={b:02X} DE={de:04X} octets '
                + ' '.join(f'{mem[de+i]:02X}' for i in range(4)))
    if tag in ('arg', 'argtbl'):
        return f'[{step:5d}] {tag:7s} B={b:02X} DE={de:04X} (de)={mem[de]:02X} hl={regs[H]:02X}{regs[L]:02X}'
    return f'[{step:5d}] {tag:7s} B={b:02X} DE={de:04X} A={regs[A]:02X}'


prev = snap()
pc = start
last_pc = pc
print(f'--- trame {FRAME} : depart PC={start:04X} ---')
for step in range(200000):
    last_pc = pc
    regs[PC] = pc
    tag = EVENTS.get(last_pc)
    if tag:
        print(ev_line(tag, step, last_pc))
    sim.trace(pc, 0, 1, 0, False, None, None, None, None, None)
    pc = regs[PC]
    cur = snap()
    if cur != prev:
        chg = [f'{a:04X}:{b:02X}' for a, b in zip(WATCH, cur) if b != prev[WATCH.index(a)]]
        print(f'[{step:5d}] ecrit {last_pc:04X} : ' + ' '.join(chg))
        prev = cur
    if pc == start:
        print(f'[{step:5d}] tour de boucle termine')
        break
else:
    print('pas de boucle en 200000 pas, PC', hex(pc))

# Etat final vs trace (apres la trame)
diffs = []
for a in amap:
    if 0xBFF0 <= a < 0xBFF6:
        continue
    got = mem[a]
    want = int(after[amap.index(a)])
    if got != want:
        diffs.append((a, want, got))
print(f'--- etat final vs trace : {len(diffs)} octets differents ---')
for a, want, got in diffs:
    print(f'  {a:04X} trace={want:02X} banc={got:02X}')
