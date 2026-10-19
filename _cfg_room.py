import os
ROOT = r"C:\projets\kirby-gb2cpc"
ROM = os.path.join(ROOT, "build/room/rom.gb")
LOGIC_OUT = os.path.join(ROOT, "build/room/gb_logic.asm")
ROOTS = {0x11C6: "boucle salle niveau 1", 0x041E: "UpdatePadState", 0x2BFD: "VBlank entites", 0x5B85: "routine 5B85", 0x5BD2: "routine 5BD2", 0x5813: "routine 5813", 0x5819: "routine 5819"}
STUBS = {0x0343: "gb_vblank", 0x0357: "read_input_native", 0x4368: "S_RET", 0xDA10: "S_RET", 0xFF88: "S_RET"}
CODE_PTRS = [2298, 2336, 2393, 2412, 2440, 2314, 2455, 2572, 2584, 2625, 2646, 2671, 2740, 2787, 2847, 2359, 2368, 2490, 2510, 2530, 2551, 2324, 2289, 2428, 2596, 2344, 2378, 2464, 2694, 2756, 2878, 2799, 2932, 2948, 2389, 2408, 2817, 2823, 2829, 2835, 2841, 2609, 2617, 15104, 4609, 11010, 5891, 6404, 4869, 15621, 2822, 9990, 1287, 4871, 8455, 11527, 14599, 1121, 22545, 13233]
DATA_PTRS = []
DATA_BLOCKS = []
DATA_LABELS = []
PATCHES = {0x05DD: "jp select_bank", 0x05F3: "jp select_bank_no_int", 0x0620: "jp far_hl", 0x015E: "jp G_016F", 0x0452: "jp G_0461"}
TRACE_ENTRIES = [0x0100,0x0040,0x0048,0x0050,0x0058,0x0060]
RST_JUMPTABLE = {}
RST_INLINE_DATA = {}
TABLE_LEN = {}
REGIONS = [(0xC000,0xE000),(0xFF80,0x10000),(0xA000,0xC000)]
COMPARE = list(range(0xC000,0xE000))
MASK = {}
