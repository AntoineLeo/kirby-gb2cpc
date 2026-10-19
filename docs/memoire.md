# Carte de la mémoire — Kirby's Dream Land 2

Complément de `docs/frontiere.md`. Les noms vérifiés sont ceux du fichier de noms pour
la ROM (`re/names.txt`) ; les variables RAM sont décrites ici car mgbdis ne nomme que
les adresses ROM. Toute ligne **[hypothèse]** n'est pas prouvée.

## Plan Game Boy

| Zone | Adresse | Taille | Usage |
|---|---|---|---|
| ROM banque 0 | `0000-3FFF` | 16 Ko | vecteurs, entrée, VBlank, attente trame, entrée manette, changement de banque |
| ROM commutée | `4000-7FFF` | 16 Ko | 31 banques (MBC1, `FFA4` = banque) |
| VRAM | `8000-9FFF` | 8 Ko | tuiles/cartes, écrite par `VBlankMain` et files `C200/C300` |
| RAM cartouche | `A000-BFFF` | 8 Ko | sauvegarde (fichiers 1-3), accès par pointeurs |
| WRAM | `C000-DFFF` | 8 Ko | état du jeu, files d'affichage, pile |
| Écho | `E000-FDFF` | — | miroir de `C000-DDFF` |
| OAM | `FE00-FE9F` | 160 o | sprites |
| I/O | `FF00-FF7F` | — | manette, son, LCD, DMA, interruptions |
| HRAM | `FF80-FFFE` | 127 o | variables rapides, copie d'entrée, routines |

## Variables vérifiées

| Adresse | Nom | Format | Preuve |
|---|---|---|---|
| `FFA4` | `CurrentBank` | octet | écrit par `SetBank` (`05DD`), lu par les routines d'appel de banque |
| `FFA5` | `Pad1Held` | octet, bits actifs à 1 (A/B/Select/Start/Haut/Bas/Gauche/Droite) | écrit par `ReadPadRaw` (`03E5-0403`), lu dans toutes les banques |
| `FFA6` | `Pad1Pressed` | octet, fronts | idem |
| `FFA7` | `Pad1Released` | octet | idem |
| `FFA8` | `Pad1Repeat` | octet, compteur | idem |
| `FFA9-FFAC` | `Pad2…` | même structure | copie de `DA42-DA45` |
| `DA0C` | `FrameFlag` | bit 0 = trame écoulée | posé par `VBlankMain`, attendu par `WaitVBlank` (`0343`) |
| `DA0D` | `TimerFlag` | octet | posé par `TimerMain` (`0333`), lu en `0483` |
| `DA0E` | `FrameCounter` | octet, incrémenté à chaque attente | `WaitVBlank` (`0352-0355`) |
| `DA38` | `InputLock` | octet, non nul = entrée ignorée | `0369`, écrit en `06D0` |
| `DA3E-DA41` | `Pad1State` | courant/nouveau/relâché/répétition | `UpdatePadState` (`041E`) |
| `DA42-DA45` | `Pad2State` | idem | `03F1`, `041E` |
| `DA00/DA01` | `ScrollY/ScrollX` | paire d'octets | corrélé à `FF42/FF43` ; lue en `04D4/04DD` |
| `DA02/DA03` | `ScrollY2/ScrollX2` | paire | écrite dans `FF42/FF43` par `VBlankMain` (`0185-0191`) |
| `DA04/DA05` | `ScrollY3/ScrollX3` | paire | variante de `VBlankMain` (`018A`) |
| `CD00-CD02` | `PaletteBuffer` | BGP, OBP0, OBP1 | recopié vers `FF47-FF49` par `VBlankMain` (`0193-019F`) |
| `DA23` | `Queue1Count` | octet | nombre d'entrées de la file `C200` |
| `DA24` | `Queue2Count` | octet | nombre d'entrées de la file `C300` |
| `DA27` | `QueueFlags` | bits 0-2 | choisit les files vidées par `VBlankMain` |
| `C200…` | `DisplayQueue1` | couples (adresse VRAM 16 bits, octet) | dépilée par `VBlankMain` (`01B8-01C6`) |
| `C300…` | `DisplayQueue2` | idem | dépilée par `VBlankMain` (`01CB-01D9`) |
| `DA25`, `DA18` | `SavedSP` | 16 bits | sauvegarde de pile pendant le vidage des files |
| `DA11/DA12` | `FarCallPointer` | 16 bits | posé par `05F9/0604`, utilisé par l'appel de banque |
| `DB60` | `LevelIndex` | octet 0-based | affiché `+1` en `9C2F` par `3131` (`31C5-31CC`) ; vaut 0 au niveau 1 |
| `DEDB-DEDD` | `Score` | 3 octets BCD, gros chiffre en `DEDB` | ajout BCD en `30E0-3105` ; copié en VRAM `9C21` par `3131` |
| `DEDE` | `ScoreFlags` | bits 0/2 | bit 0 = score modifié, bit 2 = vie supplémentaire ; `310B/312D` |
| `DEE0` | `AbilityIcon` | octet, index de tuile | lu en `31D0`, copie 0x40 octets depuis la banque 7 |
| `DEE1` | `HealthBar` | octet 0-7 | nombre de segments pleins, dessiné en `9C09` par `3131` |
| `A084` | `Lives` | octet BCD (2 chiffres) | affiché en `9C2A` par `3131` ; vaut 2 au départ (HUD « 02 ») |
| `A071` | `SaveFlag` | octet | testé en `316C` pour choisir l'icône de capacité |
| `DFE8` | `StackTop` (départ) | SP = `DFE8` au début du niveau 1 | `re/ref/manifest.json` |

## Structures d'objets

**[hypothèse]** `C300` et suivants contiennent des enregistrements de 6 octets :
exemple au début du niveau 1, `D2 9B 35 25 25 35`, `D4 9B 35 25 25 35`, … (pas de 2
sur le premier octet, puis motif constant). C'est la seule structure régulière observée.
Elle est aussi utilisée comme pile temporaire par `VBlankMain` pendant le vidage des
files, donc **ne pas la déplacer sans revérifier**.

**[hypothèse]** `DDC0-DDEF` contient des coordonnées d'objets/joueur : `DDD0` et `DDE0`
évoluent avec le déplacement (ex. `DDD0` 0x27→0x4B pendant une marche à droite) et
`DDD2`/`DDE2` suivent la position écran. Format non tranché : à confirmer en corrélant
avec OAM et le code de collision.

## Zones libres candidates

Voir la liste et les réserves de `docs/frontiere.md` §6 : environ 3,9 Ko, dont
`D35C-D70F` (948 o) et `DB8A-DCFC` (371 o). À revérifier après chaque nouveau niveau.

## Pile

- SP au début du niveau 1 : `DFE8` ; au titre : `DFDC` (relevé dans les états de référence).
- La pile descend de `DFE8` vers `DF00` environ ; les scènes observées ne dépassent pas
  ~200 octets. Prévoir au moins 256 octets dans le portage, et conserver `DFE8` comme
  valeur initiale pour que les comparaisons de mémoire restent valides.
- `VBlankMain` change temporairement SP vers `C200`/`C300` puis le restaure via `DA25`.

## Ce que la carte ne dit pas

Les formats complets des tables de niveau, des objets et des ennemis ne sont pas encore
établis. La carte ne garde que ce que le fichier de noms ne peut pas porter : variables
RAM, files d'affichage, pile, zones libres candidates. Le reste se lit dans le listing
et `re/codemap.json`.


## Banc d\'essai : fenêtre de banques (mécanisme de vérification)

Le banc d\'essai (uild/l1/test.asm) reprend la carte GB à l\'identique (adresses
brutes) pour que la comparaison reste directe :

| Adresse | Contenu |
|---|---|
| - | support + logique traduite (banque 0) + banques 07/1E/0F/1F/1A |
| - | table de sauts du script (fixe, le jeu fait ld h,) |
| - | fenêtre : image de la banque FFA4 (octets ROM + tramplins jp BNN_xxxx aux points de dispatch de win_entries.json) |
| - | VRAM GB (ombre, écrite par le jeu) |
| - | SRAM GB (structures d'entités A000-B2FF, marqueurs BFF0-BFF5) |
| - | RAM GB |
| - | suite des banques traduites (08/0B/0E/02/01) — écho inutilisé par le jeu |

- select_bank (patch de /) : ld (),a + out (),a ; l1_cmp place
  l'image de la banque demandée (le CPC mappera ou copiera autrement).
- Appels vers la fenêtre : émis en adresse GB brute, ils tombent sur les tramplins.
  Appels de banque 0 dynamiques (jp hl en ) : ar_dispatch + far0_pairs.
- Données ROM lues par pointeur (calculé) : blocs DATA_BLOCKS alignés sur l'adresse
  GB d'origine + patch de l'octet haut (ld h,D_xxxx/256) — voir docs/journal.md.
