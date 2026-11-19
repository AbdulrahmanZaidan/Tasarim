"""74HC entegre ve bellek modelleri (ta8.hw.kernel.Sim için).

Kullanım:
    sim.add(HC161('U12', {'/MR': '/RESET_s', 'CP': 'CLK', 'D0': 'DB0', ...},
                  module='M3', note='AR bit 0-3'))

Kurallar:
- Pin adları datasheet adlarıdır (çoğunlukla Nexperia). Aktif-düşük pinler
  `/` ile başlar; çok birimli paketlerde birim numarası `/`dan sonra gelir:
  '/1RD', '/2Q', '/1E', '/1Y0'. Kolaylık için '1/RD' yazımı da kabul edilir.
- Güç pinleri (VCC, GND) PINOUT'ta vardır ama netlist'te bağlanmaz.
- Her 'in' pini bağlanmalıdır (kullanılmayan kapı girişi GND'ye). Çıkış ve
  çift yönlü pinler boş kalabilir; o zaman '<ref>.<pin>' adlı özel bir net alır.
- TI adlarıyla da bağlanabilen pinler (ALIASES): 138'de G1 → E3, /G2A → /E1,
  /G2B → /E2; 191'de /CTEN → /CE, /LOAD → /PL, CLK → CP, /RCO → /RC,
  TC → MAX/MIN; 688'de /E → /G.
- Yönler: 'in' giriş, 'out' hep süren çıkış, 'tri' 3 durumlu çıkış, 'bidir'
  çift yönlü (245 A/B, SRAM IO).

Pin tablosu (pin=DIP bacağı; `pin_table()` ile üretilir, testle eşitliği denetlenir):

74HC00 (HC00, DIP-14) dörtlü 2-girişli NAND:
    1A=1 1B=2 1Y=3 2A=4 2B=5 2Y=6 GND=7 3Y=8 3A=9 3B=10 4Y=11 4A=12 4B=13 VCC=14
74HC02 (HC02, DIP-14) dörtlü 2-girişli NOR:
    1Y=1 1A=2 1B=3 2Y=4 2A=5 2B=6 GND=7 3A=8 3B=9 3Y=10 4A=11 4B=12 4Y=13 VCC=14
74HC04 (HC04, DIP-14) altılı tersleyici:
    1A=1 1Y=2 2A=3 2Y=4 3A=5 3Y=6 GND=7 4Y=8 4A=9 5Y=10 5A=11 6Y=12 6A=13 VCC=14
74HC08 (HC08, DIP-14) dörtlü 2-girişli AND:
    1A=1 1B=2 1Y=3 2A=4 2B=5 2Y=6 GND=7 3Y=8 3A=9 3B=10 4Y=11 4A=12 4B=13 VCC=14
74HC14 (HC14, DIP-14) altılı Schmitt tersleyici:
    1A=1 1Y=2 2A=3 2Y=4 3A=5 3Y=6 GND=7 4Y=8 4A=9 5Y=10 5A=11 6Y=12 6A=13 VCC=14
74HC20 (HC20, DIP-14) ikili 4-girişli NAND (3 ve 11 NC):
    1A=1 1B=2 1C=4 1D=5 1Y=6 GND=7 2Y=8 2A=9 2B=10 2C=12 2D=13 VCC=14
74HC32 (HC32, DIP-14) dörtlü 2-girişli OR:
    1A=1 1B=2 1Y=3 2A=4 2B=5 2Y=6 GND=7 3Y=8 3A=9 3B=10 4Y=11 4A=12 4B=13 VCC=14
74HC74 (HC74, DIP-14) ikili D flip-flop, asenkron /SD /RD:
    /1RD=1 1D=2 1CP=3 /1SD=4 1Q=5 /1Q=6 GND=7 /2Q=8 2Q=9 /2SD=10 2CP=11 2D=12 /2RD=13 VCC=14
74HC138 (HC138, DIP-16) 3→8 kod çözücü:
    A0=1 A1=2 A2=3 /E1=4 /E2=5 E3=6 /Y7=7 GND=8 /Y6=9 /Y5=10 /Y4=11 /Y3=12 /Y2=13 /Y1=14 /Y0=15
    VCC=16
74HC139 (HC139, DIP-16) ikili 2→4 kod çözücü:
    /1E=1 1A0=2 1A1=3 /1Y0=4 /1Y1=5 /1Y2=6 /1Y3=7 GND=8 /2Y3=9 /2Y2=10 /2Y1=11 /2Y0=12 2A1=13
    2A0=14 /2E=15 VCC=16
74HC153 (HC153, DIP-16) ikili 4→1 seçici:
    /1E=1 S1=2 1I3=3 1I2=4 1I1=5 1I0=6 1Y=7 GND=8 2Y=9 2I0=10 2I1=11 2I2=12 2I3=13 S0=14 /2E=15
    VCC=16
74HC157 (HC157, DIP-16) dörtlü 2→1 seçici:
    S=1 1I0=2 1I1=3 1Y=4 2I0=5 2I1=6 2Y=7 GND=8 3Y=9 3I1=10 3I0=11 4Y=12 4I1=13 4I0=14 /E=15
    VCC=16
74HC161 (HC161, DIP-16) 4-bit sayıcı, asenkron /MR:
    /MR=1 CP=2 D0=3 D1=4 D2=5 D3=6 CEP=7 GND=8 /PE=9 CET=10 Q3=11 Q2=12 Q1=13 Q0=14 TC=15 VCC=16
74HC163 (HC163, DIP-16) 4-bit sayıcı, senkron /MR:
    /MR=1 CP=2 D0=3 D1=4 D2=5 D3=6 CEP=7 GND=8 /PE=9 CET=10 Q3=11 Q2=12 Q1=13 Q0=14 TC=15 VCC=16
74HC164 (HC164, DIP-14) 8-bit seri giriş kaydırma registerı:
    DSA=1 DSB=2 Q0=3 Q1=4 Q2=5 Q3=6 GND=7 CP=8 /MR=9 Q4=10 Q5=11 Q6=12 Q7=13 VCC=14
74HC166 (HC166, DIP-16) 8-bit paralel giriş kaydırma registerı:
    DS=1 D0=2 D1=3 D2=4 D3=5 /CE=6 CP=7 GND=8 /MR=9 D4=10 D5=11 D6=12 Q7=13 D7=14 /PE=15 VCC=16
74HC175 (HC175, DIP-16) dörtlü D flip-flop, /MR:
    /MR=1 Q0=2 /Q0=3 D0=4 D1=5 /Q1=6 Q1=7 GND=8 CP=9 Q2=10 /Q2=11 D2=12 D3=13 /Q3=14 Q3=15
    VCC=16
74HC191 (HC191, DIP-16) 4-bit yukarı/aşağı sayıcı, asenkron /PL:
    D1=1 Q1=2 Q0=3 /CE=4 D/U=5 Q2=6 Q3=7 GND=8 D3=9 D2=10 /PL=11 MAX/MIN=12 /RC=13 CP=14 D0=15
    VCC=16
74HC245 (HC245, DIP-20) 8-bit çift yönlü tampon:
    DIR=1 A0=2 A1=3 A2=4 A3=5 A4=6 A5=7 A6=8 A7=9 GND=10 B7=11 B6=12 B5=13 B4=14 B3=15 B2=16
    B1=17 B0=18 /OE=19 VCC=20
74HC273 (HC273, DIP-20) 8-bit D register, asenkron /MR:
    /MR=1 Q0=2 D0=3 D1=4 Q1=5 Q2=6 D2=7 D3=8 Q3=9 GND=10 CP=11 Q4=12 D4=13 D5=14 Q5=15 Q6=16
    D6=17 D7=18 Q7=19 VCC=20
74HC377 (HC377, DIP-20) 8-bit D register, senkron /E:
    /E=1 Q0=2 D0=3 D1=4 Q1=5 Q2=6 D2=7 D3=8 Q3=9 GND=10 CP=11 Q4=12 D4=13 D5=14 Q5=15 Q6=16
    D6=17 D7=18 Q7=19 VCC=20
74HC540 (HC540, DIP-20) 8-bit tersleyen 3 durumlu tampon:
    /OE1=1 A0=2 A1=3 A2=4 A3=5 A4=6 A5=7 A6=8 A7=9 GND=10 /Y7=11 /Y6=12 /Y5=13 /Y4=14 /Y3=15
    /Y2=16 /Y1=17 /Y0=18 /OE2=19 VCC=20
74HC688 (HC688, DIP-20) 8-bit eşitlik karşılaştırıcı:
    /G=1 P0=2 Q0=3 P1=4 Q1=5 P2=6 Q2=7 P3=8 Q3=9 GND=10 P4=11 Q4=12 P5=13 Q5=14 P6=15 Q6=16
    P7=17 Q7=18 /P=Q=19 VCC=20
SST39SF010 (SST39SF010, DIP-32) 128K×8 flash, yalnız okuma (1 ve 30 NC):
    A16=2 A15=3 A12=4 A7=5 A6=6 A5=7 A4=8 A3=9 A2=10 A1=11 A0=12 DQ0=13 DQ1=14 DQ2=15 GND=16
    DQ3=17 DQ4=18 DQ5=19 DQ6=20 DQ7=21 /CE=22 A10=23 /OE=24 A11=25 A9=26 A8=27 A13=28 A14=29
    /WE=31 VCC=32
CY62256 (CY62256, DIP-28) 32K×8 asenkron SRAM:
    A14=1 A12=2 A7=3 A6=4 A5=5 A4=6 A3=7 A2=8 A1=9 A0=10 IO0=11 IO1=12 IO2=13 GND=14 IO3=15
    IO4=16 IO5=17 IO6=18 IO7=19 /CE=20 A10=21 /OE=22 A11=23 A9=24 A8=25 A13=26 /WE=27 VCC=28

Not: CY62256 bacakları JEDEC 62256 düzenidir; Cypress datasheet'i adres
pinlerini farklı adlandırıyor olabilir (SRAM'de adres sırası işlevsel olarak
önemsiz, ama kablolamadan önce gerçek datasheet'le karşılaştırın).
"""

import re

from .kernel import NEVER

# ----------------------------------------------------------------------------
# Gecikmeler ve zamanlama kısıtları
#
# YAKLAŞIK DEĞERLER; GERÇEK DATASHEET'TEN DOĞRULANACAK. Uydurma kesinlik iddiası
# yoktur. Her değer (tipik, en_kötü, kaynak):
#   'P' = projenin elle zamanlama hesabındaki değer (tasarim-taslaklari/
#         ISA-v0-sentez.md 5.4: 5 V, 25 °C). Simülasyon o hesapla (yol 1:
#         254/403 ns, yol 2: 94/152 ns) karşılaştırılabilsin diye aynen alındı.
#   'T' = planda yok; datasheet bilgisinden tahmin (VCC 4.5–5 V, 25 °C,
#         CL = 50 pF; Nexperia/TI 74HC tipik ve max sütunlarına yakın).
# Sim(corner='typ') 1. sütunu, Sim(corner='max') 2. sütunu kullanır.
# Bütün gecikmeler ≥ 1 ns (sıfır gecikmeli döngü olmasın; modül yüklenirken denetlenir).
# ----------------------------------------------------------------------------
_GATE = {'tpd': (9, 25, 'P')}

DELAYS = {
    '74HC00': _GATE, '74HC02': _GATE, '74HC04': _GATE, '74HC08': _GATE,
    '74HC20': _GATE, '74HC32': _GATE,
    '74HC14': {'tpd': (12, 30, 'T')},                    # Schmitt girişli, biraz yavaş
    '74HC74': {'cp_q': (16, 44, 'T'),                    # CP → Q, /Q
               'sdrd_q': (16, 50, 'T')},                 # /SD, /RD → Q, /Q
    '74HC138': {'addr': (15, 35, 'P'),                   # An → /Yn
                'en': (15, 35, 'P')},                    # E1/E2/E3 → /Yn (planda tek değer)
    '74HC139': {'addr': (15, 35, 'P'), 'en': (15, 35, 'P')},
    '74HC153': {'data': (14, 36, 'T'),                   # nIn → nY
                'sel': (16, 45, 'T'),                    # S0/S1 → nY
                'en': (12, 30, 'T')},                    # /nE → nY
    '74HC157': {'data': (11, 28, 'T'), 'sel': (16, 38, 'T'), 'en': (14, 35, 'T')},
    '74HC161': {'cp_q': (17, 40, 'P'),                   # CP → Qn
                'cp_tc': (21, 44, 'T'),                  # CP → TC
                'cet_tc': (11, 30, 'T'),                 # CET → TC
                'mr_q': (19, 44, 'T'),                   # /MR → Qn
                'mr_tc': (22, 49, 'T')},                 # /MR → TC
    '74HC163': {'cp_q': (17, 40, 'T'), 'cp_tc': (21, 44, 'T'), 'cet_tc': (11, 30, 'T')},
    '74HC164': {'cp_q': (15, 35, 'T'), 'mr_q': (15, 35, 'T')},
    '74HC166': {'cp_q': (17, 40, 'T'), 'mr_q': (17, 40, 'T')},
    '74HC175': {'cp_q': (14, 35, 'T'), 'mr_q': (14, 35, 'T')},
    '74HC191': {'cp_q': (22, 44, 'T'),                   # CP → Qn
                'pl_q': (22, 50, 'T'),                   # /PL ya da (/PL düşükken) Dn → Qn
                'cp_tc': (28, 55, 'T'),                  # CP → MAX/MIN
                'du_tc': (19, 40, 'T'),                  # D/U → MAX/MIN
                'rc': (13, 30, 'T')},                    # CP, /CE → /RC
    '74HC245': {'data': (10, 22, 'P'),                   # An ↔ Bn
                'en': (18, 38, 'P'),                     # /OE, DIR → çıkış açılır
                'dis': (16, 38, 'T')},                   # /OE, DIR → yüksek empedans
    '74HC273': {'cp_q': (14, 30, 'P'), 'mr_q': (14, 30, 'T')},
    '74HC377': {'cp_q': (14, 30, 'P')},
    '74HC540': {'data': (10, 22, 'T'), 'en': (15, 38, 'T'), 'dis': (15, 38, 'T')},
    '74HC688': {'data': (15, 40, 'T'), 'en': (12, 30, 'T')},
    # Bellekler: datasheet'ler yalnız en kötü değeri verir; tipikler tahmin.
    'SST39SF010-70': {'acc': (55, 70, 'P'),              # tAA adres → veri
                      'ce': (55, 70, 'T'),               # tCE /CE → veri
                      'oe': (25, 35, 'T'),               # tOE /OE → veri
                      'hz': (15, 25, 'T')},              # tOHZ/tCHZ (tDF) → yüksek empedans
    'SST39SF010-90': {'acc': (70, 90, 'T'), 'ce': (70, 90, 'T'), 'oe': (30, 45, 'T'),
                      'hz': (20, 30, 'T')},
    'CY62256-70': {'acc': (55, 70, 'P'),                 # tAA (plan yalnız 70 verir; 55 tahmin)
                   'ce': (55, 70, 'T'),                  # tACE
                   'oe': (25, 35, 'T'),                  # tDOE
                   'hz': (15, 25, 'T'),                  # tHZOE / tHZCE
                   'we_hz': (15, 25, 'T'),               # tHZWE: /WE düşük → yüksek empedans
                   'we_lz': (5, 10, 'T')},               # /WE yüksek → çıkış geri gelir
}

# Kısıtlar (ns, ihlal denetimi için). setup: veri/izin saat kenarından en az bu
# kadar önce oturmalı; hold: kenardan sonra en az bu kadar sabit kalmalı (plan
# varsayımı ≤ 5 ns); rec: asenkron temizleme/yükleme bırakıldıktan sonra saat
# kenarına kadar geçmesi gereken süre (toparlanma, 'setup' türüyle raporlanır).
LIMITS = {
    '74HC74': {'setup': (6, 15, 'T'), 'hold': (0, 3, 'T'), 'rec': (3, 6, 'T')},
    '74HC161': {'su_d': (15, 30, 'P'), 'su_pe': (15, 30, 'P'), 'su_ce': (15, 30, 'P'),
                'hold': (0, 3, 'T'), 'rec': (6, 20, 'T')},
    '74HC163': {'su_d': (15, 30, 'T'), 'su_pe': (15, 30, 'T'), 'su_ce': (15, 30, 'T'),
                'su_mr': (15, 30, 'T'), 'hold': (0, 3, 'T')},
    '74HC164': {'setup': (5, 12, 'T'), 'hold': (0, 3, 'T'), 'rec': (5, 12, 'T')},
    '74HC166': {'su_d': (8, 20, 'T'), 'su_pe': (8, 20, 'T'), 'hold': (0, 3, 'T'),
                'rec': (5, 15, 'T')},
    '74HC175': {'setup': (6, 15, 'T'), 'hold': (0, 3, 'T'), 'rec': (3, 6, 'T')},
    '74HC191': {'su_ce': (12, 30, 'T'), 'su_du': (15, 35, 'T'), 'hold': (0, 3, 'T'),
                'rec': (5, 15, 'T')},
    '74HC273': {'setup': (12, 20, 'P'), 'hold': (0, 3, 'T'), 'rec': (3, 10, 'T')},
    '74HC377': {'su_d': (12, 20, 'T'), 'su_e': (12, 20, 'T'), 'hold': (0, 5, 'T')},
    # SRAM yazma: datasheet'in garanti ettiği en küçük değerler (iki sütun aynı).
    'CY62256-70': {'wp': (50, 50, 'T'),                  # tPWE /WE (ve /CE) çakışma darbesi
                   'sd': (30, 30, 'T'),                  # tSD veri kurulumu (yazma sonuna)
                   'aw': (60, 60, 'T'),                  # tAW adres kurulumu (yazma sonuna)
                   'sa': (0, 0, 'T')},                   # tSA adres → yazma başı
}

for _kind, _paths in DELAYS.items():
    for _path, (_typ, _max, _src) in _paths.items():
        assert 1 <= _typ <= _max and _src in 'PT', (_kind, _path)


# ----------------------------------------------------------------------------
# Yardımcılar
# ----------------------------------------------------------------------------
def _dirs(ins='', outs='', tris='', bidirs=''):
    d = {}
    for kind, names in (('in', ins), ('out', outs), ('tri', tris), ('bidir', bidirs)):
        for p in names.split():
            d[p] = kind
    return d


def _seq(fmt, n):
    return ' '.join(fmt.format(i) for i in range(n))


def _rd(lv, nets):
    """Net listesini (LSB önce) tam sayı olarak okur."""
    v = 0
    b = 1
    for n in nets:
        if lv[n]:
            v |= b
        b <<= 1
    return v


def bus_pins(pin_prefix, net_prefix, width, pin_start=0, net_start=0):
    """{'D0': 'DB0', ...} sözlüğü: netlist yazarken kısaltma."""
    return {f'{pin_prefix}{pin_start + i}': f'{net_prefix}{net_start + i}' for i in range(width)}


class Chip:
    """Bütün çip modellerinin tabanı.

    Alt sınıf KIND, PINOUT (pin → DIP bacağı, VCC/GND dahil) ve DIRS (pin →
    yön) tanımlar; setup()'ta hızlı indeks listelerini kurar, evaluate()'te
    girişleri `self.lv` (None → 0) ya da `self.val` (ham) üzerinden okur ve
    çıkışları `self.sched(yuva, değer, zaman)` ile zamanlar.
    """
    KIND = ''
    PINOUT = {}
    DIRS = {}
    ALIASES = {}
    DELAY_KEY = None                      # DELAYS anahtarı (varsayılan KIND)

    def __init__(self, ref, pins, module=None, note=''):
        self.ref = ref
        self.module = module
        self.note = note
        self.pins = {}
        for pin, net in pins.items():
            p = self._canon(pin)
            if p in self.pins:
                raise ValueError(f'{ref} ({self.KIND}): {p} iki kez bağlanmış')
            if not isinstance(net, str) or not net:
                raise ValueError(f'{ref} ({self.KIND}): {p} için net adı geçersiz: {net!r}')
            self.pins[p] = net
        self.sim = None
        self._mark = -1

    def _canon(self, pin):
        if pin in self.DIRS:
            return pin
        p = self.ALIASES.get(pin)
        if p is None:
            m = re.fullmatch(r'(\d)/(.+)', pin)          # '1/RD' → '/1RD'
            p = f'/{m.group(1)}{m.group(2)}' if m else None
        if p in self.DIRS:
            return p
        if pin in ('VCC', 'GND'):
            raise ValueError(f'{self.ref} ({self.KIND}): güç pinleri netlist\'te bağlanmaz')
        raise ValueError(f'{self.ref} ({self.KIND}): bilinmeyen pin {pin!r}; '
                         f'geçerli pinler: {" ".join(self.DIRS)}')

    @property
    def kind(self):
        return self.KIND

    def __repr__(self):
        return f'<{self.KIND} {self.ref}>'

    @classmethod
    def leg(cls, pin):
        return cls.PINOUT[pin]

    def _attach(self, sim):
        missing = [p for p, d in self.DIRS.items() if d == 'in' and p not in self.pins]
        if missing:
            raise ValueError(f'{self.ref} ({self.KIND}): bağlanmamış giriş: {", ".join(missing)} '
                             '(CMOS girişi boşta kalamaz; kullanılmıyorsa GND ya da VCC\'ye bağlayın)')
        self.sim = sim
        self.n = {}
        self.s = {}
        self._pin_of = {}
        for p, d in self.DIRS.items():
            n = sim._net(self.pins.get(p) or f'{self.ref}.{p}')
            self.n[p] = n
            self._pin_of.setdefault(n, p)
            if d != 'in':
                self.s[p] = sim._driver(n, self.ref)
            if d in ('in', 'bidir'):
                sim._listen(n, self, d == 'in')
        key = self.DELAY_KEY or self.KIND
        col = sim._col
        self.dl = {k: v[col] for k, v in DELAYS[key].items()}
        self.lim = {k: v[col] for k, v in LIMITS.get(key, {}).items()}
        self.hwin = max(self.lim.get('hold', 0), 1)
        self.val = sim.val
        self.lv = sim.lv
        self.sched = sim._sched
        self.chk = sim.checks
        self.te = NEVER                   # son saat kenarı
        self.hn = ()                      # o kenarda tutma denetimi gereken netler
        self._floated = {}                # net → raporlanan yüzme döneminin başlangıcı
        self.setup()

    def setup(self):
        pass

    def _start(self):
        """Simülasyon başlarken (TB'nin ilk değerleri verildikten sonra) çağrılır."""

    def evaluate(self):
        raise NotImplementedError

    # --- çıkış yardımcıları ---
    def _out(self, slots, old, new, t):
        """new değerinin old'dan farklı bitlerini t anına zamanlar (old None: hepsi)."""
        d = (1 << len(slots)) - 1 if old is None else old ^ new
        i = 0
        sched = self.sched
        while d:
            if d & 1:
                sched(slots[i], (new >> i) & 1, t)
            d >>= 1
            i += 1

    def _off(self, slots, t):
        for s in slots:
            self.sched(s, None, t)

    # --- denetim yardımcıları ---
    def _pn(self, n):
        return f'{self._pin_of.get(n, "?")} ({self.sim.names[n]})'

    def _rd_chk(self, nets):
        """Çift yönlü pinlerden okur; yüzen bit 'yuzen' ihlali olur ve 0 sayılır."""
        val = self.val
        v = 0
        b = 1
        for n in nets:
            x = val[n]
            if x:
                v |= b
            elif x is None and self.chk:
                self._float_read(n)
            b <<= 1
        return v

    def _float_read(self, n):
        sim = self.sim
        if sim._cstart[n] >= 0:
            return                                        # çakışma zaten raporlandı
        episode = sim.lastch[n]
        if self._floated.get(n) == episode:
            return                                        # bu yüzme dönemi raporlandı
        self._floated[n] = episode
        if sim._starting:                                 # açılış: bütün çipler sürünce bakılır
            sim._deferred.append((self, n))
            return
        if sim.lastch[n] == NEVER and not sim._undriven(n, self.ref):
            return                                        # açılış geçişi: sürücü yolda
        sim.violation(sim.now, 'yuzen', self.ref, f'{self._pn(n)} yüzerken okundu; 0 sayıldı')

    def _chk_setup(self, t, nets, need):
        lc = self.sim.lastch
        for n in nets:
            dt = t - lc[n]
            if dt < need:
                self.sim.violation(t, 'setup', self.ref,
                                   f'{self._pn(n)} kenardan {dt} ns önce değişti (gereken {need} ns)')

    def _chk_rec(self, t, n, need):
        dt = t - self.sim.lastch[n]
        if dt < need:
            self.sim.violation(t, 'setup', self.ref,
                               f'{self._pn(n)} bırakıldıktan {dt} ns sonra saat kenarı geldi '
                               f'(toparlanma {need} ns)')

    def _arm_hold(self, t, nets):
        self.te = t
        self.hn = nets

    def _chk_hold(self, t):
        lc = self.sim.lastch
        for n in self.hn:
            if lc[n] == t:
                self.sim.violation(t, 'hold', self.ref,
                                   f'{self._pn(n)} kenardan {t - self.te} ns sonra değişti '
                                   f'(tutma {self.lim.get("hold", 0)} ns)')

    def _rule(self, desc):
        self.sim.violation(self.sim.now, 'setup', self.ref, desc)


# ----------------------------------------------------------------------------
# Kapılar
# ----------------------------------------------------------------------------
class _Gates(Chip):
    UNITS = ()                            # ((giriş pinleri), çıkış pini)
    AND = True                            # True: hepsi 1 ise 1; False: biri 1 ise 1
    INV = 0                               # 1: çıkış terslenir

    def setup(self):
        self.units = [([self.n[p] for p in ins], self.s[out]) for ins, out in self.UNITS]
        self.o = [None] * len(self.units)
        self.tpd = self.dl['tpd']

    def evaluate(self):
        lv = self.lv
        t = self.sim.now + self.tpd
        o = self.o
        andlike = self.AND
        for k, (ins, slot) in enumerate(self.units):
            if andlike:
                v = 1
                for n in ins:
                    if not lv[n]:
                        v = 0
                        break
            else:
                v = 0
                for n in ins:
                    if lv[n]:
                        v = 1
                        break
            v ^= self.INV
            if v != o[k]:
                o[k] = v
                self.sched(slot, v, t)


def _gate_dirs(units):
    d = {}
    for ins, out in units:
        for p in ins:
            d[p] = 'in'
        d[out] = 'out'
    return d


_QUAD2_PINOUT = {'1A': 1, '1B': 2, '1Y': 3, '2A': 4, '2B': 5, '2Y': 6, 'GND': 7,
                 '3Y': 8, '3A': 9, '3B': 10, '4Y': 11, '4A': 12, '4B': 13, 'VCC': 14}
_QUAD2_UNITS = tuple(((f'{i}A', f'{i}B'), f'{i}Y') for i in range(1, 5))
_HEX_PINOUT = {'1A': 1, '1Y': 2, '2A': 3, '2Y': 4, '3A': 5, '3Y': 6, 'GND': 7,
               '4Y': 8, '4A': 9, '5Y': 10, '5A': 11, '6Y': 12, '6A': 13, 'VCC': 14}
_HEX_UNITS = tuple(((f'{i}A',), f'{i}Y') for i in range(1, 7))


class HC00(_Gates):
    """Dörtlü 2-girişli NAND: nY = !(nA & nB)."""
    KIND = '74HC00'
    PINOUT = _QUAD2_PINOUT
    UNITS = _QUAD2_UNITS
    DIRS = _gate_dirs(UNITS)
    AND, INV = True, 1


class HC02(_Gates):
    """Dörtlü 2-girişli NOR: nY = !(nA | nB)."""
    KIND = '74HC02'
    PINOUT = {'1Y': 1, '1A': 2, '1B': 3, '2Y': 4, '2A': 5, '2B': 6, 'GND': 7,
              '3A': 8, '3B': 9, '3Y': 10, '4A': 11, '4B': 12, '4Y': 13, 'VCC': 14}
    UNITS = _QUAD2_UNITS
    DIRS = _gate_dirs(UNITS)
    AND, INV = False, 1


class HC04(_Gates):
    """Altılı tersleyici: nY = !nA."""
    KIND = '74HC04'
    PINOUT = _HEX_PINOUT
    UNITS = _HEX_UNITS
    DIRS = _gate_dirs(UNITS)
    AND, INV = True, 1


class HC08(_Gates):
    """Dörtlü 2-girişli AND."""
    KIND = '74HC08'
    PINOUT = _QUAD2_PINOUT
    UNITS = _QUAD2_UNITS
    DIRS = _gate_dirs(UNITS)
    AND, INV = True, 0


class HC14(_Gates):
    """Altılı Schmitt tetikli tersleyici (histerezis modellenmez)."""
    KIND = '74HC14'
    PINOUT = _HEX_PINOUT
    UNITS = _HEX_UNITS
    DIRS = _gate_dirs(UNITS)
    AND, INV = True, 1


class HC20(_Gates):
    """İkili 4-girişli NAND."""
    KIND = '74HC20'
    PINOUT = {'1A': 1, '1B': 2, '1C': 4, '1D': 5, '1Y': 6, 'GND': 7,
              '2Y': 8, '2A': 9, '2B': 10, '2C': 12, '2D': 13, 'VCC': 14}
    UNITS = tuple(((f'{i}A', f'{i}B', f'{i}C', f'{i}D'), f'{i}Y') for i in (1, 2))
    DIRS = _gate_dirs(UNITS)
    AND, INV = True, 1


class HC32(_Gates):
    """Dörtlü 2-girişli OR."""
    KIND = '74HC32'
    PINOUT = _QUAD2_PINOUT
    UNITS = _QUAD2_UNITS
    DIRS = _gate_dirs(UNITS)
    AND, INV = False, 0


# ----------------------------------------------------------------------------
# Kombinasyonel MSI
# ----------------------------------------------------------------------------
class HC138(Chip):
    """3→8 kod çözücü: E3 = 1, /E1 = /E2 = 0 iken /Y[A] = 0, diğerleri 1."""
    KIND = '74HC138'
    PINOUT = {'A0': 1, 'A1': 2, 'A2': 3, '/E1': 4, '/E2': 5, 'E3': 6, '/Y7': 7, 'GND': 8,
              '/Y6': 9, '/Y5': 10, '/Y4': 11, '/Y3': 12, '/Y2': 13, '/Y1': 14, '/Y0': 15,
              'VCC': 16}
    DIRS = _dirs(ins='A0 A1 A2 /E1 /E2 E3', outs=_seq('/Y{}', 8))
    ALIASES = {'G1': 'E3', '/G2A': '/E1', '/G2B': '/E2'}

    def setup(self):
        n = self.n
        self._a = [n['A0'], n['A1'], n['A2']]
        self._e1, self._e2, self._e3 = n['/E1'], n['/E2'], n['E3']
        self._y = [self.s[f'/Y{i}'] for i in range(8)]
        self.yo = None
        self.pa = None

    def evaluate(self):
        lv = self.lv
        a = _rd(lv, self._a)
        en = lv[self._e3] and not lv[self._e1] and not lv[self._e2]
        y = 0xFF ^ (1 << a) if en else 0xFF
        dl = self.dl['addr'] if a != self.pa else self.dl['en']
        self.pa = a
        if y != self.yo:
            self._out(self._y, self.yo, y, self.sim.now + dl)
            self.yo = y


class HC139(Chip):
    """İkili 2→4 kod çözücü: /nE = 0 iken /nY[nA] = 0."""
    KIND = '74HC139'
    PINOUT = {'/1E': 1, '1A0': 2, '1A1': 3, '/1Y0': 4, '/1Y1': 5, '/1Y2': 6, '/1Y3': 7,
              'GND': 8, '/2Y3': 9, '/2Y2': 10, '/2Y1': 11, '/2Y0': 12, '2A1': 13, '2A0': 14,
              '/2E': 15, 'VCC': 16}
    DIRS = _dirs(ins='/1E 1A0 1A1 /2E 2A0 2A1', outs=_seq('/1Y{}', 4) + ' ' + _seq('/2Y{}', 4))

    def setup(self):
        n, s = self.n, self.s
        self.units = [(n[f'/{u}E'], [n[f'{u}A0'], n[f'{u}A1']], [s[f'/{u}Y{i}'] for i in range(4)])
                      for u in (1, 2)]
        self.yo = [None, None]
        self.pa = [None, None]

    def evaluate(self):
        lv = self.lv
        for k, (e, an, ys) in enumerate(self.units):
            a = _rd(lv, an)
            y = 0xF ^ (1 << a) if not lv[e] else 0xF
            dl = self.dl['addr'] if a != self.pa[k] else self.dl['en']
            self.pa[k] = a
            if y != self.yo[k]:
                self._out(ys, self.yo[k], y, self.sim.now + dl)
                self.yo[k] = y


class HC153(Chip):
    """İkili 4→1 seçici: nY = nI[S1 S0] (/nE = 1 iken 0). S0, S1 ortak."""
    KIND = '74HC153'
    PINOUT = {'/1E': 1, 'S1': 2, '1I3': 3, '1I2': 4, '1I1': 5, '1I0': 6, '1Y': 7, 'GND': 8,
              '2Y': 9, '2I0': 10, '2I1': 11, '2I2': 12, '2I3': 13, 'S0': 14, '/2E': 15, 'VCC': 16}
    DIRS = _dirs(ins='/1E /2E S0 S1 ' + _seq('1I{}', 4) + ' ' + _seq('2I{}', 4), outs='1Y 2Y')

    def setup(self):
        n = self.n
        self._s = [n['S0'], n['S1']]
        self.units = [(n[f'/{u}E'], [n[f'{u}I{i}'] for i in range(4)], self.s[f'{u}Y'])
                      for u in (1, 2)]
        self.o = [None, None]
        self.ps = None
        self.pe = [None, None]

    def evaluate(self):
        lv = self.lv
        sel = _rd(lv, self._s)
        sel_changed = sel != self.ps
        self.ps = sel
        for k, (e, ins, slot) in enumerate(self.units):
            ev = lv[e]
            y = 0 if ev else lv[ins[sel]]
            if sel_changed:
                dl = self.dl['sel']
            elif ev != self.pe[k]:
                dl = self.dl['en']
            else:
                dl = self.dl['data']
            self.pe[k] = ev
            if y != self.o[k]:
                self.o[k] = y
                self.sched(slot, y, self.sim.now + dl)


class HC157(Chip):
    """Dörtlü 2→1 seçici: nY = S ? nI1 : nI0 (/E = 1 iken 0)."""
    KIND = '74HC157'
    PINOUT = {'S': 1, '1I0': 2, '1I1': 3, '1Y': 4, '2I0': 5, '2I1': 6, '2Y': 7, 'GND': 8,
              '3Y': 9, '3I1': 10, '3I0': 11, '4Y': 12, '4I1': 13, '4I0': 14, '/E': 15, 'VCC': 16}
    DIRS = _dirs(ins='S /E ' + ' '.join(f'{u}I0 {u}I1' for u in range(1, 5)),
                 outs='1Y 2Y 3Y 4Y')

    def setup(self):
        n = self.n
        self._sel, self._e = n['S'], n['/E']
        self._i0 = [n[f'{u}I0'] for u in range(1, 5)]
        self._i1 = [n[f'{u}I1'] for u in range(1, 5)]
        self._y = [self.s[f'{u}Y'] for u in range(1, 5)]
        self.yo = None
        self.ps = self.pe = None

    def evaluate(self):
        lv = self.lv
        sv, ev = lv[self._sel], lv[self._e]
        y = 0 if ev else _rd(lv, self._i1 if sv else self._i0)
        if sv != self.ps:
            dl = self.dl['sel']
        elif ev != self.pe:
            dl = self.dl['en']
        else:
            dl = self.dl['data']
        self.ps, self.pe = sv, ev
        if y != self.yo:
            self._out(self._y, self.yo, y, self.sim.now + dl)
            self.yo = y


class HC688(Chip):
    """8-bit eşitlik karşılaştırıcı: /P=Q = 0 ⇔ /G = 0 ve P == Q."""
    KIND = '74HC688'
    PINOUT = {'/G': 1, 'P0': 2, 'Q0': 3, 'P1': 4, 'Q1': 5, 'P2': 6, 'Q2': 7, 'P3': 8, 'Q3': 9,
              'GND': 10, 'P4': 11, 'Q4': 12, 'P5': 13, 'Q5': 14, 'P6': 15, 'Q6': 16, 'P7': 17,
              'Q7': 18, '/P=Q': 19, 'VCC': 20}
    DIRS = _dirs(ins='/G ' + _seq('P{}', 8) + ' ' + _seq('Q{}', 8), outs='/P=Q')
    ALIASES = {'/E': '/G'}

    def setup(self):
        n = self.n
        self._g = n['/G']
        self._p = [n[f'P{i}'] for i in range(8)]
        self._q = [n[f'Q{i}'] for i in range(8)]
        self._eq = self.s['/P=Q']
        self.o = None
        self.pg = None

    def evaluate(self):
        lv = self.lv
        g = lv[self._g]
        y = 0 if (not g and _rd(lv, self._p) == _rd(lv, self._q)) else 1
        dl = self.dl['en'] if g != self.pg else self.dl['data']
        self.pg = g
        if y != self.o:
            self.o = y
            self.sched(self._eq, y, self.sim.now + dl)


# ----------------------------------------------------------------------------
# Tamponlar
# ----------------------------------------------------------------------------
class HC245(Chip):
    """8-bit çift yönlü tampon: /OE = 0 iken DIR = 1 → A'dan B'ye, DIR = 0 → B'den A'ya."""
    KIND = '74HC245'
    PINOUT = {'DIR': 1, 'A0': 2, 'A1': 3, 'A2': 4, 'A3': 5, 'A4': 6, 'A5': 7, 'A6': 8, 'A7': 9,
              'GND': 10, 'B7': 11, 'B6': 12, 'B5': 13, 'B4': 14, 'B3': 15, 'B2': 16, 'B1': 17,
              'B0': 18, '/OE': 19, 'VCC': 20}
    DIRS = _dirs(ins='DIR /OE', bidirs=_seq('A{}', 8) + ' ' + _seq('B{}', 8))

    def setup(self):
        n, s = self.n, self.s
        self._oe, self._dir = n['/OE'], n['DIR']
        self._an = [n[f'A{i}'] for i in range(8)]
        self._bn = [n[f'B{i}'] for i in range(8)]
        self._as = [s[f'A{i}'] for i in range(8)]
        self._bs = [s[f'B{i}'] for i in range(8)]
        self.mode = None                  # 0 kapalı, 1 A→B, 2 B→A
        self.vo = None

    def evaluate(self):
        lv = self.lv
        t = self.sim.now
        mode = 0 if lv[self._oe] else (1 if lv[self._dir] else 2)
        if mode != self.mode:
            if self.mode == 1:
                self._off(self._bs, t + self.dl['dis'])
            elif self.mode == 2:
                self._off(self._as, t + self.dl['dis'])
            self.mode = mode
            if mode:
                v = self._rd_chk(self._an if mode == 1 else self._bn)
                self._out(self._bs if mode == 1 else self._as, None, v, t + self.dl['en'])
                self.vo = v
        elif mode:
            v = self._rd_chk(self._an if mode == 1 else self._bn)
            if v != self.vo:
                self._out(self._bs if mode == 1 else self._as, self.vo, v, t + self.dl['data'])
                self.vo = v


class HC540(Chip):
    """8-bit tersleyen 3 durumlu tampon: /OE1 = /OE2 = 0 iken /Yn = !An."""
    KIND = '74HC540'
    PINOUT = {'/OE1': 1, 'A0': 2, 'A1': 3, 'A2': 4, 'A3': 5, 'A4': 6, 'A5': 7, 'A6': 8, 'A7': 9,
              'GND': 10, '/Y7': 11, '/Y6': 12, '/Y5': 13, '/Y4': 14, '/Y3': 15, '/Y2': 16,
              '/Y1': 17, '/Y0': 18, '/OE2': 19, 'VCC': 20}
    DIRS = _dirs(ins='/OE1 /OE2 ' + _seq('A{}', 8), tris=_seq('/Y{}', 8))

    def setup(self):
        n = self.n
        self._oe1, self._oe2 = n['/OE1'], n['/OE2']
        self._a = [n[f'A{i}'] for i in range(8)]
        self._y = [self.s[f'/Y{i}'] for i in range(8)]
        self.on = False
        self.vo = None

    def evaluate(self):
        lv = self.lv
        t = self.sim.now
        on = not lv[self._oe1] and not lv[self._oe2]
        if on:
            v = _rd(lv, self._a) ^ 0xFF
            if not self.on:
                self._out(self._y, None, v, t + self.dl['en'])
            elif v != self.vo:
                self._out(self._y, self.vo, v, t + self.dl['data'])
            self.vo = v
        elif self.on:
            self._off(self._y, t + self.dl['dis'])
        self.on = on


# ----------------------------------------------------------------------------
# Flip-flop ve registerlar
# ----------------------------------------------------------------------------
class HC74(Chip):
    """İkili D flip-flop. /SD = 0 → Q = 1; /RD = 0 → Q = 0; ikisi 0 → Q = /Q = 1;
    ikisi 1 iken CP ↑ → Q = D."""
    KIND = '74HC74'
    PINOUT = {'/1RD': 1, '1D': 2, '1CP': 3, '/1SD': 4, '1Q': 5, '/1Q': 6, 'GND': 7,
              '/2Q': 8, '2Q': 9, '/2SD': 10, '2CP': 11, '2D': 12, '/2RD': 13, 'VCC': 14}
    DIRS = _dirs(ins='/1RD 1D 1CP /1SD /2RD 2D 2CP /2SD', outs='1Q /1Q 2Q /2Q')

    def setup(self):
        n, s = self.n, self.s
        self.ff = [(n[f'/{i}RD'], n[f'/{i}SD'], n[f'{i}CP'], n[f'{i}D'], s[f'{i}Q'], s[f'/{i}Q'])
                   for i in (1, 2)]
        self.q = [self.sim.power_bits(1), self.sim.power_bits(1)]
        self.pc = [None, None]
        self.tef = [NEVER, NEVER]
        self.o = [None, None]

    def _start(self):
        self.pc = [self.val[f[2]] for f in self.ff]

    def evaluate(self):
        lv, val = self.lv, self.val
        t = self.sim.now
        for i, (rd, sd, cp, dn, sq, sqn) in enumerate(self.ff):
            c = val[cp]
            edge = c == 1 and self.pc[i] == 0
            self.pc[i] = c
            r, st = lv[rd], lv[sd]
            if not r or not st:
                if not st:
                    self.q[i] = 1
                if not r:
                    self.q[i] = 0 if st else 1
                out = (1, 1) if (not r and not st) else (self.q[i], 1 - self.q[i])
                dl = self.dl['sdrd_q']
            else:
                if edge:
                    if self.chk:
                        self._chk_setup(t, (dn,), self.lim['setup'])
                        self._chk_rec(t, rd, self.lim['rec'])
                        self._chk_rec(t, sd, self.lim['rec'])
                    self.q[i] = lv[dn]
                    self.tef[i] = t
                elif self.chk and t - self.tef[i] < self.hwin and self.sim.lastch[dn] == t:
                    self.sim.violation(t, 'hold', self.ref,
                                       f'{self._pn(dn)} kenardan {t - self.tef[i]} ns sonra '
                                       f'değişti (tutma {self.lim["hold"]} ns)')
                out = (self.q[i], 1 - self.q[i])
                dl = self.dl['cp_q']
            old = self.o[i]
            if out != old:
                if old is None or out[0] != old[0]:
                    self.sched(sq, out[0], t + dl)
                if old is None or out[1] != old[1]:
                    self.sched(sqn, out[1], t + dl)
                self.o[i] = out


class HC175(Chip):
    """Dörtlü D flip-flop: /MR = 0 → Q = 0 (asenkron); CP ↑ → Q = D. /Q çıkışları da var."""
    KIND = '74HC175'
    PINOUT = {'/MR': 1, 'Q0': 2, '/Q0': 3, 'D0': 4, 'D1': 5, '/Q1': 6, 'Q1': 7, 'GND': 8,
              'CP': 9, 'Q2': 10, '/Q2': 11, 'D2': 12, 'D3': 13, '/Q3': 14, 'Q3': 15, 'VCC': 16}
    DIRS = _dirs(ins='/MR CP ' + _seq('D{}', 4), outs=_seq('Q{}', 4) + ' ' + _seq('/Q{}', 4))

    def setup(self):
        n, s = self.n, self.s
        self._mr, self._cp = n['/MR'], n['CP']
        self._d = [n[f'D{i}'] for i in range(4)]
        self._q = [s[f'Q{i}'] for i in range(4)] + [s[f'/Q{i}'] for i in range(4)]
        self.q = self.sim.power_bits(4)
        self.qo = None
        self._pc = None

    def _start(self):
        self._pc = self.val[self._cp]

    def evaluate(self):
        lv = self.lv
        t = self.sim.now
        c = self.val[self._cp]
        edge = c == 1 and self._pc == 0
        self._pc = c
        q = self.q
        if not lv[self._mr]:
            q = 0
            dl = self.dl['mr_q']
        else:
            if edge:
                if self.chk:
                    self._chk_setup(t, self._d, self.lim['setup'])
                    self._chk_rec(t, self._mr, self.lim['rec'])
                    self._arm_hold(t, self._d)
                q = _rd(lv, self._d)
            elif self.chk and t - self.te < self.hwin:
                self._chk_hold(t)
            dl = self.dl['cp_q']
        self.q = q
        both = q | (q ^ 0xF) << 4
        if both != self.qo:
            self._out(self._q, self.qo, both, t + dl)
            self.qo = both


class HC273(Chip):
    """8-bit D register: /MR = 0 → Q = 0 (asenkron); CP ↑ → Q = D."""
    KIND = '74HC273'
    PINOUT = {'/MR': 1, 'Q0': 2, 'D0': 3, 'D1': 4, 'Q1': 5, 'Q2': 6, 'D2': 7, 'D3': 8, 'Q3': 9,
              'GND': 10, 'CP': 11, 'Q4': 12, 'D4': 13, 'D5': 14, 'Q5': 15, 'Q6': 16, 'D6': 17,
              'D7': 18, 'Q7': 19, 'VCC': 20}
    DIRS = _dirs(ins='/MR CP ' + _seq('D{}', 8), outs=_seq('Q{}', 8))

    def setup(self):
        n = self.n
        self._mr, self._cp = n['/MR'], n['CP']
        self._d = [n[f'D{i}'] for i in range(8)]
        self._q = [self.s[f'Q{i}'] for i in range(8)]
        self.q = self.sim.power_bits(8)
        self.qo = None
        self._pc = None

    def _start(self):
        self._pc = self.val[self._cp]

    def evaluate(self):
        lv = self.lv
        t = self.sim.now
        c = self.val[self._cp]
        edge = c == 1 and self._pc == 0
        self._pc = c
        q = self.q
        if not lv[self._mr]:
            q = 0
            dl = self.dl['mr_q']
        else:
            if edge:
                if self.chk:
                    self._chk_setup(t, self._d, self.lim['setup'])
                    self._chk_rec(t, self._mr, self.lim['rec'])
                    self._arm_hold(t, self._d)
                q = _rd(lv, self._d)
            elif self.chk and t - self.te < self.hwin:
                self._chk_hold(t)
            dl = self.dl['cp_q']
        self.q = q
        if q != self.qo:
            self._out(self._q, self.qo, q, t + dl)
            self.qo = q


class HC377(Chip):
    """8-bit D register, senkron izinli: CP ↑ ve /E = 0 → Q = D. Reset yok."""
    KIND = '74HC377'
    PINOUT = {'/E': 1, 'Q0': 2, 'D0': 3, 'D1': 4, 'Q1': 5, 'Q2': 6, 'D2': 7, 'D3': 8, 'Q3': 9,
              'GND': 10, 'CP': 11, 'Q4': 12, 'D4': 13, 'D5': 14, 'Q5': 15, 'Q6': 16, 'D6': 17,
              'D7': 18, 'Q7': 19, 'VCC': 20}
    DIRS = _dirs(ins='/E CP ' + _seq('D{}', 8), outs=_seq('Q{}', 8))

    def setup(self):
        n = self.n
        self._e, self._cp = n['/E'], n['CP']
        self._d = [n[f'D{i}'] for i in range(8)]
        self._q = [self.s[f'Q{i}'] for i in range(8)]
        self._ehold = [self._e] + self._d
        self.q = self.sim.power_bits(8)
        self.qo = None
        self._pc = None

    def _start(self):
        self._pc = self.val[self._cp]

    def evaluate(self):
        lv = self.lv
        t = self.sim.now
        c = self.val[self._cp]
        if c == 1 and self._pc == 0:
            load = not lv[self._e]
            if self.chk:
                self._chk_setup(t, (self._e,), self.lim['su_e'])
                if load:
                    self._chk_setup(t, self._d, self.lim['su_d'])
                self._arm_hold(t, self._ehold if load else (self._e,))
            if load:
                self.q = _rd(lv, self._d)
        elif self.chk and t - self.te < self.hwin:
            self._chk_hold(t)
        self._pc = c
        if self.q != self.qo:
            self._out(self._q, self.qo, self.q, t + self.dl['cp_q'])
            self.qo = self.q


class HC161(Chip):
    """4-bit senkron sayıcı (74HC161).

    /MR = 0 → Q = 0 hemen (asenkron). CP ↑: /PE = 0 → Q = D (senkron yükleme,
    saymaya üstün); değilse CEP = CET = 1 → Q + 1; değilse tut.
    TC = CET & (Q == 15).
    """
    KIND = '74HC161'
    PINOUT = {'/MR': 1, 'CP': 2, 'D0': 3, 'D1': 4, 'D2': 5, 'D3': 6, 'CEP': 7, 'GND': 8,
              '/PE': 9, 'CET': 10, 'Q3': 11, 'Q2': 12, 'Q1': 13, 'Q0': 14, 'TC': 15, 'VCC': 16}
    DIRS = _dirs(ins='/MR CP /PE CEP CET ' + _seq('D{}', 4), outs=_seq('Q{}', 4) + ' TC')
    SYNC_CLEAR = False

    def setup(self):
        n = self.n
        self._mr, self._cp, self._pe = n['/MR'], n['CP'], n['/PE']
        self._cep, self._cet = n['CEP'], n['CET']
        self._d = [n[f'D{i}'] for i in range(4)]
        self._q = [self.s[f'Q{i}'] for i in range(4)]
        self._tc = self.s['TC']
        self._ctl = [self._pe, self._cep, self._cet] + ([self._mr] if self.SYNC_CLEAR else [])
        self.q = self.sim.power_bits(4)
        self.qo = self.tco = None
        self._pc = None

    def _start(self):
        self._pc = self.val[self._cp]

    def _edge_checks(self, t, load):
        lim = self.lim
        self._chk_setup(t, (self._pe,), lim['su_pe'])
        self._chk_setup(t, (self._cep, self._cet), lim['su_ce'])
        if load:
            self._chk_setup(t, self._d, lim['su_d'])
        if self.SYNC_CLEAR:
            self._chk_setup(t, (self._mr,), lim['su_mr'])
        else:
            self._chk_rec(t, self._mr, lim['rec'])
        self._arm_hold(t, self._ctl + self._d if load else self._ctl)

    def evaluate(self):
        lv = self.lv
        t = self.sim.now
        c = self.val[self._cp]
        edge = c == 1 and self._pc == 0
        self._pc = c
        q = self.q
        mr = lv[self._mr]
        why = 'cet'
        if not mr and not self.SYNC_CLEAR:
            q = 0
            why = 'mr'
        elif edge:
            load = not lv[self._pe]
            if self.chk:
                self._edge_checks(t, load and mr)
            if not mr:
                q = 0                                     # yalnız 163: senkron temizleme
            elif load:
                q = _rd(lv, self._d)
            elif lv[self._cep] and lv[self._cet]:
                q = (q + 1) & 15
            why = 'cp'
        elif self.chk and t - self.te < self.hwin:
            self._chk_hold(t)
        self.q = q
        dl = self.dl
        if q != self.qo:
            self._out(self._q, self.qo, q, t + (dl['mr_q'] if why == 'mr' else dl['cp_q']))
            self.qo = q
        tc = lv[self._cet] if q == 15 else 0
        if tc != self.tco:
            key = 'mr_tc' if why == 'mr' else 'cp_tc' if why == 'cp' else 'cet_tc'
            self.sched(self._tc, tc, t + dl[key])
            self.tco = tc


class HC163(HC161):
    """74HC161 ile aynı, ama /MR senkron: CP ↑ anında /MR = 0 ise Q = 0."""
    KIND = '74HC163'
    SYNC_CLEAR = True


class HC164(Chip):
    """8-bit seri giriş kaydırma registerı: CP ↑ → Q0 = DSA & DSB, Qn = Qn-1. /MR asenkron."""
    KIND = '74HC164'
    PINOUT = {'DSA': 1, 'DSB': 2, 'Q0': 3, 'Q1': 4, 'Q2': 5, 'Q3': 6, 'GND': 7, 'CP': 8,
              '/MR': 9, 'Q4': 10, 'Q5': 11, 'Q6': 12, 'Q7': 13, 'VCC': 14}
    DIRS = _dirs(ins='DSA DSB CP /MR', outs=_seq('Q{}', 8))

    def setup(self):
        n = self.n
        self._a, self._b, self._cp, self._mr = n['DSA'], n['DSB'], n['CP'], n['/MR']
        self._q = [self.s[f'Q{i}'] for i in range(8)]
        self._ds = (self._a, self._b)
        self.q = self.sim.power_bits(8)
        self.qo = None
        self._pc = None

    def _start(self):
        self._pc = self.val[self._cp]

    def evaluate(self):
        lv = self.lv
        t = self.sim.now
        c = self.val[self._cp]
        edge = c == 1 and self._pc == 0
        self._pc = c
        if not lv[self._mr]:
            self.q = 0
            dl = self.dl['mr_q']
        else:
            if edge:
                if self.chk:
                    self._chk_setup(t, self._ds, self.lim['setup'])
                    self._chk_rec(t, self._mr, self.lim['rec'])
                    self._arm_hold(t, self._ds)
                self.q = ((self.q << 1) | (lv[self._a] & lv[self._b])) & 0xFF
            elif self.chk and t - self.te < self.hwin:
                self._chk_hold(t)
            dl = self.dl['cp_q']
        if self.q != self.qo:
            self._out(self._q, self.qo, self.q, t + dl)
            self.qo = self.q


class HC166(Chip):
    """8-bit paralel/seri giriş kaydırma registerı, çıkış Q7.

    İç saat = CP OR /CE (datasheet mantık şeması); bu saatin ↑ kenarında:
    /PE = 0 → Qn = Dn (senkron yükleme), /PE = 1 → Q0 = DS, Qn = Qn-1.
    /MR = 0 → hepsi 0 (asenkron). /CE, CP düşükken yükselirse kural ihlali
    kaydedilir (ve OR saati gereği bir kenar oluşur).
    """
    KIND = '74HC166'
    PINOUT = {'DS': 1, 'D0': 2, 'D1': 3, 'D2': 4, 'D3': 5, '/CE': 6, 'CP': 7, 'GND': 8,
              '/MR': 9, 'D4': 10, 'D5': 11, 'D6': 12, 'Q7': 13, 'D7': 14, '/PE': 15, 'VCC': 16}
    DIRS = _dirs(ins='DS /CE CP /MR /PE ' + _seq('D{}', 8), outs='Q7')

    def setup(self):
        n = self.n
        self._ds, self._ce, self._cp, self._mr, self._pe = n['DS'], n['/CE'], n['CP'], n['/MR'], n['/PE']
        self._d = [n[f'D{i}'] for i in range(8)]
        self._q7 = self.s['Q7']
        self.q = self.sim.power_bits(8)
        self.o = None
        self._pk = None
        self.pce = None

    def _clk(self):
        cp, ce = self.val[self._cp], self.val[self._ce]
        if cp == 1 or ce == 1:
            return 1
        return 0 if (cp == 0 and ce == 0) else None

    def _start(self):
        self._pk = self._clk()
        self.pce = self.val[self._ce]

    def evaluate(self):
        lv = self.lv
        t = self.sim.now
        k = self._clk()
        edge = k == 1 and self._pk == 0
        self._pk = k
        ce = self.val[self._ce]
        if self.chk and ce == 1 and self.pce == 0 and self.val[self._cp] == 0:
            self._rule('/CE, CP düşükken yükseldi (datasheet: yalnız CP yüksekken); kayma oldu')
        self.pce = ce
        if not lv[self._mr]:
            self.q = 0
            dl = self.dl['mr_q']
        else:
            if edge:
                load = not lv[self._pe]
                if self.chk:
                    self._chk_setup(t, (self._pe,), self.lim['su_pe'])
                    data = self._d if load else (self._ds,)
                    self._chk_setup(t, data, self.lim['su_d'])
                    self._chk_rec(t, self._mr, self.lim['rec'])
                    self._arm_hold(t, [self._pe, *data])
                if load:
                    self.q = _rd(lv, self._d)
                else:
                    self.q = ((self.q << 1) | lv[self._ds]) & 0xFF
            elif self.chk and t - self.te < self.hwin:
                self._chk_hold(t)
            dl = self.dl['cp_q']
        y = self.q >> 7
        if y != self.o:
            self.o = y
            self.sched(self._q7, y, t + dl)


class HC191(Chip):
    """4-bit senkron yukarı/aşağı sayıcı (74HC191).

    /PL = 0 → Q = D (asenkron, seviye duyarlı). Değilse CP ↑ ve /CE = 0 iken
    D/U = 0 yukarı, D/U = 1 aşağı sayar. MAX/MIN = 1: yukarıda Q = 15, aşağıda
    Q = 0. /RC = 0 ⇔ /CE = 0, MAX/MIN = 1 ve CP = 0.
    Kural (datasheet): /CE yalnız CP yüksekken yükselmeli; D/U yalnız CP ya da
    /CE yüksekken değişmeli. Uyulmazsa 'setup' türünde kural ihlali kaydedilir.
    """
    KIND = '74HC191'
    PINOUT = {'D1': 1, 'Q1': 2, 'Q0': 3, '/CE': 4, 'D/U': 5, 'Q2': 6, 'Q3': 7, 'GND': 8,
              'D3': 9, 'D2': 10, '/PL': 11, 'MAX/MIN': 12, '/RC': 13, 'CP': 14, 'D0': 15, 'VCC': 16}
    DIRS = _dirs(ins='/PL /CE D/U CP ' + _seq('D{}', 4), outs=_seq('Q{}', 4) + ' MAX/MIN /RC')
    ALIASES = {'/CTEN': '/CE', '/LOAD': '/PL', 'CLK': 'CP', '/RCO': '/RC', 'TC': 'MAX/MIN'}

    def setup(self):
        n, s = self.n, self.s
        self._pl, self._ce, self._du, self._cp = n['/PL'], n['/CE'], n['D/U'], n['CP']
        self._d = [n[f'D{i}'] for i in range(4)]
        self._q = [s[f'Q{i}'] for i in range(4)]
        self._tc, self._rc = s['MAX/MIN'], s['/RC']
        self.q = self.sim.power_bits(4)
        self.qo = self.tco = self.rco = None
        self._pc = self.pce = self.pdu = None

    def _start(self):
        self._pc = self.val[self._cp]
        self.pce = self.lv[self._ce]
        self.pdu = self.lv[self._du]

    def evaluate(self):
        lv = self.lv
        t = self.sim.now
        c = self.val[self._cp]
        edge = c == 1 and self._pc == 0
        self._pc = c
        ce, du = lv[self._ce], lv[self._du]
        if self.chk:
            if ce == 1 and self.pce == 0 and c == 0:
                self._rule('/CE, CP düşükken yükseldi (datasheet: yalnız CP yüksekken)')
            if du != self.pdu and c == 0 and ce == 0:
                self._rule('D/U, CP ve /CE düşükken değişti (yanlış sayım riski)')
        self.pce, self.pdu = ce, du
        q = self.q
        why = None
        if not lv[self._pl]:
            q = _rd(lv, self._d)
            why = 'pl'
        elif edge:
            if self.chk:
                self._chk_setup(t, (self._ce,), self.lim['su_ce'])
                if not ce:
                    self._chk_setup(t, (self._du,), self.lim['su_du'])
                self._chk_rec(t, self._pl, self.lim['rec'])
                self._arm_hold(t, (self._ce, self._du))
            if not ce:
                q = (q - 1) & 15 if du else (q + 1) & 15
            why = 'cp'
        elif self.chk and t - self.te < self.hwin:
            self._chk_hold(t)
        self.q = q
        dl = self.dl
        if q != self.qo:
            self._out(self._q, self.qo, q, t + (dl['pl_q'] if why == 'pl' else dl['cp_q']))
            self.qo = q
        tc = int(q == 0) if du else int(q == 15)
        if tc != self.tco:
            self.sched(self._tc, tc, t + (dl['du_tc'] if why is None else dl['cp_tc']))
            self.tco = tc
        rc = 0 if (tc and not ce and c == 0) else 1
        if rc != self.rco:
            self.sched(self._rc, rc, t + dl['rc'])
            self.rco = rc


# ----------------------------------------------------------------------------
# Bellekler
# ----------------------------------------------------------------------------
class _Memory(Chip):
    """Asenkron bellek okuma zamanlaması (flash ve SRAM ortak).

    Çıkış, geçerli veri anına kadar yüksek empedans kabul edilir:
    geçerli = max(adres + tAA, /CE düşüşü + tCE, /OE düşüşü + tOE).
    Kapanış: /OE ya da /CE yükselince `hz` sonra yüksek empedans.
    (tOLZ penceresindeki belirsiz sürüş modellenmez.)
    """
    ABITS = 0
    DQ = 'DQ'

    def setup(self):
        n = self.n
        self._a = [n[f'A{i}'] for i in range(self.ABITS)]
        self._ce, self._oe, self._we = n['/CE'], n['/OE'], n['/WE']
        self._io = [n[f'{self.DQ}{i}'] for i in range(8)]
        self._ios = [self.s[f'{self.DQ}{i}'] for i in range(8)]
        self.addr = None
        self.ta = self.tce = self.toe = self.twe = NEVER
        self.pce = self.poe = self.pwe = None
        self.on = False
        self.vo = None
        self.fresh = True

    def _inputs(self, t):
        """Adres ve kontrol değişim zamanlarını günceller; (adres_değişti, ce, oe, we)."""
        lv = self.lv
        addr = _rd(lv, self._a)
        moved = addr != self.addr
        if moved:
            self.addr = addr
            self.ta = t
        ce, oe, we = lv[self._ce], lv[self._oe], lv[self._we]
        if ce != self.pce:
            self.pce = ce
            if not ce:
                self.tce = t
        if oe != self.poe:
            self.poe = oe
            if not oe:
                self.toe = t
        return moved, ce, oe, we

    def _drive(self, t, en, v, dis_delay):
        dl = self.dl
        if en:
            tv = max(self.ta + dl['acc'], self.tce + dl['ce'], self.toe + dl['oe'],
                     self.twe + dl.get('we_lz', 0), t + 1)
            if not self.on:
                self._out(self._ios, None, v, tv)
                self.on = True
            elif v != self.vo:
                self._out(self._ios, self.vo, v, tv)
            self.vo = v
        elif self.on:
            self._off(self._ios, t + dis_delay)
            self.on = False


class SST39SF010(_Memory):
    """128K×8 flash, yalnız okuma. `data`: içerik (kısaysa FF ile doldurulur).
    `speed`: 70 ya da 90 (ns). /WE düşerse 'yazma' ihlali kaydedilir."""
    KIND = 'SST39SF010'
    PINOUT = {'A16': 2, 'A15': 3, 'A12': 4, 'A7': 5, 'A6': 6, 'A5': 7, 'A4': 8, 'A3': 9,
              'A2': 10, 'A1': 11, 'A0': 12, 'DQ0': 13, 'DQ1': 14, 'DQ2': 15, 'GND': 16,
              'DQ3': 17, 'DQ4': 18, 'DQ5': 19, 'DQ6': 20, 'DQ7': 21, '/CE': 22, 'A10': 23,
              '/OE': 24, 'A11': 25, 'A9': 26, 'A8': 27, 'A13': 28, 'A14': 29, '/WE': 31,
              'VCC': 32}
    DIRS = _dirs(ins=_seq('A{}', 17) + ' /CE /OE /WE', tris=_seq('DQ{}', 8))
    ABITS = 17
    SIZE = 1 << 17

    def __init__(self, ref, pins, data=b'', speed=70, module=None, note=''):
        super().__init__(ref, pins, module, note)
        if speed not in (70, 90):
            raise ValueError('speed 70 ya da 90 olmalı')
        if len(data) > self.SIZE:
            raise ValueError(f'{ref}: imaj {len(data)} bayt, en çok {self.SIZE}')
        self.DELAY_KEY = f'SST39SF010-{speed}'
        self.data = bytearray(data) + bytearray(b'\xff' * (self.SIZE - len(data)))

    def evaluate(self):
        t = self.sim.now
        _, ce, oe, we = self._inputs(t)
        if we != self.pwe:
            if not we and self.chk:
                self.sim.violation(t, 'yazma', self.ref,
                                   '/WE düşük: flash yazma komutu modellenmez (/WE VCC\'ye bağlı olmalı)')
            self.pwe = we
        self._drive(t, not ce and not oe, self.data[self.addr], self.dl['hz'])
        self.fresh = False


class CY62256(_Memory):
    """32K×8 asenkron SRAM (-70). IO0..IO7 çift yönlü.

    Okuma: /CE = /OE = 0, /WE = 1. Yazma: /CE = /WE = 0 süresince çıkış yüksek
    empedans; /WE ya da /CE yükselince (yazmanın sonu) IO'daki veri o anki
    adrese yazılır. `data` (bytearray, 32768) dışarıdan okunup yazılabilir
    (dışarıdan yapılan değişiklik çıkışa bir giriş değişince yansır); verilmezse
    power_up'a göre sıfır ya da rastgele başlar.
    Denetimler ('yazma'): yazma sırasında adres değişmesi, adres/veri kurulumu
    (tSA, tAW, tSD) ve darbe genişliği (tPWE).
    """
    KIND = 'CY62256'
    DELAY_KEY = 'CY62256-70'
    PINOUT = {'A14': 1, 'A12': 2, 'A7': 3, 'A6': 4, 'A5': 5, 'A4': 6, 'A3': 7, 'A2': 8, 'A1': 9,
              'A0': 10, 'IO0': 11, 'IO1': 12, 'IO2': 13, 'GND': 14, 'IO3': 15, 'IO4': 16,
              'IO5': 17, 'IO6': 18, 'IO7': 19, '/CE': 20, 'A10': 21, '/OE': 22, 'A11': 23,
              'A9': 24, 'A8': 25, 'A13': 26, '/WE': 27, 'VCC': 28}
    DIRS = _dirs(ins=_seq('A{}', 15) + ' /CE /OE /WE', bidirs=_seq('IO{}', 8))
    ABITS = 15
    DQ = 'IO'
    SIZE = 1 << 15

    def __init__(self, ref, pins, data=None, module=None, note=''):
        super().__init__(ref, pins, module, note)
        if data is not None and len(data) != self.SIZE:
            raise ValueError(f'{ref}: data {self.SIZE} bayt olmalı')
        self.data = data

    def setup(self):
        super().setup()
        if self.data is None:
            self.data = (bytearray(self.SIZE) if self.sim.power_up == 'zero'
                         else bytearray(self.sim.rng.randbytes(self.SIZE)))
        self.wr = False
        self.tws = NEVER

    def evaluate(self):
        t = self.sim.now
        old = self.addr
        moved, ce, oe, we = self._inputs(t)
        chk = self.chk and not self.fresh
        if moved and self.wr and chk:
            self.sim.violation(t, 'yazma', self.ref,
                               f'yazma sırasında adres değişti ({old:04X} → {self.addr:04X})')
        we_fell = we != self.pwe and not we
        if we != self.pwe:
            if we:
                self.twe = t
            self.pwe = we
        wr = not ce and not we
        if wr and not self.wr:                            # yazma başladı
            self.wr = True
            self.tws = t
            if chk and t - self.ta < max(self.lim['sa'], 1):
                self.sim.violation(t, 'yazma', self.ref,
                                   f'adres yazma başından {t - self.ta} ns önce değişti (tSA)')
        elif not wr and self.wr:                          # yazma bitti: veriyi sakla
            self.wr = False
            v = self._rd_chk(self._io)
            if chk:
                lim = self.lim
                if t - self.tws < lim['wp']:
                    self.sim.violation(t, 'yazma', self.ref,
                                       f'yazma darbesi {t - self.tws} ns (en az {lim["wp"]} ns)')
                dt = min(t - self.sim.lastch[n] for n in self._io)
                if dt < lim['sd']:
                    self.sim.violation(t, 'yazma', self.ref,
                                       f'veri yazma sonundan {dt} ns önce değişti (tSD {lim["sd"]} ns)')
                if t - self.ta < lim['aw']:
                    self.sim.violation(t, 'yazma', self.ref,
                                       f'adres yazma sonundan {t - self.ta} ns önce değişti '
                                       f'(tAW {lim["aw"]} ns)')
            self.data[self.addr] = v
        en = not ce and not oe and we
        self._drive(t, en, self.data[self.addr],
                    self.dl['we_hz'] if (we_fell or not we) else self.dl['hz'])
        self.fresh = False


# ----------------------------------------------------------------------------
CHIP_TYPES = {c.KIND: c for c in (
    HC00, HC02, HC04, HC08, HC14, HC20, HC32, HC74, HC138, HC139, HC153, HC157,
    HC161, HC163, HC164, HC166, HC175, HC191, HC245, HC273, HC377, HC540, HC688,
    SST39SF010, CY62256)}

_TITLES = {
    '74HC00': 'dörtlü 2-girişli NAND', '74HC02': 'dörtlü 2-girişli NOR',
    '74HC04': 'altılı tersleyici', '74HC08': 'dörtlü 2-girişli AND',
    '74HC14': 'altılı Schmitt tersleyici', '74HC20': 'ikili 4-girişli NAND (3 ve 11 NC)',
    '74HC32': 'dörtlü 2-girişli OR', '74HC74': 'ikili D flip-flop, asenkron /SD /RD',
    '74HC138': '3→8 kod çözücü', '74HC139': 'ikili 2→4 kod çözücü',
    '74HC153': 'ikili 4→1 seçici', '74HC157': 'dörtlü 2→1 seçici',
    '74HC161': '4-bit sayıcı, asenkron /MR', '74HC163': '4-bit sayıcı, senkron /MR',
    '74HC164': '8-bit seri giriş kaydırma registerı',
    '74HC166': '8-bit paralel giriş kaydırma registerı',
    '74HC175': 'dörtlü D flip-flop, /MR',
    '74HC191': '4-bit yukarı/aşağı sayıcı, asenkron /PL',
    '74HC245': '8-bit çift yönlü tampon', '74HC273': '8-bit D register, asenkron /MR',
    '74HC377': '8-bit D register, senkron /E',
    '74HC540': '8-bit tersleyen 3 durumlu tampon',
    '74HC688': '8-bit eşitlik karşılaştırıcı',
    'SST39SF010': '128K×8 flash, yalnız okuma (1 ve 30 NC)',
    'CY62256': '32K×8 asenkron SRAM',
}


def pin_table(width=96):
    """Modül docstring'indeki pin tablosunu üretir (bacak sırasıyla)."""
    lines = []
    for kind, cls in CHIP_TYPES.items():
        legs = max(cls.PINOUT.values())
        legs += legs % 2
        lines.append(f'{kind} ({cls.__name__}, DIP-{legs}) {_TITLES[kind]}:')
        row = '   '
        for pin, leg in sorted(cls.PINOUT.items(), key=lambda kv: kv[1]):
            item = f' {pin}={leg}'
            if len(row) + len(item) > width:
                lines.append(row)
                row = '   '
            row += item
        lines.append(row)
    return '\n'.join(lines)
