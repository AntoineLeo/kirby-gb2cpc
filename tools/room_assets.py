"""Genere les donnees CPC de la salle 1 : decor, atlas de sprites, etat WRAM.

Sorties dans build/room/ :
  bg.bin          decor 160x144 en mode 1 (40 octets/ligne)
  sprite.bin      sprites 8x16, 4 decalages, data+masque (96 octets/16 lignes)
  sprite_tab.inc  table (tuile, attributs, offset) et terminator
  wram.bin        etat WRAM C000-DFFF au point de reprise 0x11C6
  hram.bin        etat HRAM FF80-FFFE
  meta.inc        SP initial
"""
import io
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gb_cmp  # noqa: E402
from cpcgfx import mode1_byte, HW  # noqa: E402

OUT = os.path.join(ROOT, 'build', 'room')
os.makedirs(OUT, exist_ok=True)
ROM = open(os.path.join(ROOT, 're', 'game.gb'), 'rb').read()
STATE = os.path.join(ROOT, 're', 'states', 'level1_room.state')

# 4 teintes -> 4 encres CPC (0 noir, 1 bleu, 2 bleu clair, 3 blanc)
BAYER = [[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]]
LEVEL = [16, 11, 5, 0]          # probabilite de blanc (0-16)
INKS = [HW['black'], HW['white'], HW['white'], HW['white']]

def ink_for(sh, x, y):
    return 1 if BAYER[y & 3][x & 3] < LEVEL[sh] else 0


def shade(rgb):
    g = rgb[0]
    if g < 40:
        return 3
    if g < 120:
        return 2
    if g < 210:
        return 1
    return 0


def gb_tile_pixels(vram, tile, flip_x=False, flip_y=False):
    off = tile * 16
    rows = []
    for y in range(8):
        lo = vram[off + y * 2]
        hi = vram[off + y * 2 + 1]
        row = []
        for x in range(8):
            b = 7 - x
            row.append(((lo >> b) & 1) | (((hi >> b) & 1) << 1))
        rows.append(row)
    if flip_x:
        rows = [list(reversed(r)) for r in rows]
    if flip_y:
        rows = list(reversed(rows))
    return rows


def main():
    from pyboy import PyBoy
    pb = PyBoy(os.path.join(ROOT, 're', 'game.gb'), window='null',
               sound_emulated=False, ram_file=io.BytesIO(b'\0' * 8192))
    with open(STATE, 'rb') as f:
        pb.load_state(f)
    # collecte OAM initiale (avant tout tick)
    frames = {}
    for i in range(40):
        y, x, t, a = pb.memory[0xFE00 + 4 * i:0xFE04 + 4 * i]
        if 0 < y < 160 and 0 < x < 168:
            key = (t & 0xFE, a & 0x60)
            frames[key] = None
    for _ in range(2):
        pb.tick(render=False)
    lcdc = pb.memory[0xFF40]
    bgp, obp0, obp1 = pb.memory[0xFF47], pb.memory[0xFF48], pb.memory[0xFF49]
    vram = bytes(pb.memory[0x8000:0xA000])
    # decor sans sprites (bit 1 de LCDC)
    pb.memory[0xFF40] = lcdc & ~2
    pb.tick(render=False)
    screen = pb.screen.image.copy()
    pb.memory[0xFF40] = lcdc
    pb.tick(render=False)
    # sprites utilises en marchant a droite
    for k in range(120):
        if k >= 5:
            pb.button_press('right')
        else:
            pb.button_release('right')
        pb.tick(render=False)
        for i in range(40):
            y, x, t, a = pb.memory[0xFE00 + 4 * i:0xFE04 + 4 * i]
            if 0 < y < 160 and 0 < x < 168:
                key = (t & 0xFE, a & 0x60)
                frames[key] = None
    pb.stop(save=False)

    # decor : 160x144 -> 40 octets/ligne, centre x=20 octets, y=28
    screen = screen.convert('RGB')
    w, h = screen.size
    assert (w, h) == (160, 144), (w, h)
    bg = bytearray()
    for y in range(144):
        for bx in range(40):
            pix = []
            for i in range(4):
                g = screen.getpixel((bx * 4 + i, y))[0]
                pix.append(ink_for(shade((g, g, g)), bx * 4 + i, y))
            bg.append(mode1_byte(pix))
    open(os.path.join(OUT, 'bg.bin'), 'wb').write(bg)

    # atlas de sprites
    atlas = bytearray()
    table = []
    for (tile, attr), _ in sorted(frames.items()):
        off = len(atlas)
        table.append((tile, attr, off))
        fx, fy = bool(attr & 0x20), bool(attr & 0x40)
        top = gb_tile_pixels(vram, tile, fx, fy)
        bot = gb_tile_pixels(vram, tile | 1, fx, fy)
        rows = top + bot
        pal = obp0 if not (attr & 0x10) else obp1
        for shift in range(1):
            for row_idx, row in enumerate(rows):
                pix = [None] * 12
                for i in range(8):
                    c = row[i]
                    if c == 0:
                        continue
                    sh = (pal >> (c * 2)) & 3
                    pix[shift + i] = 1 if sh < 2 else 0
                for b in range(3):
                    chunk = pix[b * 4:b * 4 + 4]
                    inks = [0 if p is None else p for p in chunk]
                    atlas.append(mode1_byte(inks))
                    mask = 0
                    for i, p in enumerate(chunk):
                        if p is not None:
                            mask |= (1 << (7 - i)) | (1 << (3 - i))
                    atlas.append(mask)
    open(os.path.join(OUT, 'sprite.bin'), 'wb').write(atlas)
    with open(os.path.join(OUT, 'sprite_tab.inc'), 'w', encoding='utf-8') as f:
        f.write('sprite_tab:\n')
        for tile, attr, off in table:
            f.write(f'        db ${tile:02X}, ${attr:02X}\n')
            f.write(f'        dw sprite_atlas+{off}\n')
        f.write('        db $FF\n')
    print(f'sprites : {len(table)} frames, {len(atlas)} octets')
    print('frames', [(hex(t), hex(a)) for t, a, _ in table])

    # etat WRAM/HRAM au point de reprise
    tm, meta, _ = gb_cmp.load_trace('room_loop')
    ref = gb_cmp.mem_matrix(tm, meta)
    amap = gb_cmp.addr_map(meta)
    idx = {a: i for i, a in enumerate(amap)}
    frame0 = ref[0]
    wram = bytes(int(frame0[idx[a]]) for a in range(0xC000, 0xE000))
    hram = bytes(int(frame0[idx[a]]) for a in range(0xFF80, 0x10000))
    open(os.path.join(OUT, 'wram.bin'), 'wb').write(wram)
    open(os.path.join(OUT, 'hram.bin'), 'wb').write(hram)
    sp = meta['registers'][0][7]
    with open(os.path.join(OUT, 'meta.inc'), 'w', encoding='utf-8') as f:
        f.write(f'START_SP equ ${sp:04X}\n')
        f.write('room_inks: db ' + ', '.join(f'${v:02X}' for v in INKS) + '\n')
    print(f'WRAM {len(wram)} octets, HRAM {len(hram)}, SP ${sp:04X}')


if __name__ == '__main__':
    main()
