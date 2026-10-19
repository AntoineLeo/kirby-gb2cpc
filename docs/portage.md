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

## 2. Mémoire (CPC 6128, 128 Ko)

Le CPC ne peut voir que 64 Ko à la fois ; les 64 Ko supplémentaires sont une
page de 16 Ko commutable en `$C000-$FFFF` (4 pages).

| Zone | Adresse | Contenu |
|---|---|---|
| vecteurs, pile moteur | `$0000-$01FF` | IM 1, `jp isr` en `$0038`, pile |
| moteur + banque 0 traduite | `$0200-$3FFF` | code Z80, table de sauts de script |
| écran | `$4000-$56BF` | mode 1, 160×144 (5 760 octets, R4=20, R6=18) |
| libre / données de niveau | `$56C0-$7FFF` | marge, données compactées |
| RAM GB native | `$8000-$9FFF` | `C000-DFFF` (8 Ko) |
| HRAM / OAM / I/O ombrés | `$A000-$A2FF` | `FE00`, `FF00-FFFF` |
| fenêtre de données de banque | `$A300-$BFFF` | banque courante compactée (7 Ko) |
| page commutée | `$C000-$FFFF` | code de la banque courante (4 pages de 16 Ko) |
| RAM cartouche | disquette | sauvegardes, même format que l'original |

Conséquences :
- la RAM GB garde ses adresses `$C000-$DFFF` : la comparaison tour par tour reste
  directe ;
- l'écran compact de 5 760 octets laisse la place à une fenêtre de données de
  7 Ko et à une page de code de 16 Ko ; le niveau 1 tient dans 4 pages pour ses
  4 banques commutées (`07, 0F, 1E, 1F`) ;
- les accès de la logique à `$4000-$7FFF` passent par la fenêtre de données ;
  les gros blobs graphiques sont convertis hors ligne et exclus de la fenêtre ;
- au-delà de 4 banques par scène, les modules sont chargés depuis la disquette
  dans une page (overlay), sans changer le code traduit ;
- la taille exacte du code traduit est mesurée après fermeture
  (`gb_closure.py`) : 7 162 octets de code GB pour le niveau 1, ~15 Ko Z80.

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
