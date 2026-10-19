"""Listing desassemblable et REASSEMBLABLE a l'identique.

Etapes :
  1. tools/gb_names.py : re/names.txt + re/codemap.json -> re/game.sym ;
  2. mgbdis -> re/listing (un fichier par banque, Makefile RGBDS) ;
  3. rgbasm / rgblink / rgbfix -> re/listing/game.gb ;
  4. comparaison MD5 avec re/game.gb ; echec si different.

Usage : python tools/gb_listing.py [--check] [--keep]
  --check : ne reecrit pas le listing, verifie seulement le listing existant.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def find_tool(name):
    for d in os.environ.get('PATH', '').split(os.pathsep) + [
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'rgbds')]:
        p = os.path.join(d, name + ('.exe' if os.name == 'nt' else ''))
        if os.path.exists(p):
            return p
    return None


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        print('ECHEC : ' + ' '.join(cmd))
        tail = (p.stdout + p.stderr).strip().splitlines()[-12:]
        for line in tail:
            print('  ' + line)
        sys.exit(1)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=os.path.join(ROOT, 're', 'game.gb'))
    ap.add_argument('--listing', default=os.path.join(ROOT, 're', 'listing'))
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    original = md5(args.rom)
    if not args.check:
        run([sys.executable, os.path.join(HERE, 'gb_names.py')], ROOT)
        if os.path.isdir(args.listing):
            shutil.rmtree(args.listing)
        os.makedirs(args.listing, exist_ok=True)
        # mgbdis lit re/game.sym (meme nom que la ROM, a cote d'elle)
        run([sys.executable, os.path.join(HERE, 'mgbdis', 'mgbdis.py'), args.rom,
             '--output-dir', args.listing, '--overwrite', '--print-hex'], ROOT)
    rgbasm = find_tool('rgbasm')
    rgblink = find_tool('rgblink')
    rgbfix = find_tool('rgbfix')
    if not (rgbasm and rgblink and rgbfix):
        print('RGBDS introuvable (attendu : %LOCALAPPDATA%\\rgbds)')
        return 1
    run([rgbasm, '-o', 'game.o', 'game.asm'], args.listing)
    run([rgblink, '-n', 'game.sym', '-m', 'game.map', '-o', 'game.gb', 'game.o'], args.listing)
    run([rgbfix, '-v', '-p', '255', 'game.gb'], args.listing)
    rebuilt = os.path.join(args.listing, 'game.gb')
    got = md5(rebuilt)
    if got != original:
        print(f'ECHEC : ROM reassemblee {got}, originale {original}')
        return 1
    print(f'listing OK : {os.path.getsize(rebuilt)} octets, MD5 {got} identique a l\'original')
    print(f'  {os.path.relpath(args.listing, ROOT)}/ (32 banques + game.asm + Makefile)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
