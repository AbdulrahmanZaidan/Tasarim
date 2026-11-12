"""Arduino iz ve yükleme aracı: td8/ardu.py, ardu_cli.py, arduino/td8_debug/td8_debug.ino.

Donanımsız. Bilgisayar tarafı, sketch'in Python ikizi FakeDevice ile bayt akışı seviyesinde
konuşur; istemci kodu (ArduClient, FrameReader) gerçek kartla konuşacak kodun aynısıdır.
Sketch burada çalıştırılamaz: protokol sabitlerinin iki tarafta aynı olduğu ve bus pinlerinin
yalnız BUSACK denetiminden sonra çıkış yapıldığı kaynak metinden denetlenir.

Çalıştırma (sim/ klasöründen): py -3 -m unittest tests.test_ardu -v
"""

import contextlib
import io
import random
import re
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ardu_cli
from td8 import ardu, asm, isa, vectors
from td8.ardu import (ArduClient, ArduDeviceError, ArduError, ArduTimeout, DeviceParser,
                      FakeDevice, FakeTransport, FrameReader, TraceCompare)

SIM = Path(__file__).resolve().parent.parent
EXAMPLES = SIM / 'examples'
SKETCH = SIM.parent / 'arduino' / 'td8_debug' / 'td8_debug.ino'

# ROM yalnız RAM'deki programa atlar; asıl program 8000'den (yükleme modu ile gelir).
RAM_PROGRAM = """
LEDS    = $F800
        .org $0000
        JMP basla
        .org $8000
basla:  LDA #0
        STA sayac
dongu:  LDA sayac
        INC
        STA sayac
        CMP #20
        BNE dongu
        STA LEDS
        LDX #mesaj
        LDA (X)
        STA $F000
        HALT
sayac:  .byte 0
mesaj:  .asciz "RAM"
"""


def program(name):
    path = EXAMPLES / name
    return asm.assemble(path.read_text(encoding='utf-8'), filename=str(path))


def connect(rom=None, rx_hook=None, tx_hook=None, **kw):
    dev = FakeDevice(rom, **kw)
    client = ArduClient(FakeTransport(dev, rx_hook=rx_hook, tx_hook=tx_hook))
    return client, dev


def traced(client, n=100_000, **kw):
    client.set_mode(ardu.MODE_TRACE)
    client.reset()
    return client.trace(n, **kw)


def run_cli(*argv):
    out = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out):
        try:
            ardu_cli.main([str(a) for a in argv])
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


# ---------------------------------------------------------------------------
# CRC ve çerçeveleme
# ---------------------------------------------------------------------------

def crc_bitwise(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc


class CrcTest(unittest.TestCase):
    def test_check_value(self):
        self.assertEqual(ardu.crc16(b'123456789'), 0x6F91)        # CRC-16/MCRF4XX

    def test_matches_bitwise(self):
        rng = random.Random(1)
        for n in (0, 1, 2, 7, 250):
            data = rng.randbytes(n)
            self.assertEqual(ardu.crc16(data), crc_bitwise(data), n)


def frames(seed, count=6):
    rng = random.Random(seed)
    return [ardu.Frame(rng.randrange(256), rng.randrange(256),
                       rng.randbytes(rng.choice((0, 1, 5, 40, 250))))
            for _ in range(count)]


def enc(f):
    return ardu.encode_frame(f.type, f.seq, f.payload)


class FrameReaderTest(unittest.TestCase):
    def test_roundtrip_and_byte_by_byte(self):
        fs = frames(2, 20)
        stream = b''.join(enc(f) for f in fs)
        self.assertEqual(FrameReader().feed(stream), fs)
        r, got = FrameReader(), []
        for b in stream:
            got += r.feed(bytes((b,)))
        self.assertEqual(got, fs)
        self.assertEqual((r.crc_errors, r.dropped), (0, 0))

    def test_crc_error_skipped(self):
        a, b, c = frames(3, 3)
        bad = bytearray(enc(b))
        bad[-3] ^= 0x10                                  # yükte (ya da uzunlukta) bir bit
        r = FrameReader()
        self.assertEqual(r.feed(enc(a) + bytes(bad) + enc(c)), [a, c])
        self.assertEqual(r.crc_errors, 1)

    def test_truncated_then_good(self):
        a, b = ardu.Frame(1, 2, bytes(range(200))), ardu.Frame(3, 4, b'xyz')
        full = enc(a)
        for k in range(1, len(full)):
            r = FrameReader()
            got = r.feed(full[:k] + enc(b))
            while not got and r.buf:                     # istemci: zaman aşımında resync
                got = r.resync()
            self.assertEqual(got, [b], k)

    def test_garbage_between_frames(self):
        fs = frames(4, 8)
        rng = random.Random(4)
        junk = [b'\xA5', b'\xA5\x5A', b'\xA5\x5A\x01\x02\xFF', b'\x5A\xA5\xA5', rng.randbytes(30)]
        stream = b''.join(rng.choice(junk) + enc(f) for f in fs) + b'\xA5'
        r = FrameReader()
        self.assertEqual(r.feed(stream), fs)
        self.assertGreater(r.dropped, 0)

    def test_length_over_limit(self):
        good = ardu.Frame(9, 9, b'ok')
        r = FrameReader()
        self.assertEqual(r.feed(bytes((0xA5, 0x5A, 1, 2, 251)) + enc(good)), [good])
        with self.assertRaises(ValueError):
            ardu.encode_frame(1, 1, bytes(251))


class DeviceParserTest(unittest.TestCase):
    """Sketch'teki rx_byte durum makinesinin ikizi."""

    def setUp(self):
        self.now = 0.0
        self.got, self.bad = [], []
        self.p = DeviceParser(lambda t, s, d: self.got.append((t, s, d)),
                              lambda t, s: self.bad.append((t, s)), clock=lambda: self.now)

    def push(self, data, dt=1e-5):
        for b in data:
            self.now += dt
            self.p.push(b)

    def test_good_bad_garbage(self):
        a, b, c = frames(5, 3)
        bad = bytearray(enc(b))
        bad[5] ^= 1 if b.payload else 0
        bad[-1] ^= 0x80
        self.push(b'\x00\xA5\xA5' + enc(a) + bytes(bad) + b'\x5A\xA5' + enc(c))
        self.assertEqual(self.got, [(a.type, a.seq, a.payload), (c.type, c.seq, c.payload)])
        self.assertEqual(len(self.bad), 1)

    def test_truncated_frame_timeout(self):
        a, b = ardu.Frame(1, 1, bytes(100)), ardu.Frame(2, 2, b'q')
        self.push(enc(a)[:20])
        self.now += 0.5                                   # > FRAME_TIMEOUT_MS
        self.push(enc(b))
        self.assertEqual(self.got, [(2, 2, b'q')])
        self.assertEqual(self.p.timeouts, 1)

    def test_truncated_frame_without_timeout(self):
        # Zaman aşımı olmazsa kesik çerçeve (başlığı tam, uzunluk 3) sonrakinin başını yük diye
        # yutar → CRC hatası; artakalan çöp atlanır, ondan sonrası sağlam.
        a, b, c = ardu.Frame(1, 1, b'abc'), ardu.Frame(2, 2, b'de'), ardu.Frame(3, 3, b'f')
        self.push(enc(a)[:5] + enc(b) + enc(c) + enc(c))
        self.assertEqual(len(self.bad), 1)
        self.assertIn((3, 3, b'f'), self.got)

    def test_length_over_limit(self):
        self.push(bytes((0xA5, 0x5A, 1, 1, 251)) + enc(ardu.Frame(4, 4, b'')))
        self.assertEqual(self.got, [(4, 4, b'')])
        self.assertEqual(self.p.errors, 1)


# ---------------------------------------------------------------------------
# Sketch ile Python aynı mı
# ---------------------------------------------------------------------------

DEFINE = re.compile(r'^\s*#define\s+(\w+)\s+(0x[0-9A-Fa-f]+|\d+|"[^"]*")(?:UL|U|L)?\s*(?://.*)?$',
                    re.M)


def sketch_constants():
    text = SKETCH.read_text(encoding='utf-8')
    block = text.split('// >>> PROTOKOL', 1)[1].split('// <<< PROTOKOL', 1)[0]
    out = {}
    for name, value in DEFINE.findall(block):
        out[name] = value[1:-1] if value.startswith('"') else int(value, 0)
    return out, block


class ConstantsTest(unittest.TestCase):
    def test_sketch_matches_python(self):
        consts, block = sketch_constants()
        defines = re.findall(r'^\s*#define\s+(\w+)', block, re.M)
        self.assertEqual(sorted(defines), sorted(consts), 'ayrıştırılamayan #define var')
        self.assertEqual(consts, ardu.PROTOCOL)

    def test_python_block_complete(self):
        # ardu.py'deki blokta tanımlı her ad PROTOCOL sözlüğünde de olmalı
        src = (SIM / 'td8' / 'ardu.py').read_text(encoding='utf-8')
        block = src.split('# >>> PROTOKOL', 1)[1].split('# <<< PROTOKOL', 1)[0]
        names = re.findall(r'^([A-Z_0-9]+) = ', block, re.M)
        self.assertEqual(sorted(names), sorted(ardu.PROTOCOL))

    def test_layout(self):
        self.assertLessEqual(4 + ardu.RECS_PER_FRAME * ardu.REC_SIZE, ardu.MAX_PAYLOAD)
        self.assertLessEqual(3 + ardu.MAX_BLOCK, ardu.MAX_PAYLOAD)
        self.assertEqual(1 << ardu.CW_HALT_BIT, isa.HALT)
        cmds = [v for k, v in ardu.PROTOCOL.items() if k.startswith('CMD_')]
        replies = {c | ardu.RSP_FLAG for c in cmds}
        self.assertEqual(len(set(cmds)), len(cmds))
        self.assertTrue(all(c < ardu.RSP_FLAG for c in cmds))
        self.assertFalse(replies & {ardu.TRACE_DATA, ardu.RSP_ERROR})
        errs = [v for k, v in ardu.PROTOCOL.items() if k.startswith('ERR_')]
        self.assertEqual(len(set(errs)), len(errs))
        self.assertEqual(set(ardu.ERR_TEXT), set(errs))
        pins = [v for k, v in ardu.PROTOCOL.items() if k.startswith('PIN_')]
        self.assertEqual(sorted(pins), [1 << k for k in range(8)])

    def test_every_command_handled(self):
        text = SKETCH.read_text(encoding='utf-8')
        client, dev = connect()
        for name, code in ardu.PROTOCOL.items():
            if name.startswith('CMD_'):
                self.assertIn(f'case {name}:', text, name)
                dev.feed(ardu.encode_frame(code, 7, b''))
                for f in FrameReader().feed(b''.join(dev.pull_frames(100))):
                    if f.type == ardu.RSP_ERROR:
                        self.assertNotEqual(f.payload[1], ardu.ERR_UNKNOWN_CMD, name)
        with self.assertRaises(ArduDeviceError) as cm:
            client.request(0x33)
        self.assertEqual(cm.exception.code, ardu.ERR_UNKNOWN_CMD)

    def test_bus_driven_only_after_busack_check(self):
        """Sketch'te AB/DB pinleri yalnız ab_drive içinde (BUSACK denetiminden sonra) ya da
        write_byte'ta ab_drive başarılı olduktan sonra çıkış yapılır."""
        text = SKETCH.read_text(encoding='utf-8')
        funcs = re.split(r'\n(?=static [\w ]+\*?\s*\w+\([^;]*\)\s*\{)', text)
        found = 0
        for body in funcs:
            name = re.match(r'static [\w ]+?\*?\s*(\w+)\(', body)
            for line_no, line in enumerate(body.splitlines()):
                if re.search(r'\b(AB_LO_DDR|AB_HI_DDR|DB_DDR)\s*=\s*0xFF', line):
                    found += 1
                    self.assertIsNotNone(name, line)
                    fn = name.group(1)
                    before = '\n'.join(body.splitlines()[:line_no])
                    if fn == 'ab_drive':
                        self.assertIn('if (!busack_now())', before)
                    else:
                        self.assertEqual(fn, 'write_byte', line)
                        self.assertIn('if (!ab_drive(addr)) return false;', before)
        self.assertEqual(found, 3)
        self.assertNotIn('delay(', re.sub(r'__builtin_avr_delay_cycles|delayMicroseconds', '', text))


# ---------------------------------------------------------------------------
# İz: sahte cihazdan alınan iz == MicroEmu izi
# ---------------------------------------------------------------------------

class TraceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.images = {name: program(name).image for name in ('merhaba.asm', 'komut_testi.asm')}
        cls.refs = {name: vectors.run_trace(img, 100_000) for name, img in cls.images.items()}

    def test_trace_equals_emulator(self):
        for name, image in self.images.items():
            with self.subTest(name):
                client, dev = connect(image)
                self.assertEqual(client.hello().ident, 'TD8-ARDU')
                res = traced(client)
                ref = self.refs[name]
                self.assertEqual(res.reason, ardu.END_HALT)
                self.assertEqual((res.done, res.cycle), (len(ref), len(ref)))
                self.assertIsNone(vectors.compare_traces(ref, res.rows)[0])
                self.assertEqual(res.rows, ref)
                self.assertTrue(res.pins & ardu.PIN_STOP)
                self.assertEqual(ardu.phase_of(res.pins), 'C')

    def test_streaming_compare(self):
        for name, image in self.images.items():
            with self.subTest(name):
                client, _ = connect(image)
                cmp = TraceCompare(image)
                res = traced(client, on_rows=cmp.feed, first_index=0)
                self.assertIsNone(cmp.diff)
                self.assertEqual(cmp.count, len(self.refs[name]))
                self.assertTrue(cmp.emu.halted)
                self.assertIsNone(res.rows)

    def test_trace_in_chunks_and_after_halt(self):
        image, ref = self.images['merhaba.asm'], self.refs['merhaba.asm']
        client, _ = connect(image)
        client.set_mode(ardu.MODE_TRACE)
        client.reset()
        rows = []
        while True:
            res = client.trace(37, first_index=len(rows))
            rows += res.rows
            if res.reason != ardu.END_OK:
                break
        self.assertEqual(res.reason, ardu.END_HALT)
        self.assertEqual(rows, ref)
        res = client.trace(10)                        # makine HALT'ta: commit yok
        self.assertEqual((res.reason, res.done), (ardu.END_STALL, 0))
        self.assertTrue(res.pins & ardu.PIN_STOP)

    def test_step_and_clock(self):
        image, ref = self.images['merhaba.asm'], self.refs['merhaba.asm']
        client, _ = connect(image)
        client.set_mode(ardu.MODE_TRACE)
        client.reset()
        self.assertEqual(ardu.phase_of(client.status().pins), 'D')     # 0. çevrim, FETCH latch'te
        for k in range(3):
            s = client.step()
            self.assertEqual(s.reason, ardu.END_OK)
            self.assertEqual((s.cycle, s.ab, s.db, s.cw), ref[k])
        pins, cyc = client.clock(1)                   # C → D
        self.assertEqual((ardu.phase_of(pins), cyc, client.take_side_rows()), ('D', 3, []))
        pins, cyc = client.clock(2)                   # D → A → B
        self.assertEqual((ardu.phase_of(pins), cyc, client.take_side_rows()), ('B', 3, []))
        pins, cyc = client.clock(1)                   # B → C: commit
        self.assertEqual((ardu.phase_of(pins), cyc), ('C', 4))
        self.assertEqual(client.take_side_rows(), [ref[3]])
        res = client.trace(100_000, first_index=4)
        self.assertEqual(res.rows, ref[4:])

    def test_memory_access_during_trace_keeps_trace_complete(self):
        """İz modunda bus isteği CPU'yu (en çok) bir çevrim ilerletir; o çevrim de kaydedilir."""
        image, ref = self.images['komut_testi.asm'], self.refs['komut_testi.asm']
        client, _ = connect(image)
        client.set_mode(ardu.MODE_TRACE)
        client.reset()
        rows = client.trace(50, first_index=0).rows
        client.read(0x8100, 4)
        side = client.take_side_rows()
        self.assertEqual(side, [ref[50]])
        client.read(0x8100, 4)                        # makine C'de BUSACK'la duruyor: ilerlemez
        self.assertEqual(client.take_side_rows(), [])
        client.bus(True)
        with self.assertRaises(ArduDeviceError) as cm:
            client.trace(5)
        self.assertEqual(cm.exception.code, ardu.ERR_BUS_HELD)
        client.bus(False)
        rows += side + client.trace(100_000, first_index=51).rows
        self.assertEqual(rows, ref)

    def test_free_mode_rejects_trace(self):
        client, _ = connect(self.images['merhaba.asm'])
        for call in (lambda: client.trace(5), client.step, lambda: client.clock(1)):
            with self.assertRaises(ArduDeviceError) as cm:
                call()
            self.assertEqual(cm.exception.code, ardu.ERR_MODE)


# ---------------------------------------------------------------------------
# Hata yakalama: sahte cihaza bilerek konan hatalar
# ---------------------------------------------------------------------------

class FaultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.merhaba = program('merhaba.asm').image
        cls.komut = program('komut_testi.asm').image
        cls.ref_merhaba = vectors.run_trace(cls.merhaba, 100_000)
        cls.ref_komut = vectors.run_trace(cls.komut, 100_000)

    def test_db_bit_flip(self):
        client, _ = connect(self.merhaba, db_flip={100: 0x04})
        rows = traced(client).rows
        idx, why = vectors.compare_traces(self.ref_merhaba, rows)
        self.assertEqual(idx, 100)
        self.assertIn('DB', why)
        self.assertEqual(rows[100][2], self.ref_merhaba[100][2] ^ 0x04)

        client, _ = connect(self.merhaba, db_flip={100: 0x04})
        cmp = TraceCompare(self.merhaba)
        res = traced(client, on_rows=cmp.feed, first_index=0)
        self.assertEqual(cmp.diff.index, 100)
        self.assertEqual(cmp.diff.fields, ['DB'])
        self.assertTrue(cmp.diff.message.startswith('çevrim 100:'))
        self.assertEqual(cmp.diff.ref, self.ref_merhaba[100])
        self.assertEqual(cmp.diff.before, self.ref_merhaba[97:100])
        self.assertEqual(res.reason, ardu.END_ABORT)          # fark görülünce iz durduruldu
        self.assertLess(res.done, len(self.ref_merhaba))
        self.assertEqual(client.status().mode, ardu.MODE_TRACE)   # bağlantı sağlam

    def test_control_word_bit_stuck(self):
        cases = [(self.komut, self.ref_komut, isa.XINC, 0, 'CW.XINC'),
                 (self.merhaba, self.ref_merhaba, isa.MARK, 1, 'CW.MARK'),
                 (self.komut, self.ref_komut, isa.SPDN, 0, 'CW.SPDN')]
        for image, ref, bit, val, field in cases:
            with self.subTest(field=field, val=val):
                expected = next(i for i, r in enumerate(ref) if bool(r[3] & bit) != bool(val))
                client, _ = connect(image, cw_stuck=(bit.bit_length() - 1, val))
                rows = traced(client).rows
                idx, why = vectors.compare_traces(ref, rows)
                self.assertEqual(idx, expected)
                self.assertIn(field[3:], why)
                client, _ = connect(image, cw_stuck=(bit.bit_length() - 1, val))
                cmp = TraceCompare(image)
                traced(client, on_rows=cmp.feed, first_index=0)
                self.assertEqual((cmp.diff.index, cmp.diff.fields), (expected, [field]))

    def test_lost_trace_frame_detected(self):
        # 2. TRACE_DATA çerçevesi yolda bozulur: iz geçersiz sayılmalı, sessizce kaymamalı.
        seen = []

        def hook(i, frame):
            if frame[2] == ardu.TRACE_DATA:
                seen.append(i)
                if len(seen) == 2:
                    frame = frame[:10] + bytes((frame[10] ^ 0xFF,)) + frame[11:]
            return frame

        client, _ = connect(self.merhaba, rx_hook=hook)
        with self.assertRaisesRegex(ArduError, 'kayboldu'):
            traced(client, on_rows=TraceCompare(self.merhaba).feed, first_index=0)
        self.assertEqual(client.reader.crc_errors, 1)
        self.assertEqual(client.status().mode, ardu.MODE_TRACE)


# ---------------------------------------------------------------------------
# Yükleme modu
# ---------------------------------------------------------------------------

class LoadTest(unittest.TestCase):
    def setUp(self):
        self.prog = asm.assemble(RAM_PROGRAM)

    def test_load_and_trace_ram_program(self):
        segs, other = ardu.ram_segments(self.prog)
        self.assertEqual([a for a, _ in segs], [0x8000])
        self.assertEqual([(r, a) for r, a, _ in other], [('ROM', 0x0000)])
        client, dev = connect(self.prog.image)          # flash'ta yalnız JMP; RAM boş
        self.assertEqual(bytes(dev.bus.mem[0x8000:0x8010]), bytes(16))
        n = ardu.load_segments(client, segs)
        self.assertEqual(n, len(segs[0][1]))
        self.assertEqual(bytes(dev.bus.mem[0x8000:0x8000 + n]), segs[0][1])
        self.assertEqual(client.read(0x8000, n), segs[0][1])
        self.assertFalse(dev.busreq or dev.bus_driven or dev.bus_hold)
        cmp = TraceCompare(self.prog.image)
        res = traced(client, on_rows=cmp.feed, first_index=0)
        self.assertIsNone(cmp.diff)
        self.assertEqual(res.reason, ardu.END_HALT)
        self.assertEqual(cmp.count, len(vectors.run_trace(self.prog.image, 100_000)))
        self.assertEqual(dev.bus.leds, 20)                # programın kendi STA LEDS'i (commit)
        self.assertEqual(dev.bus.vram[0], ord('R'))

    def test_load_random_block(self):
        data = random.Random(7).randbytes(1000)           # 8 blok
        client, dev = connect()
        self.assertEqual(client.load(0x8000, data), 1000)
        self.assertEqual(bytes(dev.bus.mem[0x8000:0x8000 + 1000]), data)
        self.assertEqual(client.read(0x8000, 1000), data)
        client.write(0xEFFE, b'\x11\x22')                 # RAM'in son baytları
        self.assertEqual(client.read(0xEFFE, 2), b'\x11\x22')

    def test_rom_and_vram_writes(self):
        client, dev = connect(program('merhaba.asm').image)
        with self.assertRaises(ArduDeviceError) as cm:
            client.write(0x0010, b'\x99')                 # flash: /WE = VCC, değişmez
        self.assertEqual(cm.exception.code, ardu.ERR_VERIFY)
        self.assertIn('0010', str(cm.exception))
        self.assertFalse(dev.busreq or dev.bus_driven)
        client.write(0xF000 + 64, b'AB', verify=False)    # VRAM yalnız yazılır
        self.assertEqual(bytes(dev.bus.vram[64:66]), b'AB')
        self.assertEqual(client.read(0xF000 + 64, 2), b'\x00\x00')   # DB pull-down
        dev.bus.dip = 0x21
        self.assertEqual(client.read(0xF801, 1)[0], 0x40 | 0x21)     # KSTAT: VWR + DIP

    def test_busack_timeout(self):
        client, dev = connect(busack=False)
        for call in (lambda: client.read(0x8000, 1), lambda: client.load(0x8000, b'\x01'),
                     lambda: client.bus(True)):
            with self.assertRaises(ArduDeviceError) as cm:
                call()
            self.assertEqual(cm.exception.code, ardu.ERR_BUSACK_TIMEOUT)
            self.assertIn('BUSACK', str(cm.exception))
            self.assertFalse(dev.busreq or dev.bus_driven or dev.bus_hold)

    def test_load_survives_corrupted_reply(self):
        def hook(i, frame):
            if i == 3:                                     # bir WRITE yanıtı bozuk gelir
                frame = frame[:6] + bytes((frame[6] ^ 0x01,)) + frame[7:]
            return frame
        client, dev = connect(rx_hook=hook)
        data = random.Random(8).randbytes(600)
        client.load(0x9000, data)
        self.assertEqual(bytes(dev.bus.mem[0x9000:0x9000 + 600]), data)
        self.assertEqual(client.reader.crc_errors, 1)
        self.assertEqual(client.retried, 1)

    def test_load_survives_corrupted_request(self):
        def hook(i, data):
            if i == 2:                                     # bilgisayarın 3. çerçevesi bozuk gider
                data = data[:8] + bytes((data[8] ^ 0x40,)) + data[9:]
            return data
        client, dev = connect(tx_hook=hook)
        data = random.Random(9).randbytes(300)
        client.load(0x8800, data)
        self.assertEqual(bytes(dev.bus.mem[0x8800:0x8800 + 300]), data)
        self.assertEqual(dev.parser.errors, 1)
        self.assertEqual(client.retried, 1)


# ---------------------------------------------------------------------------
# Yeniden senkron: çöp, kesik ve kaybolan çerçeveler
# ---------------------------------------------------------------------------

class ResyncTest(unittest.TestCase):
    def test_garbage_before_every_reply(self):
        rng = random.Random(10)
        junk = [b'\xA5', b'\xA5\x5A\x81', b'\xA5\x5A\x82\x01\xF0', rng.randbytes(17)]
        client, dev = connect(rx_hook=lambda i, f: rng.choice(junk) + f)
        client.hello()
        data = rng.randbytes(300)
        client.load(0x8000, data)
        self.assertEqual(client.read(0x8000, 300), data)
        self.assertEqual(client.retried, 0)
        self.assertGreater(client.reader.dropped, 0)

    def test_truncated_reply(self):
        client, _ = connect(rx_hook=lambda i, f: f[:6] if i == 0 else f)
        self.assertEqual(client.hello().ident, 'TD8-ARDU')
        self.assertEqual(client.retried, 1)

    def test_truncated_request(self):
        client, dev = connect(tx_hook=lambda i, d: d[:4] if i == 0 else d)
        client.hello()
        self.assertEqual(client.retried, 1)
        self.assertEqual(dev.parser.timeouts, 1)         # kartın 100 ms'lik bayt arası zaman aşımı

    def test_duplicate_reply_is_stale(self):
        client, _ = connect(rx_hook=lambda i, f: f + f if i == 0 else f)
        client.hello()
        st = client.status()
        self.assertEqual(st.mode, ardu.MODE_FREE)
        self.assertEqual(client.stale, 1)

    def test_retries_exhausted(self):
        client, _ = connect(rx_hook=lambda i, f: b'')
        with self.assertRaises(ArduTimeout):
            client.hello()
        self.assertEqual(client.retried, client.retries)

    def test_boot_announcement(self):
        dev = FakeDevice(announce=True)
        client = ArduClient(FakeTransport(dev))
        self.assertEqual(client.wait_ready(boot_wait=0.1).ident, 'TD8-ARDU')
        self.assertEqual(client.boots, 1)


# ---------------------------------------------------------------------------
# Komut satırı (--fake) ve isteğe bağlı pyserial
# ---------------------------------------------------------------------------

class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_trace_zero_diff(self):
        save = self.tmp / 'iz.txt'
        code, out = run_cli('trace', EXAMPLES / 'merhaba.asm', '--fake', '--save', save)
        self.assertEqual(code, 0, out)
        self.assertIn('SIFIR FARK (573 çevrim, ikisi de HALT)', out)
        ref = vectors.run_trace(program('merhaba.asm').image)
        self.assertEqual(vectors.parse_trace(save.read_text(encoding='utf-8')), ref)

    def test_trace_reports_first_difference(self):
        code, out = run_cli('trace', EXAMPLES / 'merhaba.asm', '--fake', '--fake-db-flip', '100:0x04')
        self.assertEqual(code, 1)
        self.assertIn('ilk fark çevrim 100: DB beklenen 1D, gelen 19', out)
        code, out = run_cli('trace', EXAMPLES / 'komut_testi.asm', '--fake',
                            '--fake-cw-stuck', '19:0')
        self.assertEqual(code, 1)
        self.assertIn('farklı alanlar: CW.XINC', out)

    def test_load_and_ram_trace(self):
        src = self.tmp / 'ramprog.asm'
        src.write_text(RAM_PROGRAM, encoding='utf-8')
        code, out = run_cli('load', src, '--fake', '--reset')
        self.assertEqual(code, 0, out)
        self.assertIn('geri okunup doğrulandı (8000–', out)
        self.assertIn('ROM bölgesindeki', out)
        code, out = run_cli('trace', src, '--fake')
        self.assertEqual(code, 0, out)
        self.assertIn('RAM: ', out)
        self.assertIn('SIFIR FARK', out)
        code, out = run_cli('load', src, '--fake', '--fake-no-busack')
        self.assertIn('BUSACK', str(code))
        code, out = run_cli('load', EXAMPLES / 'merhaba.asm', '--fake')
        self.assertIn('8000–EFFF', str(code))

    def test_small_commands(self):
        merhaba = EXAMPLES / 'merhaba.asm'
        code, out = run_cli('peek', '0000', '4', '--fake', '--fake-rom', merhaba)
        image = program('merhaba.asm').image
        self.assertIn('0000  ' + image[:4].hex(' '), out)
        code, out = run_cli('poke', '$8000', '12', '34', '--fake')
        self.assertEqual(code, 0)
        self.assertIn('8000: 2 bayt yazıldı ve doğrulandı', out)
        code, out = run_cli('step', '3', '--fake', '--fake-rom', merhaba)
        self.assertEqual(code, 0)
        self.assertEqual(out.count('AB='), 3)
        self.assertIn('AB=0000', out)
        for argv in (('status',), ('info',), ('clock', '6'), ('reset', '--mod', 'iz'), ('reset',)):
            code, out = run_cli(*argv, '--fake', '--fake-rom', merhaba)
            self.assertEqual(code, 0, (argv, out))
        self.assertIn('çevrim/s', run_cli('info', '--fake')[1])
        code, _ = run_cli('status')
        self.assertIn('--port', str(code))

    def test_missing_pyserial(self):
        with mock.patch.dict(sys.modules, {'serial': None}):
            with self.assertRaises(ArduError) as cm:
                ardu.SerialTransport('COM99')
        self.assertIn('pyserial', str(cm.exception))

    def test_rate_estimate(self):
        self.assertAlmostEqual(ardu.estimate_rate(1_000_000), 15936.25, places=1)
        self.assertGreater(1e6 / ardu.estimate_rate(115_200), 500)     # ~9 dakika


if __name__ == '__main__':
    unittest.main()
