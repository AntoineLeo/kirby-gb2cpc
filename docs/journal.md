# Journal — préparation Kirby's Dream Land 2 → CPC 6128

## Image et extraction

- `re/game.gb` : 524288 octets, MD5 `ddb5bfae32b0ca39cf8ab6c46880126c`.
- En-tête : titre `KIRBY2`, type 3 (MBC1+RAM+BATTERY), 32 banques ROM, 8 Ko RAM,
  DMG (pas CGB), sommes de contrôle valides.
- Pas de chargeur/protection/compression de conteneur : 32 images de banque de 16 Ko
  (`re/ref/bank_00.bin` … `bank_1f.bin`), MD5 par banque dans `re/ref/manifest.json`.
- État de démarrage : titre à la trame 360 (`boot_state.state`, MD5
  `c5…` voir manifeste), début du niveau 1 à la trame 780 (`start_state.state`, MD5
  `5d6375cc394559665444800110d96e09`, PC `2C04`, SP `DFE8`).
- RAM cartouche initialisée à zéro pour rendre les reprises déterministes ; PyBoy
  persistait sinon un `game.gb.ram` entre deux lancements.

## Simulateur et vitesse

- PyBoy 2.8.1, fenêtre `null`, son désactivé. Mesures (même machine) :
  - sans couverture : 800–3500 trames/s selon le scénario ;
  - avec 249 hooks de couverture : ~800 trames/s sur 60 trames, démarrage compris ;
  - extraction complète (780 trames + titre) : ~15 s.
- API : `save_state`/`load_state` (états complets), `hook_register` aux entrées de
  routines. Limite : PyBoy ne donne pas les adresses exécutées instruction par
  instruction ; la couverture est au niveau des entrées de routines, complétée par le
  PC échantillonné à chaque trame et par le traceur statique `tools/gb_codemap.py`.
- Bug PyBoy rencontré : un hook touché est retiré du dictionnaire de points d'arrêt avant
  le callback, donc `hook_deregister` échoue dedans. Solution : retirer les hooks touchés
  après `tick`, une fois par trame (`Coverage.end_frame`), et garder la première trame
  de chaque hit.
- Piège majeur : poser des hooks sur toutes les cibles de branches (`coverage_map.json`,
  4736 entrées) bloque le démarrage (des données lues sont remplacées par `BRK`).
  La carte sûre (`coverage_safe.json`, 249 entrées réellement exécutées au niveau 1)
  fonctionne.

## Listing

- mgbdis v3.0, un fichier par banque, sections `ROM0`/`ROMX`.
- `re/seeds.json` : 1611 cibles extraites d'un désassemblage brut sans `.sym` (graines
  stables, sinon la carte code/données se dégrade à chaque régénération).
- `tools/gb_codemap.py` : trace récursive par banque depuis les graines ; 4736 entrées
  de routines, zones incertaines listées. Les entrées de hooks sont filtrées aux débuts
  d'instruction réellement tracés.
- Réassemblage RGBDS : `rgbasm`/`rgblink`/`rgbfix -v -p 255` ; **MD5 identique** à
  l'original, 524288 octets. Testé plusieurs fois, y compris après ajout des noms.
- Le listing pèse ~25 Mo ; consultation ciblée uniquement (grep par adresse).

## Traces de référence

| Scénario | Départ | Trames | Contenu |
|---|---|---|---|
| `boot` | power-on | 360 | logo/titre, RAM cartouche zéro |
| `fileselect` | power-on | 520 | Start à la trame 420, écran SELECT FILE |
| `level1` | `start_state` | 600 | niveau 1, droite en continu |
| `level1_actions` | `start_state` | 900 | droite + A/B périodiques, scène de niveau |

Mémoire relevée à chaque trame : `C000-DFFF`, `FF80-FFFE`, `A000-BFFF` ; hash d'écran
par trame ; registres et PC. Auto-comparaison : 360/520/600/900 tours identiques.
États sauvegardés : `title`, `fileselect`, `level1`, `level1_room`, `level1_room2`.

## Niveau 2 — piste arrêtée

Deux essais de progression automatique (droite continue ; droite + A/B périodiques,
12 000 trames ; porte avec Gauche+Haut) ramènent à l'écran de niveau ou à la carte.
Le bot ne franchit pas la première salle. Coût d'une reprise : analyse des routines de
collision/portes (quelques heures) ou reprise manuelle à l'émulateur pour créer un état.
Non fait, signalé comme souhaitable.

## Frontière

`re/boundary.json` : 2310 accès matériels classés (VRAM 627, OAM 62, son 144, SRAM 297,
banques 80, interruptions 837, I/O 229, LCD 22, joypad 12). Appelants directs relevés
par `CALL` absolu ; les appels indirects sont marqués comme tels (ex. `ReadInput`).
Zones WRAM jamais écrites dans les quatre scénarios : ~3,9 Ko candidates, listées dans
`docs/frontiere.md` §6 (hypothèse, accès par pointeur non exclu).

## Décisions en attente (utilisateur)

- Cadence : 60 Hz d'origine contre 50 Hz CPC (ralentissement de 17 % ou compensation).
- Contrôles CPC (clavier/joystick) : à fixer avant le portage des entrées.

## Variables identifiées après la première rédaction

En suivant les routines HUD (banque 0, 3131 et 30E0) : score BCD DEDB-DEDD,
vies BCD A084 (2 au départ, affiché « 02 »), niveau 0-based DB60 (affiché +1,
0 au niveau 1), barre de vie DEE1, icône de capacité DEE0. Vérifié par les valeurs
au début du niveau et par les écritures VRAM 9C21/9C2A/9C2F/9C09.

## Portage — première tranche (niveau 1, logique)

- Profilage dynamique (`tools/gb_profile.py`) : niveau 1 = banques `00, 1E, 1F, 07, 0F`
  (5 banques), 6 390 `SetBank` sur 900 trames (~7/trame), aucun `CallBank` en jeu.
  Les `SetBank` sont toujours appelés depuis la banque 0 fixe (`ret` < $4000) : les
  banques commutées sont des feuilles appelées depuis la banque 0.
- Vidéo (`tools/gb_video_profile.py`) : max 10 sprites OAM (3,5 en moyenne, 7/ligne),
  ~2 octets OAM et ~2 octets de carte modifiés/trame, défilement X 1-2 px/trame,
  Y rare.
- Le gestionnaire de script (`00:086B`) saute par `jp hl` dans une table en `3F00`.
  Un suivi des cibles (`hook` sur `08D7`) donne 4 commandes utilisées au niveau 1 ;
  la table complète contient 72 cibles plausibles. Toutes ont été ajoutées aux roots
  (`CODE_PTRS`) pour éviter les sauts vers zéro ; `stop` est traduit en `nop`,
  `ld [a16],sp` et `swap r` sont traduits.
- `gb_vblank` du banc d'essai remplace `WaitVBlank` : incrémente `DA0E` puis appelle
  `2BFD` (boucle 8 slots entités + son). Le vrai handler VBlank (contexte de pile
  `DA1A`) n'est pas encore appelé.
- Comparaison ancrée (`level1_loop`, PC `3396`) : avec une banque de données fixe,
  0 écart sur `C200-DFFF` hors `DA00-DA2F`, `DA3E-DA45`, `DFD0-DFFF` pour les trames
  1-3 et 10 ; 42/34 octets d'écart aux trames 4-5 sur `CE2F-CE3C` (entités) selon la
  banque fixe choisie. Les tampons `C000-C1FF` (OAM/ombre) diffèrent : remplis par des
  routines de banque commutée stubbées.
- Le premier essai avec `CSimulator` ne lisait pas les écritures : le simulateur copie
  la mémoire ; corrigé en utilisant `sim.memory`.
- Les marqueurs en `3Fxx` ne fonctionnent pas (ROM protégée du CSimulator) ; marqueurs
  déplacés en SRAM `BFF0-BFF2`.
- Variables de comparaison exclues (affichage/entrées/pile), à justifier dans le
  contrôle complet : `DA09-DA0A` (file de défilement), `DA0F` (drapeau timer),
  `DA41` (répétition d'entrée), `DFD0-DFFF` (pile GB).

## Portage CPC — etat au point d'arret

- Logique niveau 1 traduite (banque 0 + routines banque 7) et comparee en
  simulateur : 0 ecart hors zones d'affichage/entrees/pile pour les trames
  stables ; ecarts residuels sur les tampons d'entites (CE2F-CE3C) dus aux
  banques commutees non encore cartographiees.
- Rendu CPC : decor 160x144 converti en mode 1, image 320x200 centree.
  Une disquette de demonstration `build/kirby-demo.dsk` affiche correctement
  la salle 1 (HUD, decor, ciel, porte) dans Caprice32 via `RUN"GAME`.
- Blocage : l'integration des sprites et de la logique GB dans le binaire CPC
  n'est pas terminee. Le dessin/effacement des rectangles de sprites produit
  une trainee incorrecte ; l'entree clavier et la boucle de jeu GB ne sont pas
  branchees dans cette disquette. Ce n'est donc PAS encore une version jouable.
- Pistes immediates : corriger le rendu sprite (atlas/decalage/restauration),
  charger les donnees hors HIMEM par blocs, puis brancher G_11C6 et
  read_input_native ; la logique est deja verifiee en simulateur.


## Corrections du rendu sprite (suite aux retours)

- **Bug critique** : `blit3` faisait `(screen & ~mask) | data` au lieu de
  `(screen & ~mask) | (data & mask)`. Les pixels transparents (data=ink 3)
  écrasaient le fond avec du blanc. Corrigé : data=0 pour les transparents,
  et `blit3` utilise `data & mask`.
- **`BG_DATA equ $8000`** pointait au milieu de `screen.bin` (qui commence à
  $6000). Corrigé : `bg.bin` (linéaire, 40 octets/ligne) est incluse à $0500.
- **`ldir`** copie de `(HL)` vers `(DE)` — le sens inverse de ce qu'on voulait.
  Remplacé par une boucle manuelle `ld a,(de); ld (hl),a; inc de; inc hl`.
- **Tuile 0x80** (tête de Kirby) absente de l'atlas : le générateur collectait
  les OAM après `pb.tick()`, mais la tuile disparaît après 1 tick. Corrigé :
  collecte OAM avant tout tick.
- **Ordre de dessin** : la tête était dessinée en premier et recouverte par le
  corps. Corrigé : corps gauche, corps droite, tête (en dernier).
- **Tramage** : les sprites utilisent un seuil simple (shade<2 → blanc) au lieu
  du tramage Bayer, pour un rendu plus net.
- Le sprite fait 16×16 pixels sur un écran 320×200 : il reste petit. Le fond
  tramé noir/blanc le rend peu visible. Amélioration possible : agrandissement
  2× ou contour noir.
