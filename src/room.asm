; ===========================================================================
; room.asm - Kirby's Dream Land 2, salle 1 du niveau 1 (CPC 6128)
;
; Memoire :
;   $0200-$02FF  demarrage
;   $0300-$1DFF  logique GB traduite (banque 0 + routines banque 7)
;   $1E00-$347F  decor 160x144 (mode 1, 40 octets/ligne)
;   $3500-$3DFF  atlas des sprites (4 decalages, data+masque)
;   $3E00-$3EFF  table des sprites
;   $3F00-$3FFF  table de sauts du script GB
;   $4000-$7FFF  banque 7 (donnees lues par la logique)
;   $8000-$BFFF  ecran (mode 1, base CRTC $8000)
;   $C000-$DFFF  RAM GB
;   $E000-$E0FF  etat du rendu (rectangles precedents)
;   $FF80-$FFFF  HRAM GB
; ===========================================================================

        DEVICE ZXSPECTRUM48
        org $0200

SCREEN          equ $4000
GA              equ $7F
GA_MODE1        equ %10001101
BG_DATA         equ $8000
LINE_TAB        equ $9700
SPRITE_ATLAS    equ $9900
PREV_LIST       equ $E000
PAD_A           equ $01
PAD_B           equ $02
PAD_R           equ $10
PAD_L           equ $20
PAD_U           equ $40
PAD_D           equ $80

start:
        di
        ld sp,$E200
        ld bc,$7F00+GA_MODE1           ; mode 1, ROM coupees
        out (c),c
        ld bc,$BC0C                    ; CRTC R12 = $20 -> ecran en $8000
        out (c),c
        ld bc,$BD10
        out (c),c
        ld bc,$BC0D
        out (c),c
        ld bc,$BD00
        out (c),c
        ; RAM GB : la photo est chargee en $8000, on la copie en $C000
        ld hl,$4000
        ld de,$C000
        ld bc,8192
        ldir
        ld hl,$6000
        ld de,$FF80
        ld bc,128
        ldir
        ld a,7
        ld ($FFA4),a
        ; ecran noir
        ld hl,SCREEN
        ld de,SCREEN+1
        ld bc,$3FFF
        ld (hl),0
        ldir
        call set_inks
        ld bc,$7F10
        out (c),c
        ld a,$54
        out (c),a
        call draw_bg
        xor a
        ld (PREV_LIST),a
        ld sp,START_SP
        jp G_11C6

set_inks:
        ld hl,room_inks
        ld c,0
.l:
        ld b,GA
        out (c),c
        ld a,(hl)
        out (c),a
        inc hl
        inc c
        ld a,c
        cp 4
        jr nz,.l
        ret

draw_bg:
        ld hl,BG_DATA
        ld (bg_ptr),hl
        ld b,144
        ld c,0
.line:
        push bc
        ld a,c
        call line_ptr
        ld de,(bg_ptr)
        ld bc,40
        ldir
        ld (bg_ptr),de
        pop bc
        inc c
        djnz .line
        ret

; ---------------------------------------------------------------------------
; Entrees : clavier/joystick -> etat joypad GB, puis UpdatePadState GB
; ---------------------------------------------------------------------------
read_input_native:
        call read_pad                  ; A = nouveau joypad GB
        ld hl,$DA3E
        ld e,(hl)
        call G_041E                    ; UpdatePadState : A=nouveau, E=ancien
        ld hl,$DA3E
        ld de,$FFA5
        ld bc,8
        ldir
        ret

; ---------------------------------------------------------------------------
; VBlank : une trame de logique, puis affichage
; ---------------------------------------------------------------------------
gb_vblank:
        call wait_frame
        ld hl,$DA0E
        inc (hl)
        call G_2BFD
        call render
        ret

wait_frame:
        ld bc,$F500
.w:
        in a,(c)
        rra
        jr nc,.w
        ret

; ---------------------------------------------------------------------------
; Affichage : restaure les anciens rectangles, puis dessine les sprites
; ---------------------------------------------------------------------------
render:
        call draw_bg
        xor a
        ld (PREV_LIST),a
        ld a,(PREV_LIST)
        jr z,.scan
        or a
        jr z,.scan
        ld b,a
        ld hl,PREV_LIST+1
.restore:
        push bc
        push hl
        ld a,(hl)
        ld (tmp_xr),a
        inc hl
        ld a,(hl)
        ld (tmp_yr),a
        call restore_rect
        pop hl
        inc hl
        inc hl
        pop bc
        djnz .restore
.scan:
        xor a
        ld (PREV_LIST),a
        ld ix,$C000
        call draw_buffer
        ld ix,$C100
        call draw_buffer
        ret

; A = y relatif (0-143) -> HL = SCREEN + line_tab[A] + 20
line_ptr:
        ld l,a
        ld h,0
        add hl,hl
        ld de,line_tab
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld de,SCREEN
        add hl,de
        ld de,20
        add hl,de
        ret

; x_rel dans tmp_xr, y_rel dans tmp_yr
restore_rect:
        ld a,(tmp_yr)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl                      ; *8
        ld e,l
        ld d,h
        add hl,hl
        add hl,hl                      ; *32
        add hl,de                      ; *40
        ld de,BG_DATA
        add hl,de
        ld a,(tmp_xr)
        ld e,a
        ld d,0
        add hl,de
        ld (bg_ptr),hl
        ld a,(tmp_yr)
        ld c,a
        ld b,16
.row:
        push bc
        ld a,c
        call line_ptr
        ld a,(tmp_xr)
        ld e,a
        ld d,0
        add hl,de
        ld de,(bg_ptr)
        ld a,(de)
        ld (hl),a
        inc de
        inc hl
        ld a,(de)
        ld (hl),a
        inc de
        inc hl
        ld a,(de)
        ld (hl),a
        inc de
        inc hl
        ld (bg_ptr),de
        pop bc
        inc c
        djnz .row
        ret

; IX = buffer OAM de 40 entrees (y,x,tuile,attributs)
draw_buffer:
        ld a,40
        ld (entry_left),a
.entry:
        ld a,(ix+0)
        or a
        jp z,.next
        sub 16
        jp c,.next
        cp 144
        jp nc,.next
        ld (tmp_y),a
        ld a,(ix+1)
        or a
        jp z,.next
        sub 8
        jp c,.next
        cp 160
        jp nc,.next
        and $FC
        ld (tmp_x),a
        ld a,(ix+2)
        and $FE
        ld (tmp_tile),a
        ld a,(ix+3)
        and $60
        ld (tmp_attr),a
        call find_frame
        jp nc,.next
        ; memorise le rectangle pour l'effacer a la trame suivante
        ld a,(PREV_LIST)
        cp 8
        jr nc,.nodraw
        ld c,a
        inc a
        ld (PREV_LIST),a
        ld l,c
        ld h,0
        add hl,hl
        ld bc,PREV_LIST+1
        add hl,bc
        ld a,(tmp_x)
        srl a
        srl a
        ld (hl),a
        inc hl
        ld a,(tmp_y)
        ld (hl),a
.nodraw:
        ld a,(tmp_y)
        ld c,a
        ld b,16
.row:
        push bc
        push de
        ld a,c
        call line_ptr
        pop de
        ld a,(tmp_x)
        srl a
        srl a
        ld l,a
        ld h,0
        call blit_byte
        call blit_byte
        call blit_byte
        pop bc
        inc c
        djnz .row
.next:
        ld de,4
        add ix,de
        ld a,(entry_left)
        dec a
        ld (entry_left),a
        jp nz,.entry
        ret

blit_byte:
        ld a,(de)                      ; data
        inc de
        ld c,a
        ld a,(de)                      ; masque
        inc de
        cpl
        and (hl)
        or c
        ld (hl),a
        inc hl
        ret

; cherche (tuile, attributs) dans la table ; rend DE=atlas, carry si trouve
find_frame:
        ld hl,sprite_tab
.l:
        ld a,(hl)
        cp $FF
        jp z,.no
        ld c,a
        ld a,(tmp_tile)
        cp c
        jr nz,.skip4
        inc hl
        ld a,(hl)
        ld b,a
        ld a,(tmp_attr)
        cp b
        jr nz,.skip3
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)
        scf
        ret
.skip3:
        inc hl
        inc hl
        inc hl
        jr .l
.skip4:
        inc hl
        inc hl
        inc hl
        inc hl
        jr .l
.no:
        or a
        ret

tmp_x:      db 0
tmp_y:      db 0
tmp_tile:   db 0
tmp_attr:   db 0
entry_left: db 0
tmp_xr:     db 0
tmp_yr:     db 0
bg_ptr:     dw 0
tmp_addr:   dw 0

far_hl:
        ret

select_bank:
        ld ($FFA4),a
        ret
select_bank_no_int:
        jp select_bank

G_RST00:
G_RST38:
G_581B:
S_RET:
S_SWITCHABLE:
        ret

; ---------------------------------------------------------------------------
; Logique GB traduite
; ---------------------------------------------------------------------------
        org $0800
        include "gb_logic.asm"
        include "input.asm"
        include "meta.inc"

; ---------------------------------------------------------------------------
; Donnees
; ---------------------------------------------------------------------------
        org BG_DATA
bg_data:
        incbin "bg.bin"

        org LINE_TAB
        include "line_tab.inc"

        org SPRITE_ATLAS
sprite_atlas:
        incbin "sprite.bin"

        org $9680
        include "sprite_tab.inc"

        org $3F00
        include "jump_table.inc"

        org $4000
        incbin "wram.bin"

        org $6000
        incbin "hram.bin"


        savebin "game.bin", $0200, $A080
