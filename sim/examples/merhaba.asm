; merhaba.asm: ekrana yazı yazar, LED'leri yakar, durur.
; Çalıştırma: py cli.py run examples/merhaba.asm
;
; puts, C derleyicisinin üreteceği kodun aynısı: X tek pointer olduğu için
; kaynak ve hedef her karakterde yeniden yüklenir (karakter başına 37 çevrim).

LEDS    = $F800
VRAM    = $F000
ps_s    = $8000             ; puts: kaynak pointer'ı (2 byte)
ps_v    = $8002             ; puts: hedef pointer'ı (2 byte)

        .org $0000
start:  LDA #<mesaj
        STA ps_s
        LDA #>mesaj
        STA ps_s+1
        LDA #<(VRAM + 64*1 + 2)     ; satır 1, sütun 2
        STA ps_v
        LDA #>(VRAM + 64*1 + 2)
        STA ps_v+1
        CALL puts
        LDA #$55
        STA LEDS
        HALT

; puts: ps_s'deki 0 ile biten metni ps_v'ye kopyalar
puts:   LDX ps_s
        LDA (X)
        TST                         ; yükleme flag'lere dokunmaz
        BEQ bitti
        LDX ps_v
        STA (X)
        INCW ps_v
        INCW ps_s
        JMP puts
bitti:  RET

mesaj:  .asciz "MERHABA, TD-8!"
