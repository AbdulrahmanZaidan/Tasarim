"""M7 PS/2 klavye ana netlist'te (cpu.py m7_ps2, build(kbd='netlist')): 6 entegre + ayrık.

- Yalnız M7: PS/2 çerçeveleri (ps2.Keyboard, KCLK/KDATA açık akaç) → KRDY, 540'tan doğru
  byte, hazır byte varken KCLK susturuluyor, okuma (KCLR) sonrası bırakılıyor; yarım çerçeve
  zaman aşımıyla atılıyor; zamanlama ihlali yok.
- CPU + M7: klavye.asm, emülatörle sıfır fark (emülatör KRDY'yi devreden oynatır).
- CPU + M6 + M7 birlikte kuruluyor ve çalışıyor.
"""
import unittest
from pathlib import Path

from ta8 import asm
from ta8.hw import cpu, harness, ps2, wiring
from ta8.hw.kernel import Sim

EXAMPLES = Path(__file__).resolve().parent.parent / 'examples'


def program(name):
    return asm.assemble((EXAMPLES / f'{name}.asm').read_text(encoding='utf-8'))


class TestM7Board(unittest.TestCase):
    def test_modes(self):
        t, n = cpu.build(), cpu.build(kbd='netlist')
        self.assertNotIn('M7', t.modules())
        self.assertEqual(len(n.modules()['M7']), 10)               # 6 entegre + 4 ayrık
        self.assertNotIn('X2', [c.ref for c in n.chips])
        self.assertIn('KRDY', t.inputs)
        self.assertNotIn('KRDY', n.inputs)
        with self.assertRaises(ValueError):
            cpu.build(kbd='yok')

    def test_shared_nets(self):
        b = cpu.build(kbd='netlist')
        m7 = {n for c in b.chips if c.module == 'M7' for n in c.pins.values()}
        rest = {n for c in b.chips if c.module != 'M7' for n in c.pins.values()}
        rest |= set(b.inputs) | set(b.ties) | {n for n in b.pulls if not n.startswith('K')}
        self.assertEqual(m7 & rest - {'VCC', 'GND'},
                         {'/KBD_RD', '/RESET_s', 'CLK_IO', 'KRDY'} | {f'DB{i}' for i in range(8)})

    def test_counts(self):
        rows = wiring.count_rows(cpu.build(vga='netlist', kbd='netlist'))
        self.assertEqual([r for r in rows if r[5] != 0], [])
        m7 = [r for r in rows if r[0] == 'M7']
        self.assertEqual((sum(r[2] for r in m7), sum(r[3] for r in m7)), (6, 6))

    def test_frame_bits(self):
        self.assertEqual(ps2.frame_bits(0x1C), [0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 1])
        self.assertEqual(ps2.frame_bits(0x00)[9], 1)               # tek eşlik


class TestM7Alone(unittest.TestCase):
    """Yalnız M7, CLK_IO 1 MHz; okuma CPU gibi: /KBD_RD bir CLK_IO kenarını kapsar, DB o
    kenardan hemen önce okunur."""

    def setUp(self):
        sim = Sim(corner='typ')
        cpu.m7_ps2().attach(sim)
        for i in range(8):
            sim.pull(f'DB{i}', 0)
        sim.set('/KBD_RD', 1)
        sim.set('/RESET_s', 0)
        sim.add_clock('CLK_IO', 500, start=0)
        self.sim, self.kb = sim, ps2.Keyboard(sim)
        sim.run_for(5000)
        sim.set('/RESET_s', 1)

    def step(self, ns):
        end = self.sim.now + ns
        while self.sim.now < end:
            self.kb.poll()
            self.sim.run_for(1000)

    def wait_krdy(self, limit=3_000_000):
        t = self.sim.now
        while not self.sim.get('KRDY') and self.sim.now - t < limit:
            self.step(1000)
        return self.sim.get('KRDY')

    def read(self):
        """CPU okuması: CLK_IO düşükken /KBD_RD indir, yükselişten 20 ns önce DB'yi oku."""
        sim = self.sim
        t = sim.now
        rise = ((t - 500) // 1000 + 1) * 1000 + 500     # CLK_IO: 0'dan başlar, yükseliş 500 + 1000k
        sim.run_until(rise - 400)
        sim.set('/KBD_RD', 0)
        sim.run_until(rise - 20)
        b = sim.bus('DB', 8)
        sim.run_until(rise + 300)
        sim.set('/KBD_RD', 1)
        self.step(3000)
        return b

    def test_bytes_inhibit_and_clear(self):
        keys = [0x1C, 0xF0, 0x1C, 0xAA, 0x00, 0xFF]
        self.kb.press(*keys)
        got = []
        for _ in keys:
            self.assertEqual(self.wait_krdy(), 1)
            self.step(250_000)                          # CPU geç okuyor: byte korunmalı
            self.assertEqual(self.sim.get('KCLK'), 0)   # susturma
            got.append(self.read())
            self.assertEqual(self.sim.get('KRDY'), 0)   # KCLR temizledi
            self.assertEqual(self.sim.get('KCLK'), 1)   # bırakıldı
        self.assertEqual(got, keys)
        self.assertEqual(self.sim.violations, [])

    def test_timeout_drops_partial_frame(self):
        """Yarım çerçeveden ≥ 200 µs sonra gelen byte doğru (zaman aşımı 190 µs'de temizler)."""
        self.kb.idle_ns = 300_000
        self.kb.press_partial(0x55, 6)                  # 6 bit, sonra sessizlik
        self.kb.press(0x1C)
        self.assertEqual(self.wait_krdy(), 1)
        self.assertEqual(self.read(), 0x1C)
        self.assertEqual(len(self.kb.sent), 2)
        self.assertEqual(self.sim.violations, [])

    def test_finding_fast_frame_after_partial_corrupts(self):
        """BULGU (19 Kasım): PS/2 cihazı 50 µs boşluktan sonra gönderebilir; zaman aşımı 190 µs.
        Yarım çerçeveden < 190 µs sonra başlayan byte bozulur. Bu test sınırlamayı belgeler;
        RC kısaltılırsa (ör. 22k / 4.7 nF ≈ 90 µs) bu testin beklentisi değişmeli."""
        self.kb.idle_ns = 50_000
        self.kb.press_partial(0x55, 6)
        self.kb.press(0x1C)
        self.wait_krdy()
        self.assertNotEqual(self.read(), 0x1C)

    def test_partial_frame_without_timeout_would_corrupt(self):
        """Kontrol: zaman aşımı devre dışıyken (RC çıkışı 0'a zorlanır) yarım çerçeve sonraki
        byte'ı bozar; yani test gerçekten zaman aşımını ölçüyor."""
        self.sim.set('KTO_RC', 0, who='ZORLA')
        self.kb.idle_ns = 300_000
        self.kb.press_partial(0x55, 6)
        self.kb.press(0x1C)
        self.wait_krdy()
        self.assertNotEqual(self.read(), 0x1C)


class TestM7System(unittest.TestCase):
    def test_klavye_zero_diff(self):
        keys = (0x1C, 0xF0, 0x1C, 0x29, 0x5A)
        prog = program('klavye')
        hw = harness.HwCpu(prog.image, keys=keys, kbd='netlist')
        hw.run(7000)
        emu = harness.emu_like(hw, prog.image, hw.n, keys)
        self.assertEqual(harness.compare(hw, emu), [])
        self.assertEqual(hw.vram()[:15], b'1C F0 1C 29 5A ')
        self.assertEqual(hw.leds(), 0x5A)
        rises = [i for i, v in enumerate(hw.krdy_seq) if v and not hw.krdy_seq[i - 1]]
        self.assertEqual(len(rises), 5)
        self.assertEqual([v for v in hw.sim.violations if v.ref.startswith(('U8', 'D8', 'Q8', 'RC8'))], [])

    def test_with_m6(self):
        """Bütün sistem: CPU + M6 (VGA) + M7 (PS/2). Yazmalar pencereyi bekler (~8 s)."""
        keys = (0x1C, 0x29)
        prog = program('klavye')
        hw = harness.HwCpu(prog.image, keys=keys, kbd='netlist', vga='netlist')
        self.assertEqual(len(hw.board.modules()['M6']), 19)
        hw.run(3000)
        emu = harness.emu_like(hw, prog.image, hw.n, keys)
        self.assertEqual(harness.compare(hw, emu), [])
        self.assertEqual(hw.vram()[:6], b'1C 29 ')


if __name__ == '__main__':
    unittest.main()
