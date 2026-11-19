/* sayac.c: sayaç, switch ve 2-B dizi örneği.
 * 0..99 arasındaki sayıları sayar; her birini 3'e ve 5'e bölünebilmesine göre
 * sınıflar (FizzBuzz), sınıf sayılarını ekrana ve sonucu LED'lere yazar.
 * Bölme yerine sayaçlar kullanılır (döngüde * / % kullanmamak, plan 11.2).
 *
 *   py -3 -m tacc examples/sayac.c -o build/sayac_c.asm --run
 */
#include "hw.h"

const char *const adlar[4] = {"SAYI", "FIZZ", "BUZZ", "FIZZBUZZ"};
unsigned char tablo[10][10];        /* her sayının sınıfı: satır = onlar, sütun = birler */
int adet[4];

void yaz(char satir, char sutun, const char *s)
{
    volatile char *v = VRAM + satir * STRIDE + sutun;
    while (*s)
        *v++ = *s++;
}

void sayi2(char satir, char sutun, char n)     /* 0..99, iki hane */
{
    char onlar = 0;
    while (n >= 10) {
        n -= 10;
        onlar++;
    }
    VRAM[satir * STRIDE + sutun] = onlar ? '0' + onlar : ' ';
    VRAM[satir * STRIDE + sutun + 1] = '0' + n;
}

int main(void)
{
    char i, k3 = 0, k5 = 0, sinif, onlar = 0, birler = 0;

    for (i = 0; i < 100; i++) {
        sinif = (k3 == 0) | (k5 == 0) << 1;
        tablo[onlar][birler] = sinif;
        if (++birler == 10) {
            birler = 0;
            onlar++;
        }
        switch (sinif) {
        case 0:  adet[0]++; break;
        case 1:  adet[1]++; break;
        case 2:  adet[2]++; break;
        default: adet[3]++;
        }
        if (++k3 == 3) k3 = 0;
        if (++k5 == 5) k5 = 0;
    }
    for (i = 0; i < 4; i++) {
        yaz(1 + i, 1, adlar[i]);
        sayi2(1 + i, 11, adet[i]);
    }
    LEDS = adet[3] << 4 | adet[1];          /* 7 FIZZBUZZ, 27 FIZZ -> $7B */
    return 0;
}
