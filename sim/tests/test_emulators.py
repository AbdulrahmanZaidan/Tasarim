"""İki emülatörün karşılaştırması ve örnek programlar.

MicroEmu üretilen uROM ve ALU imajlarını çalıştırır, RefEmu komutların anlamını
doğrudan uygular. Her komuttan sonra durum ve çevrim sayısı aynı olmalı.
"""

import random
import unittest
from pathlib import Path

from td8 import alu, asm, isa, microcode
from td8.bus import Bus
from td8.emu_micro import MicroEmu
from td8.emu_ref import RefEmu

EXAMPLES = Path(__file__).resolve().parent.parent / 'examples'
ROMS = microcode.build()
ALU = alu.build_tables()


def machines(source, **bus_kw):
    prog = asm.assemble(source)
    out = []
    for cls in (MicroEmu, RefEmu):
        bus = Bus(**bus_kw)
        bus.load(prog.image)
        out.append(MicroEmu(bus, ROMS, ALU) if cls is MicroEmu else RefEmu(bus))
    return prog, out


def random_program(rng, n):
    """Rastgele ama sonlanan program: düz kod + ileri dallanmalar + CALL."""
    ram = lambda: f'${0x8000 + rng.randrange(48):04X}'
    lines = ['.org 0', 'LDX #$8000']
    for i in range(n):
        r = rng.random()
        if r < 0.40:
            name = rng.choice([m[0] for m in isa.M_GROUP])
            modes = ['abs', '(X)', '(X+)'] + ([] if name in ('STA', 'BIT') else ['#'])
            mode = rng.choice(modes)
            operand = {'#': f'#${rng.randrange(256):02X}', 'abs': ram(),
                       '(X)': '(X)', '(X+)': '(X+)'}[mode]
            ins = f'{name} {operand}'
        elif r < 0.60:
            ins = rng.choice(isa.U_GROUP)
        elif r < 0.68:
            ins = rng.choice([f'LDX #${0x8000 + rng.randrange(48):04X}', f'LDX {ram()}',
                              'INX', 'TAXL', 'TAXH'])
        elif r < 0.74:
            ins = f'{rng.choice(["INCW", "DECW"])} {ram()}'
        elif r < 0.82:
            ins = rng.choice(['PHA', 'PLA'])
        elif r < 0.94:
            ins = f'{rng.choice([b[0] for b in isa.BRANCHES])} L{i + 2}'
        elif r < 0.97:
            ins = 'CALL alt'
        else:
            ins = f'JMP L{i + 1}'
        lines.append(f'L{i}: {ins}')
    lines += [f'L{n}: HALT', f'L{n + 1}: HALT', 'alt: INC', '     RET']
    return '\n'.join(lines)


class TestEquivalence(unittest.TestCase):
    def test_random_programs(self):
        rng = random.Random(2026)
        for trial in range(150):
            src = random_program(rng, 60)
            _, (micro, ref) = machines(src)
            # RAM'e rastgele başlangıç verisi (iki makinede aynı)
            init = bytes(rng.randrange(256) for _ in range(64))
            micro.bus.load(init, 0x8000)
            ref.bus.load(init, 0x8000)
            for step_no in range(500):
                cm, cr = micro.instruction(), ref.instruction()
                where = f'deneme {trial}, komut {step_no}, PC={ref.pc:04X}'
                self.assertEqual(micro.state(), ref.state(), where)
                self.assertEqual(cm, cr, where + ' (çevrim)')
                self.assertEqual(micro.halted, ref.halted, where)
                if ref.halted:
                    break
            self.assertTrue(ref.halted, f'deneme {trial} bitmedi')
            self.assertEqual(micro.bus.mem, ref.bus.mem, f'deneme {trial}: bellek farklı')
            self.assertEqual(micro.bus.vram, ref.bus.vram, f'deneme {trial}: VRAM farklı')


class TestPrograms(unittest.TestCase):
    def run_both(self, src, **kw):
        prog, ms = machines(src, **kw)
        for m in ms:
            m.run(200_000)
            self.assertTrue(m.halted, type(m).__name__)
        return prog, ms

    def test_compare16(self):
        """16-bit işaretli/işaretsiz karşılaştırmanın 6 ilişkisi (zincirli Z)."""
        rng = random.Random(7)
        pairs = [(0, 0), (1, 0), (0, 1), (0x8000, 0x7FFF), (0x7FFF, 0x8000),
                 (0x0100, 0x00FF), (0x00FF, 0x0100), (0xFFFF, 0xFFFF)]
        pairs += [(rng.randrange(65536), rng.randrange(65536)) for _ in range(40)]
        tests = ['BEQ', 'BNE', 'BLT', 'BGE', 'BGT', 'BLE', 'BLO', 'BHS', 'BHI', 'BLS']
        for x, y in pairs:
            body = []
            for i, b in enumerate(tests):
                body += [f'        LDA #<{x}', f'        CMP #<{y}', f'        LDA #>{x}',
                         f'        CPC #>{y}', f'        LDA #0', f'        {b} t{i}',
                         f'        JMP s{i}', f't{i}:    LDA #1', f's{i}:    STA ${0x8000 + i:04X}']
            src = '        .org 0\n' + '\n'.join(body) + '\n        HALT\n'
            _, ms = self.run_both(src)
            sx = x - 65536 if x & 0x8000 else x
            sy = y - 65536 if y & 0x8000 else y
            want = [x == y, x != y, sx < sy, sx >= sy, sx > sy, sx <= sy,
                    x < y, x >= y, x > y, x <= y]
            for m in ms:
                got = [bool(m.bus.mem[0x8000 + i]) for i in range(len(tests))]
                self.assertEqual(got, want, f'x={x:04X} y={y:04X} {type(m).__name__}')

    def test_incw_decw_chained_z(self):
        src = """
                .org 0
                LDA #$FF
                STA $8000
                LDA #$00
                STA $8001
                INCW $8000          ; 00FF -> 0100: Z = 0
                BEQ hata
                LDA #$01
                STA $8002
                LDA #$00
                STA $8003
                DECW $8002          ; 0001 -> 0000: Z = 1
                BNE hata
                LDA #$AA
                STA $F800
                HALT
        hata:   LDA #$EE
                STA $F800
                HALT
        """
        _, ms = self.run_both(src)
        for m in ms:
            self.assertEqual(m.bus.leds, 0xAA)
            self.assertEqual(m.bus.mem[0x8000:0x8004], bytes([0x00, 0x01, 0x00, 0x00]))

    def test_call_ret_stack_jmpi(self):
        src = """
                .org 0
                CALL a1
                JMPI (tablo)
                HALT
        a1:     LDA #$11
                PHA
                CALL a2
                PLA
                RET
        a2:     LDA #$22
                RET
        hedef:  LDA #$5A
                STA $F800
                HALT
        tablo:  .word hedef
        """
        _, ms = self.run_both(src)
        for m in ms:
            self.assertEqual(m.bus.leds, 0x5A)
            self.assertEqual(m.sp, 0xFF)

    def test_examples(self):
        for name, check in [('merhaba.asm', lambda bus: bus.screen()[1][2:16] == 'MERHABA, TD-8!'),
                            ('klavye.asm', lambda bus: bus.screen()[0].startswith('1C F0 1C'))]:
            src = (EXAMPLES / name).read_text(encoding='utf-8')
            prog, ms = machines(src)
            for m in ms:
                m.bus.press(0x1C, 0xF0, 0x1C)
                m.run(20_000)
                self.assertTrue(check(m.bus), f'{name} {type(m).__name__}: {m.bus.screen()[:2]}')

    def test_vram_window_stall(self):
        """VGA modeli açıkken pencere dışındaki VRAM yazması bekler ama kaybolmaz."""
        src = (EXAMPLES / 'merhaba.asm').read_text(encoding='utf-8')
        prog = asm.assemble(src)
        bus = Bus(vga_model=True)
        bus.load(prog.image)
        cpu = MicroEmu(bus, ROMS, ALU)
        cpu.run(100_000)
        self.assertTrue(cpu.halted)
        self.assertEqual(bus.screen()[1][2:16], 'MERHABA, TD-8!')
        self.assertGreater(cpu.stall_cycles, 0)


if __name__ == '__main__':
    unittest.main()
