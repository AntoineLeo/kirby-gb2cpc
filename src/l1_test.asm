; ===========================================================================
; test.asm - banc d'essai logique, boucle de niveau 1 (Kirby's Dream Land 2)
;
; Memoire :
;   $0200-$3EFF  support, logique GB traduite (banque 0) puis banques
;   $3F00-$3F55  table de sauts du script GB (fixe : le jeu fait ld h,$3f)
;   $4000-$7FFF  fenetre de banque (image courante : octets ROM + tramplins)
;   $8000-$9FFF  VRAM GB (ombre, ecrite par le jeu)
;   $A000-$BFFF  SRAM GB (structures d'entites, ecrites par le jeu)
;   $BFF0-$BFF5  marqueurs de tour (nettoyes avant chaque tour)
;   $C000-$DFFF  RAM GB
;   $E000-$FDFF  logique des banques (suite) — region inutilisee du jeu
;   $FE00-$FFFF  OAM, I/O et HRAM GB
;
; select_bank place la fenetre : le banc d'essai echange l'image par OUT $FE
; (Python) ; le CPC mappera ou copiera la banque autrement. Les appels vers la
; fenetre $4000-$7FFF sont emis en adresses GB brutes et tombent sur les
; tramplins de l'image (jp BNN_xxxx). Les pointeurs de banque 0 envoyes a
; far_dispatch (patch de $0620) passent par far0_pairs.
; ===========================================================================

        DEVICE ZXSPECTRUM48
        org $0200

; ---------------------------------------------------------------------------
; Marqueurs de tour puis routine réelle du tour (saut : son ret revient à
; l'appelant). Nettoyes par l1_cmp avant chaque tour.
; ---------------------------------------------------------------------------
m1:     ld a,1
        ld ($BFF0),a
        jp G_0496
m2:     ld a,1
        ld ($BFF1),a
        jp G_086B
m3:     ld a,1
        ld ($BFF2),a
        jp G_04AE

; ---------------------------------------------------------------------------
; VBlank GB : un tour de logique (boucle d'entites 2BFD)
; ---------------------------------------------------------------------------
gb_vblank:
        ld a,1
        ld ($BFF3),a
        ld hl,$DA0E
        inc (hl)
        call G_2BFD
        xor a
        ld ($BFF3),a
        ret

; ---------------------------------------------------------------------------
; Changement de banque : FFA4 + fenetre $4000-$7FFF
; ---------------------------------------------------------------------------
select_bank:
        ld ($FFA4),a
        out ($FE),a                     ; le banc d'essai place l'image
        ret
select_bank_no_int:
        jp select_bank

; ---------------------------------------------------------------------------
; far_dispatch (patch de $0620) : hl = cible GB
;   >= $4000 : jp (hl) vers le tramplin de la fenetre (hl inchange)
;   <  $4000 : recherche dans far0_pairs, puis jp (hl) vers le code traduit
; ---------------------------------------------------------------------------
far_dispatch:
        ld a,h
        cp $40
        jr nc,.win
        push af
        push bc
        push de
        ld de,far0_pairs
        ld b,FAR0_COUNT
.l:     ld a,(de)
        cp l
        jr nz,.n
        inc de
        ld a,(de)
        cp h
        jr z,.hit
        dec de
.n:     inc de
        inc de
        inc de
        inc de
        djnz .l
        pop de
        pop bc
        pop af
        ld a,l
        ld ($C200),a                    ; cible banque 0 inconnue : la noter
        ld a,h
        ld ($C201),a
.j:     jr .j
.hit:   inc de
        ld a,(de)
        ld l,a
        inc de
        ld a,(de)
        ld h,a
        pop de
        pop bc
        pop af
        jp (hl)
.win:   push af
        ld a,l
        ld ($BFF4),a                    ; diagnostic : derniere cible fenetre
        ld a,h
        ld ($BFF5),a
        pop af
        jp (hl)

far0_pairs:
        dw $0DA4, G_0DA4
        dw $0DCE, G_0DCE
        dw $0DF3, G_0DF3
        dw $0DF6, G_0DF6
        dw $0DFF, G_0DFF
        dw $0F50, G_0F50
        dw $0F77, G_0F77
        dw $1067, G_1067
        dw $1080, G_1080
        dw $10E6, G_10E6
        dw $1166, G_1166
        dw $11BE, G_11BE
        dw $1286, G_1286
        dw $2A2B, G_2A2B
        dw $2B91, G_2B91
        dw $3576, G_3576
        dw $357F, G_357F
        dw $35A2, G_35A2
        dw $383C, G_383C
        dw $3A6B, G_3A6B
FAR0_COUNT equ ($-far0_pairs)/4

; ---------------------------------------------------------------------------
; Stubs de la logique (remplacements de code GB)
; ---------------------------------------------------------------------------
S_INPUT_RET:
S_RET:
G_RST00:
G_RST38:
        ret

; ---------------------------------------------------------------------------
; Logique GB traduite (banque 0) puis banques commutables : BNN_xxxx = entrees
; (tramplins de fenetre). Les cibles intra-banque restent des etiquettes.
; ---------------------------------------------------------------------------
        include "gb_logic.asm"
        include "gb_logic_b07.asm"
        include "gb_logic_b1e.asm"
        include "gb_logic_b0f.asm"
        include "gb_logic_b1f.asm"
        include "gb_logic_b1a.asm"
        ASSERT $ <= $3F00

; ---------------------------------------------------------------------------
; Table de sauts du script (fixe en $3F00, 43 commandes)
; ---------------------------------------------------------------------------
        org $3F00
jump_table:
        dw G_08FA, G_0920, G_0959, G_096C, G_0988, G_090A, G_0997, G_0A0C
        dw G_0A18, G_0A41, G_0A56, G_0A6F, G_0AB4, G_0AE3, G_0B1F, G_0937
        dw G_0940, G_09BA, G_09CE, G_09E2, G_09F7, G_0914, G_08F1, G_097C
        dw G_0A24, G_0928, G_094A, G_09A0, G_0A86, G_0AC4, G_0B3E, G_0AEF
        dw G_0B74, G_0B84, G_0955, G_0968, G_0B01, G_0B07, G_0B0D, G_0B13
        dw G_0B19, G_0A31, G_0A39

; ---------------------------------------------------------------------------
; Données ROM en $3F56-$3FFF : tables de pointeurs lues par la logique
; (deuxième niveau, indexées depuis $30CF) — servies à leur adresse d'origine.
; ---------------------------------------------------------------------------
        org $3F56
        incbin "re/ref/bank_00.bin",$3F56,170

; ---------------------------------------------------------------------------
; Banques restantes : la suite du code traduit, dans la region inutilisee
; ---------------------------------------------------------------------------
        org $E000
        include "gb_logic_b08.asm"
        include "gb_logic_b0b.asm"
        include "gb_logic_b0e.asm"
        include "gb_logic_b02.asm"
        include "gb_logic_b01.asm"
        ASSERT $ <= $FE00

        savebin "build/l1/test.bin", $0200, $3E00
        savebin "build/l1/banks2.bin", $E000, $1E00
