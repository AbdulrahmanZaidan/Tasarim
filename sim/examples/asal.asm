; asal.asm: 1000'den küçük asal sayılar, deneme bölmesiyle (__divmod16).
; Yalnız tek sayılar ve tek bölenler denenir. Bölüm bölenden küçük kalınca
; bölen kökü geçmiş demektir, sayı asaldır.
; Çalıştırma: py cli.py run examples/asal.asm --ref

VRAM    = $F000
SINIR   = 1000

aday    = $8020         ; 2  denenen sayı
bolen   = $8022         ; 2
satir   = $8024         ; 2  yazılan satırın VRAM adresi
sutun   = $8026         ; 1  bu satırdaki sayı adedi (8 sayı = 40 sütun)
adet    = $8027         ; 1  bulunan asal sayısı

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

        LDA #0
        STA sutun
        STA adet
        LDA #1
        STA __pr_pad
        LDA #<(VRAM + 64*2)
        STA satir
        LDA #>(VRAM + 64*2)
        STA satir+1
        LDX satir

        LDA #2              ; 2 tek çift asal
        STA __pr_v
        LDA #0
        STA __pr_v+1
        CALL yaz
        LDA #3
        STA aday
        LDA #0
        STA aday+1

aday_dongu:
        LDA #3
        STA bolen
        LDA #0
        STA bolen+1
bolen_dongu:
        LDA aday
        STA __div_n
        LDA aday+1
        STA __div_n+1
        LDA bolen
        STA __div_d
        LDA bolen+1
        STA __div_d+1
        CALL __divmod16
        LDA __rv            ; bölüm < bölen: asal
        CMP bolen
        LDA __rv+1
        CPC bolen+1
        BLO asal
        LDA __div_r         ; kalan 0: asal değil
        OR __div_r+1
        BEQ sonraki
        LDA bolen           ; bölen += 2
        ADD #2
        STA bolen
        LDA bolen+1
        ADC #0
        STA bolen+1
        JMP bolen_dongu

asal:   LDA aday
        STA __pr_v
        LDA aday+1
        STA __pr_v+1
        CALL yaz

sonraki:
        LDA aday            ; aday += 2
        ADD #2
        STA aday
        LDA aday+1
        ADC #0
        STA aday+1
        LDA aday            ; aday < SINIR ise devam
        CMP #<SINIR
        LDA aday+1
        CPC #>SINIR
        BLO aday_dongu

        LDA satir           ; bir satır boş bırakıp toplamı yaz
        ADD #64+1
        STA __ps_v
        LDA satir+1
        ADC #0
        STA __ps_v+1
        LDA #<toplam
        STA __ps_s
        LDA #>toplam
        STA __ps_s+1
        CALL puts
        LDA #0
        STA __pr_pad
        STA __pr_v+1
        LDA adet
        STA __pr_v
        CALL print_u16
        LDA adet
        STA $F800           ; LED'lere de
        HALT

; yaz: __pr_v'yi 5 haneli yazar, 8 sayıda bir alt satıra geçer
yaz:    CALL print_u16
        LDA adet
        INC
        STA adet
        LDA sutun
        INC
        STA sutun
        CMP #8
        BNE yaz_son
        LDA #0
        STA sutun
        LDA satir
        ADD #64
        STA satir
        LDA satir+1
        ADC #0
        STA satir+1
        LDX satir
yaz_son:
        RET

baslik: .asciz "1000'DEN KUCUK ASAL SAYILAR"
toplam: .asciz "TOPLAM ASAL SAYISI: "

        .include "../lib/runtime.asm"
