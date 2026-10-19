# Reprise — portage Kirby's Dream Land 2 (GB) vers Amstrad CPC 6128

## 1. État

- Préparation complète (voir `docs/preparation.md`), extraction, listing réassemblable,
  scénarios et traces (level1, level1_loop, level1_actions), états de reprise.
- Conception écrite dans `docs/portage.md` (mémoire, mode 1 160×144, cadence, défilement).
  Décisions utilisateur validées : cadence 6 pas / 5 trames (2,1,1,1,1) ; contrôles
  flèches + Z (A) + X (B), Enter = Start, Shift = Select, manette 2 boutons ;
  défilement 8 px à 50 Hz par le CRTC (réglage à mesurer).
- Fenêtre de banques opérationnelle dans le banc d'essai : banques 01/02/07/08/0B/0E/
  0F/1A/1E/1F traduites (`BANK_ENTRIES`), images de fenêtre = octets ROM + tramplins
  aux points de dispatch (`build/l1/win_entries.json`), `select_bank` = `out ($FE),a`
  échangé par l1_cmp, `far_dispatch` (patch $0620) avec table far0_pairs pour la banque 0.
- Tour complet branché (m1/m2/m3 appellent G_0496/G_086B/G_04AE).
- Vérification `l1_cmp` sur level1_loop : **0 octet d'écart sur les trames sans
  événement d'entité** ; les trames d'événement (4-5, 13-14) et leurs suites divergent
  encore (12 trames sur les 20 premières).
- Cause racine des écarts restants identifiée : les données ROM lues par pointeur
  calculé sont servies par le code traduit dans le banc d'essai. Mécanisme de
  correction en place (blocs DATA_BLOCKS alignés sur l'adresse GB + patch de l'octet
  haut) ; il reste à classer les tables signalées par le traducteur.

## 2. Commandes

- Contrôle : `sh check.sh rapide` / `sh check.sh complet` (via `powershell -ExecutionPolicy Bypass -File check.ps1 rapide|complet`).
  Enchaîne extraction, listing, traduction multi-banques (gb2z80), assemblage du banc
  d'essai, comparaison 600 tours de niveau 1 (`tools/l1_cmp.py`, FRAMES=600).
  NB : la comparaison échoue tant que les trames d'événement divergent (voulumétrie).
- Comparaison seule : `$env:FRAMES="20"; python -X utf8 tools\l1_cmp.py` (résumé par
  trame + 8 premiers écarts).
- Analyse des banques : `$env:GB2ZX_CONFIG=(Resolve-Path _cfg_l1.py); python -X utf8 tools\gb_banks.py --out build\banks_l1.json [--dynamic re\scenarios\level1.json]`.
- Pas-à-pas d'une trame : `python -X utf8 C:\Users\Aie\AppData\Local\Temp\kilo\l1_step.py`
  (à rapatrier dans tools/ si besoin) avec `FRAME=n`, guette les écritures CExx.

## 3. Prochaine action exacte

Classer les bases de pointeur ROM signalées par le traducteur (« base de pointeur vers
la ROM ») et fermer les écarts d'événement :
1. Lancer la traduction et relever la liste `ld h/d/b,d8` (d8 < $40) ;
2. pour chaque site, regarder la routine (listing re/listing) : constante pure (ignorer),
   table de données ROM → ajout DATA_PTRS/DATA_BLOCKS (+ patch de l'octet haut si le
   pointeur est calculé, comme 2C88 → `ld h,D_30D1/256`) ;
3. viser d'abord les tables des banques 1E ($06xx via de) et 1A, qui alimentent la file
   sonore écrite par l'événement (miroir CE06-CE14) ;
4. après chaque ajout : comparaison 20 tours — les écarts doivent se réduire ; quand
   les événements passent, relancer 600 tours.
En parallèle, si la classification stagne : variante structurelle « image ROM aux
adresses GB » (tous les accès deviennent justes d'un coup), mais 6 Ko de code à trouver
hors $0000-$3FFF (zones sûres mesurées : $B300-$BFEF + $E000-$FDFF + $3F56 ≈ 11 Ko
pour 18 Ko de code).

## 4. Pièges

- Les étiquettes internes de banque ne sont PAS des points de dispatch : ne poser des
  tramplins qu'aux entrées (win_entries.json), sinon les octets de script lus dans la
  fenêtre sont écrasés.
- Ne jamais mettre de code dans $A000-$B2FF (SRAM = structures d'entités écrites par le
  jeu) ni dans $8000-$9FFF (VRAM écrite par les uploads) ni dans la fenêtre $4000-$7FFF.
  Zone sûre : $E000-$FDFF (écho inutilisé) + la place libre sous $3F00.
- L'injection d'état de l1_cmp doit couvrir toute la trace sauf les marqueurs BFF0-BFF5 ;
  sauter $A000-$C000 laissait les structures d'entités à zéro (dispatch vers le pointeur nul).
- `sim.trace(a, b, ...)` exécute toujours depuis `a` ; le budget de T-states sert de
  garde-fou, une dérive folle se voit au PC final ≠ ancre et à la pile non déséquilibrée.
- Les hooks PyBoy modifient la ROM : ne les poser que sur des entrées réellement exécutées
  (re/coverage_safe.json).
- La mémoire 0000-3FFF du CSimulator accepte les écritures : protéger ce qu'on y met.
- Une seule commande de contrôle : `sh check.sh rapide|complet` ; elle s'arrête à la
  première erreur. Le détail des comparaisons va dans /tmp/l1_cmp.log.
