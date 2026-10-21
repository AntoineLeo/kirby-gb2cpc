# Reprise — portage Kirby's Dream Land 2 (GB) vers Amstrad CPC 6128

## 1. Etat

- Preparation complete (docs/journal.md, docs/frontiere.md, docs/memoire.md).
- **Support Z80 CPC ecrit et verifie** (portage.md §10 etapes 2-3) : carte
  memoire retenue (portage.md §2), select_bank par config RAM, far_dispatch,
  gb_tick, entrees natives. **`gb_cmp.py port level1_loop` : 0 ecart sur 600
  tours** — la logique tourne dans le binaire CPC, identique au GB.
- **Logique niveau 1 prouvee identique** : `check.ps1 rapide` vert, et
  **0 trames differentes sur 599** (trace level1_loop, 600 tours, entrees
  scriptees) — la logique traduite calcule exactement comme le GB.
- Deux bugs d'outil de mesure corriges (c'etait eux, pas la logique) :
  capture de trace decalee (`gb_record_at.py`, generateur paresseux) et
  plafond T-states cumulatif (`l1_cmp.py`) ; une donnee ROM non servie
  (table $3098, valeur ecrite = octets d'instruction). Detail : docs/journal.md.
- Banc d'essai : banques 01/02/07/08/0B/0E/0F/1A/1E/1F traduites, trampolins
  aux seules entrees (win_entries.json), select_bank par OUT, far_dispatch +
  far0_pairs, tables ROM servies ($29C9, $2BF0, $3098, $30C7-$30FF, $3F56-$3FFF).
  Source versionne : src/l1_test.asm (copie dans build/l1/ a la construction).
- CPC : disquette de demo (salle 1) affichee dans Caprice32 ; integration de la
  logique et des sprites non terminee (journal : trainees sprites, donnees a
  charger hors HIMEM, G_11C6 et read_input_native a brancher).
- Conception validee dans docs/portage.md (memoire 128K, mode 1 160x144,
  cadence 6 pas/5 trames motif 2,1,1,1,1, controles).

## 2. Commandes

- Controle : `powershell -ExecutionPolicy Bypass -File check.ps1 rapide|complet`
  (= `sh check.sh rapide|complet`) : extraction, listing, traduction, banc,
  comparaison (trames 1-59 ; complet ajoute 600 tours + scenarios + frontiere).
- Comparaison seule : `Set-Item Env:FRAMES 600; python -X utf8 tools\l1_cmp.py`.
- Pas-a-pas d'une trame : `python -X utf8 tools\l1_step.py` (`FRAME=n`) :
  commandes de script (G_2C65/G_2F56), arguments (G_2D34/G_2D56), ecritures,
  etat final vs trace.
- Banques : `$env:GB2ZX_CONFIG=(Resolve-Path _cfg_l1.py); python -X utf8 tools\gb_banks.py`.

## 3. Prochaine action exacte

Etape 4 de docs/portage.md §10 — moteur d'affichage :
1. images de fenetre par banque (donnees + tramplins) placees dans les pages
   etendues, chargees depuis la disquette (palier chargement : loader AMSDOS) ;
2. decor (tuiles converties hors ligne, rendu incrémental), HUD, sprites
   logiciels (reprendre atlas/decalage/restauration du rendu sprite), cale sur
   le VSYNC lu au PPI ;
3. verification Caprice32 (capture `tools/cpcshot.sh`, une fenetre a la fois),
   puis son AY, menu/selection de fichier (etapes 5-6).

## 4. Pieges

- Un ecart de comparaison peut venir de l'outil : verifier d'abord la
  coherence de la mesure (PC de capture = ancrage dans meta['pc'] ; registres
  internes T/IFF/HALT du simulateur remis a zero entre les trames).
- `sim.trace(a,b,c,d)` : `d` est un plafond ABSOLU du registre T cumulatif,
  pas un budget par appel ; `c` = nombre max d'instructions.
- Toute donnee ROM lue par pointeur doit etre declaree dans DATA_PTRS /
  DATA_BLOCKS (_cfg_l1.py) ; un oubli se voit aux valeurs ecrites = octets
  d'instruction deplaces (cas $3098).
- Les etiquettes internes de banque ne sont PAS des points de dispatch : les
  tramplins se posent aux entrees seules (win_entries.json).
- Jamais de code dans $A000-$B2FF (SRAM), $8000-$9FFF (VRAM) ni la fenetre ;
  zones sures $E000-$FDFF et sous $3F00.
- Les hooks PyBoy modifient la ROM : la trace fait foi pour la comparaison.
- Une seule commande de controle : `sh check.sh rapide|complet`.
