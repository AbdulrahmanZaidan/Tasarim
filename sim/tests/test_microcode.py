"""Mikrokod: kurallar, FETCH, tanımsız opcode'lar, çevrim sayıları."""

import unittest

from td8 import isa, microcode


class TestMicrocode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roms = microcode.build()

    def test_counts(self):
        self.assertEqual(len(isa.INSTRUCTIONS), 88)
        self.assertEqual(len(isa.MNEMONICS), 53)

    def test_fetch_everywhere(self):
        fetch = isa.step(isa.FETCH).word()
        for bank in (0, 1):
            for ir in range(256):
                for flags in range(16):
                    z, c, n, v = flags & 1, (flags >> 1) & 1, (flags >> 2) & 1, flags >> 3
                    self.assertEqual(microcode.word_at(self.roms, 0, ir, z, c, n, v, bank), fetch)

    def test_zero_word_is_nop(self):
        self.assertEqual(isa.step('-/-/-/-').word(), 0)

    def test_illegal_opcodes_halt(self):
        halt = isa.HALT | isa.MARK | isa.NEXT
        for ir in (0x02, 0x44, 0x6C, 0x8D, 0xFF):
            self.assertNotIn(ir, isa.INSTRUCTIONS)
            self.assertEqual(microcode.word_at(self.roms, 1, ir, 0, 0, 0, 0), halt)

    def test_every_path_ends_with_next(self):
        for ir in range(256):
            for flags in range(16):
                z, c, n, v = flags & 1, (flags >> 1) & 1, (flags >> 2) & 1, flags >> 3
                for st in range(1, 16):
                    if microcode.word_at(self.roms, st, ir, z, c, n, v) & isa.NEXT:
                        break
                else:
                    self.fail(f'{ir:02X}: NEXT yok')

    def test_cycle_table(self):
        """SISTEM-PLANI 6.2'deki çevrim sayıları."""
        expected = {
            ('LDA', '#'): 2, ('LDA', 'abs'): 4, ('LDA', '(X)'): 2, ('STA', '(X+)'): 2,
            ('STA', 'abs'): 4, ('ADD', 'abs'): 4, ('LDX', '#16'): 3, ('LDX', 'abs'): 5,
            ('INX', 'imp'): 2, ('INCW', 'abs'): 7, ('DECW', 'abs'): 7, ('PHA', 'imp'): 2,
            ('PLA', 'imp'): 3, ('JMP', 'abs'): 4, ('CALL', 'abs'): 5, ('RET', 'imp'): 5,
            ('JMPI', 'ind'): 7, ('NOP', 'imp'): 2, ('HALT', 'imp'): 2, ('INC', 'imp'): 2,
        }
        for key, cycles in expected.items():
            self.assertEqual(isa.INSTRUCTIONS[isa.BY_NAME[key]].cycles(), cycles, key)
        beq = isa.INSTRUCTIONS[isa.BY_NAME[('BEQ', 'abs')]]
        self.assertEqual((beq.cycles(True), beq.cycles(False)), (4, 3))

    def test_rules_catch_errors(self):
        bad = ['PC/MEM/-/- MEMW NEXT',          # MEMW + MEM kaynağı
               'PCLD PCINC NEXT',               # ikisi birden
               '-/-/A/- NEXT',                  # A yükleniyor, ALU işlemi yok
               'AR/MEM/ARL/- ARINC NEXT',       # yükleme + artırma
               'SPCNT SPDN NEXT']               # push'suz SPDN
        for text in bad:
            with self.assertRaises(microcode.MicrocodeError, msg=text):
                microcode.check_step(isa.step(text), 'test')

    def test_branch_conditions(self):
        """Bcc: koşul doğruysa 1. adım OP1, değilse PCINC."""
        op1 = isa.step(isa.OP1).word()
        for cc, (name, cond) in enumerate(isa.BRANCHES):
            for flags in range(16):
                z, c, n, v = flags & 1, (flags >> 1) & 1, (flags >> 2) & 1, flags >> 3
                w = microcode.word_at(self.roms, 1, 0xB0 + cc, z, c, n, v)
                self.assertEqual(w == op1, bool(cond(z, c, n, v)), (name, flags))


if __name__ == '__main__':
    unittest.main()
