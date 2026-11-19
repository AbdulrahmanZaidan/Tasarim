"""Ayrık parçaların davranış modelleri (M7 PS/2 için): 2N7000, 1N4148, RC zaman aşımı.

Entegre değiller: entegre sayımına girmezler (`DISCRETE = True`), Digital'e dışa
aktarılmazlar. Bacak numaraları kılıfa göredir (TO-92, DO-35).

    Q2N7000   G → D açık akaçlı: G = 1 iken D'yi 0'a çeker, değilse bırakır (pull-up ile 1).
    D1N4148   A → K: A = 1 iken K'yi 1 yapar, değilse bırakır (K'de pull-down ile diyot-VEYA).
    RCTimeout 22k / 10 nF + boşaltma diyodu + (74HC14 girişi): IN = 0 iken kondansatör
              diyotla hızla boşalır (OUT = 0); IN = 1 kesintisiz `tau` kadar kalırsa
              eşik aşılır (OUT = 1). ~0,85·RC = 190 µs (74HC14'ün VT+ ≈ %58 VCC).
"""

from .chips import DELAYS, Chip, _dirs

DELAYS.update({
    '2N7000': {'tpd': (10, 20, 'T')},          # anahtarlama (tON/tOFF, küçük yük)
    '1N4148': {'tpd': (2, 4, 'T')},            # trr 4 ns
    'RC_TIMEOUT': {'tpd': (500, 1000, 'T'),    # boşalma: KCLK'ın akıtma direnci + diyot
                   'tau': (190_000, 190_000, 'T')},   # 0,85·22k·10nF; tolerans testte ayrıca
})


class Q2N7000(Chip):
    """N kanallı MOSFET, açık akaç (TO-92: 1 = S, 2 = G, 3 = D; S = GND)."""
    KIND = '2N7000'
    DISCRETE = True
    FOOTPRINT = 'Package_TO_SOT_THT:TO-92_Inline'
    PINOUT = {'GND': 1, 'G': 2, 'D': 3}
    DIRS = _dirs(ins='G', tris='D')

    def setup(self):
        self.g, self.d = self.n['G'], self.s['D']
        self.tpd = self.dl['tpd']
        self.o = 'x'

    def evaluate(self):
        v = 0 if self.lv[self.g] else None
        if v != self.o:
            self.o = v
            self.sched(self.d, v, self.sim.now + self.tpd)


class D1N4148(Chip):
    """Sinyal diyotu, diyot-VEYA için (DO-35: 1 = K, 2 = A). K netinde pull-down olmalı."""
    KIND = '1N4148'
    DISCRETE = True
    FOOTPRINT = 'Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal'
    PINOUT = {'K': 1, 'A': 2}
    DIRS = _dirs(ins='A', tris='K')

    def setup(self):
        self.a, self.k = self.n['A'], self.s['K']
        self.tpd = self.dl['tpd']
        self.o = 'x'

    def evaluate(self):
        v = 1 if self.lv[self.a] else None
        if v != self.o:
            self.o = v
            self.sched(self.k, v, self.sim.now + self.tpd)


class RCTimeout(Chip):
    """22k + 10 nF + 1N4148 boşaltma diyodu (1 = IN, 2 = OUT, 3 = GND). OUT, 74HC14'e gider."""
    KIND = 'RC_TIMEOUT'
    DISCRETE = True
    FOOTPRINT = 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical'
    PINOUT = {'IN': 1, 'OUT': 2, 'GND': 3}
    DIRS = _dirs(ins='IN', outs='OUT')

    def setup(self):
        self.i, self.out = self.n['IN'], self.s['OUT']
        self.tpd, self.tau = self.dl['tpd'], self.dl['tau']
        self.o = None

    def _start(self):
        self.sched(self.out, 0, self.sim.now + 1)          # açılışta kondansatör boş
        self.o = 0
        self.evaluate()

    def evaluate(self):
        now = self.sim.now
        if self.lv[self.i]:
            self.sched(self.out, 1, now + self.tau)          # kesintisiz yüksekse eşik
            self.o = 1
        else:
            self.sched(self.out, 0, now + self.tpd)          # daha erken: bekleyen 1'i iptal eder
            self.o = 0


DISCRETE_TYPES = {c.KIND: c for c in (Q2N7000, D1N4148, RCTimeout)}
