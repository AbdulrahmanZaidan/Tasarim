; runtime.asm: TD-8 çalışma zamanı kütüphanesi (C derleyicisinin de kullanacağı rutinler)
;
; Kullanım: programın sonunda   .include "../lib/runtime.asm"
;
; Çağırma kuralı (SISTEM-PLANI 11.3, statik çerçeve):
;   - Parametreler aşağıdaki sabit RAM yuvalarına yazılır, sonra CALL.
;   - 16-bit sonuç __rv'de (8000) döner.
;   - Rutinler A'yı ve flag'leri bozar. X yalnızca yazdırma rutinlerinde değişir.
;   - 8000–801F bu kütüphaneye ayrılmıştır.
;
; Rutinler:
;   __mul16     __rv = __mul_a * __mul_b            (mod 65536, işaretli/işaretsiz aynı)
;   __divmod16  __rv = __div_n / __div_d, __div_r = __div_n % __div_d  (işaretsiz)
;               __div_d = 0 ise __rv = FFFF, __div_r = __div_n
;   print_u16   __pr_v'yi ondalık olarak (X+)'a yazar; __pr_pad != 0 ise 5 haneye
;               boşlukla sağa yaslar, = 0 ise baştaki sıfırları atlar
;   puts        __ps_s adresindeki 0 ile biten metni __ps_v adresine yazar;
;               sonunda X metnin bittiği yeri gösterir (print_u16 devam edebilir)

__rv     = $8000        ; 2  dönüş değeri
__mul_a  = $8002        ; 2
__mul_b  = $8004        ; 2
__div_n  = $8006        ; 2  bölünen; rutin sonunda bölüm
__div_d  = $8008        ; 2  bölen
__div_r  = $800A        ; 2  kalan
__cnt    = $800C        ; 1  döngü sayacı
__pr_v   = $800E        ; 2
__pr_p   = $8010        ; 2  10'un kuvveti
__pr_d   = $8012        ; 1  rakam karakteri
__pr_f   = $8013        ; 1  1 = ilk anlamlı rakam yazıldı
__pr_pad = $8014        ; 1
__ps_s   = $8016        ; 2  metin göstericisi
__ps_v   = $8018        ; 2  hedef (puts içinde X yedeği)

; ---------------------------------------------------------------------------
; __mul16: kaydır-topla. Çarpanın her biti için bir tur; çarpan sıfırlanınca biter,
; yani küçük çarpanda kısa sürer (__mul_b < 256 ise en çok 8 tur).
; ---------------------------------------------------------------------------
__mul16:
        LDA #0
        STA __rv
        STA __rv+1
mul_tur:
        LDA __mul_b+1       ; b >>= 1, en düşük bit C'ye
        SHR
        STA __mul_b+1
        LDA __mul_b
        ROR
        STA __mul_b
        BCC mul_ekleme
        LDA __rv            ; bit 1 ise rv += a
        ADD __mul_a
        STA __rv
        LDA __rv+1
        ADC __mul_a+1
        STA __rv+1
mul_ekleme:
        LDA __mul_b         ; b == 0 ise bitti
        OR __mul_b+1
        BEQ mul_son
        LDA __mul_a         ; a <<= 1
        SHL
        STA __mul_a
        LDA __mul_a+1
        ROL
        STA __mul_a+1
        JMP mul_tur
mul_son:
        RET

; ---------------------------------------------------------------------------
; __divmod16: geri yüklemeli bölme, 16 tur. Bölünen sola kayarken üst biti
; kalana girer; kalan >= bölen ise çıkarılır ve bölümün o biti 1 olur.
; ---------------------------------------------------------------------------
__divmod16:
        LDA #0
        STA __div_r
        STA __div_r+1
        LDA #16
        STA __cnt
div_tur:
        LDA __div_n         ; (r:n) <<= 1
        SHL
        STA __div_n
        LDA __div_n+1
        ROL
        STA __div_n+1
        LDA __div_r
        ROL
        STA __div_r
        LDA __div_r+1       ; k. turda r < 2^k olduğundan kalan 16 bitten taşmaz
        ROL
        STA __div_r+1
        LDA __div_r         ; r < d ise çıkarma yok
        CMP __div_d
        LDA __div_r+1
        CPC __div_d+1
        BLO div_sonraki
        LDA __div_r         ; r -= d
        SUB __div_d
        STA __div_r
        LDA __div_r+1
        SBC __div_d+1
        STA __div_r+1
        LDA __div_n         ; bölümün bu biti 1
        OR #1
        STA __div_n
div_sonraki:
        LDA __cnt
        DEC
        STA __cnt
        BNE div_tur
        LDA __div_n
        STA __rv
        LDA __div_n+1
        STA __rv+1
        RET

; ---------------------------------------------------------------------------
; print_u16: 10000, 1000, 100, 10 art arda çıkarılarak rakamlar bulunur
; (bölme gerekmez, en çok 9 çıkarma / rakam).
; ---------------------------------------------------------------------------
print_u16:
        LDA #0
        STA __pr_f
        LDA #<10000
        STA __pr_p
        LDA #>10000
        STA __pr_p+1
        CALL pr_rakam
        LDA #<1000
        STA __pr_p
        LDA #>1000
        STA __pr_p+1
        CALL pr_rakam
        LDA #100
        STA __pr_p
        LDA #0
        STA __pr_p+1
        CALL pr_rakam
        LDA #10
        STA __pr_p
        CALL pr_rakam
        LDA __pr_v          ; birler basamağı her zaman yazılır
        ADD #'0'
        STA (X+)
        RET

pr_rakam:
        LDA #'0'
        STA __pr_d
pr_dongu:
        LDA __pr_v          ; v < p ise rakam bulundu
        CMP __pr_p
        LDA __pr_v+1
        CPC __pr_p+1
        BLO pr_yaz
        LDA __pr_v          ; v -= p, rakam++
        SUB __pr_p
        STA __pr_v
        LDA __pr_v+1
        SBC __pr_p+1
        STA __pr_v+1
        LDA __pr_d
        INC
        STA __pr_d
        JMP pr_dongu
pr_yaz:
        LDA __pr_d
        CMP #'0'
        BNE pr_anlamli
        LDA __pr_f          ; baştaki sıfır mı?
        TST                 ; (yükleme flag'lere dokunmaz)
        BNE pr_anlamli_0
        LDA __pr_pad
        TST
        BEQ pr_bitti
        LDA #' '
        STA (X+)
        RET
pr_anlamli_0:
        LDA #'0'
pr_anlamli:
        STA (X+)
        LDA #1
        STA __pr_f
pr_bitti:
        RET

; ---------------------------------------------------------------------------
; puts: X tek gösterici olduğu ve geri okunamadığı için kaynak ile hedef
; arasında gidip gelinir; hedef __ps_v'de tutulur.
; ---------------------------------------------------------------------------
puts:
        LDX __ps_s
        LDA (X)
        TST
        BEQ ps_son
        LDX __ps_v
        STA (X+)
        INCW __ps_v
        INCW __ps_s
        JMP puts
ps_son:
        LDX __ps_v          ; X metnin bittiği yerde kalır, yazmaya devam edilebilir
        RET
