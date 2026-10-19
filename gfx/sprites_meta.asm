; Fichier généré par tools/cpcgfx.py : sprites (mode 1).

NSPRITES    equ 1
SPR_AREA_B_SIZE equ 0
spr_raw_tab                     ; image non décalée (utilisée au démarrage)
        dw spr_raw0
spr_ptr                         ; image décalée : [numéro x 4 + décalage]
        dw $A600, $A620, $A644, $A668
spr_wtab                        ; largeur en octets : [numéro x 4 + décalage]
        db 2, 3, 3, 3
spr_htab
        db 8
spr_x0tab                       ; décalage signé depuis le point d'ancrage
        db 252
spr_y0tab
        db 248
