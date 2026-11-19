"""M6 VGA ana netlist'te (cpu.py m6_vga, build(vga='netlist')): 19 entegre.

- Kart yapısı: VWR_s artık test tezgâhı girişi değil, M1 U111'de VWR'den iki MCLK ile
  senkronlanıyor; M6 ile CPU yalnız VWR, SLOW, AB0–10, DB, /VRAM_WE netlerini paylaşıyor.
- Görüntü: VRAM + font ROM'undan beklenen kare ile devrenin VIDEO çıkışı nokta nokta aynı.
- Bütün sistem: merhaba.asm, CPU + M6 (25 MHz) emülatörle sıfır fark; VRAM yazmaları yalnız
  M6'nın açtığı pencerede (satır 482–522); sonraki karede yazı ekranda.
"""
import unittest
from pathlib import Path

from ta8 import asm, vga
from ta8.hw import cpu, harness, screen, wiring
from ta8.hw.kernel import Sim

EXAMPLES = Path(__file__).resolve().parent.parent / 'examples'
LINE_NS = vga.H_TOTAL * 8 * 80            # 50 karakter × 8 nokta × 80 ns = 32 µs


class TestM6Board(unittest.TestCase):
    def test_modes(self):
        t = cpu.build()
        n = cpu.build(vga='netlist')
        self.assertNotIn('M6', t.modules())
        self.assertEqual(len(n.modules()['M6']), 19)
        self.assertNotIn('X1', [c.ref for c in n.chips])            # VRAM taklidi kalktı
        self.assertIs(n.memories['VRAM'], n.chip('U715'))
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
        rest |= set(b.inputs) | set(b.ties) | set(b.pulls) - {f'VD{i}' for i in range(8)}  # VD pull'ları M6'nın
        shared = {'VWR', 'SLOW', '/VRAM_WE'} | {f'AB{i}' for i in range(11)} | {f'DB{i}' for i in range(8)}
        self.assertEqual(m6 & rest - {'VCC', 'GND'}, shared)

    def test_counts(self):
        rows = wiring.count_rows(cpu.build(vga='netlist'))
        self.assertEqual([r for r in rows if r[5] != 0], [])
        m6 = [r for r in rows if r[0] == 'M6']
        self.assertEqual((sum(r[2] for r in m6), sum(r[3] for r in m6), sum(r[4] for r in m6)),
                         (19, 19, 0))


class TestM6Picture(unittest.TestCase):
    """Yalnız M6: VRAM'e yazı, iki kare, VIDEO çıkışı beklenen görüntüyle aynı (~7 s)."""

    @classmethod
    def setUpClass(cls):
        vram = bytearray(32768)
        for r, m in enumerate([b'MERHABA, TA-8!', b'M6 KARAKTER HATTI', bytes(range(0x20, 0x48))]):
            vram[64 * (2 + 2 * r) + 1:64 * (2 + 2 * r) + 1 + len(m)] = m
        for c in range(40):
            vram[c], vram[64 * 29 + c] = 0x01, 0xFF
        cls.vram, cls.font = bytes(vram), vga.test_font()
        sim = Sim(corner='typ')
        cpu.m6_vga(vram_data=cls.vram, font=cls.font).attach(sim)
        sim.set('/VRAM_WE', 1)
        sim.set_bus('AB', 11, 0)
        sim.set_bus('DB', 8, 0)
        cls.cap = screen.Capture(sim)
        sim.add_clock('OSC25', 20)
        sim.run_for(int(2.3 * vga.V_TOTAL * LINE_NS))
        cls.sim = sim

    def test_frame_size(self):
        self.assertEqual(len(self.cap.frames), 2)
        self.assertEqual({len(line) for line in self.cap.frames[1]}, {screen.DOTS})
        self.assertEqual(len(self.cap.frames[1]), screen.LINES)

    def test_pixels(self):
        self.assertEqual(screen.diff(self.cap.frames[1], screen.render(self.vram, self.font)), [])

    def test_no_floating_or_late_data(self):
        """VD pull-down'ları (bulgu) sayesinde yüzen giriş yok; yalnız açılışın ilk µs'si."""
        late = [v for v in self.sim.violations if v.time > 2000]
        self.assertEqual(late, [])


class TestM6System(unittest.TestCase):
    """CPU + M6 birlikte (yavaş: ~8 s)."""

    @classmethod
    def setUpClass(cls):
        prog = asm.assemble((EXAMPLES / 'merhaba.asm').read_text(encoding='utf-8'))
        cls.hw = harness.HwCpu(prog.image, vga='netlist')
        cls.cap = screen.Capture(cls.hw.sim)
        cls.hw.run(60_000)
        cls.hw.sim.run_for(int(1.2 * vga.V_TOTAL * LINE_NS))
        cls.emu = harness.emu_like(cls.hw, prog.image, 60_000)
        cls.diffs = harness.compare(cls.hw, cls.emu)

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

    def test_text_on_screen(self):
        """Yazmalardan sonraki kare VRAM'deki yazıyı gösteriyor; ilk kare boş."""
        want = screen.render(self.hw.vram(), vga.test_font())
        self.assertEqual(len(self.cap.frames), 2)
        self.assertEqual(screen.diff(self.cap.frames[1], want), [])
        self.assertEqual(sum(map(sum, self.cap.frames[0])), 0)
        self.assertGreater(sum(map(sum, self.cap.frames[1])), 0)

    def test_m6_violations_only_in_blanking(self):
        """M6 çiplerindeki ihlaller yalnız açılışta ya da görüntünün olmadığı satırlarda
        (VMUX penceresi: VD, DB'yi izler; 166 anlamsız yükler, çıkış BLANK_n = 0 ile kapalı)."""
        frame = vga.V_TOTAL * LINE_NS
        for v in self.hw.sim.violations:
            if v.ref.startswith('U7'):
                self.assertTrue(v.time < 2000 or (v.time % frame) / LINE_NS >= 480, v)


if __name__ == '__main__':
    unittest.main()
