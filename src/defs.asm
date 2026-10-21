; ===========================================================================
; defs.asm - carte memoire du CPC6128 (Kirby's Dream Land 2) et constantes
;
; La logique GB traduite travaille sur ses adresses d'origine : fenetre de
; banque $4000-$7FFF (page etendue montee par la config RAM), VRAM $8000,
; SRAM $A000, RAM GB $C000, OAM/I/O/HRAM $FE00-$FFFF. L'ecran mode 1 tient
; dans le trou d'echo $E000-$FDFF que la logique n'utilise pas.
; Voir docs/portage.md §2 (carte retenue).
; ===========================================================================

; --- Carte memoire -------------------------------------------------------------
;   $0000-$003F  vecteurs (IM 1 : saut en $0038), $0100-$01FF pile moteur
;   $0200-$3FFF  support + banque 0 traduite + banque 07 ; table de sauts du
;                script en $3F00-$3FFF (fixe : le jeu fait ld h,$3f)
;   $4000-$7FFF  fenetre de banque : page etendue par banque GB (configs RAM
;                4-6 en jeu, 7 pour la page moteur du rendu)
;   $8000-$9FFF  VRAM GB (ombre tuiles/carte)     $A000-$BFFF  SRAM GB
;   $C000-$DFFF  RAM GB                           $E000-$F6BF  ecran mode 1
;   $F6C0-$FDFF  banques 1E/0F/1F/1A + buffers moteur
;   $FE00-$FFFF  OAM / I/O / HRAM GB
LOAD_ADDR   equ $0200
SCREEN      equ $E000               ; 160x144 mode 1 = 5 760 octets
SCREEN_SIZE equ 5760
GB_VRAM     equ $8000
GB_SRAM     equ $A000
GB_WRAM     equ $C000
GB_OAM      equ $FE00
GB_HRAM     equ $FF80
WIN_BASE    equ $4000               ; fenetre de banque
BANK_CODE   equ $F6C0               ; b1e/b0f/b1f/b1a traduites + buffers

; --- Fenetre de banque : configs RAM CPC (OUT $7Fxx) ---------------------------
; Config 4-7 : $4000-$7FFF monte la page etendue C0-C3, $C000-$FFFF reste sur
; la RAM principale (donc la RAM GB en $C000 est toujours visible). La page 3
; (config 7) est reservee au moteur d'affichage (code + sprites decales).
BANK_CFG    equ 4                   ; config RAM de la premiere page de fenetre
BANK_PAGE0  equ 4                   ; banque GB 07 -> page C0 (config 4)
BANK_PAGE1  equ 5                   ; banque GB 0F -> page C1 (config 5)
BANK_PAGE2  equ 6                   ; banque GB 1E/1F -> page C2 (config 6)
PAGE_ENGINE equ 7                   ; page moteur (rendu)

; --- Joypad GB --------------------------------------------------------------
PAD_A       equ $01
PAD_B       equ $02
PAD_START   equ $08
PAD_R       equ $10
PAD_L       equ $20
PAD_U       equ $40
PAD_D       equ $80

; --- Sprites (places d'affichage ; detail dans le moteur de rendu) -----------
NSLOTS      equ 1
S_DEMO      equ 0

; --- Materiel du CPC -----------------------------------------------------------
GA          equ $7F             ; Gate Array : encres, mode, ROM (OUT ($7Fxx))
GA_MODE1    equ %10001101       ; mode 1, ROM basse et haute coupees
GA_MODE1_LROM equ %10001001     ; mode 1, ROM basse visible (police)
GA_MODE0    equ %10001100       ; mode 0 (16 couleurs), ROM coupees
