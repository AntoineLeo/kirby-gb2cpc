"""Profil video Game Boy : ce que l'affichage demande a chaque trame.

Mesures utiles pour dimensionner un moteur CPC :
  - sprites OAM actifs, maximum par ligne (limite materielle GB : 10) ;
  - sprites OAM modifies d'une trame a l'autre (travail de redessin) ;
  - tuiles distinctes de la carte de fond et de la fenetre ;
  - defilement, LCDC, nombre d'entrees dans les files VRAM (DA23/DA24) ;
  - changements d'octets OAM et de la carte de tuiles par trame.

Usage :
  python tools/gb_video_profile.py re/scenarios/level1_actions.json
  python tools/gb_video_profile.py --state re/ref/start_state.state --frames 600
"""
import argparse
import io
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gb_sim  # noqa: E402


def make_pb(rom):
    from pyboy import PyBoy
    return PyBoy(rom, window='null', sound_emulated=False,
                 ram_file=io.BytesIO(b'\0' * 8192))


def oam_stats(mem):
    spr = []
    for i in range(40):
        y = mem[0xFE00 + i * 4]
        x = mem[0xFE01 + i * 4]
        t = mem[0xFE02 + i * 4]
        f = mem[0xFE03 + i * 4]
        if 0 < y < 160 and 0 < x < 168:
            spr.append((y, x, t, f))
    lines = Counter()
    tall = mem[0xFF40] & 4
    h = 16 if tall else 8
    for y, x, t, f in spr:
        for dy in range(h):
            lines[y + dy] += 1
    return spr, lines


def profile(rom, state, frames, events, every=1):
    pb = make_pb(rom)
    if state:
        with open(state, 'rb') as f:
            pb.load_state(f)
    else:
        for a in range(0xA000, 0xC000):
            pb.memory[a] = 0
    prev_oam = None
    prev_map = None
    out = []
    totals = Counter()
    max_line = 0
    max_spr = 0
    for f in range(frames):
        want = gb_sim.held_at(events, f)
        for b in gb_sim.BUTTONS:
            if b in want:
                pb.button_press(b)
            else:
                pb.button_release(b)
        pb.tick(render=False)
        mem = pb.memory
        spr, lines = oam_stats(mem)
        max_spr = max(max_spr, len(spr))
        if lines:
            max_line = max(max_line, max(lines.values()))
        oam = bytes(mem[0xFE00:0xFE00 + 160])
        map_bytes = bytes(mem[0x9800:0x9C00]) + bytes(mem[0x9C00:0xA000])
        oam_chg = 0 if prev_oam is None else sum(a != b for a, b in zip(oam, prev_oam))
        map_chg = 0 if prev_map is None else sum(a != b for a, b in zip(map_bytes, prev_map))
        prev_oam, prev_map = oam, map_bytes
        tiles_bg = len(set(map_bytes[:1024]))
        tiles_win = len(set(map_bytes[1024:]))
        totals['sprites'] += len(spr)
        totals['oam_changed'] += oam_chg
        totals['map_changed'] += map_chg
        if f % every == 0:
            out.append({
                'frame': f,
                'sprites': len(spr),
                'sprites_max_line': max(lines.values()) if lines else 0,
                'oam_changed': oam_chg,
                'map_changed': map_chg,
                'tiles_bg': tiles_bg,
                'tiles_win': tiles_win,
                'scroll_x': mem[0xFF43],
                'scroll_y': mem[0xFF42],
                'lcdc': mem[0xFF40],
                'queue1': mem[0xDA23],
                'queue2': mem[0xDA24],
            })
    pb.stop(save=False)
    n = max(1, frames)
    return {
        'frames': frames,
        'max_sprites': max_spr,
        'max_sprites_per_line': max_line,
        'avg_sprites': round(totals['sprites'] / n, 2),
        'avg_oam_changed': round(totals['oam_changed'] / n, 2),
        'avg_map_changed': round(totals['map_changed'] / n, 2),
        'frames_detail': out,
    }


def summarize(p):
    print(f"sprites : max {p['max_sprites']}, moyenne {p['avg_sprites']}, "
          f"max par ligne {p['max_sprites_per_line']}")
    print(f"octets changes par trame : OAM {p['avg_oam_changed']}, carte {p['avg_map_changed']}")
    fr = p['frames_detail']
    if fr:
        print('extrait (trame, sprites, max/ligne, OAM modifiee, carte, tuiles BG):')
        step = max(1, len(fr) // 8)
        for x in fr[::step][:8]:
            print(f"  {x['frame']:4d}  {x['sprites']:2d}  {x['sprites_max_line']:2d}  "
                  f"{x['oam_changed']:3d}  {x['map_changed']:3d}  {x['tiles_bg']:3d}")


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
    rom, state, frames = args.rom, args.state, args.frames
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
    p = profile(rom, state, frames, events, args.every)
    summarize(p)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(p, f, indent=1)
        print(f'detail -> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
