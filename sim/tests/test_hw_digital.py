"""td8.hw.digital: netlist → Digital (.dig) dışa aktarıcı; aynı devrenin td8.hw.Sim'de ve
Digital'de aynı sonucu verdiği.

Çalıştırma (sim/ klasöründen):
    py -3 -m unittest tests.test_hw_digital -v
    py -3 -m tests.test_hw_digital --yaz      sim/digital/ örnek devrelerini yeniden üretir
    py -3 -m tests.test_hw_digital --bench    adımlayıcı hızı (test değil)
    TD8_SLOW=1 py -3 -m unittest tests.test_hw_digital    + uzun koşular (fibonacci ×10)

Yöntem: her örnek devre bir Board'dur. Uyaranlar Sim'de koşulur, Sim'in çıkışları Digital
Testcase'inin beklenen değerleri olur ve `CLI test` bunları Digital'in kendi 74xx modelleriyle
denetler. Ayrıca Sim'in çıkışları Python'da bağımsız bir beklentiyle karşılaştırılır.
Digital bulunamazsa (TD8_DIGITAL_HOME ya da <depo>/../araclar) Digital'i çağıran testler atlanır.
"""

import os
import random
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

from td8 import alu, asm, vectors
from td8.hw import (CHIP_TYPES, CY62256, HC04, HC32, HC74, HC138, HC139, HC161, HC191, HC245,
                    HC273, HC377, HC540, SST39SF010, bus_pins)
from td8.hw import cpu
from td8.hw import digital as dg
from td8.hw import digital_cpu as dc

SETUP = dg.find_digital()
DIG_DIR = dg.SIM_DIR / 'digital'
BUILD = dg.SIM_DIR / 'build'
TIMES = []                                 # (ne, süre sn) — Digital çağrıları


def needs_digital(fn):
    return unittest.skipIf(SETUP is None, 'Digital bulunamadı (TD8_DIGITAL_HOME ya da ../araclar)')(fn)


def tmpdir(test):
    d = Path(tempfile.mkdtemp(prefix='td8dig_'))
    if not os.environ.get('TD8_DIGITAL_KEEP'):
        test.addCleanup(shutil.rmtree, d, True)
    return d


def dtest(what, dig, tests=None, verbose=True):
    r = dg.run_test(dig, tests, verbose=verbose, setup=SETUP)
    TIMES.append((what, r.seconds))
    return r


def tearDownModule():
    if TIMES:
        total = sum(t for _, t in TIMES)
        sys.stderr.write(f'\nDigital çağrıları: {len(TIMES)} adet, toplam {total:.1f} s '
                         f'(en uzun: {max(TIMES, key=lambda x: x[1])[0]} '
                         f'{max(t for _, t in TIMES):.1f} s)\n')


def P(label, nets, default=0):
    return dg.Port(label, nets, default)


# ============================================================================
# Örnek devreler
# ============================================================================
# --- 1. iki 74HC161, CET/TC zinciri ------------------------------------------
def counter_board(broken=False, name='ornek_sayac'):
    common = {'/MR': '/MR', 'CP': 'CLK', 'CEP': 'EN', '/PE': 'VCC',
              'D0': 'GND', 'D1': 'GND', 'D2': 'GND', 'D3': 'GND'}
    u1 = HC161('U1', {**common, 'CET': 'EN', **bus_pins('Q', 'Q', 4), 'TC': 'TC_LO'},
               module='M3', note='Q[3:0]')
    # bozuk: üst sayacın CET'i TC_LO yerine EN'e bağlı (zincir yok)
    u2 = HC161('U2', {**common, 'CET': 'EN' if broken else 'TC_LO',
                      **bus_pins('Q', 'Q', 4, net_start=4), 'TC': 'TC_HI'},
               module='M3', note='Q[7:4]; CET = TC_LO')
    return dg.Board(name, [u1, u2], inputs={'/MR': 1, 'EN': 0},
                    outputs=[P('Q', dg.bus_nets('Q', 8)), 'TC_HI'], clock='CLK',
                    title='İki 74HC161: CET/TC zinciriyle 8 bit sayıcı')


def counter_steps():
    return ([({'MR_n': 0}, False), ({'MR_n': 1, 'EN': 1}, False)] + [({}, True)] * 257
            + [({'EN': 0}, True), ({'EN': 0}, True)])


# --- 2. 74HC138 + 74HC139 + 74HC04 kod çözme --------------------------------
def decode_board(name='ornek_kod_cozme'):
    u1 = HC138('U1', {'A0': 'S0', 'A1': 'S1', 'A2': 'S2', '/E1': '/E1', '/E2': '/E2', 'E3': 'E3',
                      **{f'/Y{i}': f'/Y{i}' for i in range(8)}}, module='M5', note='S → /Y')
    u2 = HC139('U2', {'/1E': '/EA', '1A0': 'S0', '1A1': 'S1',
                      **{f'/1Y{i}': f'/YA{i}' for i in range(4)},
                      '/2E': '/EB', '2A0': 'T0', '2A1': 'T1',
                      **{f'/2Y{i}': f'/YB{i}' for i in range(4)}}, module='M5')
    u3 = HC04('U3', {**{f'{i + 1}A': f'/YA{i}' for i in range(4)},
                     **{f'{i + 1}Y': f'YA{i}' for i in range(4)},
                     '5A': 'EB', '5Y': '/EB', '6A': 'GND'}, module='M5', note='YA etkin-yüksek, /EB')
    ins = [P('S', dg.bus_nets('S', 3)), '/E1', '/E2', 'E3', '/EA', P('T', dg.bus_nets('T', 2)),
           'EB']
    outs = [P('Y_n', [f'/Y{i}' for i in range(8)]), P('YA', dg.bus_nets('YA', 4)),
            P('YB_n', [f'/YB{i}' for i in range(4)])]
    return dg.Board(name, [u1, u2, u3], inputs=ins, outputs=outs,
                    title='74HC138 + 74HC139 + 74HC04 kod çözme')


def decode_steps():
    steps = []
    for k in range(1 << 10):
        steps.append({'S': k & 7, 'E1_n': k >> 3 & 1, 'E2_n': k >> 4 & 1, 'E3': k >> 5 & 1,
                      'EA_n': k >> 6 & 1, 'T': k >> 7 & 3, 'EB': k >> 9 & 1})
    return steps


def decode_expect(v):
    en = v['E3'] and not v['E1_n'] and not v['E2_n']
    y = 0xFF ^ (1 << v['S']) if en else 0xFF
    ya = (1 << (v['S'] & 3)) if not v['EA_n'] else 0
    yb = 0xF ^ (1 << v['T']) if v['EB'] else 0xF
    return {'Y_n': y, 'YA': ya, 'YB_n': yb}


# --- 3. 245'ler + 540 ile tri-state bus + pull-down ---------------------------
def bus_board(name='ornek_bus'):
    bus = dg.bus_nets('BUS', 8)
    u1 = HC245('U1', {'DIR': 'VCC', '/OE': '/OEA', **bus_pins('A', 'SA', 8),
                      **bus_pins('B', 'BUS', 8)}, module='BUS', note='SA → BUS')
    u2 = HC245('U2', {'DIR': 'VCC', '/OE': '/OEB', **bus_pins('A', 'SB', 8),
                      **bus_pins('B', 'BUS', 8)}, module='BUS', note='SB → BUS')
    u3 = HC540('U3', {'/OE1': '/OEC', '/OE2': 'GND', **bus_pins('A', 'SC', 8),
                      **bus_pins('/Y', 'BUS', 8)}, module='BUS', note='~SC → BUS')
    u4 = HC245('U4', {'DIR': 'GND', '/OE': 'GND', **bus_pins('A', 'RD', 8),
                      **bus_pins('B', 'BUS', 8)}, module='BUS', note='BUS → RD (B→A)')
    ins = [P('SA', dg.bus_nets('SA', 8)), P('SB', dg.bus_nets('SB', 8)),
           P('SC', dg.bus_nets('SC', 8)), ('/OEA', 1), ('/OEB', 1), ('/OEC', 1)]
    return dg.Board(name, [u1, u2, u3, u4], pulls={n: 0 for n in bus}, inputs=ins,
                    outputs=[P('BUS', bus), P('RD', dg.bus_nets('RD', 8))],
                    title='Tri-state bus: 2× 74HC245 + 74HC540 kaynak, pull-down, 74HC245 okuyucu')


def bus_steps(n=60, seed=1):
    rng = random.Random(seed)
    steps, expect = [], []
    for k in range(n):
        src = None if k % 2 else rng.choice('ABCN')     # kaynak değişimleri arasında boş satır
        v = {'SA': rng.randrange(256), 'SB': rng.randrange(256), 'SC': rng.randrange(256),
             'OEA_n': int(src != 'A'), 'OEB_n': int(src != 'B'), 'OEC_n': int(src != 'C')}
        steps.append(v)
        bus = {'A': v['SA'], 'B': v['SB'], 'C': v['SC'] ^ 0xFF}.get(src, 0)
        expect.append({'BUS': bus, 'RD': bus})
    return steps, expect


# --- 4. iki flash'lı ALU (SISTEM-PLANI 5.2) -----------------------------------
def alu_board(lo_data, hi_data, lo_file, hi_file, name='ornek_alu', swap=False):
    op = [f'ALUOP{i}' for i in range(5)]
    a = dg.bus_nets('A', 8)
    db = dg.bus_nets('DB', 8)
    lo_addr = a[0:4] + db[0:4] + ['CIN', a[4]] + op + [a[7], 'GND']
    hi_addr = a[4:8] + db[4:8] + ['C4', 'ZLO', 'ZIN'] + op + ['GND']
    if swap:                                             # bozuk: ALU-H A8/A9 yer değiştirmiş
        hi_addr[8], hi_addr[9] = hi_addr[9], hi_addr[8]
    ctl = {'/CE': 'GND', '/OE': 'GND', '/WE': 'VCC'}
    u1 = SST39SF010('U1', {**{f'A{i}': n for i, n in enumerate(lo_addr)}, **ctl,
                           'DQ0': 'R0', 'DQ1': 'R1', 'DQ2': 'R2', 'DQ3': 'R3',
                           'DQ4': 'C4', 'DQ5': 'ZLO', 'DQ6': 'CLO'},
                    data=lo_data, module='M4', note='ALU-L')
    u2 = SST39SF010('U2', {**{f'A{i}': n for i, n in enumerate(hi_addr)}, **ctl,
                           'DQ0': 'R4', 'DQ1': 'R5', 'DQ2': 'R6', 'DQ3': 'R7',
                           'DQ4': 'ZOUT', 'DQ5': 'CHI', 'DQ6': 'NOUT', 'DQ7': 'VOUT'},
                    data=hi_data, module='M4', note='ALU-H')
    u3 = HC32('U3', {'1A': 'CLO', '1B': 'CHI', '1Y': 'COUT',
                     '2A': 'GND', '2B': 'GND', '3A': 'GND', '3B': 'GND', '4A': 'GND', '4B': 'GND'},
              module='M4', note='C = Clo OR Chi')
    ins = [P('OP', op), P('A', a), P('B', db), P('Cin', 'CIN'), P('Zin', 'ZIN')]
    outs = [P('R', dg.bus_nets('R', 8)), P('Z', 'ZOUT'), P('C', 'COUT'), P('N', 'NOUT'),
            P('V', 'VOUT')]
    return dg.Board(name, [u1, u2, u3], inputs=ins, outputs=outs,
                    rom_files={'U1': lo_file, 'U2': hi_file},
                    title='M4 ALU: 2× SST39SF010 (ALU-L, ALU-H) + 74HC32')


def vector_steps(text):
    names, rows = vectors.parse_table(text)
    ins = ['OP', 'A', 'B', 'Cin', 'Zin']
    steps = [{k: r[names.index(k)] for k in ins} for r in rows]
    expect = [{k: r[names.index(k)] for k in ('R', 'Z', 'C', 'N', 'V')} for r in rows]
    return steps, expect


# --- 5. SRAM ----------------------------------------------------------------
def sram_board(name='ornek_sram'):
    u1 = CY62256('U1', {**bus_pins('A', 'ADDR', 15), **bus_pins('IO', 'D', 8),
                        '/CE': '/CE', '/OE': '/OE', '/WE': '/WE'}, module='M5', note='RAM')
    d = dg.bus_nets('D', 8)
    return dg.Board(name, [u1], inputs=[P('ADDR', dg.bus_nets('ADDR', 15)), ('/CE', 1), ('/OE', 1),
                                        ('/WE', 1), dg.Port('D', d, default=None)],
                    outputs=[P('Q', d)], title='CY62256: /WE darbesiyle yaz, /OE ile oku')


def sram_steps(n=12, seed=2):
    rng = random.Random(seed)
    addrs = rng.sample(range(1 << 15), n)
    vals = [rng.randrange(256) for _ in addrs]
    steps, expect = [], []

    def add(v, q):
        steps.append(v)
        expect.append({'Q': q})

    for a, v in zip(addrs, vals):                         # yazma: /WE darbesi, /OE kapalı
        add({'ADDR': a, 'D': v, 'CE_n': 0}, v)
        add({'WE_n': 0}, v)
        add({'WE_n': 1}, v)
        add({'D': None, 'CE_n': 1}, None)
    for a, v in zip(addrs, vals):                         # okuma
        add({'ADDR': a, 'CE_n': 0}, None)                 # /OE kapalı: bus serbest
        add({'OE_n': 0}, v)
        add({'OE_n': 1}, None)
        add({'CE_n': 1, 'OE_n': 0}, None)                 # /CE kapalı: bus serbest
        add({'OE_n': 1}, None)
    add({'ADDR': addrs[0], 'D': 0x5A, 'CE_n': 0}, 0x5A)   # üzerine yaz, geri oku
    add({'WE_n': 0}, 0x5A)
    add({'WE_n': 1}, 0x5A)                                # veri /WE'den sonra bırakılır (tutma)
    add({'D': None}, None)
    add({'OE_n': 0}, 0x5A)
    add({'OE_n': 1, 'CE_n': 1}, None)
    return steps, expect


# --- 6. 74HC74 + 273 + 377 + 191 ardışıl -------------------------------------
def seq_board(name='ornek_ardisil'):
    din = dg.bus_nets('DIN', 8)
    u1 = HC74('U1', {'/1RD': '/R', '/1SD': '/S', '1D': 'DIN0', '1CP': 'CLK', '1Q': 'FQ1',
                     '/1Q': '/FQ1', '/2RD': 'VCC', '/2SD': 'VCC', '2D': 'FQ1', '2CP': 'CLK',
                     '2Q': 'FQ2'}, module='SEQ', note='FF1: /R /S; FF2: FQ1 kaydırır')
    u2 = HC273('U2', {'/MR': '/MR', 'CP': 'CLK', **bus_pins('D', 'DIN', 8),
                      **bus_pins('Q', 'R273_', 8)}, module='SEQ', note='asenkron /MR')
    u3 = HC377('U3', {'/E': '/E', 'CP': 'CLK', **bus_pins('D', 'DIN', 8),
                      **bus_pins('Q', 'R377_', 8)}, module='SEQ', note='senkron /E')
    u4 = HC191('U4', {'/PL': '/PL', '/CE': '/CE', 'D/U': 'DU', 'CP': 'CLKN',
                      **bus_pins('D', 'DIN', 4), **bus_pins('Q', 'C', 4),
                      'MAX/MIN': 'MAXMIN', '/RC': '/RC'}, module='SEQ',
               note='CP = NOT CLK: /CE, D/U CP yüksekken değişir')
    u5 = HC04('U5', {'1A': 'CLK', '1Y': 'CLKN', '2A': 'GND', '3A': 'GND', '4A': 'GND',
                     '5A': 'GND', '6A': 'GND'}, module='SEQ')
    ins = [P('DIN', din), ('/R', 1), ('/S', 1), ('/MR', 1), ('/E', 1), ('/PL', 1), ('/CE', 1),
           ('DU', 0)]
    outs = ['FQ1', '/FQ1', 'FQ2', P('R273', dg.bus_nets('R273_', 8)),
            P('R377', dg.bus_nets('R377_', 8)), P('C', dg.bus_nets('C', 4)), 'MAXMIN', '/RC']
    return dg.Board(name, [u1, u2, u3, u4, u5], inputs=ins, outputs=outs, clock='CLK',
                    title='Ardışıl: 74HC74, 74HC273, 74HC377, 74HC191')


SEQ_SCRIPT = [
    # (değerler, darbe, beklenen çıkışların bir kısmı)
    ({'R_n': 0}, False, {'FQ1': 0, 'FQ1_n': 1}),
    ({'R_n': 1, 'S_n': 0}, False, {'FQ1': 1, 'FQ1_n': 0}),
    ({'R_n': 0}, False, {'FQ1': 1, 'FQ1_n': 1}),             # /SD = /RD = 0 → Q = /Q = 1
    ({'R_n': 1}, False, {'FQ1': 1, 'FQ1_n': 0}),
    ({'S_n': 1, 'DIN': 0x00}, True, {'FQ1': 0, 'FQ2': 1}),
    ({'DIN': 0xA5}, True, {'FQ1': 1, 'FQ2': 0, 'R273': 0xA5, 'R377': 0, 'C': 0}),
    ({'MR_n': 0}, False, {'R273': 0}),                        # asenkron temizleme
    ({'MR_n': 1, 'E_n': 0, 'DIN': 0x3C}, True, {'R273': 0x3C, 'R377': 0x3C}),
    ({'E_n': 1, 'DIN': 0xFF}, True, {'R273': 0xFF, 'R377': 0x3C}),   # /E = 1: tutar
    ({'PL_n': 0, 'DIN': 0x0D}, False, {'C': 0xD}),            # asenkron yükleme
    ({'PL_n': 1}, False, {'C': 0xD}),
    ({'CE_n': 0, 'DU': 0}, True, {'C': 0xE}),
    ({}, True, {'C': 0xF, 'MAXMIN': 1}),
    ({}, True, {'C': 0x0, 'MAXMIN': 0}),
    ({}, True, {'C': 0x1}),
    ({'DU': 1}, False, {'C': 0x1, 'MAXMIN': 0}),
    ({}, True, {'C': 0x0, 'MAXMIN': 1}),
    ({}, True, {'C': 0xF, 'MAXMIN': 0}),
    ({'CE_n': 1}, True, {'C': 0xF}),
]


def seq_steps(n_random=120, seed=3):
    steps = [(v, p) for v, p, _ in SEQ_SCRIPT]
    rng = random.Random(seed)
    pl, din = 1, 0xFF
    for _ in range(n_random):
        npl = int(rng.random() > 0.1)
        if not (npl and not pl):                         # /PL bırakılırken D sabit (kurulum)
            din = rng.randrange(256)
        pl = npl
        r = rng.random()
        steps.append(({'DIN': din, 'PL_n': pl, 'CE_n': int(rng.random() < 0.3),
                       'DU': rng.randrange(2), 'E_n': rng.randrange(2),
                       'MR_n': int(rng.random() > 0.05),
                       'R_n': int(r > 0.05), 'S_n': int(r > 0.1 or r < 0.05)},
                      rng.random() > 0.1))
    return steps


# --- 7. iz: sayıcı → flash → 377 (AB, DB, CW) ---------------------------------
def trace_data(bad_at=None):
    data = bytes(((i * 37 + 11) & 0xFF) for i in range(256))
    if bad_at is not None:
        data = data[:bad_at] + bytes([data[bad_at] ^ 0x40]) + data[bad_at + 1:]
    return data


def trace_board(data, name='ornek_iz'):
    common = {'/MR': '/MR', 'CP': 'CLK', 'CEP': 'VCC', '/PE': 'VCC',
              'D0': 'GND', 'D1': 'GND', 'D2': 'GND', 'D3': 'GND'}
    u1 = HC161('U1', {**common, 'CET': 'VCC', **bus_pins('Q', 'AB', 4), 'TC': 'TC0'},
               module='SAYAC', note='AB[3:0]')
    u2 = HC161('U2', {**common, 'CET': 'TC0', **bus_pins('Q', 'AB', 4, net_start=4)},
               module='SAYAC', note='AB[7:4]')
    u3 = SST39SF010('U3', {**bus_pins('A', 'AB', 8), **{f'A{i}': 'GND' for i in range(8, 17)},
                           '/CE': 'GND', '/OE': 'GND', '/WE': 'VCC', **bus_pins('DQ', 'DB', 8)},
                    data=data, module='BELLEK', note='DB = tablo[AB]')
    u4 = HC377('U4', {'/E': 'GND', 'CP': 'CLK', **bus_pins('D', 'DB', 8), **bus_pins('Q', 'CW', 8)},
               module='LATCH', note='CW = önceki DB')
    return dg.Board(name, [u1, u2, u3, u4], inputs={'/MR': 1},
                    outputs=[P('AB', dg.bus_nets('AB', 8)), P('DB', dg.bus_nets('DB', 8)),
                             P('CW', dg.bus_nets('CW', 8)), 'TC0'],
                    clock='CLK', title='İz örneği: sayıcı → flash → 74HC377 (AB, DB, CW)')


def trace_from_rows(rows):
    return [(k, r['AB'], r['DB'], r['CW']) for k, r in enumerate(rows)]


def trace_ref(data, n):
    return [(k, k & 0xFF, data[k & 0xFF], data[(k - 1) & 0xFF] if k else 0) for k in range(n + 1)]


# --- tüm 74HC türleri tek devrede --------------------------------------------
CLOCK_PINS = {'74HC74': ('1CP', '2CP'), '74HC161': ('CP',), '74HC163': ('CP',),
              '74HC164': ('CP',), '74HC166': ('CP',), '74HC175': ('CP',), '74HC191': ('CP',),
              '74HC273': ('CP',), '74HC377': ('CP',)}
INV_CLOCK = ('74HC166', '74HC191')        # CP = NOT CLK: /CE, D/U CP yüksekken değişsin


def all_chips_board(name='ornek_tum_cipler'):
    chips, ins, outs = [], [], []
    for kind, cls in CHIP_TYPES.items():
        if not kind.startswith('74HC'):
            continue
        ref = 'U' + kind[4:]
        pins = {}
        # açılış: /OE kapalı (245 çakışmasın), /PL ve /CE pasif. Digital'de CLKN (= NOT CLK)
        # model kurulurken 0 → 1 olur ve 166/191 bunu kenar sayar; Sim'de açılış kenarı yok.
        for p, d in cls.DIRS.items():
            if p in CLOCK_PINS.get(kind, ()):
                pins[p] = 'CLKN' if kind in INV_CLOCK else 'CLK'
                continue
            net = f'{ref}_{dg.safe_name(p)}'
            pins[p] = net
            if d == 'in':
                ins.append(dg.Port(net, net, default=int(p in ('/OE', '/OE1', '/OE2', '/G', '/PL', '/CE'))))
            elif d == 'bidir':
                ins.append(dg.Port(net, net, default=None))
                outs.append(dg.Port(net + '_o', net))
            else:
                outs.append(dg.Port(net, net))
        chips.append(cls(ref, pins, module=kind))
    chips.append(HC04('UINV', {'1A': 'CLK', '1Y': 'CLKN', '2A': 'GND', '3A': 'GND', '4A': 'GND',
                               '5A': 'GND', '6A': 'GND'}, module='saat', note='CLKN = NOT CLK'))
    return dg.Board(name, chips, inputs=ins, outputs=outs, clock='CLK',
                    title='Bütün 74HC türleri: rastgele uyaranla Sim ↔ Digital')


def all_chips_steps(board, n=250, seed=7):
    rng = random.Random(seed)
    labels = [p.label for p in board.inputs]
    steps = []
    pl = {'U191': 1}
    for k in range(n):
        v = {}
        for lab in labels:
            if not lab.startswith(('U245_', 'U191_')):
                v[lab] = rng.randrange(2)
        # 191: /PL bırakılırken D sabit
        npl = int(rng.random() > 0.1)
        if not (npl and not pl['U191']):
            for i in range(4):
                v[f'U191_D{i}'] = rng.randrange(2)
        pl['U191'] = npl
        v.update(U191_PL_n=npl, U191_CE_n=int(rng.random() < 0.2), U191_D_U=rng.randrange(2))
        # 245: (A) sürüş, (B) kapat, (C) iki tarafı da TB sürer — çakışmasız sıra
        phase = k % 3
        if phase == 0:
            d = rng.randrange(2)
            v.update(U245_OE_n=0, U245_DIR=d)
            for i in range(8):
                src, dst = (('A', 'B') if d else ('B', 'A'))
                v[f'U245_{src}{i}'] = rng.randrange(2)
                v[f'U245_{dst}{i}'] = None
        elif phase == 1:
            v['U245_OE_n'] = 1
        else:
            for i in range(8):
                v[f'U245_A{i}'] = rng.randrange(2)
                v[f'U245_B{i}'] = rng.randrange(2)
        steps.append((v, True))
    return steps


# ============================================================================
# Testler: Digital gerekmeyenler
# ============================================================================
class TestExporter(unittest.TestCase):
    def test_safe_name(self):
        for net, want in (('/MRD', 'MRD_n'), ('/RESET_s', 'RESET_s_n'), ('U3.Q0', 'U3_Q0'),
                          ('/P=Q', 'P_Q_n'), ('DB7', 'DB7'), ('1Y', 'N1Y'), ('MAX/MIN', 'MAX_MIN')):
            self.assertEqual(dg.safe_name(net), want)
        # vectors.py ile aynı kural (DECODE_OUT: MRD_n, RAM_CE_n ...)
        self.assertEqual(dg.safe_name('/RAM_CE'), 'RAM_CE_n')
        with self.assertRaises(dg.DigitalError):
            dg.name_map(['/A', 'A_n'])

    def test_every_chip_type_maps(self):
        for kind, cls in CHIP_TYPES.items():
            spec = dg.dil_spec(cls)
            self.assertEqual(spec.legs, max(cls.PINOUT.values()) + max(cls.PINOUT.values()) % 2,
                             kind)

    def test_mismatch_is_reported(self):
        class Bad(HC161):
            KIND = '74HC161'
            DIRS = dict(HC161.DIRS, TC='in')            # yön uyuşmazlığı
        dg._SPEC_CACHE.pop('74HC161', None)
        try:
            with self.assertRaises(dg.DigitalError) as cm:
                dg.dil_spec(Bad)
            self.assertIn('bacak 15', str(cm.exception))
        finally:
            dg._SPEC_CACHE.pop('74HC161', None)

        class Short(HC161):
            KIND = '74HC161'
            PINOUT = {p: l for p, l in HC161.PINOUT.items() if p != 'TC'}
            DIRS = {p: d for p, d in HC161.DIRS.items() if p != 'TC'}
        try:
            with self.assertRaises(dg.DigitalError):
                dg.dil_spec(Short)
        finally:
            dg._SPEC_CACHE.pop('74HC161', None)

    def test_pin_positions(self):
        # keşif raporu e.1: 74161 pos (0,0): ~CLR (0,0), GND (0,280), ~LD (120,280), VCC (120,0)
        spec = dg.dil_spec(HC161)
        self.assertEqual(spec.pin_xy(1, 0, 0), (0, 0))
        self.assertEqual(spec.pin_xy(8, 0, 0), (0, 280))
        self.assertEqual(spec.pin_xy(9, 0, 0), (120, 280))
        self.assertEqual(spec.pin_xy(16, 0, 0), (120, 0))
        self.assertEqual(dg.dil_spec(HC191).pin_xy(16, 0, 0), (160, 0))       # Width 7

    def test_data_string(self):
        self.assertEqual(dg.data_string(bytes([0x12, 0x34, 0, 0, 0, 0, 0xFF, 0, 0])),
                         '12,34,4*0,ff')
        self.assertEqual(dg.data_string(b'\xff' * 1000), '1000*ff')

    def test_deterministic(self):
        a = dg.render(counter_board(), DIG_DIR, 'x')
        b = dg.render(counter_board(), DIG_DIR, 'x')
        self.assertEqual(a, b)
        lo, hi = alu.build_tables()
        b = alu_board(lo, hi, BUILD / 'alu_lo.hex', BUILD / 'alu_hi.hex')
        a = dg.render(b, DIG_DIR, rom_mode='file')
        self.assertIn('<file>../build/alu_lo.hex</file>', a['TD8_SST39SF010_alu_lo.dig'])
        self.assertIn('<boolean>true</boolean>', a['TD8_SST39SF010_alu_lo.dig'])
        a = dg.render(b, DIG_DIR)                              # gömülü
        self.assertIn(f'<data>{dg.data_string(lo)}</data>', a['TD8_SST39SF010_alu_lo.dig'])

    def test_validate_warns(self):
        u = HC04('U1', {'1A': 'NOWHERE', '2A': 'GND', '3A': 'GND', '4A': 'GND', '5A': 'GND',
                        '6A': 'GND'})
        w = dg.Board('x', [u]).validate()
        self.assertTrue(any('NOWHERE' in s for s in w), w)
        with self.assertRaises(dg.DigitalError):
            dg.Board('x', [u], inputs={'A': 0}, outputs=[dg.Port('A', 'NOWHERE')]).validate()

    def test_module_board(self):
        b = trace_board(trace_data())
        m = dg.module_board(b, 'BELLEK')
        self.assertEqual([p.label for p in m.inputs], [f'AB{i}' for i in range(8)])
        self.assertEqual([p.label for p in m.outputs], [f'DB{i}' for i in range(8)])
        self.assertIsNone(m.clock)
        s = dg.module_board(b, 'SAYAC')
        self.assertEqual(s.clock, 'CLK')
        self.assertEqual([p.label for p in s.inputs], ['MR_n'])
        self.assertIn('TC0', [p.label for p in s.outputs])

    def test_committed_examples_up_to_date(self):
        for name, files in example_files().items():
            for fname, text in files.items():
                path = DIG_DIR / fname
                self.assertTrue(path.is_file(), f'{path} yok: py -3 -m tests.test_hw_digital --yaz')
                self.assertEqual(path.read_bytes(), text.encode('utf-8'),
                                 f'{fname} eski: py -3 -m tests.test_hw_digital --yaz')


# ============================================================================
# Testler: Sim ↔ Digital
# ============================================================================
@needs_digital
class TestDigital(unittest.TestCase):
    maxDiff = 2000

    def check(self, board, steps, expect=None, broken=None):
        """Sim'de koş, beklentiyle karşılaştır, Testcase'i Digital'de koş; TestRun döndür."""
        d = tmpdir(self)
        rows, states, sim = dg.simulate(board, steps)
        self.assertEqual(sim.violations, [], sim.violations[:5])
        if expect is not None:
            for i, (r, e) in enumerate(zip(rows, expect)):
                for k, v in e.items():
                    self.assertEqual(r[k], v, f'Sim satır {i} {k}: {states[i]}')
        tc = dg.testcase_text(board, steps, rows, states)
        target = broken or board
        dg.export(target, d / f'{target.name}.dig', tests=tc)
        r = dtest(target.name, d / f'{target.name}.dig')
        return r

    def assertPassed(self, r):
        self.assertTrue(r.passed, r.summary()[:3000])

    def test_0_library_table_matches_installed_digital(self):
        """digital._LIB (bacak etiketleri, yön, Width) kurulu Digital'in 74xx kütüphanesiyle aynı."""
        self.assertEqual(dg.scan_library(SETUP.library), dg._LIB)

    # 1 ----------------------------------------------------------------------
    def test_1_counter_chain(self):
        steps = counter_steps()
        q = [0, 0] + [(k + 1) & 0xFF for k in range(257)] + [1, 1]
        expect = [{'Q': v, 'TC_HI': int(v == 255 and i < 259)} for i, v in enumerate(q)]
        r = self.check(counter_board(), steps, expect)
        self.assertPassed(r)

    def test_1b_broken_counter_fails_in_digital(self):
        """Bozuk zincir (U2.CET = EN): beklenenler doğru devreden; Digital KALMALI."""
        r = self.check(counter_board(), counter_steps(),
                       broken=counter_board(broken=True, name='bozuk_sayac'))
        self.assertEqual(r.returncode, 1, r.summary()[:2000])
        self.assertFalse(r.passed)
        bad = r.mismatches()
        self.assertTrue(bad)
        # ilk fark: 2 başlangıç satırı + 1. darbe → Q = 0x01 beklenirken üst nibble da saydı (0x11)
        test, row, col, exp, found = bad[0]
        self.assertEqual((row, col, int(exp, 16), int(found, 16)), (2, 'Q', 0x01, 0x11), bad[:3])

    # 2 ----------------------------------------------------------------------
    def test_2_decode_truth_table(self):
        steps = decode_steps()
        r = self.check(decode_board(), steps, [decode_expect(s) for s in steps])
        self.assertPassed(r)

    # 3 ----------------------------------------------------------------------
    def test_3_tristate_bus(self):
        steps, expect = bus_steps()
        self.assertIn(0, [e['BUS'] for e in expect])
        r = self.check(bus_board(), steps, expect)
        self.assertPassed(r)

    def test_3b_bus_conflict_is_an_error(self):
        """İki 245 aynı anda farklı değer sürerse: Sim 'cakisma', Digital kısa devre hatası."""
        b = bus_board()
        sim = dg.build_sim(bus_board())
        sim.run_for(1000)
        for i in range(8):
            sim.set(f'SA{i}', (0x0F >> i) & 1, who='port:SA')
            sim.set(f'SB{i}', (0xF0 >> i) & 1, who='port:SB')
        sim.set('/OEA', 0, who='port:OEA_n')
        sim.set('/OEB', 0, who='port:OEB_n')
        sim.run_for(1000)
        self.assertIn('cakisma', sim.summary())
        d = tmpdir(self)
        tc = 'SA SB SC OEA_n OEB_n OEC_n BUS RD\n0x0F 0xF0 0 1 1 1 0 0\n0x0F 0xF0 0 0 0 1 X X\n'
        dg.export(b, d / f'{b.name}.dig', tests=tc)
        r = dtest('bus_cakisma', d / f'{b.name}.dig')
        self.assertFalse(r.passed)
        self.assertIn('short circuit', r.output)

    # 4 ----------------------------------------------------------------------
    def test_4_alu_10000_vectors(self):
        d = tmpdir(self)
        lo, hi = alu.build_tables()
        (d / 'rom').mkdir()
        dg.write_raw_hex(d / 'rom' / 'alu_lo.hex', lo)
        dg.write_raw_hex(d / 'rom' / 'alu_hi.hex', hi)
        lof, hif = d / 'rom' / 'alu_lo.hex', d / 'rom' / 'alu_hi.hex'
        d = d / 'devre'
        d.mkdir()
        text = vectors.alu_vectors(10000, seed=1)          # = py -3 cli.py vectors alu -n 10000
        steps, expect = vector_steps(text)
        self.assertEqual(len(steps), 10000)
        t0 = time.perf_counter()
        rows, states, sim = dg.simulate(alu_board(lo, hi, lof, hif), steps)
        TIMES.append(('(Sim) alu 10000', time.perf_counter() - t0))
        self.assertEqual(sim.violations, [])
        self.assertEqual(rows, expect)                     # Sim = alu_ref (vektördeki beklenen)
        (d / 'alu_test.dig').write_text(dg.test_dig(text, 'alu10000'), encoding='utf-8')
        for mode in ('embed', 'file'):
            b = alu_board(lo, hi, lof, hif, name=f'alu_{mode}')
            dg.export(b, d / f'{b.name}.dig', rom_mode=mode)
            r = dtest(f'alu 10000 ({mode})', d / f'{b.name}.dig', d / 'alu_test.dig',
                      verbose=False)
            self.assertPassed(r)
            self.assertEqual(r.results, [('alu10000', 'passed')])
        self.assertIn('<file>../rom/alu_lo.hex</file>',
                      (d / 'TD8_SST39SF010_alu_lo.dig').read_text(encoding='utf-8'))
        # göreli yol ÇALIŞMA KLASÖRÜNE göre çözülür: başka klasörden çalıştırınca bulunamaz
        r = dg.run_test(d / 'alu_file.dig', d / 'alu_test.dig', setup=SETUP, cwd=d.parent.parent)
        self.assertFalse(r.passed)
        self.assertIn('alu_lo.hex', r.output)
        # bozuk: ALU-H'nin A8/A9'u yer değiştirmiş → kalmalı
        bb = alu_board(lo, hi, lof, hif, name='bozuk_alu', swap=True)
        dg.export(bb, d / 'bozuk_alu.dig')
        r = dtest('bozuk alu 10000', d / 'bozuk_alu.dig', d / 'alu_test.dig', verbose=False)
        self.assertEqual(r.returncode, 1, r.summary()[:1000])

    # 5 ----------------------------------------------------------------------
    def test_5_sram(self):
        steps, expect = sram_steps()
        r = self.check(sram_board(), steps, expect)
        self.assertPassed(r)

    # 6 ----------------------------------------------------------------------
    def test_6_sequential(self):
        steps = seq_steps()
        expect = [e for _, _, e in SEQ_SCRIPT]
        r = self.check(seq_board(), steps, expect)
        self.assertPassed(r)

    def test_6b_all_chip_types_random(self):
        b = all_chips_board()
        r = self.check(b, all_chips_steps(b))
        bad = r.mismatches()
        chips = sorted({c.split('_')[0] for _, _, c, _, _ in bad})
        self.assertTrue(r.passed, f'farklı çipler: {chips}; ilk: {bad[:5]}\n{r.summary()[:500]}')

    # 7 ----------------------------------------------------------------------
    def test_7_trace_stepper(self):
        d = tmpdir(self)
        n = 300
        data = trace_data()
        rows, _, sim = dg.simulate(trace_board(data), [{}] + [({}, True)] * n)
        ref = trace_from_rows(rows)
        self.assertEqual(ref, trace_ref(data, n))          # Sim = bağımsız beklenti
        b = trace_board(data)
        dg.export(b, d / f'{b.name}.dig')
        st = dg.run_stepper(d / f'{b.name}.dig', n, signals=['AB', 'DB', 'CW'], setup=SETUP)
        TIMES.append(('stepper 300', st.seconds))
        self.assertEqual(st.names, ['CYC', 'AB', 'DB', 'CW'])
        got = vectors.parse_trace(st.text)
        self.assertEqual(vectors.compare_traces(ref, got)[0], None,
                         vectors.compare_traces(ref, got)[1])
        # tetikli: TC0'ın yükselen kenarından hemen önceki değerler (AB = 14, 30, ...)
        st2 = dg.run_stepper(d / f'{b.name}.dig', 100, trigger='TC0', signals=['AB', 'TC0'],
                             setup=SETUP)
        self.assertEqual(st2.column('AB'), [14, 30, 46, 62, 78, 94])
        self.assertEqual(st2.column('CYC'), [14, 30, 46, 62, 78, 94])
        # bozuk flash içeriği: compare_traces ilk farkı bulmalı
        bad = trace_board(trace_data(bad_at=37), name='bozuk_iz')
        dg.export(bad, d / 'bozuk_iz.dig')
        st3 = dg.run_stepper(d / 'bozuk_iz.dig', n, signals=['AB', 'DB', 'CW'], setup=SETUP)
        i, msg = vectors.compare_traces(ref, vectors.parse_trace(st3.text))
        self.assertEqual(i, 37, msg)
        self.assertIn('DB beklenen', msg)
        # giriş ayarlama: /MR 5. periyottan önce 0, 7.'den önce 1
        st4 = dg.run_stepper(d / f'{b.name}.dig', 10, signals=['AB'],
                             sets=[('MR_n', 0, 5), ('MR_n', 1, 7)], setup=SETUP)
        self.assertEqual(st4.column('AB'), [0, 1, 2, 3, 4, 0, 0, 0, 1, 2, 3])

    def test_7b_modules(self):
        """export_all: modül modül .dig + tek parça; her modül Sim ↔ Digital."""
        d = tmpdir(self)
        data = trace_data()
        written = dg.export_all(trace_board(data), d)
        names = sorted(p.name for p in written)
        self.assertEqual(len(names), 5, names)               # flash alt devresi tek, paylaşılır
        self.assertEqual(names[1:], ['bellek.dig', 'latch.dig', 'ornek_iz.dig', 'sayac.dig'])
        self.assertTrue(names[0].startswith('TD8_SST39SF010_h'), names)
        rng = random.Random(5)
        for mod in ('SAYAC', 'BELLEK', 'LATCH'):
            mb = dg.module_board(trace_board(data), mod)
            steps = []
            for _ in range(40):
                v = {p.label: rng.randrange(2) for p in mb.inputs if p.label != 'MR_n'}
                if any(p.label == 'MR_n' for p in mb.inputs):
                    v['MR_n'] = int(rng.random() > 0.1)
                steps.append((v, mb.clock is not None))
            r = self.check(mb, steps)
            self.assertPassed(r)


# ============================================================================
# 2. aşama: TD-8 işlemcisi (td8.hw.cpu) Digital'de
# ============================================================================
SLOW = os.environ.get('TD8_SLOW') == '1'
EXAMPLES = dg.SIM_DIR / 'examples'


def assemble(name):
    path = EXAMPLES / f'{name}.asm'
    return asm.assemble(path.read_text(encoding='utf-8'), str(path))


def cpu_full():
    """Bütün kart (boş program); alt küme Board'ları için çip kaynağı (her çağrıda yeni çipler)."""
    return dc.td8_board(b'')[0]


def bits(prefix, n, v):
    return {f'{prefix}{i}': (v >> i) & 1 for i in range(n)}


def word(row, prefix, n):
    return sum(row[f'{prefix}{i}'] << i for i in range(n))


# --- M2: uROM + kontrol latch'i (vectors urom) ------------------------------
def m2_urom_board():
    return dg.sub_board(cpu_full(), ['U201', 'U202', 'U203', 'U204', 'U205', 'U206'], 'm2_urom',
                        inputs=[P('STEP', cpu.nets('STEP', 4)), P('IR', cpu.nets('IR', 8)),
                                P('Z', 'Z'), P('C', 'C'), P('N', 'N'), P('V', 'V'),
                                P('RESET_s_n', '/RESET_s', 1)],
                        outputs=[P('CW0', cpu.CW_L[0:8]), P('CW1', cpu.CW_L[8:16]),
                                 P('CW2', cpu.CW_L[16:24])],
                        clock='LCLK', title='M2: uROM0–2 + kontrol latch\'i (U201–U206)')


# --- M2: kod çözücüler (vectors cs) -----------------------------------------
def m2_cs_board():
    outs = [P(name, '/' + name[:-2]) for name in vectors.CS_OUT]
    return dg.sub_board(cpu_full(), ['U207', 'U208', 'U209'], 'm2_cs',
                        inputs=[P('DSRC', cpu.CW_L[2:5]), P('DDST', cpu.CW_L[5:8]),
                                P('ASRC', cpu.CW_L[0:2]), P('BUSACK', 'BUSACK')],
                        outputs=outs, title='M2: #DS, #DD, #AS kod çözücüleri (U207–U209)')


# --- M4: iki flash + 74HC32 (vectors alu) -----------------------------------
def m4_alu_board():
    return dg.sub_board(cpu_full(), ['U407', 'U408', 'U503'], 'm4_alu_tablo',
                        inputs=[P('OP', cpu.CW_L[8:13]), P('A', cpu.nets('ACC', 8)),
                                P('B', cpu.nets('DB', 8)), P('Cin', 'C'), P('Zin', 'Z')],
                        outputs=[P('R', cpu.nets('R', 8)), P('Z', 'Znew'), P('C', 'Cnew'),
                                 P('N', 'Nnew'), P('V', 'Vnew')],
                        title='M4 ALU: ALU-L (U407), ALU-H (U408), C = Clo OR Chi (U503)')


# --- M5: adres çözme (vectors decode) ---------------------------------------
DECODE_NETS = {'ROM_CE_n': 'AB15', 'FPAGE_n': '/FPAGE', 'RAM_CE_n': '/RAM_CE',
               'VRAMSEL_n': '/VRAMSEL', 'IOSEL_n': '/IOSEL', 'RD_n': '/RD', 'MWR_n': '/MWR',
               'WR_n': '/WR', 'KBD_RD_n': '/KBD_RD', 'STAT_RD_n': '/STAT_RD',
               'LED_E_n': '/LED_E', 'VRAM_WE_n': '/VRAM_WE'}


def m5_decode_board():
    return dg.sub_board(cpu_full(), ['U603', 'U604', 'U501', 'U502', 'U503', 'U209', 'U211'],
                        'm5_cozme',
                        inputs=[P('AB', cpu.nets('AB', 16)), P('MRD_n', '/MRD', 1),
                                P('MEMW_L', 'MEMW_L'), P('WSTB', 'WSTB')],
                        outputs=[P(k, DECODE_NETS[k]) for k in vectors.DECODE_OUT],
                        title='M5 adres çözme (7.2): U603 U604 + AUX U501–U503 + M2 U209 U211')


# --- M3: modül dosyasının kendisi, senaryo ----------------------------------
class M3Script:
    """m3_adres modül Board'u için adımlar + Python modeli (PC, AR, X, SP)."""
    SRC = ('PC', 'AR', 'X', 'SP')

    def __init__(self):
        self.steps, self.expect = [], []
        self.pc = self.ar = self.x = 0
        self.sp = 0xFF
        self.k = 0

    def ab(self, src):
        return {'PC': self.pc, 'AR': self.ar, 'X': self.x, 'SP': 0xEF00 | self.sp}[src]

    def row(self, values, expect=None):
        self.steps.append(values)
        self.expect.append(expect)

    def clk(self, v):
        return {'CLK_PC': v, 'CLK_AR': v, 'CLK_X': v, 'CLK_SP': v}

    def reset(self):
        self.row({**self.clk(1), 'RESET_s_n': 0})
        self.pc = self.ar = self.x = 0
        self.sp = 0xFF
        self.row({'RESET_s_n': 1}, self.state(None))       # AB kaynağı yok: pull-up → FFFF

    def state(self, src):
        return {'PC': self.pc, 'AR': self.ar, 'X': self.x, 'SP': self.sp,
                'AB': 0xFFFF if src is None else self.ab(src)}

    def cycle(self, db=0, pcld=0, pcinc=0, arl=0, arh=0, arinc=0, xl=0, xh=0, xinc=0,
              spcnt=0, spdn=None):
        """Bir CPU çevrimi: kontroller CLK yüksekken değişir (191 kuralı), sonra CLK 0, CLK ↑."""
        src = self.SRC[self.k % 4]
        self.k += 1
        if spdn is not None:                             # D/U ayrı satırda (MAX/MIN oturur)
            self.row({'SPDN_L': spdn})
            self.dn = spdn
        dn = getattr(self, 'dn', 0)
        mm = (self.sp & 15) == (0 if dn else 15)
        ctl = {**bits('DB', 8, db), 'PCLD_n': 1 - pcld, 'PCINC_L': pcinc,
               'DD_ARL_n': 1 - arl, 'DD_ARH_n': 1 - arh, 'ARINC_L': arinc,
               'DD_XL_n': 1 - xl, 'DD_XH_n': 1 - xh, 'XINC_L': xinc,
               'SPCNT_n': 1 - spcnt, 'SPCNT_HI_n': 0 if (spcnt and mm) else 1,
               **{f'AB_{s}_n': int(s != src) for s in self.SRC}}
        self.row(ctl, self.state(src))
        self.row(self.clk(0), self.state(src))
        if pcld:                                         # hepsi aynı kenarda, eski değerlerle
            pc = self.ar
        else:
            pc = (self.pc + pcinc) & 0xFFFF
        ar = self.ar
        if arl:
            ar = (ar & 0xFF00) | db
        if arh:
            ar = (ar & 0x00FF) | db << 8
        if arinc and not (arl or arh):
            ar = (ar + 1) & 0xFFFF
        x = self.x
        if xl:
            x = (x & 0xFF00) | db
        if xh:
            x = (x & 0x00FF) | db << 8
        if xinc and not (xl or xh):
            x = (x + 1) & 0xFFFF
        if spcnt:
            self.sp = (self.sp + (-1 if dn else 1)) & 0xFF
        self.pc, self.ar, self.x = pc, ar, x
        self.row(self.clk(1), self.state(src))

    def load(self, which, v):
        if which == 'AR':
            self.cycle(db=v & 0xFF, arl=1)
            self.cycle(db=v >> 8, arh=1)
        else:
            self.cycle(db=v & 0xFF, xl=1)
            self.cycle(db=v >> 8, xh=1)


def m3_script():
    s = M3Script()
    s.reset()
    s.load('AR', 0x12FE)
    for _ in range(3):
        s.cycle(arinc=1)                                 # 12FF, 1300 (FF/00), 1301
    s.cycle(pcld=1)
    s.cycle(pcinc=1)
    for v in (0x000F, 0x00FF, 0x0FFF, 0xFFFF):           # x0/xF ve FF/00 sınırları
        s.load('AR', v)
        s.cycle(pcld=1)
        s.cycle(pcinc=1)
        s.cycle(pcinc=1)
    for v in (0x00FE, 0x0FFF, 0xFFFF):
        s.load('X', v)
        for _ in range(3):
            s.cycle(xinc=1)
    s.cycle(spcnt=1, spdn=1)                             # push: FF → FE
    for _ in range(17):
        s.cycle(spcnt=1)                                 # … F0 → EF → ED (nibble borcu)
    s.cycle(spcnt=1, spdn=0)                             # pop
    for _ in range(19):
        s.cycle(spcnt=1)                                 # … FF → 00 (taşma), 01
    for _ in range(4):
        s.cycle()                                        # her kaynak AB'de
    return s


def m3_module_board():
    return dc.module_board('M3')


# --- M1: modül + STOP OR'u (U503) -------------------------------------------
def m1_board():
    full = cpu_full()
    m1 = [c.ref for c in full.chips if c.module == 'M1']
    return dg.sub_board(full, m1 + ['U503'], 'm1_saat_stop',
                        inputs=[P('RESET_n', '/RESET', 1), P('GO_BTN', 'GO_BTN'),
                                P('STEPMODE', 'STEPMODE'), P('MICRO', 'MICRO'),
                                P('NEXT_L', 'NEXT_L'), P('HALT_L', 'HALT_L'),
                                P('FPAGE_n', '/FPAGE', 1), P('AB11', 'AB11'),
                                P('MEMW_n', '/MEMW', 1), P('VWR_s', 'VWR_s', 1)],
                        outputs=[P('Q1', 'Q1'), P('CLK', 'CLK'), P('LCLK', 'LCLK'),
                                 P('WSTB', 'WSTB'), P('STOP', 'STOP'), P('GO_n', '/GO'),
                                 P('RESET_s_n', '/RESET_s'), P('CLK_SP', 'CLK_SP')],
                        clock='MCLK', title='M1 saat/reset/STOP/WAIT + STOP OR\'u (U503)')


PHASE = {(0, 0): 'A', (1, 0): 'B', (1, 1): 'C', (0, 1): 'D'}


def m1_script():
    """(adımlar, işaretler): her adım bir MCLK periyodu; işaretler {ad: adım indeksi}."""
    steps, marks = [], {}

    def put(v=None, n=1):
        for _ in range(n):
            steps.append(({} if v is None else v, True))
            v = None

    put({'RESET_n': 0}, 3)
    marks['release'] = len(steps)
    put({'RESET_n': 1}, 14)
    marks['halt'] = len(steps)
    put({'HALT_L': 1}, 10)                               # STOP: C'de durur
    marks['unhalt'] = len(steps)
    put({'HALT_L': 0}, 6)
    marks['wait'] = len(steps)
    put({'FPAGE_n': 0, 'AB11': 0, 'MEMW_n': 0, 'VWR_s': 0}, 12)   # VRAM yazması, pencere kapalı
    marks['window'] = len(steps)
    put({'VWR_s': 1}, 6)
    marks['stepmode'] = len(steps)
    put({'FPAGE_n': 1, 'MEMW_n': 1, 'STEPMODE': 1, 'MICRO': 1}, 10)
    marks['go'] = len(steps)
    put({'GO_BTN': 1}, 3)
    put({'GO_BTN': 0}, 20)
    marks['reset2'] = len(steps)
    put({'STEPMODE': 0, 'MICRO': 0}, 5)
    put({'RESET_n': 0}, 1)
    marks['end'] = len(steps)
    put({'RESET_n': 0}, 2)
    return steps, marks


@needs_digital
class TestCpuModules(unittest.TestCase):
    """Planın modül kabul ölçütleri (SISTEM-PLANI 12.3), Digital'de CLI test ile."""

    def run_digital(self, board, text, name):
        d = tmpdir(self)
        dg.export(board, d / f'{board.name}.dig')
        (d / 'test.dig').write_text(dg.test_dig(text, name), encoding='utf-8')
        r = dtest(name, d / f'{board.name}.dig', d / 'test.dig')
        self.assertTrue(r.passed, f'{r.mismatches()[:5]}\n{r.summary()[:1500]}')
        return r

    def sim_rows(self, board, steps):
        rows, states, sim = dg.simulate(board, steps)
        self.assertEqual(sim.violations, [], sim.violations[:5])
        return rows, states

    def test_m2_urom_1000(self):
        text = vectors.urom_vectors(1000, seed=1)        # = cli.py vectors urom -n 1000
        names, vrows = vectors.parse_table(text)
        ins = ['STEP', 'IR', 'Z', 'C', 'N', 'V']
        steps = [({k: r[names.index(k)] for k in ins}, True) for r in vrows]
        want = [{k: r[names.index(k)] for k in ('CW0', 'CW1', 'CW2')} for r in vrows]
        rows, states = self.sim_rows(m2_urom_board(), steps)
        self.assertEqual(rows, want)                     # Sim = microcode.word_at
        tc = dg.testcase_text(m2_urom_board(), steps, rows, states,
                              comments=['vectors urom -n 1000 + LCLK darbesi (latch çıkışı)'])
        self.run_digital(m2_urom_board(), tc, 'urom1000')
        self.assertEqual(len(steps), 1000)

    def test_m2_cs_full_table(self):
        text = vectors.cs_vectors()
        names, vrows = vectors.parse_table(text)
        steps = [{k: r[names.index(k)] for k in vectors.CS_IN} for r in vrows]
        want = [{k: r[names.index(k)] for k in vectors.CS_OUT} for r in vrows]
        rows, _ = self.sim_rows(m2_cs_board(), steps)
        self.assertEqual(rows, want)
        self.run_digital(m2_cs_board(), text, 'cs512')    # vektör metni olduğu gibi
        self.assertEqual(len(steps), 512)

    def test_m4_alu_10000(self):
        text = vectors.alu_vectors(10000, seed=1)        # = cli.py vectors alu -n 10000
        steps, want = vector_steps(text)
        rows, _ = self.sim_rows(m4_alu_board(), steps)
        self.assertEqual(rows, want)
        self.run_digital(m4_alu_board(), text, 'alu10000')

    def test_m5_decode(self):
        text = vectors.decode_vectors(1000, seed=1)      # = cli.py vectors decode
        names, vrows = vectors.parse_table(text)
        steps = [{k: r[names.index(k)] for k in vectors.DECODE_IN} for r in vrows]
        want = [{k: r[names.index(k)] for k in vectors.DECODE_OUT} for r in vrows]
        rows, _ = self.sim_rows(m5_decode_board(), steps)
        self.assertEqual(rows, want)
        self.run_digital(m5_decode_board(), text, 'decode')
        self.assertEqual(len(steps), 1096)

    def test_m3_registers(self):
        """m3_adres.dig'in kendisi: PC yükle/artır, AR/X bayt yükle + artır, SP push/pop."""
        s = m3_script()
        rows, states = self.sim_rows(m3_module_board(), s.steps)
        for i, (row, e) in enumerate(zip(rows, s.expect)):
            if e is None:
                continue
            got = {'PC': word(row, 'PC', 16), 'AR': word(row, 'AR', 16), 'X': word(row, 'X', 16),
                   'SP': word(row, 'SP', 8), 'AB': word(row, 'AB', 16)}
            self.assertEqual(got, e, f'satır {i}: {s.steps[i]}')
        seen_sp = {e['SP'] for e in s.expect if e}
        self.assertTrue({0xFF, 0xF0, 0xEF, 0xED, 0x00, 0x01} <= seen_sp, sorted(seen_sp))
        tc = dg.testcase_text(m3_module_board(), s.steps, rows, states,
                              comments=['M3: PC, AR, X, SP sınırları (Sim + Python modeli)'])
        self.run_digital(m3_module_board(), tc, 'm3')

    def test_m1_clock(self):
        steps, mk = m1_script()
        rows, states = self.sim_rows(m1_board(), steps)
        ph = [PHASE[(r['Q1'], r['CLK'])] for r in rows]
        clk_up = [i for i in range(1, len(rows)) if rows[i]['CLK'] and not rows[i - 1]['CLK']]
        # reset: C'de park
        self.assertEqual(ph[:mk['release']], ['C'] * mk['release'])
        run = ''.join(ph[mk['release']:mk['halt']])
        self.assertIn('CDABCDAB', run)                   # faz sırası C → D → A → B
        # STOP (HALT_L) C'de tutar
        held = ph[mk['halt'] + 4:mk['unhalt']]
        self.assertEqual(set(held), {'C'}, ph[mk['halt']:mk['unhalt']])
        # WAIT D'de tutar, pencere açılınca A'ya geçer
        self.assertEqual(set(ph[mk['wait'] + 4:mk['window']]), {'D'}, ph[mk['wait']:mk['window']])
        self.assertEqual(ph[mk['window']], 'A')          # VWR_s = 1 olduğu kenarda D → A
        # GO: tam bir çevrim (bir CLK yükselişi) sonra yine C'de
        go_ups = [i for i in clk_up if mk['go'] <= i < mk['reset2']]
        self.assertEqual(len(go_ups), 1, ph[mk['go']:mk['reset2']])
        self.assertEqual(ph[mk['reset2'] - 1], 'C')
        self.assertEqual(ph[mk['end']:], ['C'] * (len(ph) - mk['end']))   # reset → C
        tc = dg.testcase_text(m1_board(), steps, rows, states,
                              comments=['M1: faz sırası, STOP, WAIT, GO, reset'])
        self.run_digital(m1_board(), tc, 'm1')

    def test_module_files_random(self):
        """m1_saat, m2_kontrol, aux_kapilar modül dosyaları: rastgele girişler, Sim ↔ Digital."""
        rng = random.Random(11)
        for mod in ('M1', 'M2', 'AUX'):
            with self.subTest(mod):
                b = dc.module_board(mod)
                clocks = [p.label for p in b.inputs if p.label in ('LCLK', 'CLK_SP')]
                steps = []
                for k in range(150):
                    v = {}
                    if k % 2 and clocks:                 # saat girişleri ayrı satırda (kurulum)
                        v = {c: rng.randrange(2) for c in clocks}
                    else:
                        for p in b.inputs:
                            if p.label in clocks:
                                continue
                            if p.label in ('RESET_n', 'RESET_s_n'):
                                v[p.label] = int(rng.random() > 0.05)
                            else:
                                v[p.label] = rng.randrange(2)
                    steps.append((v, b.clock is not None))
                rows, states = self.sim_rows(b, steps)
                tc = dg.testcase_text(dc.module_board(mod), steps, rows, states)
                self.run_digital(dc.module_board(mod), tc, f'{mod}_rastgele')


K2_PROGRAMS = {'merhaba': 573, 'komut_testi': 796, 'fibonacci': 33170}


@needs_digital
class TestCpuK2(unittest.TestCase):
    """K2: td8.dig Digital'de; her CPU çevriminde (AB, DB, CW), MicroEmu izine karşı sıfır fark."""

    def check(self, name, cycles):
        d = tmpdir(self)
        prog = assemble(name)
        dc.export_cpu(d, prog.image, name, modules=False)
        run = dc.digital_trace(d / 'td8.dig', cycles + 100, setup=SETUP)
        TIMES.append((f'K2 {name}', run.step.seconds))
        emu = dc.emu_reference(prog.image, cycles + 100, run)
        self.assertTrue(run.halted and emu.halted)
        self.assertEqual(len(run.trace), cycles)
        self.assertEqual(len(emu.trace), cycles)
        self.assertEqual(dc.compare_run(run, emu), [])
        return run, emu

    def test_merhaba(self):
        self.check('merhaba', K2_PROGRAMS['merhaba'])

    def test_komut_testi(self):
        run, emu = self.check('komut_testi', K2_PROGRAMS['komut_testi'])
        self.assertEqual(run.leds, emu.bus.leds)

    def test_fibonacci(self):
        self.check('fibonacci', K2_PROGRAMS['fibonacci'])

    @unittest.skipUnless(SLOW, 'TD8_SLOW=1 ile')
    def test_fibonacci_repeated(self):
        """Digital'in açılış yayılımı koşudan koşuya değişir; 10 koşunun hepsi sıfır fark."""
        for _ in range(10):
            self.check('fibonacci', K2_PROGRAMS['fibonacci'])

    def test_broken_netlist_is_caught(self):
        """Bozuk netlist (ALU-H'nin A8/A9'u yer değiştirmiş): iz farkı bulunmalı."""
        d = tmpdir(self)
        prog = assemble('komut_testi')
        board, _ = dc.td8_board(prog.image, 'komut_testi')
        u = next(c for c in board.chips if c.ref == 'U408')
        u.pins['A8'], u.pins['A9'] = u.pins['A9'], u.pins['A8']
        dg.export(board, d / 'td8.dig')
        run = dc.digital_trace(d / 'td8.dig', 900, setup=SETUP)
        emu = dc.emu_reference(prog.image, 900, run)
        diffs = dc.compare_run(run, emu)
        self.assertTrue(diffs and diffs[0].startswith('iz: satır'), diffs)


class TestCpuExport(unittest.TestCase):
    def test_deterministic_and_ports(self):
        prog = assemble('merhaba')
        b1, _ = dc.td8_board(prog.image, 'merhaba')
        b2, _ = dc.td8_board(prog.image, 'merhaba')
        a = dg.render(b1, DIG_DIR)
        self.assertEqual(a, dg.render(b2, DIG_DIR))
        self.assertIn('TD8_SST39SF010_urom0.dig', a)
        self.assertIn('TD8_SST39SF010_prog_merhaba.dig', a)
        self.assertEqual(b1.validate(), [])
        for mod in dc.MODULE_FILES:
            mb = dc.module_board(mod)
            self.assertEqual(mb.validate(), [], mod)

    def test_committed_cpu_files_up_to_date(self):
        """sim/digital/td8.dig varsa `py cli.py hw digital` ile üretilmişle aynı olmalı."""
        if not (DIG_DIR / 'td8.dig').is_file():
            self.skipTest('sim/digital/td8.dig yok (py -3 cli.py hw digital)')
        prog = assemble('merhaba')
        files = {}
        for mod, fname in dc.MODULE_FILES.items():
            board, _ = dc.td8_board(prog.image, 'merhaba')
            files.update(dg.render(dg.module_board(board, mod, fname,
                                                   cpu.MODULE_TITLES.get(mod)), DIG_DIR))
        board, _ = dc.td8_board(prog.image, 'merhaba')
        files.update(dg.render(board, DIG_DIR))
        for fname, text in files.items():
            self.assertEqual((DIG_DIR / fname).read_bytes(), text.encode('utf-8'),
                             f'{fname} eski: py -3 cli.py hw digital')


# ============================================================================
# Depodaki örnekler (sim/digital/)
# ============================================================================
def example_boards():
    """{ad: (Board, adımlar)} — sim/digital/'e yazılan örnekler (testleri kısaltılmış)."""
    lo, hi = alu.build_tables()
    alu_text = vectors.alu_vectors(200, seed=1)
    alu_steps, _ = vector_steps(alu_text)
    out = {
        'ornek_sayac': (counter_board(), counter_steps()),
        'ornek_kod_cozme': (decode_board(), decode_steps()),
        'ornek_bus': (bus_board(), bus_steps()[0]),
        'ornek_alu': (alu_board(lo, hi, BUILD / 'alu_lo.hex', BUILD / 'alu_hi.hex'), alu_steps),
        'ornek_sram': (sram_board(), sram_steps()[0]),
        'ornek_ardisil': (seq_board(), seq_steps(40)),
        'ornek_iz': (trace_board(trace_data()), [{}] + [({}, True)] * 40),
    }
    return out


def example_files():
    """{ad: {dosya adı: metin}} (sim/digital/ için, ROM yolları oraya göre göreli)."""
    out = {}
    for name, (board, steps) in example_boards().items():
        tc = dg.testcase_text(board, steps)
        out[name] = dg.render(board, DIG_DIR, tc)
    return out


@needs_digital
class TestCommittedExamples(unittest.TestCase):
    def test_examples_pass_in_digital(self):
        """sim/digital/ornek_*.dig Digital'de kendi testlerinden geçer (çalışma klasörü başka)."""
        for name in example_boards():
            with self.subTest(name):
                r = dg.run_test(DIG_DIR / f'{name}.dig', verbose=True, setup=SETUP,
                                cwd=Path(tempfile.gettempdir()))
                TIMES.append((name, r.seconds))
                self.assertTrue(r.passed, r.summary()[:2000])


def write_examples():
    files = {}
    for name, f in example_files().items():
        files.update(f)
    DIG_DIR.mkdir(exist_ok=True)
    for fname, text in files.items():
        (DIG_DIR / fname).write_bytes(text.encode('utf-8'))
        print(f'{DIG_DIR / fname}: {len(text) // 1024} KB')


def bench():
    if SETUP is None:
        sys.exit('Digital bulunamadı')
    d = Path(tempfile.mkdtemp(prefix='td8bench_'))
    try:
        b = trace_board(trace_data())
        dg.export(b, d / f'{b.name}.dig')
        for n in (1000, 20000):
            st = dg.run_stepper(d / f'{b.name}.dig', n, signals=['AB', 'DB', 'CW'], setup=SETUP)
            print(f'ornek_iz (4 çip): {n} periyot, java toplam {st.seconds:.2f} s, '
                  f'adımlama {st.sim_seconds:.2f} s, {st.rate} periyot/sn')
        b = all_chips_board()
        dg.export(b, d / f'{b.name}.dig')
        for n in (1000, 10000):
            st = dg.run_stepper(d / f'{b.name}.dig', n, setup=SETUP)
            print(f'ornek_tum_cipler ({len(b.chips)} çip, {len(b.outputs)} Out): {n} periyot, '
                  f'java toplam {st.seconds:.2f} s, adımlama {st.sim_seconds:.2f} s, '
                  f'{st.rate} periyot/sn')
    finally:
        shutil.rmtree(d, True)


if __name__ == '__main__':
    if '--yaz' in sys.argv:
        write_examples()
    elif '--bench' in sys.argv:
        bench()
    else:
        unittest.main()
