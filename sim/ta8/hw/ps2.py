"""PS/2 klavye test tezgâhı: KCLK ve KDATA'yı açık akaç sürer (M7 için).

    kb = ps2.Keyboard(sim)          # KCLK, KDATA netleri (pull-up M7'de)
    kb.press(0x1C, 0xF0, 0x1C)
    ... her µs civarında: kb.poll()  (HwCpu commit'te çağırır)

Cihaz kuralları (PS/2, cihazdan ana makineye):
- Göndermeden önce KCLK en az `idle_ns` (50 µs) kesintisiz yüksek olmalı; ana makine
  KCLK'ı düşük tutuyorsa (susturma) cihaz bekler, byte kaybolmaz.
- Çerçeve: start 0, 8 veri (LSB önce), tek eşlik, stop 1. Bit periyodu `bit_ns`
  (80 µs = 12.5 kHz); her bitte veri, saat yüksekken (önceki yükselişten 20 µs sonra)
  değişir, saat 40 µs düşük, 40 µs yüksek. 11. yükselişte çerçeve biter.
- Saat düşükken ana makine de çekiyorsa fark edilmez (açık akaç); çerçeve ortasında
  susturma (ana makinenin yarıda kesmesi) bu modelde yok: M7 yalnız çerçeve sonunda susturur.
"""

from collections import deque


def frame_bits(byte):
    data = [(byte >> i) & 1 for i in range(8)]
    parity = 1 - (sum(data) & 1)                   # tek eşlik
    return [0] + data + [parity, 1]


class Keyboard:
    def __init__(self, sim, clk='KCLK', data='KDATA', bit_ns=80_000, idle_ns=50_000, who='KBD'):
        self.sim, self.clk, self.data, self.who = sim, clk, data, who
        self.bit_ns, self.idle_ns = bit_ns, idle_ns
        self.queue = deque()
        self.busy_until = 0
        self.sent = []                             # (byte, çerçeve başlangıcı, bitiş)
        self.last_low = 0                          # KCLK'ın son düşük görüldüğü an
        sim.watch(clk, self._on_clk)

    def press(self, *codes):
        self.queue.extend(codes)

    def press_partial(self, byte, nbits):
        """Yarım çerçeve: yalnız ilk `nbits` biti gönderip susar (bağlantı kopması, gürültü).
        M7'nin zaman aşımı bunu atmalı."""
        self.queue.append((byte, nbits))

    def _on_clk(self, t, v):
        if v != 1:
            self.last_low = t

    def poll(self):
        """Boştaysa ve KCLK yeterince uzun yüksekse sıradaki byte'ın çerçevesini zamanlar."""
        sim = self.sim
        now = sim.now
        if not self.queue or now < self.busy_until:
            return False
        if sim.get(self.clk) != 1 or now - max(self.last_low, sim.last_change(self.clk) or 0) < self.idle_ns:
            return False
        item = self.queue.popleft()
        byte, nbits = item if isinstance(item, tuple) else (item, 11)
        t0 = now + 1000
        T = self.bit_ns
        for i, b in enumerate(frame_bits(byte)[:nbits]):
            tb = t0 + i * T
            sim.set(self.data, 0 if b == 0 else None, who=self.who, at=tb)
            sim.set(self.clk, 0, who=self.who, at=tb + T // 4)
            sim.set(self.clk, None, who=self.who, at=tb + 3 * T // 4)
        end = t0 + (nbits - 1) * T + 3 * T // 4
        sim.set(self.data, None, who=self.who, at=end + T // 4)
        self.busy_until = end + T // 4 + 1
        self.sent.append((byte, t0, end) if nbits == 11 else (byte, t0, end, nbits))
        return True
