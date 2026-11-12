/* snake.c: TD-8 yılan oyunu (SISTEM-PLANI 11.4), projenin final demosu.
 *
 *   py -3 -m tdcc examples/snake.c -o build/snake_c.asm     derle
 *   py -3 play.py examples/snake.c                           klavyeyle oyna
 *
 * Ekran (40 x 30 karakter):
 *   satır 0          başlık ve 4 basamaklı skor
 *   satır 1 ve 29    üst ve alt duvar; sütun 0 ve 39 yan duvarlar
 *   satır 2..28, sütun 1..38: oyun alanı (27 x 38 = 1026 hücre)
 *
 * Konum = satır * 64 + sütun: VRAM adresiyle aynı düzen (VRAM[konum]); 64 ile
 * çarpma kaydırmadır, oyun döngüsünde hiç çarpma/bölme yoktur.
 *
 * board[]: VRAM'in RAM'deki gölgesi (VRAM yalnız yazılır, okunamaz). Oyun
 *   alanında ve duvarlarda her hücrede ekrandaki karakter durur; başlık satırı ve
 *   görünmeyen sütunlar (40..63) DIS (0) kalır. Çarpışma denetimi ve yemin boş
 *   hücre araması böylece tek bir bellek okumasıdır.
 * govde[]: yılanın hücreleri, kuyruktan başa doğru halka tampon. 256 giriş;
 *   indeksler unsigned char olduğundan 255'ten 0'a kendiliğinden sarar.
 *
 * Zamanlama: VRAM yazma penceresi (KSTAT.VWIN) her karede bir kez açılır
 *   (kare = 16,8 ms, pencere 1,31 ms). Ana döngü pencerenin açıldığı kenarı sayar
 *   ve `hiz` karede bir hamle yapar. Hamle pencere açılır açılmaz yapılır; VRAM
 *   yazmaları pencerenin içine düşer ve CPU beklemez (SISTEM-PLANI 8.5). Yem
 *   yenince yenisinin yeri hemen aranır (yalnız RAM, süresi değişken) ama ekrana
 *   bir sonraki karenin penceresinde yazılır.
 *
 * En büyük uzunluk (UZUN_MAX, en çok 256) dolunca oyun kazanılır: "KAZANDIN".
 * 256 < 1026 olduğundan yem için her zaman boş hücre vardır.
 */
#include "hw.h"

/* --- Ekran düzeni -------------------------------------------------------- */
#define BASLIK_SATIR  0
#define UST_DUVAR     1
#define ALT_DUVAR     29
#define SOL_DUVAR     0
#define SAG_DUVAR     39
#define ILK_SATIR     2             /* oyun alanı: satır 2..28 (sütun 1..38) */
#define SON_SATIR     28
#define SKOR_SUTUN    35            /* başlıktaki 4 basamak: sütun 35..38 */
#define TAHTA_BOYU    (ROWS * STRIDE)   /* board[] boyutu: 1920 */

#define KUTU_SATIR    13            /* "OYUN BITTI" kutusu: satır 13..17 */
#define KUTU_SUTUN    10            /* sütun 10..29 */
#define KUTU_SKOR     11            /* kutudaki skorun kutu içindeki sütunu */

/* --- Hücre karakterleri ---------------------------------------------------- */
#define DIS     0                   /* board: oyun alanının dışı */
#define BOS     ' '
#define DUVAR   '#'
#define BAS     'O'
#define GOVDE   'o'
#define YEM     '*'

/* --- PS/2 set 2 scan code'ları (SISTEM-PLANI 9) ------------------------------ */
#define K_ONEK    0xE0              /* genişletilmiş tuş öneki: atlanır */
#define K_BIRAK   0xF0              /* bırakma: sonraki byte atlanır */
#define K_YUKARI  0x75              /* ok tuşları E0 ile gelir (E0 yoksa sayısal tuş takımı 8 2 4 6) */
#define K_ASAGI   0x72
#define K_SOL     0x6B
#define K_SAG     0x74
#define K_W       0x1D
#define K_A       0x1C
#define K_S       0x1B
#define K_D       0x23
#define K_BOSLUK  0x29
#define K_ENTER   0x5A              /* ana Enter; E0 5A (sayısal Enter) de olur */

/* --- Yönler: zıt yön = yön ^ 2 ---------------------------------------------- */
#define SAG     0
#define ASAGI   1
#define SOL     2
#define YUKARI  3

/* --- Hız: `hiz` karede bir hamle ------------------------------------------- */
#ifndef HIZ_BAS
#define HIZ_BAS   8                 /* başlangıç: 8 kare = 134 ms, ~7,4 hamle/sn */
#endif
#define HIZ_MIN   4                 /* en hızlı: 4 karede bir */
#define HIZ_ADIM  5                 /* her 5 yemde bir kare azalır */

/* VGA kartı yoksa (NO-VGA jumper'ı) VWIN hep 1 olur, kenar gelmez. Pencere bu
 * kadar tur boyunca açık kalırsa bir kare geçmiş sayılır (normalde pencere
 * 1,3 ms'dir, ana döngü o sürede en çok ~40 tur döner). */
#define VGA_YOK_TUR  250            /* x ~63 çevrimlik tur = ~16 ms */

/* --- Yılan ------------------------------------------------------------------ */
#ifndef UZUN_MAX
#define UZUN_MAX  256               /* govde[] halkasının boyu; en çok 256 */
#endif
#define BAS_UZUN  3
#define BAS_KONUM (15 * STRIDE + 20)    /* başlangıçta baş: satır 15, sütun 20 */

/* --- Yem: 16-bit Galois LFSR (x^16 + x^14 + x^13 + x^11 + 1, periyot 65535) -- */
#define LFSR_TOHUM  0xACE1
#define LFSR_MASKE  0xB400
#define KONUM_MASKE 0x7FF           /* 11 bit = satır (5 bit) * 64 + sütun (6 bit) */

/* --- Oyun durumu ------------------------------------------------------------- */
#define OYNUYOR  0
#define BITTI    1
#define KAZANDI  2

char board[TAHTA_BOYU];             /* VRAM'in gölgesi */
unsigned govde[256];                /* halka tampon: yılanın konumları */
unsigned char kuyruk, bas;          /* halkada kuyruğun ve başın indeksi */
unsigned bas_konum;                 /* = govde[bas] */
unsigned uzunluk;
unsigned yem_konum;
unsigned lfsr = LFSR_TOHUM;         /* oyunlar arasında sürer: her oyun farklı başlar */
unsigned skor;                      /* ikili skor: LED'ler düşük byte'ı gösterir */
char skor_k[4];                     /* aynı skor, ondalık karakterler ('0'..'9') */
unsigned char yon;                  /* son hamlenin yönü */
unsigned char istek;                /* sonraki hamlenin yönü (tuşlarla değişir) */
unsigned char hiz;                  /* kaç karede bir hamle */
unsigned char kare_say;             /* son hamleden beri geçen kare */
unsigned char hiz_yem;              /* son hızlanmadan beri yenen yem */
unsigned char durum;
unsigned char birak;                /* F0 görüldü: sonraki byte bırakma kodu */
unsigned char pencere;              /* VWIN'in önceki değeri (kenar bulmak için) */
unsigned char acik_tur;             /* pencere kaç turdur açık (VGA yok denetimi) */
unsigned char yeniden;              /* boşluk/Enter: sonraki karede yeni oyun */
unsigned char yem_bekliyor;         /* yeni yem seçildi, sonraki karede ekrana yazılacak */
unsigned hamle_sayisi;              /* bitmiş hamle sayısı (testler bununla eşlenir) */
unsigned char oyun_sayisi;          /* başlamış oyun sayısı (testler için) */

/* Hücreye karakter koy: gölgeye ve ekrana birlikte. */
void koy(unsigned p, char c)
{
    board[p] = c;
    VRAM[p] = c;
}

/* Metni yalnız ekrana yaz (başlık satırı; gölgede DIS kalır). */
void ekrana(unsigned p, const char *s)
{
    volatile char *v = VRAM + p;
    while (*s)
        *v++ = *s++;
}

/* Metni oyun alanına yaz: ekran ve gölge birlikte (yeni oyunda silinsin diye). */
void alana(unsigned p, const char *s)
{
    char *b = board + p;
    volatile char *v = VRAM + p;
    while (*s) {
        *b++ = *s;
        *v++ = *s++;
    }
}

/* 4 basamaklı skoru başlık satırına yaz (yalnız ekrana). */
void skor_yaz(void)
{
    volatile char *v = VRAM + BASLIK_SATIR * STRIDE + SKOR_SUTUN;
    v[0] = skor_k[0];
    v[1] = skor_k[1];
    v[2] = skor_k[2];
    v[3] = skor_k[3];
}

/* LFSR'yi bir adım ilerlet. */
void lfsr_adim(void)
{
    if (lfsr & 1)
        lfsr = (lfsr >> 1) ^ LFSR_MASKE;
    else
        lfsr = lfsr >> 1;
}

/* Yem için rastgele boş hücre seç ve gölgeye koy (yalnız RAM; ekrana çağıran
 * yazar). 11 bitlik değer doğrudan konumdur: satır (5 bit) * 64 + sütun (6 bit).
 * Alan dışı ya da dolu çıkarsa yeniden denenir. Ardışık LFSR durumları birbirinin
 * bir bit kaymışıdır; üst byte'ı alta katlamak (^ >> 8) ret zincirlerini kısaltır:
 * boş alanda, 65535 başlangıç durumunun hepsinde ortalama 2,08 deneme, en çok 16
 * (katlamasız 2,44 ve 33). Her hücre periyotta eşit sayıda (32 kez) çıkar. */
void yem_ara(void)
{
    unsigned p;
    do {
        lfsr_adim();
        p = (lfsr ^ (lfsr >> 8)) & KONUM_MASKE;
    } while (p >= TAHTA_BOYU || board[p] != BOS);
    yem_konum = p;
    board[p] = YEM;
}

/* Skoru bir artır: ondalık karakterlerde elle elde (bölme yok), LED'ler. */
void skor_artir(void)
{
    char *d = skor_k + 3;           /* birler basamağı */
    skor++;
    LEDS = skor;
    while (++*d > '9') {
        *d = '0';
        if (d == skor_k)
            break;                  /* 9999'dan sonra 0000 */
        d--;
    }
    skor_yaz();
}

/* Oyun bitti ya da kazanıldı: ortada kutu, içinde skor. */
void oyun_sonu(unsigned char d)
{
    char k;

    durum = d;
    alana(KUTU_SATIR * STRIDE + KUTU_SUTUN,       "+------------------+");
    if (d == KAZANDI)
        alana((KUTU_SATIR + 1) * STRIDE + KUTU_SUTUN, "|     KAZANDIN!    |");
    else
        alana((KUTU_SATIR + 1) * STRIDE + KUTU_SUTUN, "|    OYUN BITTI    |");
    alana((KUTU_SATIR + 2) * STRIDE + KUTU_SUTUN, "|    SKOR: 0000    |");
    for (k = 0; k < 4; k++)
        koy((KUTU_SATIR + 2) * STRIDE + KUTU_SUTUN + KUTU_SKOR + k, skor_k[k]);
    alana((KUTU_SATIR + 3) * STRIDE + KUTU_SUTUN, "|  BOSLUK / ENTER  |");
    alana((KUTU_SATIR + 4) * STRIDE + KUTU_SUTUN, "+------------------+");
}

/* Bir hamle: başı ilerlet, yem/duvar/gövde denetimi, kuyruğu çek. */
void hamle(void)
{
    unsigned yeni, kuyruk_konum;
    char c, buyu;

    lfsr_adim();                   /* yem yeri oyuncunun hareketine de bağlı olsun */
    yon = istek;
    if (yon == SAG)
        yeni = bas_konum + 1;
    else if (yon == SOL)
        yeni = bas_konum - 1;
    else if (yon == ASAGI)
        yeni = bas_konum + STRIDE;
    else
        yeni = bas_konum - STRIDE;

    c = board[yeni];
    kuyruk_konum = govde[kuyruk];
    buyu = 0;
    if (c == YEM)
        buyu = 1;
    else if (c != BOS && yeni != kuyruk_konum) {
        oyun_sonu(BITTI);           /* duvar ya da gövde (kuyruğun ucu bu hamlede boşalır) */
        return;
    }

    if (!buyu) {                    /* uzamıyorsa kuyruk bir hücre çekilir */
        koy(kuyruk_konum, BOS);
        kuyruk++;
    }
    koy(bas_konum, GOVDE);
    bas++;
    govde[bas] = yeni;
    bas_konum = yeni;
    koy(yeni, BAS);

    if (buyu) {
        uzunluk++;
        skor_artir();
        if (uzunluk == UZUN_MAX) {
            oyun_sonu(KAZANDI);
            return;
        }
        if (++hiz_yem == HIZ_ADIM) {
            hiz_yem = 0;
            if (hiz > HIZ_MIN)
                hiz--;
        }
        /* Yeni yemin yeri hemen aranır ama ekrana sonraki karede yazılır: arama
         * yalnız RAM okur, ne kadar sürerse sürsün pencere kapanınca CPU'yu
         * bekletmez; pencereye düşmesi gereken tek iş o bir VRAM yazması. */
        yem_ara();
        yem_bekliyor = 1;
    }
}

/* Yön isteği: o anki yönün tersi yok sayılır. Bir hamle içinde birden çok tuş
 * gelirse sonuncusu geçerli olur; hepsi son hamlenin yönüne göre denetlendiği
 * için 180 derece dönüş olamaz. */
void yon_iste(unsigned char y)
{
    if ((y ^ 2) != yon)
        istek = y;
}

/* Klavyeden gelen bir byte. */
void tus(unsigned char k)
{
    if (k == K_BIRAK) {
        birak = 1;
        return;
    }
    if (k == K_ONEK)
        return;
    if (birak) {                    /* bırakılan tuşun kodu */
        birak = 0;
        return;
    }
    if (durum != OYNUYOR) {
        if (k == K_BOSLUK || k == K_ENTER)
            yeniden = 1;
        return;
    }
    switch (k) {
    case K_YUKARI: case K_W: yon_iste(YUKARI); break;
    case K_ASAGI:  case K_S: yon_iste(ASAGI);  break;
    case K_SOL:    case K_A: yon_iste(SOL);    break;
    case K_SAG:    case K_D: yon_iste(SAG);    break;
    }
}

/* Açılışta bir kez: gölgede duvarlar ve boş alan, ekranda başlık ve duvarlar.
 * VRAM'i crt0 boşlukla doldurdu. Önce yalnız RAM işi yapılır, sonra VRAM
 * yazmaları art arda gelir: pencere kapalıyken yazan CPU bekletildiği için
 * (SISTEM-PLANI 8.5) uzun bir RAM döngüsünün arasına serpiştirilmiş her VRAM
 * yazması bir kare kaybettirirdi. */
void ilk_kurulum(void)
{
    char *b;
    volatile char *v;
    char r, k;

    /* gölge: satır 1..29, sütun 0..39 (gerisi DIS = 0 kalır, .bss sıfır) */
    b = board + UST_DUVAR * STRIDE;
    for (r = UST_DUVAR; r <= ALT_DUVAR; r++) {
        for (k = 0; k < COLS; k++) {
            if (r == UST_DUVAR || r == ALT_DUVAR || k == SOL_DUVAR || k == SAG_DUVAR)
                b[k] = DUVAR;
            else
                b[k] = BOS;
        }
        b += STRIDE;
    }

    /* ekran */
    ekrana(BASLIK_SATIR * STRIDE + 1, "TD-8 YILAN OYUNU");
    ekrana(BASLIK_SATIR * STRIDE + SKOR_SUTUN - 5, "SKOR");
    v = VRAM + UST_DUVAR * STRIDE;
    for (k = 0; k < COLS; k++) {
        v[k] = DUVAR;
        v[(ALT_DUVAR - UST_DUVAR) * STRIDE + k] = DUVAR;
    }
    v = VRAM + ILK_SATIR * STRIDE;
    for (r = ILK_SATIR; r <= SON_SATIR; r++) {
        v[SOL_DUVAR] = DUVAR;
        v[SAG_DUVAR] = DUVAR;
        v += STRIDE;
    }
}

/* Biten oyunun izlerini sil: kutu, yılan, yem. Alanda başka dolu hücre yoktur;
 * bunlar silinince gölge yine tamamen BOS olur. Bütün alanı taramaktan hızlıdır
 * ve yazmalar art arda gelir. */
void alani_temizle(void)
{
    unsigned char k;

    for (k = 0; k < 5; k++)
        alana((KUTU_SATIR + k) * STRIDE + KUTU_SUTUN, "                    ");
    k = kuyruk;
    for (;;) {
        koy(govde[k], BOS);
        if (k == bas)
            break;
        k++;
    }
    koy(yem_konum, BOS);            /* kazanıldıysa yem zaten yenmişti: zararsız */
}

/* Yeni oyun: yılanı, skoru ve yemi koy. Alan boş olmalı. */
void yeni_oyun(void)
{
    char k;

    kuyruk = 0;
    bas = BAS_UZUN - 1;
    for (k = 0; k < BAS_UZUN; k++) {
        govde[k] = BAS_KONUM - (BAS_UZUN - 1) + k;
        koy(govde[k], GOVDE);
    }
    bas_konum = BAS_KONUM;
    koy(bas_konum, BAS);
    uzunluk = BAS_UZUN;
    yon = SAG;
    istek = SAG;
    hiz = HIZ_BAS;
    kare_say = 0;
    hiz_yem = 0;
    skor = 0;
    for (k = 0; k < 4; k++)
        skor_k[k] = '0';
    skor_yaz();
    LEDS = 0;
    durum = OYNUYOR;
    yem_ara();
    VRAM[yem_konum] = YEM;
    yem_bekliyor = 0;
    oyun_sayisi++;
}

/* Her karede bir kez (pencere açılırken). */
void kare(void)
{
    if (yeniden) {
        yeniden = 0;
        alani_temizle();
        yeni_oyun();
        return;
    }
    if (durum != OYNUYOR)
        return;
    if (yem_bekliyor) {             /* yem yiyen hamleden sonraki kare: yemi çiz */
        VRAM[yem_konum] = YEM;
        yem_bekliyor = 0;
    }
    if (++kare_say >= hiz) {
        kare_say = 0;
        hamle();
        hamle_sayisi++;
    }
}

int main(void)
{
    unsigned char s;

    ilk_kurulum();
    yeni_oyun();
    for (;;) {
        s = KSTAT;
        if (s & KRDY)
            tus(KBD);
        if (s & VWIN) {
            if (!pencere) {         /* pencere şimdi açıldı: yeni kare */
                pencere = 1;
                acik_tur = 0;
                kare();
            } else if (++acik_tur == VGA_YOK_TUR) {
                acik_tur = 0;       /* VGA yok: VWIN hep 1, kareyi turla say */
                kare();
            }
        } else
            pencere = 0;
    }
    return 0;
}
