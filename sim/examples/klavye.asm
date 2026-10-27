; klavye.asm: gelen her PS/2 byte'ını LED'lere ve ekrana (onaltılık) yazar.
; Çalıştırma: py cli.py run examples/klavye.asm --keys 1C,F0,1C --cycles 20000

KBD     = $F800
KSTAT   = $F801             ; b7 = byte hazır (BIT ile N), b6 = VRAM penceresi (V)
LEDS    = $F800

        .org $0000
start:  LDX #$F000          ; satır 0, sütun 0
bekle:  BIT KSTAT
        BPL bekle           ; KRDY = 0 ise bekle
        LDA KBD             ; okumak KRDY'yi temizler, klavye serbest kalır
        STA LEDS
        CALL hex2
        LDA #' '
        STA (X+)
        JMP bekle

; hex2: A'yı iki onaltılık karakter olarak (X+)'a yazar
hex2:   PHA
        SHR
        SHR
        SHR
        SHR
        CALL nibble
        PLA
        AND #$0F
        CALL nibble
        RET

nibble: CMP #10
        BLO rakam           ; A < 10
        ADD #'A'-10
        STA (X+)
        RET
rakam:  ADD #'0'
        STA (X+)
        RET
