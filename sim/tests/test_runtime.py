"""lib/runtime.asm: çarpma, bölme ve yazdırma rutinleri, örnek programlar.

Rutinler RefEmu'da çok sayıda girişle Python'un sonucuyla karşılaştırılır.
Bir alt kümede MicroEmu da çalıştırılır: sonuç ve çevrim sayısı aynı olmalı.
"""

import random
import unittest
from pathlib import Path

from td8 import alu, asm, microcode
from td8.bus import Bus
from td8.emu_micro import MicroEmu
from td8.emu_ref import RefEmu

SIM = Path(__file__).resolve().parent.parent
EXAMPLES = SIM / 'examples'
ROMS = microcode.build()
ALU = alu.build_tables()


def harness(routine):
    prog = asm.assemble(f'.org 0\nCALL {routine}\nHALT\n.include "lib/runtime.asm"', base=str(SIM))
    return prog, prog.symbols


def call(prog, params, micro=False, x=0xF000):
    """Parametreleri RAM'e yazar, rutini çalıştırır; (bus, cpu) döndürür."""
    bus = Bus()
    bus.load(prog.image)
    for addr, value, size in params:
        bus.mem[addr:addr + size] = value.to_bytes(size, 'little')
    cpu = MicroEmu(bus, ROMS, ALU) if micro else RefEmu(bus)
    cpu.x = x
    cpu.run(100_000)
    assert cpu.halted
    return bus, cpu


def word(bus, addr):
    return bus.mem[addr] | bus.mem[addr + 1] << 8


class TestMul(unittest.TestCase):
    def test_mul16(self):
        prog, s = harness('__mul16')
        rng = random.Random(11)
        pairs = [(0, 0), (0, 65535), (65535, 0), (1, 1), (65535, 65535), (255, 255),
                 (256, 256), (300, 218), (0x8000, 2), (12345, 3)]
        pairs += [(rng.randrange(65536), rng.randrange(65536)) for _ in range(300)]
        pairs += [(rng.randrange(65536), rng.randrange(256)) for _ in range(100)]
        for i, (a, b) in enumerate(pairs):
            params = [(s['__mul_a'], a, 2), (s['__mul_b'], b, 2)]
            bus, ref = call(prog, params)
            self.assertEqual(word(bus, s['__rv']), a * b & 0xFFFF, f'{a} * {b}')
            if i < 30:
                bus_m, micro = call(prog, params, micro=True)
                self.assertEqual(word(bus_m, s['__rv']), a * b & 0xFFFF, f'{a} * {b} (Micro)')
                self.assertEqual(micro.cycles, ref.cycles, f'{a} * {b} çevrim')


class TestDivmod(unittest.TestCase):
    def test_divmod16(self):
        prog, s = harness('__divmod16')
        rng = random.Random(12)
        pairs = [(0, 1), (1, 1), (65535, 1), (65535, 65535), (65534, 65535), (1000, 7),
                 (65535, 0x8000), (65535, 0x8001), (0xFFFE, 0xFFFF), (50000, 255), (7, 1000)]
        pairs += [(rng.randrange(65536), rng.randrange(1, 65536)) for _ in range(300)]
        pairs += [(rng.randrange(65536), rng.randrange(1, 256)) for _ in range(100)]
        for i, (n, d) in enumerate(pairs):
            params = [(s['__div_n'], n, 2), (s['__div_d'], d, 2)]
            bus, ref = call(prog, params)
            got = (word(bus, s['__rv']), word(bus, s['__div_r']))
            self.assertEqual(got, divmod(n, d), f'{n} / {d}')
            if i < 30:
                bus_m, micro = call(prog, params, micro=True)
                self.assertEqual((word(bus_m, s['__rv']), word(bus_m, s['__div_r'])),
                                 divmod(n, d), f'{n} / {d} (Micro)')
                self.assertEqual(micro.cycles, ref.cycles, f'{n} / {d} çevrim')

    def test_divide_by_zero(self):
        """Bölen 0: bölüm FFFF, kalan bölünen (makine durmaz, kilitlenmez)."""
        prog, s = harness('__divmod16')
        for n in (0, 1, 1234, 65535):
            bus, _ = call(prog, [(s['__div_n'], n, 2), (s['__div_d'], 0, 2)])
            self.assertEqual((word(bus, s['__rv']), word(bus, s['__div_r'])), (0xFFFF, n))


class TestPrint(unittest.TestCase):
    def test_print_u16(self):
        prog, s = harness('print_u16')
        rng = random.Random(13)
        values = [0, 5, 9, 10, 99, 100, 1000, 9999, 10000, 10001, 65535]
        values += [rng.randrange(65536) for _ in range(100)]
        for v in values:
            for pad in (0, 1):
                bus, _ = call(prog, [(s['__pr_v'], v, 2), (s['__pr_pad'], pad, 1)])
                text = bus.screen()[0].rstrip() if not pad else bus.screen()[0][:5]
                want = f'{v:>5}' if pad else str(v)
                self.assertEqual(text, want, f'v={v} pad={pad}')


def run_example(name, micro=False, cycles=10_000_000):
    path = EXAMPLES / name
    prog = asm.assemble(path.read_text(encoding='utf-8'), filename=str(path))
    bus = Bus()
    bus.load(prog.image)
    cpu = MicroEmu(bus, ROMS, ALU) if micro else RefEmu(bus)
    cpu.run(cycles)
    return bus, cpu


class TestExamples(unittest.TestCase):
    def test_fibonacci(self):
        fib = [0, 1]
        while len(fib) < 25:
            fib.append(fib[-1] + fib[-2])
        for micro in (False, True):
            bus, cpu = run_example('fibonacci.asm', micro)
            self.assertTrue(cpu.halted)
            rows = bus.screen()
            self.assertEqual(rows[0].strip(), 'FIBONACCI SAYILARI (16-BIT)')
            for n, f in enumerate(fib):
                self.assertEqual(rows[2 + n][1:].rstrip(), f'F{n:<3}= {f:>5}', f'F{n}')

    def test_asal(self):
        primes = [p for p in range(2, 1000) if all(p % d for d in range(2, int(p ** .5) + 1))]
        bus, cpu = run_example('asal.asm')
        self.assertTrue(cpu.halted)
        rows = bus.screen()
        got = [int(t) for row in rows[2:23] for t in row.split()]
        self.assertEqual(got, primes)
        self.assertEqual(rows[24].strip(), f'TOPLAM ASAL SAYISI: {len(primes)}')
        self.assertEqual(bus.leds, len(primes))


if __name__ == '__main__':
    unittest.main()
