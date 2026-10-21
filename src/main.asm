; ===========================================================================
; main.asm - portage Kirby's Dream Land 2 -> Amstrad CPC 6128 (sjasmplus)
;
; La logique du jeu est la ROM GB traduite en Z80 (gb/gb_logic*.asm, genere
; par tools/gb2z80.py) ; elle est prouvee identique tour par tour contre le
; GB (check.sh, trace level1_loop). Ce fichier : demarrage (firmware coupe),
; interruption, boucle de jeu avec la cadence GB (6 pas / 5 trames CPC,
; motif 2,1,1,1,1) et les entrees natives. L'affichage vient ensuite
; (docs/portage.md §10 etape 4).
;
; Carte memoire : docs/portage.md §2 (toute la RAM GB reste a ses adresses).
; ===========================================================================

        DEVICE NOSLOT64K
        INCLUDE "defs.asm"

; =====================================================================================
; Partie A : $0200-$3FFF (support + entrees + son + banque 0 + banque 07)
; =====================================================================================
        ORG LOAD_ADDR
start:
        di
        ld sp,LOAD_ADDR             ; pile en $0100-$01FF
        ld bc,$7F00 + GA_MODE1      ; mode 1, ROM coupees
        out (c),c
        ld a,$C3                    ; IM 1 : saut en $0038 vers isr
        ld ($0038),a
        ld hl,isr
        ld ($0039),hl
        im 1
        ld bc,$BC01                 ; CRTC R1 : 20 caracteres (40 o/mode 1)
        out (c),c
        ld bc,$BD14
        out (c),c
        ld bc,$BC06                 ; R6 : 18 rangees affichees (144 lignes)
        out (c),c
        ld bc,$BD12
        out (c),c
        ld bc,$BC0C                 ; R12/R13 : ecran en $E000 (base $C000 + $2000)
        out (c),c
        ld bc,$BD38
        out (c),c
        ld bc,$BC0D
        out (c),c
        ld bc,$BD00
        out (c),c
        call sound_init
        ei
        call play_game
.halt:  jr .halt

; --- Interruption (300 Hz, 6 par trame) : compte le temps ecoule ------------
isr:
        push af
        ld a,(int6)
        inc a
        cp 6
        jr c,.s
        ld a,(frames)
        inc a
        ld (frames),a
        xor a
.s:     ld (int6),a
        pop af
        ei
        ret

frames: db 0
int6:   db 0

; Attend le debut du signal VSYNC (PPI port B, bit 0).
wait_frame:
        ld b,$F5
        in a,(c)
        rra
        ret c
.w:     call gb_idle
        ld b,$F5
        in a,(c)
        rra
        jr nc,.w
        ret

; Cale le compteur de trames sur le VSYNC.
sync_frames:
        ld b,$F5
.a:     in a,(c)
        rra
        jr c,.a
.b:     in a,(c)
        rra
        jr nc,.b
        xor a
        ld (int6),a
        ret

; --- Partie en cours ----------------------------------------------------------
tick_pattern: db 2, 1, 1, 1, 1
tick_phase:   db 0
ticks_due:    db 0
last_frame:   db 0

play_game:
        call gb_new_game
        call sync_frames
        ld a,(frames)
        ld (last_frame),a
.frame:
        call wait_frame
        ld a,(frames)               ; pas de logique dus pour les trames ecoulees
        ld hl,last_frame
        sub (hl)
        cp 7                        ; au plus 6 trames de retard rattrapees
        jr c,.lag
        ld a,6
.lag:   ld b,a
        ld a,(frames)
        ld (hl),a
        or a
        ld a,b
        or a
        jr z,.nodue
.due:   ld a,(tick_phase)
        ld e,a
        ld d,0
        ld hl,tick_pattern
        add hl,de
        ld a,(ticks_due)
        add a,(hl)
        ld (ticks_due),a
        ld a,e
        inc a
        cp 5
        jr c,.ph
        xor a
.ph:    ld (tick_phase),a
        djnz .due
.nodue: call read_pad
        call apply_fire
        call read_input_native      ; bloc FFA5-FFA8 (une fois par trame CPC)
.tick:  ld a,(ticks_due)
        or a
        jr z,.ticked
        dec a
        ld (ticks_due),a
        call gb_tick
        jr .tick
.ticked:
        call play_sfx
        ld a,(game_over)
        or a
        jr z,.frame
        ret

        INCLUDE "gb_support.asm"
        INCLUDE "input.asm"
        INCLUDE "sound.asm"

; --- Logique GB traduite ------------------------------------------------------
        INCLUDE "../gb/gb_logic.asm"
        INCLUDE "../gb/gb_logic_b07.asm"
        ASSERT $ <= $3F00, "logique niveau 1 trop grande pour $0200-$3F00"

; ---------------------------------------------------------------------------
; Table de sauts du script (fixe en $3F00, 43 commandes) : le jeu fait ld h,$3f
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
; Donnees ROM en $3F56-$3FFF : tables de pointeurs lues par la logique
; ---------------------------------------------------------------------------
        org $3F56
        incbin "../re/ref/bank_00.bin",$3F56,170

; =====================================================================================
; Banques traduites restantes : $F6C0-$FDFF (trou d'echo, apres l'ecran)
; =====================================================================================
        ORG BANK_CODE
        INCLUDE "../gb/gb_logic_b1e.asm"
        INCLUDE "../gb/gb_logic_b0f.asm"
        INCLUDE "../gb/gb_logic_b1f.asm"
        INCLUDE "../gb/gb_logic_b1a.asm"
        ASSERT $ <= $FE00, "banques 1E/0F/1F/1A trop grandes"

        SAVEBIN "build/game.bin", LOAD_ADDR, $4000 - LOAD_ADDR
        SAVEBIN "build/game_banks.bin", BANK_CODE, $FE00 - BANK_CODE
