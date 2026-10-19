"""Banques ROM utilisees par la logique GB : entrees, code atteint, donnees.

Analyse statique du code explore depuis CFG.ROOTS (gb_closure) :
  - chaque appel/saut vers la fenetre $4000-$7FFF, avec la banque retenue par le
    motif « ld a,N ; call SetBank/SetBankNoInt/CallBank » le plus proche ;
  - par banque : fermeture du code atteint depuis ses entrees, taille GB,
    lectures de donnees dans la fenetre, appels rentrant vers la banque 0 ;
  - (--dynamic) confirmation par PyBoy sur des scenarios : banque courante au
    moment de chaque appel de banque (hooks sur SetBank/CallBank).

Sortie par defaut : un resume de quelques lignes. Le detail va dans --out.

Usage :
  python tools/gb_banks.py
  python tools/gb_banks.py --out /tmp/banks.json
  python tools/gb_banks.py --dynamic re/scenarios/level1.json
"""
import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gbrom import CFG, ROM, instructions, cb_instructions, length, w, jr_target, inline_len, \
    RST_JUMPTABLE, RST_INLINE_DATA, TABLE_LEN, JUMPS16, JUMPS8, ENDS  # noqa: E402
import gb_closure as gc  # noqa: E402

WINDOW = (0x4000, 0x8000)
SETBANK = {0x05DD, 0x05F3, 0x05CF, 0x05BF, 0x05E5}
STUBS = dict(CFG.STUBS)


def in_window(v):
    return WINDOW[0] <= v < WINDOW[1]


# Les CODE_PTRS de la fenetre ne sont pas du code banque 0 : ne pas explorer
# leurs octets (ceux de la banque 1 du fichier ROM) comme du code.
gc.CODE_PTRS = [c for c in gc.CODE_PTRS if not in_window(c)]


def bank_rom(bank):
    base = bank * 0x4000
    return ROM[base:base + 0x8000] if bank == 0 else None


def rom_at(pc, bank=None):
    if pc < 0x4000 or bank is None:
        return ROM[pc]
    return ROM[bank * 0x4000 + (pc - 0x4000)]


def decode(pc, bank=None):
    op = rom_at(pc, bank)
    m = instructions[op]
    n = length(op)
    return op, m, n


def scan_bank0():
    """Paires (banque, entree) depuis les motifs d'appel du code banque 0."""
    starts, targets, tables, calls_to_stub, hw, imm16, special = gc.explore()
    order = sorted(starts)
    sel = {}          # pc -> banque choisie juste avant
    pairs = []        # (site, banque, cible, motif)
    unattributed = []
    last_bank = {}
    prev = {}
    for pc in order:
        prev[pc] = None
    for i, pc in enumerate(order):
        op, m, n = decode(pc)
        nxt = pc + n
        if op == 0x3E and nxt in starts:                 # ld a,d8
            op2, m2, n2 = decode(nxt)
            if op2 == 0xCD:
                t = w(nxt + 1)
                if t in SETBANK:
                    last_bank[nxt] = ROM[pc + 1]
        if op == 0x21 and nxt in starts:                 # ld hl,d16
            prev[nxt] = ('hl', w(pc + 1), pc)
        if op in JUMPS16:
            t = w(pc + 1)
            if in_window(t):
                b = None
                motif = '?'
                if pc in last_bank:
                    b, motif = last_bank[pc], 'direct'
                else:
                    for back in order[max(0, i - 8):i][::-1]:
                        if back in last_bank:
                            b, motif = last_bank[back], 'avant'
                            break
                        pr = prev.get(back)
                        if pr and pr[0] == 'hl':
                            b, motif = None, 'hl'
                            break
                if b is None:
                    unattributed.append((pc, t, motif))
                else:
                    pairs.append((pc, b, t, motif))
        if op == 0xCD and w(pc + 1) in SETBANK:
            pass
    return order, pairs, unattributed


def scan_callbank_sites():
    """Sites CallBank : (site, hl, banque) a partir des motifs immediats."""
    starts, *_ = gc.explore()
    order = sorted(starts)
    out = []
    for i, pc in enumerate(order):
        op, m, n = decode(pc)
        if op != 0xCD or w(pc + 1) != 0x05CF:
            continue
        hl = bank = None
        for back in order[max(0, i - 8):i][::-1]:
            o2, m2, n2 = decode(back)
            if o2 == 0x21 and hl is None:
                hl = w(back + 1)
            if o2 == 0x3E and bank is None and back + 2 in starts:
                o3, _, _ = decode(back + 2)
                if o3 == 0xCD and w(back + 3) in SETBANK:
                    bank = ROM[back + 1]
            if hl is not None and bank is not None:
                break
        out.append((pc, hl, bank))
    return out


def bank_closure(bank, entries):
    """Fermeture du code d'une banque depuis ses entrees.

    Retourne : code (starts), taille GB, lectures de donnees fenetre,
    appels vers la banque 0, appels fenetre intra-banque, motifs de banque."""
    starts = set()
    code_bytes = 0
    data_reads = set()
    calls_b0 = set()
    calls_win = set()
    selects = []
    todo = list(entries)
    while todo:
        pc = todo.pop()
        while True:
            if pc in starts or (pc in STUBS and not in_window(pc)):
                break
            if not (0 <= pc < 0x8000):
                break
            if pc < 0x4000:
                calls_b0.add(pc)
                break
            op, m, n = decode(pc, bank)
            if instructions[op].startswith('ILLEGAL'):
                break
            starts.add(pc)
            code_bytes += n
            nxt = pc + n
            if op in RST_JUMPTABLE:
                ents = []
                a = nxt
                lim = TABLE_LEN.get(nxt, 99)
                while len(ents) < lim and len(ents) < 32:
                    t = rom_at(a, bank) | (rom_at(a + 1, bank) << 8)
                    if not (0x0150 <= t < 0x8000):
                        break
                    ents.append(t)
                    a += 2
                for t in ents:
                    if t >= 0x4000:
                        calls_win.add(t)
                        todo.append(t)
                    else:
                        calls_b0.add(t)
                break
            if op in RST_INLINE_DATA:
                pc = nxt + inline_len(pc)
                continue
            if op == 0x3E and rom_at(nxt, bank) == 0xCD and \
                    (rom_at(nxt + 1, bank) | (rom_at(nxt + 2, bank) << 8)) in SETBANK:
                selects.append((pc, ROM[bank * 0x4000 + pc - 0x4000 + 1] if pc >= 0x4000 else ROM[pc + 1]))
            if 'd16' in m or 'a16' in m:
                v = rom_at(pc + 1, bank) | (rom_at(pc + 2, bank) << 8)
                if op in JUMPS16:
                    if in_window(v):
                        calls_win.add(v)
                        todo.append(v)
                    elif v < 0x4000:
                        calls_b0.add(v)
                    else:
                        data_reads.add(v)
                else:
                    if in_window(v):
                        data_reads.add(v)
            if op in JUMPS8:
                t = jr_target_from(pc, bank)
                todo.append(t)
            if op in ENDS:
                break
            pc = nxt
    return {
        'bank': bank,
        'entries': sorted(set(entries)),
        'starts': len(starts),
        'code_bytes': code_bytes,
        'data_reads': sorted(data_reads),
        'calls_b0': sorted(calls_b0),
        'calls_win': sorted(calls_win),
        'selects': selects,
    }


def jr_target_from(pc, bank):
    r = rom_at(pc + 1, bank)
    return pc + 2 + (r - 256 if r > 127 else r)


def dynamic(scenarios):
    """Confirmation PyBoy : (banque, cible) reels aux appels de banque."""
    import gb_sim
    from pyboy import PyBoy
    hits = defaultdict(int)
    hl_calls = defaultdict(int)

    def make(rom):
        return PyBoy(rom, window='null', sound_emulated=False)

    for sc_path in scenarios:
        sc = gb_sim.load_scenario(sc_path)
        rom = gb_sim.resolve(sc.get('rom', 're/game.gb'), sc.get('_base'))
        state = gb_sim.resolve(sc.get('state'), sc.get('_base')) if sc.get('state') else None
        frames = int(sc.get('frames', 600))
        events = gb_sim.parse_press(sc.get('press', ''))
        for inp in sc.get('inputs', []):
            a = int(inp['from'])
            b = int(inp.get('to', a))
            events.append((a, b, [n.lower() for n in inp.get('buttons', [])]))
        pb = make(rom)
        if state:
            with open(state, 'rb') as f:
                pb.load_state(f)

        def on_setbank(ctx):
            sp = pb.register_file.SP
            ret = pb.memory[sp] | (pb.memory[sp + 1] << 8)
            a = pb.register_file.A
            site = bytes(pb.memory[ret - 3:ret])
            if site not in (b'\xcd\xdd\x05', b'\xcd\xf3\x05'):
                return
            op = pb.memory[ret]
            tgt = ret
            if op in (0xCD, 0xC3, 0xC4, 0xCC, 0xD4, 0xDC):
                tgt = pb.memory[ret + 1] | (pb.memory[ret + 2] << 8)
            hits[(a, ret, tgt)] += 1

        def on_callbank(ctx):
            hl = pb.register_file.HL
            a = pb.register_file.A
            hl_calls[(a, hl)] += 1

        pb.hook_register(0, 0x05DD, on_setbank, None)
        pb.hook_register(0, 0x05F3, on_setbank, None)
        pb.hook_register(0, 0x05CF, on_callbank, None)
        for f in range(frames):
            want = gb_sim.held_at(events, f)
            for b in gb_sim.BUTTONS:
                if b in want:
                    pb.button_press(b)
                else:
                    pb.button_release(b)
            pb.tick(render=False)
        pb.stop(save=False)
    return hits, hl_calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--dynamic', nargs='*')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()

    if args.selftest:
        pairs_ok = scan_callbank_sites()
        assert any(hl == 0x5B85 and b == 0x07 for _, hl, b in pairs_ok), 'CallBank 07:5B85 absent'
        assert any(hl == 0x4232 and b == 0x1F for _, hl, b in pairs_ok), 'CallBank 1F:4232 absent'
        print('selftest OK : motifs CallBank retrouves')
        return 0

    order, pairs, unattr = scan_bank0()
    cbs = scan_callbank_sites()
    entries = defaultdict(set)
    for pc, b, t, motif in pairs:
        entries[b].add(t)
    for pc, hl, b in cbs:
        if b is not None and hl is not None and in_window(hl):
            entries[b].add(hl)
    print(f'appels fenetre attribues : {len(pairs)}, sites CallBank : {len(cbs)}, non attribues : {len(unattr)}')
    if unattr:
        print('  non attribues :', ', '.join(f'{t:04X}@{pc:04X}({m})' for pc, t, m in unattr[:12]))

    rep = {'pairs': [[f'{pc:04x}', b, f'{t:04x}', motif] for pc, b, t, motif in pairs],
           'callbank': [[f'{pc:04x}', f'{hl:04x}' if hl else None, b] for pc, hl, b in cbs],
           'unattributed': [[f'{pc:04x}', f'{t:04x}', m] for pc, t, m in unattr],
           'banks': {}}
    total = 0
    for b in sorted(entries):
        info = bank_closure(b, entries[b])
        rep['banks'][f'{b:02x}'] = {
            'entries': [f'{a:04x}' for a in info['entries']],
            'starts': info['starts'],
            'code_bytes': info['code_bytes'],
            'data_reads': [f'{a:04x}' for a in info['data_reads']],
            'calls_b0': [f'{a:04x}' for a in info['calls_b0']],
            'calls_win': [f'{a:04x}' for a in info['calls_win']],
        }
        total += info['code_bytes']
        print(f"banque {b:02X} : {len(info['entries'])} entrees ({', '.join(f'{a:04X}' for a in info['entries'][:8])}"
              f"{', ...' if len(info['entries']) > 8 else ''}), {info['starts']} instructions,"
              f" {info['code_bytes']} o code GB, {len(info['data_reads'])} lectures donnees,"
              f" {len(info['calls_b0'])} appels banque 0")
    print(f'total code GB des banques commutables : {total} o (~{total * 2} o Z80 estimes)')

    if args.dynamic:
        hits, hl_calls = dynamic(args.dynamic)
        dyn_pairs = set()
        for (a, ret, nxt), n in sorted(hits.items()):
            if in_window(nxt):
                dyn_pairs.add((a, nxt))
        for (a, hl), n in sorted(hl_calls.items()):
            if in_window(hl):
                dyn_pairs.add((a, hl))
        stat_pairs = {(b, t) for _, b, t, _ in pairs} | {(b, hl) for _, hl, b in cbs if b and hl and in_window(hl)}
        missing = sorted(dyn_pairs - stat_pairs)
        unused = sorted(stat_pairs - dyn_pairs)
        print(f'dynamique : {len(dyn_pairs)} paires (banque, entree) executees')
        if missing:
            print('  vues en dynamique seulement :', ', '.join(f'{b:02X}:{t:04X}' for b, t in missing))
        if unused:
            print('  attribuees statiquement seulement :', ', '.join(f'{b:02X}:{t:04X}' for b, t in unused))
        rep['dynamic'] = [[b, f'{t:04x}'] for b, t in sorted(dyn_pairs)]
        rep['dynamic_missing'] = [[b, f'{t:04x}'] for b, t in missing]

    if args.out:
        os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(rep, f, indent=1)
        print(f'detail -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
