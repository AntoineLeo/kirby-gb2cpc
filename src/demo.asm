        DEVICE ZXSPECTRUM48
        org $0200
SCREEN          equ $4000
GA              equ $7F
BG_DATA         equ $8000
LINE_TAB        equ $9800
SPRITE_ATLAS    equ $9900
PAD_R           equ $10
PAD_L           equ $20
PAD_U           equ $40
PAD_D           equ $80
PAD_A           equ $01
PAD_B           equ $02

start:
        di
        ld sp,$BFF0
        ld bc,$7F00+%10001101
        out (c),c
        ld bc,$BC0C
        out (c),c
        ld bc,$BD10
        out (c),c
        ld bc,$BC0D
        out (c),c
        ld bc,$BD00
        out (c),c
        ; copie des donnees de $4000 (fichier) vers $8000
        ld hl,$4000
        ld de,$8000
        ld bc,$1B00
        ldir
        ld hl,SCREEN
        ld de,SCREEN+1
        ld bc,$3FFF
        ld (hl),0
        ldir
        call set_inks
        ld a,140
        ld (spr_x),a
        ld a,64
        ld (spr_y),a
        call draw_bg
        call draw_sprites
main:
        call wait_frame
        call read_pad
        ld c,a
        ld e,0
        bit 5,c
        jr z,.nr
        ld a,(spr_x)
        cp 24
        jr c,.nr
        sub 4
        ld (spr_x),a
        ld e,1
.nr:
        bit 4,c
        jr z,.nl
        ld a,(spr_x)
        cp 132
        jr nc,.nl
        add a,4
        ld (spr_x),a
        ld e,1
.nl:
        bit 6,c
        jr z,.nu
        ld a,(spr_y)
        cp 4
        jr c,.nu
        dec a
        ld (spr_y),a
        ld e,1
.nu:
        bit 7,c
        jr z,.nd
        ld a,(spr_y)
        cp 124
        jr nc,.nd
        inc a
        ld (spr_y),a
        ld e,1
.nd:
        ld a,e
        or a
        jr z,main
        call draw_bg
        call draw_sprites
        jr main

set_inks:
        ld hl,inks
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
        ld bc,$7F10
        out (c),c
        ld a,$54
        out (c),a
        ret

line_ptr:
        ld l,a
        ld h,0
        add hl,hl
        ld de,LINE_TAB
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

draw_sprites:
        ld hl,SPRITE_ATLAS+384
        ld a,(spr_x)
        ld (sx),a
        ld a,(spr_y)
        ld (sy),a
        call draw_one
        ld hl,SPRITE_ATLAS+192
        ld a,(spr_x)
        add a,8
        ld (sx),a
        ld a,(spr_y)
        ld (sy),a
        call draw_one
        ret

draw_one:
        ld a,(sy)
        ld c,a
        ld b,16
.row:
        push bc
        push hl
        ld a,c
        call line_ptr
        ld a,(sx)
        srl a
        srl a
        ld e,a
        ld d,0
        add hl,de
        pop de
        call blit3
        pop bc
        inc c
        djnz .row
        ret

blit3:
        ld a,(de)
        inc de
        ld c,a
        ld a,(de)
        inc de
        cpl
        and (hl)
        or c
        ld (hl),a
        inc hl
        ld a,(de)
        inc de
        ld c,a
        ld a,(de)
        inc de
        cpl
        and (hl)
        or c
        ld (hl),a
        inc hl
        ld a,(de)
        inc de
        ld c,a
        ld a,(de)
        inc de
        cpl
        and (hl)
        or c
        ld (hl),a
        inc hl
        ret

wait_frame:
        ld bc,$F500
.w:
        in a,(c)
        rra
        jr nc,.w
        ret

inks:   db $54,$44,$55,$40
bg_ptr: dw 0
spr_x:  db 140
spr_y:  db 64
sx:     db 0
sy:     db 0

        org $4000
        incbin "bg.bin"
        org $5800
        include "line_tab.inc"
        org $5900
sprite_atlas:
        incbin "sprite.bin"
        include "sprite_tab.inc"
        include "input.asm"
        savebin "demo.bin",$0200,$5B00
