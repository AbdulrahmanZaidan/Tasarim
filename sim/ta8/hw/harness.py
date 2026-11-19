"""HwCpu: çip seviyesindeki TA-8 netlist'ini (ta8.hw.cpu) zamanlı çekirdekte çalıştıran
test tezgâhı ve MicroEmu ile karşılaştırma yardımcıları.

    hw = HwCpu(prog.image, corner='typ')     # MCLK 4 MHz (1 MHz CPU)
    hw.run(10_000)                           # açılış + reset + bırakma, HALT'ta durur
    emu = emu_like(hw, prog.image, 10_000)   # aynı başlangıç durumuyla MicroEmu
    assert compare(hw, emu) == []            # iz, registerlar, RAM, VRAM, LED

İz: her CLK (commit) yükselen kenarında (çevrim, AB, DB, CW); CW = 273 kontrol
latch'inin çıkışları. Kenar anında çipler henüz tepki vermediği için değerler
commit öncesi (B fazı) değerleridir: MicroEmu.trace ile aynı anlam.

Klavye (M7 yok): KRDY ve 540'ın girişleri test tezgâhından; okuma sonrası
temizleme ve byte'lar arası süre sim/ta8/bus.py'deki modelin aynısı (harness
kendi içinde bir Bus nesnesini klavye durum makinesi olarak kullanır; her
commit'te /KBD_RD düşükse bus.read(F800), sonra bus.tick(1)). WAIT beklemesi
sırasında klavye saati ilerlemez (MicroEmu'dan farklı; testlerde birlikte
kullanılmıyor).

Zamanlama ölçümü (ISA-v0-sentez 5.4 yolları; her çevrimde, koşu boyunca en kötü):
  yol1  LCLK↑ → commit'te örneklenen girişlerin (R0..7, Znew Cnew Nnew Vnew, DB0..7)
        son değişimi; pencere = LCLK↑ → CLK↑ (1 MHz'de 750 ns)
  yol2  CLK↑ → 273 girişlerinin (uROM çıkışları) son değişimi; pencere = CLK↑ → LCLK↑
  yol3  LCLK↑ → Johnson Q2 girişinin (Q2_D) son değişimi, D→A kenarından önce;
        pencere = LCLK↑ → o MCLK kenarı. Ayrıca MCLK (C→D) kenarından ölçülmüşü
        (`yol3_mclk`): gerçek sınır budur, çünkü D→A kararı LCLK'e değil MCLK'ye
        göre örneklenir.
"""

import time

from .. import isa
from ..bus import Bus, IO_BASE, VRAM_BASE
from ..emu_micro import MicroEmu
from ..vectors import compare_traces
from . import cpu
from .kernel import NEVER, Sim

MCLK_HALF = {4: 125, 6: 83, 8: 62}       # MHz → yarım periyot (ns); 6 ve 8 MHz yuvarlanmış
P1_NETS = [f'R{i}' for i in range(8)] + ['Znew', 'Cnew', 'Nnew', 'Vnew'] + [f'DB{i}' for i in range(8)]
STATE_KEYS = ('pc', 'ar', 'x', 'sp', 'a', 'ir', 'step', 'z', 'c', 'n', 'v')


class HwCpu:
    """Çip seviyesindeki CPU + test tezgâhı.

    program   ROM imajı (ilk 32 KB kullanılır; prog.image verilebilir)
    corner    'typ' | 'max' (gecikme sütunu)
    mclk_mhz  4 (1 MHz CPU), 6 ya da 8; ya da mclk_half ile yarım periyot (ns)
    power_up  'zero' | 'random' (seed ile): FF, register ve SRAM içerikleri
    stepmode, micro, vwr, dip   anahtarların başlangıç değerleri
    keys      klavyeden gönderilecek scan code'lar (bus.py zamanlamasıyla)
    vga       'taklit' (VWR_s = vwr anahtarı) ya da 'netlist' (M6 zamanlaması devrede, 25 MHz
              OSC25; VWR_s M1'de VWR'den senkronlanır, vwr yok sayılır). netlist kipi ~25 kat yavaş.
    """

    def __init__(self, program=b'', *, corner='typ', mclk_mhz=4, mclk_half=None,
                 power_up='zero', seed=1, checks=True, stepmode=0, micro=0, vwr=1, dip=0,
                 keys=(), urom=None, alu_tables=None, rom_speed=90, bank=0, wait_fix=True,
                 vga='taklit'):
        self.half = mclk_half or MCLK_HALF[mclk_mhz]
        self.cycle_ns = 8 * self.half
        self.sim = sim = Sim(corner=corner, checks=checks, power_up=power_up, seed=seed)
        self.board = cpu.build(sim, program=program, urom=urom, alu_tables=alu_tables,
                               rom_speed=rom_speed, bank=bank, mclk_half=self.half,
                               wait_fix=wait_fix, vga=vga)
        self.vga = vga
        self.ram_initial = self.vram_initial = None   # reset ilk bırakıldığında alınır
        self.release_time = None
        self.dip = dip
        sim.set('STEPMODE', stepmode)
        sim.set('MICRO', micro)
        if vga == 'taklit':
            sim.set('VWR_s', vwr)
        sim.set_bus('DIP', 6, dip)
        sim.set('/RESET', 0)                  # açılış: reset basılı
        self.kbd = Bus()                      # yalnız klavye durum makinesi olarak
        if keys:
            self.kbd.press(*keys)
        ix = sim.index
        self._i_ab = [ix[f'AB{i}'] for i in range(16)]
        self._i_db = [ix[f'DB{i}'] for i in range(8)]
        self._i_cw = [ix[n] for n in cpu.CW_L]
        self._i_cwin = [ix[n] for n in cpu.CW_NAMES]
        self._i_p1 = [ix[n] for n in P1_NETS]
        for name in ('/RESET_s', 'Q1', 'CLK', 'STOP', '/GO', '/KBD_RD', 'VWR_s', 'Q2_D', '/WAIT'):
            setattr(self, '_i_' + name.strip('/').replace('/', ''), ix[name])
        self.trace = []
        self.n = 0
        self.halted = False
        self.parked = 0                       # art arda kaç MCLK kenarında C'de STOP'la beklendi
        self.started = False
        self.reset_marks = []                 # reset bırakıldığında len(trace)
        self.vram_writes = []                 # (adres, veri, zaman)
        self.wait_errors = []                 # pencere kapalıyken başlayan VRAM yazmaları
        self.stall_ns = 0                     # D fazında WAIT ile beklenen toplam süre
        self.timing = {k: [0, None, None] for k in ('yol1', 'yol2', 'yol3', 'yol3_mclk', 'wait')}
        self.windows = {k: None for k in ('yol1', 'yol2', 'yol3', 'yol3_mclk')}
        self._prev = {'CLK': None, 'LCLK': None, 'MCLK': None, 'VWE': None}
        self._tL = self._tC = None
        self._tE = 0                          # son MCLK↑ zamanı
        self._tCD = None                      # LCLK'e yol açan MCLK↑ (C→D) zamanı
        self._p3 = 0                          # 1: LCLK görüldü, 2: karar kenarı geçti
        self._tD = None                       # LCLK'ten sonraki ilk MCLK↑ (D→A kararı)
        self._q2d = self._wt = NEVER          # yol 3 penceresinde Q2_D / /WAIT son değişimi
        self._vwr_edge = 1                    # son MCLK↑ anında VWR_s
        self.lclk_times = []                  # violation sınıflandırması için
        sim.watch('CLK', self._on_clk)
        sim.watch('LCLK', self._on_lclk)
        sim.watch('MCLK', self._on_mclk)
        sim.watch('/VRAM_WE', self._on_vwe)
        sim.watch('Q2_D', self._on_q2d)
        sim.watch('/WAIT', self._on_wait)
        sim.add_clock('MCLK', self.half)
        for net, half in self.board.clocks.items():
            if net != 'MCLK':
                sim.add_clock(net, half)            # OSC25 (vga='netlist')

    # ------------------------------------------------------------------ olaylar
    def _rising(self, key, v):
        p = self._prev[key]
        self._prev[key] = v
        return v == 1 and p == 0

    def _in_p3(self, t):
        """Yol 3 penceresi: LCLK↑'den, karar kenarından yarım MCLK sonrasına kadar ve
        makine hâlâ D fazındayken (karardan sonra gelen geç değişimler de görülsün)."""
        if not self._p3 or (self._p3 == 2 and t > self._tD + self.half):
            return False
        val = self.sim.val
        return val[self._i_Q1] == 0 and val[self._i_CLK] == 1

    def _on_q2d(self, t, v):
        if self._in_p3(t):
            self._q2d = t

    def _on_wait(self, t, v):
        if self._in_p3(t):
            self._wt = t

    def _on_mclk(self, t, v):
        if not self._rising('MCLK', v):
            return
        val = self.sim.val
        q1, q2 = val[self._i_Q1], val[self._i_CLK]
        if self._p3 == 1:                               # LCLK'ten sonraki ilk MCLK↑: D→A kararı
            self._p3 = 2
            self._tD = t
        elif self._p3 == 2:                             # bir sonraki MCLK↑: yol 3'ü kapat
            self._p3 = 0
            tL, tD = self._tL, self._tD
            if self._q2d > tL:
                self._note('yol3', self._q2d - tL, tD - tL)
                self._note('yol3_mclk', self._q2d - self._tCD, tD - self._tCD)
            if self._wt > tL:
                self._note('wait', self._wt - tL, tD - tL)
        if q1 == 0 and q2 == 1:                         # D fazında kenar
            if self._tE and val[self._i_Q2_D] == 1:     # bu kenarda D'de kalınıyor (WAIT)
                self.stall_ns += t - self._tE
        if q1 == 1 and q2 == 1 and val[self._i_STOP] == 1 and val[self._i_GO] == 1:
            self.parked += 1
        else:
            self.parked = 0
        self._vwr_edge = val[self._i_VWR_s]
        self._tE = t

    def _on_lclk(self, t, v):
        if not self._rising('LCLK', v):
            return
        if self._tC is not None:                        # yol 2: CLK↑ → uROM çıkışları
            lc = self.sim.lastch
            last = max(lc[i] for i in self._i_cwin)
            if last > self._tC:
                self._note('yol2', last - self._tC, t - self._tC)
        self._tL = t
        self._tCD = self._tE
        self._p3 = 1
        self._q2d = self._wt = NEVER
        self.lclk_times.append(t)

    def _on_clk(self, t, v):
        if not self._rising('CLK', v):
            return
        val = self.sim.val
        if val[self._i_RESET_s] != 1:                   # reset sırasında (asenkron kurma) iz yok
            self._tC = None
            return
        ab = 0
        for k, i in enumerate(self._i_ab):
            b = val[i]
            if b is None:
                ab = None
                break
            ab |= b << k
        db = 0
        for k, i in enumerate(self._i_db):
            b = val[i]
            if b is None:
                db = None
                break
            db |= b << k
        cw = 0
        for k, i in enumerate(self._i_cw):
            if val[i]:
                cw |= 1 << k
        self.trace.append((self.n, ab, db, cw))
        self.n += 1
        if self._tL is not None:                        # yol 1: LCLK↑ → commit girişleri
            lc = self.sim.lastch
            last = max(lc[i] for i in self._i_p1)
            if last > self._tL:
                self._note('yol1', last - self._tL, t - self._tL)
        self._tC = t
        # klavye: bus.py ile aynı durum makinesi (okuma sonrası temizleme + byte arası süre)
        kb = self.kbd
        before = (kb.krdy, kb.kbd_byte)
        if val[self._i_KBD_RD] == 0:
            kb.read(IO_BASE)
        kb.tick(1)
        if (kb.krdy, kb.kbd_byte) != before:
            sr = (~kb.kbd_byte & 0xFF) if kb.krdy else 0
            self.sim.set('KRDY', kb.krdy, at=t + 1)
            self.sim.set_bus('KSR', 8, sr, at=t + 1)
        if cw & isa.HALT:
            self.halted = True

    def _on_vwe(self, t, v):
        p = self._prev['VWE']
        self._prev['VWE'] = v
        if self.sim.val[self._i_RESET_s] != 1:
            return                                      # açılış geçişi
        if v == 0 and p == 1:
            if self._vwr_edge == 0:
                self.wait_errors.append((t, self.n))
        elif v == 1 and p == 0:
            ab = self.sim.bus('AB', 16)
            self.vram_writes.append((ab, self.sim.bus('DB', 8), t))

    def _note(self, key, settle, window):
        rec = self.timing[key]
        if settle > rec[0]:
            rec[0] = settle
            rec[1] = self.n
            rec[2] = window
        w = self.windows.get(key, 0)
        if key in self.windows and (w is None or window < w):
            self.windows[key] = window

    # ------------------------------------------------------------------ denetim
    def power_on(self, reset_mclk=6):
        """Açılış: /RESET birkaç MCLK basılı, sonra bırakılır."""
        if self.started:
            return
        self.started = True
        self.sim.run_for(reset_mclk * 2 * self.half)
        self.release_reset()

    def release_reset(self):
        if self.ram_initial is None:                    # açılıştaki (reset sonrası) içerik
            mem = self.board.memories
            self.ram_initial = bytes(mem['RAM'].data)
            self.vram_initial = bytes(mem['VRAM'].data)
            self.release_time = self.sim.now
        self.sim.set('/RESET', 1)
        self.reset_marks.append(len(self.trace))
        self.halted = False

    def reset(self, hold_mclk=4):
        """Çalışırken reset butonu: bas, hold_mclk MCLK tut, bırak."""
        self.power_on()
        self.sim.set('/RESET', 0)
        self.sim.run_for(hold_mclk * 2 * self.half)
        self.release_reset()

    def run(self, max_cycles=1_000_000, idle_limit=None):
        """HALT'a ya da toplam max_cycles commit'e kadar çalıştırır; commit sayısını döndürür.
        idle_limit çevrim süresi boyunca hiç commit olmazsa (takılma) durur. Varsayılan 5000
        (5 ms); vga='netlist' kipinde 20000: WAIT bir kareye (16.8 ms) kadar sürebilir."""
        if idle_limit is None:
            idle_limit = 20000 if self.vga == 'netlist' else 5000
        self.power_on()
        idle = 0
        while not self.halted and self.n < max_cycles:
            n0 = self.n
            self.sim.run_for(self.cycle_ns)
            if self.n == n0:
                idle += 1
                if idle >= idle_limit:
                    break
            else:
                idle = 0
        self.sim.run_for(2 * self.half)                 # commit sonrası oturma
        return self.n

    def go(self, max_cycles=64, press_mclk=4):
        """GO butonuna basar; makine yeniden C'de STOP ile park edene kadar çalıştırır.
        Bu GO ile yapılan commit sayısını döndürür."""
        self.power_on()
        n0 = self.n
        self.halted = False
        self.parked = 0
        self.sim.set('GO_BTN', 1)
        self.sim.run_for(press_mclk * 2 * self.half)
        self.sim.set('GO_BTN', 0)
        for _ in range(max_cycles + 4):
            if self.n > n0 and self.parked >= 2:
                break
            self.sim.run_for(self.cycle_ns)
        return self.n - n0

    def set(self, net, value, at=None):
        """Bir anahtar/girişi sür (STEPMODE, MICRO, VWR_s, DIP0..5, GO_BTN, /RESET, BP0..15,
        /BP_EN)."""
        self.sim.set(net, value, at=at)

    # ------------------------------------------------------------------ hata ayıklama
    def set_breakpoint(self, addr):
        """BP0..15 anahtarlarına adresi verir ve breakpoint'i açar; None: kapatır (/BP_EN = 1)."""
        if addr is None:
            self.sim.set('/BP_EN', 1)
        else:
            self.sim.set_bus('BP', 16, addr)
            self.sim.set('/BP_EN', 0)

    def run_to_stop(self, max_cycles=1_000_000):
        """Makine C'de STOP ile park edene (HALT, breakpoint, BUSREQ, adım) ya da max_cycles
        commit'e kadar çalıştırır. Bu çağrıda yapılan commit sayısını döndürür."""
        self.power_on()
        n0 = self.n
        self.parked = 0
        while self.n - n0 < max_cycles:
            self.sim.run_for(self.cycle_ns)
            if self.n > n0 and self.parked >= 2:
                break
        self.sim.run_for(2 * self.half)
        return self.n - n0

    def stopped_by(self):
        """Duran makinede STOP'un nedenleri: {'HALT', 'BRK', 'BUSREQ', 'ADIM'} alt kümesi."""
        g = self.sim.get
        why = set()
        if g('HALT_L'):
            why.add('HALT')
        if g('BRK_L'):
            why.add('BRK')
        if g('BRQ_s'):
            why.add('BUSREQ')
        if g('STOP_SM'):
            why.add('ADIM')
        return why

    # Arduino (yükleme modu, arduino/README.md): /BUSREQ açık-drain, AB/DB/strobe'lar 'ARD'
    # sürücüsü. Zamanlar Arduino'nun hızına göre cömert (her adım ≥ 250 ns).
    def bus_request(self, timeout_mclk=64):
        """/BUSREQ'i indirir, BUSACK = 1'i bekler; bekleme süresini (MCLK periyodu) döndürür."""
        self.power_on()
        self.sim.set('/BUSREQ', 0, who='ARD')
        for k in range(1, timeout_mclk + 1):
            self.sim.run_for(2 * self.half)
            if self.sim.get('BUSACK') == 1:
                self.sim.run_for(500)                    # Arduino BUSACK'ı okuyup pinleri açar
                self.sim.set('/ARD_RD', 1, who='ARD')
                self.sim.set('/ARD_WR', 1, who='ARD')
                return k
        raise RuntimeError(f'BUSACK {timeout_mclk} MCLK içinde gelmedi')

    def _need_bus(self):
        if self.sim.get('BUSACK') != 1:
            raise RuntimeError('BUSACK = 0: bus Arduino\'da değil')

    def ard_write(self, addr, data):
        """BUSACK = 1 iken belleğe bir bayt yazar (AB, DB, sonra /ARD_WR darbesi)."""
        self._need_bus()
        s = self.sim
        s.set_bus('AB', 16, addr, who='ARD')
        s.set_bus('DB', 8, data, who='ARD')
        s.run_for(250)
        s.set('/ARD_WR', 0, who='ARD')
        s.run_for(500)
        s.set('/ARD_WR', 1, who='ARD')
        s.run_for(250)

    def ard_read(self, addr):
        """BUSACK = 1 iken bellekten bir bayt okur (DB bırakılır, /ARD_RD darbesi)."""
        self._need_bus()
        s = self.sim
        s.set_bus('DB', 8, None, who='ARD')
        s.set_bus('AB', 16, addr, who='ARD')
        s.run_for(250)
        s.set('/ARD_RD', 0, who='ARD')
        s.run_for(500)
        v = s.bus('DB', 8)
        s.set('/ARD_RD', 1, who='ARD')
        s.run_for(250)
        return v

    def bus_release(self, timeout_mclk=64):
        """Pinleri bırakır, sonra /BUSREQ'i; BUSACK = 0'ı bekler (MCLK periyodu döndürür)."""
        s = self.sim
        s.set_bus('AB', 16, None, who='ARD')
        s.set_bus('DB', 8, None, who='ARD')
        s.set('/ARD_RD', None, who='ARD')
        s.set('/ARD_WR', None, who='ARD')
        s.run_for(250)
        s.set('/BUSREQ', None, who='ARD')
        for k in range(1, timeout_mclk + 1):
            s.run_for(2 * self.half)
            if s.get('BUSACK') == 0:
                return k
        raise RuntimeError(f'BUSACK {timeout_mclk} MCLK içinde düşmedi')

    # ------------------------------------------------------------------ okuma
    def phase(self):
        q1, q2 = self.sim.get('Q1'), self.sim.get('CLK')
        return {(0, 0): 'A', (1, 0): 'B', (1, 1): 'C', (0, 1): 'D'}.get((q1, q2), '?')

    def state(self):
        s = self.sim
        return dict(pc=s.bus('PC', 16), ar=s.bus('AR', 16), x=s.bus('X', 16), sp=s.bus('SP', 8),
                    a=s.bus('ACC', 8), ir=s.bus('IR', 8), step=s.bus('STEP', 4),
                    z=s.get('Z'), c=s.get('C'), n=s.get('N'), v=s.get('V'))

    def ram(self):
        """8000–EFFF (RAM'in ilk 28 KB'ı)."""
        return bytes(self.board.memories['RAM'].data[:0x7000])

    def vram(self):
        return bytes(self.board.memories['VRAM'].data[:0x800])

    def leds(self):
        return self.sim.bus('LED', 8)

    def summary(self):
        return dict(self.sim.summary())

    def timing_report(self):
        """{yol: (en kötü oturma ns, o çevrim, o çevrimin penceresi ns, en dar pencere ns)}."""
        return {k: (v[0], v[1], v[2], self.windows.get(k)) for k, v in self.timing.items()}


# ----------------------------------------------------------------------------
# MicroEmu ile karşılaştırma
# ----------------------------------------------------------------------------
def emu_like(hw, program, max_cycles=1_000_000, keys=()):
    """hw ile aynı başlangıç durumunda (ROM, RAM ve VRAM içeriği, DIP, klavye) bir
    MicroEmu kurar, izini tutarak çalıştırır ve döndürür."""
    bus = Bus()
    bus.load(bytes(program[:0x8000]))
    bus.mem[0x8000:0xF000] = hw.ram_initial[:0x7000]
    bus.vram[:] = hw.vram_initial[:0x800]
    bus.dip = hw.dip
    if keys:
        bus.press(*keys)
    emu = MicroEmu(bus, cpu.default_urom(), cpu.default_alu())
    emu.trace = []
    emu.run(max_cycles)
    return emu


def emu_state(emu):
    return dict(pc=emu.pc, ar=emu.ar, x=emu.x, sp=emu.sp, a=emu.a, ir=emu.ir, step=emu.step,
                z=emu.z, c=emu.c, n=emu.n, v=emu.v)


def compare(hw, emu, trace_from=0, check_state=True):
    """Farkların listesi (boş = sıfır fark): iz, durum, RAM, VRAM, LED.
    İkisi de HALT'ta değilse izlerin ortak uzunluğu karşılaştırılır, durum karşılaştırılmaz."""
    out = []
    got, ref = hw.trace[trace_from:], emu.trace
    both_halted = hw.halted and emu.halted
    if not both_halted:
        k = min(len(got), len(ref))
        got, ref = got[:k], ref[:k]
    i, msg = compare_traces(ref, got)
    if i is not None:
        out.append(f'iz: {msg}')
    if both_halted and check_state:
        hs, es = hw.state(), emu_state(emu)
        diff = {k: (es[k], hs[k]) for k in STATE_KEYS if hs[k] != es[k]}
        if diff:
            out.append(f'durum (emu, devre): {diff}')
        ram, eram = hw.ram(), bytes(emu.bus.mem[0x8000:0xF000])
        if ram != eram:
            bad = [a for a in range(len(ram)) if ram[a] != eram[a]]
            out.append(f'RAM {len(bad)} byte farklı, ilk {0x8000 + bad[0]:04X}: '
                       f'emu {eram[bad[0]]:02X}, devre {ram[bad[0]]:02X}')
        if hw.vram() != bytes(emu.bus.vram):
            out.append('VRAM farklı')
        if hw.leds() != emu.bus.leds:
            out.append(f'LED emu {emu.bus.leds:02X}, devre {hw.leds()}')
    return out


def run_and_compare(program, max_cycles=200_000, keys=(), **hw_kw):
    """Devreyi ve MicroEmu'yu çalıştırır. Döner: (hw, emu, farklar, saniye)."""
    t0 = time.perf_counter()
    hw = HwCpu(program, keys=keys, **hw_kw)
    hw.run(max_cycles)
    dt = time.perf_counter() - t0
    emu = emu_like(hw, program, max_cycles, keys)
    return hw, emu, compare(hw, emu), dt


def emu_vram_writes(emu):
    """Emülatör izinden VRAM'e yazmalar: [(adres, veri), ...]."""
    return [(ab, db) for _, ab, db, cw in emu.trace
            if cw & isa.MEMW and VRAM_BASE <= ab < IO_BASE]


# ----------------------------------------------------------------------------
# İhlallerin sınıflandırılması
# ----------------------------------------------------------------------------
def _duration(v):
    """'(N ns sürdü)' → N (çakışma bitmediyse None)."""
    d = v.desc
    k = d.rfind('(')
    if k < 0 or not d.endswith('sürdü)'):
        return None
    try:
        return int(d[k + 1:].split()[0])
    except ValueError:
        return None


def classify_violations(hw):
    """İhlalleri sınıflara ayırır:

    acilis        reset ilk bırakılmadan önce (güç verildiği an; bütün çipler aynı anda
                  değerlendirilir, kod çözücüler oturana kadar kısa çakışmalar ve SRAM'e
                  sahte yazma görünür; gerçekte reset basılıyken anlamsız)
    devir_teslim  DB'de, LCLK↑'den (C→D) sonraki iki faz içinde başlayan kısa çakışma:
                  eski kaynağın kapanması (bellek tDF / 245 kapanma) yeni kaynağın
                  açılmasından geç (DOGRULAMA 3.5'in bilinen sorunu)
    diger         geri kalan her şey (sıfır olmalı)
    Döner: {sınıf: [Violation, ...]}.
    """
    from bisect import bisect_right
    t0 = hw.release_time if hw.release_time is not None else -1
    lt = hw.lclk_times
    out = {'acilis': [], 'devir_teslim': [], 'diger': []}
    for v in hw.sim.violations:
        if v.time <= t0:
            out['acilis'].append(v)
            continue
        if v.kind == 'cakisma' and v.desc.startswith('DB'):
            k = bisect_right(lt, v.time) - 1
            if k >= 0 and v.time - lt[k] < 4 * hw.half:
                d = _duration(v)
                if d is not None and d < 2 * hw.half:
                    out['devir_teslim'].append(v)
                    continue
        out['diger'].append(v)
    return out


def handover_summary(viols):
    """devir_teslim ihlalleri için {sürücü çifti: (adet, en uzun ns)}."""
    out = {}
    for v in viols:
        n, m = out.get(v.ref, (0, 0))
        out[v.ref] = (n + 1, max(m, _duration(v) or 0))
    return dict(sorted(out.items(), key=lambda kv: -kv[1][0]))
