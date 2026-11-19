; komut_testi.asm: TA-8'in 88 opcode'unun hepsini çalıştıran test programı.
;   - M grubu: 12 işlem × 4 kip (44 STA # ve 6C BIT # yasak) = 46 opcode
;   - U grubu (80–8C), LDX #/abs, INX, TAXL, TAXH, INCW, DECW (bayt taşmalarıyla),
;     PHA, PLA, JMP, CALL (3 seviye iç içe), RET, JMPI (ROM'daki ve RAM'deki tablo),
;     NOP, HALT
;   - 14 dallanmanın hepsi hem alınan hem alınmayan haliyle (4 flag durumu)
;   - I/O: KSTAT (BIT → N, V), KBD, ayrılmış I/O, VRAM okuması (00), VRAM ve LED yazması
; Sonuçlar 8100'den başlayarak RAM'e yazılır. Hata yoksa sonunda LED = $A5, varsa $EE.
; Çip seviyesindeki devre ile MicroEmu'nun çevrim çevrim karşılaştırması için
; (tests/test_hw_cpu.py). Çalıştırma: py cli.py run examples/komut_testi.asm

LEDS    = $F800
KBD     = $F800
KSTAT   = $F801
IO_RES  = $F803         ; ayrılmış I/O (00 okunur)
VRAM    = $F000
OUT     = $8100         ; sonuç alanı
T0      = $8080
T1      = $8081
W0      = $8082         ; 16-bit
W1      = $8084         ; 16-bit
W2      = $8086         ; 16-bit (JMPI hedefi RAM'de)
CNT     = $8088         ; 16-bit sayaç

        .org $0000
start:  NOP                     ; 01
; ---- M grubu, # kipi --------------------------------------------------------
        LDX #OUT                ; 90
        LDA #$5A                ; 40
        ADD #$30                ; 48  5A+30 = 8A (V = 1)
        STA (X+)                ; 47
        ADC #$90                ; 4C
        STA (X+)
        SUB #$11                ; 50
        STA (X+)
        SBC #$22                ; 54
        STA (X+)
        AND #$F3                ; 58
        STA (X+)
        OR #$0C                 ; 5C
        STA (X+)
        XOR #$A5                ; 60
        STA (X+)
        CMP #$40                ; 64
        CPC #$01                ; 68
        STA (X)                 ; 46
        INX                     ; 92
; ---- M grubu, abs kipi ------------------------------------------------------
        LDA #$37
        STA T0                  ; 45
        LDA #$C9
        STA T1
        LDA T0                  ; 41
        ADD T1                  ; 49
        STA (X+)
        ADC T1                  ; 4D
        STA (X+)
        SUB T0                  ; 51
        STA (X+)
        SBC T1                  ; 55
        STA (X+)
        AND T1                  ; 59
        STA (X+)
        OR T0                   ; 5D
        STA (X+)
        XOR T1                  ; 61
        STA (X+)
        CMP T0                  ; 65
        CPC T1                  ; 69
        BIT T1                  ; 6D
; ---- M grubu, (X) ve (X+) kipleri (X tabloyu gösterir) -----------------------
        LDX #tab
        LDA (X)                 ; 42
        ADD (X)                 ; 4A
        ADD (X+)                ; 4B
        STA OUT+$20
        ADC (X)                 ; 4E
        ADC (X+)                ; 4F
        STA OUT+$21
        SUB (X)                 ; 52
        SUB (X+)                ; 53
        STA OUT+$22
        SBC (X)                 ; 56
        SBC (X+)                ; 57
        STA OUT+$23
        AND (X)                 ; 5A
        AND (X+)                ; 5B
        STA OUT+$24
        OR (X)                  ; 5E
        OR (X+)                 ; 5F
        STA OUT+$25
        XOR (X)                 ; 62
        XOR (X+)                ; 63
        STA OUT+$26
        CMP (X)                 ; 66
        CMP (X+)                ; 67
        CPC (X)                 ; 6A
        CPC (X+)                ; 6B
        BIT (X)                 ; 6E
        BIT (X+)                ; 6F
        LDA (X+)                ; 43
        STA OUT+$27
; ---- U grubu ----------------------------------------------------------------
        LDA #$7F
        INC                     ; 80  80 (V = 1)
        STA OUT+$30
        DEC                     ; 81  7F (V = 1)
        STA OUT+$31
        NOT                     ; 82
        STA OUT+$32
        NEG                     ; 83
        STA OUT+$33
        SHL                     ; 84
        STA OUT+$34
        ROL                     ; 85
        STA OUT+$35
        SHR                     ; 86
        STA OUT+$36
        ROR                     ; 87
        STA OUT+$37
        ASR                     ; 88
        STA OUT+$38
        TST                     ; 89
        CLC                     ; 8A
        SEC                     ; 8B
        SEX                     ; 8C
        STA OUT+$39
        LDA #$80
        NEG                     ; 80 → 80 (V = 1, C = 0)
        LDA #$00
        NEG                     ; 00 → 00 (C = 1)
        SEX
        STA OUT+$3A
; ---- X ve W grupları --------------------------------------------------------
        LDA #$FF
        STA W0
        LDA #$00
        STA W0+1                ; W0 = 00FF
        INCW W0                 ; 98  → 0100
        DECW W0                 ; 99  → 00FF
        DECW W1                 ;     0000 → FFFF
        INCW W1                 ;     FFFF → 0000
        INCW W1                 ;     → 0001
        LDX W0                  ; 91  X = 00FF
        INX                     ;     X = 0100
        LDA #<(OUT+$40)
        TAXL                    ; 93
        LDA #>(OUT+$40)
        TAXH                    ; 94
        LDA W0
        STA (X+)
        LDA W0+1
        STA (X+)
        LDA W1
        STA (X+)
        LDA W1+1
        STA (X+)
; ---- stack ve akış ----------------------------------------------------------
        LDA #$11
        PHA                     ; A0
        LDA #$22
        PHA
        CALL alt1               ; A3
        PLA                     ; A1
        STA (X+)
        PLA
        STA (X+)
        JMPI (vektor)           ; A5  ROM'daki tablo
        JMP fail                ; A2
don1:   LDA #<don2
        STA W2
        LDA #>don2
        STA W2+1
        JMPI (W2)               ;     RAM'deki tablo
        JMP fail
don2:   JMP don3                ; A2  (yukarıdaki JMP fail'ler hiç çalışmaz)
        JMP fail
don3:
; ---- dallanmalar: 4 flag durumu, her koşul hem alınır hem alınmaz -------------
; D1: Z=1 C=0 N=0 V=0
        CLC
        BIT bits                ; M = 00
        BEQ a1
        JMP fail
a1:     BCC a2
        JMP fail
a2:     BPL a3
        JMP fail
a3:     BVC a4
        JMP fail
a4:     BGE a5
        JMP fail
a5:     BLE a6
        JMP fail
a6:     BLS a7
        JMP fail
a7:     BNE fail
        BCS fail
        BMI fail
        BVS fail
        BLT fail
        BGT fail
        BHI fail
        INCW CNT
; D2: Z=0 C=1 N=1 V=1
        SEC
        BIT bits+1              ; M = C1
        BNE b1
        JMP fail
b1:     BCS b2
        JMP fail
b2:     BMI b3
        JMP fail
b3:     BVS b4
        JMP fail
b4:     BGE b5
        JMP fail
b5:     BGT b6
        JMP fail
b6:     BHI b7
        JMP fail
b7:     BEQ fail
        BCC fail
        BPL fail
        BVC fail
        BLT fail
        BLE fail
        BLS fail
        INCW CNT
; D3: Z=0 C=0 N=1 V=0
        CLC
        BIT bits+2              ; M = 81
        BNE c1
        JMP fail
c1:     BCC c2
        JMP fail
c2:     BMI c3
        JMP fail
c3:     BVC c4
        JMP fail
c4:     BLT c5
        JMP fail
c5:     BLE c6
        JMP fail
c6:     BLS c7
        JMP fail
c7:     BEQ fail
        BCS fail
        BPL fail
        BVS fail
        BGE fail
        BGT fail
        BHI fail
        INCW CNT
; D4: Z=0 C=1 N=0 V=1
        SEC
        BIT bits+3              ; M = 41
        BNE d1
        JMP fail
d1:     BCS d2
        JMP fail
d2:     BPL d3
        JMP fail
d3:     BVS d4
        JMP fail
d4:     BLT d5
        JMP fail
d5:     BLE d6
        JMP fail
d6:     BHI d7
        JMP fail
d7:     BEQ fail
        BCC fail
        BMI fail
        BVC fail
        BGE fail
        BGT fail
        BLS fail
        INCW CNT
; ---- I/O ve bellek bölgeleri ------------------------------------------------
        BIT KSTAT               ; b7 = KRDY (N), b6 = VWR_s (V)
        BVC fail                ; pencere açık olmalı (VWR_s = 1)
        LDA KSTAT
        STA OUT+$50
        LDA KBD                 ; KRDY = 0: boş register → FF
        STA OUT+$51
        LDA IO_RES              ; ayrılmış I/O → 00
        STA OUT+$52
        LDA VRAM+5              ; VRAM okunamaz → 00 (DB pull-down)
        STA OUT+$53
        LDA $7FFF               ; ROM'un son byte'ı
        STA OUT+$54
        LDA $EFFF               ; RAM'in son byte'ı (stack sayfası)
        STA OUT+$55
        LDA #'T'
        STA VRAM+64*2+3
        LDX #VRAM+64*29+39      ; son görünen hücre
        LDA #'8'
        STA (X)
        LDA #$3C
        STA LEDS+8              ; I/O her 8 byte'ta tekrarlanır: F808 → LED
        LDA CNT
        CMP #4
        BNE fail
        LDA #$A5
        STA LEDS
        HALT                    ; 00

fail:   LDA #$EE
        STA LEDS
        HALT

; iç içe çağrılar: alt1 → alt2 → alt3
alt1:   LDA #$33
        PHA
        CALL alt2
        PLA
        STA OUT+$48
        RET                     ; A4
alt2:   LDA #$44
        CALL alt3
        STA OUT+$49
        RET
alt3:   INC
        RET

tab:    .byte $81, $7F, $40, $00, $FF, $C3, $3C, $01, $80, $55, $AA, $10, $E0, $0F
        .byte $00, $FE, $7E, $91
bits:   .byte $00, $C1, $81, $41
vektor: .word don1
