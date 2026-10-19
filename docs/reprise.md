# Reprise — Kirby's Dream Land 2 → Amstrad CPC 6128

## 1. État

Préparation terminée (obligatoires) : cartouche MBC1 512 Ko, 32 banques, 8 Ko SRAM,
images et traces de référence, listing réassemblable à l'identique, frontière et carte
mémoire.

Portage commencé :
- conception écrite dans `docs/portage.md` (mémoire 128 Ko, mode 1 160×144, cadence,
  défilement, outils, vérification) ;
- `tools/gb_profile.py` (banques utilisées, PC/SP par trame) et
  `tools/gb_video_profile.py` (OAM, tuiles, défilement) ajoutés ;
- `tools/gb_record_at.py` : trace ancrée sur la boucle de jeu (`03:3396`), format
  identique aux traces de référence ;
- traduction Z80 du niveau 1 (banque 0 + gestionnaires de script, 7 162 octets de code
  GB → ~15 Ko Z80) : `build/l1/gb_logic.asm` ;
- banc d'essai `build/l1/test.asm` + `tools/l1_cmp.py` (CSimulator 64 Ko, banque de
  données fixe) : **0 octet d'écart** sur les trames sans événement d'entité, hors
  tampons d'affichage, entrées et pile ; écarts localisés CE2F-CE3C aux trames 4-5,
  attribués aux banques commutées encore stubbées.

Affichage CPC : décor 160×144 converti en mode 1, image 320×200 centrée.
`build/kirby-demo.dsk` se lance par `RUN"GAME` et affiche la salle 1 ; Kirby
(16×16) se déplace aux flèches QAOP ou au joystick, avec restauration du fond
et sans traînée. C’est une **version fonctionnelle de démonstration** (décor et
sprite authentiques, déplacement), pas encore le jeu complet : la logique GB
(G_11C6, WRAM, banques), les ennemis, le défilement et le son ne sont pas
branchés dans ce binaire.

## 2. Commandes

Installation (une fois) :
```
powershell -ExecutionPolicy Bypass -File install.ps1
```

Contrôle unique (préparation) :
```
powershell -ExecutionPolicy Bypass -File check.ps1 rapide
powershell -ExecutionPolicy Bypass -File check.ps1 complet
```

Profilage :
```
python tools/gb_profile.py re/scenarios/level1.json --out /tmp/prof.json
python tools/gb_video_profile.py re/scenarios/level1_actions.json --out /tmp/video.json
```

Trace ancrée sur la boucle (point de reprise stable pour la comparaison du port) :
```
python tools/gb_record_at.py --scenario re/scenarios/level1.json --pc 3396 \
    --out re/traces/level1_loop.npz
```

Traduction + banc d'essai du niveau 1 :
```
$env:GB2ZX_CONFIG=(Resolve-Path _cfg_l1.py)
python tools/gb2z80.py
& "$env:LOCALAPPDATA\sjasmplus\sjasmplus-1.24.0.win\sjasmplus.exe" `
    --nologo --msg=war --sym=build/l1/test.sym build/l1/test.asm
Copy-Item test.bin build/l1/test.bin -Force
python tools/l1_cmp.py
```
Variables utiles : `BANK` (banque de données fixe, défaut `1F`), `FRAMES` (défaut 60).

## 3. Prochaine action exacte

Remplacer la banque de données fixe par la vraie fenêtre de banque :
1. cartographier les 4 pages de 16 Ko du 6128 et la fenêtre de données (cible :
   écran 160×144 = 5 760 octets, RAM GB native `C000-DFFF`, code en page commutée) ;
2. écrire `select_bank` qui copie (ou mappe) la banque `FFA4` dans la fenêtre ;
3. traduire les banques 07/0F/1E/1F (mêmes roots + `far_hl`) et remplacer les
   `S_SWITCHABLE` par les vrais appels ;
4. corriger le rendu sprite CPC (trainee noire/bleue dans `build/demo/demo2.dsk`) :
   atlas, décalage, restauration du fond ; vérifier par capture avant/après ;
5. brancher `G_11C6` + `read_input_native` dans le binaire CPC et relancer
   `tools/room_cmp.py` ;
6. seulement ensuite, passer au contrôle complet et au son.

## 4. Pièges

- `CSimulator(mem)` **copie** la mémoire : travailler ensuite sur `sim.memory`, pas sur
  le `bytearray` d'origine.
- La mémoire `0000-3FFF` du CSimulator est une ROM protégée : un marqueur ou une table
  écrite à `3Fxx` est ignoré. Mettre les marqueurs de test en RAM (`BFF0`…), hors
  régions injectées, ou désactiver l'injection SRAM pour un test ciblé.
- Le `.sym` doit être régénéré après chaque assemblage ; un symbole périmé décale le PC
  d'un octet et produit des boucles incompréhensibles.
- La trace ancrée sur `03:3396` est prise **au début de la boucle**, pas au VBlank. Le
  pas de port va de `G_3396` à `G_3396` suivant, avec `WaitVBlank` remplacé par
  `gb_vblank` (compteur `DA0E` + boucle VBlank `2BFD`).
- Toute écriture >2 min (jeu complet, comparaison longue) se lance en tâche de fond.
- PyBoy persiste `re/game.gb.ram` : passer par `tools/gb_sim.py`/`gb_record_at.py`
  (RAM zéro) ou supprimer ce fichier.
- Les hooks PyBoy modifient la ROM : ne les poser que sur des entrées réellement
  exécutées (`re/coverage_safe.json`).
- Les adresses de la zone commutable n'ont de sens qu'avec `FFA4` : ne pas confondre
  `1e:4357` et l'adresse logique `$4357`.
- `check.sh` réextrait l'image : l'état de départ doit garder le MD5
  `5d6375cc394559665444800110d96e09`.
- Le niveau 2 n'a pas d'état sauvegardé : ne pas l'annoncer comme disponible.
