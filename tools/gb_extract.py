"""Extraction d'une cartouche Game Boy : images de reference et manifeste.

La cartouche est un fichier .gb deja decompresse : il n'y a ni chargeur, ni
protection, ni compression de conteneur. Le contenu utile est :
  - 32 banques ROM de 16 Ko (MBC1) ;
  - 1 banque de RAM externe de 8 Ko (sauvegarde par pile) ;
  - l'etat CPU/RAM au demarrage du jeu (premiere image de jeu).

Sorties (par defaut re/ref/) :
  bank_00.bin ... bank_1f.bin      banques ROM, MD5 dans manifest.json
  cartram_start.bin                RAM cartouche (A000-BFFF) au demarrage
  wram_start.bin, hram_start.bin   RAM de travail au demarrage
  vram_start.bin, oam_start.bin    memoire video au demarrage (reference d'ecran)
  start_state.state                etat PyBoy complet (rechargement immediat)
  start_state.json                 registres CPU, PC, banques selectionnees
  manifest.json                    MD5 de chaque image et de la cartouche

Usage : python tools/gb_extract.py [--rom re/game.gb] [--out re/ref]
        [--frames 600] [--start-script "start@420,wait@470"]
"""
import argparse
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CART_TYPES = {
    0x00: 'ROM ONLY', 0x01: 'MBC1', 0x02: 'MBC1+RAM', 0x03: 'MBC1+RAM+BATTERY',
    0x05: 'MBC2', 0x06: 'MBC2+BATTERY', 0x08: 'ROM+RAM', 0x09: 'ROM+RAM+BATTERY',
    0x0B: 'MMM01', 0x0C: 'MMM01+RAM', 0x0D: 'MMM01+RAM+BATTERY',
    0x0F: 'MBC3+TIMER+BATTERY', 0x10: 'MBC3+TIMER+RAM+BATTERY', 0x11: 'MBC3',
    0x12: 'MBC3+RAM', 0x13: 'MBC3+RAM+BATTERY', 0x19: 'MBC5', 0x1A: 'MBC5+RAM',
    0x1B: 'MBC5+RAM+BATTERY', 0x1C: 'MBC5+RUMBLE', 0x1D: 'MBC5+RUMBLE+RAM',
    0x1E: 'MBC5+RUMBLE+RAM+BATTERY', 0x20: 'MBC6', 0x22: 'MBC7',
    0xFC: 'POCKET CAMERA', 0xFD: 'BANDAI TAMA5', 0xFE: 'HuC3', 0xFF: 'HuC1+RAM+BATTERY',
}
ROM_SIZES = {0: 2, 1: 4, 2: 8, 3: 16, 4: 32, 5: 64, 6: 128, 7: 256, 8: 512}
RAM_SIZES = {0: 0, 1: 2, 2: 8, 3: 32, 4: 128, 5: 64}


def md5(data):
    return hashlib.md5(data).hexdigest()


def header(rom):
    b = rom
    return {
        'entry': b[0x100:0x104].hex(),
        'title': b[0x134:0x144].split(b'\0')[0].decode('ascii', 'replace'),
        'cgb_flag': b[0x143],
        'cart_type': b[0x147],
        'cart_type_name': CART_TYPES.get(b[0x147], f'inconnu ({b[0x147]:02x})'),
        'rom_size_code': b[0x148],
        'rom_banks': ROM_SIZES.get(b[0x148], 0),
        'ram_size_code': b[0x149],
        'ram_kb': RAM_SIZES.get(b[0x149], 0),
        'header_checksum': b[0x14D],
        'global_checksum': (b[0x14E] << 8) | b[0x14F],
        'rom_file_size': len(b),
    }


def verify(rom, h):
    problems = []
    want = ROM_SIZES.get(h['rom_size_code'], 0) * 16384
    if want != len(rom):
        problems.append(f'taille ROM : en-tete {want} octets, fichier {len(rom)}')
    x = 0
    for a in range(0x134, 0x14D):
        x = (x - rom[a] - 1) & 0xFF
    if x != rom[0x14D]:
        problems.append(f'somme de controle en-tete : calculee {x:02x}, fichier {rom[0x14D]:02x}')
    total = (sum(rom) - rom[0x14E] - rom[0x14F]) & 0xFFFF
    if total != h['global_checksum']:
        problems.append(f'somme de controle globale : calculee {total:04x}, fichier {h["global_checksum"]:04x}')
    return problems


def parse_script(spec):
    """'start@420,a@470-478' -> [(frame, button, hold)] ; wait@N = pause sans touche."""
    events = []
    if not spec:
        return events
    for item in spec.split(','):
        item = item.strip()
        if not item:
            continue
        name, _, at = item.partition('@')
        hold = 6
        if '-' in at:
            at, _, hold_s = at.partition('-')
            hold = int(hold_s) - int(at) + 1
        events.append((int(at), name.lower(), hold))
    return sorted(events)


def run_to_start(rom_path, frames, script, state_path, out, boot_frames=360):
    from pyboy import PyBoy
    pb = PyBoy(rom_path, window='null', sound_emulated=False,
               ram_file=io.BytesIO(b'\0' * 8192))
    events = parse_script(script)
    pending = {i: ev for i, ev in enumerate(events)}
    held = set()
    boot = None
    for f in range(frames):
        if f == boot_frames:
            pb.tick(render=True)
            with open(os.path.join(out, 'boot_state.state'), 'wb') as bf:
                pb.save_state(bf)
            regs = pb.register_file
            boot = {'frame': f, 'registers': {'A': regs.A, 'F': regs.F, 'B': regs.B, 'C': regs.C,
                                              'D': regs.D, 'E': regs.E, 'HL': regs.HL, 'SP': regs.SP,
                                              'PC': regs.PC},
                    'wram_md5': md5(bytes(pb.memory[0xC000:0xE000])),
                    'state_md5': md5(open(os.path.join(out, 'boot_state.state'), 'rb').read())}
        for i, (at, button, hold) in list(pending.items()):
            if f == at:
                if button != 'wait':
                    pb.button_press(button)
                    held.add(button)
                pending[i] = (at, button, at + hold)
        for i, (at, button, end) in list(pending.items()):
            if f == end and button in held:
                pb.button_release(button)
                held.discard(button)
        pb.tick(render=False)
    pb.tick(render=True)
    with open(state_path, 'wb') as f:
        pb.save_state(f)
    regs = pb.register_file
    img = {
        'registers': {'A': regs.A, 'F': regs.F, 'B': regs.B, 'C': regs.C,
                      'D': regs.D, 'E': regs.E, 'HL': regs.HL, 'SP': regs.SP, 'PC': regs.PC},
        'frame': frames,
        'wram': bytes(pb.memory[0xC000:0xE000]),
        'hram': bytes(pb.memory[0xFF80:0xFFFF]),
        'cartram': bytes(pb.memory[0xA000:0xC000]),
        'vram': bytes(pb.memory[0x8000:0xA000]),
        'oam': bytes(pb.memory[0xFE00:0xFEA0]),
        'ppu': {f'FF{r:02X}': pb.memory[0xFF00 + r] for r in (0x40, 0x41, 0x42, 0x43, 0x44, 0x47, 0x48, 0x49, 0x4A, 0x4B)},
    }
    pb.stop(save=False)
    return img, boot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=os.path.join(ROOT, 're', 'game.gb'))
    ap.add_argument('--out', default=os.path.join(ROOT, 're', 'ref'))
    ap.add_argument('--frames', type=int, default=780,
                    help='trames avant la sauvegarde de demarrage (defaut : debut du niveau 1)')
    ap.add_argument('--start-script', default='start@420-427,a@520-527',
                    help='touches scriptees pour atteindre le demarrage')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rom = open(args.rom, 'rb').read()
    h = header(rom)
    problems = verify(rom, h)
    if problems:
        print('en-tete incoherent :')
        for p in problems:
            print('  ' + p)
        sys.exit(1)
    if h['rom_banks'] * 16384 != len(rom):
        print(f"nombre de banques incohérent : {h['rom_banks']} x 16 Ko != {len(rom)}")
        sys.exit(1)

    manifest = {
        'rom': {'path': os.path.relpath(args.rom, ROOT), 'md5': md5(rom), 'size': len(rom)},
        'header': h,
        'banks': [],
        'images': {},
        'start': {},
    }
    for i in range(h['rom_banks']):
        data = rom[i * 16384:(i + 1) * 16384]
        name = f'bank_{i:02x}.bin'
        with open(os.path.join(args.out, name), 'wb') as f:
            f.write(data)
        manifest['banks'].append({'index': i, 'file': name, 'md5': md5(data)})

    state_path = os.path.join(args.out, 'start_state.state')
    img, boot = run_to_start(args.rom, args.frames, args.start_script, state_path, args.out)
    for key, name in (('wram', 'wram_start.bin'), ('hram', 'hram_start.bin'),
                      ('cartram', 'cartram_start.bin'), ('vram', 'vram_start.bin'),
                      ('oam', 'oam_start.bin')):
        data = img[key]
        with open(os.path.join(args.out, name), 'wb') as f:
            f.write(data)
        manifest['images'][key] = {'file': name, 'size': len(data), 'md5': md5(data)}
    manifest['images']['start_state'] = {
        'file': os.path.basename(state_path), 'size': os.path.getsize(state_path),
        'md5': md5(open(state_path, 'rb').read()),
    }
    manifest['images']['boot_state'] = {
        'file': 'boot_state.state',
        'size': os.path.getsize(os.path.join(args.out, 'boot_state.state')),
        'md5': boot['state_md5'],
    }
    manifest['start'] = {'frame': img['frame'], 'registers': img['registers'], 'ppu': img['ppu'],
                         'boot': boot}
    with open(os.path.join(args.out, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    print(f"extraction OK : {h['title']} ({h['cart_type_name']}), "
          f"{h['rom_banks']} banques ROM, {h['ram_kb']} Ko RAM cartouche")
    print(f"  ROM MD5 {md5(rom)}")
    print(f"  etat de demarrage : trame {img['frame']}, PC {img['registers']['PC']:04X}, "
          f"MD5 {manifest['images']['start_state']['md5']}")
    print(f"  -> {os.path.relpath(args.out, ROOT)}/manifest.json")
    return 0


if __name__ == '__main__':
    sys.exit(main())

