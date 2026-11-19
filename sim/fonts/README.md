# Fontlar

| Dosya | Kaynak | Lisans |
|---|---|---|
| `font8x8_basic.h` | Daniel Hepper, [github.com/dhepper/font8x8](https://github.com/dhepper/font8x8) (Marcel Sondaar ve IBM'in kamu malı VGA fontlarından). 19 Kasım 2026'da `master`'dan alındı, değiştirilmedi. | Kamu malı (public domain) |

U+0000–U+007F, karakter başına 8 byte, bit 0 en soldaki nokta. `ta8.vga.font_from_c_header()` bitleri ters çevirir (font ROM'unda bit 7 en sol, 74HC166'nın H girişi) ve 2 KB'ı 64 banka kopyalar.

Kullanım: `ta8.vga.default_font()` (font ROM'u imajı), `py cli.py roms` (build/font.bin), `cpu.m6_vga()` (varsayılan font). Test deseni için `vga.test_font()` ya da `py cli.py roms --test-font`.
