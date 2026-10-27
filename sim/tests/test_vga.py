"""VGA zamanlama ROM'u: periyotlar, sync genişlikleri, pencereler, toparlanma."""

import unittest

from td8 import vga


def bit(word, n):
    return (word >> n) & 1


class TestVgaTiming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = vga.timing_rom()

    def test_periods(self):
        seen = list(vga.simulate(self.rom, 0, 0, steps=3 * vga.H_TOTAL * vga.V_TOTAL))
        hs = [h for h, v, _ in seen]
        vs = [v for h, v, _ in seen]
        self.assertEqual(max(hs), 49)
        self.assertEqual(max(vs), 524)
        starts = [i for i, (h, v, _) in enumerate(seen) if h == 0 and v == 0]
        self.assertEqual(starts[1] - starts[0], 50 * 525)        # 400 nokta × 525 satır

    def test_sync_and_blank(self):
        rom = self.rom
        line = [rom[h | 100 << 6] for h in range(50)]
        self.assertEqual(sum(1 - bit(w, vga.HSYNC_N) for w in line), 6)     # 48 nokta
        self.assertEqual(sum(bit(w, vga.BLANK_N) for w in line), 40)        # 320 nokta
        vsync_lines = [v for v in range(525) if not bit(rom[0 | v << 6], vga.VSYNC_N)]
        self.assertEqual(vsync_lines, [490, 491])
        visible = sum(bit(rom[h | v << 6], vga.BLANK_N) for v in range(525) for h in range(50))
        self.assertEqual(visible, 40 * 480)

    def test_windows(self):
        rom = self.rom
        vmux = [v for v in range(525) if bit(rom[20 | v << 6], vga.VMUX)]
        vwr = [v for v in range(525) if bit(rom[20 | v << 6], vga.VWR)]
        self.assertEqual((vmux[0], vmux[-1]), (481, 523))
        self.assertEqual((vwr[0], vwr[-1], len(vwr)), (482, 522, 41))
        for v in range(525):
            for h in range(50):
                w = rom[h | v << 6]
                if not bit(w, vga.BUFEN_N):
                    self.assertTrue(bit(w, vga.VMUX), f'/BUFEN VMUX dışında: V{v} H{h}')
                if bit(w, vga.VWR):
                    self.assertFalse(bit(w, vga.BUFEN_N), f'VWR var ama tampon kapalı: V{v} H{h}')

    def test_slow_bank(self):
        rom = self.rom
        for v in (0, 100, 490, 524):
            for h in (0, 20, 44):
                fast, slow = rom[h | v << 6], rom[h | v << 6 | 1 << 16]
                self.assertEqual(slow & 0b00110111, fast & 0b00110111)    # sync, blank, sayaç
                self.assertTrue(bit(slow, vga.VMUX) and bit(slow, vga.VWR))
                self.assertFalse(bit(slow, vga.BUFEN_N))

    def test_recovers_from_any_state(self):
        for h0, v0 in [(63, 1023), (55, 600), (49, 524), (10, 530)]:
            seen = list(vga.simulate(self.rom, h0, v0, steps=2 * 50 * 525))
            first = next(i for i, (h, v, _) in enumerate(seen) if h == 0 and v == 0)
            self.assertLess(first, 50 * 525 + 64, (h0, v0))
            self.assertTrue(all(h <= 49 and v <= 524 for h, v, _ in seen[first:]))


class TestFont(unittest.TestCase):
    def test_c_header(self):
        rows = ', '.join(['0x01'] * 8)
        text = '\n'.join('{ %s },' % rows for _ in range(128))
        rom = vga.font_from_c_header(text)
        self.assertEqual(rom[0], 0x80)              # bit 0 (sol) -> bit 7
        self.assertEqual(rom[0x800], 0x80)          # bank 1 kopya


if __name__ == '__main__':
    unittest.main()
