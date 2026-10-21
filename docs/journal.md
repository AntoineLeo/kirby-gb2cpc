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


## Portage — fenêtre de banques et tour complet (étape du fichier de reprise)

### Décisions validées (utilisateur)
- Cadence : 6 pas de logique / 5 trames CPC (motif 2,1,1,1,1).
- Contrôles : flèches + Z (A) + X (B), Enter = Start, Shift = Select ; manette 2 boutons (1=A, 2=B).
- Défilement : 8 px à 50 Hz par le CRTC (R12/R13), réglage à mesurer puis ajuster.

### Outils ajoutés
- tools/gb_banks.py : entrées de banque (statique + dynamique PyBoy), fermeture par
  banque, lectures de données. Selftest inclus. C'est lui qui a montré que les motifs
  ld a,N ; call SetBank ne suffisent pas : les appels de banque passent aussi par
  CallBank (05CF, hl=constante) et par les pointeurs de callbacks (0887→0620).
- build/l1/win_entries.json (produit par gb2z80) : les points de dispatch de fenêtre,
  seuls lieux où poser les tramplins.

### Mécanisme de banque retenu (banc d'essai)
- La fenêtre $4000-$7FFF montre la banque courante : octets ROM bruts + tramplins
  jp BNN_xxxx aux seuls points de dispatch (les étiquettes internes n'en reçoivent
  pas : les poser partout écrasait les octets de script lus dans la fenêtre — corrigé).
- select_bank = ld ($FFA4),a ; out ($FE),a ; l1_cmp échange l'image par le traceur.
- far_dispatch (patch de $0620) : hl≥$4000 → jp (hl) (tramplin, hl inchangé) ;
  hl<$4000 → table far0_pairs (20 cibles mesurées) puis saut. Une cible inconnue
  écrit son adresse en C200 et boucle : signalée tout de suite par la comparaison.
- Banques traduites : 01, 02, 07, 08, 0B, 0E, 0F, 1A, 1E, 1F (BANK_ENTRIES dans
  _cfg_l1.py, mesurées par gb_banks sur level1 + level1_actions).

### Vérification (trace level1_loop, 600 tours)
- Trames sans événement d'entité : **0 octet d'écart** (mesuré : trames 1-3, 10-12…),
  le tour complet tournant (m1/m2/m3 appellent G_0496/G_086B/G_04AE, plus des stubs).
- Trames d'événement (4-5, 13-14) et leurs suites (6-9, 15-18) : écarts, 12 trames
  sur les 20 premières.

### Cause racine des écarts d'événement (identifiée, pas encore résolue)
Le banc d'essai réutilise les adresses ROM ($0000-$3FFF) pour le code traduit : les
**données ROM lues par pointeur calculé** sont servies avec les octets du code traduit.
Trois lectures fautives prouvées pas-à-pas (outil de pas-à-pas par sim.trace(pc,0,1,0)) :
- la table d'événements $29C9 (8 entrées de 12 octets, lue via BC) — relocalisée en
  DATA_PTRS/DATA_BLOCKS, l'écart a bougé (preuve de la cause) ;
- la table d'animation $30D1 (15 octets, lue via ld h,d8 + offset calculé) — bloc
  aligné sur son adresse GB + patch ld h,D_30D1/256 en 2C88, l'écart a encore bougé ;
- d'autres tables du même type restent : le traducteur signale maintenant chaque
  ld h/d/b,d8 avec d8 < $4000 (« base de pointeur vers la ROM »), liste à classer.

### Pistes abandonnées / pièges corrigés
- Tramplins sur toutes les étiquettes : écrasait les scripts lus dans la fenêtre
  (les étiquettes internes ne sont pas des points de dispatch).
- Code des banques en $A000 : la SRAM GB ($A000-$B2FF) porte les structures d'entités
  écrites par le jeu — le code était écrasé (dérive folle à l’exécution). Zone sûre : $E000-$FDFF (inutilisée par le jeu) + la zone libre sous $3F00.
- Injection d'état sautant $A000-$BFFF : les structures d'entités en SRAM n'étaient
  pas réinjectées (dispatch vers le pointeur nul). Seuls les marqueurs BFF0-BFF5 sont
  épargnés maintenant.
- sim.trace(start, stop, ...) : exécute toujours depuis start (non reprise) ; le
  pas-à-pas se fait en réalignant PC à chaque appel, budget d'un tour ~1400 instructions.
- Double appel sim.trace dans la boucle de comparaison : les compteurs décalaient de 1.
- ld hl,sp+0 (banque 1E) traduit en hl=sp, drapeaux GB non conservés (morts ici).


## Portage — classification des donnees ROM (suite de la fenêtre de banques)

### Mecanisme de correction (convergent, prouve par pas-à-pas)
Le banc d'essai reutilise les adresses ROM pour le code traduit : chaque donnee ROM
lue par pointeur est servie par un bloc aligné sur son adresse GB (defs + contenu brut)
et, si le pointeur est calcule, un patch de l'octet haut (ld h,D_xxxx/256).
Outillage : tools/l1_step.py (pas-à-pas via sim.trace(pc,0,1,0) + guet d'ecritures),
tools/gb_banks.py (entrees de banque), le traducteur signale les bases de pointeur
(ld h/d/b,d8 avec d8 < $4000).

### Corrections faites (chaque fois un recul mesure des ecarts)
- $29C9 : table d'evenements (8 x 12 octets, lue via BC) — bloc DATA_PTRS.
- $2BF0 : table 13 octets, pointeur calcule — bloc + patch 2BD8.
- $30C7-$30FF : tables d'animation (3 lectures : 2C88, 2D1C, 2EF5) — bloc unique
  aligne + patches.
- $3F56-$3FFF : tables de pointeurs deuxieme niveau (valeurs 074E/07C4 lues via
  hl calcule) — servies a leur adresse d'origine (zone libre du banc, incbin).
- Tramplins de fenetre limites aux vrais points de dispatch (win_entries.json) :
  les poser partout ecrasait les octets de script lus dans la fenetre.
- Code des banques deplace hors de la SRAM GB ($A000-$B2FF ecrite par le jeu).

### Etat de la comparaison (trace level1_loop)
- Trames sans evenement : **0 octet d'ecart** (1-3, 10-12...).
- Trames 4-5 / 13-14 (evenements d'entite) + suites : 29 octets d'ecart en trame 4
  (etape amelioree : 44 -> 29). Les ecarts restants : compteurs CE82+B (valeur de
  recharge 05/04), pointeurs de script CE77-CE79 (+3 octets de derive sur la chaine
  2F4B), compteurs CE56-CE58 (recharges 09 au lieu de 0A/01/01).

### Piste en cours (precise)
Les arguments de recharge des scripts d'entite : le parseur G_2D34/G_2D3F lit
l'argument via (de) + le champ [CEAA+B] + la table WRAM $DExx. Le harnais recharge
tous les compteurs a 0x09 (la valeur du slot B=7) alors que le GB recharge
(0A,01,01,09) par slot. A verifier : la lecture de l'argument par slot et
l'avance du pointeur de la chaine 2F4B (le GB s'arrete au opcode FF de fin de
script, le harnais continue de 3 octets).

### Reperes de debug (outils)
- python tools/l1_step.py avec FRAME=4 : pas-à-pas, ecritures C200-CFFF + FF80-FFFF,
  journal des commandes de script (entrees 2C64/2C65/2F56), etat final vs trace.
- gb_anchor_only.py / gb_slots.py (temp) : etat GB aux entrees de routine —
  attention, les hooks PyBoy modifient la ROM : comparer avec la trace (l1_loop)
  qui fait foi, pas avec un rejoue piege.


## Phase 2 — cause racine des ecarts de trames d'evenement (2026-10-21)

### Cause racine : capture de trace decalee (artefact de mesure, pas de logique)
Les "ecarts des trames d'evenement" (compteurs CE56-CE58 "recharges a 09",
pointeurs CE77-CE79 "+3 octets") etaient des ARTEFACTS. `gb_record_at.py`
capturait memoire et registres via un generateur paresseux, evalue a la fin du
tick PyBoy et non au PC d'ancrage : les snapshots tombaient en plein milieu du
traitement d'entite. Preuve : les PC de capture de l'ancienne trace (2F4B,
2CF3, 2FBF, 2C5F, 2F3E, 2C04...) au lieu de 3396 ; l'etat "en vol" de la
trame 4 (slot 7 traite, 6/5/4 pas encore) explique exactement les valeurs
0A/01/01/09 lues et le +3 du pointeur (stocke une trame plus tard).
Correction : capture immediate dans le hook (memoire + registres), trace
level1_loop re-enregistree (600 trames, tous les PC = 3396). Trame 4 :
29 octets d'ecart -> 0.

### Vrai ecart : table ROM $3098 non servie
Restait CE12/CE3A (2 octets, trames 5/8/14/17). CE12 n'est qu'une copie de
CE3A (bloc source $CE38+2 de la copie d'entites B1E_43xx) ; CE3A etait ecrit
par G_3085 (ld [hl],e ; $3095) avec la table ROM $3098-$309B (00 60 40 20),
index e>>2. Le banc servait $29C9, $2BF0, $30C7-$30FF mais pas $3098 :
la lecture tombait sur les octets d'instruction deplaces (21 E3 = ld hl,$DEE3
assemble en $3098) — les valeurs E3/21 ecrites sont exactement ces octets.
Correction : DATA_PTRS += 0x3098, DATA_BLOCKS += (0x3098, 0x309C, 'db') ;
le traducteur emet desormais `ld hl,D_3098` + le bloc aligne. 0 ecart sur 19.

### Methode retenue pour la suite
- L'outil de comparaison donne seul le diagnostic ; un ecart peut venir de
  l'outil lui-meme — verifier d'abord la coherence de la mesure (PC de capture,
  phase de snapshot) avant de suspecter la logique.
- Les lectures de donnees ROM doivent passer par DATA_PTRS/DATA_BLOCKS (le
  traducteur symbolise les d16 connus) ; un oubli se detecte aux valeurs
  ecrites = octets d'instruction. Balayage des litteraux bruts fait (cf.
  ATTENTION du traducteur) : la plupart sont compteurs ou paires x/y ; le
  reste se detecte scenario par scenario par l1_cmp.


### Suite : plafond T-states de sim.trace (deuxieme artefact, meme famille)
La comparaison 600 tours s'arretait des la trame 153 (PC 0D57, puis 0200) :
le 4e argument de `sim.trace` est un plafond ABSOLU du registre T (temps
cumule), et T s'accumule d'une trame a l'autre dans le simulateur. Vers
2 000 000 T-states (trame 153), chaque appel suivant s'arrete immediatement.
Correction : `regs[25] = 0` (T) avant chaque trame dans tools/l1_cmp.py, comme
`regs[26] = 0` (IFF). Principe general : un outil de comparaison trame par
trame doit remettre a zero TOUT etat interne du simulateur qui n'est pas dans
la memoire injectee (T, IFF, HALT...), sinon les arrets ressemblent a des
ecarts de logique.
