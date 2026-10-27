"""Bellek ve I/O modeli (SISTEM-PLANI 7).

0000–7FFF ROM (yazma etkisiz), 8000–EFFF RAM, F000–F7FF VRAM (yalnız yazılır),
F800–FFFF I/O (A2..A0 çözülür, her 8 byte'ta tekrarlanır).
"""

from collections import deque

ROM_END = 0x8000
VRAM_BASE = 0xF000
IO_BASE = 0xF800
COLS, ROWS, STRIDE = 40, 30, 64

# VGA penceresi (25.000 MHz osilatör, 1 MHz CPU): satır 32 µs, kare 525 satır
LINE_CYCLES = 32
FRAME_CYCLES = 525 * LINE_CYCLES          # 16.800 çevrim = 16,8 ms
VWR_START = 482 * LINE_CYCLES             # VWR: satır 482–522
VWR_END = 523 * LINE_CYCLES


class Bus:
    def __init__(self, vga_model=False):
        self.mem = bytearray(0x10000)     # ROM + RAM (F000 üstü kullanılmaz)
        self.vram = bytearray(0x800)
        self.leds = 0
        self.dip = 0                      # KSTAT b5..b0
        self.vga_model = vga_model        # False: pencere hep açık
        self.cycle = 0
        self.krdy = 0
        self.kbd_byte = 0
        self.kbd_queue = deque()
        self.kbd_gap = 1100               # byte'lar arası çevrim (~11 bit, ~10 kHz)
        self._kbd_timer = 0

    # --- yükleme ---------------------------------------------------------
    def load(self, image, start=0):
        """İmajı belleğe koyar (ROM bölgesi dahil)."""
        self.mem[start:start + len(image)] = image

    # --- klavye ----------------------------------------------------------
    def press(self, *codes):
        """Klavyeden scan code byte'ları gönderir (set 2)."""
        if not self.kbd_queue and not self.krdy:
            self._kbd_timer = self.kbd_gap
        self.kbd_queue.extend(codes)

    # --- zaman -----------------------------------------------------------
    def tick(self, n=1):
        self.cycle += n
        if not self.krdy and self.kbd_queue:
            self._kbd_timer -= n
            if self._kbd_timer <= 0:
                self.kbd_byte = self.kbd_queue.popleft()
                self.krdy = 1

    def vwr(self):
        """VRAM yazma penceresi açık mı (KSTAT b6)."""
        if not self.vga_model:
            return 1
        return int(VWR_START <= self.cycle % FRAME_CYCLES < VWR_END)

    def cycles_until_window(self):
        if self.vwr():
            return 0
        pos = self.cycle % FRAME_CYCLES
        return (VWR_START - pos) % FRAME_CYCLES

    # --- erişim ----------------------------------------------------------
    def read(self, addr):
        if addr < VRAM_BASE:
            return self.mem[addr]
        if addr < IO_BASE:
            return 0                      # VRAM okunamaz; DB pull-down'ları 00
        reg = addr & 7
        if reg == 0:                      # KBD
            if self.krdy:
                self.krdy = 0
                self._kbd_timer = self.kbd_gap
                return self.kbd_byte
            return 0xFF                   # yaklaşık: boş kaydırma registerı (tersleyen 540)
        if reg == 1:                      # KSTAT
            return self.krdy << 7 | self.vwr() << 6 | (self.dip & 0x3F)
        return 0

    def write(self, addr, value):
        if addr < ROM_END:
            return                        # ROM /WE bağlı değil
        if addr < VRAM_BASE:
            self.mem[addr] = value
        elif addr < IO_BASE:
            self.vram[addr & 0x7FF] = value
        else:
            self.leds = value

    def screen(self):
        """VRAM'in görünen 40×30 bölümü, satır satır metin."""
        lines = []
        for row in range(ROWS):
            chunk = self.vram[row * STRIDE:row * STRIDE + COLS]
            lines.append(''.join(chr(b) if 32 <= b < 127 else '.' if b else ' ' for b in chunk))
        return lines
