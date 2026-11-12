/* hw.h: TD-8 donanım tanımları (SISTEM-PLANI 7.1, 7.3). tdcc ile kullanılır.
 *
 *   VRAM[64*satir + sutun] = 'A';   ekrana karakter (yalnız yazılır, okunamaz)
 *   LEDS = 0x55;                    8 LED
 *   if (KSTAT & KRDY) k = KBD;      klavye: byte hazır mı, scan code'u oku
 */
#ifndef TD8_HW_H
#define TD8_HW_H

#define VRAM    ((volatile char *)0xF000)   /* 30 satır x 64 (40 sütun görünür) */
#define LEDS    (*(volatile char *)0xF800)  /* yazma: 8 LED */
#define KBD     (*(volatile char *)0xF800)  /* okuma: PS/2 scan code byte'ı */
#define KSTAT   (*(volatile char *)0xF801)  /* okuma: durum */

#define KRDY    0x80    /* KSTAT b7: klavye byte'ı hazır */
#define VWIN    0x40    /* KSTAT b6: VRAM yazma penceresi açık */
#define DIPSW   0x3F    /* KSTAT b5..b0: DIP anahtarlar */

#define COLS    40
#define ROWS    30
#define STRIDE  64

#define NULL    ((void *)0)

#endif
