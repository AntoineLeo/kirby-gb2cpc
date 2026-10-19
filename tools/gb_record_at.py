"""Enregistre l'etat GB a un point de reprise precis (une fois par trame).

Les traces de la preparation sont prises au debut du VBlank. Pour verifier un
portage dont la logique demarre apres l'attente VBlank, il faut un point de
reprise stable, identique chaque trame : ce script accroche un PC (banque 0
par defaut) et enregistre la memoire GB, les registres et le PC a chaque
passage. Le format de sortie est celui de gb_trace/gb_cmp (mem + meta).

Usage :
  python tools/gb_record_at.py --scenario re/scenarios/level1.json \
      --pc 33AA --out re/traces/level1_loop.npz
"""
import argparse
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gb_sim  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenario', required=True)
    ap.add_argument('--rom')
    ap.add_argument('--state')
    ap.add_argument('--frames', type=int, default=0)
    ap.add_argument('--pc', default='33AA')
    ap.add_argument('--bank', type=lambda x: int(x, 16), default=0)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    sc = gb_sim.load_scenario(args.scenario)
    rom = gb_sim.resolve(sc.get('rom', args.rom or 're/game.gb'), sc.get('_base'))
    state = gb_sim.resolve(sc['state'], sc['_base']) if sc.get('state') else args.state
    frames = args.frames or int(sc.get('frames', 600))
    events = gb_sim.parse_press(sc.get('press', ''))
    for inp in sc.get('inputs', []):
        a = int(inp['from'])
        b = int(inp.get('to', a))
        events.append((a, b, [n.lower() for n in inp.get('buttons', [])]))
    from pyboy import PyBoy
    pb = PyBoy(rom, window='null', sound_emulated=False,
               ram_file=io.BytesIO(b'\0' * 8192))
    if state:
        with open(state, 'rb') as f:
            pb.load_state(f)
    else:
        for a in range(0xA000, 0xC000):
            pb.memory[a] = 0
    regions = [(0xC000, 0xE000), (0xFF80, 0x10000), (0xA000, 0xC000)]
    frames_mem = []
    regs = []
    pcs = []
    pending = []

    def hook(ctx):
        pending.append((bytes(pb.memory[lo:hi]) for lo, hi in regions))

    pc = int(args.pc, 16)
    pb.hook_register(args.bank, pc, hook, ('at', args.bank, pc))
    f = 0
    while len(frames_mem) < frames and f < frames * 3:
        want = gb_sim.held_at(events, f)
        for b in gb_sim.BUTTONS:
            if b in want:
                pb.button_press(b)
            else:
                pb.button_release(b)
        pb.tick(render=False)
        f += 1
        if pending:
            block = pending[-1]
            pending.clear()
            frames_mem.append(b''.join(block))
            r = pb.register_file
            regs.append([r.A, r.F, r.B, r.C, r.D, r.E,
                         r.HL, r.SP, r.PC])
            pcs.append(r.PC)
    pb.stop(save=False)
    n = len(frames_mem)
    if n == 0:
        raise SystemExit('aucun passage au PC demande')
    size = sum(hi - lo for lo, hi in regions)
    meta = {
        'name': os.path.splitext(os.path.basename(args.out))[0],
        'rom': os.path.basename(rom),
        'rom_md5': gb_sim.md5(open(rom, 'rb').read()),
        'frames': n,
        'every': 1,
        'regions': regions,
        'frame_hashes': [gb_sim.hash_bytes(b) for b in frames_mem],
        'screen_hashes': [''] * n,
        'registers': regs,
        'pc': pcs,
        'coverage': {},
        'scenario_md5': gb_sim.md5(open(args.scenario, 'rb').read()),
        'anchor_pc': pc,
        'anchor_bank': args.bank,
    }
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    np.savez_compressed(args.out, mem=np.frombuffer(b''.join(frames_mem), dtype=np.uint8),
                        meta=np.frombuffer(json.dumps(meta).encode('utf-8'), dtype=np.uint8))
    print(f'{n} trames au PC {pc:04x} -> {args.out} ({size} octets/trame)')


if __name__ == '__main__':
    main()
