"""M6 VGA zamanlaması ana netlist'te (cpu.py m6_vga, build(vga='netlist')).

- Kart yapısı: M6'nın 11 entegresi, VWR_s artık test tezgâhı girişi değil, M1 U111'de
  VWR'den iki MCLK ile senkronlanıyor; M6 ile CPU yalnız VWR ve SLOW netlerini paylaşıyor.
- Bütün sistem: merhaba.asm, CPU + gerçek M6 zamanlaması (25 MHz) ile emülatörle sıfır fark;
  VRAM yazmaları yalnız M6'nın açtığı pencerede (satır 482–522).
"""
import unittest
from pathlib import Path

from ta8 import asm, vga
from ta8.hw import cpu, harness, wiring

EXAMPLES = Path(__file__).resolve().parent.parent / 'examples'
LINE_NS = vga.H_TOTAL * 8 * 80            # 50 karakter × 8 nokta × 80 ns = 32 µs


class TestM6Board(unittest.TestCase):
    def test_modes(self):
        t = cpu.build()
        n = cpu.build(vga='netlist')
        self.assertNotIn('M6', t.modules())
        self.assertEqual(len(n.modules()['M6']), 11)
        self.assertIn('VWR_s', t.inputs)
        self.assertNotIn('VWR_s', n.inputs)
        self.assertEqual(n.clocks['OSC25'], 20)
        with self.assertRaises(ValueError):
            cpu.build(vga='yok')

    def test_vwr_synchronizer(self):
        u111 = cpu.build(vga='netlist').chip('U111')
        self.assertEqual((u111.pins['D2'], u111.pins['Q2'], u111.pins['D3'], u111.pins['Q3']),
                         ('VWR', 'VWR_S1', 'VWR_S1', 'VWR_s'))
        self.assertEqual(u111.pins['CP'], 'MCLK')
        self.assertEqual(cpu.build().chip('U111').pins['D2'], 'GND')

    def test_shared_nets(self):
        b = cpu.build(vga='netlist')
        m6 = {n for c in b.chips if c.module == 'M6' for n in c.pins.values()}
        rest = {n for c in b.chips if c.module != 'M6' for n in c.pins.values()}
        rest |= set(b.inputs) | set(b.ties) | set(b.pulls)
        self.assertEqual(m6 & rest - {'VCC', 'GND'}, {'VWR', 'SLOW'})

    def test_counts(self):
        rows = wiring.count_rows(cpu.build(vga='netlist'))
        self.assertEqual([r for r in rows if r[5] != 0], [])
        m6 = [r for r in rows if r[0] == 'M6']
        self.assertEqual((sum(r[2] for r in m6), sum(r[3] for r in m6), sum(r[4] for r in m6)),
                         (19, 11, 8))


class TestM6System(unittest.TestCase):
    """CPU + M6 zamanlaması birlikte (yavaş: ~4 s)."""

    @classmethod
    def setUpClass(cls):
        prog = asm.assemble((EXAMPLES / 'merhaba.asm').read_text(encoding='utf-8'))
        cls.hw, cls.emu, cls.diffs, _ = harness.run_and_compare(prog.image, max_cycles=60_000,
                                                                vga='netlist')

    def test_zero_diff(self):
        self.assertTrue(self.hw.halted)
        self.assertEqual(self.diffs, [])

    def test_text_in_vram(self):
        v = self.hw.vram()
        self.assertEqual(v[0x42:0x42 + 14], b'MERHABA, TA-8!')

    def test_writes_inside_window(self):
        """Her VRAM yazması VWR penceresinde (satır 482–522, açılışta kare 0'dan)."""
        self.assertEqual(self.hw.wait_errors, [])
        self.assertEqual(len(self.hw.vram_writes), 14)
        frame = vga.V_TOTAL * LINE_NS
        for _, _, t in self.hw.vram_writes:
            line = (t % frame) / LINE_NS
            self.assertGreaterEqual(line, 482, t)
            self.assertLess(line, 523, t)
        self.assertGreater(self.hw.stall_ns, 10_000_000)      # pencereyi ~15 ms bekledi


if __name__ == '__main__':
    unittest.main()
