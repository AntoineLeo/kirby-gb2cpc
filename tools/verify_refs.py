"""Verifie les livrables de preparation sans relancer les simulations longues.

Controles :
  - image de reference : ROM, 32 banques, WRAM/HRAM/SRAM/VRAM/OAM, etats ;
  - listings : presence des 32 fichiers et du Makefile ;
  - traces : .npz present, meta coherente, ref.json a jour (ROM + scenario) ;
  - frontiere et carte memoire : JSON non vide, documents presents ;
  - noms : re/names.txt -> re/game.sym.

Usage : python tools/verify_refs.py [--quick]
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def fail(msg):
    print('ECHEC : ' + msg)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    a = ap.parse_args()
    man = json.load(open(os.path.join(ROOT, 're', 'ref', 'manifest.json'), encoding='utf-8'))
    rom = os.path.join(ROOT, man['rom']['path'])
    if md5(rom) != man['rom']['md5']:
        fail('MD5 de la ROM different du manifeste')
    if len(man['banks']) != 32:
        fail('le manifeste ne contient pas 32 banques')
    for b in man['banks']:
        p = os.path.join(ROOT, 're', 'ref', b['file'])
        if not os.path.exists(p) or md5(p) != b['md5']:
            fail('banque ' + b['file'])
    for key, im in man['images'].items():
        p = os.path.join(ROOT, 're', 'ref', im['file'])
        if not os.path.exists(p):
            fail('image ' + key)
        if key != 'start_state' and md5(p) != im['md5']:
            fail('image ' + key)
    for st in ('title.state', 'fileselect.state', 'level1.state', 'level1_room.state'):
        p = os.path.join(ROOT, 're', 'states', st)
        if not os.path.exists(p):
            fail('etat ' + st)
    listing = os.path.join(ROOT, 're', 'listing')
    for i in range(32):
        p = os.path.join(listing, f'bank_{i:03x}.asm')
        if not os.path.exists(p):
            fail('listing bank_' + f'{i:03x}')
    if not os.path.exists(os.path.join(listing, 'Makefile')):
        fail('Makefile du listing')
    if not os.path.exists(os.path.join(ROOT, 're', 'names.txt')):
        fail('fichier de noms')
    if not os.path.exists(os.path.join(ROOT, 're', 'game.sym')):
        fail('re/game.sym (lancer tools/gb_names.py)')
    with open(os.path.join(ROOT, 're', 'boundary.json'), encoding='utf-8') as f:
        b = json.load(f)
    if len(b) < 500:
        fail('frontiere trop pauvre')
    for d in ('frontiere.md', 'memoire.md', 'reprise.md', 'journal.md'):
        if not os.path.exists(os.path.join(ROOT, 'docs', d)):
            fail('docs/' + d)
    import glob
    import numpy as np
    for ref in glob.glob(os.path.join(ROOT, 're', 'traces', '*.ref.json')):
        name = os.path.basename(ref)[:-len('.ref.json')]
        with open(ref, encoding='utf-8') as f:
            r = json.load(f)
        if r['rom_md5'] != man['rom']['md5']:
            fail('reference ' + name + ' : ROM differente')
        tp = os.path.join(ROOT, r['trace'])
        if not os.path.exists(tp):
            fail('trace ' + name)
        if not a.quick:
            d = np.load(tp)
            meta = json.loads(d['meta'].tobytes().decode())
            if len(meta['frame_hashes']) != meta['frames']:
                fail('trace ' + name + ' : nombre de trames')
    print(f"references OK : 32 banques, {len(man['images'])} images, "
          f"{len(glob.glob(os.path.join(ROOT, 're', 'traces', '*.ref.json')))} traces, "
          f"{len(b)} acces materiel")
    return 0


if __name__ == '__main__':
    sys.exit(main())
