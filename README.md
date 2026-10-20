# Kirby's Dream Land 2 (Game Boy) → Amstrad CPC 6128

Portage de *Kirby's Dream Land 2* (Game Boy, SM83) vers l'Amstrad CPC 6128 (Z80) par
**traduction statique** : la logique du jeu est traduite routine par routine depuis la ROM
et vérifiée **tour par tour** contre l'original ; seul l'affichage, le son et les entrées
sont réécrits avec les moyens du CPC.

## Ce dépôt contient

- `tools/` — outils de préparation et de portage : extraction (`gb_extract.py`), listing
  réassemblable (`gb_listing.py`, mgbdis, RGBDS), traducteur SM83→Z80 (`gb2z80.py`),
  comparaison tour par tour (`l1_cmp.py`, `gb_cmp.py`, `l1_step.py`), frontière du portage
  (`gb_boundary.py`), carte code/données (`gb_codemap.py`), graphismes (`cpcgfx.py`),
  disquette (`make_dsk.py`) ;
- `src/` — moteur CPC (sjasmplus) : support Z80, fenêtre de banques, rendu ;
- `re/` — métadonnées de rétro-ingénierie : fichier de noms (`names.txt`), frontière
  (`boundary.json`), carte code/données (`codemap.json`), scénarios de test ;
- `docs/` — journal de préparation, frontière du portage, carte mémoire, conception,
  fichier de reprise ;
- `check.sh` / `check.ps1` — commande de contrôle unique (extraction, listing, traduction,
  comparaison 600 tours).

## Le jeu n'est pas distribué

La version publiée sur GitHub ne contient **aucune ROM ni donnée dérivée du jeu** :
pas de `re/game.gb`, `re/ref/`, `re/listing/`, `re/traces/`, `re/states/`. Pour rejouer la
chaîne complète, déposez votre propre copie légalement obtenue dans `re/game.gb` (attendue :
MD5 `ddb5bfae32b0ca39cf8ab6c46880126c`, *Kirby's Dream Land 2*, MBC1+RAM+BATTERY,
32 banques) et régénérez les artefacts avec `tools/gb_extract.py` puis `tools/gb_listing.py`.
Les outils fonctionnent sans modification ; seul le contenu du jeu vous revient.

## Prérequis

- Python 3.11+ (PyBoy, SkoolKit, Pillow, numpy) — `install.ps1` installe les paquets ;
- RGBDS (rgbasm/rgblink/rgbfix) — réassemblage du listing GB ;
- sjasmplus 1.24 — assembleur Z80 cible ;
- Caprice32 (fork ColinPitrat) — émulateur CPC 6128 ;
- Git for Windows (Git Bash pour les scripts `*.sh`).

## Contrôle

```powershell
powershell -ExecutionPolicy Bypass -File check.ps1 rapide   # < 2 min
powershell -ExecutionPolicy Bypass -File check.ps1 complet
```

État : préparation validée (extraction, listing réassemblé à l'identique, traces
reproductibles, frontière, carte mémoire) ; logique du niveau 1 traduite et comparée en
banc d'essai, écarts résiduels sur les trames d'événement (voir `docs/reprise.md`).
