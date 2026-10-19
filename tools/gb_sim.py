"""Simulateur Game Boy pilotable par script (PyBoy, sans fenetre).

Sert a toutes les verifications du portage :
  - lancer une image de reference ou une sauvegarde d'etat ;
  - jouer des touches scriptees (scenario JSON) ;
  - relever la memoire du jeu a chaque tour ;
  - noter les adresses de routines executees (couverture) ;
  - sauvegarder et recharger un etat a tout moment.

Sortie par defaut : un resume de quelques lignes. Le detail va dans le fichier
de trace (.npz : memoire par tour, hashes d'ecran, registres, couverture).

Usage :
  python tools/gb_sim.py run re/scenarios/level1.json --trace re/traces/level1.npz
  python tools/gb_sim.py run --frames 600 --press "0-59:right,60-66:a" --trace /tmp/t.npz
  python tools/gb_sim.py state --load re/ref/start_state.state --frames 60 --save /tmp/s.state
  python tools/gb_sim.py shot --load re/ref/start_state.state --out /tmp/start.png
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

DEFAULT_REGIONS = [(0xC000, 0xE000), (0xFF80, 0xFFFF), (0xA000, 0xC000)]
BUTTONS = {'a', 'b', 'start', 'select', 'up', 'down', 'left', 'right'}


def md5(data):
    return hashlib.md5(data).hexdigest()


def hash_bytes(data):
    return hashlib.sha1(data).hexdigest()


def load_scenario(path):
    with open(path, encoding='utf-8') as f:
        sc = json.load(f)
    base = os.path.dirname(os.path.abspath(path))
    sc['_base'] = base
    return sc


def resolve(path, base=None):
    if not path:
        return None
    if os.path.isabs(path):
        return path
    for root in (base, ROOT):
        p = os.path.join(root, path) if root else path
        if os.path.exists(p):
            return p
    return os.path.join(ROOT, path)


def parse_press(spec):
    """'420-427:start,500-507:a,600:right' -> [(debut, fin, [touches])]."""
    out = []
    for item in (spec or '').split(','):
        item = item.strip()
        if not item:
            continue
        rng, _, names = item.partition(':')
        a, _, b = rng.partition('-')
        a = int(a)
        b = int(b) if b else a
        btns = [n.strip().lower() for n in names.split('+') if n.strip()]
        for n in btns:
            if n not in BUTTONS:
                raise SystemExit(f'touche inconnue : {n}')
        out.append((a, b, btns))
    return out


def held_at(events, frame):
    held = set()
    for a, b, names in events:
        if a <= frame <= b:
            held.update(names)
    return held


def buttons_enabled(sc):
    return {k.lower(): bool(v) for k, v in (sc.get('buttons') or {}).items()} or \
        {b: True for b in BUTTONS}


class Coverage:
    """Hooks aux entrees de routines : note la premiere execution par trame.

    PyBoy remplace l'opcode par un point d'arret et appelle le callback. On
    retire le hook apres la premiere execution pour ne pas ralentir la suite.
    """

    def __init__(self, pb, entries, frame_ref):
        self.pb = pb
        self.entries = entries
        self.frame_ref = frame_ref
        self.hits = {}
        self.pending_remove = []
        self.registered = []
        seen = set()
        for e in entries:
            bank, addr = e['bank'], e['addr']
            if (bank, addr) in seen:
                continue
            seen.add((bank, addr))
            try:
                pb.hook_register(bank, addr, self._callback, (bank, addr))
                self.registered.append((bank, addr))
            except Exception as exc:              # adresse non executable
                print(f'  hook ignore {bank:02x}:{addr:04x} ({exc})', file=sys.stderr)

    def _callback(self, ctx):
        if ctx in self.hits:
            return
        self.hits[ctx] = self.frame_ref[0]
        self.pending_remove.append(ctx)
        if os.environ.get('GB_SIM_DEBUG_HOOKS'):
            print(f'  hook {ctx[0]:02x}:{ctx[1]:04x} trame {self.frame_ref[0]}', file=sys.stderr)

    def end_frame(self):
        """Retire les hooks touches pendant la trame (PyBoy les garde sinon)."""
        for bank, addr in self.pending_remove:
            try:
                self.pb.hook_deregister(bank, addr)
            except Exception:
                pass
        self.pending_remove.clear()

    def close(self):
        for bank, addr in list(self.registered):
            try:
                self.pb.hook_deregister(bank, addr)
            except Exception:
                pass
        self.registered.clear()


def make_pb(rom):
    from pyboy import PyBoy
    # RAM cartouche a zero, sans fichier .ram persistant (traces reproductibles)
    return PyBoy(rom, window='null', sound_emulated=False,
                 ram_file=io.BytesIO(b'\0' * 8192))


def run(sc):
    from pyboy import PyBoy
    rom = resolve(sc.get('rom', 're/game.gb'), sc.get('_base'))
    frames = int(sc.get('frames', 600))
    regions = [tuple(r) for r in sc.get('memory_regions', DEFAULT_REGIONS)]
    every = int(sc.get('every', 1))
    events = parse_press(sc.get('press', ''))
    for inp in sc.get('inputs', []):
        a = int(inp['from'])
        b = int(inp.get('to', a))
        names = [n.lower() for n in inp.get('buttons', [])]
        events.append((a, b, names))
    enabled = buttons_enabled(sc)
    state_in = resolve(sc.get('state'), sc.get('_base')) if sc.get('state') else None
    state_out = resolve(sc.get('state_out'), sc.get('_base')) if sc.get('state_out') else None
    state_at = sc.get('states', [])
    screens = set(int(x) for x in sc.get('screens', []))
    screen_dir = resolve(sc.get('screen_dir'), sc.get('_base')) if sc.get('screen_dir') else None
    trace_path = resolve(sc.get('trace'), sc.get('_base')) if sc.get('trace') else None
    coverage_entries = sc.get('coverage_entries') or []
    if sc.get('coverage_map'):
        cmap = resolve(sc['coverage_map'], sc.get('_base'))
        with open(cmap, encoding='utf-8') as f:
            coverage_entries = json.load(f)

    pb = make_pb(rom)
    if state_in:
        with open(state_in, 'rb') as f:
            pb.load_state(f)
    else:
        # RAM cartouche non initialisee au premier demarrage : on la met a zero
        # pour que deux executions soient identiques (les traces le comparent).
        for a in range(0xA000, 0xC000):
            pb.memory[a] = 0
    cov = None
    hit_count = {}
    frame_box = [0]
    if coverage_entries:
        cov = Coverage(pb, coverage_entries, frame_box)

    mem_frames = []
    h_frame, h_screen, regs, pcs = [], [], [], []
    t0 = time.perf_counter()
    msg = 0
    for f in range(frames):
        frame_box[0] = f
        want = held_at(events, f)
        for b in enabled:
            if b in want and enabled[b]:
                pb.button_press(b)
            elif b in enabled:
                pb.button_release(b)
        render = True
        pb.tick(render=render)
        if cov:
            cov.end_frame()
        if f % every == 0 or f == frames - 1:
            data = b''.join(bytes(pb.memory[a:b]) for a, b in regions)
            mem_frames.append(data)
            h_frame.append(md5(data))
            h_screen.append(md5(pb.screen.ndarray.tobytes()))
            r = pb.register_file
            regs.append((r.A, r.F, r.B, r.C, r.D, r.E, r.HL, r.SP, r.PC))
            pcs.append(r.PC)
        if screen_dir and f in screens:
            from PIL import Image
            os.makedirs(screen_dir, exist_ok=True)
            Image.fromarray(pb.screen.ndarray[:, :, :3]).save(
                os.path.join(screen_dir, sc.get('name', 'frame') + f'_{f:05d}.png'))
        for st in state_at:
            if int(st['frame']) == f:
                path = resolve(st['path'], sc.get('_base'))
                os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
                with open(path, 'wb') as sf:
                    pb.save_state(sf)
        if f and f % 600 == 0:
            print(f'  {f}/{frames} trames ({time.perf_counter() - t0:.1f} s)', flush=True)
    elapsed = time.perf_counter() - t0
    if state_out:
        os.makedirs(os.path.dirname(state_out) or '.', exist_ok=True)
        with open(state_out, 'wb') as f:
            pb.save_state(f)
    hits = cov.hits if cov else {}
    if cov:
        cov.close()

    meta = {
        'name': sc.get('name', 'run'),
        'rom': os.path.relpath(rom, ROOT),
        'rom_md5': md5(open(rom, 'rb').read()),
        'frames': frames,
        'every': every,
        'regions': regions,
        'frame_hashes': h_frame,
        'screen_hashes': h_screen,
        'registers': regs,
        'pc': pcs,
        'coverage': {f'{b:02x}:{a:04x}': fr for (b, a), fr in sorted(hits.items())},
        'scenario_md5': md5(json.dumps(sc, sort_keys=True, default=str).encode()),
    }
    if trace_path:
        os.makedirs(os.path.dirname(trace_path) or '.', exist_ok=True)
        try:
            import numpy as np
            arr = np.frombuffer(b''.join(mem_frames), dtype=np.uint8)
            np.savez_compressed(trace_path, mem=arr, meta=json.dumps(meta).encode('utf-8'))
        except ImportError:
            with gzip.open(trace_path + '.gz', 'wb') as f:
                f.write(json.dumps(meta).encode('utf-8') + b'\n' + b''.join(mem_frames))
    pb.stop(save=False)

    tps = frames / elapsed
    print(f"{sc.get('name', 'run')} : {frames} trames, {tps:.0f} trames/s ({elapsed:.1f} s), "
          f"{len(h_frame)} releves memoire")
    if cov:
        print(f'  couverture : {len(hits)}/{len(coverage_entries)} entrees de routines executees')
    if trace_path:
        print(f'  trace -> {os.path.relpath(trace_path, ROOT)} ({os.path.getsize(trace_path) // 1024} Ko)')
    if state_out:
        print(f'  etat -> {os.path.relpath(state_out, ROOT)}')
    return 0


def cmd_state(args):
    rom = resolve(args.rom)
    pb = make_pb(rom)
    with open(args.load, 'rb') as f:
        pb.load_state(f)
    for f in range(args.frames):
        pb.tick(render=False)
    if args.save:
        os.makedirs(os.path.dirname(args.save) or '.', exist_ok=True)
        with open(args.save, 'wb') as f:
            pb.save_state(f)
        print(f'etat -> {args.save}')
    r = pb.register_file
    print(f'PC {r.PC:04X} SP {r.SP:04X} A {r.A:02X} F {r.F:02X} '
          f'HL {r.HL:04X} LY {pb.memory[0xFF44]:02X}')
    pb.stop(save=False)
    return 0


def cmd_shot(args):
    rom = resolve(args.rom)
    from PIL import Image
    pb = make_pb(rom)
    if args.load:
        with open(args.load, 'rb') as f:
            pb.load_state(f)
    for _ in range(args.frames):
        pb.tick(render=False)
    pb.tick(render=True)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    Image.fromarray(pb.screen.ndarray[:, :, :3]).save(args.out)
    print(f'capture -> {args.out}')
    pb.stop(save=False)
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    p = sub.add_parser('run')
    p.add_argument('scenario', nargs='?')
    p.add_argument('--frames', type=int)
    p.add_argument('--press')
    p.add_argument('--trace')
    p.add_argument('--state')
    p.add_argument('--state-out')
    p.add_argument('--rom', default=os.path.join(ROOT, 're', 'game.gb'))
    p.add_argument('--every', type=int)
    p.add_argument('--screens', default='')
    p.add_argument('--screen-dir')
    p = sub.add_parser('state')
    p.add_argument('--load', required=True)
    p.add_argument('--save')
    p.add_argument('--frames', type=int, default=0)
    p.add_argument('--rom', default=os.path.join(ROOT, 're', 'game.gb'))
    p = sub.add_parser('shot')
    p.add_argument('--load')
    p.add_argument('--frames', type=int, default=0)
    p.add_argument('--out', required=True)
    p.add_argument('--rom', default=os.path.join(ROOT, 're', 'game.gb'))
    args = ap.parse_args()
    if args.cmd == 'run':
        if args.scenario:
            sc = load_scenario(args.scenario)
        else:
            sc = {'rom': args.rom}
        base = sc.get('_base')
        if args.frames is not None:
            sc['frames'] = args.frames
        if args.press is not None:
            sc['press'] = args.press
        if args.trace:
            sc['trace'] = os.path.abspath(args.trace)
        if args.state:
            sc['state'] = os.path.abspath(args.state)
        if args.state_out:
            sc['state_out'] = os.path.abspath(args.state_out)
        if args.every is not None:
            sc['every'] = args.every
        if args.screens:
            sc['screens'] = [int(x) for x in args.screens.split(',') if x]
        if args.screen_dir:
            sc['screen_dir'] = os.path.abspath(args.screen_dir)
        return run(sc)
    if args.cmd == 'state':
        return cmd_state(args)
    if args.cmd == 'shot':
        return cmd_shot(args)
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())

