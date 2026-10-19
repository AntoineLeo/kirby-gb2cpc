# Frontière du portage — Kirby's Dream Land 2 (Game Boy)

Source : `re/game.gb`, MD5 `ddb5bfae32b0ca39cf8ab6c46880126c`, 512 Ko, MBC1+RAM+BATTERY,
32 banques ROM, 8 Ko de RAM cartouche. Un seul processeur (SM83). Le conteneur est une
cartouche nue : pas de chargeur, pas de protection, pas de compression de conteneur.
Les images de référence et leurs MD5 sont dans `re/ref/manifest.json`.

Méthode : listing `re/listing` (mgbdis + `re/names.txt`, réassemblé à l'identique),
relevé automatique `re/boundary.json` (`tools/gb_boundary.py`), traces de quatre scénarios
(`boot`, `fileselect`, `level1`, `level1_actions`) et lecture du code appelant.
Une ligne « vérifié » n'est écrite qu'après lecture du code ou trace. Les hypothèses sont
marquées **[hypothèse]**.

## 1. Entrées / manette

| Adresse | Rôle | Effets hors affichage | Appelants |
|---|---|---|---|
| `00:0357` `ReadInput` | point d'entrée lecture manette 1 | met à jour `DA3E-DA41` | indirect (pointeur de fonction, non identifié) |
| `00:036E` `ReadPadRaw` | lit `$FF00`, anti-rebond | écrit `DA3E…` via `041E` | atteint par `0357` |
| `00:0387` `ReadPadState` | directions + boutons, anti-rebond | écrit `DA3E…` via `041E` | atteint par `0357` |
| `00:041E` `UpdatePadState` | structure courant/nouveau/relâché/répétition | écrit `HL`, `HL+1`, `HL+2`, `HL+3` | `03A8`, `03EC` |
| `00:03E5–0403` | recopie la structure vers la HRAM | `FFA5-FFAC` | dans `ReadPadRaw` |

Structure d'entrée (vérifiée) : 4 octets par manette, à `DA3E` (manette 1) et `DA42` (manette 2) :
`[courant] [nouveau] [relâché] [compteur de répétition]`. La copie de travail lue par la
logique est en HRAM : `FFA5-FFA8` manette 1, `FFA9-FFAC` manette 2.
`DA38` est un verrou d'entrée (non nul : lecture ignorée).

À porter : une routine CPC qui produit exactement `FFA5-FFAC` (mêmes bits et mêmes règles
de front/relâchement/répétition). Toute la logique du jeu lit ces octets.

## 2. Attente d'image, interruptions, cadence

| Adresse | Rôle | Effets | Appelants |
|---|---|---|---|
| `00:0040` vecteur VBlank | sauve AF/HL/BC/DE puis `JP 0159` | — | matériel |
| `00:0159` `VBlankMain` | met à jour l'écran, drapeau de trame | écrit `DA0C` bit 0, `DA0E`, files `C200/C300` | vecteur |
| `00:0048` vecteur STAT | `JP $DA13` (RAM écho) | — | matériel ; **[hypothèse]** vecteur non utilisé |
| `00:0050` vecteur Timer | sauve puis `JP 0333` | — | matériel |
| `00:0333` `TimerMain` | pose `DA0D=1` | `DA0D` | vecteur |
| `00:0058` vecteur série | `RETI` | — | matériel |
| `00:0060` vecteur joypad | `RETI` | — | matériel |
| `00:0343` `WaitVBlank` | attend `DA0C` bit 0 ; `HALT` | incrémente `DA0E` (compteur de trames) ; remet `DA0C=0` | `00:043D` |

Cadence : la boucle attend une trame VBlank, donc **60 Hz** sur Game Boy. `DA0E` est le
compteur de trames. À porter : une attente de trame CPC à 50 Hz, avec le même compteur
incrémenté une fois par tour. Le rapport 60/50 devra être décidé au portage (jeu ralenti
de 17 % ou compensation), ce choix revient à l'utilisateur.

## 3. Écran, décor, sprites, textes

Tout passe par le gestionnaire VBlank et par des files de commandes en RAM.

| Adresse | Rôle | Effets hors affichage | Appelants |
|---|---|---|---|
| `00:0159` `VBlankMain` | écrit `SCY/SCX` depuis `DA02`/`DA04` (ou `DA00`/`DA01`), palettes `CD00-CD02` vers `FF47-FF49` | consomme les files `C200`/`C300`, flags `DA27`, compteurs `DA23/DA24`, sauve/restaure SP (`DA25`, `DA18`) | vecteur VBlank |
| `00:0193–0207` | recopie des files d'écriture VRAM | piles temporaires `C200`, `C300`, `DA23`, `DA24`, `DA25`, `DA18` | dans `VBlankMain` |
| `00:0210–022A` | fin de VBlank, `LYC=0`, retour | `DA14-DA18` | dans `VBlankMain` |
| `00:04C0` `04D8` | empile des écritures VRAM (adresse, octet) dans les files | `C200…`, `C300…`, `DA23/DA24/DA27` | routines d'affichage |
| `re/boundary.json` | 627 accès VRAM, 62 accès OAM, 22 accès LCD | — | détail par instruction |

Files d'affichage (vérifiées) : `C200` et `C300` contiennent des couples
`(adresse VRAM 16 bits, octet)`, dépilés par `VBlankMain` ; `DA23`/`DA24` comptent les
entrées de chaque file, `DA27` choisit les files à vider. Le jeu ne relit pas la VRAM
pour la logique dans les scènes observées : l'écran peut être remplacé par un rendu natif,
mais **les files et leurs compteurs doivent être conservés** (la logique les remplit et
les routines VBlank les vident).

Graphismes : la décompression/le pré-découpage se fait dans les banques ROM (accès VRAM
en masse relevés dans `re/boundary.json`, catégories `vram` et `lcd`), pas dans une zone
de travail identifiée. À traiter au portage en convertissant les données une fois pour
toutes ; la logique de décompression n'a pas d'effet RAM hors files ci-dessus.

## 4. Son

144 accès aux registres `FF10-FF3F` (catégorie `sound` de `re/boundary.json`), répartis
dans 117 routines ; aucun tampon son identifiable en RAM. La logique de jeu ne lit pas
les registres son. À porter : traduction des écritures SN76489 (Game Boy) vers AY-3-8912
(CPC), sans conserver d'état autre que les variables de musique du jeu (non identifiées,
coût faible : elles ne sont lues que par le code son).

## 5. Banques, chargements, RAM cartouche

| Adresse | Rôle | Effets | Appelants |
|---|---|---|---|
| `00:05DD` `SetBank` | `DI` ; `LD [$2100],A` ; `FFA4=A` ; `EI` | `FFA4` = banque courante | nombreux appels banque 0 (`028F`, `0296`, `0447`, `044F`, `0475`, `047F`, `05C6`, `05D6`, `0832`, `083F`, `08C7`, `08E1`, `09B2`, `0A9D`, `0DD6`, `0DEA`, `0F2E`, `10E0`, `1128`, `1136`, `1144`…) |
| `00:05F3` `SetBankNoInt` | même chose sans `DI/EI` | `FFA4` | `028F`, `0296`, `06FB`, `0703`… |
| `00:05CF` `CallBank` | sélectionne une banque, appelle un pointeur HL, restaure `FFA4` | `FFA4`, pile | `0418`, `0447`, `044F`, `0475`, `047F`, `0C43`, `10A2`, `10AF`, `10BF`… |
| `00:060D` | variante avec restauration de banque | `FFA4` | banque 0 |

`FFA4` est la banque ROM courante (vérifié). Le portage n'a pas de banques : les appels
`SetBank`/`CallBank` deviennent des appels directs vers le code traduit, mais `FFA4`
doit rester à jour car la logique le lit (ex. `028A`, `082C`, `3D78`).

RAM cartouche `A000-BFFF` : 8 Ko, sauvegarde sur pile, accédée par 297 instructions
(catégorie `sram`) ; elle contient les fichiers de sauvegarde (écran SELECT FILE).
À conserver telle quelle dans le portage (fichier disque), même format que l'original.

## 6. Mémoire jamais lue — espace récupérable

Vérifié en simulation : les plages suivantes restent à zéro dans les quatre scénarios
(`boot`, `fileselect`, `level1`, `level1_actions`) et ne sont jamais visées par une adresse
absolue du listing. **[hypothèse]** elles sont libres pour le portage ; un accès par
pointeur calculé n'est pas exclu, donc à re-vérifier après chaque nouveau niveau.

```
C028-C0FF (216)   C128-C1FF (216)   C290-C2FF (112)   C34E-C3FF (178)
C918-C947 (48)    C960-C9FF (160)   CA05-CAFF (251)   CB05-CBFF (251)
CC05-CCFF (251)   CD0C-CD2C (33)    CD41-CD53 (19)    CD56-CE00 (171)
CED3-CEFF (45)    D314-D343 (48)    D35C-D70F (948)   DA4B-DB35 (235)
DB8A-DCFC (371)   DCFF-DD2C (46)    DD2E-DD90 (99)    DEED-DEFF (19)
DF16-DF32 (29)
```

Total : environ 3,9 Ko. Les plus gros blocs (`D35C-D70F`, `DB8A-DCFC`) sont les meilleurs
candidats. Les plages `C200` et `C300` ne sont **pas** libres (files d'affichage), ni
`DA00-DA2D`, `DA3E-DA45`, `FFA4-FFAC`, ni la pile.

## 7. Ce qui reste incertain

- Appelants indirects de `ReadInput` (`0357`) : le pointeur est chargé dans une table,
  pas par un `CALL` absolu. Le portage n'en a pas besoin s'il remplace la source d'entrée.
- Vecteur STAT (`0048`) pointe vers `DA13` (RAM écho) : jamais exécuté dans les traces.
  Laisser le vecteur inactif côté CPC.
- Rôle exact de `DA02`/`DA04` vs `DA00`/`DA01` (trois paires de scroll) : `VBlankMain`
  utilise `DA02`/`DA04` selon un drapeau ; les trois paires sont égales dans les scènes
  observées. Les conserver toutes.
- Zone de travail des graphismes décompressés : non identifiée séparément ; les accès
  VRAM sont dans `re/boundary.json`.
- Table des objets/ennemis : structure non tranchée (voir `docs/memoire.md`).
- Niveau 2 : pas de sauvegarde d'état obtenue (voir `docs/journal.md`).
