"""Profil d'execution Game Boy : banques ROM utilisees et PC echantillonnes.

Complete gb_sim.py (memoire, couverture par routines) par ce que la logique
utilise reellement au fil du jeu :
  - banque ROM courante (FFA4) a chaque trame ;
  - PC, SP et registres a chaque trame ;
  - PC exact a chaque changement de banque (cible des appels de banque) ;
  - resume court : banques, hotspots de PC, sauts de banque.

Sortie par defaut : quelques lignes. Le detail va dans le fichier JSON demande.

Usage :
  python tools/gb_profile.py re/scenarios/level1.json
  python tools/gb_profile.py --state re/ref/start_state.state --frames 900 \
      --press "30-899:right" --out /tmp/prof.json
"""
import argparse
import io
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gb_sim  # noqa: E402


def make_pb(rom):
    from pyboy import PyBoy
    return PyBoy(rom, window='null', sound_emulated=False,
                 ram_file=io.BytesIO(b'\0' * 8192))


def profile(rom, state, frames, events, every=1):
    pb = make_pb(rom)
    if state:
        with open(state, 'rb') as f:
            pb.load_state(f)
    else:
        for a in range(0xA000, 0xC000):
            pb.memory[a] = 0
    banks = Counter()
    pcs = Counter()
    bank_pc = defaultdict(Counter)
    switches = []
    per_frame = []
    last_bank = None
    for f in range(frames):
        want = gb_sim.held_at(events, f)
        for b in gb_sim.BUTTONS:
            if b in want:
                pb.button_press(b)
            else:
                pb.button_release(b)
        pb.tick(render=False)
        r = pb.register_file
        bank = pb.memory[0xFFA4]
        banks[bank] += 1
        pcs[r.PC] += 1
        bank_pc[bank][r.PC] += 1
        if bank != last_bank:
            switches.append((f, last_bank, bank, r.PC))
            last_bank = bank
        if f % every == 0:
            per_frame.append((f, bank, r.PC, r.SP, r.A, r.F, r.HL))
    pb.stop(save=False)
    return {
        'frames': frames,
        'banks': {f'{b:02x}': n for b, n in sorted(banks.items())},
        'top_pc': [[f'{a:04x}', n] for a, n in pcs.most_common(40)],
        'bank_top_pc': {f'{b:02x}': [[f'{a:04x}', n] for a, n in c.most_common(12)]
                        for b, c in bank_pc.items()},
        'switches': [[f, f'{a:02x}' if a is not None else None, f'{b:02x}', f'{pc:04x}']
                     for f, a, b, pc in switches],
        'per_frame': per_frame,
    }


def summarize(prof):
    print(f"banques : {prof['banks']}")
    print('hotspots PC :', ', '.join(f'{a}:{n}' for a, n in prof['top_pc'][:12]))
    sw = prof['switches']
    print(f"changements de banque : {len(sw)}")
    for f, a, b, pc in sw[:20]:
        print(f'  trame {f}: {a or "--"} -> {b}  PC {pc}')
    if len(sw) > 20:
        print(f'  ... ({len(sw) - 20} autres dans le detail)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario', nargs='?')
    ap.add_argument('--rom', default=os.path.join(ROOT, 're', 'game.gb'))
    ap.add_argument('--state')
    ap.add_argument('--frames', type=int, default=600)
    ap.add_argument('--press', default='')
    ap.add_argument('--every', type=int, default=1)
    ap.add_argument('--out')
    args = ap.parse_args()
    rom = args.rom
    state = args.state
    frames = args.frames
    events = gb_sim.parse_press(args.press)
    if args.scenario:
        sc = gb_sim.load_scenario(args.scenario)
        rom = gb_sim.resolve(sc.get('rom', rom), sc.get('_base'))
        state = gb_sim.resolve(sc.get('state'), sc.get('_base')) if sc.get('state') else state
        frames = int(sc.get('frames', frames))
        events = gb_sim.parse_press(sc.get('press', ''))
        for inp in sc.get('inputs', []):
            a = int(inp['from'])
            b = int(inp.get('to', a))
            events.append((a, b, [n.lower() for n in inp.get('buttons', [])]))
    prof = profile(rom, state, frames, events, args.every)
    summarize(prof)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(prof, f, indent=1)
        print(f'detail -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
