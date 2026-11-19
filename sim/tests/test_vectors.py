"""Intel HEX, test vektörü üreticileri ve iz karşılaştırması (ta8/ihex.py, ta8/vectors.py)."""

import contextlib
import io
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cli
from ta8 import asm, ihex, isa, vectors
from ta8.bus import IO_BASE, ROM_END, VRAM_BASE, Bus
from ta8.emu_micro import MicroEmu

EXAMPLES = Path(__file__).resolve().parent.parent / 'examples'
MERHABA = EXAMPLES / 'merhaba.asm'


def merhaba_image():
    return asm.assemble(MERHABA.read_text(encoding='utf-8')).image


def run_cli(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        cli.main(list(argv))
    return out.getvalue()


# ---------------------------------------------------------------------------
# Intel HEX
# ---------------------------------------------------------------------------

class IntelHexTest(unittest.TestCase):
    def test_roundtrip_128k(self):
        data = random.Random(5).randbytes(0x20000)
        self.assertEqual(ihex.load(ihex.dump(data)), data)

    def test_type04_at_64k_boundary(self):
        lines = ihex.dump(bytes(0x20000)).splitlines()
        ext = [i for i, line in enumerate(lines) if line[7:9] == '04']
        self.assertEqual(len(ext), 1)
        i = ext[0]
        self.assertEqual(lines[i], ':020000040001F9')         # üst 16 bit = 0001
        self.assertEqual(i, 0x10000 // 16)                    # tam 4096 veri satırından sonra
        self.assertTrue(lines[i - 1].startswith(':10FFF000'))
        self.assertTrue(lines[i + 1].startswith(':10000000'))
        self.assertEqual(lines[-1], ':00000001FF')
        # 64 KB'lık imajda tip 04 kaydı gerekmez
        self.assertFalse(any(l[7:9] == '04' for l in ihex.dump(bytes(0x10000)).splitlines()))

    def test_checksums(self):
        text = ihex.dump(random.Random(6).randbytes(1000))
        for line in text.splitlines():
            self.assertEqual(sum(bytes.fromhex(line[1:])) & 0xFF, 0, line)
        bad = text.replace(text.splitlines()[3], text.splitlines()[3][:-2] + '00', 1)
        with self.assertRaises(ValueError):
            ihex.load(bad)

    def test_known_text(self):
        # Wikipedia "Intel HEX" örnek kaydı
        self.assertEqual(ihex.record(0x0010, 0, b'address gap'), ':0B0010006164647265737320676170A7')
        self.assertEqual(ihex.dump(bytes(range(16)) + b'\x10\x11'),
                         ':10000000000102030405060708090A0B0C0D0E0F78\n'
                         ':020010001011CD\n'
                         ':00000001FF\n')


# ---------------------------------------------------------------------------
# M5 adres çözme
# ---------------------------------------------------------------------------

CHIPS = ('ROM_CE_n', 'RAM_CE_n', 'VRAMSEL_n', 'IOSEL_n')


class DecodeTest(unittest.TestCase):
    def test_boundaries_read(self):
        # Okuma (MRD_n = 0, MEMW_L = 0, WSTB = 0): seçili çip ve I/O okuma çıkışları
        expected = {      # adres: (seçili çip, FPAGE_n, KBD_RD_n, STAT_RD_n)
            0x0000: ('ROM_CE_n', 1, 1, 1), 0x7FFF: ('ROM_CE_n', 1, 1, 1),
            0x8000: ('RAM_CE_n', 1, 1, 1), 0xEFFF: ('RAM_CE_n', 1, 1, 1),
            0xF000: ('VRAMSEL_n', 0, 1, 1), 0xF7FF: ('VRAMSEL_n', 0, 1, 1),
            0xF800: ('IOSEL_n', 0, 0, 1), 0xF801: ('IOSEL_n', 0, 1, 0),
            0xF807: ('IOSEL_n', 0, 1, 1), 0xF808: ('IOSEL_n', 0, 0, 1),
            0xF809: ('IOSEL_n', 0, 1, 0), 0xFFFF: ('IOSEL_n', 0, 1, 1),
        }
        for ab, (chip, fpage_n, kbd_n, stat_n) in expected.items():
            out = vectors.decode(ab, mrd_n=0, memw_l=0, wstb=0)
            with self.subTest(ab=hex(ab)):
                for c in CHIPS:
                    self.assertEqual(out[c], 0 if c == chip else 1, c)
                self.assertEqual(out['FPAGE_n'], fpage_n)
                self.assertEqual(out['KBD_RD_n'], kbd_n)
                self.assertEqual(out['STAT_RD_n'], stat_n)
                self.assertEqual((out['RD_n'], out['MWR_n'], out['WR_n']), (0, 1, 1))
                self.assertEqual((out['LED_E_n'], out['VRAM_WE_n']), (1, 1))
        # okuma yoksa (MRD_n = 1) I/O okuma çıkışları pasif
        out = vectors.decode(0xF800, mrd_n=1, memw_l=0, wstb=0)
        self.assertEqual((out['KBD_RD_n'], out['STAT_RD_n'], out['RD_n']), (1, 1, 1))

    def test_boundaries_write(self):
        # Yazma adımı (MRD_n = 1, MEMW_L = 1): /MWR yalnız WSTB = 1 (A fazı) iken düşük
        for wstb in (0, 1):
            vram = vectors.decode(0xF000, 1, 1, wstb)
            self.assertEqual((vram['MWR_n'], vram['WR_n'], vram['VRAM_WE_n']), (1 - wstb,) * 3)
            self.assertEqual(vram['LED_E_n'], 1)
            leds = vectors.decode(0xF800, 1, 1, wstb)
            self.assertEqual(leds['LED_E_n'], 0)               # commit'te örneklenir, WSTB'den bağımsız
            self.assertEqual(leds['VRAM_WE_n'], 1)
            for ab in (0x0000, 0x8000, 0xEFFF):
                self.assertEqual(vectors.decode(ab, 1, 1, wstb)['VRAM_WE_n'], 1)
                self.assertEqual(vectors.decode(ab, 1, 1, wstb)['LED_E_n'], 1)

    def test_one_chip_per_address(self):
        for ab in range(0x10000):
            out = vectors.decode(ab, 0, 0, 0)
            selected = [c for c in CHIPS if out[c] == 0]
            self.assertLessEqual(len(selected), 1, hex(ab))
            # bus.py'deki bellek haritasıyla aynı bölge
            region = ('ROM_CE_n' if ab < ROM_END else 'RAM_CE_n' if ab < VRAM_BASE
                      else 'VRAMSEL_n' if ab < IO_BASE else 'IOSEL_n')
            self.assertEqual(selected, [region], hex(ab))

    def test_table(self):
        names, rows = vectors.parse_table(vectors.decode_vectors(n=50, seed=3))
        self.assertEqual(names, vectors.DECODE_IN + vectors.DECODE_OUT)
        self.assertEqual(len(rows), len(vectors.DECODE_ADDRS) * 8 + 50)
        for addr in (0x0000, 0x7FFF, 0x8000, 0xEFFF, 0xF000, 0xF7FF,
                     0xF800, 0xF801, 0xF807, 0xF808, 0xF809, 0xFFFF):
            self.assertIn(addr, {r[0] for r in rows})
        for r in rows:
            out = vectors.decode(*r[:4])
            self.assertEqual(r[4:], [out[s] for s in vectors.DECODE_OUT])


# ---------------------------------------------------------------------------
# M2 kod çözücüler
# ---------------------------------------------------------------------------

class ChipSelectTest(unittest.TestCase):
    def test_at_most_one_active(self):
        for busack in (0, 1):
            for dsrc in range(8):
                for ddst in range(8):
                    for asrc in range(4):
                        out = vectors.chip_selects(dsrc, ddst, asrc, busack)
                        for group in (vectors.DS_OUT, vectors.DD_OUT, vectors.AS_OUT):
                            self.assertLessEqual([out[s] for s in group].count(0), 1)
                        if busack:
                            for s in vectors.DS_OUT + vectors.AS_OUT:
                                self.assertEqual(out[s], 1, (dsrc, ddst, asrc, s))
                        else:
                            self.assertEqual([out[s] for s in vectors.AS_OUT].count(0), 1)

    def test_mapping(self):
        out = vectors.chip_selects(isa.DSRC['MEM'], isa.DDST['IR'], isa.ASRC['SP'], 0)
        active = sorted(s for s, v in out.items() if v == 0)
        self.assertEqual(active, ['AB_SP_n', 'DD_IR_n', 'MRD_n'])
        out = vectors.chip_selects(7, 7, 0, 0)        # 7 = yok/panel, 7 = yasak: çıkış yok
        self.assertEqual(sorted(s for s, v in out.items() if v == 0), ['AB_PC_n'])
        out = vectors.chip_selects(isa.DSRC['PCH'], isa.DDST['ARH'], 2, 1)
        self.assertEqual(sorted(s for s, v in out.items() if v == 0), ['DD_ARH_n'])

    def test_table(self):
        names, rows = vectors.parse_table(vectors.cs_vectors())
        self.assertEqual(names, vectors.CS_IN + vectors.CS_OUT)
        self.assertEqual(len(rows), 512)
        self.assertEqual(len({tuple(r[:4]) for r in rows}), 512)


# ---------------------------------------------------------------------------
# Bütün CPU izi
# ---------------------------------------------------------------------------

class TraceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = merhaba_image()
        cls.text = vectors.trace_vectors(cls.image)
        cls.names, cls.rows = vectors.parse_table(cls.text)
        bus = Bus()
        bus.load(cls.image)
        cls.cpu = MicroEmu(bus)
        cls.cpu.run(2000)

    def test_row_count_and_first_row(self):
        self.assertTrue(self.cpu.halted)
        self.assertEqual(len(self.rows), self.cpu.cycles)
        self.assertEqual(self.names, vectors.TRACE_COLS)
        first = dict(zip(self.names, self.rows[0]))
        self.assertEqual((first['CYC'], first['AB']), (0, 0x0000))
        self.assertEqual(first['CW'], isa.step(isa.FETCH).word())
        self.assertEqual(dict(zip(self.names, self.rows[-1]))['HALT'], 1)

    def test_fields_match_cw(self):
        col = {n: i for i, n in enumerate(self.names)}
        for r in self.rows:
            cw = (r[col['ASRC']] << isa.ASRC_SHIFT | r[col['DSRC']] << isa.DSRC_SHIFT
                  | r[col['DDST']] << isa.DDST_SHIFT | r[col['ALUOP']] << isa.ALUOP_SHIFT)
            for name, bit in isa.BITS.items():
                cw |= bit if r[col[name]] else 0
            self.assertEqual(cw, r[col['CW']], r)

    def test_cycle_limit(self):
        rows = vectors.parse_table(vectors.trace_vectors(self.image, cycles=10))[1]
        self.assertEqual(len(rows), 10)

    def test_formats(self):
        csv = vectors.trace_vectors(self.image, fmt='csv')
        self.assertNotIn('#', csv)
        self.assertEqual(vectors.parse_table(csv), (self.names, self.rows))
        clocked = vectors.trace_vectors(self.image, clock='CLK')
        names, rows = vectors.parse_table(clocked)
        self.assertEqual(names, ['CLK'] + self.names)
        self.assertTrue(all(r[0] == 'C' and r[1:] == s for r, s in zip(rows, self.rows)))
        with self.assertRaises(ValueError):
            vectors.trace_vectors(self.image, fmt='csv', clock='CLK')

    def test_compare_traces(self):
        ref = vectors.parse_trace(self.text)
        self.assertEqual(ref, vectors.run_trace(self.image))
        self.assertIsNone(vectors.compare_traces(ref, list(ref))[0])

        bad = list(ref)
        c, ab, db, cw = bad[100]
        bad[100] = (c, ab, db, cw ^ isa.MEMW)
        bad[200] = (c, ab ^ 1, db, cw)                    # sonraki fark raporlanmaz
        idx, why = vectors.compare_traces(ref, bad)
        self.assertEqual(idx, 100)
        self.assertIn('MEMW', why)

        bad = list(ref)
        c, ab, db, cw = bad[7]
        bad[7] = (c + 1000, ab, db ^ 0x80, cw)            # çevrim numarası karşılaştırılmaz
        idx, why = vectors.compare_traces(ref, bad)
        self.assertEqual(idx, 7)
        self.assertIn('DB', why)

        self.assertEqual(vectors.compare_traces(ref, ref[:300])[0], 300)


# ---------------------------------------------------------------------------
# Komut satırı
# ---------------------------------------------------------------------------

class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_vectors_commands(self):
        for what, extra, nrows in [('alu', ['-n', '5'], 5), ('urom', ['-n', '5'], 5),
                                   ('decode', ['-n', '5'], len(vectors.DECODE_ADDRS) * 8 + 5),
                                   ('cs', [], 512)]:
            text = run_cli('vectors', what, *extra)
            self.assertEqual(len(vectors.parse_table(text)[1]), nrows, what)
            csv = run_cli('vectors', what, *extra, '--format', 'csv')
            self.assertTrue(csv.splitlines()[0].count(',') > 2, what)
        self.assertEqual(run_cli('vectors', 'alu', '-n', '50', '--seed', '9'),
                         vectors.alu_vectors(50, 9))

    def test_vectors_trace_to_file(self):
        out = self.tmp / 'iz.txt'
        msg = run_cli('vectors', 'trace', str(MERHABA), '-o', str(out), '--clock', 'CLK')
        self.assertIn('trace', msg)
        names, rows = vectors.parse_table(out.read_text(encoding='utf-8'))
        self.assertEqual(names[0], 'CLK')
        self.assertEqual(len(rows), 573)
        with self.assertRaises(SystemExit):
            run_cli('vectors', 'trace')                        # .asm yok
        with self.assertRaises(SystemExit):
            run_cli('vectors', 'alu', '--clock', 'CLK')

    def test_roms_writes_proteus(self):
        with mock.patch.object(cli, 'BUILD', self.tmp):
            msg = run_cli('roms')
        self.assertIn('bank 0', msg)                           # vga_timing'in üst yarısı SLOW
        names = ['urom0', 'urom1', 'urom2', 'alu_lo', 'alu_hi', 'vga_timing', 'font']
        proteus = self.tmp / 'proteus'
        self.assertEqual(sorted(p.name for p in proteus.glob('*.hex')),
                         sorted(n + '.hex' for n in names))
        for name in names:
            full = (self.tmp / f'{name}.bin').read_bytes()
            self.assertEqual(len(full), 0x20000)
            self.assertTrue((self.tmp / f'{name}.hex').read_text().startswith('v2.0 raw'))
            low = (proteus / f'{name}.bin').read_bytes()
            self.assertEqual(low, full[:0x10000])
            self.assertEqual(ihex.load((proteus / f'{name}.hex').read_text()), low)

    def test_asm_ihex(self):
        src = self.tmp / 'merhaba.asm'
        shutil.copy(MERHABA, src)
        msg = run_cli('asm', str(src), '--ihex')
        self.assertIn('Intel HEX', msg)
        rom = (self.tmp / 'merhaba.bin').read_bytes()
        self.assertEqual(len(rom), 0x8000)
        self.assertEqual(ihex.load((self.tmp / 'merhaba.hex').read_text()), rom)


if __name__ == '__main__':
    unittest.main()
