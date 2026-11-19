/* fib.c: 16-bit Fibonacci sayıları F0..F24 (examples/fibonacci.asm'nin C karşılığı).
 * Sayılar sağa yaslı 5 hane yazılır; bölme/kalan runtime'a gider (__divmod16).
 * Sonuçlar ayrıca fib[] dizisinde kalır; LED'lere terim sayısı (25) yazılır.
 *
 *   py -3 -m tacc examples/fib.c -o build/fib_c.asm --run
 */
#include "hw.h"

unsigned fib[25];

void yaz(char satir, char sutun, const char *s)
{
    volatile char *v = VRAM + satir * STRIDE + sutun;
    while (*s)
        *v++ = *s++;
}

/* n'yi `genislik` haneye sağa yaslı yazar */
void sayi(char satir, char sutun, unsigned n, char genislik)
{
    volatile char *v = VRAM + satir * STRIDE + sutun + genislik;
    do {
        *--v = '0' + n % 10;
        n /= 10;
        genislik--;
    } while (n);
    while (genislik--)
        *--v = ' ';
}

int main(void)
{
    unsigned a = 0, b = 1, t;
    char n;

    yaz(0, 1, "FIBONACCI SAYILARI (C)");
    for (n = 0; n < 25; n++) {
        fib[n] = a;
        yaz(2 + n, 1, "F");
        sayi(2 + n, 2, n, 2);
        yaz(2 + n, 5, "=");
        sayi(2 + n, 7, a, 5);
        t = a + b;
        a = b;
        b = t;
    }
    LEDS = n;
    return 0;
}
