; fibonacci.asm: 16-bit Fibonacci sayıları, F0 … F24 = 46368 (16 bite sığan son terim).
; 16-bit toplama (ADD + ADC) ve print_u16 örneği.
; Çalıştırma: py cli.py run examples/fibonacci.asm

VRAM    = $F000

fa      = $8020         ; F(n)
fb      = $8022         ; F(n+1)
ft      = $8024         ; geçici
n       = $8026
satir   = $8028         ; yazılan satırın VRAM adresi

        .org $0000
start:  LDA #<baslik
        STA __ps_s
        LDA #>baslik
        STA __ps_s+1
        LDA #<(VRAM + 1)
        STA __ps_v
        LDA #>(VRAM + 1)
        STA __ps_v+1
        CALL puts

        LDA #0              ; F0 = 0, F1 = 1
        STA fa
        STA fa+1
        STA fb+1
        STA n
        LDA #1
        STA fb
        LDA #<(VRAM + 64*2 + 1)
        STA satir
        LDA #>(VRAM + 64*2 + 1)
        STA satir+1

dongu:  LDX satir           ; "F<n>" satır başına
        LDA #'F'
        STA (X+)
        LDA n
        STA __pr_v
        LDA #0
        STA __pr_v+1
        STA __pr_pad
        CALL print_u16

        LDA satir           ; X = satir + 4: "=" hep aynı sütunda
        ADD #4
        TAXL
        LDA satir+1
        ADC #0
        TAXH
        LDA #'='
        STA (X+)
        LDA #' '
        STA (X+)
        LDA #1              ; değer 5 haneye sağa yaslı
        STA __pr_pad
        LDA fa
        STA __pr_v
        LDA fa+1
        STA __pr_v+1
        CALL print_u16

        LDA fa              ; t = a + b, a = b, b = t
        ADD fb
        STA ft
        LDA fa+1
        ADC fb+1
        STA ft+1
        LDA fb
        STA fa
        LDA fb+1
        STA fa+1
        LDA ft
        STA fb
        LDA ft+1
        STA fb+1

        LDA satir           ; alt satır
        ADD #64
        STA satir
        LDA satir+1
        ADC #0
        STA satir+1
        LDA n
        INC
        STA n
        CMP #25
        BNE dongu
        HALT

baslik: .asciz "FIBONACCI SAYILARI (16-BIT)"

        .include "../lib/runtime.asm"
