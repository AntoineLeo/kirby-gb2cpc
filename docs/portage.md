# Conception du portage — Kirby's Dream Land 2 → Amstrad CPC 6128

Document de décision. Rien ici n'est encore implémenté ; les chiffres marqués
« mesuré » viennent des traces de la préparation, les autres sont des estimations
à vérifier par la mesure (outil de profilage à écrire).

## 1. Périmètre

Le jeu complet fait 512 Ko (32 banques). La préparation couvre le démarrage,
l'écran de sélection de fichier et le niveau 1. Le portage est mené par
tranches verticales :

1. **Niveau 1 jouable** : logique traduite et vérifiée tour par tour, puis
   affichage, son, menu, chargement. C'est la première livraison.
2. **Extension** aux autres niveaux/scènes, par overlay de banques traduites
   depuis la disquette, sans changer l'architecture.

Le niveau 2 n'a pas d'état sauvegardé : il ne sera pas annoncé avant d'en avoir
un. La première tranche a mesuré que le niveau 1 n'utilise que 5 banques
(`00, 07, 0F, 1E, 1F`) et que les changements de banque sont tous commandés
depuis la banque 0 fixe ; les banques commutées sont des feuilles appelées
depuis la banque 0.

## 2. Mémoire (CPC 6128, 128 Ko) — carte retenue

Le CPC ne voit que 64 Ko à la fois ; les 64 Ko supplémentaires sont 4 pages
de 16 Ko commutables. La logique GB doit trouver ses données aux adresses
calculées : la fenêtre de banque ($4000-$7FFF, ~1600 littéraux + pointeurs
bruts) et la RAM GB (hauts d'octets littéraux $A0/$C4-$DE/$FF) restent donc à
leurs adresses GB d'origine. Les configurations RAM 4 à 7 du CPC montent une
page étendue en $4000-$7FFF en laissant $C000-$FFFF sur la RAM principale.

| Zone | Adresse CPC | Contenu |
|---|---|---|
| vecteurs, pile moteur | `$0000-$01FF` | IM 1, `jp isr` en `$0038`, pile |
| moteur + code traduit | `$0200-$3FFF` | support, banque 0 traduite, banques 07, table de sauts `$3F00-$3FFF` |
| page commutée | `$4000-$7FFF` | fenêtre de banque (page étendue par banque GB : 07, 0F, 1E, 1F) |
| VRAM GB | `$8000-$9FFF` | native — ombre tuiles/carte, lue par le moteur d'affichage |
| SRAM GB | `$A000-$BFFF` | native — structures d'entités |
| RAM GB | `$C000-$DFFF` | native — la comparaison tour par tour reste directe |
| écran | `$E000-$F6BF` | mode 1, 160×144 (5 760 o, R4=20, R6=18), base CRTC `$C000` + décalage |
| données moteur | `$F6C0-$FDFF` | banques 1E/0F/1F/1A traduites + buffers |
| OAM / I/O / HRAM | `$FE00-$FFFF` | natifs (`FE00`, `FF00-FFFF`) |

Pages étendues : 4 au total — trois pages de fenêtre (banques 07, 1E, et 0F/1F
combinées) et une page moteur (code d'affichage + images de sprites décalées)
montée en $4000-$7FFF pendant le rendu. Les banques hors niveau 1 (01, 02, 08,
0B, 0E, 1A : ~3,8 Ko, non sollicitées par le profil) seront des overlays
disquette dans la phase d'extension.

Conséquences :
- tout le GB est à ses adresses natives : pas de `RAM_MAP`, la comparaison
  tour par tour (`gb_cmp.py port`) injecte et relit aux adresses GB ;
- les accès de la logique à `$4000-$7FFF` tombent juste : la fenêtre monte la
  page étendue de la banque courante (commutation par OUT `$7Fxx`) ; les gros
  blobs graphiques sont convertis hors ligne et exclus de la fenêtre ;
- l'écran tient dans le trou d'écho `$E000-$FDFF` que la logique n'utilise pas
  (vérifié sur 600 tours) ;
- la taille du code traduit est mesurée après fermeture (`gb_closure.py`) :
  banque 0 = 10 047 o, b07 = 2 767 o, b1e/b0f/b1f/b1a = 1 429 o.

(Décision d'implémentation : la table d'origine de ce paragraphe plaçait
l'écran en $4000 et la fenêtre en $A300 ; la fenêtre ne peut pas bouger — ses
pointeurs sont calculés à l'exécution — et la RAM GB doit rester en $C000
pour la comparaison. La carte ci-dessus résout les deux contradictions.)

## 3. Affichage

Mesuré sur `level1_actions` (900 trames) :

- image GB 160×144, 4 teintes ; au plus **10 sprites** OAM, **3,5 en moyenne**,
  **7 au plus par ligne** ;
- ~2 octets OAM et ~2 octets de carte modifiés par trame ; jusqu'à 104 tuiles
  distinctes à l'écran ;
- défilement horizontal de 1 à 2 pixels par trame pendant la marche, vertical
  rare (0→20).

Choix proposé :

- **mode 1** (320×200, 4 encres), image GB à l'échelle 1 (160×144) centrée,
  bordure noire ; les 4 teintes GB deviennent les 4 encres sans perte ;
- **décor** : tuiles 8×8 converties hors ligne, carte de tuiles en RAM, rendu
  incrémental (seules les colonnes/rangées qui changent) ;
- **sprites logiciels XOR** pré-décalés, comme CPC Tennis ; seuls les sprites
  modifiés sont redessinés, dans l'ordre du faisceau ;
- **défilement** : budget d'une trame = **79 872 cycles** (4 MHz, 20 ms).
  - pas de 8 pixels par le CRTC (R12/R13, unité de 2 octets en mode 1) :
    quasi gratuit, 50 Hz ;
  - pas de 4 pixels par recopie logicielle des 5 760 octets visibles :
    ~46–69 k cycles par pas, soit 25–30 Hz ;
  - pas de 1 pixel : ~90–140 k cycles, soit ~15–20 Hz.

Décision à valider : **8 px à 50 Hz** (fluide mais saccadé), **4 px à 25–30 Hz**
(compromis), ou **1 px à 15–20 Hz** (fidèle mais saccadé). Le premier réglage
sera mesuré, puis ajusté sans toucher à la logique ; l'affichage peut sauter des
images, jamais la logique.

## 4. Cadence

Original : 60 Hz, une attente VBlank par pas de logique. CPC : 50 Hz.
Proposition : **6 pas de logique toutes les 5 trames** (motif 2,1,1,1,1),
rattrapage plafonné à 6, comme CPC Tennis. La vitesse du jeu reste celle du GB ;
le compteur `DA0E` avance d'un pas par pas de logique. Option de repli :
50 Hz ralenti de 17 %, à ne choisir que si la mesure montre que la logique ne
tient pas dans une trame.

## 5. Graphismes

Conversion hors ligne, réutilisable par un futur éditeur :

- rejouer les écritures VRAM de la ROM (`tools/gbgfx.py`) pour extraire tuiles,
  cartes et palettes ;
- convertir les tuiles en mode 1 (`tools/cpcgfx.py`) ;
- assembler les listes OAM et convertir les sprites en images pré-décalées ;
- vérifier chaque écran par comparaison chiffrée avec la capture GB, puis
  regarder la zone utile au palier (titre, HUD, premier décor).

## 6. Entrées

Manette GB : A, B, Select, Start, directions.
CPC : clavier **Q/A/O/P** + **ESPACE** (A) + **M** (B), plus joystick
(directions, tir 1 = A, tir 2 = B) ; Select/Start sur des touches à définir.
La routine CPC produira exactement `FFA5-FFAC` (même structure
courant/nouveau/relâché/répétition que `UpdatePadState` en `00:041E`), y compris
le verrou `DA38`.

## 7. Son

Écritures SN76489 (GB) → AY-3-8912, sans conserver d'état lu par la logique.
Les 144 accès son de la préparation seront classés par canal/effet ; musique et
bruitages sont deux tables distinctes. Le son ne bloque pas la logique : les
demandes sont mémorisées et jouées après l'affichage.

## 8. Chargement

Une disquette `.dsk` (format DATA), `RUN"GAME"`, binaire AMSDOS. Le chargeur
reste sous HIMEM, coupe les ROM, installe l'écran en `$4000`, charge la fenêtre
de banque et la logique. Les sauvegardes utilisent un fichier disque au format
de la RAM cartouche (8 Ko), pas de conversion.

## 9. Vérification

- **Rapide** (< 2 min) : assemblage + `gb_cmp.py port level1_court` (300 tours),
  mémoire GB identique tour par tour. Prérequis : activer `gb_cmp.py port`
  (actuellement une coquille) avec le simulateur Z80 64 Ko.
- **Complet** (paliers) : `boot`, `fileselect`, `level1`, `level1_actions`,
  comparaison tour par tour, coût mesuré de chaque partie du moteur en % du
  budget, captures Caprice32 et lancement réel.
- Le coût du moteur n'est remesuré que si l'affichage, le son ou la cadence
  changent.

## 10. Ordre de travail

1. Fermer la logique (`ROOTS`, `STUBS`, RST) et traduire le niveau 1.
2. Écrire le support Z80 (RST, banques, entrées) et `gb_tick`.
3. Activer la comparaison port, corriger jusqu'à 0 écart.
4. Moteur d'affichage : décor fixes, HUD, sprites, défilement mesuré.
5. Son, menu/sélection de fichier, chargement.
6. Palier : captures, coût, essai Caprice32, livraison de la tranche verticale.

## 11. Risques

- Le code traduit peut dépasser les 30 Ko de la tranche verticale : overlay dès
  l'étape 1.
- Le défilement 1 px est probablement hors budget à 50 Hz : concession à
  valider.
- La structure des objets/ennemis est encore une hypothèse ; la traduction
  automatique la couvre, mais le rendu des sprites devra être confronté aux OAM.
- Les banques de graphismes utilisent peut-être un format compressé non
  identifié ; à traiter par rejeu des routines de décompression, pas à l'œil.
