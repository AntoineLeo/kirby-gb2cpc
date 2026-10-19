"""Comparaison tour par tour : original Game Boy contre portage CPC.

Deux usages :
  record  : enregistre UNE FOIS la reference d'un scenario (gb_sim.py) ;
  self    : rejoue le GB et compare a la reference (controle du simulateur) ;
  port    : compare la reference a la logique Z80 du portage (gb_tick).

En cas d'ecart, affiche un diagnostic court : premier tour different,
adresses en cause, valeurs, routines GB executees juste avant, et instructions
candidates qui ecrivent ces adresses (lues dans re/listing et build/game.lst),
puis ecrit le detail dans re/traces/<scenario>.diff.txt.

La reference n'est recalculee que si la ROM ou le scenario change (MD5 dans
re/traces/<scenario>.ref.json).

Usage :
  python tools/gb_cmp.py record level1
  python tools/gb_cmp.py self level1
  python tools/gb_cmp.py port level1 [--frames N]
"""
import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

TRACES = os.path.join(ROOT, 're', 'traces')


def md5_file(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def scenario_path(name):
    p = os.path.join(ROOT, 're', 'scenarios', name + '.json')
    if not os.path.exists(p):
        raise SystemExit(f'scenario introuvable : {p}')
    return p


def load_scenario(name):
    with open(scenario_path(name), encoding='utf-8') as f:
        sc = json.load(f)
    sc['_base'] = os.path.dirname(scenario_path(name))
    return sc


def scenario_md5(sc):
    keep = {k: v for k, v in sc.items() if not k.startswith('_') and k not in
            ('trace', 'screen_dir', 'states', 'state_out')}
    state = sc.get('state')
    if state:
        p = state if os.path.isabs(state) else os.path.join(ROOT, state)
        if os.path.exists(p):
            keep['state_md5'] = md5_file(p)
    return hashlib.md5(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()


def trace_paths(name):
    return (os.path.join(TRACES, name + '.npz'),
            os.path.join(TRACES, name + '.ref.json'))


def record(name, force=False):
    sc = load_scenario(name)
    rom = os.path.join(ROOT, sc.get('rom', 're/game.gb'))
    want = {'rom_md5': md5_file(rom), 'scenario_md5': scenario_md5(sc),
            'trace': os.path.relpath(trace_paths(name)[0], ROOT)}
    tp, rp = trace_paths(name)
    if os.path.exists(rp) and not force:
        with open(rp, encoding='utf-8') as f:
            have = json.load(f)
        if have == want and os.path.exists(tp):
            print(f'{name} : reference deja a jour (MD5 image et scenario identiques)')
            return 0
    sc2 = dict(sc)
    sc2['trace'] = tp
    sc2['name'] = name
    import gb_sim
    gb_sim.run(sc2)
    with open(rp, 'w', encoding='utf-8') as f:
        json.dump(want, f, indent=1)
    print(f'{name} : reference enregistree -> {os.path.relpath(tp, ROOT)}')
    return 0


def load_trace(name):
    import numpy as np
    tp, rp = trace_paths(name)
    if not os.path.exists(tp):
        raise SystemExit(f'trace absente : {tp} (lancer record {name})')
    d = np.load(tp)
    meta = json.loads(d['meta'].tobytes().decode('utf-8'))
    return d['mem'].copy(), meta, np.load(tp)


def mem_matrix(mem, meta):
    import numpy as np
    size = sum(b - a for a, b in meta['regions'])
    n = len(meta['frame_hashes'])
    return np.asarray(mem[:n * size]).reshape(n, size)


def addr_map(meta):
    out = []
    for lo, hi in meta['regions']:
        out += list(range(lo, hi))
    return out


def compare(name, other_mem=None, other_meta=None, other_label='portage'):
    import numpy as np
    mem, meta, _ = load_trace(name)
    ref = mem_matrix(mem, meta)
    amap = addr_map(meta)
    if other_mem is None:
        # self : rejoue le GB et compare a la reference
        sc = load_scenario(name)
        sc2 = dict(sc)
        sc2['trace'] = os.path.join(TRACES, name + '.self.npz')
        sc2['name'] = name + '.self'
        import gb_sim
        gb_sim.run(sc2)
        d = np.load(sc2['trace'])
        other_meta = json.loads(d['meta'].tobytes().decode('utf-8'))
        other_mem = d['mem']
        other_label = 'GB rejoue'
    got = mem_matrix(other_mem, other_meta)
    n = min(len(ref), len(got), len(meta['frame_hashes']), len(other_meta['frame_hashes']))
    diff_frame = None
    for f in range(n):
        if not np.array_equal(ref[f], got[f]):
            diff_frame = f
            break
    detail = []
    if diff_frame is None:
        print(f'{name} : OK, {n} tours identiques ({other_label})')
        if len(ref) != len(got):
            print(f'  attention : {len(ref)} tours de reference, {len(got)} cotes {other_label}')
        return 0
    a, b = ref[diff_frame], got[diff_frame]
    idx = np.nonzero(a != b)[0]
    diff = [(amap[i], int(a[i]), int(b[i])) for i in idx[:40]]
    pc_gb = meta['registers'][diff_frame][8] if diff_frame < len(meta['registers']) else -1
    detail.append(f'premier tour different : {diff_frame} / {n}')
    detail.append(f'PC GB a ce tour : {pc_gb:04X}')
    detail.append(f'{len(idx)} adresses differentes, 40 premieres (adresse, GB, {other_label}) :')
    for ad, va, vb in diff:
        detail.append(f'  {ad:04X}  {va:02X}  {vb:02X}')
    # routines GB executees juste avant
    before = [(int(fr), k) for k, fr in meta.get('coverage', {}).items() if int(fr) <= diff_frame]
    before.sort()
    detail.append('dernieres routines GB executees (entree, premiere trame) :')
    for fr, k in before[-12:]:
        detail.append(f'  {k}  trame {fr}')
    pcs = meta.get('pc', [])
    if pcs:
        seq = []
        for f in range(max(0, diff_frame - 20), diff_frame + 1):
            if f < len(pcs) and (not seq or seq[-1][1] != pcs[f]):
                seq.append((f, pcs[f]))
        detail.append('PC GB echantillonnes avant l\'ecart (trame, PC) :')
        for f, pc in seq[-12:]:
            detail.append(f'  trame {f}  PC {pc:04X}')
    # instructions candidates qui ecrivent ces adresses dans le listing GB
    addrs = {ad for ad, _, _ in diff[:10]}
    cands = writer_candidates(addrs, 'gb')
    detail.append('instructions candidates cote GB (re/listing) :')
    detail += cands or ['  (aucune instruction a adresse absolue trouvee)']
    if other_label != 'GB rejoue':
        cands = writer_candidates(addrs, 'cpc')
        detail.append('instructions candidates cote CPC (build/game.lst) :')
        detail += cands or ['  (aucune instruction a adresse absolue trouvee)']
    out = os.path.join(TRACES, name + '.diff.txt')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(detail) + '\n')
    print(f'{name} : ECART au tour {diff_frame}, {len(idx)} adresses ; detail -> {os.path.relpath(out, ROOT)}')
    for line in detail[:14]:
        print('  ' + line)
    return 1


WRITE_RE = re.compile(r'\[\$([0-9a-fA-F]{4})\]|\[\$FF([0-9a-fA-F]{2})\]')
GB_LABEL_RE = re.compile(r'^(?:Call|Jump)_([0-9a-f]{3})_([0-9a-f]{4}):')


def writer_candidates(addrs, side):
    """Instructions qui ecrivent une adresse absolue (candidats, pas preuve)."""
    out = []
    if side == 'gb':
        base = os.path.join(ROOT, 're', 'listing')
        files = [os.path.join(base, f) for f in sorted(os.listdir(base)) if f.startswith('bank_')]
    else:
        p = os.path.join(ROOT, 'build', 'game.lst')
        files = [p] if os.path.exists(p) else []
    want = {f'{a & 0xFFFF:04x}' for a in addrs}
    want_ff = {f'{a & 0xFF:02x}' for a in addrs if 0xFF00 <= a <= 0xFFFF}
    cur = None
    last_c = None
    for path in files:
        try:
            f = open(path, encoding='utf-8', errors='replace')
        except OSError:
            continue
        with f:
            for line in f:
                m = GB_LABEL_RE.match(line)
                if m:
                    cur = f'{int(m.group(1), 16):02x}:{m.group(2)}'
                low = line.lower()
                mc = re.search(r'\bld\s+c,\s*\$([0-9a-f]{2})', low)
                if mc:
                    last_c = mc.group(1)
                if 'ldh [c], a' in low and last_c is not None:
                    full = 0xFF00 | int(last_c, 16)
                    if full in addrs:
                        out.append(f'  {cur or "?"} {line.strip()[:110]}  '
                                   f'(ecriture indirecte, C=${last_c})')
                        if len(out) >= 12:
                            return out
                if '[' not in line:
                    continue
                hit = None
                for mm in WRITE_RE.finditer(low):
                    if mm.group(1):
                        if mm.group(1) in want:
                            hit = '$' + mm.group(1)
                    elif mm.group(2) in want_ff:
                        hit = '$FF' + mm.group(2)
                if not hit:
                    continue
                # heuristique : instruction d'ecriture (le crochet est destination)
                if not re.search(r'\]\s*,', low):
                    continue
                if not re.search(r'\b(ld|ldh|ldi|ldd|set|res|inc|dec|pop|push)\b', low):
                    continue
                if re.search(r'\b(ld|ldh)\s+[a-fhl]+\s*,\s*\[', low):
                    continue
                out.append(f'  {cur or "?"} {line.strip()[:110]}')
                if len(out) >= 12:
                    return out
    return out


def load_port_state():
    """Charge build/game.bin dans un Z80 64 Ko et rend (sim, adresse gb_tick)."""
    try:
        from skoolkit import CSimulator
    except ImportError:
        raise SystemExit('skoolkit manquant : python -m pip install skoolkit')
    import importlib.util
    spec = importlib.util.spec_from_file_location('port_config', os.path.join(ROOT, 'port_config.py'))
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    binp = os.path.join(ROOT, getattr(cfg, 'BIN', 'build/game.bin'))
    symp = os.path.join(ROOT, getattr(cfg, 'SYM', 'build/game.sym'))
    if not (os.path.exists(binp) and os.path.exists(symp)):
        raise SystemExit('portage pas encore construit (build/game.bin et build/game.sym)')
    import sim64  # noqa: F401  (simulateur 64 Ko fourni par le kit)
    code = open(binp, 'rb').read()
    mem = bytearray(65536)
    load = int(getattr(cfg, 'LOAD_ADDR', 0x0200))
    mem[load:load + len(code)] = code
    sim = CSimulator(mem)
    sym = open(symp, encoding='utf-8', errors='replace').read()
    m = re.search(r'^' + re.escape(getattr(cfg, 'TICK_SYMBOL', 'gb_tick')) +
                  r':\s+EQU\s+0x([0-9A-Fa-f]+)', sym, re.M)
    if not m:
        raise SystemExit('symbole %s introuvable dans %s' %
                         (getattr(cfg, 'TICK_SYMBOL', 'gb_tick'), symp))
    return sim, int(m.group(1), 16), cfg


def port_compare(name, frames=None):
    """Compare la trace GB a un pas de logique Z80 (CFG.TICK_SYMBOL)."""
    import numpy as np
    mem, meta, _ = load_trace(name)
    ref = mem_matrix(mem, meta)
    amap = addr_map(meta)
    sim, tick, cfg = load_port_state()
    regions = [tuple(r) for r in meta['regions']]
    compare = list(getattr(cfg, 'COMPARE', [])) or list(amap)
    mask = dict(getattr(cfg, 'MASK', {}))
    stack = int(getattr(cfg, 'PORT_STACK', 0x5FE0))
    ret = int(getattr(cfg, 'PORT_RETURN', stack + 0x10))
    n = min(len(ref) - 1, frames or len(ref) - 1)
    compared = mismatched = skipped = 0
    first = []
    zmem = sim.memory
    for i in range(1, n):
        before, after = ref[i - 1], ref[i]
        if not getattr(cfg, 'gb_logic_ran', lambda a, b: True)(dict(zip(amap, before)),
                                                             dict(zip(amap, after))):
            skipped += 1
            continue
        changed = any(before[amap.index(a)] != after[amap.index(a)] for a in compare)
        if not changed:
            skipped += 1
            continue
        for a in amap:
            zmem[a] = int(before[amap.index(a)])
        zmem[stack] = ret & 0xFF
        zmem[stack + 1] = ret >> 8
        sim.registers[12] = stack
        sim.run(tick, ret, interrupts=False)
        got = [zmem[a] for a in compare]
        want = [int(after[amap.index(a)]) for a in compare]
        diff = [a for a, va, vb in zip(compare, want, got)
                if (va ^ vb) & mask.get(a, 0xFF)]
        compared += 1
        if diff:
            mismatched += 1
            if len(first) < 8:
                first.append((i, [(f'{a:04X}', f'{after[amap.index(a)]:02X}',
                                  f'{zmem[a]:02X}') for a in diff[:10]]))
    print(f'{name} : port {compared} pas compares, {mismatched} differents '
          f'({skipped} trames sans pas de logique ignorees)')
    for i, d in first:
        print(f'  trame {i} : (adresse, GB, Z80)', d)
    return 0 if mismatched == 0 else 1


def selftest(name='level1'):
    """Verifie que le diagnostic se declenche sur un ecart injecte."""
    import numpy as np
    mem, meta, _ = load_trace(name)
    arr = mem.copy()
    size = sum(b - a for a, b in meta['regions'])
    amap = addr_map(meta)
    target = 0xFFA5 if 0xFFA5 in amap else amap[0]
    frame = min(100, len(meta['frame_hashes']) - 1)
    pos = frame * size + amap.index(target)
    arr[pos] ^= 0x01
    rc = compare(name, arr, meta, 'test')
    if rc != 1:
        print('ECHEC : un ecart injecte n\'a pas ete detecte')
        return 1
    print(f'selftest OK : ecart injecte en {target:04X} trame {frame} detecte, diagnostic ecrit')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['record', 'self', 'port', 'selftest'])
    ap.add_argument('scenario', nargs='?', default='level1')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--frames', type=int)
    args = ap.parse_args()
    if args.action == 'record':
        return record(args.scenario, args.force)
    if args.action == 'self':
        return compare(args.scenario)
    if args.action == 'selftest':
        return selftest(args.scenario)
    return port_compare(args.scenario, args.frames)


if __name__ == '__main__':
    sys.exit(main())
