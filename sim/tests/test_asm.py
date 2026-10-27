"""Assembler: kodlamalar, ifadeler, yönergeler ve hata mesajları."""

import unittest

from td8 import asm


def code(src):
    prog = asm.assemble(src)
    (start, length), = prog.ranges()
    return bytes(prog.image[start:start + length])


class TestAsm(unittest.TestCase):
    def test_encodings(self):
        self.assertEqual(code('LDA #$41'), bytes([0x40, 0x41]))
        self.assertEqual(code('STA $F000'), bytes([0x45, 0x00, 0xF0]))
        self.assertEqual(code('add (x+)'), bytes([0x4B]))
        self.assertEqual(code('LDX #$1234'), bytes([0x90, 0x34, 0x12]))
        self.assertEqual(code('JMPI ($8010)'), bytes([0xA5, 0x10, 0x80]))
        self.assertEqual(code('BHS $0100'), bytes([0xB2, 0x00, 0x01]))
        self.assertEqual(code('TST'), bytes([0x89]))

    def test_labels_and_expressions(self):
        src = """
        V = $F000
                .org $0010
        bas:    LDA #<(V + 64*2 + 5)
                LDA #>(V + 64*2 + 5)
                BEQ son
                LDA #'A'-10
        son:    .word bas, son
        """
        self.assertEqual(code(src), bytes([0x40, 0x85, 0x40, 0xF0, 0xB0, 0x19, 0x00,
                                           0x40, 55, 0x10, 0x00, 0x19, 0x00]))

    def test_data(self):
        self.assertEqual(code('.byte 1, $FF, "a;b", \',\''), bytes([1, 0xFF, 97, 59, 98, 44]))
        self.assertEqual(code('.asciz "OK"'), b'OK\x00')
        self.assertEqual(code('.res 3'), bytes(3))

    def test_errors(self):
        cases = {
            'STA #1': 'adresleme modunu desteklemiyor',
            'FOO': 'bilinmeyen komut',
            'JMP yok': 'tanımsız etiket',
            'LDA #300': 'aralık dışı',
            'a: NOP\na: NOP': 'iki kez',
        }
        for src, msg in cases.items():
            with self.assertRaises(asm.AsmError) as ctx:
                asm.assemble(src)
            self.assertIn(msg, str(ctx.exception), src)


if __name__ == '__main__':
    unittest.main()
