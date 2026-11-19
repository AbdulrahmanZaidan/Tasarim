"""Arduino hata ayıklama kartının bilgisayar tarafı (SISTEM-PLANI 10, kabul ölçütü 16.3).

Sketch: ../../arduino/ta8_debug/ta8_debug.ino. Protokol ve kullanım: ../../arduino/README.md.

!!! Bu sürüm gerçek donanımla HİÇ denenmedi. Yalnızca aşağıdaki FakeDevice ile
(sketch'in Python ikizi) sınandı. !!!

İçerik:
    sabitler      sketch'teki ">>> PROTOKOL" bloğunun aynısı (tests/test_ardu.py karşılaştırır)
    çerçeveleme   crc16, encode_frame, FrameReader (bilgisayar), DeviceParser (cihazın ikizi)
    taşıyıcılar   SerialTransport (pyserial isteğe bağlı), FakeTransport (bayt akışı, hata ekleme)
    ArduClient    hello, status, set_mode, reset, trace, step, clock, read, write, bus, load
    TraceCompare  cihaz izini MicroEmu ile akarken karşılaştırır, farkın başladığı çevrimi bulur
    FakeDevice    sketch'in Python ikizi: aynı bayt akışı, arkasında MicroEmu + Bus

Çerçeve (iki yönde aynı):
    A5 5A | TİP | SIRA | UZUNLUK | YÜK[UZUNLUK] | CRC lo | CRC hi
CRC-16 (polinom 0x8408, başlangıç FFFF) TİP, SIRA, UZUNLUK ve YÜK üzerinden.
"""

import struct
import time
from collections import deque, namedtuple
from functools import lru_cache

from . import alu, microcode, vectors
from .bus import IO_BASE, ROM_END, VRAM_BASE, Bus
from .emu_micro import MicroEmu


@lru_cache(maxsize=1)
def _tables():
    """uROM ve ALU imajları (donanımdakilerin aynısı); süreç başına bir kez üretilir."""
    return microcode.build(), alu.build_tables()

# >>> PROTOKOL SABİTLERİ: arduino/ta8_debug/ta8_debug.ino ile birebir AYNI
PROTO_VERSION = 1
FW_MAJOR = 0
FW_MINOR = 1
DEVICE_ID = 'TA8-ARDU'
SERIAL_BAUD = 1_000_000
FRAME_SYNC1 = 0xA5
FRAME_SYNC2 = 0x5A
MAX_PAYLOAD = 250
MAX_BLOCK = 128
REC_SIZE = 6
RECS_PER_FRAME = 40
FRAME_TIMEOUT_MS = 100
BUSACK_TIMEOUT_MS = 500
RESET_HOLD_MS = 50
RESET_TIMEOUT_MS = 1000
FREE_CLOCK_CHECK_MS = 5
STALL_PULSES = 1024
CW_HALT_BIT = 23

CMD_HELLO = 0x01
CMD_STATUS = 0x02
CMD_MODE = 0x03
CMD_RESET = 0x04
CMD_TRACE = 0x05
CMD_STEP = 0x06
CMD_CLOCK = 0x07
CMD_READ = 0x08
CMD_WRITE = 0x09
CMD_BUS = 0x0A
RSP_FLAG = 0x80
TRACE_DATA = 0xA0
RSP_ERROR = 0xFF

MODE_FREE = 0
MODE_TRACE = 1
WRITE_VERIFY = 0x01

ERR_CRC = 1
ERR_UNKNOWN_CMD = 2
ERR_BAD_LEN = 3
ERR_BAD_ARG = 4
ERR_MODE = 5
ERR_BUS_HELD = 6
ERR_BUSACK_TIMEOUT = 7
ERR_BUSACK_LOST = 8
ERR_VERIFY = 9
ERR_RESET_NOT_C = 10
ERR_RESET_TIMEOUT = 11
ERR_FREE_CLOCK = 12

END_OK = 0
END_HALT = 1
END_STALL = 2
END_ABORT = 3
END_PHASE = 4

PIN_Q1 = 0x01
PIN_CLK = 0x02
PIN_STOP = 0x04
PIN_BUSACK = 0x08
PIN_BUSREQ_OUT = 0x10
PIN_RESET_OUT = 0x20
PIN_BUS_DRIVEN = 0x40
PIN_TRACE_MODE = 0x80
# <<< PROTOKOL SABİTLERİ

PROTOCOL = {name: globals()[name] for name in """
    PROTO_VERSION FW_MAJOR FW_MINOR DEVICE_ID SERIAL_BAUD FRAME_SYNC1 FRAME_SYNC2 MAX_PAYLOAD
    MAX_BLOCK REC_SIZE RECS_PER_FRAME FRAME_TIMEOUT_MS BUSACK_TIMEOUT_MS RESET_HOLD_MS
    RESET_TIMEOUT_MS FREE_CLOCK_CHECK_MS STALL_PULSES CW_HALT_BIT
    CMD_HELLO CMD_STATUS CMD_MODE CMD_RESET CMD_TRACE CMD_STEP CMD_CLOCK CMD_READ CMD_WRITE
    CMD_BUS RSP_FLAG TRACE_DATA RSP_ERROR MODE_FREE MODE_TRACE WRITE_VERIFY
    ERR_CRC ERR_UNKNOWN_CMD ERR_BAD_LEN ERR_BAD_ARG ERR_MODE ERR_BUS_HELD ERR_BUSACK_TIMEOUT
    ERR_BUSACK_LOST ERR_VERIFY ERR_RESET_NOT_C ERR_RESET_TIMEOUT ERR_FREE_CLOCK
    END_OK END_HALT END_STALL END_ABORT END_PHASE
    PIN_Q1 PIN_CLK PIN_STOP PIN_BUSACK PIN_BUSREQ_OUT PIN_RESET_OUT PIN_BUS_DRIVEN PIN_TRACE_MODE
""".split()}

CMD_NAMES = {CMD_HELLO: 'HELLO', CMD_STATUS: 'STATUS', CMD_MODE: 'MODE', CMD_RESET: 'RESET',
             CMD_TRACE: 'TRACE', CMD_STEP: 'STEP', CMD_CLOCK: 'CLOCK', CMD_READ: 'READ',
             CMD_WRITE: 'WRITE', CMD_BUS: 'BUS'}
MODE_NAMES = {MODE_FREE: 'serbest', MODE_TRACE: 'iz'}

ERR_TEXT = {
    ERR_CRC: 'çerçeve cihaza bozuk ulaştı (CRC)',
    ERR_UNKNOWN_CMD: 'bilinmeyen komut',
    ERR_BAD_LEN: 'yük uzunluğu yanlış',
    ERR_BAD_ARG: 'geçersiz değer',
    ERR_MODE: 'bu komut serbest modda kullanılamaz (önce iz modu)',
    ERR_BUS_HELD: 'bus Arduino\'da tutuluyor; önce bırakılmalı',
    ERR_BUSACK_TIMEOUT: (f'BUSACK {BUSACK_TIMEOUT_MS} ms içinde gelmedi: makinenin saati çalışıyor '
                         'mu (saat seçici I3/Arduino ise iz modu gerekir), /BUSREQ ve BUSACK '
                         'kabloları doğru mu?'),
    ERR_BUSACK_LOST: 'erişim sırasında BUSACK düştü (reset mi basıldı?); pinler bırakıldı',
    ERR_VERIFY: 'geri okunan değer yazılanla aynı değil',
    ERR_RESET_NOT_C: '/RESET indirildiği halde faz C değil: reset, Q1 ya da CLK kablosu?',
    ERR_RESET_TIMEOUT: ('reset bırakıldı ama makine C fazından çıkmadı: STOP = 1 mi (RUN/STEP '
                        'anahtarı STEP\'te, breakpoint), reset hattı takılı mı?'),
    ERR_FREE_CLOCK: ('makine Arduino darbe vermeden ilerliyor: saat seçici I3 (Arduino) '
                     'konumunda değil'),
}
END_TEXT = {
    END_OK: 'istenen çevrim sayısı tamamlandı',
    END_HALT: 'HALT (makine C fazında durdu)',
    END_STALL: f'makine {STALL_PULSES} MCLK darbesinde commit yapmadı (STOP = 1 ya da saat yok)',
    END_ABORT: 'bilgisayar durdurdu',
    END_PHASE: 'commit darbesinden sonra faz C değil (saat ya da Q1/CLK kablosu sorunu)',
}

PHASES = {(0, 0): 'A', (1, 0): 'B', (1, 1): 'C', (0, 1): 'D'}   # (Q1, Q2)


def phase_of(pins):
    """Durum baytından faz harfi (SISTEM-PLANI 2: A = 00, B = 10, C = 11, D = 01)."""
    return PHASES[(int(bool(pins & PIN_Q1)), int(bool(pins & PIN_CLK)))]


def describe_pins(pins):
    parts = [f'faz {phase_of(pins)}', f'STOP={int(bool(pins & PIN_STOP))}',
             f'BUSACK={int(bool(pins & PIN_BUSACK))}']
    for bit, name in ((PIN_BUSREQ_OUT, '/BUSREQ düşük'), (PIN_RESET_OUT, '/RESET düşük'),
                      (PIN_BUS_DRIVEN, 'bus Arduino\'da')):
        if pins & bit:
            parts.append(name)
    parts.append('iz modu' if pins & PIN_TRACE_MODE else 'serbest mod')
    return ', '.join(parts)


# Arduino'nun işlemcisiyle sınırlı iz hızı: derlenmiş sketch'in komut sayımından kaba tahmin
# (çevrim başına ~25 µs darbe + örnekleme, ~55 µs Serial.write + gönderme kesmesi, ~8 µs CRC).
# ÖLÇÜLMEDİ.
ESTIMATED_DEVICE_RATE = 11_000


def estimate_rate(baud=SERIAL_BAUD):
    """Seri hattın izin verdiği en yüksek iz hızı (çevrim/s), 10 bit/bayt (8N1).

    Çevrim başına 6 bayt kayıt + çerçeve payı (5 başlık + 2 CRC + 4 ilk çevrim) / 40 kayıt.
    Arduino'nun işlemci süresi (darbe, örnekleme, CRC, seri kesmeleri) bunu düşürebilir;
    gerçek hız ölçülmedi.
    """
    per_cycle = REC_SIZE + (5 + 2 + 4) / RECS_PER_FRAME
    return baud / 10 / per_cycle


# ---------------------------------------------------------------------------
# Çerçeveleme
# ---------------------------------------------------------------------------

Frame = namedtuple('Frame', 'type seq payload')


def crc16(data, crc=0xFFFF):
    """CRC-16, polinom 0x8408 (yansıtılmış CCITT), son XOR yok; sketch'teki crc_update."""
    for b in data:
        b ^= crc & 0xFF
        b ^= (b << 4) & 0xFF
        crc = (((b << 8) | (crc >> 8)) ^ (b >> 4) ^ (b << 3)) & 0xFFFF
    return crc


def encode_frame(ftype, seq, payload=b''):
    payload = bytes(payload)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f'yük {len(payload)} bayt, en fazla {MAX_PAYLOAD}')
    body = bytes((ftype, seq, len(payload))) + payload
    return bytes((FRAME_SYNC1, FRAME_SYNC2)) + body + struct.pack('<H', crc16(body))


class FrameReader:
    """Bilgisayar tarafı çerçeve çözücü: bayt akışından çerçeveleri ayıklar.

    Bozuk çerçevede (CRC, uzunluk) yalnız ilk baytı atıp yeniden tarar; böylece kesik
    bir çerçevenin içine düşmüş sağlam çerçeve de kurtarılır. Araya giren çöp atlanır.
    """

    SYNC = bytes((FRAME_SYNC1, FRAME_SYNC2))

    def __init__(self):
        self.buf = bytearray()
        self.crc_errors = 0
        self.dropped = 0                  # atlanan bayt sayısı (çöp + bozuk çerçeve başları)

    def feed(self, data=b''):
        self.buf += data
        out = []
        while True:
            i = self.buf.find(self.SYNC)
            if i < 0:
                keep = 1 if self.buf[-1:] == self.SYNC[:1] else 0
                self.dropped += len(self.buf) - keep
                del self.buf[:len(self.buf) - keep]
                return out
            if i:
                self.dropped += i
                del self.buf[:i]
            if len(self.buf) < 5:
                return out
            n = self.buf[4]
            if n > MAX_PAYLOAD:
                self._skip()
                continue
            total = 5 + n + 2
            if len(self.buf) < total:
                return out
            body = bytes(self.buf[2:5 + n])
            if crc16(body) != self.buf[5 + n] | self.buf[6 + n] << 8:
                self.crc_errors += 1
                self._skip()
                continue
            out.append(Frame(body[0], body[1], body[3:]))
            del self.buf[:total]

    def _skip(self):
        del self.buf[:1]
        self.dropped += 1

    def resync(self):
        """Zaman aşımında: yarım kalmış çerçeveyi bırak (ilk baytı at, yeniden tara)."""
        if self.buf:
            self._skip()
        return self.feed()


class DeviceParser:
    """ta8_debug.ino'daki rx_byte durum makinesinin Python ikizi (FakeDevice kullanır).

    Sketch gibi çalışır: bozuk çerçevede SYNC aramaya döner, çerçeve içinde iki bayt
    arası FRAME_TIMEOUT_MS'yi aşarsa yarım çerçeveyi atar.
    """

    SYNC1, SYNC2, TYPE, SEQ, LEN, DATA, CRC_L, CRC_H = range(8)

    def __init__(self, on_frame, on_crc_error, clock=time.monotonic):
        self.on_frame, self.on_crc_error, self.clock = on_frame, on_crc_error, clock
        self.state = self.SYNC1
        self.errors = 0
        self.timeouts = 0
        self.last = 0.0
        self.type = self.seq = self.len = self.crc_l = 0
        self.buf = bytearray()

    def push(self, b):
        now = self.clock()
        if self.state != self.SYNC1 and now - self.last > FRAME_TIMEOUT_MS / 1000:
            self.state = self.SYNC1
            self.timeouts += 1
        self.last = now
        s = self.state
        if s == self.SYNC1:
            if b == FRAME_SYNC1:
                self.state = self.SYNC2
        elif s == self.SYNC2:
            if b == FRAME_SYNC2:
                self.state = self.TYPE
            elif b != FRAME_SYNC1:
                self.state = self.SYNC1
        elif s == self.TYPE:
            self.type, self.state = b, self.SEQ
        elif s == self.SEQ:
            self.seq, self.state = b, self.LEN
        elif s == self.LEN:
            if b > MAX_PAYLOAD:
                self.errors += 1
                self.state = self.SYNC1
            else:
                self.len, self.buf = b, bytearray()
                self.state = self.DATA if b else self.CRC_L
        elif s == self.DATA:
            self.buf.append(b)
            if len(self.buf) == self.len:
                self.state = self.CRC_L
        elif s == self.CRC_L:
            self.crc_l, self.state = b, self.CRC_H
        else:
            self.state = self.SYNC1
            body = bytes((self.type, self.seq, self.len)) + bytes(self.buf)
            if crc16(body) != self.crc_l | b << 8:
                self.errors += 1
                self.on_crc_error(self.type, self.seq)
            else:
                self.on_frame(self.type, self.seq, bytes(self.buf))


# ---------------------------------------------------------------------------
# Kayıtlar
# ---------------------------------------------------------------------------

def pack_record(ab, db, cw):
    """İz kaydı (6 bayt): AB lo, AB hi, DB, CW0, CW1, CW2."""
    return struct.pack('<HB', ab, db) + (cw & 0xFFFFFF).to_bytes(3, 'little')


def unpack_record(data, off=0):
    ab, db = struct.unpack_from('<HB', data, off)
    return ab, db, int.from_bytes(data[off + 3:off + 6], 'little')


def decode_trace_data(payload):
    """TRACE_DATA yükü → (ilk çevrim, [(çevrim, AB, DB, CW), ...])."""
    if len(payload) < 4 or (len(payload) - 4) % REC_SIZE:
        raise ArduError(f'TRACE_DATA yükü {len(payload)} bayt: biçim bozuk')
    start = struct.unpack_from('<I', payload)[0]
    rows = [(start + k, *unpack_record(payload, 4 + k * REC_SIZE))
            for k in range((len(payload) - 4) // REC_SIZE)]
    return start, rows


# ---------------------------------------------------------------------------
# Hatalar
# ---------------------------------------------------------------------------

class ArduError(Exception):
    """Arduino aracıyla ilgili her hata (bağlantı, protokol, doğrulama)."""


class ArduTimeout(ArduError):
    """Yanıt gelmedi."""


class ArduDeviceError(ArduError):
    """Cihaz RSP_ERROR ile yanıt verdi."""

    def __init__(self, cmd, code, pins, extra=b''):
        self.cmd, self.code, self.pins, self.extra = cmd, code, pins, bytes(extra)
        msg = f'{CMD_NAMES.get(cmd, f"komut {cmd:#04x}")}: {ERR_TEXT.get(code, f"hata {code}")}'
        if code == ERR_VERIFY and len(extra) >= 4:
            addr, exp, got = struct.unpack('<HBB', bytes(extra[:4]))
            msg += f' (adres {addr:04X}: yazılan {exp:02X}, okunan {got:02X})'
        super().__init__(f'{msg} [{describe_pins(pins)}]')

    @classmethod
    def from_payload(cls, payload):
        if len(payload) < 3:
            raise ArduError(f'RSP_ERROR yükü kısa: {payload.hex()}')
        return cls(payload[0], payload[1], payload[2], payload[3:])


# ---------------------------------------------------------------------------
# Taşıyıcılar: write(bytes), read(n, timeout) -> bytes (b'' = zaman aşımı), close()
# ---------------------------------------------------------------------------

class SerialTransport:
    """Gerçek seri port. pyserial yalnız burada (isteğe bağlı) içe aktarılır."""

    def __init__(self, port, baud=SERIAL_BAUD):
        try:
            import serial
        except ImportError:
            raise ArduError('pyserial kurulu değil; gerçek port için: py -3 -m pip install pyserial '
                            '(donanımsız denemek için --fake)') from None
        s = serial.Serial()
        s.port, s.baudrate, s.timeout, s.write_timeout = port, baud, 0.1, 2.0
        # DTR'yi baştan pasif tutmak çoğu sürücüde Mega'nın açılışta resetlenmesini önler.
        s.dtr = False
        s.rts = False
        try:
            s.open()
        except serial.SerialException as e:
            raise ArduError(f'{port} açılamadı: {e}') from None
        try:
            s.set_buffer_size(rx_size=1 << 20)     # Windows: iz akarken taşmasın
        except (AttributeError, ValueError, serial.SerialException):
            pass
        self.s = s

    def write(self, data):
        self.s.write(data)

    def read(self, n, timeout):
        self.s.timeout = max(timeout, 0.001)
        first = self.s.read(1)
        if not first:
            return b''
        waiting = self.s.in_waiting
        return first + (self.s.read(min(waiting, n - 1)) if waiting else b'')

    def close(self):
        self.s.close()


class FakeTransport:
    """FakeDevice'a bayt akışı seviyesinde bağlanan taşıyıcı (testler, --fake).

    rx_hook(sıra, çerçeve) -> bayt: cihazdan bilgisayara giden her çerçeveyi bozmak,
    kesmek ya da önüne çöp eklemek için. tx_hook(sıra, bayt) -> bayt: bilgisayarın
    her write çağrısı için. Cihaz yalnız bilgisayar yazınca konuştuğundan, boş okuma
    "zaman aşımı" demektir; gerçek bekleme yapılmaz, yalnız cihazın benzetimli saati
    (device.now) bekleme süresi kadar ilerletilir.
    """

    def __init__(self, device, rx_hook=None, tx_hook=None):
        self.device, self.rx_hook, self.tx_hook = device, rx_hook, tx_hook
        self.rx_frames = 0
        self.tx_writes = 0
        self._buf = bytearray()

    def write(self, data):
        data = bytes(data)
        if self.tx_hook:
            data = self.tx_hook(self.tx_writes, data)
        self.tx_writes += 1
        self.device.feed(data)

    def read(self, n, timeout=0.0):
        if not self._buf:
            for frame in self.device.pull_frames(8):
                if self.rx_hook:
                    frame = self.rx_hook(self.rx_frames, frame)
                self.rx_frames += 1
                self._buf += frame
        out = bytes(self._buf[:n])
        del self._buf[:n]
        if not out:
            self.device.now += max(timeout, 0.0)      # bilgisayar bu kadar bekledi
        return out

    def close(self):
        pass


# ---------------------------------------------------------------------------
# İstemci
# ---------------------------------------------------------------------------

Hello = namedtuple('Hello', 'proto fw max_payload max_block recs_per_frame mode ident')
Status = namedtuple('Status', 'mode pins phase cycle ab db cw rx_errors rx_timeouts bus_hold')
TraceResult = namedtuple('TraceResult', 'rows reason done cycle pins seconds')
Step = namedtuple('Step', 'reason pins cycle ab db cw')


class ArduClient:
    """Protokol istemcisi; gerçek cihaz da sahte cihaz da aynı kodla konuşulur."""

    def __init__(self, transport, timeout=1.0, retries=2):
        self.t = transport
        self.timeout = timeout
        self.retries = retries
        self.reader = FrameReader()
        self._frames = deque()
        self._seq = 0
        self.side_rows = []   # iz modunda bellek/bus komutları sırasında olan commit'ler
        self.stale = 0        # sıra numarası tutmayan (eski) yanıtlar
        self.boots = 0        # görülen açılış duyuruları (Arduino resetlendi)
        self.retried = 0      # yeniden gönderilen istekler

    def close(self):
        self.t.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- alt katman ------------------------------------------------------
    def _send(self, cmd, payload=b''):
        self._seq = self._seq % 255 + 1           # 1..255; 0 cihazın kendiliğinden gönderdikleri
        self.t.write(encode_frame(cmd, self._seq, payload))
        return self._seq

    def _next_frame(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            if self._frames:
                return self._frames.popleft()
            remaining = deadline - time.monotonic()
            data = self.t.read(4096, remaining) if remaining > 0 else b''
            if data:
                self._frames.extend(self.reader.feed(data))
                continue
            self._frames.extend(self.reader.resync())
            if self._frames:
                continue
            return None

    def _other(self, f):
        """İstenen yanıt beklenirken gelen başka çerçeve."""
        if f.type == TRACE_DATA:
            _, rows = decode_trace_data(f.payload)
            for row in rows:
                if not self.side_rows or row[0] > self.side_rows[-1][0]:
                    self.side_rows.append(row)
        elif f.seq == 0 and f.type == CMD_HELLO | RSP_FLAG:
            self.boots += 1
        else:
            self.stale += 1

    def request(self, cmd, payload=b'', timeout=None, retries=None):
        """İstek gönderir, yanıt yükünü döndürür. Zaman aşımında ya da cihaz çerçeveyi
        bozuk aldığında (ERR_CRC) yeniden dener; cihaz hatasında ArduDeviceError."""
        timeout = self.timeout if timeout is None else timeout
        retries = self.retries if retries is None else retries
        why = ''
        for attempt in range(retries + 1):
            if attempt:
                self.retried += 1
            seq = self._send(cmd, payload)
            while True:
                f = self._next_frame(timeout)
                if f is None:
                    why = 'zaman aşımı'
                    break
                if f.type == RSP_ERROR and len(f.payload) >= 2 and f.payload[1] == ERR_CRC:
                    why = 'cihaz çerçeveyi bozuk aldı'
                    break
                if f.seq != seq or f.type == TRACE_DATA:
                    self._other(f)
                    continue
                if f.type == RSP_ERROR:
                    raise ArduDeviceError.from_payload(f.payload)
                if f.type != cmd | RSP_FLAG:
                    raise ArduError(f'{CMD_NAMES.get(cmd)}: beklenmeyen yanıt tipi {f.type:#04x}')
                return f.payload
        raise ArduTimeout(f'{CMD_NAMES.get(cmd, cmd)}: yanıt alınamadı ({retries + 1} deneme, '
                          f'son durum: {why})')

    def _abort(self):
        self.t.write(b'\x00')                     # iz sırasında gelen her bayt izi durdurur

    def take_side_rows(self):
        rows, self.side_rows = self.side_rows, []
        return rows

    # --- komutlar --------------------------------------------------------
    def hello(self, timeout=None, retries=None):
        p = self.request(CMD_HELLO, timeout=timeout, retries=retries)
        if len(p) < 7:
            raise ArduError(f'HELLO yanıtı kısa: {p.hex()}')
        h = Hello(p[0], f'{p[1]}.{p[2]}', p[3], p[4], p[5], p[6], p[7:].decode('ascii', 'replace'))
        if h.proto != PROTO_VERSION or h.ident != DEVICE_ID:
            raise ArduError(f'cihaz {h.ident!r} protokol {h.proto}; beklenen {DEVICE_ID!r} '
                            f'protokol {PROTO_VERSION} (sketch ile ardu.py aynı sürüm mü?)')
        return h

    def wait_ready(self, boot_wait=3.0):
        """Bağlanınca: cihaz hemen yanıt vermezse açılışını (DTR reseti, bootloader) bekler."""
        try:
            return self.hello(timeout=0.3, retries=0)
        except ArduTimeout:
            pass
        deadline = time.monotonic() + boot_wait
        while (remaining := deadline - time.monotonic()) > 0:
            f = self._next_frame(remaining)
            if f is None:
                break
            if f.seq == 0 and f.type == CMD_HELLO | RSP_FLAG:
                self.boots += 1
                break
        return self.hello()

    def status(self):
        p = self.request(CMD_STATUS)
        mode, pins, cycle = struct.unpack_from('<BBI', p)
        ab, db, cw = unpack_record(p, 6)
        rx_err, rx_to, hold = struct.unpack_from('<HHB', p, 12)
        return Status(mode, pins, phase_of(pins), cycle, ab, db, cw, rx_err, rx_to, bool(hold))

    def set_mode(self, mode):
        return self.request(CMD_MODE, bytes((mode,)))[0]

    def reset(self):
        """Makineyi resetler. İz modunda makine 0. çevrimin D fazında kalır.
        Döner: reset bırakıldıktan sonra C'den çıkmak için verilen MCLK darbesi sayısı."""
        timeout = (RESET_HOLD_MS + RESET_TIMEOUT_MS + FREE_CLOCK_CHECK_MS) / 1000 + 1.0
        p = self.request(CMD_RESET, timeout=timeout)
        self.side_rows.clear()
        return struct.unpack_from('<I', p, 1)[0]

    def step(self):
        p = self.request(CMD_STEP, retries=0)
        reason, pins, cycle = struct.unpack_from('<BBI', p)
        return Step(reason, pins, cycle, *unpack_record(p, 6))

    def clock(self, n):
        """n ham MCLK darbesi (faz faz adım). Olan commit'ler side_rows'a eklenir."""
        p = self.request(CMD_CLOCK, struct.pack('<H', n), retries=0)
        pins, cycle = struct.unpack('<BI', p)
        return pins, cycle

    def bus(self, hold):
        p = self.request(CMD_BUS, bytes((1 if hold else 0,)))
        return bool(p[0]), p[1]

    def read(self, addr, n):
        out = bytearray()
        while len(out) < n:
            a, k = (addr + len(out)) & 0xFFFF, min(MAX_BLOCK, n - len(out))
            p = self.request(CMD_READ, struct.pack('<HB', a, k))
            if struct.unpack_from('<H', p)[0] != a or len(p) != 2 + k:
                raise ArduError(f'READ yanıtı uyuşmuyor (adres {a:04X}, {k} bayt istendi)')
            out += p[2:]
        return bytes(out)

    def write(self, addr, data, verify=True):
        data = bytes(data)
        for off in range(0, len(data), MAX_BLOCK):
            a, chunk = (addr + off) & 0xFFFF, data[off:off + MAX_BLOCK]
            p = self.request(CMD_WRITE, struct.pack('<HB', a, WRITE_VERIFY if verify else 0) + chunk)
            if struct.unpack('<HB', p) != (a, len(chunk)):
                raise ArduError(f'WRITE yanıtı uyuşmuyor (adres {a:04X})')

    def load(self, addr, data, verify=True):
        """Yükleme modu: bus'ı al, bloklar halinde yaz (her bayt geri okunur), bütün bloğu
        ayrıca geri oku ve karşılaştır, bus'ı bırak. Döner: yazılan bayt sayısı."""
        data = bytes(data)
        self.bus(True)
        try:
            self.write(addr, data, verify=verify)
            back = self.read(addr, len(data)) if verify else data
        finally:
            try:
                self.bus(False)
            except ArduError:
                pass
        if back != data:
            i = next(k for k in range(len(data)) if back[k] != data[k])
            raise ArduError(f'doğrulama: {addr + i:04X} adresine {data[i]:02X} yazıldı, '
                            f'{back[i]:02X} okundu')
        return len(data)

    def trace(self, n, on_rows=None, first_index=None, frame_timeout=2.0):
        """n çevrimlik iz. on_rows verilmezse satırlar listede döner; verilirse her çerçevenin
        satırlarıyla çağrılır, False döndürürse iz durdurulur. first_index verilirse ilk
        çerçevenin o çevrimle başlaması denetlenir (kayıp çerçeve hizayı kaydırmasın)."""
        if not 0 < n <= 0xFFFFFFFF:
            raise ValueError('çevrim sayısı 1..2^32-1')
        seq = self._send(CMD_TRACE, struct.pack('<I', n))
        rows = [] if on_rows is None else None
        expected, got, stopped, lost = first_index, 0, False, None
        t0 = time.monotonic()
        while True:
            f = self._next_frame(frame_timeout)
            if f is None:
                raise ArduTimeout(f'iz akışı {frame_timeout:.1f} s kesildi ({got} çevrim alındı)')
            if f.seq != seq:
                self._other(f)
                continue
            if f.type == TRACE_DATA:
                start, batch = decode_trace_data(f.payload)
                if expected is not None and start != expected and lost is None:
                    lost = (expected, start)
                    if not stopped:
                        self._abort()
                        stopped = True
                expected = start + len(batch)
                got += len(batch)
                if stopped:
                    continue
                if rows is not None:
                    rows.extend(batch)
                elif on_rows(batch) is False:
                    self._abort()
                    stopped = True
            elif f.type == CMD_TRACE | RSP_FLAG:
                reason, done, cycle, pins = struct.unpack('<BIIB', f.payload)
                if lost:
                    raise ArduError(f'iz çerçevesi kayboldu: çevrim {lost[0]}..{lost[1] - 1} '
                                    'gelmedi (bozuk çerçeve ya da taşma); bu iz geçersiz')
                if got != done and not stopped:
                    raise ArduError(f'iz eksik: cihaz {done} çevrim gönderdi, {got} alındı')
                return TraceResult(rows, reason, done, cycle, pins, time.monotonic() - t0)
            elif f.type == RSP_ERROR:
                raise ArduDeviceError.from_payload(f.payload)
            else:
                self.stale += 1


def open_serial(port, baud=SERIAL_BAUD, timeout=1.0, boot_wait=3.0):
    """Gerçek karta bağlanır (pyserial gerekir) ve HELLO ile doğrular."""
    client = ArduClient(SerialTransport(port, baud), timeout=timeout)
    try:
        client.info = client.wait_ready(boot_wait)
    except BaseException:
        client.close()
        raise
    return client


# ---------------------------------------------------------------------------
# İz karşılaştırma ve program yükleme
# ---------------------------------------------------------------------------

TraceDiff = namedtuple('TraceDiff', 'index fields message ref got before')


def diff_fields(ref, got):
    """İki iz satırında farklı olan alanlar: AB, DB, CW.<alan> (SISTEM-PLANI 4.2)."""
    out = []
    if ref[1] != got[1]:
        out.append('AB')
    if ref[2] != got[2]:
        out.append('DB')
    if ref[3] != got[3]:
        fr, fg = vectors.cw_fields(ref[3]), vectors.cw_fields(got[3])
        out += ['CW.' + k for k in vectors.CW_FIELDS if fr[k] != fg[k]]
    return out


class TraceCompare:
    """Cihazdan gelen satırları MicroEmu'nun izine karşı akarken karşılaştırır.

    Bellek bütün iz için tutulmaz (1.000.000 çevrim için de çalışır). Emülatör Arduino
    saatindeki makineyi modeller: SLOW modda VRAM hep CPU'nun, yani WAIT yok
    (Bus(vga_model=False)); RAM açılışta sıfır kabul edilir.
    """

    def __init__(self, image, dip=0, keep=False, context=3):
        bus = Bus()
        bus.load(bytes(image))
        bus.dip = dip
        roms, alu_tables = _tables()
        self.emu = MicroEmu(bus, roms, alu_tables)
        self.emu.trace = []
        self.count = 0
        self.diff = None
        self.rows = [] if keep else None
        self._recent = deque(maxlen=context)

    def feed(self, rows):
        if self.diff is not None:
            return False
        need = len(rows)
        while len(self.emu.trace) < need and not self.emu.halted:
            self.emu.cycle()
        ref = self.emu.trace[:need]
        del self.emu.trace[:need]
        idx, msg = vectors.compare_traces(ref, rows)
        if idx is not None:
            r = ref[idx] if idx < len(ref) else None
            g = rows[idx] if idx < len(rows) else None
            fields = diff_fields(r, g) if r and g else ['uzunluk']
            detail = msg.split(': ', 1)[1] if ': ' in msg else msg
            before = (list(self._recent) + ref[:idx])[-self._recent.maxlen:]
            self.diff = TraceDiff(self.count + idx, fields, f'çevrim {self.count + idx}: {detail}',
                                  r, g, before)
            return False
        self._recent.extend(ref)
        self.count += need
        if self.rows is not None:
            self.rows.extend(rows)
        return True


def ram_segments(prog):
    """Assembler çıktısının RAM'e (8000–EFFF) düşen parçaları ve dışarıda kalanlar.

    Döner: ([(adres, bayt), ...], [(bölge, adres, uzunluk), ...]). ROM bölümü flash'a
    T48 ile yazılır; VRAM ve I/O yüklenmez.
    """
    segs, other = [], []
    for start, length in prog.ranges():
        end = start + length
        lo, hi = max(start, ROM_END), min(end, VRAM_BASE)
        if lo < hi:
            segs.append((lo, bytes(prog.image[lo:hi])))
        if start < ROM_END:
            other.append(('ROM', start, min(end, ROM_END) - start))
        if end > VRAM_BASE:
            s = max(start, VRAM_BASE)
            other.append(('VRAM/I/O', s, end - s))
    return segs, other


def load_segments(client, segments, verify=True):
    """Parçaları sırayla yükler (her biri ayrı ayrı doğrulanır). Döner: toplam bayt."""
    return sum(client.load(addr, data, verify=verify) for addr, data in segments)


# ---------------------------------------------------------------------------
# Sahte cihaz: sketch'in Python ikizi
# ---------------------------------------------------------------------------

class _FaultyEmu(MicroEmu):
    """MicroEmu; kontrol latch'inin bir çıkışı yapışık olabilir (makine de buna göre çalışır)."""

    def __init__(self, bus, stuck=None):
        self.stuck = stuck                        # (bit, 0|1) ya da None
        super().__init__(bus, *_tables())

    def control_word(self):
        cw = super().control_word()
        if self.stuck is not None:
            bit, val = self.stuck
            cw = cw | 1 << bit if val else cw & ~(1 << bit)
        return cw


class FakeDevice:
    """ta8_debug.ino'nun Python ikizi: aynı çerçeveler, aynı komutlar, aynı hata kodları.

    Makine tarafı: MicroEmu + Bus ve MCLK kenarında saatlenen flip-flop'ların modeli
    (Johnson fazı, /BUSREQ'in 2 FF'lik senkronlayıcısı, BUSACK). Serbest modda
    makinenin kendi saati yalnız bus el sıkışması sırasında modellenir; makine komutlar
    arasında "koşmaz".

    Hata ekleme: busack=False (BUSACK hiç gelmez), db_flip={çevrim: maske} (kayıtta DB
    bitleri ters: kötü kablo), cw_stuck=(bit, 0|1) (kontrol latch'i çıkışı yapışık;
    makine de yanlış çalışır).
    """

    def __init__(self, rom=None, *, dip=0, busack=True, db_flip=None, cw_stuck=None,
                 announce=False):
        self.bus = Bus()
        if rom is not None:
            rom = bytes(rom[:ROM_END])
            self.bus.mem[:len(rom)] = rom             # flash'a yazılmış program
        self.bus.dip = dip
        self.emu = _FaultyEmu(self.bus, cw_stuck)
        self.emu.trace = []
        self.busack_works = busack
        self.db_flip = dict(db_flip or {})
        # sketch'teki g_* durumları
        self.mode = MODE_FREE
        self.bus_hold = False
        self.bus_driven = False
        self.cycle = 0
        self._tbuf = bytearray()
        self._tcount = 0
        self._tseq = 0
        # makinenin MCLK ile saatlenen kısımları
        self.phase = 'C'
        self.busreq = False                           # Arduino /BUSREQ'i indiriyor
        self.sync1 = self.brq_s = False               # 2 FF'lik senkronlayıcı
        self.busack = False
        self.reset_out = False
        self.last_rec = bytes(REC_SIZE)
        # seri hat; zaman benzetimli: bayt başına 10 µs (1 Mbaud), boş beklemeler FakeTransport'tan
        self.now = 0.0
        self.parser = DeviceParser(self._handle_command, self._crc_error, clock=lambda: self.now)
        self._rx = bytearray()                        # Serial RX tamponu
        self._out = deque()                           # gönderilecek çerçeveler
        self._job = None                              # akan iz (üreteç)
        if announce:
            self._cmd_hello(0)

    # --- seri hat ----------------------------------------------------------
    def feed(self, data):
        self._rx += data
        self._process_rx()

    def _process_rx(self):
        while self._rx and self._job is None:
            b = self._rx[0]
            del self._rx[:1]
            self.now += 1e-5
            self.parser.push(b)

    def pull_frames(self, max_frames=8):
        out = []
        while len(out) < max_frames:
            if self._out:
                out.append(self._out.popleft())
            elif self._job is not None:
                try:
                    next(self._job)
                except StopIteration:
                    self._job = None
                    self._process_rx()
            else:
                break
        return out

    def _send(self, ftype, seq, payload=b''):
        self._out.append(encode_frame(ftype, seq, payload))

    def _send_error(self, cmd, seq, code, extra=b''):
        self._send(RSP_ERROR, seq, bytes((cmd, code, self._pins())) + bytes(extra[:8]))

    def _crc_error(self, ftype, seq):
        self._send_error(ftype, seq, ERR_CRC)

    # --- makine modeli -----------------------------------------------------
    def _stop(self):
        return self.brq_s or self.emu.halted          # STOP = BRQ_s | HALT_L ... (3.3)

    def _pins(self):
        q1, q2 = {'A': (0, 0), 'B': (1, 0), 'C': (1, 1), 'D': (0, 1)}[self.phase]
        v = (PIN_Q1 if q1 else 0) | (PIN_CLK if q2 else 0)
        v |= PIN_STOP if self._stop() else 0
        v |= PIN_BUSACK if self.busack else 0
        v |= PIN_BUSREQ_OUT if self.busreq else 0
        v |= PIN_RESET_OUT if self.reset_out else 0
        v |= PIN_BUS_DRIVEN if self.bus_driven else 0
        v |= PIN_TRACE_MODE if self.mode == MODE_TRACE else 0
        return v

    def _edge(self, record=True):
        """Bir MCLK yükselen kenarı. Bütün FF'ler kenar öncesi değerleri örnekler.
        B→C commit'tir: MicroEmu bir çevrim çalışır. Döner: (çevrim, kayıt) ya da None."""
        stop = self._stop()
        busack_d = self.brq_s and self.phase == 'C' and self.busack_works
        sync1_d = self.busreq
        result = None
        if self.phase == 'B':
            self.emu.cycle()
            _, ab, db, cw = self.emu.trace.pop()
            if record:
                idx = self.cycle
                self.cycle += 1
                db ^= self.db_flip.get(idx, 0)
                self.last_rec = pack_record(ab, db, cw)
                result = (idx, self.last_rec)
            nxt = 'C'
        elif self.phase == 'C':
            nxt = 'C' if stop else 'D'
        elif self.phase == 'D':
            nxt = 'A'                                 # WAIT yok: SLOW'da VRAM hep CPU'nun
        else:
            nxt = 'B'
        self.phase = nxt
        self.busack = busack_d
        self.brq_s = self.sync1
        self.sync1 = sync1_d
        return result

    def _tick(self):                                  # sketch: mclk_tick
        return self._edge(record=True)

    def _run_cycle(self):                             # sketch: run_cycle
        for _ in range(STALL_PULSES):
            r = self._tick()
            if r is not None:
                return (END_OK if self.phase == 'C' else END_PHASE), r[0], r[1]
        return END_STALL, self.cycle, bytes(REC_SIZE)

    def _emit(self, idx, rec):                        # sketch: emit_record
        if self._tcount == 0:
            self._tbuf = bytearray(struct.pack('<I', idx))
        self._tbuf += rec
        self._tcount += 1
        if self._tcount == RECS_PER_FRAME:
            self._flush()

    def _flush(self):                                 # sketch: flush_trace
        if self._tcount:
            self._send(TRACE_DATA, self._tseq, self._tbuf)
            self._tcount = 0

    # --- bus -----------------------------------------------------------------
    def _bus_acquire(self):
        self.busreq = True
        for _ in range(64):                           # kartta: BUSACK_TIMEOUT_MS
            if self.busack:
                return 0
            if self.mode == MODE_TRACE:
                r = self._tick()
                if r is not None:
                    self._emit(*r)
            else:
                self._edge(record=False)              # makinenin kendi saati
        self.busreq = False
        return ERR_BUSACK_TIMEOUT

    def _bus_release(self):
        self.bus_driven = False
        self.busreq = False
        if self.mode == MODE_FREE:
            for _ in range(64):
                if not self.busack:
                    break
                self._edge(record=False)

    def _bus_release_all(self):
        self._bus_release()
        self.bus_hold = False

    def _mem_read(self, addr):
        """Arduino'nun /ARD_RD ile gördüğü değer (yan etkisiz: KCLR commit'te çalışır)."""
        if addr < VRAM_BASE:
            return self.bus.mem[addr]
        if addr < IO_BASE:
            return 0                                  # VRAM okunmaz: DB pull-down'ları
        reg = addr & 7
        if reg == 0:
            return self.bus.kbd_byte if self.bus.krdy else 0xFF
        if reg == 1:
            return self.bus.krdy << 7 | self.bus.vwr() << 6 | (self.bus.dip & 0x3F)
        return 0

    def _mem_write(self, addr, value):
        if addr < ROM_END:
            return                                    # flash: /WE = VCC
        if addr < VRAM_BASE:
            self.bus.mem[addr] = value
        elif addr < IO_BASE:
            self.bus.vram[addr & 0x7FF] = value       # SLOW modda VRAM CPU tarafında
        # I/O (LED): latch CLK ile, commit'te yüklenir; BUSACK sırasında commit yok

    def _read_byte(self, addr):
        if not self.busack:
            self.bus_driven = False
            return None
        self.bus_driven = True
        return self._mem_read(addr & 0xFFFF)

    def _write_byte(self, addr, value):
        if not self.busack:
            self.bus_driven = False
            return False
        self.bus_driven = True
        self._mem_write(addr & 0xFFFF, value)
        return True

    # --- komutlar ----------------------------------------------------------
    def _handle_command(self, ftype, seq, p):
        handler = {
            CMD_HELLO: lambda: self._cmd_hello(seq),
            CMD_STATUS: lambda: self._cmd_status(seq),
            CMD_MODE: lambda: self._cmd_mode(seq, p),
            CMD_RESET: lambda: self._cmd_reset(seq),
            CMD_TRACE: lambda: self._cmd_trace(seq, p),
            CMD_STEP: lambda: self._cmd_step(seq, p),
            CMD_CLOCK: lambda: self._cmd_clock(seq, p),
            CMD_READ: lambda: self._cmd_read(seq, p),
            CMD_WRITE: lambda: self._cmd_write(seq, p),
            CMD_BUS: lambda: self._cmd_bus(seq, p),
        }.get(ftype)
        if handler is None:
            self._send_error(ftype, seq, ERR_UNKNOWN_CMD)
        else:
            handler()

    def _cmd_hello(self, seq):
        self._send(CMD_HELLO | RSP_FLAG, seq,
                   bytes((PROTO_VERSION, FW_MAJOR, FW_MINOR, MAX_PAYLOAD, MAX_BLOCK,
                          RECS_PER_FRAME, self.mode)) + DEVICE_ID.encode('ascii'))

    def _cmd_status(self, seq):
        self._send(CMD_STATUS | RSP_FLAG, seq,
                   struct.pack('<BBI', self.mode, self._pins(), self.cycle) + self.last_rec
                   + struct.pack('<HHB', self.parser.errors, self.parser.timeouts, self.bus_hold))

    def _cmd_mode(self, seq, p):
        if len(p) != 1:
            return self._send_error(CMD_MODE, seq, ERR_BAD_LEN)
        if p[0] > MODE_TRACE:
            return self._send_error(CMD_MODE, seq, ERR_BAD_ARG, p)
        self._bus_release_all()
        self.mode = p[0]
        self._send(CMD_MODE | RSP_FLAG, seq, bytes((self.mode,)))

    def _cmd_reset(self, seq):
        self._bus_release_all()
        self.reset_out = True
        # Reset hemen etki eder: Johnson C'ye, latch NOP'a, PC/AR/X/F/STEP 0, SP FF, BUSACK 0.
        self.phase = 'C'
        self.busack = False
        self.emu.reset()
        self.reset_out = False
        pulses = 0
        if self.mode == MODE_TRACE:
            while self.phase == 'C':
                self._edge(record=False)              # C'de commit olmaz
                pulses += 1
                if pulses > 100_000:
                    return self._send_error(CMD_RESET, seq, ERR_RESET_TIMEOUT)
        self.cycle = 0
        self._send(CMD_RESET | RSP_FLAG, seq, struct.pack('<BI', self._pins(), pulses))

    def _cmd_trace(self, seq, p):
        if len(p) != 4:
            return self._send_error(CMD_TRACE, seq, ERR_BAD_LEN)
        if self.mode != MODE_TRACE:
            return self._send_error(CMD_TRACE, seq, ERR_MODE)
        if self.bus_hold:
            return self._send_error(CMD_TRACE, seq, ERR_BUS_HELD)
        self._job = self._trace_job(seq, struct.unpack('<I', p)[0])

    def _trace_job(self, seq, count):
        self._tseq = seq
        done, reason = 0, END_OK
        while done < count:
            reason, idx, rec = self._run_cycle()
            if reason == END_STALL:
                break
            self._emit(idx, rec)
            done += 1
            if reason != END_OK:
                break
            if rec[5] & 1 << (CW_HALT_BIT - 16):
                reason = END_HALT
                break
            if self._rx:                              # sketch: Serial.available()
                reason = END_ABORT
                break
            if self._tcount == 0:
                yield                                 # bir çerçeve gitti; bilgisayara sıra
        self._flush()
        self._send(CMD_TRACE | RSP_FLAG, seq,
                   struct.pack('<BIIB', reason, done, self.cycle, self._pins()))

    def _cmd_step(self, seq, p):
        if p:
            return self._send_error(CMD_STEP, seq, ERR_BAD_LEN)
        if self.mode != MODE_TRACE:
            return self._send_error(CMD_STEP, seq, ERR_MODE)
        if self.bus_hold:
            return self._send_error(CMD_STEP, seq, ERR_BUS_HELD)
        reason, idx, rec = self._run_cycle()
        self._send(CMD_STEP | RSP_FLAG, seq, struct.pack('<BBI', reason, self._pins(), idx) + rec)

    def _cmd_clock(self, seq, p):
        if len(p) != 2:
            return self._send_error(CMD_CLOCK, seq, ERR_BAD_LEN)
        if self.mode != MODE_TRACE:
            return self._send_error(CMD_CLOCK, seq, ERR_MODE)
        if self.bus_hold:
            return self._send_error(CMD_CLOCK, seq, ERR_BUS_HELD)
        self._tseq = seq
        for _ in range(struct.unpack('<H', p)[0]):
            r = self._tick()
            if r is not None:
                self._emit(*r)
        self._flush()
        self._send(CMD_CLOCK | RSP_FLAG, seq, struct.pack('<BI', self._pins(), self.cycle))

    def _mem_begin(self, seq):
        self._tseq = seq
        if self.bus_hold:
            return 0 if self.busack else ERR_BUSACK_LOST
        return self._bus_acquire()

    def _mem_fail(self, cmd, seq, code, extra=b''):
        self._bus_release_all()
        self._flush()
        self._send_error(cmd, seq, code, extra)

    def _mem_end(self):
        self.bus_driven = False
        if not self.bus_hold:
            self._bus_release()
        self._flush()

    def _cmd_read(self, seq, p):
        if len(p) != 3:
            return self._send_error(CMD_READ, seq, ERR_BAD_LEN)
        addr, n = struct.unpack('<HB', p)
        if not 0 < n <= MAX_BLOCK:
            return self._send_error(CMD_READ, seq, ERR_BAD_ARG, p[2:])
        err = self._mem_begin(seq)
        if err:
            return self._mem_fail(CMD_READ, seq, err)
        data = bytearray()
        for i in range(n):
            v = self._read_byte(addr + i)
            if v is None:
                return self._mem_fail(CMD_READ, seq, ERR_BUSACK_LOST)
            data.append(v)
        self._mem_end()
        self._send(CMD_READ | RSP_FLAG, seq, struct.pack('<H', addr) + data)

    def _cmd_write(self, seq, p):
        if not 4 <= len(p) <= 3 + MAX_BLOCK:
            return self._send_error(CMD_WRITE, seq, ERR_BAD_LEN)
        addr, flags = struct.unpack_from('<HB', p)
        data = p[3:]
        err = self._mem_begin(seq)
        if err:
            return self._mem_fail(CMD_WRITE, seq, err)
        for i, v in enumerate(data):
            a = (addr + i) & 0xFFFF
            if not self._write_byte(a, v):
                return self._mem_fail(CMD_WRITE, seq, ERR_BUSACK_LOST)
            if flags & WRITE_VERIFY:
                got = self._read_byte(a)
                if got is None:
                    return self._mem_fail(CMD_WRITE, seq, ERR_BUSACK_LOST)
                if got != v:
                    return self._mem_fail(CMD_WRITE, seq, ERR_VERIFY, struct.pack('<HBB', a, v, got))
        self._mem_end()
        self._send(CMD_WRITE | RSP_FLAG, seq, struct.pack('<HB', addr, len(data)))

    def _cmd_bus(self, seq, p):
        if len(p) != 1:
            return self._send_error(CMD_BUS, seq, ERR_BAD_LEN)
        self._tseq = seq
        if p[0]:
            if not self.bus_hold:
                err = self._bus_acquire()
                if err:
                    return self._mem_fail(CMD_BUS, seq, err)
                self.bus_hold = True
        else:
            self._bus_release_all()
        self._flush()
        self._send(CMD_BUS | RSP_FLAG, seq, bytes((self.bus_hold, self._pins())))
