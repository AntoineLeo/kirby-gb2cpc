# Reprise — portage Kirby's Dream Land 2 (GB) vers Amstrad CPC 6128

## 1. État

- Préparation (`docs/journal.md`, `docs/frontiere.md`, `docs/memoire.md`), traces et
  états de reprise disponibles.
- Conception écrite (`docs/portage.md`) : mémoire, mode 1 160×144, cadence 6 pas/5 trames
  (2,1,1,1,1), contrôles flèches + Z (A) + X (B), Enter = Start, Shift = Select,
  manette 2 boutons, défilement 8 px/50 Hz par CRTC (à mesurer).
- Banc d'essai complet : banques 01/02/07/08/0B/0E/0F/1A/1E/1F traduites, fenêtre de
  banque (octets ROM + tramplins aux points de dispatch), `select_bank` par OUT échangé
  par l1_cmp, `far_dispatch` + far0_pairs (20 cibles banque 0), tour complet branché.
- Données ROM lues par pointeur : mécanisme de correction en place et convergent
  (blocs alignés sur l'adresse GB + patches d'octet haut ; tables $29C9, $2BF0,
  $30C7-$30FF, $3F56-$3FFF corrigées — voir docs/journal.md).
- Vérification : `check.ps1 rapide` (ou `$env:FRAMES="600"; python -X utf8 tools\l1_cmp.py`,
  trace level1_loop). État : 0 écart hors trames d'événement ; écarts résiduels sur les
  trames d'événement (chiffres courants et historique : `docs/journal.md`).

## 2. Commandes

- Contrôle : `powershell -ExecutionPolicy Bypass -File check.ps1 rapide|complet`
  (= `sh check.sh rapide|complet`) : extraction, listing, traduction multi-banques,
  assemblage du banc d'essai, comparaison 600 tours. Échoue tant que les événements
  divergent (volontaire).
- Comparaison seule : `$env:FRAMES="20"; python -X utf8 tools\l1_cmp.py`.
- Pas-à-pas d'une trame : `python -X utf8 tools\l1_step.py` (`FRAME=n`) : écritures,
  commandes de script, état final vs trace.
- Banques : `$env:GB2ZX_CONFIG=(Resolve-Path _cfg_l1.py); python -X utf8 tools\gb_banks.py`.

## 3. Prochaine action exacte

Fermer les écarts des trames d'événement (la logique de script d'entité) — 29 octets
en trame 4 lors du dernier relevé, à remesurer avec `tools\l1_step.py` :
1. `python tools\l1_step.py` avec `FRAME=4` : le journal des commandes montre que le
   harnais recharge les compteurs CE56-CE58 à 0x09 (la valeur du slot B=7) alors que le
   GB recharge 0A/01/01 par slot, et que la chaîne 2F4B avance le pointeur CE77-CE79
   de 3 octets de trop (le GB s'arrête au opcode FF de fin de script) ;
2. suivre la lecture d'argument du parseur G_2D34/G_2D3F (l'argument = octet de script
   transformé + champ [CEAA+B] + table WRAM $DExx) et la boucle des handlers
   (G_2F56 → G_2F69/G_2F86/G_2FB6/G_300D) ; vérifier chaque lecture de table ROM
   restante avec le traducteur (les bases `ld h/d/b,d8`) ;
3. après chaque correction : comparaison 20 tours (les écarts doivent baisser), puis
   600 tours quand les événements passent.
Si les scripts piétinent : comparer les flux de commandes GB vs harnais par
`tools/l1_step.py` (les commandes du harnais) contre les octets de script en fenêtre
(les commandes attendues) — l'écart de consommation désigne la commande fautive.

## 4. Pièges

- Les étiquettes internes de banque ne sont PAS des points de dispatch : les tramplins
  se posent aux entrées seules (win_entries.json), sinon les octets de script lus dans
  la fenêtre sont écrasés.
- Ne jamais mettre de code dans $A000-$B2FF (SRAM = structures d'entités écrites par le
  jeu), $8000-$9FFF (VRAM) ni la fenêtre $4000-$7FFF. Zones sûres : $E000-$FDFF et la
  place libre sous $3F00 ; les données ROM se servent à leur adresse d'origine quand la
  zone est libre (le cas $3F56-$3FFF).
- L'injection d'état doit couvrir toute la trace sauf les marqueurs BFF0-BFF5.
- `sim.trace(a, b, ...)` exécute toujours depuis `a` (non reprise) : le pas-à-pas
  réaligne PC à chaque appel, budget d'un tour ≈ 3000 instructions.
- Les hooks PyBoy modifient la ROM : la trace (l1_loop) fait foi pour la comparaison,
  pas un rejouage avec hooks (observé : états différents du hook au même point).
- Les blocs DATA_BLOCKS s'alignent sur l'adresse GB (defs) pour que les pointeurs
  calculés (`ld h,imm` + offset) tombent juste ; les patches d'octet haut pointent
  vers D_xxxx/256.
- Une seule commande de contrôle : `sh check.sh rapide|complet`, elle s'arrête à la
  première erreur ; le détail des comparaisons va dans /tmp/l1_cmp.log.
