"""play.py: TD-8 programını terminalde gerçek zamanlı çalıştırır; klavyeyle oynanır.

    py -3 play.py examples/snake.c                  oyna: ok tuşları/WASD, Boşluk/Enter, Esc çıkış
    py -3 play.py examples/snake.c --speed 2        iki kat hızlı (0: olabildiğince hızlı)
    py -3 play.py examples/snake.c --demo           hazır tuş senaryosu, tuş beklemez
    py -3 play.py examples/snake.c --demo --frames 900 --speed 0
                                                    sonlu kip: 900 kare koşar, son ekranı basar
    py -3 play.py examples/merhaba.asm              .asm (ya da 32 KB .bin) de olur
    py -3 play.py examples/snake.c --micro          mikroadım emülatörü (MicroEmu)

Program C ise tdcc ile derlenir, .asm ise td8.asm ile çevrilir. Bus(vga_model=True):
VRAM penceresi ve kare zamanlaması (16.800 çevrim = 16,8 ms) açık; MicroEmu pencere
kapalıyken VRAM'e yazan CPU'yu bekletir, RefEmu bekletmez (varsayılan, daha hızlı).

Klavye (yalnız Windows konsolu, msvcrt): basılan tuş PS/2 set 2 scan code'una çevrilir
ve basma + bırakma kodu olarak (ör. sağ ok: E0 74 E0 F0 74) bus.press ile gönderilir.
Konsol yalnız basmayı bildirdiği için bırakma kodu hemen ardından gelir; tuşu basılı
tutmak konsolun otomatik tekrarıyla aynı tuşu tekrar tekrar basar.

Ekran ANSI kaçışlarıyla yerinde tazelenir (silmeden üzerine yazılır, titremez); altta
LED'ler, kare ve çevrim sayısı. Tam görünüm 35 satır ister; pencere kısaysa önce
bilgi/yardım satırları, sonra üst/alt çerçeve, en son durum satırı atlanır (en az 30
satır). Çıktı terminal değilse (yönlendirme, test) yalnız son ekran basılır.
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

from td8 import asm
from td8.bus import COLS, FRAME_CYCLES, Bus

# --- PS/2 set 2 ---------------------------------------------------------------

SET2 = {
    'a': 0x1C, 'b': 0x32, 'c': 0x21, 'd': 0x23, 'e': 0x24, 'f': 0x2B, 'g': 0x34,
    'h': 0x33, 'i': 0x43, 'j': 0x3B, 'k': 0x42, 'l': 0x4B, 'm': 0x3A, 'n': 0x31,
    'o': 0x44, 'p': 0x4D, 'q': 0x15, 'r': 0x2D, 's': 0x1B, 't': 0x2C, 'u': 0x3C,
    'v': 0x2A, 'w': 0x1D, 'x': 0x22, 'y': 0x35, 'z': 0x1A,
    '0': 0x45, '1': 0x16, '2': 0x1E, '3': 0x26, '4': 0x25, '5': 0x2E, '6': 0x36,
    '7': 0x3D, '8': 0x3E, '9': 0x46,
    ' ': 0x29, '\r': 0x5A, '\b': 0x66, '\t': 0x0D,
}
EXTENDED = {'yukari': 0x75, 'asagi': 0x72, 'sol': 0x6B, 'sag': 0x74}
# msvcrt: özel tuşlar '\x00' ya da '\xe0' ile, ardından bu karakter
MSVCRT_SPECIAL = {'H': 'yukari', 'P': 'asagi', 'K': 'sol', 'M': 'sag'}
KEY_NAMES = {'bosluk': ' ', 'enter': '\r'}


def scan_codes(key):
    """Tuş adı ya da karakteri -> basma + bırakma byte'ları (bilinmiyorsa None)."""
    if key in EXTENDED:
        c = EXTENDED[key]
        return (0xE0, c, 0xE0, 0xF0, c)
    key = KEY_NAMES.get(key, key)
    c = SET2.get(key.lower() if len(key) == 1 else key)
    if c is None:
        return None
    return (c, 0xF0, c)


# --- Hazır senaryo (--demo) ---------------------------------------------------
# (kare, tuş): o karenin başında basılır. snake.c için RefEmu'da, bu dosyadaki kare
# döngüsüyle ve tests/test_snake.py'deki modelin otomatik pilotuyla üretildi:
#   1. oyun: 6 yem (kare 64, 232, 552, 728, 1008, 1225; 5.'de hızlanır), sonra
#            duvara (kare 1233, skor 0006)
#   Boşluk -> 2. oyun: WASD ile 2 yem, sonra kendi gövdesine (kare 1557)
#   Enter  -> 3. oyun: 3 yem, duvara (kare 2137); sonra "OYUN BITTI"de kalır.
# Başka programlarda da çalışır (yalnız tuş basar). snake.c değişirse ya da --micro
# ile (açılış bekletmeleri kareleri kaydırır) yılan başka yerde ölebilir.
DEMO = [
    (9, 'yukari'), (16, 'sol'), (32, 'yukari'), (64, 'sol'), (184, 'yukari'), (232, 'sag'),
    (376, 'asagi'), (552, 'sag'), (632, 'yukari'), (728, 'sol'), (928, 'yukari'),
    (1008, 'sag'), (1057, 'asagi'), (1323, 'bosluk'), (1372, 's'), (1404, 'a'), (1500, 'w'),
    (1532, 'sag'), (1540, 'asagi'), (1548, 'sol'), (1647, 'enter'), (1649, 'asagi'),
    (1656, 'sol'), (1800, 'asagi'), (1856, 'sag'), (1944, 'yukari'), (1960, 'sag'),
    (1976, 'yukari'),
]


# --- Program yükleme ------------------------------------------------------------

def load(path):
    """(32 KB ROM imajı, semboller, açıklama). C, .asm ya da .bin."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == '.c':
        from tdcc import build, code_size
        res = build(p.read_text(encoding='utf-8'), str(p))
        prog = res.program
        info = (f'{p.name}: ROM {code_size(prog)} byte, RAM 8020-{res.ram_end - 1:04X} '
                f'({res.ram_end - 0x8020} byte)')
        return bytes(prog.image[:0x8000]), prog.symbols, info
    if ext == '.asm':
        prog = asm.assemble(p.read_text(encoding='utf-8'), filename=str(p))
        return bytes(prog.image[:0x8000]), prog.symbols, f'{p.name}: {sum(prog.used[:0x8000])} byte'
    data = p.read_bytes()
    if len(data) > 0x8000:
        raise ValueError(f'{p.name}: 32 KB\'tan büyük')
    return data, {}, f'{p.name}: {len(data)} byte'


# --- Terminal ---------------------------------------------------------------------

def enable_ansi():
    """Windows konsolunda ANSI kaçışlarını aç (ENABLE_VIRTUAL_TERMINAL_PROCESSING)."""
    if os.name != 'nt':
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            k32.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


class Keyboard:
    """msvcrt ile basılan tuşları okur. read(): scan code demetleri listesi ya da None (Esc)."""

    def __init__(self):
        try:
            import msvcrt
        except ImportError:
            msvcrt = None
        self.msvcrt = msvcrt

    @property
    def available(self):
        return self.msvcrt is not None

    def read(self):
        out = []
        m = self.msvcrt
        if m is None:
            return out
        while m.kbhit():
            ch = m.getwch()
            if ch in ('\x00', '\xe0'):
                name = MSVCRT_SPECIAL.get(m.getwch())
                codes = scan_codes(name) if name else None
            elif ch in ('\x1b', '\x03'):            # Esc, Ctrl+C
                return None
            else:
                codes = scan_codes(ch)
            if codes:
                out.append(codes)
        return out


def frame_text(bus, frame, cpu, speed_now, info, help_line, rows=None):
    """Ekran + durum satırları. rows verilirse terminale sığacak kadar kısaltılır:
    35 satır tam; < 35 bilgi/yardım satırları gider; < 33 üst/alt çerçeve de gider;
    < 31 yalnız 30 ekran satırı kalır."""
    leds = ''.join('*' if bus.leds >> (7 - i) & 1 else '.' for i in range(8))
    border = '+' + '-' * COLS + '+'
    screen = ['|' + row + '|' for row in bus.screen()]
    status = (f' LED {leds} (${bus.leds:02X})   kare {frame}   çevrim {cpu.cycles:,}'
              f' ({cpu.cycles / 1e6:.2f} sn @ 1 MHz)')
    if speed_now is not None:
        status += f'   x{speed_now:.2f}'
    if cpu.halted:
        status += '   HALT'
    extra = [' ' + info] + ([' ' + help_line] if help_line else [])
    full = [border] + screen + [border, status] + extra
    if rows is None or rows >= len(full):
        return full
    if rows >= len(screen) + 3:
        return [border] + screen + [border, status]
    if rows >= len(screen) + 1:
        return screen + [status]
    return screen


# --- Ana döngü ---------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(prog='play.py', description='TD-8 programını gerçek zamanlı çalıştırır')
    ap.add_argument('program', help='.c, .asm ya da 32 KB .bin')
    ap.add_argument('--speed', type=float, default=1.0,
                    help='hız çarpanı (1 = 1 MHz gerçek zaman, 0 = olabildiğince hızlı)')
    ap.add_argument('--demo', action='store_true', help='hazır tuş senaryosunu oynat')
    ap.add_argument('--frames', type=int, default=0, help='bu kadar kare sonra dur (0: sınırsız)')
    ap.add_argument('--micro', action='store_true', help='MicroEmu (mikroadım) kullan')
    args = ap.parse_args(argv)

    try:
        image, symbols, info = load(args.program)
    except Exception as e:                                  # derleme/çevirme hatası
        print(f'HATA: {e}', file=sys.stderr)
        return 1

    tty = sys.stdout.isatty()
    kbd = Keyboard()
    interactive = tty and sys.stdin.isatty() and kbd.available
    if not args.demo and not interactive and not args.frames:
        print('HATA: klavye okunamıyor (msvcrt yok ya da konsol değil); --demo ya da '
              '--frames N kullanın', file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(errors='replace')
    except (AttributeError, ValueError):
        pass

    bus = Bus(vga_model=True)
    bus.load(image)
    if args.micro:
        from td8.emu_micro import MicroEmu
        cpu = MicroEmu(bus)
    else:
        from td8.emu_ref import RefEmu
        cpu = RefEmu(bus)
    info += f' · {"MicroEmu" if args.micro else "RefEmu"}'
    if args.demo:
        help_line = 'DEMO: hazır tuş senaryosu' + (' · Esc: çıkış' if interactive else '')
    else:
        help_line = 'Ok tuşları / WASD: yön · Boşluk / Enter: yeniden · Esc: çıkış'

    demo = sorted(DEMO) if args.demo else []
    di = 0
    frame = 0
    last_vram = None
    shown_frame = -1
    speed_now = None
    t_start, c_start = time.perf_counter(), cpu.cycles
    t_rate, c_rate = t_start, cpu.cycles

    def render():
        # İmleç başa, satırların üzerine yaz (silmeden: titremez), satır sonlarını ve
        # alttan artanı temizle. Son satırdan sonra '\n' yok: tam sığan pencerede
        # kaydırma olmasın. 30 satırdan kısa pencerede ekran yine kayar.
        rows = shutil.get_terminal_size((80, 40)).lines
        lines = frame_text(bus, frame, cpu, speed_now, info, help_line, rows)
        sys.stdout.write('\x1b[H' + '\n'.join(l + '\x1b[K' for l in lines) + '\x1b[J')
        sys.stdout.flush()

    if tty:
        enable_ansi()
        sys.stdout.write('\x1b[2J\x1b[?25l')                # temizle, imleci gizle
    try:
        while True:
            # tuşlar: kullanıcıdan ya da senaryodan, karenin başında
            if interactive:
                keys = kbd.read()
                if keys is None:
                    break
                if not args.demo:
                    for codes in keys:
                        bus.press(*codes)
            while di < len(demo) and demo[di][0] <= frame:
                codes = scan_codes(demo[di][1])
                if codes:
                    bus.press(*codes)
                di += 1

            # bir kare koştur (kare sınırına kadar)
            if not cpu.halted:
                cpu.run((cpu.cycles // FRAME_CYCLES + 1) * FRAME_CYCLES)
                frame += 1

            # hız ölçümü ve gerçek zamana uyma
            now = time.perf_counter()
            if now - t_rate >= 0.5:
                speed_now = (cpu.cycles - c_rate) / 1e6 / (now - t_rate)
                t_rate, c_rate = now, cpu.cycles
            if args.speed > 0 and not cpu.halted:
                ahead = (cpu.cycles - c_start) / (1e6 * args.speed) - (now - t_start)
                if ahead > 0:
                    time.sleep(ahead)
                elif ahead < -0.25:                         # yetişemiyoruz: geride kalma
                    t_start, c_start = now, cpu.cycles

            # ekran: VRAM değiştiyse ya da durum satırı için ~10 Hz
            done = args.frames and frame >= args.frames
            if tty:
                vram = bytes(bus.vram)
                if vram != last_vram or frame - shown_frame >= 6 or done:
                    render()
                    last_vram, shown_frame = vram, frame
            if done:
                break
            if cpu.halted and not interactive:
                break
            if cpu.halted:
                time.sleep(0.02)                            # HALT: Esc'i bekle
    except KeyboardInterrupt:
        pass
    finally:
        if tty:
            if shown_frame != frame:
                render()                                    # çıkarken son durum
            sys.stdout.write('\x1b[?25h\n')                 # imleci geri getir
            sys.stdout.flush()
    if not tty:
        print('\n'.join(frame_text(bus, frame, cpu, None, info, help_line)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
