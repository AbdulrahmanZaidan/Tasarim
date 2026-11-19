/* merhaba.c: ekranın 1. satırına, 2. sütundan başlayarak "MERHABA, TA-8!" yazar,
 * LED'lere 0x55 yazar ve durur (main dönünce crt0 HALT eder).
 * examples/merhaba.asm'nin C karşılığı: aynı yer, aynı metin.
 *
 *   py -3 -m tacc examples/merhaba.c -o build/merhaba_c.asm --run
 */
#include "hw.h"

void yaz(char satir, char sutun, const char *s)
{
    volatile char *v = VRAM + satir * STRIDE + sutun;
    while (*s)
        *v++ = *s++;
}

int main(void)
{
    yaz(1, 2, "MERHABA, TA-8!");
    LEDS = 0x55;
    return 0;
}
