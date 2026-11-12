"""TD-8 işlemcisi: çip seviyesinde, pin pin netlist (SISTEM-PLANI 2–5, 7, 15.1).

Her modül ayrı bir kurucu fonksiyondur ve kendi parçasını bir `Board` olarak
döndürür; modüller arasındaki bağlantı yalnızca net adlarıyla kurulur (Digital
dışa aktarıcı her modülü ayrı bir .dig yapabilsin diye):

    m1_clock()      M1  saat / reset / durdurma / WAIT          U1xx
    m2_control()    M2  uROM, kontrol latch'i, kod çözücüler     U2xx
    m3_address()    M3  PC, AR, X, SP ve AB tamponları           U3xx
    m4_data()       M4  A, IR, F, ALU flash'ları, DB tamponları  U4xx
    aux_gates()     AUX CPU yardımcı kapıları                    U5xx
    m5_memory()     M5  ROM, RAM, adres çözme, LED, KSTAT        U6xx
    stubs()         TB  henüz olmayan M6/M7 için taklitler       X…

    board = build(sim, program=prog.image)   # hepsini birleştirir, sim'e ekler

Net adları SISTEM-PLANI bölüm 2'deki sinyal sözlüğüyle aynıdır: AB0..15, DB0..7,
R0..7, CLK, LCLK, WSTB, STOP, /WAIT, /RESET_s, /MRD, /OE_A, /DD_IR, ...
Kontrol kelimesinin uROM çıkışları ASRC0, DSRC0, ..., HALT; 273 latch
çıkışları aynı adlar + `_L` (ASRC0_L, ..., HALT_L). Register çıkışları:
PC0..15, AR0..15 (= sözlükteki PCIN), X0..15, SP0..7, ACC0..7 (A), IR0..7,
STEP0..3, Z C N V (F), LED0..7.

Kapsam dışı (5. hafta; kodda `# 5. hafta` ile işaretli): NE555, kaynak seçici
74HC153, RC/74HC14 kısımları (MCLK ve butonlar test tezgâhından temiz sayısal
giriş), breakpoint (2× 74HC688, BRK), BUSREQ/BUSACK (BUSACK = 0, /ARD_RD =
/ARD_WR = 1), MANUAL paneli (uROM /OE = 0). Bunların netleri `Board.ties`
(pasif değer) ya da `Board.pulls` (gerçekte de var olan pull-up'lar) ile
sabitlenir.

Plan bir ayrıntıyı vermediğinde yapılan seçimler her çipin `note` alanında;
planın yazıldığı gibi çalışmadığı yerler "PLAN DÜZELTMESİ" diye işaretli
(bkz. PLAN_FIXES).
"""

from dataclasses import dataclass, field
from functools import lru_cache

from .. import alu, isa, microcode
from .chips import (CY62256, HC00, HC02, HC04, HC08, HC20, HC32, HC74, HC138, HC139, HC161,
                    HC175, HC191, HC245, HC273, HC377, HC540, SST39SF010)

# ----------------------------------------------------------------------------
# Net adları
# ----------------------------------------------------------------------------
CW_NAMES = ['ASRC0', 'ASRC1', 'DSRC0', 'DSRC1', 'DSRC2', 'DDST0', 'DDST1', 'DDST2',
            'ALUOP0', 'ALUOP1', 'ALUOP2', 'ALUOP3', 'ALUOP4', 'FL', 'MEMW', 'MARK',
            'PCINC', 'PCLD', 'ARINC', 'XINC', 'SPCNT', 'SPDN', 'NEXT', 'HALT']
CW_L = [n + '_L' for n in CW_NAMES]          # 273 çıkışları, bit 0..23
for _name, _bit in isa.BITS.items():          # isa.py ile tutarlılık
    assert CW_NAMES[_bit.bit_length() - 1] == _name, _name
assert (isa.ASRC_SHIFT, isa.DSRC_SHIFT, isa.DDST_SHIFT, isa.ALUOP_SHIFT) == (0, 2, 5, 8)

MODULE_ORDER = ('M1', 'M2', 'M3', 'M4', 'AUX', 'M5', 'TB')
MODULE_TITLES = {
    'M1': 'M1 Saat / reset / durdurma',
    'M2': 'M2 Kontrol ünitesi',
    'M3': 'M3 Adres registerları',
    'M4': 'M4 Veri ve ALU',
    'AUX': 'CPU yardımcı kapıları',
    'M5': 'M5 Bellek + I/O',
    'TB': 'Test tezgâhı taklitleri (M6/M7 yerine; entegre sayımına girmez)',
}

# Planın yazıldığı gibi kurulunca çalışmayan / kendi içinde çelişen yerler ve
# netlist'te yapılan en küçük düzeltme. (Boş liste = düzeltme gerekmedi.)
PLAN_FIXES = [
    "WAIT yolu (SISTEM-PLANI 3.6, ISA-v0-sentez 5.4 yol 3): plan Q2' = NAND(/Q1, "
    "OR(/WAIT, /Q2)) ve 138 G1 = VCC diyor; elle hesap ~236 ns < 250 ns. Hesap, LCLK'in "
    "MCLK kenarından Johnson 74HC74'ün kendi CP→Q gecikmesi kadar (en kötü ~44 ns) sonra "
    "yükseldiğini ve 74HC74 kurulum süresini (~15 ns) atlıyor: D→A kararı LCLK'e değil "
    "MCLK'ye göre örneklenir. Simülasyonda max köşede, 1 MHz'de /WAIT kararı C→D MCLK "
    "kenarından ~257 ns sonra geliyor; VRAM'e pencere kapalıyken yapılan her yazma "
    "beklemeden A fazına geçiyor (merhaba.asm: 14 yazmanın 12'si, bekleme 0). "
    "Düzeltme: WAIT 138'inin G1 ucu VCC yerine CLK (= Q2); bu, OR(/WAIT, /Q2)'yi "
    "138'in içinde yapar. Johnson Q2' = NAND(/Q1, /WAIT) olur, bir kapı seviyesi "
    "(OR, en kötü 25 ns) kalkar ve U104'ün 1. OR kapısı boşa çıkar. Mantık birebir aynı "
    "(/WAIT' = /WAIT | /Q2). Max köşede karar ~232 ns + kurulum 15 = 247 < 250 ns "
    "(pay ~3 ns: sınırda; osiloskopla doğrulanmalı).",
]


def nets(prefix, n, start=0):
    return [f'{prefix}{start + i}' for i in range(n)]


def pins(pin_prefix, net_list, pin_start=0):
    return {f'{pin_prefix}{pin_start + i}': net for i, net in enumerate(net_list)}


@lru_cache(maxsize=None)
def default_urom():
    """Üç uROM imajı (bank 0 ve 1), sim/td8/microcode.py'den."""
    return tuple(bytes(r) for r in microcode.build())


@lru_cache(maxsize=None)
def default_alu():
    """(ALU-L, ALU-H) imajları, sim/td8/alu.py'den."""
    return tuple(bytes(t) for t in alu.build_tables())


# ----------------------------------------------------------------------------
# Board: saf veri
# ----------------------------------------------------------------------------
@dataclass
class Board:
    """Bir netlist parçası (tek modül ya da bütün kart).

    chips     çip nesneleri (sırası kurulum sırası)
    pulls     net → 0/1: gerçek pull-up/pull-down dirençleri (AB 10k↑, DB 10k↓, ...)
    ties      net → 0/1: kapsam dışı (5. hafta) sürücülerin yerine pasif değer
    inputs    net → varsayılan: test tezgâhının sürdüğü netler (butonlar, anahtarlar,
              taklitlerin girişleri). MCLK burada değil, `clocks`ta.
    clocks    net → yarım periyot (ns): MCLK 4 MHz = 125 ns
    memories  ad → bellek çipi (UROM0..2, ALU_L, ALU_H, ROM, RAM, VRAM)
    notes     modül düzeyindeki notlar
    """
    chips: list = field(default_factory=list)
    pulls: dict = field(default_factory=dict)
    ties: dict = field(default_factory=dict)
    inputs: dict = field(default_factory=dict)
    clocks: dict = field(default_factory=dict)
    memories: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    @classmethod
    def merge(cls, parts):
        b = cls()
        for p in parts:
            b.chips.extend(p.chips)
            for name in ('pulls', 'ties', 'inputs', 'clocks', 'memories'):
                dst, src = getattr(b, name), getattr(p, name)
                for k, v in src.items():
                    if k in dst and dst[k] is not v and dst[k] != v:
                        raise ValueError(f'{name}: {k} iki modülde farklı ({dst[k]} / {v})')
                    dst[k] = v
            b.notes.extend(p.notes)
        seen = set()
        for c in b.chips:
            if c.ref in seen:
                raise ValueError(f'aynı ref iki kez: {c.ref}')
            seen.add(c.ref)
        return b

    def chip(self, ref):
        for c in self.chips:
            if c.ref == ref:
                return c
        raise KeyError(ref)

    def modules(self):
        """Modül adı → o modülün çipleri (MODULE_ORDER sırasıyla)."""
        out = {m: [] for m in MODULE_ORDER}
        for c in self.chips:
            out.setdefault(c.module, []).append(c)
        return {m: cs for m, cs in out.items() if cs}

    def net_users(self):
        """Net → [(ref, pin), ...] (güç netleri dahil)."""
        users = {}
        for c in self.chips:
            for p, n in c.pins.items():
                users.setdefault(n, []).append((c.ref, p))
        return users

    def ports(self, module):
        """Modülün sınır netleri: başka bir modülün çipine, bir girişe, saate, pull'a
        ya da tie'a da bağlı olan netler (VCC/GND hariç). Digital dışa aktarıcı için."""
        own = {c.ref for c in self.chips if c.module == module}
        ext = set(self.inputs) | set(self.clocks) | set(self.ties) | set(self.pulls)
        out = set()
        for net, us in self.net_users().items():
            if net in ('VCC', 'GND'):
                continue
            mine = any(r in own for r, _ in us)
            other = any(r not in own for r, _ in us)
            if mine and (other or net in ext):
                out.add(net)
        return sorted(out)

    def attach(self, sim):
        """Çipleri, pull'ları, tie'ları ve girişlerin varsayılan değerlerini sim'e verir.
        (Saatleri test tezgâhı ekler: sim.add_clock('MCLK', board.clocks['MCLK']).)"""
        sim.add(*self.chips)
        for net, v in self.pulls.items():
            sim.pull(net, v)
        for net, v in self.ties.items():
            sim.pull(net, v)
        for net, v in self.inputs.items():
            sim.set(net, v)
        return self


def _chip(cls, ref, pin_map, module, note='', **kw):
    return cls(ref, pin_map, module=module, note=note, **kw)


def _unused_gates(units, kind='2'):
    """Kullanılmayan kapı birimlerinin girişleri GND'ye."""
    out = {}
    for u in units:
        if kind == '2':
            out.update({f'{u}A': 'GND', f'{u}B': 'GND'})
        elif kind == '1':
            out[f'{u}A'] = 'GND'
        elif kind == '4':
            out.update({f'{u}{x}': 'GND' for x in 'ABCD'})
    return out


# ----------------------------------------------------------------------------
# M1: saat, reset, durdurma, WAIT (SISTEM-PLANI 3)
# ----------------------------------------------------------------------------
def m1_clock(mclk_half=125, wait_fix=True):
    """wait_fix=False: planın yazıldığı hâli (138 G1 = VCC, Q2' = NAND(/Q1, OR(/WAIT, /Q2)));
    max köşede 1 MHz'de WAIT kaçırır (PLAN_FIXES[0]). Varsayılan: düzeltilmiş hâl."""
    M = 'M1'
    fix = ' PLAN DÜZELTMESİ (PLAN_FIXES[0]).' if wait_fix else ''
    chips = [
        _chip(HC74, 'U101', {
            '/1RD': 'VCC', '/1SD': '/RESET_s', '1CP': 'MCLK', '1D': 'Q1_D', '1Q': 'Q1', '/1Q': 'LCLK',
            '/2RD': 'VCC', '/2SD': '/RESET_s', '2CP': 'MCLK', '2D': 'Q2_D', '2Q': 'CLK', '/2Q': '/CLK',
        }, M, 'Johnson sayacı (3.1): FF1 = Q1, FF2 = Q2. Fazlar A=00 B=10 C=11 D=01. '
              'CLK = Q2 (net adı CLK), LCLK = /Q1. /RESET_s her iki FF\'yi /SD ile 1\'e '
              'kurar → C fazı (3.4). /RD kullanılmaz (VCC).'),
        _chip(HC74, 'U102', {
            '/1RD': '/RESET', '/1SD': 'VCC', '1CP': 'MCLK', '1D': 'VCC', '1Q': 'RST_S1',
            '/2RD': '/RESET', '/2SD': 'VCC', '2CP': 'MCLK', '2D': 'RST_S1', '2Q': '/RESET_s',
        }, M, 'Reset senkronlayıcısı (3.4): 2 FF, D1 = VCC. /RESET düşünce iki FF de '
              'hemen 0 (asenkron başlama), bırakılınca 1 iki MCLK kenarında geçer '
              '(senkron bırakma). Giriş /RESET: RC + buton + Arduino → 74HC14 çıkışı; '
              '74HC14 ve RC 5. hafta, burada test tezgâhından temiz aktif-düşük giriş.'),
        _chip(HC00, 'U103', {
            '1A': 'STOP', '1B': 'Q1', '1Y': 'STOP_Q1_n',
            '2A': 'CLK', '2B': 'STOP_Q1_n', '2Y': 'Q1_D',
            '3A': 'LCLK', '3B': '/WAIT' if wait_fix else 'WAIT_OR', '3Y': 'Q2_D',
            '4A': 'GO_S2', '4B': '/GO_PREV', '4Y': '/GO',
        }, M, 'Johnson sonraki durum (3.1, 3.6): Q1\' = NAND(Q2, NAND(STOP, Q1)) '
              '(= !Q2 | STOP&Q1, 2 kapı); '
              + ('Q2\' = NAND(/Q1, /WAIT); /WAIT, 138\'in G1 = Q2 ucu sayesinde zaten '
                 'OR(/WAIT, /Q2).' if wait_fix else
                 'Q2\' = NAND(/Q1, OR(/WAIT, /Q2)) (138\'li WAIT, OR U104\'te).')
              + ' 4. kapı /GO = NAND(sync2, /prev) (3.3).' + fix),
        _chip(HC32, 'U104', {
            **({'1A': 'GND', '1B': 'GND'} if wait_fix else
               {'1A': '/WAIT', '1B': '/CLK', '1Y': 'WAIT_OR'}),
            '2A': 'MICRO', '2B': 'NEXT_L', '2Y': 'STOP_MN',
            '3A': 'HALT_L', '3B': 'BRK_L', '3Y': 'STOP_HB',
            '4A': 'STOP_HB', '4B': 'STOP_SM', '4Y': 'STOP_T',
        }, M, ('1. kapı boş, girişleri GND (planda OR(/WAIT, /Q2); düzeltmeyle 138\'in '
               'G1 ucuna taşındı). ' if wait_fix else '1. kapı OR(/WAIT, /Q2) Johnson için (3.6). ')
              + 'STOP denkleminin 3 OR\'u (3.3): MICRO|NEXT_L, HALT_L|BRK_L, '
              '(HALT_L|BRK_L)|(STEPMODE_s&(MICRO|NEXT_L)). 4. STOP OR\'u (BRQ_s) AUX U503\'te.'
              + fix),
        _chip(HC08, 'U105', {
            '1A': 'STEPMODE_s', '1B': 'STOP_MN', '1Y': 'STOP_SM',
            '2A': 'STOP_T', '2B': '/GO', '2Y': 'STOP_G',
            **_unused_gates((3, 4)),   # 5. hafta: BUSACK D = BRQ_s & Q1 & Q2 (2 kapı)
        }, M, 'STEPMODE_s & (MICRO|NEXT_L); (…) & !GO. 3. ve 4. kapı BUSACK D için '
              'ayrılmış (5. hafta), girişleri GND.'),
        _chip(HC02, 'U106', {
            '1A': 'Q1', '1B': 'CLK', '1Y': 'WSTB',
            **_unused_gates((2, 3, 4)),  # 5. hafta: 2. kapı BRK D = NOR(/MATCH, /ACCESS)
        }, M, 'WSTB = NOR(Q1, Q2): A fazında 1. 2. kapı BRK D için ayrılmış (5. hafta); '
              '3, 4 boş. Kullanılmayan girişler GND.'),
        _chip(HC175, 'U107', {
            '/MR': 'VCC', 'CP': 'MCLK',
            'D0': 'GO_BTN', 'Q0': 'GO_S1',
            'D1': 'GO_S1', 'Q1': 'GO_S2',
            'D2': 'GO_S2', 'Q2': 'GO_PREV', '/Q2': '/GO_PREV',
            'D3': 'STEPMODE', 'Q3': 'STEPMODE_s',
        }, M, 'GO senkronlayıcısı (sync1, sync2, prev; GO = sync2 & !prev tam bir MCLK) ve '
              'STEPMODE senkronlayıcısı. /MR planda yok: VCC seçildi (reset GO\'yu '
              'etkilemesin). GO_BTN: RC + 74HC14 çıkışı (5. hafta), burada temiz giriş. '
              'MICRO senkronlanmaz (plan 3.3: yalnız STEPMODE_s).'),
        _chip(HC138, 'U108', {
            'E3': 'CLK' if wait_fix else 'VCC', '/E1': '/FPAGE', '/E2': 'AB11',
            'A0': '/MEMW', 'A1': 'VWR_s', 'A2': 'GND', '/Y0': '/WAIT',
        }, M, 'WAIT (3.6, DOGRULAMA 2.5): '
              + ('G1 = CLK (= Q2; planda VCC)' if wait_fix else 'G1 = VCC')
              + ', /G2A = /FPAGE, /G2B = A11, A = /MEMW, B = VWR_s, C = GND. Y0 = /WAIT '
              '(F000–F7FF\'ye yazma VE pencere kapalı'
              + (' VE Q2 = 1, yani C ya da D fazı' if wait_fix else '') + '). Y1–Y7 boş.' + fix),
        _chip(HC245, 'U109', {
            'DIR': 'VCC', '/OE': 'GND',
            **{f'A{i}': 'CLK' for i in range(7)}, 'A7': 'GND',
            'B0': 'CLK_PC', 'B1': 'CLK_AR', 'B2': 'CLK_X', 'B3': 'CLK_SP',
            'B4': 'CLK_AFI', 'B5': 'CLK_IO', 'B6': 'CLK_TP',
        }, M, 'CLK tamponu (3.5): her çıkış ayrı bir yıldız dal (gerçekte 47 Ω seri). '
              'Dallar: PC | AR | X | SP+STEP | A+F+IR (aynı dal, 3.5) | LED (+BRK, KCLR '
              '5. hafta) | test noktası. 8. kanal boş: A7 = GND (çıkışı boşta '
              'salınmasın diye), B7 bağlı değil.'),
    ]
    b = Board(chips=chips,
              ties={'BRK_L': 0, 'BRQ_s': 0},          # 5. hafta: breakpoint FF'i, BUSREQ senkronlayıcısı
              inputs={'/RESET': 1, 'GO_BTN': 0, 'STEPMODE': 0, 'MICRO': 0},
              clocks={'MCLK': mclk_half})
    b.notes.append('M1 kapsam dışı (5. hafta): NE555, 74HC153 (kaynak seçici; MCLK doğrudan '
                   'test tezgâhından), 74HC14 (RC/debounce), 3. 74HC74 (BRK + BUSACK FF\'leri; '
                   'BRK_L = 0, BUSACK = 0), 2. 74HC175 (BRQ ×2, VWR ×2 senkronlayıcıları; '
                   'BRQ_s = 0, VWR_s test tezgâhından).')
    return b


# ----------------------------------------------------------------------------
# M2: kontrol ünitesi (SISTEM-PLANI 4)
# ----------------------------------------------------------------------------
def m2_control(urom=None, bank=0):
    M = 'M2'
    urom = urom if urom is not None else default_urom()
    addr = {**pins('A', nets('STEP', 4)), **pins('A', nets('IR', 8), 4),
            'A12': 'Z', 'A13': 'C', 'A14': 'N', 'A15': 'V',
            'A16': 'VCC' if bank else 'GND'}
    chips = []
    for i in range(3):
        chips.append(_chip(SST39SF010, f'U20{i + 1}', {
            **addr, '/CE': 'GND', '/OE': 'MANUAL', '/WE': 'VCC',
            **pins('DQ', CW_NAMES[8 * i:8 * i + 8]),
        }, M, f'uROM{i} (4.1): A0–3 STEP, A4–11 IR, A12–15 Z C N V, A16 BANK jumper '
              f'(= {"VCC" if bank else "GND"}, bank {bank}). /CE = GND, /WE = VCC, '
              f'/OE = MANUAL (panel 5. hafta: MANUAL = 0). -70 (DOGRULAMA 2b). '
              f'Çıkış: kontrol kelimesi bit {8 * i}–{8 * i + 7}.',
            data=urom[i], speed=70))
    for i in range(3):
        chips.append(_chip(HC273, f'U20{i + 4}', {
            '/MR': '/RESET_s', 'CP': 'LCLK',
            **pins('D', CW_NAMES[8 * i:8 * i + 8]), **pins('Q', CW_L[8 * i:8 * i + 8]),
        }, M, f'Kontrol latch\'i {i} (4.2): CP = LCLK (C→D), /MR = /RESET_s (NOP kelimesi). '
              f'LCLK doğrudan 74HC74\'ten (3.5).'))
    chips += [
        _chip(HC138, 'U207', {
            'A0': 'DSRC0_L', 'A1': 'DSRC1_L', 'A2': 'DSRC2_L',
            'E3': 'VCC', '/E1': 'BUSACK', '/E2': 'GND',
            '/Y1': '/MRD', '/Y2': '/OE_A', '/Y3': '/OE_PCL', '/Y4': '/OE_PCH',
        }, M, '#DS (4.3): G1 = VCC, /G2A = BUSACK, /G2B = GND (ISA-v0-sentez 4.3). '
              'Y0 (yok), Y5–Y6 (ayrılmış), Y7 (yok/panel) boş.'),
        _chip(HC138, 'U208', {
            'A0': 'DDST0_L', 'A1': 'DDST1_L', 'A2': 'DDST2_L',
            'E3': 'VCC', '/E1': 'GND', '/E2': 'GND',
            '/Y1': '/DD_IR', '/Y2': '/DD_A', '/Y3': '/DD_XL', '/Y4': '/DD_XH',
            '/Y5': '/DD_ARL', '/Y6': '/DD_ARH',
        }, M, '#DD (4.3): hep izinli. Çıkışlar senkron yükleme izinleri (saat değil). '
              'Y0 (yok), Y7 (yasak) boş.'),
        _chip(HC139, 'U209', {
            '/1E': 'BUSACK', '1A0': 'ASRC0_L', '1A1': 'ASRC1_L',
            '/1Y0': '/AB_PC', '/1Y1': '/AB_AR', '/1Y2': '/AB_X', '/1Y3': '/AB_SP',
            '/2E': '/FPAGE', '2A0': 'AB11', '2A1': 'GND',
            '/2Y0': '/VRAMSEL', '/2Y1': '/IOSEL',
        }, M, '1. yarı #AS (4.3): /G = BUSACK, Y0..Y3 → PC/AR/X/SP AB tamponlarının /OE\'si. '
              '2. yarı #MS (7.2): /G = /FPAGE, A = A11, B = GND → Y0 /VRAMSEL, Y1 /IOSEL; '
              'Y2, Y3 boş.'),
        _chip(HC161, 'U210', {
            '/MR': '/RESET_s', 'CP': 'CLK_SP', 'CEP': 'VCC', 'CET': 'VCC', '/PE': '/NEXT',
            **pins('D', ['GND'] * 4), **pins('Q', nets('STEP', 4)),
        }, M, 'STEP sayacı (4.4): CEP = CET = 1, /PE = NOT NEXT, P = 0000 (senkron sıfırlama), '
              '/MR = /RESET_s. CLK dalı: SP+STEP (3.5). TC boş.'),
        _chip(HC04, 'U211', {
            '1A': 'FL_L', '1Y': '/FL', '2A': 'PCLD_L', '2Y': '/PCLD',
            '3A': 'NEXT_L', '3Y': '/NEXT', '4A': 'SPCNT_L', '4Y': '/SPCNT',
            '5A': 'MEMW_L', '5Y': '/MEMW', '6A': 'GND',
        }, M, 'Kutup düzeltmeleri (4.2): FL → F /PE, PCLD → PC /PE, NEXT → STEP /PE, '
              'SPCNT → SP /CE (alt), MEMW → /MEMW. 6. kapı boş (girişi GND).'),
    ]
    b = Board(chips=chips,
              ties={'MANUAL': 0,     # 5. hafta: MANUAL paneli (uROM /OE açık)
                    'BUSACK': 0},    # 5. hafta: BUSACK FF'i (M1'in 3. 74HC74'ü)
              memories={f'UROM{i}': chips[i] for i in range(3)})
    b.notes.append('M2 kapsam dışı (5. hafta): 2× 74HC688 (breakpoint). MANUAL paneli yok: '
                   'MANUAL = 0 (uROM /OE açık); 24 latch girişindeki 47k pull-down\'lar ve '
                   'DB DIP switch\'leri de panelle birlikte 5. hafta.')
    return b


# ----------------------------------------------------------------------------
# M3: adres registerları ve AB tamponları (SISTEM-PLANI 5.1)
# ----------------------------------------------------------------------------
def _counter16(M, base, name, q, d, pe, cep, cp, note):
    """4× 74HC161 kademeli: CET zinciri TC'den (CET0 = VCC)."""
    out = []
    for k in range(4):
        out.append(_chip(HC161, f'U3{base + k:02d}', {
            '/MR': '/RESET_s', 'CP': cp, '/PE': pe[k], 'CEP': cep,
            'CET': 'VCC' if k == 0 else f'{name}_TC{k - 1}',
            **({'TC': f'{name}_TC{k}'} if k < 3 else {}),
            **pins('D', d[4 * k:4 * k + 4]), **pins('Q', q[4 * k:4 * k + 4]),
        }, M, f'{name} bit {4 * k}–{4 * k + 3}. {note} CET zinciri: '
              + ('CET = VCC (planda yalnız "CET chained from TC"; ilk kademe VCC seçildi).'
                 if k == 0 else 'CET = önceki kademenin TC\'si.')
              + (' TC boş.' if k == 3 else '')))
    return out


def m3_address():
    M = 'M3'
    db = nets('DB', 8)
    chips = []
    chips += _counter16(M, 1, 'PC', nets('PC', 16), nets('AR', 16), ['/PCLD'] * 4, 'PCINC_L',
                        'CLK_PC', 'PC (5.1): /PE = /PCLD, P = AR (PCIN, 16 bit birden), '
                        'CEP = PCINC, /MR = /RESET_s → 0000.')
    chips += _counter16(M, 5, 'AR', nets('AR', 16), db + db, ['/DD_ARL'] * 2 + ['/DD_ARH'] * 2,
                        'ARINC_L', 'CLK_AR', 'AR (5.1): P = DB, alt çift /DD_ARL, üst çift '
                        '/DD_ARH, CEP = ARINC. Çıkışlar = PCIN.')
    chips += _counter16(M, 9, 'X', nets('X', 16), db + db, ['/DD_XL'] * 2 + ['/DD_XH'] * 2,
                        'XINC_L', 'CLK_X', 'X (5.1): P = DB, /DD_XL, /DD_XH, CEP = XINC.')
    chips += [
        _chip(HC191, 'U313', {
            '/PL': '/RESET_s', '/CE': '/SPCNT', 'D/U': 'SPDN_L', 'CP': 'CLK_SP',
            **pins('D', ['VCC'] * 4), **pins('Q', nets('SP', 4)), 'MAX/MIN': 'SP_MM0',
        }, M, 'SP alt nibble (5.1): /CE = NOT SPCNT (U211), D/U = SPDN (1 = aşağı), D = 1111, '
              '/PL = /RESET_s → F. MAX/MIN → üst /CE NAND\'ı (U501). /RC boş.'),
        _chip(HC191, 'U314', {
            '/PL': '/RESET_s', '/CE': '/SPCNT_HI', 'D/U': 'SPDN_L', 'CP': 'CLK_SP',
            **pins('D', ['VCC'] * 4), **pins('Q', nets('SP', 4, 4)),
        }, M, 'SP üst nibble: /CE = NAND(SPCNT, MAX/MIN_alt) (U501). MAX/MIN ve /RC boş.'),
    ]
    buf = [('U315', nets('PC', 8), nets('AB', 8), '/AB_PC', 'PC alt → AB0–7'),
           ('U316', nets('PC', 8, 8), nets('AB', 8, 8), '/AB_PC', 'PC üst → AB8–15'),
           ('U317', nets('AR', 8), nets('AB', 8), '/AB_AR', 'AR alt → AB0–7'),
           ('U318', nets('AR', 8, 8), nets('AB', 8, 8), '/AB_AR', 'AR üst → AB8–15'),
           ('U319', nets('X', 8), nets('AB', 8), '/AB_X', 'X alt → AB0–7'),
           ('U320', nets('X', 8, 8), nets('AB', 8, 8), '/AB_X', 'X üst → AB8–15'),
           ('U321', nets('SP', 8), nets('AB', 8), '/AB_SP', 'SP → AB0–7'),
           ('U322', ['VCC', 'VCC', 'VCC', 'VCC', 'GND', 'VCC', 'VCC', 'VCC'], nets('AB', 8, 8),
            '/AB_SP', 'EF sabiti → AB8–15 (A girişleri EF = 1110 1111\'e bağlı)')]
    for ref, a, bnets, oe, what in buf:
        chips.append(_chip(HC245, ref, {'DIR': 'VCC', '/OE': oe, **pins('A', a), **pins('B', bnets)},
                           M, f'AB tamponu: {what}. DIR = VCC (A→B), /OE = {oe} (#AS).'))
    return Board(chips=chips, pulls={f'AB{i}': 1 for i in range(16)},
                 notes=['AB: 16× 10k pull-up (boşta FFFF).'])


# ----------------------------------------------------------------------------
# M4: A, IR, F, ALU ve DB tamponları (SISTEM-PLANI 5.1–5.2)
# ----------------------------------------------------------------------------
def m4_data(alu_tables=None):
    M = 'M4'
    lo, hi = alu_tables if alu_tables is not None else default_alu()
    acc, db, aluop = nets('ACC', 8), nets('DB', 8), CW_L[8:13]
    chips = [
        _chip(HC161, 'U401', {
            '/MR': '/RESET_s', 'CP': 'CLK_AFI', '/PE': '/FL', 'CEP': 'GND', 'CET': 'GND',
            'D0': 'Znew', 'D1': 'Cnew', 'D2': 'Nnew', 'D3': 'Vnew',
            'Q0': 'Z', 'Q1': 'C', 'Q2': 'N', 'Q3': 'V',
        }, M, 'F (5.1): 4-bit register olarak 161, /PE = NOT FL (U211), CEP = CET = 0, '
              '/MR = /RESET_s → 0000. Q0..3 = Z C N V (uROM A12–15). TC boş.'),
        _chip(HC377, 'U402', {'/E': '/DD_A', 'CP': 'CLK_AFI', **pins('D', nets('R', 8)),
                              **pins('Q', acc)},
              M, 'A (5.1): D = R, /E = /DD_A. Reset yok (açılışta belirsiz).'),
        _chip(HC377, 'U403', {'/E': '/DD_IR', 'CP': 'CLK_AFI', **pins('D', db),
                              **pins('Q', nets('IR', 8))},
              M, 'IR (5.1): D = DB, /E = /DD_IR. Reset yok (0. adım her IR için FETCH).'),
        _chip(HC245, 'U404', {'DIR': 'VCC', '/OE': '/OE_A', **pins('A', acc), **pins('B', db)},
              M, 'A → DB (#DS Y2).'),
        _chip(HC245, 'U405', {'DIR': 'VCC', '/OE': '/OE_PCL', **pins('A', nets('PC', 8)),
                              **pins('B', db)}, M, 'PCL → DB (#DS Y3).'),
        _chip(HC245, 'U406', {'DIR': 'VCC', '/OE': '/OE_PCH', **pins('A', nets('PC', 8, 8)),
                              **pins('B', db)}, M, 'PCH → DB (#DS Y4).'),
        _chip(SST39SF010, 'U407', {
            **pins('A', acc[0:4]), **pins('A', db[0:4], 4), 'A8': 'C', 'A9': 'ACC4',
            **pins('A', aluop, 10), 'A15': 'ACC7', 'A16': 'GND',
            '/CE': 'GND', '/OE': 'GND', '/WE': 'VCC',
            **pins('DQ', nets('R', 4)), 'DQ4': 'c4', 'DQ5': 'Zlo', 'DQ6': 'Clo',
        }, M, 'ALU-L (5.2): A0–3 = A[3:0], A4–7 = DB[3:0], A8 = C, A9 = A4, A10–14 = ALUOP, '
              'A15 = A7, A16 = tablo jumper\'ı (GND). D0–3 = R0–3, D4 = c4, D5 = Zlo, '
              'D6 = Clo, D7 boş. Hep etkin. -70.', data=lo, speed=70),
        _chip(SST39SF010, 'U408', {
            **pins('A', acc[4:8]), **pins('A', db[4:8], 4), 'A8': 'c4', 'A9': 'Zlo', 'A10': 'Z',
            **pins('A', aluop, 11), 'A16': 'GND',
            '/CE': 'GND', '/OE': 'GND', '/WE': 'VCC',
            **pins('DQ', nets('R', 4, 4)), 'DQ4': 'Znew', 'DQ5': 'Chi', 'DQ6': 'Nnew',
            'DQ7': 'Vnew',
        }, M, 'ALU-H (5.2): A0–3 = A[7:4], A4–7 = DB[7:4], A8 = c4, A9 = Zlo, A10 = Z, '
              'A11–15 = ALUOP, A16 = GND. D0–3 = R4–7, D4 = Z, D5 = Chi, D6 = N, D7 = V. '
              '-70.', data=hi, speed=70),
    ]
    return Board(chips=chips, pulls={f'DB{i}': 0 for i in range(8)},
                 memories={'ALU_L': chips[6], 'ALU_H': chips[7]},
                 notes=['DB: 8× 10k pull-down (boşta 00).'])


# ----------------------------------------------------------------------------
# CPU yardımcı kapıları (SISTEM-PLANI 1, 15.1; ISA-v0-sentez 8.1 kapı dağılımı)
# ----------------------------------------------------------------------------
def aux_gates():
    M = 'AUX'
    chips = [
        _chip(HC00, 'U501', {
            '1A': 'SPCNT_L', '1B': 'SP_MM0', '1Y': '/SPCNT_HI',
            '2A': 'AB15', '2B': '/FPAGE', '2Y': '/RAM_CE',
            '3A': 'MEMW_L', '3B': 'WSTB', '3Y': '/MWR',
            **_unused_gates((4,)),
        }, M, 'SP üst /CE = NAND(SPCNT, MAX/MIN_alt) (5.1); RAM /CE = NAND(A15, /FPAGE) '
              '(7.2); /MWR = NAND(MEMW_L, WSTB) (7.2). 4. kapı boş.'),
        _chip(HC08, 'U502', {
            '1A': '/MRD', '1B': '/ARD_RD', '1Y': '/RD',
            '2A': '/MWR', '2B': '/ARD_WR', '2Y': '/WR',
            **_unused_gates((3, 4)),   # 5. hafta: 3. kapı /ACCESS = AND(/MRD, /MEMW)
        }, M, '/RD = AND(/MRD, /ARD_RD), /WR = AND(/MWR, /ARD_WR) (2). 3. kapı /ACCESS '
              '(breakpoint, 5. hafta), 4. boş.'),
        _chip(HC32, 'U503', {
            '1A': 'Clo', '1B': 'Chi', '1Y': 'Cnew',
            '2A': '/IOSEL', '2B': '/MEMW', '2Y': '/LED_E',
            '3A': '/WR', '3B': '/VRAMSEL', '3Y': '/VRAM_WE',
            '4A': 'BRQ_s', '4B': 'STOP_G', '4Y': 'STOP',
        }, M, 'C = OR(Clo, Chi) (5.2); /LED_E = OR(/IOSEL, /MEMW) (7.2); VRAM /WE = '
              'OR(/WR, /VRAMSEL) (7.2; VRAM M6\'da, burada taklit X1); STOP\'un son OR\'u '
              'BRQ_s | (…) (3.3).'),
    ]
    b = Board(chips=chips, pulls={'/ARD_RD': 1, '/ARD_WR': 1})
    b.notes.append('Planda yardımcı 74HC00 ×2. 138\'li WAIT çözümüyle (DOGRULAMA 2.5) '
                   'NAND(MEMW_L, /VWR_s) kapısı kalktı ve Johnson 3 NAND + 1 OR oldu; '
                   '12 NAND\'ın 7\'si kullanılıyor (M1 U103: 4, U501: 3). 2. yardımcı 74HC00 '
                   'gereksiz, netlist\'te yok.')
    b.notes.append('/ARD_RD, /ARD_WR: Arduino takılı değilken 10k pull-up (BUSREQ 5. hafta).')
    return b


# ----------------------------------------------------------------------------
# M5: bellek ve I/O (SISTEM-PLANI 7)
# ----------------------------------------------------------------------------
def m5_memory(program=b'', rom_speed=90, ram_data=None):
    M = 'M5'
    ab, db = nets('AB', 16), nets('DB', 8)
    image = bytes(program[:0x8000])
    chips = [
        _chip(SST39SF010, 'U601', {
            **pins('A', ab[:15]), 'A15': 'GND', 'A16': 'GND',
            '/CE': 'AB15', '/OE': '/RD', '/WE': 'VCC', **pins('DQ', db),
        }, M, f'Program ROM (7.1): A0–14 = AB, A15/A16 = bank jumper\'ları (GND: bank 0), '
              f'/CE = A15 (doğrudan kablo), /OE = /RD, /WE = VCC. -{rom_speed} '
              f'(DOGRULAMA 2b: -90 eski stok program ROM\'una).', data=image, speed=rom_speed),
        _chip(CY62256, 'U602', {
            **pins('A', ab[:15]), '/CE': '/RAM_CE', '/OE': '/RD', '/WE': '/WR', **pins('IO', db),
        }, M, 'RAM CY62256-70 (7.1): 8000–EFFF. /CE = NAND(A15, /FPAGE) (U501), '
              '/OE = /RD, /WE = /WR.', data=ram_data),
        _chip(HC20, 'U603', {
            '1A': 'AB15', '1B': 'AB14', '1C': 'AB13', '1D': 'AB12', '1Y': '/FPAGE',
            **_unused_gates((2,), '4'),
        }, M, '/FPAGE = NAND4(A15..A12) (7.2). 2. kapı boş (girişleri GND).'),
        _chip(HC138, 'U604', {
            'A0': 'AB0', 'A1': 'AB1', 'A2': 'AB2', 'E3': 'VCC', '/E1': '/IOSEL', '/E2': '/RD',
            '/Y0': '/KBD_RD', '/Y1': '/STAT_RD',
        }, M, '#IOR (7.2): A0..A2, G1 = VCC (ISA-v0-sentez 6.1), /G2A = /IOSEL, /G2B = /RD. '
              'Y0 /KBD_RD (F800), Y1 /STAT_RD (F801), Y2–Y7 ayrılmış (boş).'),
        _chip(HC377, 'U605', {'/E': '/LED_E', 'CP': 'CLK_IO', **pins('D', db),
                              **pins('Q', nets('LED', 8))},
              M, 'LED portu (7.3): /E = OR(/IOSEL, /MEMW) commit\'te örneklenir, CP = CLK '
                 '(LED dalı). F800–FFFF\'e her yazma buraya.'),
        _chip(HC245, 'U606', {
            'DIR': 'VCC', '/OE': '/STAT_RD',
            **pins('A', nets('DIP', 6)), 'A6': 'VWR_s', 'A7': 'KRDY', **pins('B', db),
        }, M, 'KSTAT (7.3): b7 = KRDY, b6 = VWR_s, b5..b0 = DIP SW5..SW0 → DB, '
              '/OE = /STAT_RD. DIP: anahtar + pull-up/down (burada test tezgâhı girişi).'),
    ]
    return Board(chips=chips, inputs={f'DIP{i}': 0 for i in range(6)},
                 memories={'ROM': chips[0], 'RAM': chips[1]})


# ----------------------------------------------------------------------------
# Test tezgâhı taklitleri: M6 (VRAM) ve M7 (klavye okuma tamponu)
# ----------------------------------------------------------------------------
def stubs(vram_data=None):
    M = 'TB'
    chips = [
        _chip(CY62256, 'X1', {
            **pins('A', nets('AB', 11)), **pins('A', ['GND'] * 4, 11),
            '/CE': 'GND', '/OE': 'VCC', '/WE': '/VRAM_WE', **pins('IO', nets('DB', 8)),
        }, M, 'VRAM taklidi (M6 yok): yalnız yazılır. A0–10 = AB0–10, /WE = '
              'OR(/WR, /VRAMSEL) (U503), /OE = VCC. Gerçekte veri DB → 74HC245 '
              '(/OE = /BUFEN) üzerinden, adres 3× 74HC157 üzerinden gelir; burada '
              'doğrudan DB/AB.', data=vram_data),
        _chip(HC540, 'X2', {
            '/OE1': '/KBD_RD', '/OE2': 'GND', **pins('A', nets('KSR', 8)),
            **pins('/Y', nets('DB', 8)),
        }, M, 'Klavye okuma tamponu taklidi (M7\'nin 74HC540\'ı, /OE1 = /KBD_RD): '
              'KSR0..7 = kaydırma registerının terslenmiş veri bitleri (test tezgâhı; '
              'boşken 00 → DB\'de FF, bus.py ile aynı). KRDY de test tezgâhından; '
              'okuma sonrası temizleme (KCLR) test tezgâhında modellenir.'),
    ]
    return Board(chips=chips,
                 inputs={'VWR_s': 1, 'KRDY': 0, **{f'KSR{i}': 0 for i in range(8)}},
                 memories={'VRAM': chips[0]},
                 notes=['VWR_s gerçekte M1\'deki 2. 74HC175\'te VWR\'den (M6) senkronlanır; '
                        'burada test tezgâhı doğrudan VWR_s\'i sürer (varsayılan 1 = pencere '
                        'açık, NO-VGA jumper\'ı gibi).'])


MODULES = {'M1': m1_clock, 'M2': m2_control, 'M3': m3_address, 'M4': m4_data,
           'AUX': aux_gates, 'M5': m5_memory, 'TB': stubs}


def build(sim=None, program=b'', urom=None, alu_tables=None, rom_speed=90, bank=0,
          mclk_half=125, ram_data=None, vram_data=None, wait_fix=True):
    """Bütün CPU kartını kurar. `sim` verilirse çipler, pull'lar, tie'lar ve girişlerin
    varsayılan değerleri ona eklenir (saat eklenmez). Board döndürür."""
    board = Board.merge([
        m1_clock(mclk_half, wait_fix),
        m2_control(urom, bank),
        m3_address(),
        m4_data(alu_tables),
        aux_gates(),
        m5_memory(program, rom_speed, ram_data),
        stubs(vram_data),
    ])
    if wait_fix:
        board.notes.extend(f'PLAN DÜZELTMESİ: {f}' for f in PLAN_FIXES)
    if sim is not None:
        board.attach(sim)
    return board
