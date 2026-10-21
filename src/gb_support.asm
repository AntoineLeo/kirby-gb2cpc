; ===========================================================================
; gb_support.asm - ce que la logique GB traduite attend autour d'elle
;
; Support Z80 du portage (docs/portage.md §10 etape 2) : commutation de
; banque par la config RAM du CPC, dispatch lointain, un pas de logique
; (gb_tick), entrees natives.
;
; La fenetre de banque ($4000-$7FFF) monte une page etendue par banque GB ;
; la config RAM 4-7 laisse $C000-$FFFF sur la RAM principale : la RAM GB en
; $C000 reste visible en permanence.
; ===========================================================================

; --- Commutation de banque (remplace SetBank $05DD/$05F3) ----------------------
; A = numero de banque GB. Ecrit FFA4 (la banque courante, lue par la logique)
; et monte la page etendue correspondante en $4000-$7FFF. Registres preserves.
select_bank:
select_bank_no_int:
        push af
        push hl
        push bc
        ld ($FFA4),a
        ld hl,banke_cfg
        add a,l
        ld l,a
        jr nc,.nc
        inc h
.nc:    ld a,(hl)
        ld b,GA
        ld c,a
        out (c),c               ; config RAM (bit 7 a 0)
        pop bc
        pop hl
        pop af
        ret

; --- Dispatch lointain (remplace $0620) ---------------------------------------
; HL = cible GB : >= $4000 -> la fenetre (tramplins de banque) ; sinon une
; cible de la banque 0, resolue par far0_pairs (paires adresse GB, etiquette).
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
.j:     jr .j                   ; cible banque 0 inconnue : diagnostic
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
.win:   jp (hl)                 ; tramplin pose sur l'entree de fenetre

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

; --- Un pas de logique (docs/portage.md §4 : 6 pas / 5 trames) ----------------
; Le corps de la boucle de jeu GB ($3396) : une iteration = une trame GB.
gb_tick:
        call G_0496
        call G_086B
        ld a,$07
        call select_bank
        call $4259              ; tramplin de la fenetre (banque 07)
        call G_04AE
        call gb_vblank          ; attente de trame -> compteur + entites
        ret

; --- VBlank GB (remplace WaitVBlank $0343) ------------------------------------
gb_vblank:
        push af
        ld hl,$DA0E
        inc (hl)
        pop af
        call G_2BFD
        ret

; --- Entrees natives ----------------------------------------------------------
; A = touches du moment (PAD_*). Meme structure que UpdatePadState ($041E) :
; bloc FFA5 : courant, nouvellement presse, relache, repetition.
read_input_native:
        ld d,a
        ld hl,$FFA5
        ld a,(hl)               ; e = etat precedent
        ld e,a
        ld a,d
        ld (hl),a               ; FFA5 = courant
        inc hl
        xor e
        and d
        ld (hl),a               ; FFA6 = nouvellement presse
        inc hl
        jr z,.norel
        ld (hl),a               ; FFA7 = relache
        inc hl
        ld (hl),$14             ; FFA8 = delai de repetition
        ret
.norel: inc hl
        or (hl)
        jr z,.rst
        dec (hl)
        dec hl
        ld (hl),$00
        ret
.rst:   ld (hl),$03
        dec hl
        ld (hl),d
        ret

; --- Routines RST de la ROM ---------------------------------------------------
; rst $08 : saut indexe. A = index, table de DW juste apres le CALL.
G_RST08:
        pop hl
        add a,a
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        jp (hl)

; rst $18 : lecture indexee. Apres le CALL : DB N puis N octets.
G_RST18:
        pop hl
        ld c,a
        ld b,0
        ld a,(hl)
        inc hl
        push hl
        add hl,bc
        ld c,a
        ld a,(hl)
        pop hl
        add hl,bc
        jp (hl)

; rst $28 : copie en ligne. Apres le CALL : DB N puis N octets copies vers (DE).
G_RST28:
        pop hl
        ld b,(hl)
        inc hl
.copy:  ld a,(hl)
        inc hl
        ld (de),a
        inc de
        dec b
        jr nz,.copy
        jp (hl)

; --- Remplacements des routines non traduites (CFG.STUBS) ---------------------
; Demande de son (A = numero GB) : memorisee, jouee apres l'affichage.
S_SOUND:
        ld (sfx_req),a
        ret

S_RET:
        ret

; Appele en boucle pendant l'attente de trame (wait_frame).
gb_idle:
        ret

; Nouvelle partie : la RAM GB part de zero ; la sequence d'init du jeu vient
; du chargement de l'etat de depart (palier chargement).
gb_new_game:
        ld hl,GB_WRAM
        ld de,GB_WRAM+1
        ld bc,$1FFF
        ld (hl),0
        ldir
        xor a
        ld (game_over),a
        ret

; --- Etat ---------------------------------------------------------------------
; Config RAM CPC par banque GB : $00 = RAM principale (pas de fenetre),
; $04-$07 = pages etendues C0-C3 montees en $4000-$7FFF.
banke_cfg:
        db $00,$00,$00,$00,$00,$00,$00,$04     ; 00-07 (07 -> page C0)
        db $00,$00,$00,$00,$00,$00,$00,$05     ; 08-0F (0F -> page C1)
        db $00,$00,$00,$00,$00,$00,$00,$00     ; 10-17
        db $00,$00,$00,$00,$00,$00,$06,$07     ; 18-1F (1E -> C2, 1F -> C3)
        db $00,$00,$00,$00,$00,$00,$00,$00     ; 20-27 (hors carte)

sfx_req:    db 0
game_over:  db 0
