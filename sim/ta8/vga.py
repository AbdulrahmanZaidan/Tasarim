"""VGA zamanlama ROM'u, font ROM'u ve karakter seviyesinde sayaç simülasyonu
(SISTEM-PLANI 8).

Zamanlama ROM'u adresi: A0–5 = H (karakter), A6–15 = V (satır), A16 = SLOW.
Font ROM'u adresi: A0–2 = font satırı (V3..V1), A3–10 = karakter kodu, A11–16 = bank.
Font byte'ında bit 7 en soldaki noktadır (74HC166'nın H girişi).
"""

import re

ROM_SIZE = 0x20000
H_TOTAL, V_TOTAL = 50, 525

# Bit numaraları
HSYNC_N, VSYNC_N, BLANK_N, BUFEN_N, HEND_N, VEND_N, VMUX, VWR = range(8)


def timing_word(h, v, slow):
    """Bir (H, V, SLOW) adresi için ROM byte'ı."""
    bits = {}
    bits[HSYNC_N] = 0 if 41 <= h <= 46 else 1
    bits[VSYNC_N] = 0 if 490 <= v <= 491 else 1
    bits[BLANK_N] = 1 if h <= 39 and v <= 479 else 0
    in_buf = (481, 10) <= (v, h) <= (523, 40)
    bits[BUFEN_N] = 0 if (slow or in_buf) else 1
    bits[HEND_N] = 0 if h >= 49 else 1
    bits[VEND_N] = 0 if (v == 524 and h == 49) or v >= 525 else 1
    bits[VMUX] = 1 if slow or 481 <= v <= 523 else 0
    bits[VWR] = 1 if slow or 482 <= v <= 522 else 0
    return sum(b << i for i, b in bits.items())


def timing_rom():
    rom = bytearray(ROM_SIZE)
    for addr in range(ROM_SIZE):
        rom[addr] = timing_word(addr & 63, (addr >> 6) & 1023, addr >> 16)
    return rom


def simulate(rom, h=0, v=0, slow=0, steps=2 * H_TOTAL * V_TOTAL):
    """Sayaçları karakter saati (CCLK) adımlarıyla çalıştırır.

    Her adımda (h, v, T1) verir. T1, bir önceki karakter sınırında yakalanan
    ROM çıkışıdır (o anda ekrana giden sync/blank).
    """
    t1 = 0xFF
    for _ in range(steps):
        out = rom[h | v << 6 | slow << 16]
        yield h, v, t1
        t1 = out
        hend = not (out >> HEND_N) & 1
        vend = not (out >> VEND_N) & 1
        if vend:
            v = 0                         # senkron temizleme, sayma izninden önce gelir
        elif hend:
            v = (v + 1) & 1023
        h = 0 if hend else (h + 1) & 63


def test_font():
    """Gerçek font gelene kadar test deseni.

    00 ve 20 boş, FF dolu kare, 01 çerçeve. Diğer kodlarda 1–6. satırlar kodun
    bit desenini gösterir; böylece her karakter ekranda ayırt edilebilir.
    """
    rom = bytearray(ROM_SIZE)
    for code in range(256):
        for row in range(8):
            if code in (0x00, 0x20):
                g = 0
            elif code == 0xFF:
                g = 0xFF
            elif code == 0x01:
                g = 0xFF if row in (0, 7) else 0x81
            else:
                g = code if 1 <= row <= 6 else 0
            rom[code << 3 | row] = g
    _fill_banks(rom)
    return rom


def font_from_c_header(text):
    """font8x8_basic.h biçimindeki (kamu malı) fontu ROM imajına çevirir.

    O dosyada her karakter 8 byte ve bit 0 en soldaki nokta; burada bit 7 en sol
    olduğu için bitler ters çevrilir. 128'den az karakter varsa kalanı boş kalır.
    """
    values = [int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]{2})\b', text)]
    if len(values) < 8 * 32:
        raise ValueError('font dosyasında yeterli veri yok')
    rom = bytearray(ROM_SIZE)
    for i in range(min(len(values) // 8, 256)):
        for row in range(8):
            b = values[i * 8 + row]
            rom[i << 3 | row] = int(f'{b:08b}'[::-1], 2)
    _fill_banks(rom)
    return rom


def _fill_banks(rom):
    for bank in range(1, ROM_SIZE // 0x800):
        rom[bank * 0x800:(bank + 1) * 0x800] = rom[:0x800]
