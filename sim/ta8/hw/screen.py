"""M6'nın görüntü çıkışını yakalama ve beklenen görüntüyle karşılaştırma.

    cap = screen.Capture(sim)          # DCLK, VIDEO, BLANK_n, /VSYNC izlenir
    sim.run_for(...)
    frame = cap.frames[-1]             # [satır][nokta] = 0/1 (480 × 320, BLANK_n = 1 iken)
    want = screen.render(vram, font)   # VRAM + font ROM'undan beklenen görüntü
    screen.write_png(frame, 'ekran.png', scale=2)

Bir nokta = DCLK periyodu (80 ns) = ekranda iki VGA pikseli; 40 × 8 = 320 nokta, 480 satır.
Değerler DCLK ↑ anında okunur: VIDEO (U719) ve BLANK_n (T1) ikisi de DCLK ile değişen
registerlardan geldiği için o anda bir önceki noktanın kararlı değeri görülür.
"""

import struct
import zlib

COLS, ROWS = 40, 30
DOTS = COLS * 8
LINES = 480


class Capture:
    def __init__(self, sim, video='VIDEO', blank='BLANK_n', dclk='DCLK', vsync='/VSYNC'):
        self.sim = sim
        self.video, self.blank = video, blank
        self.frames = []                  # tamamlanmış kareler (VSYNC ile ayrılır)
        self.lines = []
        self.cur = []
        self.prev_blank = 0
        sim.watch(dclk, self._on_dclk)
        sim.watch(vsync, self._on_vsync)

    def _on_dclk(self, t, v):
        if v != 1:
            return
        b = self.sim.get(self.blank) or 0
        if b:
            self.cur.append(self.sim.get(self.video) or 0)
        elif self.prev_blank:
            self.lines.append(self.cur)
            self.cur = []
        self.prev_blank = b

    def _on_vsync(self, t, v):
        if v == 0:
            if self.lines:
                self.frames.append(self.lines)
            self.lines = []


def render(vram, font):
    """Beklenen görüntü: satır y, nokta x → font[kod·8 + (y/2 mod 8)] bit (7 − x mod 8),
    kod = vram[64·(y/16) + x/8] (SISTEM-PLANI 7.1, 8.3)."""
    out = []
    for y in range(LINES):
        row = []
        for x in range(DOTS):
            code = vram[64 * (y // 16) + x // 8]
            g = font[code << 3 | (y >> 1) & 7]
            row.append(g >> (7 - x % 8) & 1)
        out.append(row)
    return out


def diff(frame, want):
    """[(satır, nokta, görülen, beklenen)]; boyut farkı da satır olarak raporlanır."""
    out = []
    if len(frame) != len(want):
        out.append(('satır sayısı', len(frame), len(want), None))
    for y, (a, b) in enumerate(zip(frame, want)):
        if len(a) != len(b):
            out.append((y, 'nokta sayısı', len(a), len(b)))
            continue
        out += [(y, x, p, q) for x, (p, q) in enumerate(zip(a, b)) if p != q]
    return out


def write_png(frame, path, scale=2, fg=(80, 255, 120), bg=(8, 12, 10)):
    """Kareyi PNG olarak yazar (yatayda nokta başına 2 piksel: VGA'daki gibi 640 genişlik)."""
    w = len(frame[0]) * 2 * scale
    h = len(frame) * scale
    raw = bytearray()
    for row in frame:
        line = bytearray()
        for p in row:
            line += bytes(fg if p else bg) * (2 * scale)
        for _ in range(scale):
            raw += b'\x00' + line

    def chunk(kind, data):
        c = kind + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)
    return path
