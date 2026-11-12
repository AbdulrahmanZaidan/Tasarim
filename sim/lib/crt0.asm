; crt0.asm: tdcc ile derlenen C programlarının reset girişi (SISTEM-PLANI 11.3).
;
; tdcc'nin ürettiği assembly bu dosyayı en başta .include eder. Derleyici şu
; sembolleri tanımlar:
;   __data_rom   .data başlangıç değerlerinin ROM'daki kopyası
;   __data_ram   .data'nın RAM'deki yeri        __data_size  byte sayısı
;   __bss_start  sıfırlanacak global alan        __bss_size   byte sayısı
;   _main        C'deki main()
;
; Sıra: VRAM'i boşlukla doldur, .data'yı kopyala, .bss'i sıfırla, CALL main, HALT.
; Stack açılışta EFFF'den başlar (SP = FF); burada ayarlanmaz.

__rv     = $8000        ; int/işaretçi dönüş değeri (runtime.asm ile aynı)
__crt_s  = $801A        ; 2  kopyalama kaynağı      (yalnız main'den önce)
__crt_d  = $801C        ; 2  kopyalama hedefi
__crt_n  = $801E        ; 2  kalan byte sayısı

        .org $0000
__start:
        ; --- VRAM: F000–F7FF (2048 byte), 16'lık açılmış döngü, 128 tur ---
        LDX #$F000
        LDA #128
        STA __crt_n
crt_vram:
        LDA #' '
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        LDA __crt_n
        DEC
        STA __crt_n
        BNE crt_vram

        ; --- .data: __data_rom -> __data_ram ---
        LDA #<__data_rom
        STA __crt_s
        LDA #>__data_rom
        STA __crt_s+1
        LDA #<__data_ram
        STA __crt_d
        LDA #>__data_ram
        STA __crt_d+1
        LDA #<__data_size
        STA __crt_n
        LDA #>__data_size
        STA __crt_n+1
crt_data:
        LDA __crt_n
        OR __crt_n+1
        BEQ crt_bss
        LDX __crt_s
        LDA (X)
        LDX __crt_d
        STA (X)
        INCW __crt_s
        INCW __crt_d
        DECW __crt_n
        JMP crt_data

        ; --- .bss: sıfırla ---
crt_bss:
        LDX #__bss_start
        LDA #<__bss_size
        STA __crt_n
        LDA #>__bss_size
        STA __crt_n+1
        OR __crt_n
        BEQ crt_main
crt_bss_tur:
        LDA #0
        STA (X+)
        DECW __crt_n
        BNE crt_bss_tur

crt_main:
        CALL _main
        HALT
