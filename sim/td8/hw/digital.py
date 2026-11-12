"""td8.hw netlist'ini Digital'in (hneemann/Digital v0.31) devre dosyasına (.dig) çevirir
ve Digital'i komut satırından çalıştırır (SISTEM-PLANI 12.2).

Dışa aktarma
------------
`Board` = çipler (td8.hw.chips nesneleri) + pull dirençleri (net → 0/1) + dış girişler
(Digital'de `In`) + gözlenen çıkışlar (`Out`) + isteğe bağlı saat (`Clock`) + flash'ların
ROM dosyaları. `export(board, yol, tests=...)` tek bir `.dig` yazar:

- Her 74HC çipi, Digital'in 74xx kütüphanesindeki pinli DIL alt devresi olarak yerleşir
  (`74161.dig` ...). Her bacağın TAM ÜSTÜNE o bacağın netini taşıyan bir `Tunnel` konur;
  tel çizilmez (Digital'de pinle aynı noktadaki tunnel o pine bağlıdır). Bizim pin adlarımız
  ile Digital'in etiketleri farklı olabildiği için eşleme DIP bacak numarasıyla yapılır;
  bacak sayısı ve yön `_LIB` tablosuyla (Digital kütüphanesinden çıkarıldı, testte yeniden
  karşılaştırılır) denetlenir, uyuşmazlıkta `DigitalError`.
- VCC/GND bacakları 'VCC'/'GND' tunnel'larına, onlar da bir `VDD` ve bir `Ground`'a bağlanır.
- Bellekler kütüphanede yok; dışa aktarıcı aynı klasöre bizim bacak düzenimizle DIL alt
  devreleri yazar:
    TD8_SST39SF010_<etiket>.dig  ROM (17 bit adres, 8 bit) + NOR(/CE, /OE) → sel. Veri
                                  varsayılan olarak gömülü (`Data` = chip.data); isteğe bağlı
                                  göreli yollu dosya + autoReload (bkz. `render`, rom_mode).
    TD8_CY62256.dig              RAMAsync (yazma seviye duyarlı: /CE = /WE = 0 süresince) +
                                  sürücü: çıkış yalnız /CE = /OE = 0 ve /WE = 1 iken.
- Pull dirençleri `PullUp`/`PullDown`, çok bitli giriş/çıkışlar `Splitter` ile kurulur.
- Yerleşim: soldaki sütunda dış bağlantılar ve testler; sağda her modül için bir çerçeve
  (`Rectangle`, etiketi modül adı), içinde çipler ızgarada; her çipin üstünde ref + tür (+ not).
- Çıktı belirlenimlidir: aynı girdi → bayt bayt aynı dosya (satır sonu '\n').

Ad dönüşümü (tek yer: `safe_name`): baştaki '/' (aktif düşük) '_n' son ekine döner (/MRD →
MRD_n; vectors.py ile aynı kural), harf/rakam/_ dışındaki karakterler '_' olur (U3.Q0 → U3_Q0).
Tunnel adları, In/Out etiketleri ve test başlıkları hep bu adları kullanır.

Doğrulama
---------
`simulate(board, adımlar)` aynı Board'u td8.hw.Sim'de koşar; `testcase_text` sonuçları
Digital Testcase metnine çevirir (Sim beklenen değerleri üretir, Digital denetler).
Bir adım = (giriş değerleri sözlüğü, saat darbesi var mı). Darbeli adımın anlamı Digital'in
`C` değeriyle aynıdır: girişler verilir, saat 1 sonra 0 olur, ardından çıkışlar okunur.

`run_test(dig, tests=None)` → `java -cp Digital.jar CLI test`; `run_stepper(dig, N, ...)` →
sim/digital/arac/TD8Adim.java ile N saat periyodu adımlar ve sinyalleri CSV (vectors.parse_table
biçimi) olarak döker. Digital'in yeri: TD8_DIGITAL_HOME ortam değişkeni, yoksa depo kökünün
yanındaki `araclar` klasörü (içinde Digital/Digital.jar ve isteğe bağlı jdk-21/).

Modül modül çıktı: `module_board(board, 'M4')` modülün çiplerini ve sınır netlerini (In/Out)
ayrı bir Board yapar; `export_all(board, klasör)` her modül için bir .dig ve tek parça td8.dig yazar.
"""

import hashlib
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

from .chips import CHIP_TYPES, CY62256, SST39SF010
from .kernel import Sim

SIM_DIR = Path(__file__).resolve().parents[2]            # sim/
REPO_ROOT = SIM_DIR.parent
DEFAULT_HOME = REPO_ROOT.parent / 'araclar'
STEPPER_SRC = SIM_DIR / 'digital' / 'arac' / 'TD8Adim.java'
GRID = 20
POWER_NETS = ('VCC', 'GND')


class DigitalError(Exception):
    """Dışa aktarma ya da Digital çalıştırma hatası."""


# ============================================================================
# Ad dönüşümü
# ============================================================================
_UNSAFE = re.compile(r'[^A-Za-z0-9_]')


def safe_name(net):
    """Net adını Digital'de güvenli bir ada çevirir (tunnel, In/Out etiketi, test başlığı).

    '/MRD' → 'MRD_n', '/RESET_s' → 'RESET_s_n', 'U3.Q0' → 'U3_Q0', '/P=Q' → 'P_Q_n'.
    Rakamla başlayan adların başına 'N' eklenir (test dili etiketleri tanımlayıcı ister).
    """
    low = net.startswith('/')
    s = _UNSAFE.sub('_', net[1:] if low else net)
    if low:
        s += '_n'
    if not s or s[0].isdigit():
        s = 'N' + s
    return s


def name_map(nets):
    """{net: güvenli ad}; iki farklı net aynı ada düşerse DigitalError."""
    out, back = {}, {}
    for net in nets:
        if net in out:
            continue
        s = safe_name(net)
        other = back.get(s)
        if other is not None:
            raise DigitalError(f'ad çakışması: {other!r} ve {net!r} ikisi de {s!r} oluyor')
        out[net] = s
        back[s] = net
    return out


def _dig_label(pin):
    """Alt devre pin etiketi: Digital'in üst çizgi gösterimi ('/CE' → '~CE')."""
    return '~' + pin[1:] if pin.startswith('/') else pin


# ============================================================================
# Digital 74xx kütüphanesi
# ============================================================================
# tür → (kütüphane dosyası (.dig'siz), Width, bacak 1..N etiketleri boşlukla).
# Etiket sonu '>' = Out (çıkış), '=' = isHighZ In (çift yönlü bacak), '-' = tanımsız (NC).
# Digital v0.31 lib/DIL Chips/74xx'ten `scan_library` ile çıkarıldı; test yeniden karşılaştırır.
_LIB = {
    '74HC00': ('7400', 5, '1A 1B 1Y> 2A 2B 2Y> GND 3Y> 3A 3B 4Y> 4A 4B VCC'),
    '74HC02': ('7402', 5, '1Y> 1A 1B 2Y> 2A 2B GND 3A 3B 3Y> 4A 4B 4Y> VCC'),
    '74HC04': ('7404', 5, '1A 1Y> 2A 2Y> 3A 3Y> GND 4Y> 4A 5Y> 5A 6Y> 6A VCC'),
    '74HC08': ('7408', 5, '1A 1B 1Y> 2A 2B 2Y> GND 3Y> 3A 3B 4Y> 4A 4B VCC'),
    '74HC14': ('7414', 5, '1A 1Y> 2A 2Y> 3A 3Y> GND 4Y> 4A 5Y> 5A 6Y> 6A VCC'),
    '74HC20': ('7420', 5, '1A 1B - 1C 1D 1Y> GND 2Y> 2A 2B - 2C 2D VCC'),
    '74HC32': ('7432', 5, '1A 1B 1Y> 2A 2B 2Y> GND 3Y> 3A 3B 4Y> 4A 4B VCC'),
    '74HC74': ('7474', 5, '~1RD 1D 1CP ~1SD 1Q> ~1Q> GND ~2Q> 2Q> ~2SD 2CP 2D ~2RD VCC'),
    '74HC138': ('74138', 5, 'A B C ~GA ~GB G ~Y7> GND ~Y6> ~Y5> ~Y4> ~Y3> ~Y2> ~Y1> ~Y0> VCC'),
    '74HC139': ('74139', 5,
                '~1G 1A 1B ~1Y0> ~1Y1> ~1Y2> ~1Y3> GND ~2Y3> ~2Y2> ~2Y1> ~2Y0> 2B 2A ~2G VCC'),
    '74HC153': ('74153', 5, '1G B 1C3 1C2 1C1 1C0 1Y> GND 2Y> 2C0 2C1 2C2 2C3 A 2G VCC'),
    '74HC157': ('74157', 5, 'S A1 B1 Y1> A2 B2 Y2> GND Y3> B3 A3 Y4> B4 A4 G VCC'),
    '74HC161': ('74161', 5, '~CLR CLK A B C D ENP GND ~LD ENT QD> QC> QB> QA> RCO> VCC'),
    '74HC163': ('74163', 5, '~SR CP P0 P1 P2 P3 CEP GND ~PE CET Q3> Q2> Q1> Q0> TC> VCC'),
    '74HC164': ('74164', 5, 'DSA DSB Q0> Q1> Q2> Q3> GND CP ~MR Q4> Q5> Q6> Q7> VCC'),
    '74HC166': ('74166', 5, 'SER A B C D INH CLK GND ~CLR E F G QH> H ~LD VCC'),
    '74HC175': ('74175', 5, '~CL Q1> ~Q1> D1 D2 ~Q2> Q2> GND CLK Q3> ~Q3> D3 D4 ~Q4> Q4> VCC'),
    '74HC191': ('74191', 7, 'D1 Q1> Q0> ~CE ~U/D Q2> Q3> GND D3 D2 ~PL TC> ~RC> CP D0 VCC'),
    '74HC245': ('74245', 5, 'DIR A1= A2= A3= A4= A5= A6= A7= A8= GND '
                            'B8= B7= B6= B5= B4= B3= B2= B1= ~OE VCC'),
    '74HC273': ('74273', 5, '~MR Q0> D0 D1 Q1> Q2> D2 D3 Q3> GND CP Q4> D4 D5 Q5> Q6> D6 D7 Q7> VCC'),
    '74HC377': ('74377', 5, '~E Q0> D0 D1 Q1> Q2> D2 D3 Q3> GND CLK Q4> D4 D5 Q5> Q6> D6 D7 Q7> VCC'),
    '74HC540': ('74540', 5, '~OE1 0D 1D 2D 3D 4D 5D 6D 7D GND 7O> 6O> 5O> 4O> 3O> 2O> 1O> 0O> ~OE2 VCC'),
    '74HC688': ('74688', 5, '~OE P_0 Q_0 P_1 Q_1 P_2 Q_2 P_3 Q_3 GND '
                            'P_4 Q_4 P_5 Q_5 P_6 Q_6 P_7 Q_7 ~EQ> VCC'),
}

_KIND_OF_MARK = {'>': 'out', '=': 'hz'}
_COMPAT = {'in': 'in', 'out': 'out', 'tri': 'out', 'bidir': 'hz'}   # bizim yön → Digital pin türü
MEM_WIDTH = 7                                                          # bellek alt devrelerinin Width'i


class DilSpec:
    """Bir DIL alt devresinin bacak düzeni: file (elementName, .dig'li), width, legs, pins."""

    def __init__(self, file, width, legs, pins):
        self.file = file
        self.width = width
        self.legs = legs
        self.pins = pins                  # bacak → (Digital etiketi, 'in' | 'out' | 'hz')

    def pin_xy(self, leg, x0, y0):
        """Bacağın mutlak konumu (rotation 0; keşif raporu e.2'deki formül)."""
        n = self.legs
        if leg <= n // 2:
            return x0, y0 + 40 * (leg - 1)
        return x0 + GRID * (self.width + 1), y0 + 40 * (n - leg)

    @property
    def size(self):
        return GRID * (self.width + 1), 40 * (self.legs // 2 - 1)


def _parse_spec(file, width, text):
    pins = {}
    for leg, tok in enumerate(text.split(), 1):
        if tok == '-':
            continue
        kind = _KIND_OF_MARK.get(tok[-1], 'in')
        pins[leg] = (tok.rstrip('>='), kind)
    return DilSpec(file + '.dig', width, len(text.split()), pins)


def _mem_spec(cls):
    pins = {}
    for pin, leg in cls.PINOUT.items():
        d = cls.DIRS.get(pin, 'in')
        pins[leg] = (_dig_label(pin), _COMPAT[d])
    legs = max(cls.PINOUT.values())
    legs += legs % 2
    return DilSpec(None, MEM_WIDTH, legs, pins)


_SPEC_CACHE = {}


def dil_spec(cls):
    """Çip sınıfının Digital DIL düzeni; bizim PINOUT/DIRS ile uyuşmuyorsa DigitalError."""
    kind = cls.KIND
    if kind in _SPEC_CACHE:
        return _SPEC_CACHE[kind]
    if cls in (SST39SF010, CY62256):
        spec = _mem_spec(cls)
    elif kind in _LIB:
        spec = _parse_spec(*_LIB[kind])
    else:
        raise DigitalError(f'{kind}: Digital karşılığı tanımlı değil')
    problems = []
    ours = {leg: pin for pin, leg in cls.PINOUT.items()}
    if len(ours) != len(cls.PINOUT):
        problems.append('PINOUT\'ta aynı bacak iki kez var')
    for leg in sorted(set(ours) | set(spec.pins)):
        if leg not in ours:
            problems.append(f'bacak {leg}: Digital\'de {spec.pins[leg][0]!r} var, bizde yok')
            continue
        if leg not in spec.pins:
            problems.append(f'bacak {leg}: bizde {ours[leg]!r} var, Digital\'de yok')
            continue
        pin = ours[leg]
        label, dkind = spec.pins[leg]
        if pin in POWER_NETS:
            if label != pin:
                problems.append(f'bacak {leg}: güç bacağı {pin}, Digital\'de {label!r}')
            continue
        want = _COMPAT[cls.DIRS[pin]]
        if want != dkind:
            problems.append(f'bacak {leg}: {pin} ({cls.DIRS[pin]}) ↔ Digital {label!r} ({dkind})')
    if max(ours) > spec.legs:
        problems.append(f'bacak sayısı: bizde {max(ours)}, Digital\'de {spec.legs}')
    if problems:
        raise DigitalError(f'{kind} ↔ Digital {spec.file}: ' + '; '.join(problems))
    _SPEC_CACHE[kind] = spec
    return spec


def scan_library(libdir):
    """Digital'in 74xx klasöründen `_LIB` biçiminde tablo çıkarır (yalnız CHIP_TYPES'taki 74HC'ler)."""
    index = {}
    for root, _, files in os.walk(libdir):
        for f in files:
            if f.endswith('.dig'):
                index.setdefault(f[:-4], os.path.join(root, f))
    table = {}
    for kind in CHIP_TYPES:
        if not kind.startswith('74HC'):
            continue
        name = kind.replace('HC', '', 1)
        if name not in index:
            continue
        root = ET.parse(index[name]).getroot()
        cattr = _entries(root.find('attributes'))
        width = int(cattr['Width'].text) if 'Width' in cattr else 3
        count = int(cattr['pinCount'].text) if 'pinCount' in cattr else 0
        pins = {}
        for ve in root.find('visualElements'):
            ename = ve.findtext('elementName')
            if ename not in ('In', 'Out', 'Clock'):
                continue
            a = _entries(ve.find('elementAttributes'))
            leg = int(a['pinNumber'].text)
            hz = 'isHighZ' in a and a['isHighZ'].text == 'true'
            pins[leg] = a['Label'].text + ('>' if ename == 'Out' else '=' if hz else '')
        legs = max(count, max(pins))
        table[kind] = (name, width, ' '.join(pins.get(i, '-') for i in range(1, legs + 1)))
    return table


def _entries(node):
    d = {}
    if node is not None:
        for e in node.findall('entry'):
            d[e[0].text] = e[1]
    return d


# ============================================================================
# XML yazımı
# ============================================================================
class _Raw:
    """Önceden biçimlenmiş XML değer düğümü."""

    def __init__(self, xml):
        self.xml = xml


def _rot(n):
    return _Raw(f'<rotation rotation="{n}"/>')


def _in_default(v):
    return _Raw('<value v="0" z="true"/>' if v is None else f'<value v="{int(v)}" z="false"/>')


def _long(v):
    return _Raw(f'<long>{int(v)}</long>')


def _xml_value(v):
    if isinstance(v, _Raw):
        return v.xml
    if isinstance(v, bool):
        return f'<boolean>{"true" if v else "false"}</boolean>'
    if isinstance(v, int):
        return f'<int>{v}</int>'
    return f'<string>{escape(str(v))}</string>'


def _el(name, x, y, **attrs):
    """Tek satırlık <visualElement>. Öznitelik adındaki '__' boşluğa döner."""
    ent = ''.join(f'<entry><string>{escape(k.replace("__", " "))}</string>{_xml_value(v)}</entry>'
                  for k, v in attrs.items() if v is not None)
    body = f'<elementAttributes>{ent}</elementAttributes>' if ent else '<elementAttributes/>'
    return (f'<visualElement><elementName>{escape(name)}</elementName>{body}'
            f'<pos x="{x}" y="{y}"/></visualElement>')


def _tunnel(net, x, y, rot=0):
    return _el('Tunnel', x, y, rotation=_rot(rot) if rot else None, NetName=net)


def _circuit(elements, attrs=None):
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<circuit>', '  <version>2</version>']
    if attrs:
        lines.append('  <attributes>')
        for k, v in attrs.items():
            lines.append(f'    <entry><string>{escape(k)}</string>{_xml_value(v)}</entry>')
        lines.append('  </attributes>')
    else:
        lines.append('  <attributes/>')
    lines.append('  <visualElements>')
    lines.extend('    ' + e for e in elements)
    lines.append('  </visualElements>')
    lines.append('  <wires/>')
    lines.append('</circuit>')
    return '\n'.join(lines) + '\n'


def _testcase(label, text, x, y):
    return _el('Testcase', x, y, Label=label,
               Testdata=_Raw(f'<testData><dataString>{escape(text)}</dataString></testData>'))


def test_dig(text, label='test'):
    """Yalnız bir Testcase içeren .dig metni (`CLI test -tests` ile kullanılır)."""
    return _circuit([_testcase(label, text, 0, 0)])


def data_string(data):
    """Bayt dizisini Digital'in `Data` biçimine çevirir: onaltılı, virgüllü, 'n*v' tekrarları,
    sondaki sıfırlar atılır."""
    data = bytes(data).rstrip(b'\0')
    toks = []
    i, n = 0, len(data)
    while i < n:
        j = i
        while j < n and data[j] == data[i]:
            j += 1
        run = j - i
        toks.append(f'{run}*{data[i]:x}' if run >= 4 else ','.join([f'{data[i]:x}'] * run))
        i = j
    out, line = [], ''
    for t in toks:
        if len(line) + len(t) > 72:
            out.append(line)
            line = ''
        line += (',' if line else '') + t
    if line:
        out.append(line)
    return ',\n'.join(out)


def write_raw_hex(path, data):
    """Logisim/Digital 'v2.0 raw' biçiminde ROM dosyası yazar (cli.py roms ile aynı biçim)."""
    lines = ['v2.0 raw']
    for i in range(0, len(data), 16):
        lines.append(' '.join(f'{b:x}' for b in data[i:i + 16]))
    Path(path).write_text('\n'.join(lines) + '\n', encoding='ascii', newline='\n')


# ============================================================================
# Bellek alt devreleri
# ============================================================================
def _wrapper_pins(cls, spec, internal):
    """Alt devrenin In/Out pinleri (sol sütunda) + iç tunnel'ları. internal: pin → iç net."""
    els = []
    for i, (pin, leg) in enumerate(sorted(cls.PINOUT.items(), key=lambda kv: kv[1])):
        label, kind = spec.pins[leg]
        y = 40 * i
        if kind == 'out':
            els.append(_el('Out', 0, y, Label=label, pinNumber=str(leg)))
        elif kind == 'hz':
            els.append(_el('In', 0, y, Label=label, pinNumber=str(leg),
                           InDefault=_in_default(None), isHighZ=True))
        else:
            els.append(_el('In', 0, y, Label=label, pinNumber=str(leg),
                           InDefault=_in_default(1) if pin == 'VCC' else None))
        net = internal.get(pin)
        if net:
            els.append(_tunnel(net, 0, y))
    return els


def _merge(x, y, nets, bus):
    """Splitter: 1 bitlik netler (x, y+20i) → çok bitli `bus` (x+20, y)."""
    n = len(nets)
    els = [_el('Splitter', x, y, Input__Splitting=','.join(['1'] * n), Output__Splitting=str(n))]
    els += [_tunnel(net, x, y + GRID * i, 2) for i, net in enumerate(nets)]
    els.append(_tunnel(bus, x + GRID, y))
    return els


def _split(x, y, bus, nets):
    """Splitter: çok bitli `bus` (x, y) → 1 bitlik netler (x+20, y+20i)."""
    n = len(nets)
    els = [_el('Splitter', x, y, Input__Splitting=str(n), Output__Splitting=','.join(['1'] * n))]
    els.append(_tunnel(bus, x, y, 2))
    els += [_tunnel(net, x + GRID, y + GRID * i) for i, net in enumerate(nets)]
    return els


def _flash_wrapper(rom_attrs, title):
    cls = SST39SF010
    spec = dil_spec(cls)
    internal = {p: safe_name(p) for p in cls.PINOUT if p not in ('/WE', 'VCC', 'GND')}
    els = _wrapper_pins(cls, spec, internal)
    els += _merge(240, 0, [f'A{i}' for i in range(17)], 'ADDR')
    els.append(_el('ROM', 440, 0, AddrBits=17, Bits=8, Label='ROM', **rom_attrs))
    els += [_tunnel('ADDR', 440, 0, 2), _tunnel('SEL', 440, 40, 2), _tunnel('DATA', 500, 20)]
    els.append(_el('NOr', 240, 440))                                  # sel = NOR(/CE, /OE)
    els += [_tunnel('CE_n', 240, 440, 2), _tunnel('OE_n', 240, 480, 2), _tunnel('SEL', 320, 460)]
    els += _split(640, 0, 'DATA', [f'DQ{i}' for i in range(8)])
    els.append(_el('Text', 240, 600, Description=title))
    desc = ('TD-8: SST39SF010 128K×8 flash (td8.hw.chips.SST39SF010). ROM (17 bit adres) çıkışı '
            '/CE = /OE = 0 iken etkin, değilse yüksek empedans. /WE kullanılmaz (yazma komutları '
            'modellenmez). td8.hw.digital tarafından üretildi.')
    attrs = {'shapeType': _Raw('<shapeType>DIL</shapeType>'), 'Width': MEM_WIDTH,
             'pinCount': spec.legs, 'Description': desc}
    return _circuit(els, attrs)


def _sram_wrapper():
    cls = CY62256
    spec = dil_spec(cls)
    internal = {p: safe_name(p) for p in cls.PINOUT if p not in ('VCC', 'GND')}
    els = _wrapper_pins(cls, spec, internal)
    io = [f'IO{i}' for i in range(8)]
    els += _merge(240, 0, [f'A{i}' for i in range(15)], 'ADDR')
    els += _merge(240, 360, io, 'DIN')
    els.append(_el('RAMAsync', 440, 0, AddrBits=15, Bits=8, Label='*'))
    els += [_tunnel('ADDR', 440, 0, 2), _tunnel('DIN', 440, 20, 2), _tunnel('WE', 440, 40, 2),
            _tunnel('Q', 500, 20)]
    els.append(_el('NOr', 240, 600))                                  # we = NOR(/CE, /WE)
    els += [_tunnel('CE_n', 240, 600, 2), _tunnel('WE_n', 240, 640, 2), _tunnel('WE', 320, 620)]
    els.append(_el('Not', 240, 720))
    els += [_tunnel('WE_n', 240, 720, 2), _tunnel('WE_H', 280, 720)]
    els.append(_el('NOr', 240, 800, Inputs=3))                        # oe = !/CE & !/OE & /WE
    els += [_tunnel('CE_n', 240, 800, 2), _tunnel('OE_n', 240, 820, 2),
            _tunnel('WE_H', 240, 840, 2), _tunnel('OE', 320, 820)]
    els.append(_el('Driver', 560, 240, Bits=8))
    els += [_tunnel('Q', 540, 240, 2), _tunnel('OE', 560, 220), _tunnel('QOUT', 580, 240)]
    els += _split(680, 240, 'QOUT', io)
    els.append(_el('Text', 240, 960, Description='CY62256 32K×8 SRAM: RAMAsync + sürücü'))
    desc = ('TD-8: CY62256 32K×8 asenkron SRAM (td8.hw.chips.CY62256). RAMAsync: /CE = /WE = 0 '
            'süresince IO\'daki veri adrese yazılır (seviye duyarlı; yazma sonundaki değer kalır). '
            'IO yalnız /CE = /OE = 0 ve /WE = 1 iken sürülür. Açılışta içerik 0. '
            'td8.hw.digital tarafından üretildi.')
    attrs = {'shapeType': _Raw('<shapeType>DIL</shapeType>'), 'Width': MEM_WIDTH,
             'pinCount': spec.legs, 'Description': desc}
    return _circuit(els, attrs)


SRAM_FILE = 'TD8_CY62256.dig'


# ============================================================================
# Board
# ============================================================================
class Port:
    """Üst seviye giriş/çıkış. nets: LSB önce net adları (tek net → 1 bit).

    Giriş için `default` açılış değeri (None = yüksek empedans; `highz` kendiliğinden True olur).
    `highz` girişler testte 'Z' alabilir (çift yönlü bus'ı test tezgâhı sürerken kullanılır).
    """

    def __init__(self, label, nets, default=0, highz=False):
        self.label = label
        self.nets = (nets,) if isinstance(nets, str) else tuple(nets)
        if not self.nets:
            raise ValueError(f'{label}: boş port')
        self.default = default
        self.highz = bool(highz or default is None)

    @property
    def bits(self):
        return len(self.nets)

    def __repr__(self):
        return f'Port({self.label!r}, {list(self.nets)!r})'


def bus_nets(prefix, width, start=0):
    """['A0', 'A1', ...] (LSB önce)."""
    return [f'{prefix}{start + i}' for i in range(width)]


def _ports(spec, is_input):
    if spec is None:
        return []
    if isinstance(spec, dict):
        spec = list(spec.items())
    out = []
    for p in spec:
        if isinstance(p, Port):
            out.append(p)
        elif isinstance(p, str):
            out.append(Port(safe_name(p), p))
        elif isinstance(p, tuple) and len(p) == 2 and is_input:
            out.append(Port(safe_name(p[0]), p[0], default=p[1]))
        else:
            raise ValueError(f'port anlaşılmadı: {p!r}')
    return out


class Board:
    """Dışa aktarılacak devre.

    chips:     td8.hw çip nesneleri (sırası yerleşimde korunur; `module` gruplamada kullanılır)
    pulls:     {net: 0 | 1}
    inputs:    {net: varsayılan} ya da Port / net adı / (net, varsayılan) listesi
    outputs:   Port ya da net adı listesi
    clock:     saat netinin adı (Digital'de Clock elemanı; testte 'C')
    clock_hz:  verilirse Clock 'runRealTime' + bu frekans: GUI'de simülasyon başlayınca saat
               kendiliğinden işler (CLI test ve adımlayıcı saati yine kendisi sürer)
    rom_files: {flash ref: .hex/.bin yolu}; gömülü modda yalnız alt devrenin adını verir,
               rom_mode='file' iken Digital veriyi bu dosyadan okur
    """

    def __init__(self, name, chips=(), pulls=None, inputs=None, outputs=None, clock=None,
                 rom_files=None, title=None, clock_hz=None):
        if not re.fullmatch(r'[A-Za-z0-9_]+', name):
            raise ValueError(f'Board adı yalnız harf/rakam/_ olmalı: {name!r}')
        self.name = name
        self.title = title or name
        self.chips = list(chips)
        self.pulls = dict(pulls or {})
        self.inputs = _ports(inputs, True)
        self.outputs = _ports(outputs, False)
        self.clock = clock
        self.clock_hz = clock_hz          # verilirse GUI'de gerçek zamanlı saat (runRealTime)
        self.rom_files = {ref: Path(p) for ref, p in (rom_files or {}).items()}

    @classmethod
    def from_sim(cls, sim, name, inputs=None, outputs=None, clock=None, rom_files=None,
                 title=None):
        """Kurulmuş bir td8.hw.Sim'den (çipler + pull'lar) Board."""
        pulls = {sim.names[n]: v for n, v in enumerate(sim.pullv) if v is not None}
        return cls(name, sim._order, pulls, inputs, outputs, clock, rom_files, title)

    @property
    def clock_label(self):
        return safe_name(self.clock) if self.clock else None

    def nets(self):
        """Board'daki bütün netler (ilk görülme sırasıyla)."""
        seen = dict.fromkeys(POWER_NETS)
        for c in self.chips:
            seen.update(dict.fromkeys(c.pins.values()))
        for p in self.inputs + self.outputs:
            seen.update(dict.fromkeys(p.nets))
        seen.update(dict.fromkeys(self.pulls))
        if self.clock:
            seen[self.clock] = None
        return list(seen)

    def validate(self):
        """Tutarlılık denetimi; uyarı listesi döndürür, ciddi hatada DigitalError."""
        names = name_map(self.nets())
        refs = [c.ref for c in self.chips]
        if len(set(refs)) != len(refs):
            raise DigitalError('aynı ref iki kez: ' + ', '.join(sorted({r for r in refs
                                                                       if refs.count(r) > 1})))
        labels = [p.label for p in self.inputs + self.outputs]
        if self.clock:
            labels.append(self.clock_label)
        dup = sorted({x for x in labels if labels.count(x) > 1})
        if dup:
            raise DigitalError(f'aynı In/Out/Clock etiketi iki kez: {", ".join(dup)}')
        for lab in labels:
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', lab):
                raise DigitalError(f'etiket test dilinde kullanılamaz: {lab!r}')
        for c in self.chips:
            dil_spec(type(c))
        for net, v in self.pulls.items():
            if v not in (0, 1):
                raise DigitalError(f'pull değeri 0 ya da 1 olmalı: {net}={v!r}')
        warnings = []
        drivers, readers = {}, {}
        for c in self.chips:
            for pin, net in c.pins.items():
                d = c.DIRS[pin]
                if d != 'in':
                    drivers.setdefault(net, []).append(c.ref)
                if d in ('in', 'bidir'):
                    readers.setdefault(net, []).append(c.ref)
        driven = set(drivers) | set(self.pulls) | set(POWER_NETS)
        for p in self.inputs:
            driven.update(p.nets)
        if self.clock:
            driven.add(self.clock)
        for net, refs_ in readers.items():
            if net not in driven:
                warnings.append(f'{net} ({names[net]}) okunuyor ama süren yok, pull yok: '
                                f'{", ".join(refs_)}')
        return warnings


# ============================================================================
# Dışa aktarma
# ============================================================================
CHAR_W = 9           # Digital'de bir etiket karakterinin yaklaşık genişliği (px)


def _margin(labels):
    """Tunnel etiketleri için pinin yanında bırakılacak genişlik (ızgaraya yuvarlanmış)."""
    w = max((len(s) for s in labels), default=0) * CHAR_W + 40
    return max(60, int(math.ceil(w / GRID)) * GRID)


def _snap(v):
    return int(math.ceil(v / GRID)) * GRID


def _rom_tag(path):
    return safe_name(Path(path).stem)


def _relpath(target, start):
    try:
        return Path(os.path.relpath(target, start)).as_posix()
    except ValueError:                    # farklı sürücü
        return Path(target).resolve().as_posix()


def render(board, out_dir, tests=None, rom_mode='embed'):
    """Board'u XML metinlerine çevirir (dosya yazmaz).

    Döner: {dosya adı: metin}; ilk anahtar ana devre (`<board.name>.dig`), sonrakiler
    gereken bellek alt devreleri. tests: Testcase metni ya da [(etiket, metin), ...].

    rom_mode (flash içerikleri):
      'embed' (varsayılan) chip.data alt devreye gömülür (`Data`). Sim'in kullandığı baytların
              aynısıdır; .dig her yerden, her çalışma klasöründen açılır. Alt devre adı
              rom_files'taki dosya adından (TD8_SST39SF010_alu_lo.dig), yoksa içeriğin
              özetinden (TD8_SST39SF010_h1a2b3c4d5e.dig) gelir; aynı imaj tek dosyadır.
      'file'  rom_files[ref] `out_dir`'e göre göreli yolla + autoReload bağlanır. DİKKAT:
              Digital (v0.31, FileLocator) göreli yolu .dig'e göre değil ÇALIŞMA KLASÖRÜNE
              göre çözer; bulamazsa yalnız dosya ADIYLA ana devrenin klasörü altında arar.
              run_test/run_stepper Java'yı .dig'in klasöründe başlattığı için CLI'da çalışır;
              GUI'de Digital'in o klasörden başlatılması gerekir.
    """
    if rom_mode not in ('embed', 'file'):
        raise ValueError("rom_mode 'embed' ya da 'file' olmalı")
    board.validate()
    out_dir = Path(out_dir)
    names = name_map(board.nets())
    files = {}
    wrapper_of = {}
    for c in board.chips:
        if isinstance(c, SST39SF010):
            path = board.rom_files.get(c.ref)
            if rom_mode == 'file':
                if path is None:
                    raise DigitalError(f'{c.ref}: rom_mode=file ama rom_files içinde dosya yok')
                fname = f'TD8_SST39SF010_{_rom_tag(path)}.dig'
                rel = _relpath(Path(path), out_dir)
                text = _flash_wrapper({'lastDataFile': _Raw(f'<file>{escape(rel)}</file>'),
                                       'autoReload': True},
                                      f'SST39SF010 flash, veri: {rel} (autoReload)')
            else:
                data = bytes(c.data)
                tag = (_rom_tag(path) if path is not None
                       else 'h' + hashlib.sha1(data).hexdigest()[:10])
                fname = f'TD8_SST39SF010_{tag}.dig'
                src = f'kaynak: {Path(path).name}, ' if path is not None else ''
                text = _flash_wrapper({'Data': _Raw(f'<data>{data_string(data)}</data>')},
                                      f'SST39SF010 flash, veri gömülü ({src}'
                                      f'sha1 {hashlib.sha1(data).hexdigest()[:10]})')
            if files.get(fname, text) != text:
                raise DigitalError(f'{fname}: aynı adla farklı içerik (aynı adlı iki ROM dosyası?)')
            files[fname] = text
            wrapper_of[c.ref] = fname
        elif isinstance(c, CY62256):
            files[SRAM_FILE] = _sram_wrapper()
            wrapper_of[c.ref] = SRAM_FILE
    main = _layout(board, names, wrapper_of, tests)
    return {f'{board.name}.dig': main, **files}


def export(board, path, tests=None, rom_mode='embed'):
    """Board'u `path`'e (.dig) yazar; bellek alt devreleri aynı klasöre. Yazılan yolları döndürür."""
    path = Path(path)
    if path.suffix != '.dig':
        raise ValueError('dosya .dig ile bitmeli')
    if path.stem != board.name:
        raise ValueError(f'dosya adı Board adıyla aynı olmalı: {board.name}.dig')
    path.parent.mkdir(parents=True, exist_ok=True)
    written = []
    for fname, text in render(board, path.parent, tests, rom_mode).items():
        p = path.parent / fname
        p.write_bytes(text.encode('utf-8'))
        written.append(p)
    return written


def _layout(board, names, wrapper_of, tests):
    els = []
    # ---- başlık ve testler
    els.append(_el('Text', 0, -240, Description=board.title, textFontSize=28))
    if isinstance(tests, str):
        tests = [(board.name, tests)]
    for i, (label, text) in enumerate(tests or ()):
        els.append(_testcase(label, text, 200 * i, -160))
    # ---- dış bağlantılar (sol sütun)
    in_labels = [p.label for p in board.inputs] + ([board.clock_label] if board.clock else [])
    x_in = _margin(in_labels) + 20
    tun_in = [names[n] for p in board.inputs for n in p.nets]
    y = 0
    els.append(_el('Text', 0, -80, Description='Dış bağlantılar', textFontSize=20))
    for p in board.inputs:
        attrs = dict(Label=p.label, Bits=p.bits if p.bits > 1 else None)
        if p.highz:
            attrs.update(InDefault=_in_default(None), isHighZ=True)
        elif p.default:
            attrs.update(InDefault=_in_default(p.default))
        els.append(_el('In', x_in, y, **attrs))
        if p.bits == 1:
            els.append(_tunnel(names[p.nets[0]], x_in, y))
            y += 40
        else:
            els += _split(x_in, y, f'{p.label}__bus', [names[n] for n in p.nets])[0:1]
            els += [_tunnel(names[n], x_in + GRID, y + GRID * i) for i, n in enumerate(p.nets)]
            y += GRID * p.bits + 40
    if board.clock:
        rt = {'runRealTime': True, 'Frequency': int(board.clock_hz)} if board.clock_hz else {}
        els.append(_el('Clock', x_in, y, Label=board.clock_label, **rt))
        els.append(_tunnel(names[board.clock], x_in, y))
        y += 60
    els.append(_el('VDD', x_in, y))
    els.append(_tunnel('VCC', x_in, y))
    els.append(_el('Ground', x_in + 80, y))
    els.append(_tunnel('GND', x_in + 80, y))
    y += 80
    for net in sorted(board.pulls):
        els.append(_el('PullUp' if board.pulls[net] else 'PullDown', x_in, y))
        els.append(_tunnel(names[net], x_in, y))
        y += 80
    x_out = x_in + GRID + _margin(tun_in + ['GND']) + _margin([names[n] for p in board.outputs
                                                             for n in p.nets])
    y = 0
    for p in board.outputs:
        if p.bits == 1:
            els.append(_el('Out', x_out, y, Label=p.label))
            els.append(_tunnel(names[p.nets[0]], x_out, y, 2))
            y += 40
        else:
            sx = x_out - GRID
            els.append(_el('Splitter', sx, y, Input__Splitting=','.join(['1'] * p.bits),
                           Output__Splitting=str(p.bits)))
            els += [_tunnel(names[n], sx, y + GRID * i, 2) for i, n in enumerate(p.nets)]
            els.append(_el('Out', x_out, y, Label=p.label, Bits=p.bits))
            y += GRID * p.bits + 40
    x_mod = x_out + _margin([p.label for p in board.outputs]) + 120
    # ---- modüller
    groups = {}
    for c in board.chips:
        groups.setdefault(c.module or '-', []).append(c)
    gy = 0
    max_row = 2600
    for module, chips in groups.items():
        cells = []
        for c in chips:
            spec = dil_spec(type(c))
            left, right = [], []
            for leg, (label, _) in spec.pins.items():
                net = _pin_net(c, leg)
                if net is None:
                    continue
                (left if leg <= spec.legs // 2 else right).append(names[net])
            cw, ch = spec.size
            lm, rm = _margin(left), _margin(right)
            cells.append((c, spec, lm, rm, lm + cw + rm + 40, 80 + ch + 100))
        rows, row, w = [], [], 0
        for cell in cells:
            if row and w + cell[4] > max_row:
                rows.append(row)
                row, w = [], 0
            row.append(cell)
            w += cell[4]
        if row:
            rows.append(row)
        pad = 40
        cy = gy + pad + 40
        width = 0
        for row in rows:
            cx = x_mod + pad
            for c, spec, lm, rm, cw_, ch_ in row:
                x0, y0 = cx + lm, cy + 80
                els.extend(_chip_elements(c, spec, x0, y0, names, wrapper_of, lm + rm + spec.size[0]))
                cx += cw_
            width = max(width, cx - x_mod)
            cy += max(cell[5] for cell in row)
        height = cy - gy + pad
        els.insert(0, _el('Rectangle', x_mod, gy, Label=f'{module}',
                          RectWidth=_snap(width + pad) // GRID, RectHeight=_snap(height) // GRID,
                          textFontSize=24))
        gy += _snap(height) + 80
    return _circuit(els, {'Description': f'{board.title}\nTD-8: td8.hw.digital ile üretildi '
                                         f'({len(board.chips)} çip). Elle düzenlemeyin; '
                                         f'Python netlist\'inden yeniden üretin.'})


def _pin_net(chip, leg):
    pin = next(p for p, l in chip.PINOUT.items() if l == leg)
    if pin in POWER_NETS:
        return pin
    return chip.pins.get(pin)


def _chip_elements(c, spec, x0, y0, names, wrapper_of, avail):
    els = []
    file = wrapper_of.get(c.ref, spec.file)
    els.append(_el(file, x0, y0, Label=c.ref))
    head = f'{c.ref}  {c.KIND}'
    note = ' '.join((c.note or '').split())
    maxc = max(10, avail // 12)                     # Digital'in yazısı CHAR_W'den geniş
    if note:
        note = note if len(note) <= maxc else note[:maxc - 1] + '…'
        els.append(_el('Text', x0, y0 - 80, Description=head))
        els.append(_el('Text', x0, y0 - 50, Description=note))
    else:
        els.append(_el('Text', x0, y0 - 50, Description=head))
    for leg in sorted(spec.pins):
        net = _pin_net(c, leg)
        if net is None:
            continue
        x, y = spec.pin_xy(leg, x0, y0)
        els.append(_tunnel(names[net], x, y, 2 if leg <= spec.legs // 2 else 0))
    return els


# ============================================================================
# Modül modül
# ============================================================================
def pin_role(chip, pin):
    """Bacağın gerçek yönü: chip.DIRS, ama DIR'i VCC/GND'ye bağlı 74HC245'in A/B bacakları
    çift yönlü değil (DIR = VCC: A okur, B 3 durumlu sürer; DIR = GND: tersi)."""
    d = chip.DIRS[pin]
    if d == 'bidir' and chip.KIND == '74HC245' and chip.pins.get('DIR') in POWER_NETS:
        a_in = chip.pins['DIR'] == 'VCC'
        return 'in' if (pin[0] == 'A') == a_in else 'tri'
    return d


def sub_board(board, refs, name, inputs=(), outputs=(), clock=None, title=None):
    """Board'daki çiplerin bir alt kümesinden test Board'u (modül sınırını aşan testler için).

    refs: çip ref'leri; inputs/outputs: Port listeleri. Alt kümedeki çiplerin okuduğu ama
    alt kümenin sürmediği, girişlere/saate bağlı olmayan her net sabitlenir: Board'da pull'u
    varsa o değer, yoksa 0 (PullDown). Alt kümenin pull'ları korunur.
    """
    chips = [c for c in board.chips if c.ref in set(refs)]
    missing = set(refs) - {c.ref for c in chips}
    if missing:
        raise DigitalError(f'böyle çip yok: {sorted(missing)}')
    driven, read, used = set(POWER_NETS), [], set()
    for c in chips:
        for pin, net in c.pins.items():
            used.add(net)
            role = pin_role(c, pin)
            if role != 'in':
                driven.add(net)
            if role in ('in', 'bidir') and net not in read:
                read.append(net)
    for p in inputs:
        driven.update(p.nets)
    if clock:
        driven.add(clock)
    pulls = {n: v for n, v in board.pulls.items() if n in used}
    for net in read:
        if net not in driven and net not in pulls:
            pulls[net] = 0
    rom_files = {r: p for r, p in board.rom_files.items() if r in set(refs)}
    return Board(name, chips, pulls, inputs, outputs, clock, rom_files, title or name)


def module_board(board, module, name=None, title=None):
    """Board'un tek modülünü ayrı bir Board yapar; modül sınırındaki netler port olur.

    Dışarıdan sürülüp içeride okunan net → In (adı '/' ile başlıyorsa varsayılanı 1);
    içeride sürülüp dışarıda okunan (ya da üst Board'un çıkışı olan) net → Out; ikisi birden
    (ör. veri yolu) → isHighZ In (etiket = net, varsayılan Z) + Out (etiket = net + '_o').
    Yön `pin_role` ile belirlenir. Saat neti modülde kullanılıyorsa saat olur. Pull'lar korunur.
    """
    chips = [c for c in board.chips if c.module == module]
    if not chips:
        raise DigitalError(f'{module}: bu modülde çip yok')
    inside = {id(c) for c in chips}
    inner_nets = {n for c in chips for n in c.pins.values()}
    use = {}
    order = []

    def mark(net, where, what):
        if net not in use:
            use[net] = set()
            order.append(net)
        use[net].add((where, what))

    for c in board.chips:
        where = 'in' if id(c) in inside else 'out'
        for pin, net in c.pins.items():
            if net in POWER_NETS or net not in inner_nets:
                continue
            d = pin_role(c, pin)
            if d != 'in':
                mark(net, where, 'tri' if d in ('tri', 'bidir') else 'drv')
            if d in ('in', 'bidir'):
                mark(net, where, 'rd')
    for p in board.inputs:
        for net in p.nets:
            if net in use:
                mark(net, 'out', 'tri' if p.highz else 'drv')
    for p in board.outputs:
        for net in p.nets:
            if net in use:
                mark(net, 'out', 'rd')
    inputs, outputs = [], []
    clock = board.clock if board.clock in use else None
    for net in order:
        if net == clock:
            continue
        u = use[net]
        in_drv = any(w == 'in' and k in ('drv', 'tri') for w, k in u)
        in_rd = any(w == 'in' and k == 'rd' for w, k in u)
        out_drv = any(w == 'out' and k in ('drv', 'tri') for w, k in u)
        out_tri = any(w == 'out' and k == 'tri' for w, k in u)
        out_rd = any(w == 'out' and k == 'rd' for w, k in u)
        if in_rd and out_drv and not in_drv:          # aktif düşük girişler açılışta pasif
            inputs.append(Port(safe_name(net), net, default=int(net.startswith('/')),
                               highz=out_tri))
        elif in_drv and out_rd and not out_drv:
            outputs.append(Port(safe_name(net), net))
        elif in_drv and out_drv:
            inputs.append(Port(safe_name(net), net, default=None))
            outputs.append(Port(safe_name(net) + '_o', net))
    pulls = {n: v for n, v in board.pulls.items() if n in use}
    rom_files = {r: p for r, p in board.rom_files.items() if any(c.ref == r for c in chips)}
    mname = name or safe_name(str(module)).lower()
    return Board(mname, chips, pulls, inputs, outputs, clock, rom_files,
                 title or f'{board.title}: {module}', board.clock_hz if clock else None)


def export_all(board, out_dir, module_names=None, tests=None, rom_mode='embed'):
    """Her modül için `<ad>.dig` ve bütün devre için `<board.name>.dig` yazar.

    module_names: {modül: dosya adı (uzantısız)}, ör. {'M4': 'm4_alu'}; verilmezse modül adı
    küçük harfle. tests: {dosya adı (uzantısız): Testcase metni}. Yazılan yolları döndürür.
    """
    out_dir = Path(out_dir)
    tests = tests or {}
    written = []
    modules = list(dict.fromkeys(c.module for c in board.chips if c.module))
    for m in modules:
        name = (module_names or {}).get(m)
        mb = module_board(board, m, name)
        written += export(mb, out_dir / f'{mb.name}.dig', tests.get(mb.name), rom_mode)
    written += export(board, out_dir / f'{board.name}.dig', tests.get(board.name), rom_mode)
    return list(dict.fromkeys(written))


# ============================================================================
# Sim tarafı: aynı Board'u td8.hw.Sim'de koşmak
# ============================================================================
def build_sim(board, **sim_kw):
    """Board'un çiplerini ve pull'larını yeni bir Sim'e ekler; girişleri varsayılana sürer."""
    sim = Sim(**sim_kw)
    sim.add(*board.chips)
    for net in sorted(board.pulls):
        sim.pull(net, board.pulls[net])
    for p in board.inputs:
        _drive(sim, p, p.default)
    if board.clock:
        sim.set(board.clock, 0, who='saat')
    return sim


def _drive(sim, port, value, at=None):
    who = f'port:{port.label}'
    pairs = [(net, None if value is None else (value >> i) & 1) for i, net in enumerate(port.nets)]
    sim._set_many(pairs, who, at)


def read_port(sim, port):
    """Portun Sim'deki değeri: tam sayı, hepsi yüzüyorsa None; kısmen yüzüyorsa DigitalError."""
    bits = [sim.get(n) for n in port.nets]
    if all(b is None for b in bits):
        return None
    if any(b is None for b in bits):
        raise DigitalError(f'{port.label}: bazı bitler yüksek empedans: {bits}')
    return sum(b << i for i, b in enumerate(bits))


def _norm_steps(steps):
    for st in steps:
        if isinstance(st, dict):
            yield st, False
        else:
            values, pulse = st
            yield values, bool(pulse)


def simulate(board, steps, sim=None, settle=1000, **sim_kw):
    """Adımları Sim'de koşar. Döner: (çıkış satırları, giriş durumları, sim).

    Her adım (değerler, darbe): değerler {giriş etiketi: değer} (None = Z); darbe True ise
    saat 1 sonra 0 olur. Her yarım adımda `settle` ns beklenir. Çıkış satırı {etiket: değer}.
    Bir adımın bütün girişleri AYNI ANDA değişir (Digital'deki gibi); aynı anda değişen
    sinyaller arasındaki yarışlar (ör. /WE ile verinin birlikte bırakılması) böylece Sim'de
    ihlal olarak görünür.
    """
    if sim is None:
        sim = build_sim(board, **sim_kw)
    if not sim._started:
        # Digital de önce girişleri varsayılanlarıyla kurar; ilk adımın değerleri gerçek
        # geçişler olarak gelsin (ör. /PL 0 → 1).
        sim.run_for(settle)
    inport = {p.label: p for p in board.inputs}
    state = {p.label: p.default for p in board.inputs}
    rows, states = [], []
    for values, pulse in _norm_steps(steps):
        t = sim.now + 1
        for label, v in values.items():
            if label not in inport:
                raise DigitalError(f'böyle bir giriş yok: {label}')
            _drive(sim, inport[label], v, at=t)
            state[label] = v
        sim.run_for(settle)
        if pulse:
            if not board.clock:
                raise DigitalError('saat darbesi istendi ama Board\'da saat yok')
            sim.set(board.clock, 1, who='saat')
            sim.run_for(settle)
            sim.set(board.clock, 0, who='saat')
            sim.run_for(settle)
        rows.append({p.label: read_port(sim, p) for p in board.outputs})
        states.append(dict(state))
    return rows, states, sim


def fmt_value(v, bits):
    if v is None:
        return 'Z'
    if bits == 1:
        return str(v)
    return f'0x{v:0{(bits + 3) // 4}X}'


def testcase_text(board, steps, rows=None, states=None, comments=(), **sim_kw):
    """Digital Testcase metni: başlık girişler + [saat] + çıkışlar; beklenenler Sim'den.

    rows/states verilmezse `simulate` çağrılır. Döner: metin.
    """
    steps = list(_norm_steps(steps))
    if rows is None:
        rows, states, _ = simulate(board, steps, **sim_kw)
    head = [p.label for p in board.inputs]
    if board.clock:
        head.append(board.clock_label)
    head += [p.label for p in board.outputs]
    lines = [f'# {c}' for c in comments]
    lines.append(' '.join(head))
    for (values, pulse), row, st in zip(steps, rows, states):
        cells = [fmt_value(st[p.label], p.bits) for p in board.inputs]
        if board.clock:
            cells.append('C' if pulse else '0')
        cells += [fmt_value(row[p.label], p.bits) for p in board.outputs]
        lines.append(' '.join(cells))
    return '\n'.join(lines) + '\n'


# ============================================================================
# Digital'i çalıştırmak
# ============================================================================
class DigitalSetup:
    """Digital kurulumu: java, javac (yoksa None), Digital.jar."""

    def __init__(self, home, java, javac, jar):
        self.home, self.java, self.javac, self.jar = home, java, javac, jar

    @property
    def library(self):
        return self.jar.parent / 'lib' / 'DIL Chips' / '74xx'

    def __repr__(self):
        return f'DigitalSetup(java={self.java}, jar={self.jar})'


def find_digital(home=None):
    """Digital'i bulur: home > TD8_DIGITAL_HOME > <depo>/../araclar. Bulamazsa None.

    home klasöründe `Digital/Digital.jar` (ya da doğrudan `Digital.jar`) ve isteğe bağlı
    `jdk-21/bin/java` aranır; java yoksa JAVA_HOME ve PATH denenir.
    """
    home = Path(home or os.environ.get('TD8_DIGITAL_HOME') or DEFAULT_HOME)
    jar = next((j for j in (home / 'Digital' / 'Digital.jar', home / 'Digital.jar') if j.is_file()),
               None)
    if jar is None:
        return None
    exe = '.exe' if os.name == 'nt' else ''
    cands = [home / 'jdk-21' / 'bin']
    if os.environ.get('JAVA_HOME'):
        cands.append(Path(os.environ['JAVA_HOME']) / 'bin')
    java = javac = None
    for d in cands:
        if (d / f'java{exe}').is_file():
            java = d / f'java{exe}'
            javac = d / f'javac{exe}' if (d / f'javac{exe}').is_file() else None
            break
    if java is None:
        w = shutil.which('java')
        if w is None:
            return None
        java = Path(w)
        w = shutil.which('javac')
        javac = Path(w) if w else None
    return DigitalSetup(home, java, javac, jar)


_JVM_OPTS = ['-Djava.awt.headless=true', '-Dstdout.encoding=UTF-8', '-Dstderr.encoding=UTF-8',
             '-Dfile.encoding=UTF-8']


def _run(cmd, timeout, cwd=None):
    t0 = time.perf_counter()
    p = subprocess.run([str(c) for c in cmd], capture_output=True, timeout=timeout,
                       cwd=None if cwd is None else str(cwd))
    dt = time.perf_counter() - t0
    out = p.stdout.decode('utf-8', 'replace').replace('\r\n', '\n')
    err = p.stderr.decode('utf-8', 'replace').replace('\r\n', '\n')
    return p.returncode, out, err, dt


class TestRun:
    """`CLI test` sonucu. returncode: 0 geçti, 1 kaldı, 2 çalışma hatası (Digital'e göre)."""
    __test__ = False                      # unittest/pytest bunu test sınıfı sanmasın

    def __init__(self, returncode, output, seconds, cmd):
        self.returncode = returncode
        self.output = output
        self.seconds = seconds
        self.cmd = cmd
        self.results = re.findall(r'^(\S[^\n]*?): (passed|failed[^\n]*)$', output, re.M)

    @property
    def passed(self):
        return self.returncode == 0 and bool(self.results) and all(
            s == 'passed' for _, s in self.results)

    def mismatches(self):
        """-verbose çıktısındaki tutmayan hücreler: [(test, satır no, sütun, beklenen, bulunan)].

        Satır no, Digital'in bastığı (repeat/loop açılmış) tablodaki 0 tabanlı sıradır.
        """
        out = []
        lines = [ln for ln in self.output.splitlines() if ' INFO ' not in ln]
        i = 0
        while i < len(lines):
            m = re.match(r'^(\S[^\n]*?): failed', lines[i])
            if not m or i + 1 >= len(lines):
                i += 1
                continue
            head = lines[i + 1].split()
            j, row = i + 2, 0
            while j < len(lines):
                ln = lines[j]
                if (not ln.strip() or ln.startswith('Tests ')
                        or re.match(r'^\S[^\n]*?: (passed|failed)', ln)):
                    break
                for k, cell in enumerate(re.findall(r'E: \S+ / F: \S+|\S+', ln)):
                    e = re.fullmatch(r'E: (\S+) / F: (\S+)', cell)
                    if e:
                        out.append((m.group(1), row, head[k] if k < len(head) else str(k),
                                    e.group(1), e.group(2)))
                row += 1
                j += 1
            i = j
        return out

    def summary(self):
        """Gürültüsüz özet (INFO satırları ve Java yığın izleri atılır)."""
        keep = [ln for ln in self.output.splitlines()
                if ln.strip() and ' INFO ' not in ln and not ln.lstrip().startswith('at ')]
        return '\n'.join(keep)

    def __repr__(self):
        return f'TestRun(rc={self.returncode}, {self.results}, {self.seconds:.1f} s)'


def run_test(dig, tests=None, verbose=False, setup=None, timeout=1800, cwd=None):
    """`java -cp Digital.jar CLI test -circ dig [-tests tests] [-verbose]`.

    Java, `cwd` verilmezse .dig'in klasöründe başlatılır (göreli ROM yolları için; bkz. render).
    """
    setup = setup or find_digital()
    if setup is None:
        raise DigitalError('Digital bulunamadı (TD8_DIGITAL_HOME ayarlayın)')
    cmd = [setup.java, *_JVM_OPTS, '-cp', setup.jar, 'CLI', 'test', '-circ', Path(dig).resolve()]
    if tests:
        cmd += ['-tests', Path(tests).resolve()]
    if verbose:
        cmd.append('-verbose')
    code, out, err, dt = _run(cmd, timeout, cwd or Path(dig).resolve().parent)
    return TestRun(code, out + err, dt, cmd)


def _stepper_classpath(setup):
    """TD8Adim'i geçici klasöre derler (javac varsa); (classpath, ana sınıf ya da kaynak)."""
    src = STEPPER_SRC.read_bytes()
    st = setup.jar.stat()
    key = hashlib.sha1(src + f'{st.st_size}:{int(st.st_mtime)}'.encode()).hexdigest()[:12]
    if setup.javac is None:
        return str(setup.jar), str(STEPPER_SRC)              # tek dosya kaynak çalıştırma
    out = Path(tempfile.gettempdir()) / 'td8_digital_arac' / key
    if not (out / 'TD8Adim.class').is_file():
        out.mkdir(parents=True, exist_ok=True)
        code, o, e, _ = _run([setup.javac, '-encoding', 'UTF-8', '-cp', setup.jar, '-d', out,
                              STEPPER_SRC], 300)
        if code:
            raise DigitalError(f'TD8Adim derlenemedi:\n{o}{e}')
    return f'{setup.jar}{os.pathsep}{out}', 'TD8Adim'


class StepRun:
    """Adımlayıcı sonucu: names (CYC dahil), rows (vectors.parse_table biçiminde),
    seconds (java süreci dahil toplam), sim_seconds/rate (yalnız adımlama), text (CSV)."""

    def __init__(self, text, err, seconds):
        from .. import vectors
        self.text = text
        self.names, self.rows = vectors.parse_table(text)
        self.seconds = seconds
        m = re.search(r'TD8Adim: (\d+) periyot, (\d+) satır, ([\d.]+) s, (\d+) periyot/sn', err)
        self.sim_seconds = float(m.group(3)) if m else None
        self.rate = int(m.group(4)) if m else None
        self.log = err

    def column(self, name):
        i = self.names.index(name)
        return [r[i] for r in self.rows]

    def as_dicts(self):
        return [dict(zip(self.names, r)) for r in self.rows]


def run_stepper(dig, cycles, clock=None, trigger=None, sets=None, signals=None, setup=None,
                timeout=3600, cwd=None, end_row=False, dumps=None):
    """Digital'de devreyi `cycles` saat periyodu adımlar (sim/digital/arac/TD8Adim.java).

    clock:   saat etiketi (verilmezse ilk Clock)
    trigger: 'AD' ya da 'AD:fall' — satırlar AD'nin kenarından hemen önceki değerler
    sets:    [(giriş etiketi, değer, periyot), ...] ya da {etiket: değer} (değer None = Z)
    signals: kaydedilecek etiketler (verilmezse bütün Out'lar)
    end_row: sona son durumu CYC = -1 satırı olarak ekle
    dumps:   {RAM etiketi (bellek alt devresinde örneğin ref'i, ör. 'U602'): dosya yolu} ya da
             [(etiket, yol, periyot), ...]: RAM içeriği oraya ham bayt olarak yazılır — koşu
             sonunda ya da (periyot verilirse) o periyodun başında, girişler uygulanmadan önce
    """
    setup = setup or find_digital()
    if setup is None:
        raise DigitalError('Digital bulunamadı (TD8_DIGITAL_HOME ayarlayın)')
    cp, main = _stepper_classpath(setup)
    cmd = [setup.java, *_JVM_OPTS, '-cp', cp, main, Path(dig).resolve(), '-n', str(cycles)]
    if clock:
        cmd += ['-c', clock]
    if trigger:
        cmd += ['-t', trigger]
    if signals:
        cmd += ['-w', ','.join(signals)]
    if isinstance(sets, dict):
        sets = [(k, v, 0) for k, v in sets.items()]
    for label, value, at in sets or ():
        cmd += ['-s', f'{label}={"Z" if value is None else value}@{at}']
    if end_row:
        cmd += ['-e', '1']
    if isinstance(dumps, dict):
        dumps = [(k, v, None) for k, v in dumps.items()]
    for label, path, at in dumps or ():
        cmd += ['-m', f'{label}={Path(path).resolve()}' + ('' if at is None else f'@{at}')]
    code, out, err, dt = _run(cmd, timeout, cwd or Path(dig).resolve().parent)
    if code:
        msg = '\n'.join(ln for ln in err.splitlines() if 'TD8Adim' in ln or 'Exception' in ln)
        raise DigitalError(f'adımlayıcı hata kodu {code}: {msg or err[-2000:]}')
    return StepRun(out, err, dt)
