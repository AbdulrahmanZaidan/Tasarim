"""ALU tabloları: iki nibble flash'ı birlikte her girişte referansla aynı mı?"""

import unittest

from td8 import alu, isa


class TestAlu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lo, cls.hi = alu.build_tables()

    def test_exhaustive(self):
        """25 işlem + POISON × 256 × 256 × C × Z: tüm girişler (~8 milyon)."""
        lo, hi, ref = self.lo, self.hi, alu.alu_ref
        lo_addr, hi_addr = alu.lo_addr, alu.hi_addr
        for op in range(32):
            for c in (0, 1):
                for z in (0, 1):
                    for a in range(256):
                        for b in range(256):
                            lv = lo[lo_addr(op, a, b, c)]
                            hv = hi[hi_addr(op, a, b, (lv >> 4) & 1, (lv >> 5) & 1, z)]
                            got = ((lv & 15) | (hv & 15) << 4, (hv >> 4) & 1,
                                   ((lv >> 6) & 1) | ((hv >> 5) & 1), (hv >> 6) & 1, hv >> 7)
                            want = ref(op, a, b, c, z)
                            if got != want:
                                name = isa.ALUOPS[op] if op < len(isa.ALUOPS) else 'POISON'
                                self.fail(f'{name} A={a:02X} B={b:02X} C={c} Z={z}: '
                                          f'tablo {got}, referans {want}')

    def test_known_values(self):
        def run(name, a, b=0, c=0, z=0):
            return alu.alu_tables(self.lo, self.hi, isa.ALUOP[name], a, b, c, z)
        # (sonuç, Z, C, N, V)
        self.assertEqual(run('ADD', 0x7F, 0x01), (0x80, 0, 0, 1, 1))
        self.assertEqual(run('ADD', 0xFF, 0x01), (0x00, 1, 1, 0, 0))
        self.assertEqual(run('SUB', 0x05, 0x07), (0xFE, 0, 0, 1, 0))     # borç: C = 0
        self.assertEqual(run('SUB', 0x07, 0x07), (0x00, 1, 1, 0, 0))     # eşit: Z = 1, C = 1
        self.assertEqual(run('SBC', 0x00, 0x00, c=1, z=0), (0x00, 0, 1, 0, 0))   # zincirli Z
        self.assertEqual(run('ROR', 0x01, c=1), (0x80, 0, 1, 1, 0))
        self.assertEqual(run('ASR', 0x81), (0xC0, 0, 1, 1, 0))
        self.assertEqual(run('NEG', 0x80), (0x80, 0, 0, 1, 1))
        self.assertEqual(run('NEG', 0x00), (0x00, 1, 1, 0, 0))
        self.assertEqual(run('SEX', 0x80), (0xFF, 0, 0, 1, 0))
        self.assertEqual(run('PASSB', 0, 0x40), (0x40, 0, 0, 0, 1))      # BIT: V = M6
        self.assertEqual(run('CLC', 0x00, c=1), (0x00, 1, 0, 0, 0))
        self.assertEqual(alu.alu_tables(self.lo, self.hi, 0x1F, 0x12, 0x34, 0, 0),
                         (0xA5, 1, 1, 1, 1))                              # POISON

    def test_upper_half_is_copy(self):
        self.assertEqual(self.lo[:0x10000], self.lo[0x10000:])
        self.assertEqual(self.hi[:0x10000], self.hi[0x10000:])


if __name__ == '__main__':
    unittest.main()
