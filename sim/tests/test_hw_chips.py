"""td8.hw: gecikmeli simülatör çekirdeği ve 74HC / bellek modelleri.

Çalıştırma (sim/ klasöründen):
    py -3 -m unittest tests.test_hw_chips -v
    py -3 -m tests.test_hw_chips --bench        hız ölçümü (test değil)
"""

import itertools
import random
import sys
import time
import unittest

from td8.hw import (CHIP_TYPES, DELAYS, LIMITS, CY62256, HC00, HC02, HC04, HC08, HC14, HC20,
                    HC32, HC74, HC138, HC139, HC153, HC157, HC161, HC163, HC164, HC166, HC175,
                    HC191, HC245, HC273, HC377, HC540, HC688, SST39SF010, Sim, bus_pins,
                    pin_table)
from td8.hw import chips as hwchips


def rig(cls, *args, init=None, corner='typ', **kw):
    """Çipin her pinini aynı adlı nete bağlar; 'in' pinlerini 0 (ya da init) sürer."""
    sim = Sim(corner=corner)
    chip = sim.add(cls('U1', {p: p for p in cls.DIRS}, *args, **kw))
    init = init or {}
    for p, d in cls.DIRS.items():
        if d == 'in':
            sim.set(p, init.get(p, 0))
    sim.run_for(200)
    return sim, chip


def put(sim, values, ns=100):
    for k, v in values.items():
        sim.set(k, v)
    sim.run_for(ns)


def tick(sim, cp='CP', ns=100):
    sim.set(cp, 1)
    sim.run_for(ns)
    sim.set(cp, 0)
    sim.run_for(ns)


class HwTest(unittest.TestCase):
    def clean(self, sim):
        self.assertEqual(sim.violations, [], sim.violations[:5])


# ============================================================================
# Kombinasyonel çipler
# ============================================================================
class TestGates(HwTest):
    def check(self, cls, fn):
        sim, _ = rig(cls)
        k = len(cls.UNITS[0][0])
        for bits in itertools.product((0, 1), repeat=k):
            for u, (ins, _) in enumerate(cls.UNITS):
                ub = bits[u % k:] + bits[:u % k]           # birimlere farklı girişler
                for p, b in zip(ins, ub):
                    sim.set(p, b)
            sim.run_for(50)
            for u, (ins, out) in enumerate(cls.UNITS):
                ub = bits[u % k:] + bits[:u % k]
                self.assertEqual(sim.get(out), fn(ub), f'{cls.KIND} {out} {ub}')
        self.clean(sim)

    def test_00(self):
        self.check(HC00, lambda b: 1 - (b[0] & b[1]))

    def test_02(self):
        self.check(HC02, lambda b: 1 - (b[0] | b[1]))

    def test_04(self):
        self.check(HC04, lambda b: 1 - b[0])

    def test_08(self):
        self.check(HC08, lambda b: b[0] & b[1])

    def test_14(self):
        self.check(HC14, lambda b: 1 - b[0])

    def test_20(self):
        self.check(HC20, lambda b: 1 - (b[0] & b[1] & b[2] & b[3]))

    def test_32(self):
        self.check(HC32, lambda b: b[0] | b[1])

    def test_gate_delay(self):
        for corner, col in (('typ', 0), ('max', 1)):
            sim, _ = rig(HC00, corner=corner)
            t0 = sim.now
            sim.set('1A', 1)
            sim.set('1B', 1)
            sim.run_for(100)
            self.assertEqual(sim.get('1Y'), 0)
            self.assertEqual(sim.last_change('1Y') - t0, DELAYS['74HC00']['tpd'][col])


class TestDecoders(HwTest):
    def test_138(self):
        sim, _ = rig(HC138)
        for e1, e2, e3 in itertools.product((0, 1), repeat=3):
            for a in range(8):
                put(sim, {'/E1': e1, '/E2': e2, 'E3': e3, 'A0': a & 1, 'A1': a >> 1 & 1,
                          'A2': a >> 2}, 60)
                en = e3 and not e1 and not e2
                want = 0xFF ^ (1 << a) if en else 0xFF
                self.assertEqual(sim.bus('/Y', 8), want, (e1, e2, e3, a))
        self.clean(sim)

    def test_138_ti_aliases(self):
        chip = HC138('U9', {'G1': 'VCC', '/G2A': 'x', '/G2B': 'GND', 'A0': 'GND', 'A1': 'GND',
                            'A2': 'GND'})
        self.assertEqual(chip.pins['E3'], 'VCC')
        self.assertEqual(chip.pins['/E1'], 'x')

    def test_139(self):
        sim, _ = rig(HC139)
        for e1, e2 in itertools.product((0, 1), repeat=2):
            for a in range(4):
                b = 3 - a
                put(sim, {'/1E': e1, '1A0': a & 1, '1A1': a >> 1,
                          '/2E': e2, '2A0': b & 1, '2A1': b >> 1}, 60)
                self.assertEqual(sim.bus('/1Y', 4), 0xF if e1 else 0xF ^ (1 << a))
                self.assertEqual(sim.bus('/2Y', 4), 0xF if e2 else 0xF ^ (1 << b))
        self.clean(sim)

    def test_153(self):
        sim, _ = rig(HC153)
        rng = random.Random(1)
        for _ in range(40):
            p1, p2 = rng.randrange(16), rng.randrange(16)
            e1, e2, sel = rng.randrange(2), rng.randrange(2), rng.randrange(4)
            vals = {'/1E': e1, '/2E': e2, 'S0': sel & 1, 'S1': sel >> 1}
            for i in range(4):
                vals[f'1I{i}'] = p1 >> i & 1
                vals[f'2I{i}'] = p2 >> i & 1
            put(sim, vals, 80)
            self.assertEqual(sim.get('1Y'), 0 if e1 else p1 >> sel & 1)
            self.assertEqual(sim.get('2Y'), 0 if e2 else p2 >> sel & 1)
        self.clean(sim)

    def test_157(self):
        sim, _ = rig(HC157)
        for i0, i1 in ((0x5, 0xA), (0xF, 0x0), (0x3, 0xC)):
            vals = {}
            for u in range(1, 5):
                vals[f'{u}I0'] = i0 >> (u - 1) & 1
                vals[f'{u}I1'] = i1 >> (u - 1) & 1
            put(sim, vals)
            for s, e in itertools.product((0, 1), repeat=2):
                put(sim, {'S': s, '/E': e}, 60)
                y = sum(sim.get(f'{u}Y') << (u - 1) for u in range(1, 5))
                self.assertEqual(y, 0 if e else (i1 if s else i0))
        self.clean(sim)

    def test_688(self):
        sim, _ = rig(HC688)
        rng = random.Random(2)
        cases = [(v, v) for v in (0, 0xFF, 0x5A)] + [(rng.randrange(256), rng.randrange(256))
                                                    for _ in range(60)]
        for p, q in cases:
            for g in (0, 1):
                vals = {'/G': g}
                for i in range(8):
                    vals[f'P{i}'] = p >> i & 1
                    vals[f'Q{i}'] = q >> i & 1
                put(sim, vals, 80)
                self.assertEqual(sim.get('/P=Q'), 0 if (g == 0 and p == q) else 1)
        self.clean(sim)


class TestBuffers(HwTest):
    def test_245_both_directions(self):
        sim, _ = rig(HC245, init={'/OE': 1, 'DIR': 1})
        self.assertIsNone(sim.bus('B', 8))
        sim.set_bus('A', 8, 0x5A)
        put(sim, {'/OE': 0})
        self.assertEqual(sim.bus('B', 8), 0x5A)
        sim.set_bus('A', 8, 0xC3)
        sim.run_for(50)
        self.assertEqual(sim.bus('B', 8), 0xC3)
        put(sim, {'/OE': 1})                              # önce kapat, sonra yönü çevir
        self.assertIsNone(sim.bus('B', 8))
        sim.set_bus('A', 8, None)
        sim.set_bus('B', 8, 0x81)
        put(sim, {'DIR': 0})
        put(sim, {'/OE': 0})
        self.assertEqual(sim.bus('A', 8), 0x81)
        put(sim, {'/OE': 1})
        self.assertIsNone(sim.bus('A', 8))
        self.clean(sim)

    def test_245_enable_timing(self):
        sim, _ = rig(HC245, init={'/OE': 1, 'DIR': 1}, corner='max')
        sim.set_bus('A', 8, 0xFF)
        sim.run_for(100)
        t0 = sim.now
        sim.set('/OE', 0)
        en = DELAYS['74HC245']['en'][1]
        sim.run_until(t0 + en - 1)
        self.assertIsNone(sim.get('B0'))
        sim.run_until(t0 + en)
        self.assertEqual(sim.bus('B', 8), 0xFF)

    def test_540(self):
        sim, _ = rig(HC540)
        sim.set_bus('A', 8, 0x0F)
        sim.run_for(100)
        self.assertEqual(sim.bus('/Y', 8), 0xF0)
        put(sim, {'/OE1': 1})
        self.assertIsNone(sim.bus('/Y', 8))
        put(sim, {'/OE1': 0, '/OE2': 1})
        self.assertIsNone(sim.bus('/Y', 8))
        put(sim, {'/OE2': 0})
        sim.set_bus('A', 8, 0xA5)
        sim.run_for(100)
        self.assertEqual(sim.bus('/Y', 8), 0x5A)
        self.clean(sim)


# ============================================================================
# Ardışıl çipler
# ============================================================================
class TestFlipFlops(HwTest):
    def test_74(self):
        sim, _ = rig(HC74)                                # /SD = /RD = 0
        self.assertEqual((sim.get('1Q'), sim.get('/1Q')), (1, 1))
        put(sim, {'/1SD': 1})                             # yalnız /RD aktif
        self.assertEqual((sim.get('1Q'), sim.get('/1Q')), (0, 1))
        put(sim, {'/1SD': 0, '/1RD': 1})                  # yalnız /SD aktif
        self.assertEqual((sim.get('1Q'), sim.get('/1Q')), (1, 0))
        put(sim, {'/1SD': 1, '1D': 0})
        tick(sim, '1CP')
        self.assertEqual((sim.get('1Q'), sim.get('/1Q')), (0, 1))
        put(sim, {'1D': 1})
        self.assertEqual(sim.get('1Q'), 0)                # saat yokken değişmez
        tick(sim, '1CP')
        self.assertEqual(sim.get('1Q'), 1)
        put(sim, {'/1RD': 0})                             # asenkron temizleme, saatsiz
        self.assertEqual(sim.get('1Q'), 0)
        put(sim, {'/1RD': 1, '/2RD': 1, '/2SD': 1, '2D': 1})
        tick(sim, '2CP')
        self.assertEqual((sim.get('2Q'), sim.get('1Q')), (1, 0))   # birimler bağımsız
        self.clean(sim)

    def test_74_unit_name_alias(self):
        chip = HC74('U5', {'1/RD': 'r'})
        self.assertEqual(chip.pins, {'/1RD': 'r'})

    def test_175(self):
        sim, _ = rig(HC175)
        self.assertEqual(sim.bus('Q', 4), 0)
        self.assertEqual(sim.bus('/Q', 4), 0xF)
        put(sim, {'/MR': 1})
        sim.set_bus('D', 4, 0b1010)
        sim.run_for(100)
        tick(sim)
        self.assertEqual(sim.bus('Q', 4), 0b1010)
        self.assertEqual(sim.bus('/Q', 4), 0b0101)
        put(sim, {'/MR': 0})
        self.assertEqual(sim.bus('Q', 4), 0)
        self.clean(sim)

    def test_273(self):
        sim, _ = rig(HC273)
        put(sim, {'/MR': 1})
        sim.set_bus('D', 8, 0x3C)
        sim.run_for(100)
        self.assertEqual(sim.bus('Q', 8), 0)
        tick(sim)
        self.assertEqual(sim.bus('Q', 8), 0x3C)
        put(sim, {'/MR': 0})                              # asenkron
        self.assertEqual(sim.bus('Q', 8), 0)
        self.clean(sim)

    def test_377(self):
        sim, _ = rig(HC377, init={'/E': 1})
        sim.set_bus('D', 8, 0x96)
        sim.run_for(100)
        tick(sim)
        self.assertEqual(sim.bus('Q', 8), 0)              # /E = 1: yüklemez
        put(sim, {'/E': 0})
        tick(sim)
        self.assertEqual(sim.bus('Q', 8), 0x96)
        put(sim, {'/E': 1})
        sim.set_bus('D', 8, 0x11)
        sim.run_for(100)
        tick(sim)
        self.assertEqual(sim.bus('Q', 8), 0x96)
        self.clean(sim)


class TestCounters(HwTest):
    def test_161(self):
        sim, _ = rig(HC161)
        self.assertEqual(sim.bus('Q', 4), 0)
        put(sim, {'/MR': 1, '/PE': 1, 'CEP': 1, 'CET': 1})
        for i in range(1, 17):
            tick(sim)
            self.assertEqual(sim.bus('Q', 4), i & 15)
            self.assertEqual(sim.get('TC'), int(i & 15 == 15))
        sim.set_bus('D', 4, 0xA)
        put(sim, {'/PE': 0})
        tick(sim)                                         # yükleme saymaya üstün
        self.assertEqual(sim.bus('Q', 4), 0xA)
        put(sim, {'/PE': 1, 'CEP': 0})
        tick(sim)
        self.assertEqual(sim.bus('Q', 4), 0xA)            # CEP = 0: tut
        put(sim, {'CEP': 1, 'CET': 0})
        tick(sim)
        self.assertEqual(sim.bus('Q', 4), 0xA)            # CET = 0: tut
        sim.set_bus('D', 4, 0xF)
        put(sim, {'/PE': 0})
        tick(sim)
        put(sim, {'/PE': 1})
        self.assertEqual(sim.get('TC'), 0)                # Q = 15 ama CET = 0
        put(sim, {'CET': 1})
        self.assertEqual(sim.get('TC'), 1)
        put(sim, {'/MR': 0})                              # asenkron, saatsiz
        self.assertEqual((sim.bus('Q', 4), sim.get('TC')), (0, 0))
        self.clean(sim)

    def test_163_sync_clear(self):
        sim, _ = rig(HC163, init={'/MR': 1, '/PE': 1, 'CEP': 1, 'CET': 1})
        for _ in range(5):
            tick(sim)
        self.assertEqual(sim.bus('Q', 4), 5)
        put(sim, {'/MR': 0})
        self.assertEqual(sim.bus('Q', 4), 5)              # saat gelmeden temizlenmez
        tick(sim)
        self.assertEqual(sim.bus('Q', 4), 0)
        self.clean(sim)

    def test_191(self):
        sim, _ = rig(HC191)                               # /PL = 0: Q = D = 0
        self.assertEqual(sim.bus('Q', 4), 0)
        sim.set_bus('D', 4, 9)
        sim.run_for(100)
        self.assertEqual(sim.bus('Q', 4), 9)              # asenkron, seviye duyarlı
        put(sim, {'/PL': 1})
        sim.set_bus('D', 4, 0)
        sim.run_for(100)
        self.assertEqual(sim.bus('Q', 4), 9)
        for want in (10, 11, 12, 13, 14, 15):
            tick(sim)
            self.assertEqual(sim.bus('Q', 4), want)
        self.assertEqual(sim.get('MAX/MIN'), 1)
        self.assertEqual(sim.get('/RC'), 0)               # CP düşük, /CE = 0, MAX
        sim.set('CP', 1)
        sim.run_for(100)                                  # 15 → 0
        self.assertEqual(sim.bus('Q', 4), 0)
        self.assertEqual(sim.get('/RC'), 1)
        put(sim, {'D/U': 1})                              # CP yüksekken yön değişir
        self.assertEqual(sim.get('MAX/MIN'), 1)           # aşağıda Q = 0
        put(sim, {'CP': 0})
        self.assertEqual(sim.get('/RC'), 0)
        for want in (15, 14, 13):
            tick(sim)
            self.assertEqual(sim.bus('Q', 4), want)
        sim.set('CP', 1)
        sim.run_for(100)                                  # 12
        put(sim, {'/CE': 1})                              # CP yüksekken durdur
        put(sim, {'CP': 0})
        for _ in range(3):
            tick(sim)
        self.assertEqual(sim.bus('Q', 4), 12)
        self.assertEqual(sim.get('MAX/MIN'), 0)
        self.clean(sim)

    def test_191_rules(self):
        sim, _ = rig(HC191, init={'/PL': 1})
        put(sim, {'D/U': 1})                              # CP = /CE = 0 iken D/U değişti
        put(sim, {'/CE': 1})                              # CP = 0 iken /CE yükseldi
        kinds = [v.kind for v in sim.violations]
        self.assertEqual(kinds, ['setup', 'setup'])
        self.assertIn('D/U', sim.violations[0].desc)
        self.assertIn('/CE', sim.violations[1].desc)

    def test_191_ti_aliases(self):
        chip = HC191('U3', {'/CTEN': 'a', '/LOAD': 'b', 'CLK': 'c', '/RCO': 'd', 'TC': 'e'})
        self.assertEqual(chip.pins, {'/CE': 'a', '/PL': 'b', 'CP': 'c', '/RC': 'd', 'MAX/MIN': 'e'})


class TestShiftRegisters(HwTest):
    def test_164(self):
        sim, _ = rig(HC164)
        put(sim, {'/MR': 1, 'DSB': 1})
        pattern = [1, 0, 1, 1, 0, 0, 1, 0]
        for b in pattern:
            put(sim, {'DSA': b})
            tick(sim)
        want = sum(b << (7 - i) for i, b in enumerate(pattern))   # ilk giren Q7'de
        self.assertEqual(sim.bus('Q', 8), want)
        put(sim, {'DSA': 1, 'DSB': 0})                    # DSA & DSB = 0
        tick(sim)
        self.assertEqual(sim.bus('Q', 8), (want << 1) & 0xFF)
        put(sim, {'/MR': 0})
        self.assertEqual(sim.bus('Q', 8), 0)
        self.clean(sim)

    def test_166(self):
        sim, _ = rig(HC166)
        sim.set_bus('D', 8, 0xB4)
        put(sim, {'/MR': 1})
        tick(sim)                                         # /PE = 0: yükle
        out = [sim.get('Q7')]
        put(sim, {'/PE': 1, 'DS': 0})
        for _ in range(7):
            tick(sim)
            out.append(sim.get('Q7'))
        self.assertEqual(out, [0xB4 >> (7 - i) & 1 for i in range(8)])   # D7 önce çıkar
        put(sim, {'/PE': 0})
        put(sim, {'CP': 1})                               # yeniden yükle: Q7 = 1
        put(sim, {'/CE': 1})                              # CP yüksekken kilitle
        put(sim, {'/PE': 1})
        put(sim, {'CP': 0})
        for _ in range(3):
            tick(sim)
        self.assertEqual(sim.get('Q7'), 1)                # kaymadı
        self.clean(sim)
        put(sim, {'/CE': 0})
        put(sim, {'/CE': 1})                              # CP düşükken /CE ↑: kural + kayma
        self.assertEqual(sim.get('Q7'), 0)                # 0xB4 << 1 → bit7 = 0
        self.assertEqual([v.kind for v in sim.violations], ['setup'])
        put(sim, {'/MR': 0})
        self.assertEqual(sim.get('Q7'), 0)


class TestMemories(HwTest):
    def test_flash_read_timing_and_hiz(self):
        rng = random.Random(3)
        data = bytes(rng.randrange(256) for _ in range(1 << 17))
        sim, flash = rig(SST39SF010, data, init={'/WE': 1}, corner='max')
        self.assertEqual(sim.bus('DQ', 8), data[0])
        for addr in (0x1234, 0x1ABCD, 0x0FFFF, 0x10000):
            old = sim.bus('DQ', 8)
            if data[addr] == old:
                continue
            t0 = sim.now
            sim.set_bus('A', 17, addr)
            sim.run_until(t0 + 69)
            self.assertEqual(sim.bus('DQ', 8), old)       # tAA = 70 ns dolmadı
            sim.run_until(t0 + 70)
            self.assertEqual(sim.bus('DQ', 8), data[addr])
            sim.run_for(100)
        t0 = sim.now
        sim.set('/OE', 1)
        sim.run_until(t0 + 24)
        self.assertEqual(sim.bus('DQ', 8), data[0x10000])
        sim.run_until(t0 + 25)                            # tOHZ = 25 ns
        self.assertIsNone(sim.bus('DQ', 8))
        sim.run_for(100)
        t0 = sim.now
        sim.set('/OE', 0)
        sim.run_until(t0 + 34)
        self.assertIsNone(sim.get('DQ0'))
        sim.run_until(t0 + 35)                            # tOE = 35 ns
        self.assertEqual(sim.bus('DQ', 8), data[0x10000])
        self.clean(sim)
        put(sim, {'/WE': 0})
        self.assertEqual([v.kind for v in sim.violations], ['yazma'])

    def test_flash_90_and_padding(self):
        sim, flash = rig(SST39SF010, b'\x12\x34', init={'/WE': 1}, speed=90)
        self.assertEqual(flash.dl['acc'], DELAYS['SST39SF010-90']['acc'][0])
        sim.set_bus('A', 17, 1)
        sim.run_for(200)
        self.assertEqual(sim.bus('DQ', 8), 0x34)
        sim.set_bus('A', 17, 5)
        sim.run_for(200)
        self.assertEqual(sim.bus('DQ', 8), 0xFF)          # silinmiş flash

    def sram(self, corner='typ'):
        return rig(CY62256, init={'/CE': 0, '/OE': 1, '/WE': 1}, corner=corner)

    def write(self, sim, addr, value, pulse=100):
        sim.set_bus('A', 15, addr)
        sim.set_bus('IO', 8, value)
        sim.run_for(100)
        put(sim, {'/WE': 0}, pulse)
        put(sim, {'/WE': 1}, 50)
        sim.set_bus('IO', 8, None)
        sim.run_for(50)

    def read(self, sim, addr):
        sim.set_bus('A', 15, addr)
        put(sim, {'/OE': 0}, 150)
        v = sim.bus('IO', 8)
        put(sim, {'/OE': 1}, 100)
        return v

    def test_sram_write_read(self):
        sim, ram = self.sram(corner='max')
        rng = random.Random(4)
        cells = {rng.randrange(1 << 15): rng.randrange(256) for _ in range(20)}
        for a, v in cells.items():
            self.write(sim, a, v)
        for a, v in cells.items():
            self.assertEqual(ram.data[a], v)
            self.assertEqual(self.read(sim, a), v)
        ram.data[0x0100] = 0x77                            # dışarıdan erişim
        self.assertEqual(self.read(sim, 0x0100), 0x77)
        self.assertIsNone(sim.bus('IO', 8))               # /OE = 1: yüksek empedans
        self.clean(sim)

    def test_sram_ce_controlled_write_and_we_hiz(self):
        sim, ram = self.sram()
        put(sim, {'/CE': 1})
        sim.set_bus('A', 15, 0x2222)
        sim.set_bus('IO', 8, 0x5C)
        put(sim, {'/WE': 0})
        self.assertEqual(ram.data[0x2222], 0)
        put(sim, {'/CE': 0})
        put(sim, {'/CE': 1})                              # yazma /CE ↑ ile biter
        self.assertEqual(ram.data[0x2222], 0x5C)
        sim.set_bus('IO', 8, None)
        put(sim, {'/WE': 1, '/CE': 0, '/OE': 0}, 150)
        self.assertEqual(sim.bus('IO', 8), 0x5C)
        put(sim, {'/WE': 0})                              # /WE düşük: çıkış kapanır
        self.assertIsNone(sim.bus('IO', 8))
        self.clean(sim)

    def test_sram_write_violations(self):
        sim, ram = self.sram()
        sim.set_bus('A', 15, 0x10)
        sim.set_bus('IO', 8, 0xAA)
        put(sim, {'/WE': 0})
        sim.set_bus('A', 15, 0x11)                        # yazma sırasında adres değişti
        sim.run_for(100)
        sim.set_bus('IO', 8, 0xAB)                        # veri kurulumu: 10 ns
        sim.run_for(10)
        put(sim, {'/WE': 1})
        descs = [v.desc for v in sim.violations]
        self.assertTrue(all(v.kind == 'yazma' for v in sim.violations))
        self.assertTrue(any('adres değişti' in d for d in descs), descs)
        self.assertTrue(any('tSD' in d for d in descs), descs)
        sim.violations.clear()
        put(sim, {'/WE': 0}, 20)                          # 20 ns darbe < tPWE
        put(sim, {'/WE': 1})
        self.assertTrue(any('darbesi' in v.desc for v in sim.violations), sim.violations)


# ============================================================================
# Çekirdek
# ============================================================================
class TestKernel(HwTest):
    def test_pull(self):
        sim = Sim()
        sim.add(HC04('U1', {'1A': 'X', **{f'{i}A': 'GND' for i in range(2, 7)}}))
        sim.pull('X', 1)
        sim.run_for(100)
        self.assertEqual((sim.get('X'), sim.get('U1.1Y')), (1, 0))
        put(sim, {'X': 0})
        self.assertEqual(sim.get('U1.1Y'), 1)
        put(sim, {'X': None})                             # bırakınca pull-up
        self.assertEqual((sim.get('X'), sim.get('U1.1Y')), (1, 0))
        self.clean(sim)

    def test_constants(self):
        sim = Sim()
        sim.run_for(1)
        self.assertEqual((sim.get('VCC'), sim.get('GND')), (1, 0))

    def two_inverters(self):
        sim = Sim()
        rest = {f'{i}A': 'GND' for i in range(2, 7)}
        sim.add(HC04('U1', {'1A': 'a', '1Y': 'Y', **rest}),
                HC04('U2', {'1A': 'b', '1Y': 'Y', **rest}))
        sim.set('a', 0)
        sim.set('b', 0)
        sim.run_for(100)
        return sim

    def test_conflict(self):
        sim = self.two_inverters()
        self.assertEqual(sim.get('Y'), 1)                 # ikisi de 1 sürüyor: sorun yok
        self.clean(sim)
        put(sim, {'b': 1})
        self.assertIsNone(sim.get('Y'))
        self.assertEqual(len(sim.violations), 1)
        v = sim.violations[0]
        self.assertEqual((v.kind, v.ref), ('cakisma', 'U1/U2'))
        put(sim, {'b': 0})
        self.assertEqual(sim.get('Y'), 1)
        self.assertIn('100 ns sürdü', sim.violations[0].desc)

    def test_conflict_external_drivers(self):
        sim = Sim()
        sim.set('N', 1, who='buton')
        sim.set('N', 0, who='arduino')
        sim.run_for(10)
        self.assertEqual([v.kind for v in sim.violations], ['cakisma'])
        self.assertIsNone(sim.get('N'))

    def test_same_time_handover_no_false_conflict(self):
        sim = Sim()
        sim.pull('BUS', 0)
        sim.set('BUS', 1, who='a')
        sim.run_for(50)
        t = sim.now + 10
        sim.set('BUS', 0, who='b', at=t)                  # b açılırken
        sim.set('BUS', None, who='a', at=t)               # a aynı anda kapanıyor
        sim.run_for(50)
        self.clean(sim)
        self.assertEqual(sim.get('BUS'), 0)
        sim.set('BUS', 1, who='a', at=sim.now + 10)       # örtüşen el değiştirme: 2 ns
        sim.set('BUS', None, who='b', at=sim.now + 12)
        sim.run_for(50)
        self.assertEqual([v.kind for v in sim.violations], ['cakisma'])
        self.assertIn('2 ns sürdü', sim.violations[0].desc)

    def test_same_time_handover_with_chips(self):
        # İki 540 aynı neti sürer, /OE1'leri tümleyen; 540'ta açma = kapama gecikmesi.
        for corner, col in (('typ', 0), ('max', 1)):
            d = DELAYS['74HC540']
            self.assertEqual(d['en'][col], d['dis'][col])
            sim = Sim(corner=corner)
            for ref, oe, a in (('U1', 'SEL', 'GND'), ('U2', '/SEL', 'VCC')):
                pins = {'/OE1': oe, '/OE2': 'GND', '/Y0': 'BUS', **bus_pins('A', 'x', 8)}
                pins['A0'] = a
                sim.add(HC540(ref, pins))
            sim.set_bus('x', 8, 0)
            for sel in (0, 1, 0, 1):
                sim.set('SEL', sel)
                sim.set('/SEL', 1 - sel)
                sim.run_for(100)
                self.assertEqual(sim.get('BUS'), 1 if sel == 0 else 0)
            self.clean(sim)

    def test_floating_input(self):
        sim = Sim()
        sim.add(HC04('U1', {'1A': 'X', **{f'{i}A': 'GND' for i in range(2, 7)}}))
        sim.set('X', 1)
        sim.run_for(100)
        self.clean(sim)
        put(sim, {'X': None})
        self.assertEqual(sim.get('U1.1Y'), 1)             # yüzen giriş 0 okunur
        self.assertEqual([(v.kind, v.ref) for v in sim.violations], [('yuzen', 'U1')])

    def test_never_driven_input(self):
        sim = Sim()
        sim.add(HC04('U1', {'1A': 'X', **{f'{i}A': 'GND' for i in range(2, 7)}}))
        sim.run_for(100)
        self.assertEqual([v.kind for v in sim.violations], ['yuzen'])

    def test_startup_order_no_false_float(self):
        # 245 kaynağından (273) önce eklenmiş ve açılışta açık: sahte 'yuzen' olmamalı.
        sim = Sim()
        sim.add(HC245('U1', {'DIR': 'VCC', '/OE': 'GND', **bus_pins('A', 'r', 8),
                             **bus_pins('B', 'b', 8)}),
                HC273('U2', {'/MR': 'GND', 'CP': 'GND', **{f'D{i}': 'GND' for i in range(8)},
                             **bus_pins('Q', 'r', 8)}))
        sim.run_for(200)
        self.assertEqual(sim.bus('b', 8), 0)
        self.clean(sim)

    def test_bidir_unconnected_source_floats(self):
        sim = Sim()
        sim.add(HC245('U1', {'DIR': 'VCC', '/OE': 'GND', **bus_pins('B', 'b', 8)}))
        sim.run_for(200)
        self.assertEqual(sim.bus('b', 8), 0)
        self.assertEqual({(v.kind, v.ref) for v in sim.violations}, {('yuzen', 'U1')})
        self.assertEqual(len(sim.violations), 8)

    def test_unconnected_input_rejected(self):
        sim = Sim()
        with self.assertRaises(ValueError) as cm:
            sim.add(HC00('U1', {'1A': 'a', '1B': 'b'}))
        self.assertIn('2A', str(cm.exception))
        with self.assertRaises(ValueError):
            HC00('U2', {'1C': 'a'})                       # bilinmeyen pin
        with self.assertRaises(ValueError):
            HC00('U3', {'VCC': 'VCC'})                    # güç pini bağlanmaz

    def ff(self, corner='typ', checks=True):
        sim = Sim(corner=corner, checks=checks)
        sim.add(HC273('U1', {'/MR': 'VCC', 'CP': 'CLK', **bus_pins('D', 'D', 8),
                             **bus_pins('Q', 'Q', 8)}))
        sim.set('CLK', 0)
        sim.set_bus('D', 8, 0)
        sim.run_for(200)
        return sim

    def test_setup_violation(self):
        sim = self.ff(corner='max')
        need = LIMITS['74HC273']['setup'][1]
        sim.set('D3', 1)
        sim.run_for(need - 5)
        sim.set('CLK', 1)
        sim.run_for(100)
        self.assertEqual([v.kind for v in sim.violations], ['setup'])
        self.assertIn('D3', sim.violations[0].desc)
        self.assertIn(f'{need - 5} ns', sim.violations[0].desc)

    def test_hold_violation(self):
        sim = self.ff(corner='max')
        hold = LIMITS['74HC273']['hold'][1]
        self.assertGreaterEqual(hold, 2)
        sim.set('CLK', 1)
        sim.run_for(hold - 1)                             # tutma süresi dolmadan değişti
        sim.set('D5', 1)
        sim.run_for(100)
        self.assertEqual([v.kind for v in sim.violations], ['hold'])
        self.assertEqual(sim.bus('Q', 8), 0)              # kenardaki eski veri alındı
        sim.set('CLK', 0)
        sim.run_for(100)
        sim.set('CLK', 1)                                 # aynı anda (sonraki delta) değişim
        sim.set('D6', 1)
        sim.run_for(100)
        self.assertEqual([v.kind for v in sim.violations], ['hold', 'hold'])

    def test_checks_off(self):
        sim = self.ff(checks=False)
        sim.set('D3', 1)
        sim.run_for(1)
        sim.set('CLK', 1)
        sim.set('D4', 1)
        sim.run_for(100)
        self.assertEqual(sim.violations, [])
        self.assertEqual(sim.bus('Q', 8), 0x08)

    def test_same_clock_shift_chain(self):
        # 4 flip-flop (iki 74HC74), hepsi aynı CLK: her kenarda veri bir kat ilerler.
        for corner in ('typ', 'max'):
            sim = Sim(corner=corner)
            stages = ['IN', 'S1', 'S2', 'S3', 'S4']
            for ref, k in (('U1', 0), ('U2', 2)):
                pins = {}
                for u in (1, 2):
                    pins.update({f'/{u}RD': 'VCC', f'/{u}SD': 'VCC', f'{u}CP': 'CLK',
                                 f'{u}D': stages[k + u - 1], f'{u}Q': stages[k + u]})
                sim.add(HC74(ref, pins))
            sim.set('CLK', 0)
            sim.set('IN', 0)
            sim.run_for(100)
            for _ in range(4):                            # temizle
                tick(sim, 'CLK', 200)
            pattern = [1, 0, 1, 1, 0, 0, 0, 0]
            hist = []
            for b in pattern:
                sim.set('IN', b)
                sim.run_for(200)
                tick(sim, 'CLK', 200)
                hist.append(b)
                want = [hist[-k] if len(hist) >= k else 0 for k in (1, 2, 3, 4)]
                self.assertEqual([sim.get(s) for s in stages[1:]], want)
            self.clean(sim)

    def test_watch_sees_pre_commit_values(self):
        sim = self.ff(corner='max')
        sim.set_bus('D', 8, 0x55)
        sim.run_for(100)
        seen = []
        sim.watch('CLK', lambda t, v: v and seen.append((t, sim.bus('Q', 8), sim.bus('D', 8))))
        qchg = []
        sim.watch('Q0', lambda t, v: qchg.append((t, v)))
        t0 = sim.now
        sim.set('CLK', 1)
        sim.run_for(100)
        self.assertEqual(seen, [(t0, 0x00, 0x55)])        # commit öncesi değer
        self.assertEqual(sim.bus('Q', 8), 0x55)
        self.assertEqual(qchg, [(t0 + DELAYS['74HC273']['cp_q'][1], 1)])
        self.assertEqual(sim.last_change('Q0'), t0 + DELAYS['74HC273']['cp_q'][1])
        self.clean(sim)

    def test_watch_can_drive_same_instant(self):
        sim = self.ff()
        sim.watch('CLK', lambda t, v: sim.set('D0', 1) if v else None)
        tick(sim, 'CLK')
        self.assertEqual(sim.bus('Q', 8), 0)              # kenarda D0 hâlâ 0'dı
        self.assertEqual([v.kind for v in sim.violations], ['hold'])

    def test_clock_and_stop(self):
        sim = Sim()
        edges = []
        sim.add_clock('MCLK', 125)
        sim.watch('MCLK', lambda t, v: edges.append((t, v)))
        sim.run_until(1000)
        self.assertEqual(edges[:4], [(0, 0), (125, 1), (250, 0), (375, 1)])
        self.assertEqual(len(edges), 9)
        sim.stop_clock('MCLK')
        level = sim.get('MCLK')
        sim.run_for(1000)
        self.assertEqual(len(edges), 9)
        self.assertEqual(sim.get('MCLK'), level)

    def test_power_up_random_is_seeded(self):
        vals = []
        for seed in (7, 7, 8):
            sim = Sim(power_up='random', seed=seed)
            pins = {'/E': 'VCC', 'CP': 'GND', **{f'D{i}': 'GND' for i in range(8)},
                    **bus_pins('Q', 'Q', 8)}
            sim.add(HC377('U1', pins), HC377('U2', {**pins, **bus_pins('Q', 'R', 8)}))
            sim.run_for(100)
            vals.append((sim.bus('Q', 8), sim.bus('R', 8)))
        self.assertEqual(vals[0], vals[1])
        self.assertNotEqual(vals[0], vals[2])

    def test_161_cascade_counts_0_to_255_and_wraps(self):
        sim = Sim(corner='max')
        common = {'/MR': '/RST', 'CP': 'CLK', '/PE': 'VCC', 'CEP': 'VCC',
                  **{f'D{i}': 'GND' for i in range(4)}}
        sim.add(HC161('U1', {**common, 'CET': 'VCC', 'TC': 'TC_lo', **bus_pins('Q', 'C', 4)}),
                HC161('U2', {**common, 'CET': 'TC_lo', **bus_pins('Q', 'C', 4, net_start=4)}))
        sim.set('/RST', 0)
        sim.add_clock('CLK', 250, start=0, offset=100)
        sim.run_for(100)
        sim.set('/RST', 1)
        self.assertEqual(sim.bus('C', 8), 0)
        counts = []
        sim.watch('CLK', lambda t, v: v == 0 and counts.append(sim.bus('C', 8)))
        sim.run_for(258 * 500)                            # her düşen kenarda oku
        self.assertEqual(counts, [(i + 1) & 0xFF for i in range(258)])   # 1..255, 0, 1, 2
        self.clean(sim)

    def test_191_pair_counts_down_and_up_from_ff(self):
        # SISTEM-PLANI 5.1 SP: alt /CE = NOT SPCNT; üst /CE = NAND(SPCNT, MAX/MIN_alt);
        # D/U = SPDN; D girişleri 1; /PL = /RESET → FF.
        sim = Sim(corner='max')
        rest = {f'{i}A': 'GND' for i in range(2, 7)}
        sim.add(HC04('U1', {'1A': 'SPCNT', '1Y': '/CE_lo', **rest}),
                HC00('U2', {'1A': 'SPCNT', '1B': 'MM_lo', '1Y': '/CE_hi',
                            **{p: 'GND' for p in ('2A', '2B', '3A', '3B', '4A', '4B')}}))
        for ref, ce, base, extra in (('U3', '/CE_lo', 0, {'MAX/MIN': 'MM_lo'}),
                                     ('U4', '/CE_hi', 4, {})):
            sim.add(HC191(ref, {'/PL': '/RESET', '/CE': ce, 'D/U': 'SPDN', 'CP': 'CLK',
                                **{f'D{i}': 'VCC' for i in range(4)},
                                **bus_pins('Q', 'SP', 4, net_start=base), **extra}))
        sim.set('CLK', 1)
        sim.set('SPCNT', 0)
        sim.set('SPDN', 1)
        sim.set('/RESET', 0)
        sim.run_for(500)
        self.assertEqual(sim.bus('SP', 8), 0xFF)
        sim.set('/RESET', 1)
        sim.set('SPCNT', 1)                               # CLK yüksekken (kural)
        sim.run_for(100)

        def cycle():
            sim.set('CLK', 0)
            sim.run_for(500)
            sim.set('CLK', 1)                             # commit
            sim.run_for(500)

        sp = 0xFF
        for _ in range(300):                              # FF'ten aşağı, 00'ı geçerek
            cycle()
            sp = (sp - 1) & 0xFF
            self.assertEqual(sim.bus('SP', 8), sp)
        sim.set('SPDN', 0)                                # CLK yüksekken yön değişir
        sim.run_for(100)
        for _ in range(300):
            cycle()
            sp = (sp + 1) & 0xFF
            self.assertEqual(sim.bus('SP', 8), sp)
        self.assertEqual(sp, 0xFF)
        sim.set('SPCNT', 0)                               # CLK yüksekken
        sim.run_for(100)
        cycle()
        self.assertEqual(sim.bus('SP', 8), 0xFF)
        self.clean(sim)


class TestTables(unittest.TestCase):
    def test_every_kind_from_plan_is_modelled(self):
        kinds = {'74HC00', '74HC02', '74HC04', '74HC08', '74HC14', '74HC20', '74HC32', '74HC74',
                 '74HC138', '74HC139', '74HC153', '74HC157', '74HC161', '74HC163', '74HC164',
                 '74HC166', '74HC175', '74HC191', '74HC245', '74HC273', '74HC377', '74HC540',
                 '74HC688', 'SST39SF010', 'CY62256'}
        self.assertEqual(set(CHIP_TYPES), kinds)

    def test_pinouts_consistent(self):
        for kind, cls in CHIP_TYPES.items():
            self.assertEqual(set(cls.PINOUT) - {'VCC', 'GND'}, set(cls.DIRS), kind)
            legs = list(cls.PINOUT.values())
            self.assertEqual(len(legs), len(set(legs)), kind)
            for p in cls.DIRS:
                self.assertTrue(not p.startswith('/') or len(p) > 1, (kind, p))

    def test_docstring_table_matches_code(self):
        self.assertIn(pin_table(), hwchips.__doc__)

    def test_delays_positive_and_sourced(self):
        for kind, paths in list(DELAYS.items()) + list(LIMITS.items()):
            for path, (typ, worst, src) in paths.items():
                self.assertLessEqual(typ, worst, (kind, path))
                self.assertIn(src, 'PT', (kind, path))
        for kind, paths in DELAYS.items():
            for path, (typ, worst, src) in paths.items():
                self.assertGreaterEqual(typ, 1, (kind, path))
        for kind, lim in LIMITS.items():
            if 'hold' in lim:
                self.assertLessEqual(lim['hold'][1], 5, kind)   # plan varsayımı ≤ 5 ns


# ============================================================================
# Hız ölçümü (test değil): py -3 -m tests.test_hw_chips --bench
# ============================================================================
def build_bench(groups=8, corner='max'):
    """~70 çipli, CPU benzeri etkinlikte bir devre (CPU'nun kendisi değil).

    MCLK 4 MHz, Johnson sayacıyla CLK = MCLK/4 (1 CPU çevrimi = 1000 ns). Her grupta:
    8-bit sayıcı (2× 161, CET/TC zinciri) → her çevrim yükleyen 377 → hep açık 245 → grup
    bus'ı → 688 karşılaştırıcı; ayrıca 138, 00, 32. Grup 0'ın bus'ı flash'ın, grup 1'inki
    SRAM'in adresini sürer; flash veri çıkışı ortak DB'yi sürer."""
    sim = Sim(corner=corner)
    sim.add_clock('MCLK', 125)
    sim.set('/RST', 0)
    sim.add(HC74('J1', {'/1RD': '/RST', '/1SD': 'VCC', '1CP': 'MCLK', '1D': '/Q2', '1Q': 'Q1',
                        '/2RD': '/RST', '/2SD': 'VCC', '2CP': 'MCLK', '2D': 'Q1', '2Q': 'CLK',
                        '/2Q': '/Q2'}))
    for g in range(groups):
        p = f'g{g}_'
        sim.add(HC161(f'{p}C0', {'/MR': '/RST', 'CP': 'CLK', '/PE': 'VCC', 'CEP': 'VCC',
                                 'CET': 'VCC', 'TC': f'{p}tc', **{f'D{i}': 'GND' for i in range(4)},
                                 **bus_pins('Q', f'{p}c', 4)}),
                HC161(f'{p}C1', {'/MR': '/RST', 'CP': 'CLK', '/PE': 'VCC', 'CEP': 'VCC',
                                 'CET': f'{p}tc', **{f'D{i}': 'GND' for i in range(4)},
                                 **bus_pins('Q', f'{p}c', 4, net_start=4)}),
                HC138(f'{p}D', {'A0': f'{p}c0', 'A1': f'{p}c1', 'A2': f'{p}c2', '/E1': 'GND',
                                '/E2': 'GND', 'E3': 'VCC', '/Y0': f'{p}y0'}),
                HC00(f'{p}N', {'1A': f'{p}c0', '1B': f'{p}c1', '2A': f'{p}y0', '2B': 'CLK',
                               **{x: 'GND' for x in ('3A', '3B', '4A', '4B')}}),
                HC377(f'{p}R', {'/E': 'GND', 'CP': 'CLK', **bus_pins('D', f'{p}c', 8),
                                **bus_pins('Q', f'{p}r', 8)}),
                HC245(f'{p}B', {'DIR': 'VCC', '/OE': 'GND', **bus_pins('A', f'{p}r', 8),
                                **bus_pins('B', f'{p}b', 8)}),
                HC688(f'{p}E', {'/G': 'GND', **bus_pins('P', f'{p}b', 8),
                                **bus_pins('Q', f'{p}c', 8)}),
                HC32(f'{p}O', {'1A': f'{p}c5', '1B': f'{p}c6', '2A': f'{p}b0', '2B': f'{p}c7',
                               **{x: 'GND' for x in ('3A', '3B', '4A', '4B')}}))
    sim.add(SST39SF010('ROM', {**bus_pins('A', 'g0_b', 8), **bus_pins('A', 'g2_b', 8, pin_start=8),
                               'A16': 'GND', '/CE': 'GND', '/OE': 'GND', '/WE': 'VCC',
                               **bus_pins('DQ', 'DB', 8)}, bytes(range(256)) * 512),
            CY62256('RAM', {**bus_pins('A', 'g1_b', 8), **bus_pins('A', 'g3_b', 7, pin_start=8),
                            '/CE': 'GND', '/OE': 'VCC', '/WE': 'VCC', **bus_pins('IO', 'DB', 8)}))
    return sim


def benchmark(groups=8, cpu_cycles=2000):
    sim = build_bench(groups)
    sim.run_for(300)
    sim.set('/RST', 1)
    n_chips = len(sim.chips)
    e0, t0 = sim.evals, time.perf_counter()
    sim.run_for(cpu_cycles * 1000)                        # 1 CPU çevrimi = 4 MCLK = 1000 ns
    dt = time.perf_counter() - t0
    evals = sim.evals - e0
    print(f'{n_chips} çip, {cpu_cycles} CPU çevrimi ({cpu_cycles * 4} MCLK periyodu) '
          f'{dt:.2f} s')
    print(f'  {evals} evaluate → {evals / dt:,.0f} değerlendirme/s, '
          f'{evals / cpu_cycles:.0f} değerlendirme/çevrim')
    print(f'  {cpu_cycles / dt:,.0f} CPU çevrimi/s; ihlal: {dict(sim.summary())}')


if __name__ == '__main__':
    if '--bench' in sys.argv:
        benchmark()
    else:
        unittest.main()
