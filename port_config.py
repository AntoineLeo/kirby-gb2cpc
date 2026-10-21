"""Configuration du portage vers l'Amstrad CPC (un fichier par jeu). Lu par tools/*.py.

Niveau 1 de Kirby's Dream Land 2 : la logique GB est traduite et prouvee identique
tour par tour (banc build/l1, trace level1_loop). Les valeurs viennent de
_cfg_l1.py (banc de verification) et restent synchronisees avec lui.

Carte memoire CPC (docs/portage.md §2, resolution des contradictions) :
  $0000-$01FF vecteurs + pile moteur      $A000-$BFFF SRAM GB (native)
  $0200-$3FFF moteur + code traduit       $C000-$DFFF RAM GB (native)
  $4000-$7FFF page commutee : fenetre     $E000-$F6BF ecran mode 1 (5 760 o)
  de banque (configs RAM 4-6)             $F6C0-$FDFF donnees moteur
  $8000-$9FFF VRAM GB (native)            $FE00-$FFFF OAM/I/O/HRAM (natifs)
La fenetre de banque ($4000-$7FFF) monte une page etendue par banque GB
commutee ; la config RAM 4-7 laisse $C000-$FFFF sur la RAM principale, donc
la RAM GB garde ses adresses et la comparaison tour par tour reste directe.
"""

# --- Fichiers ------------------------------------------------------------------
ROM = 're/game.gb'                            # ROM GB
SYM_OUT = 're/game.sym'                       # gb_trace.py -> blocs code/donnees pour mgbdis
LOGIC_OUT = 'gb/gb_logic.asm'                 # gb2z80.py -> logique traduite (Z80)
BIN = 'build/game.bin'                        # binaire CPC construit (partie A)
BANKS_BIN = 'build/game_banks.bin'            # banques 1E/0F/1F/1A ($F6C0-$FDFF)
BANKS_LOAD = 0xF6C0
SYM = 'build/game.sym'                        # symboles du binaire CPC

# --- Conventions RST du jeu -----------------------------------------------------
RST_JUMPTABLE = {}
RST_INLINE_DATA = {}
TABLE_LEN = {}

# --- Traceur --------------------------------------------------------------------
TRACE_ENTRIES = [0x0100, 0x0040, 0x0048, 0x0050, 0x0058, 0x0060]

# --- Logique a traduire (identique a _cfg_l1.py) --------------------------------
ROOTS = {0x3396: "boucle de jeu", 0x0040: "VBlank", 0x2BFD: "VBlank entites",
         0x0DA4: "cible far_hl", 0x0DCE: "cible far_hl", 0x0DF3: "cible far_hl",
         0x0DF6: "cible far_hl", 0x0DFF: "cible far_hl", 0x0F50: "cible far_hl",
         0x0F77: "cible far_hl", 0x1067: "cible far_hl", 0x1080: "cible far_hl",
         0x10E6: "cible far_hl", 0x1166: "cible far_hl", 0x11BE: "cible far_hl",
         0x1286: "cible far_hl", 0x2A2B: "cible far_hl", 0x2B91: "cible far_hl",
         0x3576: "cible far_hl", 0x357F: "cible far_hl", 0x35A2: "cible far_hl",
         0x383C: "cible far_hl", 0x3A6B: "cible far_hl"}
STUBS = {0x0343: "gb_vblank", 0x0357: "S_RET", 0xDA10: "S_RET", 0xFF88: "S_RET"}
CODE_PTRS = [2298, 2336, 2393, 2412, 2440, 2314, 2455, 2572, 2584, 2625, 2646, 2671,
             2740, 2787, 2847, 2359, 2368, 2490, 2510, 2530, 2551, 2324, 2289, 2428,
             2596, 2344, 2378, 2464, 2694, 2756, 2878, 2799, 2932, 2948, 2389, 2408,
             2817, 2823, 2829, 2835, 2841, 2609, 2617, 15104, 4609, 11010, 5891, 6404,
             4869, 15621, 2822, 9990, 1287, 4871, 8455, 11527, 14599, 1121, 13233]
DATA_PTRS = [0x29C9, 0x2BF0, 0x3098, 0x30C7]
DATA_BLOCKS = [(0x29C9, 0x2A29, 'db'), (0x2BF0, 0x2BFD, 'db'),
               (0x3098, 0x309C, 'db'), (0x30C7, 0x3100, 'db')]
DATA_LABELS = []
PATCHES = {0x05DD: "jp select_bank", 0x05F3: "jp select_bank_no_int", 0x0620: "jp far_dispatch",
           0x015E: "jp G_016F", 0x0452: "jp G_0461", 0x33AF: "jp G_33B1",
           0x2C88: "ld h,D_30C7/256", 0x2D1C: "ld h,D_30C7/256",
           0x2BD8: "ld h,D_2BF0/256", 0x2F01: "adc a,D_30C7/256"}
BANK_ENTRIES = {
    0x01: [0x4027, 0x450E, 0x45E4, 0x46BD, 0x46E1, 0x4792, 0x481B, 0x4821, 0x4967,
           0x72BE, 0x72E5, 0x7407, 0x79F4, 0x7B40],
    0x02: [0x747D],
    0x07: [0x40E2, 0x4105, 0x4128, 0x41DC, 0x4259, 0x43A0, 0x43CB, 0x4584, 0x4611,
           0x4662, 0x4A93, 0x5ADA, 0x5B28, 0x5B85, 0x5BD2, 0x7452, 0x746C],
    0x08: [0x4000, 0x473A, 0x5ED9, 0x5F76, 0x607D, 0x615B, 0x6192, 0x6E10, 0x7012,
           0x7067, 0x741F],
    0x0B: [0x785B],
    0x0E: [0x60B2],
    0x0F: [0x4841],
    0x1A: [0x4246, 0x424E, 0x427B, 0x47F6, 0x4829],
    0x1E: [0x4299, 0x4368, 0x5DFF, 0x5FEB, 0x6002, 0x6011, 0x602E, 0x606D],
    0x1F: [0x4232],
}

# --- Comparaison port (gb_cmp.py port) ------------------------------------------
TICK_SYMBOL = 'gb_tick'
LOAD_ADDR = 0x0200
PORT_STACK = 0xDFC0                          # dans la zone pile exclue de la comparaison
PORT_WINDOWS = {4: 0x07, 5: 0x0F, 6: 0x1E, 7: 0x1F}  # config RAM -> banque (suit banke_cfg)
REGIONS = [(0xC000, 0xE000), (0xFF80, 0x10000), (0xA000, 0xC000)]  # identique aux traces
COMPARE = [a for a in range(0xC200, 0xE000)
           if not (0xD200 <= a < 0xD400 or 0xD800 <= a < 0xD820
                   or 0xDA00 <= a < 0xDA30 or 0xDA3E <= a < 0xDA46
                   or a >= 0xDF00)]
MASK = {}


def gb_logic_ran(before, after):
    """Vrai si un pas de logique GB a eu lieu entre deux trames (compteur DA0E)."""
    return before.get(0xDA0E) != after.get(0xDA0E)
