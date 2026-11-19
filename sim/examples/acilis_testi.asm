; acilis_testi.asm: TA-8 açılış kendi kendini testi (POST), ROM'da 0000'dan başlar.
; SISTEM-PLANI bölüm 16 madde 2: RAM, VRAM yazma ve ALU sınanır; sonuç LED'lerde ve ekranda.
; Çalıştırma: py cli.py run examples/acilis_testi.asm   (--dip 1 ile SW0 = 1)
; Testler:    py -m unittest tests.test_acilis
;
; Kural: henüz sınanmamış bir şeye güvenme. Aşamalar bu yüzden şu sırada:
;
;   Aşama  LED (başta)  Ne sınanır                                      Neye güvenir
;   1      $01          14 dallanma (4 bayrak durumu, alınır/alınmaz),  yalnız A, anında değerler,
;                       LDA/STA bayrağa dokunmaz, 21 ALU işlemi          dallanmalar (RAM/yığın yok)
;                       (61 vektör: sonuç + Z C N V, zincirli Z)
;   2      $02          X (LDX #/abs, INX, TAXL, TAXH, (X), (X+), sayfa  ROM'daki tablolar
;                       taşması), M grubunun abs/(X)/(X+) kipleri,
;                       BIT, JMP, JMPI (ROM'daki vektör), NOP
;   3      $03          RAM: 3a yığın sayfası EF00–EFFF (55/AA dama,     A, X ve ROM'daki özdeşlik
;                       tersi, düşük^yüksek byte deseni);                tablosu (RAM yok, yığın yok)
;                       3b 8000–EFFF, sütun sırasında MATS+ march
;   4      $04          PHA/PLA, iç içe CALL/RET (3 seviye), yığındaki    yığın sayfası (3a'da sınandı)
;                       dönüş adresi
;   5      $05          STA abs/(X)/(X+), INCW/DECW (taşma, 16-bit Z),   yığın sayfasının altı (EF00–EF17)
;                       LDX abs (RAM), JMPI (RAM'deki vektör)
;   6      $06          KSTAT b6 (VRAM penceresi) ~1 kare içinde hem 0   RAM, yığın, CALL
;                       hem 1; ekranı siler, gözle denetim deseni yazar
;   başarı $3C          ekranda "TEST TAMAM"; SW0 = 1 ise JMP $8000, değilse HALT
;
;   Hata kodu (LED) = $E0 + aşama: $E1 ALU, $E2 X/adresleme, $E3 RAM, $E4 yığın/çağrı,
;   $E5 STA/INCW/DECW/JMPI, $E6 VRAM penceresi hiç açılmıyor. Hata olunca HALT.
;   Takılma (sonsuz döngü, WAIT) olursa LED'de o aşamanın ilerleme kodu ($01–$06) kalır.
;
; Hata yolları (her biri ÖNCE LED'e yazar, çünkü VRAM'e yazılamıyor olabilir):
;   - Ekranın 0. satırına "HATA n" yazılır; ekran silinmez (RAM'e/yığına güvenilemediği için
;     silme döngüsü kurulamaz; emülatörde VRAM zaten boştur).
;   - $E1: "HATA 1 ALT xx", xx = alt test (grup) no. ALU'ya güvenilmediği için onaltılık
;     çevrim ALU'suz, ROM tablolarıyla (HEXHI/HEXLO) yapılır. Alt test no X'te durur.
;   - $E3: "HATA 3 ADRES hhll". İlk hatalı adres HALT'ta X'te, üst byte'ı A'dadır.
;     3a (yığın sayfası) hatasında RAM hiç kullanılmaz (üst byte sabit EF).
;     3b (march) hatasında adres A ve X'te yakalanır; ekrana yazmak için 3a'da sınanmış
;     iki hücreye (EF00, EF01) kopyalanır, A ve X oradan geri yüklenir.
;   - $E6: pencere hiç açılmıyorsa VRAM'e yazmak CPU'yu WAIT'te kilitler; ekrana yazılmaz.
;
; RAM testi nasıl RAM'siz ve yığınsız yapılıyor:
;   X yalnız yazılabilir (geri okunamaz) ve tek register A'dır. İki sayaç gerekir (sayfa ve
;   sayfa içi). Çözüm: dış sayaç L (adresin alt byte'ı) XL'de durur; XH'ye ROM'daki özdeşlik
;   tablosunun sayfası (IDTAB, IDTAB[i] = i) yazılıp LDA (X) yapılınca A = L olur. İç sayaç
;   H (üst byte) A'dadır ve TAXH ile XH'ye geçer. Yani adresler "sütun sırasında" gezilir:
;   (H, L) için önce L sabit, H değişir. Bu yüzden yazılan veri yalnız H'den türetilebilir:
;   d0 = H, d1 = ~H. "Adres kendi içinde" deseni burada üst byte'tır; alt adres hatlarındaki
;   yapışma/kısa devreyi march sırası yakalar (MATS+: ⇕w d0; ⇑(r d0, w d1); ⇓(r d1, w d0) her
;   adres kod çözücü hatasını ve her yapışık biti bulur; iki adres aynı hücreye düşerse sonra
;   gezilen adres d0 yerine d1 okur). Literal 55/AA ve "düşük byte XOR yüksek byte" desenleri
;   yığın sayfasında (3a) uygulanır; orada sayfa sabit olduğu için sayaç XL'dir.
;
; SW0 = 1 (Arduino'nun 8000'e yüklediği program): 8000–EEFF'e HİÇ dokunulmaz, 3b atlanır.
;   Yalnız yığın sayfası (EF00–EFFF) sınanır ve kullanılır; yüklenen program EF00'a kadar
;   uzanmamalıdır (zaten yığın orada). Böylece yüklenen program bozulmaz. (Yıkıcı olmayan
;   "oku-sakla-sına-geri yaz" seçilmedi: saklayacak yer yok, A sayaç olarak kullanılıyor.)
;
; KSTAT b6 (VRAM penceresi): önce b6 = 0, sonra b6 = 1 beklenir; her bekleme ~1 karedir
;   (1000 tur × 18 çevrim = 18.000 çevrim > 16.800). Hiç 0 görülmezse pencere hep açıktır
;   (VGA takılı değil, NO-VGA jumper'ı ya da SLOW saat): hata sayılmaz, ekranda "HEP ACIK"
;   yazar. 0 görülüp 1 görülmezse pencere hiç açılmıyordur: hata $E6.
;
; Süre (RefEmu = MicroEmu, VGA modeli kapalı; 1 MHz'de 1 çevrim = 1 µs):
;   aşama 1: 1.581, aşama 2: 776, aşama 3a: ~20.500, aşama 3b (march): ~1.445.600,
;   aşama 4–5: ~400, aşama 6 (pencere ~18.000 + ekran): ~40.500  →  toplam 1.509.387 çevrim
;   = 1,51 s. SW0 = 1 (3b atlanır): 63.757 çevrim. VGA modeli açıkken MicroEmu'da VRAM
;   yazmaları pencereyi bekler: +247.677 çevrim (toplam 1,75 s).
;   ROM: kod 0000–0F41 (3.906 byte) + tablolar 7D00–7FFF (768 byte).

LEDS    = $F800
KSTAT   = $F801
VRAM    = $F000
BASARI  = $3C

; RAM yardımcı hücreleri: yığın sayfasının altı (3a'da sınanır; SW0 = 1'de de güvenli)
S_H     = $EF00         ; march hatasında adresin üst byte'ı
S_L     = $EF01         ;                       alt byte'ı
W0      = $EF02         ; 16-bit (INCW/DECW)
W1      = $EF04         ; 16-bit
VEK     = $EF06         ; 16-bit (LDX abs, JMPI)
T0      = $EF08         ; 3 byte (STA kipleri)
METIN   = $EF10         ; ekran_yaz: liste göstericisi
HEDEF   = $EF12         ; ekran_yaz: VRAM göstericisi
SAYAC   = $EF14         ; 16-bit sayaç
RAMMOD  = $EF16         ; 0: 8000–EFFF sınandı, 1: SW0 = 1, yalnız EF00–EFFF
PENCERE = $EF17         ; 0: pencere açılıp kapanıyor, 1: hep açık (VGA yok)

; ROM tabloları (sayfa hizalı; dosyanın sonunda)
HEXHI   = $7D00         ; HEXHI[i] = i'nin üst hanesi ('0'–'F')
HEXLO   = $7E00         ; HEXLO[i] = i'nin alt hanesi
IDTAB   = $7F00         ; IDTAB[i] = i  (XL'yi geri okumak için)

        .org $0000
basla:  LDA #$01
        STA LEDS

; ============================================================================
; 1. aşama: dallanmalar, bayraklar, ALU. RAM yok, yığın yok, X yalnız alt test no.
; ============================================================================
; --- 1.00 dallanmalar: 4 bayrak durumu; her koşul hem alınır hem alınmaz.
        LDX #$00
; D1: Z=1 C=0 N=0 V=0
        LDA #$00
        CLC
        LDA #$FF                ; yükleme bayraklara dokunmaz
        BEQ d1a
        JMP f1
d1a:    BCC d1b
        JMP f1
d1b:    BPL d1c
        JMP f1
d1c:    BVC d1d
        JMP f1
d1d:    BGE d1e
        JMP f1
d1e:    BLE d1f
        JMP f1
d1f:    BLS d1g
        JMP f1
d1g:    BNE f1
        BCS f1
        BMI f1
        BVS f1
        BLT f1
        BGT f1
        BHI f1
; D2: Z=0 C=1 N=1 V=1
        LDA #$7F
        SEC
        INC                     ; 80: N=1 V=1, C korunur
        LDA #$00                ; yükleme bayraklara dokunmaz
        BNE d2a
        JMP f1
d2a:    BCS d2b
        JMP f1
d2b:    BMI d2c
        JMP f1
d2c:    BVS d2d
        JMP f1
d2d:    BGE d2e
        JMP f1
d2e:    BGT d2f
        JMP f1
d2f:    BHI d2g
        JMP f1
d2g:    BEQ f1
        BCC f1
        BPL f1
        BVC f1
        BLT f1
        BLE f1
        BLS f1
; D3: Z=0 C=0 N=1 V=0
        LDA #$80
        CLC
        BNE d3a
        JMP f1
d3a:    BCC d3b
        JMP f1
d3b:    BMI d3c
        JMP f1
d3c:    BVC d3d
        JMP f1
d3d:    BLT d3e
        JMP f1
d3e:    BLE d3f
        JMP f1
d3f:    BLS d3g
        JMP f1
d3g:    BEQ f1
        BCS f1
        BPL f1
        BVS f1
        BGE f1
        BGT f1
        BHI f1
; D4: Z=0 C=1 N=0 V=1
        LDA #$80
        SEC
        DEC                     ; 7F: V=1, C korunur
        BNE d4a
        JMP f1
d4a:    BCS d4b
        JMP f1
d4b:    BPL d4c
        JMP f1
d4c:    BVS d4d
        JMP f1
d4d:    BLT d4e
        JMP f1
d4e:    BLE d4f
        JMP f1
d4f:    BHI d4g
        JMP f1
d4g:    BEQ f1
        BCC f1
        BMI f1
        BVC f1
        BGE f1
        BGT f1
        BLS f1

; --- ALU vektörleri. Her vektör: giriş C/Z kurulur, işlem, 4 bayrak, sonuç (CMP #).
;     Beklenen değerler ta8/alu.py alu_ref ile hesaplandı. CMP eşit çıkınca Z=1 C=1 kalır.

; --- 1.01 TST, CLC, SEC (A değişmez; Z/N A'dan, V = 0)
        LDX #$01           ; alt test no (hata ekranında görünür)
        SEC
        LDA #$00
        TST             ; TST 00 (C1 Z0) = 00  Z1 C1 N0 V0
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1
        CLC
        LDA #$80
        TST             ; TST 80 (C0 Z1) = 80  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$80
        BNE f1
        LDA #$81
        CLC             ; CLC 81 (C1 Z1) = 81  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$81
        BNE f1
        CLC
        LDA #$00
        SEC             ; SEC 00 (C0 Z0) = 00  Z1 C1 N0 V0
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1

; --- 1.02 ADD (elde, yarım elde, taşma)
        LDX #$02           ; alt test no (hata ekranında görünür)
        LDA #$35
        ADD #$4A        ; ADD 35,4A (C1 Z1) = 7F  Z0 C0 N0 V0  C girişi yok sayılır
        BEQ f1
        BCS f1
        BMI f1
        BVS f1
        CMP #$7F
        BNE f1
        LDA #$0F
        ADD #$01        ; ADD 0F,01 (C1 Z1) = 10  Z0 C0 N0 V0
        BEQ f1
        BCS f1
        BMI f1
        BVS f1
        CMP #$10
        BNE f1
        LDA #$7F
        ADD #$01        ; ADD 7F,01 (C1 Z1) = 80  Z0 C0 N1 V1
        BEQ f1
        BCS f1
        BPL f1
        BVC f1
        CMP #$80
        BNE f1
        LDA #$80
        ADD #$80        ; ADD 80,80 (C1 Z1) = 00  Z1 C1 N0 V1
        BNE f1
        BCC f1
        BMI f1
        BVC f1
        CMP #$00
        BNE f1
        LDA #$C0
        ADD #$C0        ; ADD C0,C0 (C1 Z1) = 80  Z0 C1 N1 V0
        BEQ f1
        BCC f1
        BPL f1
        BVS f1
        CMP #$80
        BNE f1

; --- 1.03 ADC (C girişi, zincirli Z)
        LDX #$03           ; alt test no (hata ekranında görünür)
        CLC
        LDA #$12
        ADC #$34        ; ADC 12,34 (C0 Z0) = 46  Z0 C0 N0 V0
        BEQ f1
        BCS f1
        BMI f1
        BVS f1
        CMP #$46
        BNE f1
        LDA #$0F
        ADC #$00        ; ADC 0F,00 (C1 Z1) = 10  Z0 C0 N0 V0
        BEQ f1
        BCS f1
        BMI f1
        BVS f1
        CMP #$10
        BNE f1
        LDA #$7F
        ADC #$00        ; ADC 7F,00 (C1 Z1) = 80  Z0 C0 N1 V1
        BEQ f1
        BCS f1
        BPL f1
        BVC f1
        CMP #$80
        BNE f1
        LDA #$FF
        ADC #$00        ; ADC FF,00 (C1 Z1) = 00  Z1 C1 N0 V0  zincir: Z eski 1
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1
        LDA #$01
        SEC
        LDA #$FF
        ADC #$00        ; ADC FF,00 (C1 Z0) = 00  Z0 C1 N0 V0  zincir: Z eski 0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1

; --- 1.04 SUB (C = borç yok)
        LDX #$04           ; alt test no (hata ekranında görünür)
        LDA #$50
        SUB #$30        ; SUB 50,30 (C1 Z1) = 20  Z0 C1 N0 V0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$20
        BNE f1
        LDA #$30
        SUB #$50        ; SUB 30,50 (C1 Z1) = E0  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$E0
        BNE f1
        LDA #$10
        SUB #$01        ; SUB 10,01 (C1 Z1) = 0F  Z0 C1 N0 V0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$0F
        BNE f1
        LDA #$80
        SUB #$01        ; SUB 80,01 (C1 Z1) = 7F  Z0 C1 N0 V1
        BEQ f1
        BCC f1
        BMI f1
        BVC f1
        CMP #$7F
        BNE f1
        CLC
        LDA #$45
        SUB #$45        ; SUB 45,45 (C0 Z0) = 00  Z1 C1 N0 V0  C girişi yok sayılır
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1

; --- 1.05 SBC (borç girişi, zincirli Z)
        LDX #$05           ; alt test no (hata ekranında görünür)
        LDA #$50
        SBC #$30        ; SBC 50,30 (C1 Z1) = 20  Z0 C1 N0 V0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$20
        BNE f1
        CLC
        LDA #$50
        SBC #$30        ; SBC 50,30 (C0 Z0) = 1F  Z0 C1 N0 V0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$1F
        BNE f1
        CLC
        LDA #$00
        SBC #$00        ; SBC 00,00 (C0 Z0) = FF  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$FF
        BNE f1
        LDA #$45
        SBC #$45        ; SBC 45,45 (C1 Z1) = 00  Z1 C1 N0 V0  zincir: Z eski 1
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1
        LDA #$01
        SEC
        LDA #$45
        SBC #$45        ; SBC 45,45 (C1 Z0) = 00  Z0 C1 N0 V0  zincir: Z eski 0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1

; --- 1.06 CMP ve CPC (A değişmez)
        LDX #$06           ; alt test no (hata ekranında görünür)
        LDA #$30
        CMP #$50        ; CMP 30,50 (C1 Z1) = E0  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$30
        BNE f1
        LDA #$50
        CMP #$30        ; CMP 50,30 (C1 Z1) = 20  Z0 C1 N0 V0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$50
        BNE f1
        CLC
        LDA #$45
        CMP #$45        ; CMP 45,45 (C0 Z0) = 00  Z1 C1 N0 V0
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$45
        BNE f1
        LDA #$12
        CPC #$12        ; CPC 12,12 (C1 Z1) = 00  Z1 C1 N0 V0  16-bit eşit: üst byte
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$12
        BNE f1
        LDA #$01
        SEC
        LDA #$12
        CPC #$12        ; CPC 12,12 (C1 Z0) = 00  Z0 C1 N0 V0  alt byte farklıydı
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$12
        BNE f1
        CLC
        LDA #$12
        CPC #$12        ; CPC 12,12 (C0 Z0) = FF  Z0 C0 N1 V0  alt byte borç verdi
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$12
        BNE f1

; --- 1.07 AND, OR, XOR (C korunur, V = 0)
        LDX #$07           ; alt test no (hata ekranında görünür)
        LDA #$F0
        AND #$0F        ; AND F0,0F (C1 Z1) = 00  Z1 C1 N0 V0
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1
        CLC
        LDA #$FF
        AND #$81        ; AND FF,81 (C0 Z1) = 81  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$81
        BNE f1
        CLC
        LDA #$00
        OR #$00         ; OR 00,00 (C0 Z0) = 00  Z1 C0 N0 V0
        BNE f1
        BCS f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1
        LDA #$50
        OR #$0A         ; OR 50,0A (C1 Z1) = 5A  Z0 C1 N0 V0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$5A
        BNE f1
        LDA #$5A
        XOR #$5A        ; XOR 5A,5A (C1 Z1) = 00  Z1 C1 N0 V0
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1
        CLC
        LDA #$5A
        XOR #$FF        ; XOR 5A,FF (C0 Z1) = A5  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$A5
        BNE f1

; --- 1.08 INC, DEC (C korunur)
        LDX #$08           ; alt test no (hata ekranında görünür)
        CLC
        LDA #$7F
        INC             ; INC 7F (C0 Z0) = 80  Z0 C0 N1 V1
        BEQ f1
        BCS f1
        BPL f1
        BVC f1
        CMP #$80
        BNE f1
        CLC
        LDA #$FF
        INC             ; INC FF (C0 Z0) = 00  Z1 C0 N0 V0
        BNE f1
        BCS f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1
        LDA #$0F
        INC             ; INC 0F (C1 Z1) = 10  Z0 C1 N0 V0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$10
        BNE f1
        LDA #$80
        DEC             ; DEC 80 (C1 Z1) = 7F  Z0 C1 N0 V1
        BEQ f1
        BCC f1
        BMI f1
        BVC f1
        CMP #$7F
        BNE f1
        CLC
        LDA #$01
        DEC             ; DEC 01 (C0 Z0) = 00  Z1 C0 N0 V0
        BNE f1
        BCS f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1
        LDA #$10
        DEC             ; DEC 10 (C1 Z1) = 0F  Z0 C1 N0 V0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$0F
        BNE f1

; --- 1.09 NOT, NEG
        LDX #$09           ; alt test no (hata ekranında görünür)
        CLC
        LDA #$00
        NOT             ; NOT 00 (C0 Z0) = FF  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$FF
        BNE f1
        LDA #$5A
        NOT             ; NOT 5A (C1 Z1) = A5  Z0 C1 N1 V0
        BEQ f1
        BCC f1
        BPL f1
        BVS f1
        CMP #$A5
        BNE f1
        CLC
        LDA #$00
        NEG             ; NEG 00 (C0 Z0) = 00  Z1 C1 N0 V0
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1
        LDA #$01
        NEG             ; NEG 01 (C1 Z1) = FF  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$FF
        BNE f1
        LDA #$80
        NEG             ; NEG 80 (C1 Z1) = 80  Z0 C0 N1 V1
        BEQ f1
        BCS f1
        BPL f1
        BVC f1
        CMP #$80
        BNE f1

; --- 1.10 SHL, ROL
        LDX #$0A           ; alt test no (hata ekranında görünür)
        CLC
        LDA #$81
        SHL             ; SHL 81 (C0 Z0) = 02  Z0 C1 N0 V0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$02
        BNE f1
        LDA #$40
        SHL             ; SHL 40 (C1 Z1) = 80  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$80
        BNE f1
        LDA #$80
        ROL             ; ROL 80 (C1 Z1) = 01  Z0 C1 N0 V0
        BEQ f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$01
        BNE f1
        LDA #$08
        ROL             ; ROL 08 (C1 Z1) = 11  Z0 C0 N0 V0
        BEQ f1
        BCS f1
        BMI f1
        BVS f1
        CMP #$11
        BNE f1
        CLC
        LDA #$40
        ROL             ; ROL 40 (C0 Z0) = 80  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$80
        BNE f1

; --- 1.11 SHR, ROR, ASR
        LDX #$0B           ; alt test no (hata ekranında görünür)
        CLC
        LDA #$01
        SHR             ; SHR 01 (C0 Z0) = 00  Z1 C1 N0 V0
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1
        LDA #$80
        SHR             ; SHR 80 (C1 Z1) = 40  Z0 C0 N0 V0
        BEQ f1
        BCS f1
        BMI f1
        BVS f1
        CMP #$40
        BNE f1
        LDA #$01
        ROR             ; ROR 01 (C1 Z1) = 80  Z0 C1 N1 V0
        BEQ f1
        BCC f1
        BPL f1
        BVS f1
        CMP #$80
        BNE f1
        LDA #$10
        ROR             ; ROR 10 (C1 Z1) = 88  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$88
        BNE f1
        CLC
        LDA #$81
        ASR             ; ASR 81 (C0 Z0) = C0  Z0 C1 N1 V0
        BEQ f1
        BCC f1
        BPL f1
        BVS f1
        CMP #$C0
        BNE f1
        LDA #$7E
        ASR             ; ASR 7E (C1 Z1) = 3F  Z0 C0 N0 V0
        BEQ f1
        BCS f1
        BMI f1
        BVS f1
        CMP #$3F
        BNE f1

; --- 1.12 SEX (C korunur)
        LDX #$0C           ; alt test no (hata ekranında görünür)
        CLC
        LDA #$80
        SEX             ; SEX 80 (C0 Z0) = FF  Z0 C0 N1 V0
        BEQ f1
        BCS f1
        BPL f1
        BVS f1
        CMP #$FF
        BNE f1
        LDA #$7F
        SEX             ; SEX 7F (C1 Z1) = 00  Z1 C1 N0 V0
        BNE f1
        BCC f1
        BMI f1
        BVS f1
        CMP #$00
        BNE f1

; ============================================================================
; 2. aşama: X register'ı, adresleme kipleri, atlamalar. Yalnız ROM okunur.
; RAM testi X'e ve özdeşlik tablosuna dayandığı için önce bunlar sınanır.
; ============================================================================
asama2: LDA #$02
        STA LEDS
; LDX #, (X), (X+), INX
        LDX #tab2
        LDA (X)
        CMP #$11
        BNE f2
        LDA (X+)
        CMP #$11
        BNE f2
        LDA (X+)
        CMP #$22
        BNE f2
        INX
        LDA (X)
        CMP #$88
        BNE f2
; TAXL, TAXH ve özdeşlik tablosu (RAM testinin dayanağı)
        LDA #>IDTAB
        TAXH
        LDA #$5A
        TAXL
        LDA (X)
        CMP #$5A
        BNE f2
        LDA #$A5
        TAXL
        LDA (X)
        CMP #$A5
        BNE f2
        LDA #>HEXLO             ; TAXH alt byte'a dokunmaz: X = HEXLO+A5
        TAXH
        LDA (X)
        CMP #'5'
        BNE f2
        LDA #>HEXHI
        TAXH
        LDA (X)
        CMP #'A'
        BNE f2
; (X+) ve INX'te sayfa taşması: HEXLO+FF ('F') → IDTAB+00 (00)
        LDX #HEXLO+$FF
        LDA (X+)
        CMP #'F'
        BNE f2
        LDA (X)
        CMP #$00
        BNE f2
        LDX #HEXLO+$FF
        INX
        LDA (X)
        CMP #$00
        BNE f2
        LDX #IDTAB+$0F          ; alt yarım byte taşması
        INX
        LDA (X)
        CMP #$10
        BNE f2
; LDX abs (ROM'dan 16-bit)
        LDX px
        LDA (X)
        CMP #$C3
        BNE f2
; JMP, NOP, JMPI (ROM'daki vektör; A ← hedefin alt byte'ı)
        CMP #$C3                ; Z = 1: JMP atlamazsa aşağıdaki BEQ hataya gider
        JMP j2a
        BEQ f2
j2a:    NOP
        JMPI (vek2)
        JMP f2
j2b:    CMP #<j2b
        BNE f2
; M grubu: abs, (X), (X+) kipleri; işlenenler ROM'daki mtx (X ile) ve mta (abs) tablolarında.
; Her işlemden sonra 4 bayrak ve A denetlenir (CMP/CPC/BIT A'yı değiştirmez).
        LDX #mtx
        LDA (X+)      ; A = 3C
        CMP #$3C
        BNE f2
        LDA (X)       ; A = 5A
        CMP #$5A
        BNE f2
        LDA mta+0     ; A = 96
        CMP #$96
        BNE f2
        ADD (X)       ; 96 ADD 5A (C1 Z1) = F0  Z0 C0 N1 V0
        BEQ f2
        BCS f2
        BPL f2
        BVS f2
        CMP #$F0
        BNE f2
        ADD (X+)      ; F0 ADD 5A (C1 Z1) = 4A  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$4A
        BNE f2
        ADD mta+1     ; 4A ADD 69 (C1 Z1) = B3  Z0 C0 N1 V1
        BEQ f2
        BCS f2
        BPL f2
        BVC f2
        CMP #$B3
        BNE f2
        ADC (X)       ; B3 ADC C3 (C1 Z1) = 77  Z0 C1 N0 V1
        BEQ f2
        BCC f2
        BMI f2
        BVC f2
        CMP #$77
        BNE f2
        ADC (X+)      ; 77 ADC C3 (C1 Z1) = 3B  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$3B
        BNE f2
        ADC mta+2     ; 3B ADC 0F (C1 Z1) = 4B  Z0 C0 N0 V0
        BEQ f2
        BCS f2
        BMI f2
        BVS f2
        CMP #$4B
        BNE f2
        SUB (X)       ; 4B SUB 81 (C1 Z1) = CA  Z0 C0 N1 V1
        BEQ f2
        BCS f2
        BPL f2
        BVC f2
        CMP #$CA
        BNE f2
        SUB (X+)      ; CA SUB 81 (C1 Z1) = 49  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$49
        BNE f2
        SUB mta+3     ; 49 SUB 11 (C1 Z1) = 38  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$38
        BNE f2
        SBC (X)       ; 38 SBC 7E (C1 Z1) = BA  Z0 C0 N1 V0
        BEQ f2
        BCS f2
        BPL f2
        BVS f2
        CMP #$BA
        BNE f2
        SBC (X+)      ; BA SBC 7E (C1 Z1) = 3C  Z0 C1 N0 V1
        BEQ f2
        BCC f2
        BMI f2
        BVC f2
        CMP #$3C
        BNE f2
        SBC mta+4     ; 3C SBC 22 (C1 Z1) = 1A  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$1A
        BNE f2
        AND (X)       ; 1A AND 0F (C1 Z1) = 0A  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$0A
        BNE f2
        AND (X+)      ; 0A AND 0F (C1 Z1) = 0A  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$0A
        BNE f2
        AND mta+5     ; 0A AND F3 (C1 Z1) = 02  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$02
        BNE f2
        OR (X)       ; 02 OR F0 (C1 Z1) = F2  Z0 C1 N1 V0
        BEQ f2
        BCC f2
        BPL f2
        BVS f2
        CMP #$F2
        BNE f2
        OR (X+)      ; F2 OR F0 (C1 Z1) = F2  Z0 C1 N1 V0
        BEQ f2
        BCC f2
        BPL f2
        BVS f2
        CMP #$F2
        BNE f2
        OR mta+6     ; F2 OR 0C (C1 Z1) = FE  Z0 C1 N1 V0
        BEQ f2
        BCC f2
        BPL f2
        BVS f2
        CMP #$FE
        BNE f2
        XOR (X)       ; FE XOR 55 (C1 Z1) = AB  Z0 C1 N1 V0
        BEQ f2
        BCC f2
        BPL f2
        BVS f2
        CMP #$AB
        BNE f2
        XOR (X+)      ; AB XOR 55 (C1 Z1) = FE  Z0 C1 N1 V0
        BEQ f2
        BCC f2
        BPL f2
        BVS f2
        CMP #$FE
        BNE f2
        XOR mta+7     ; FE XOR A5 (C1 Z1) = 5B  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$5B
        BNE f2
        CMP (X)       ; 5B CMP AA (C1 Z1)  Z0 C0 N1 V1
        BEQ f2
        BCS f2
        BPL f2
        BVC f2
        CMP #$5B
        BNE f2
        CMP (X+)      ; 5B CMP AA (C1 Z1)  Z0 C0 N1 V1
        BEQ f2
        BCS f2
        BPL f2
        BVC f2
        CMP #$5B
        BNE f2
        CMP mta+8     ; 5B CMP 3C (C1 Z1)  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$5B
        BNE f2
        CPC (X)       ; 5B CPC 01 (C1 Z1)  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$5B
        BNE f2
        CPC (X+)      ; 5B CPC 01 (C1 Z1)  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$5B
        BNE f2
        CPC mta+9     ; 5B CPC 00 (C1 Z1)  Z0 C1 N0 V0
        BEQ f2
        BCC f2
        BMI f2
        BVS f2
        CMP #$5B
        BNE f2
        BIT (X)       ; 5B BIT 80 (C1 Z1)  Z0 C1 N1 V0
        BEQ f2
        BCC f2
        BPL f2
        BVS f2
        CMP #$5B
        BNE f2
        BIT (X+)      ; 5B BIT 80 (C1 Z1)  Z0 C1 N1 V0
        BEQ f2
        BCC f2
        BPL f2
        BVS f2
        CMP #$5B
        BNE f2
        BIT mta+10    ; 5B BIT C0 (C1 Z1)  Z0 C1 N1 V1
        BEQ f2
        BCC f2
        BPL f2
        BVC f2
        CMP #$5B
        BNE f2

; ============================================================================
; 3. aşama: RAM. Yığın kullanılmaz; durum yalnız A, X ve ROM'daki IDTAB'tadır.
; ============================================================================
asama3: LDA #$03
        STA LEDS
; --- 3a: yığın sayfası EF00–EFFF, satır sırasında. Sayfa sabit (EF) olduğu için sayaç
;     XL'dir: XH ← IDTAB, LDA (X) = XL, sonra XH ← EF geri (LDA bayrakları bozmaz).
; (w 55/AA dama)
        LDX #$EF00
ya1:    LDA #$55
        STA (X+)
        LDA #$AA
        STA (X+)
        LDA #>IDTAB
        TAXH
        LDA (X)                 ; A = XL
        TST                     ; XL = 0: sayfa bitti
        LDA #$EF
        TAXH
        BNE ya1
; (r 55/AA, w AA/55): okuma, yazmadan önce; aynı hücreye düşen iki adres burada görünür
ya2:    LDA #$55
        CMP (X)
        BNE f3a
        LDA #$AA
        STA (X+)
        CMP (X)
        BNE f3a
        LDA #$55
        STA (X+)
        LDA #>IDTAB
        TAXH
        LDA (X)
        TST
        LDA #$EF
        TAXH
        BNE ya2
; (r AA/55)
ya3:    LDA #$AA
        CMP (X)
        BNE f3a
        INX
        LDA #$55
        CMP (X)
        BNE f3a
        INX
        LDA #>IDTAB
        TAXH
        LDA (X)
        TST
        LDA #$EF
        TAXH
        BNE ya3
; (w L xor EF, sonra r): "adres kendi içinde", sayaç A
        LDA #$EF                ; L = 0: 00 xor EF
ya4:    STA (X+)
        XOR #$EF                ; A = L
        INC
        XOR #$EF                ; A = (L+1) xor EF
        CMP #$EF                ; L+1 = 0 (sayfa bitti) ise A = EF
        BNE ya4
        LDX #$EF00
ya5:    CMP (X)
        BNE f3a
        INX
        XOR #$EF
        INC
        XOR #$EF
        CMP #$EF
        BNE ya5
        LDA $EFFF               ; son hücre de yazıldı mı (iki döngü aynı yerde erken
        CMP #$FF^$EF            ; çıkarsa yukarıdaki doğrulama bunu göremez)
        BNE f3a

; --- SW0 = 1: 8000–EEFF'teki yüklenmiş program bozulmasın diye 3b atlanır.
        LDA KSTAT
        AND #$01
        BEQ mats
        LDA #1
        STA RAMMOD
        JMP asama4

; --- 3b: 8000–EFFF, sütun sırasında MATS+. Adres (H, L): L dış sayaç (XL'de; IDTAB ile
;     geri okunur), H iç sayaç (A'da; TAXH ile XH'ye). d0 = H, d1 = ~H.
;     ⇑ = L artan, H azalan (EF→80); ⇓ = tam tersi.
; M0 ⇕ (w d0)
mats:   LDA #$00
m0s:    TAXL
        LDA #$EF
m0h:    TAXH
        STA (X)
        DEC
        BMI m0h                 ; 80'den sonra 7F: N = 0, sütun bitti
        LDA #>IDTAB
        TAXH
        LDA (X)                 ; A = L
        INC
        BNE m0s
; M1 ⇑ (r d0, w d1)
m1s:    TAXL                    ; A = 0
        LDA #$EF
m1h:    TAXH
        CMP (X)
        BNE f3b                 ; A = H, X = hatalı adres
        NOT
        STA (X)
        NOT
        DEC
        BMI m1h
        LDA #>IDTAB
        TAXH
        LDA (X)
        INC
        BNE m1s
; M2 ⇓ (r d1, w d0)
        LDA #$FF
m2s:    TAXL
        LDA #$80
m2h:    TAXH
        NOT
        CMP (X)
        BNE f3m2                ; A = ~H, X = hatalı adres
        NOT
        STA (X)
        INC
        CMP #$F0
        BNE m2h
        LDA #>IDTAB
        TAXH
        LDA (X)
        DEC
        CMP #$FF
        BNE m2s
        LDA #0
        STA RAMMOD              ; (march yığın sayfasını da yazdığı için en sonda)

; ============================================================================
; 4. aşama: yığın ve çağrılar. SP açılışta FF; yığın EF00–EFFF (3a'da sınandı).
; ============================================================================
asama4: LDA #$04
        STA LEDS
        LDA #$11
        PHA                     ; EFFF ← 11
        LDA #$22
        PHA                     ; EFFE ← 22
        LDA $EFFF
        CMP #$11
        BNE f4
        LDA $EFFE
        CMP #$22
        BNE f4
        PLA
        CMP #$22
        BNE f4
        PLA
        CMP #$11
        BNE f4
        CALL c1                 ; EFFF ← >c_don, EFFE ← <c_don
c_don:  CMP #$C3
        BNE f4
        LDA #$44                ; SP yeniden FF olmalı
        PHA
        LDA $EFFF
        CMP #$44
        BNE f4
        PLA
        CMP #$44
        BNE f4
        JMP asama5

c1:     LDA $EFFF               ; dönüş adresi yığında doğru yerde mi
        CMP #>c_don
        BNE f4
        LDA $EFFE
        CMP #<c_don
        BNE f4
        LDA #$33
        PHA                     ; EFFD
        CALL c2
        CMP #$C3
        BNE f4
        PLA
        CMP #$33
        BNE f4
        LDA #$C3
        RET
c2:     CALL c3
        RET
c3:     LDA #$C3
        RET

; ============================================================================
; 5. aşama: STA kipleri, INCW/DECW, LDX abs ve JMPI (RAM'deki işlenenler).
; ============================================================================
asama5: LDA #$05
        STA LEDS
        LDA #$3C
        STA T0                  ; STA abs
        LDX #T0+1
        LDA #$C3
        STA (X)                 ; STA (X)
        LDA T0+1
        CMP #$C3
        BNE f5
        LDA #$5A
        STA (X+)                ; STA (X+): T0+1 ← 5A (C3'ün üstüne)
        LDA #$A5
        STA (X+)                ; T0+2 ← A5
        LDA T0
        CMP #$3C
        BNE f5
        LDA T0+1
        CMP #$5A
        BNE f5
        LDA T0+2
        CMP #$A5
        BNE f5
; INCW/DECW: A ← yeni üst byte, Z 16-bit
        LDA #$FF
        STA W0
        LDA #$00
        STA W0+1                ; W0 = 00FF
        INCW W0                 ; 0100
        BEQ f5
        CMP #$01
        BNE f5
        LDA W0
        CMP #$00
        BNE f5
        DECW W0                 ; 00FF
        BEQ f5
        BCC f5
        CMP #$00
        BNE f5
        LDA W0
        CMP #$FF
        BNE f5
        LDA #$FF
        STA W1
        STA W1+1                ; W1 = FFFF
        INCW W1                 ; 0000: Z = 1, C = 1
        BNE f5
        BCC f5
        LDA W1
        CMP #$00
        BNE f5
        DECW W1                 ; FFFF: Z = 0, C = 0 (borç)
        BEQ f5
        BCS f5
        CMP #$FF
        BNE f5
        LDA #$01
        STA W1
        LDA #$00
        STA W1+1                ; W1 = 0001
        DECW W1                 ; 0000: Z = 1
        BNE f5
; LDX abs (RAM'den)
        LDA #<(IDTAB+$77)
        STA VEK
        LDA #>(IDTAB+$77)
        STA VEK+1
        LDX VEK
        LDA (X)
        CMP #$77
        BNE f5
; JMPI (RAM'deki vektör)
        LDA #<j5
        STA VEK
        LDA #>j5
        STA VEK+1
        JMPI (VEK)
        JMP f5
j5:     CMP #<j5
        BNE f5

; ============================================================================
; 6. aşama: VRAM penceresi ve ekran (gözle denetim; VRAM okunamaz).
; ============================================================================
asama6: LDA #$06
        STA LEDS
        LDA #0
        STA PENCERE
        LDA #<1000
        STA SAYAC
        LDA #>1000
        STA SAYAC+1
p0:     BIT KSTAT               ; V = b6
        BVC p0_var              ; pencere kapalı an görüldü
        DECW SAYAC
        BNE p0
        LDA #1                  ; ~1 kare hep açık: VGA yok / SLOW, hata değil
        STA PENCERE
        JMP ekran
p0_var: LDA #<1000
        STA SAYAC
        LDA #>1000
        STA SAYAC+1
p1:     BIT KSTAT
        BVS ekran               ; pencere açıldı
        DECW SAYAC
        BNE p1
        JMP f6                  ; pencere hiç açılmıyor

; --- ekranı sil (F000–F7FF boşluk), sonra desen ve sonuçlar
ekran:  LDX #VRAM
        LDA #$00
        STA SAYAC
        LDA #$01
        STA SAYAC+1             ; 256 tur × 8 byte
sil:    LDA #' '
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        STA (X+)
        DECW SAYAC
        BNE sil
; kenarlar: 1–28. satırlarda 0. ve 39. sütun '|'
        LDA #<(VRAM+64)
        STA HEDEF
        LDA #>(VRAM+64)
        STA HEDEF+1
        LDA #28
        STA SAYAC
kenar:  LDX HEDEF
        LDA #'|'
        STA (X)
        LDA HEDEF
        ADD #39                 ; satır başı 64'ün katı: alt byte taşmaz
        TAXL
        LDA #'|'
        STA (X)
        LDA HEDEF
        ADD #64
        STA HEDEF
        LDA HEDEF+1
        ADC #0
        STA HEDEF+1
        LDA SAYAC
        DEC
        STA SAYAC
        BNE kenar
; karakter tablosu 20–7E
        LDX #VRAM+64*11+4
        LDA #$20
kt1:    STA (X+)
        INC
        CMP #$40
        BNE kt1
        LDX #VRAM+64*12+4
kt2:    STA (X+)
        INC
        CMP #$60
        BNE kt2
        LDX #VRAM+64*13+4
kt3:    STA (X+)
        INC
        CMP #$7F
        BNE kt3
; metinler
        LDA #<l_ana
        STA METIN
        LDA #>l_ana
        STA METIN+1
        CALL ekran_yaz
        LDA RAMMOD
        TST
        BNE e_ram_k
        LDA #<l_ram
        STA METIN
        LDA #>l_ram
        STA METIN+1
        JMP e_ram
e_ram_k:
        LDA #<l_ram_k
        STA METIN
        LDA #>l_ram_k
        STA METIN+1
e_ram:  CALL ekran_yaz
        LDA PENCERE
        TST
        BNE e_vga_y
        LDA #<l_vga
        STA METIN
        LDA #>l_vga
        STA METIN+1
        JMP e_vga
e_vga_y:
        LDA #<l_vga_y
        STA METIN
        LDA #>l_vga_y
        STA METIN+1
e_vga:  CALL ekran_yaz
        LDA #<l_son
        STA METIN
        LDA #>l_son
        STA METIN+1
        CALL ekran_yaz

; ============================================================================
; Sonuç: başarı. SW0 = 1 ise Arduino'nun 8000'e yüklediği program çalıştırılır.
; ============================================================================
        LDA #BASARI
        STA LEDS
        LDA KSTAT
        AND #$01
        BEQ bitti
        JMP $8000
bitti:  HALT

; ekran_yaz: METIN'deki listeyi yazar. Liste: (.word hedef, .asciz metin)..., .word 0
ekran_yaz:
        LDX METIN
        LDA (X+)
        STA HEDEF
        LDA (X)
        STA HEDEF+1
        INCW METIN
        INCW METIN
        LDA HEDEF+1
        TST
        BEQ ey_son
ey_kar: LDX METIN
        LDA (X)
        TST
        BEQ ey_sat
        LDX HEDEF
        STA (X)
        INCW HEDEF
        INCW METIN
        JMP ey_kar
ey_sat: INCW METIN              ; sondaki 0
        JMP ekran_yaz
ey_son: RET

; ============================================================================
; Hata yolları. Hepsi önce LED'e yazar, sonra 0. satıra "HATA n ..." yazar ve durur.
; ============================================================================
; $E1 ALU: ALU'ya güvenilmez; yalnız LDA #, STA, TAXH ve ROM tabloları. X = alt test no.
f1:     LDA #$E1
        STA LEDS
        LDA #'H'
        STA VRAM
        LDA #'A'
        STA VRAM+1
        STA VRAM+3
        STA VRAM+8
        LDA #'T'
        STA VRAM+2
        STA VRAM+10
        LDA #' '
        STA VRAM+4
        STA VRAM+6
        STA VRAM+11
        LDA #'1'
        STA VRAM+5
        LDA #'L'
        STA VRAM+9
        LDA #>HEXHI
        TAXH
        LDA (X)
        STA VRAM+12
        LDA #>HEXLO
        TAXH
        LDA (X)
        STA VRAM+13
        LDA #$00
        TAXH                    ; X = alt test no
        HALT

; $E3, 3a: yığın sayfasında hata. X = (EF, L). RAM'e hiç dokunulmaz.
f3a:    LDA #$E3
        STA LEDS
        CLC                     ; C = 0: 3a (başlık kodu bayrakları bozmaz)
        JMP h3
; $E3, 3b: march'ta hata. A = H, X = (H, L).
f3m2:   NOT                     ; M2'de A = ~H
f3b:    STA S_H                 ; 3a'da sınanmış hücre
        LDA #$E3
        STA LEDS
        LDA #>IDTAB
        TAXH
        LDA (X)                 ; A = L (XL)
        STA S_L
        SEC                     ; C = 1: 3b
h3:     LDA #'H'                ; "HATA 3 ADRES "
        STA VRAM
        LDA #'A'
        STA VRAM+1
        STA VRAM+3
        STA VRAM+7
        LDA #'T'
        STA VRAM+2
        LDA #' '
        STA VRAM+4
        STA VRAM+6
        STA VRAM+12
        LDA #'3'
        STA VRAM+5
        LDA #'D'
        STA VRAM+8
        LDA #'R'
        STA VRAM+9
        LDA #'E'
        STA VRAM+10
        LDA #'S'
        STA VRAM+11
        BCS h3b
; 3a: üst byte sabit EF, alt byte XL'de
        LDA #'E'
        STA VRAM+13
        LDA #'F'
        STA VRAM+14
        LDA #>HEXHI
        TAXH
        LDA (X)
        STA VRAM+15
        LDA #>HEXLO
        TAXH
        LDA (X)
        STA VRAM+16
        LDA #$EF
        TAXH                    ; X = hatalı adres, A = üst byte
        HALT
; 3b: S_H, S_L
h3b:    LDA S_H
        TAXL
        LDA #>HEXHI
        TAXH
        LDA (X)
        STA VRAM+13
        LDA #>HEXLO
        TAXH
        LDA (X)
        STA VRAM+14
        LDA S_L
        TAXL
        LDA #>HEXHI
        TAXH
        LDA (X)
        STA VRAM+15
        LDA #>HEXLO
        TAXH
        LDA (X)
        STA VRAM+16
        LDA S_H
        TAXH                    ; X = (H, L) hatalı adres, A = H
        HALT

; $E2, $E4, $E5: ALU sınanmış; aşama rakamı XL'de saklanır.
f2:     LDA #'2'
        JMP f_gen
f4:     LDA #'4'
        JMP f_gen
f5:     LDA #'5'
f_gen:  TAXL
        AND #$0F
        OR #$E0
        STA LEDS                ; $E0 + aşama
        LDA #'H'
        STA VRAM
        LDA #'A'
        STA VRAM+1
        STA VRAM+3
        LDA #'T'
        STA VRAM+2
        LDA #' '
        STA VRAM+4
        LDA #>IDTAB
        TAXH
        LDA (X)                 ; aşama rakamı
        STA VRAM+5
        HALT

; $E6: VRAM penceresi hiç açılmıyor. VRAM'e yazılırsa CPU WAIT'te kalır: yalnız LED.
f6:     LDA #$E6
        STA LEDS
        HALT

; ============================================================================
; Veriler
; ============================================================================
tab2:   .byte $11, $22, $44, $88
px:     .word IDTAB+$C3
vek2:   .word j2b
mtx:    .byte $3C, $5A, $C3, $81, $7E, $0F, $F0, $55, $AA, $01, $80, $40
        .byte $99, $66, $12, $34, $FE, $7F, $00, $C0, $2D, $E1, $4B, $B4
mta:    .byte $96, $69, $0F, $11, $22, $F3, $0C, $A5, $3C, $00, $C0

; ekran listeleri: .word hedef, .asciz metin ... .word 0
l_ana:  .word VRAM+64*0
        .asciz "0123456789012345678901234567890123456789"
        .word VRAM+64*29
        .asciz "0123456789012345678901234567890123456789"
        .word VRAM+64*1+2
        .asciz "TA-8 ACILIS TESTI"
        .word VRAM+64*3+2
        .asciz "1 ALU VE BAYRAKLAR ....... TAMAM"
        .word VRAM+64*4+2
        .asciz "2 X, ADRESLEME, ATLAMA ... TAMAM"
        .word VRAM+64*6+2
        .asciz "4 YIGIN, CALL/RET ........ TAMAM"
        .word VRAM+64*7+2
        .asciz "5 STA, INCW/DECW, JMPI ... TAMAM"
        .word VRAM+64*10+2
        .asciz "KARAKTERLER:"
        .word 0
l_ram:  .word VRAM+64*5+2
        .asciz "3 RAM 8000-EFFF .......... TAMAM"
        .word 0
l_ram_k:
        .word VRAM+64*5+2
        .asciz "3 RAM EF00-EFFF (SW0=1) .. TAMAM"
        .word 0
l_vga:  .word VRAM+64*8+2
        .asciz "6 VRAM PENCERESI ......... TAMAM"
        .word 0
l_vga_y:
        .word VRAM+64*8+2
        .asciz "6 VRAM PENCERESI ...... HEP ACIK"
        .word 0
l_son:  .word VRAM+64*27+2
        .asciz "TEST TAMAM"
        .word 0

; ============================================================================
; Sayfa hizalı tablolar
; ============================================================================
        .org HEXHI
        .text "0000000000000000"
        .text "1111111111111111"
        .text "2222222222222222"
        .text "3333333333333333"
        .text "4444444444444444"
        .text "5555555555555555"
        .text "6666666666666666"
        .text "7777777777777777"
        .text "8888888888888888"
        .text "9999999999999999"
        .text "AAAAAAAAAAAAAAAA"
        .text "BBBBBBBBBBBBBBBB"
        .text "CCCCCCCCCCCCCCCC"
        .text "DDDDDDDDDDDDDDDD"
        .text "EEEEEEEEEEEEEEEE"
        .text "FFFFFFFFFFFFFFFF"
        .org HEXLO
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .text "0123456789ABCDEF"
        .org IDTAB
        .byte $00, $01, $02, $03, $04, $05, $06, $07, $08, $09, $0A, $0B, $0C, $0D, $0E, $0F
        .byte $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $1A, $1B, $1C, $1D, $1E, $1F
        .byte $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $2A, $2B, $2C, $2D, $2E, $2F
        .byte $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $3A, $3B, $3C, $3D, $3E, $3F
        .byte $40, $41, $42, $43, $44, $45, $46, $47, $48, $49, $4A, $4B, $4C, $4D, $4E, $4F
        .byte $50, $51, $52, $53, $54, $55, $56, $57, $58, $59, $5A, $5B, $5C, $5D, $5E, $5F
        .byte $60, $61, $62, $63, $64, $65, $66, $67, $68, $69, $6A, $6B, $6C, $6D, $6E, $6F
        .byte $70, $71, $72, $73, $74, $75, $76, $77, $78, $79, $7A, $7B, $7C, $7D, $7E, $7F
        .byte $80, $81, $82, $83, $84, $85, $86, $87, $88, $89, $8A, $8B, $8C, $8D, $8E, $8F
        .byte $90, $91, $92, $93, $94, $95, $96, $97, $98, $99, $9A, $9B, $9C, $9D, $9E, $9F
        .byte $A0, $A1, $A2, $A3, $A4, $A5, $A6, $A7, $A8, $A9, $AA, $AB, $AC, $AD, $AE, $AF
        .byte $B0, $B1, $B2, $B3, $B4, $B5, $B6, $B7, $B8, $B9, $BA, $BB, $BC, $BD, $BE, $BF
        .byte $C0, $C1, $C2, $C3, $C4, $C5, $C6, $C7, $C8, $C9, $CA, $CB, $CC, $CD, $CE, $CF
        .byte $D0, $D1, $D2, $D3, $D4, $D5, $D6, $D7, $D8, $D9, $DA, $DB, $DC, $DD, $DE, $DF
        .byte $E0, $E1, $E2, $E3, $E4, $E5, $E6, $E7, $E8, $E9, $EA, $EB, $EC, $ED, $EE, $EF
        .byte $F0, $F1, $F2, $F3, $F4, $F5, $F6, $F7, $F8, $F9, $FA, $FB, $FC, $FD, $FE, $FF
