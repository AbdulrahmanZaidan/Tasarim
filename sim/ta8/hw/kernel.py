"""Çip seviyesinde, gecikmeli (zamanlı) olay tabanlı lojik simülatör çekirdeği.

Netler tek bitlik ve isimlidir; değerleri 0, 1 ya da None (yüksek empedans /
yüzen). Zaman tam sayı nanosaniyedir. Çip çıkışları, girişleri değiştikten
gecikme kadar (≥ 1 ns) sonra değişir (taşıma gecikmesi).

Bir zaman adımında sıra:
  1. O ana ait bütün sürücü güncellemeleri uygulanır.
  2. Etkilenen netler çözülür: süren sürücüler aynı değerdeyse o değer; hiç
     süren yoksa pull değeri ya da None; farklı değerler varsa 'cakisma'.
  3. Değişen netlerin watch geri çağrıları çalışır. Bu anda hiçbir çip bu
     değişikliğe henüz tepki vermemiştir (commit öncesi değerler görülür).
  4. Girişi değişen her çipin evaluate()'i bir kez çağrılır; çıkışlarını
     ileriye zamanlar.

Test tezgâhı:
  sim.set(net, v)  sim.set_bus(önek, n, v)  sim.get(net)  sim.bus(önek, n)
  sim.pull(net, v)  sim.add_clock(net, yarım_periyot)  sim.stop_clock(net)
  sim.run_for(ns)  sim.run_until(t)  sim.now  sim.watch(net, fn)
  sim.last_change(net)  sim.violations  sim.summary()

İhlaller sim.violations listesine Violation(zaman, tür, çip_ref, açıklama)
olarak eklenir (4 elemanlı tuple). Türler: 'cakisma', 'yuzen', 'setup',
'hold', 'yazma'.
"""

import heapq
import random
from collections import Counter, namedtuple

NEVER = -(1 << 40)                       # "hiç değişmedi" zamanı
KINDS = ('cakisma', 'yuzen', 'setup', 'hold', 'yazma')

Violation = namedtuple('Violation', 'time kind ref desc')


class Sim:
    def __init__(self, corner='typ', checks=True, power_up='zero', seed=1,
                 max_violations=100_000):
        if corner not in ('typ', 'max'):
            raise ValueError("corner 'typ' ya da 'max' olmalı")
        if power_up not in ('zero', 'random'):
            raise ValueError("power_up 'zero' ya da 'random' olmalı")
        self.corner = corner
        self._col = 0 if corner == 'typ' else 1
        self.checks = checks
        self.power_up = power_up
        self.rng = random.Random(seed)
        self.max_violations = max_violations
        self.dropped = 0                  # sınırı aşınca kaydedilmeyen ihlal sayısı
        self.violations = []
        self.now = 0
        self.evals = 0                    # toplam evaluate() çağrısı
        self.chips = {}                   # ref → çip
        self._order = []
        # --- netler (tam sayı indeksli listeler) ---
        self.names = []
        self.index = {}
        self.val = []                     # çözülmüş değer: 0, 1, None
        self.lv = []                      # girişlerin gördüğü değer (None → 0)
        self.lastch = []                  # son değişim zamanı
        self.pullv = []
        self.drivers = []                 # net → sürücü yuvaları
        self.fanout = []                  # net → girişi bu nette olan çipler
        self.inputs = []                  # net → saf giriş pini olan ilk çipin ref'i
        self.watchers = []
        self._nmark = []
        self._cstart = []                 # çakışma başlangıcı (yoksa -1)
        self._cvi = []                    # çakışma ihlalinin indeksi
        # --- sürücü yuvaları ---
        self.d_net = []
        self.d_val = []                   # şu an sürdüğü değer
        self.d_sched = []                 # bekleyen olaylardan sonraki değer
        self.d_last = []                  # son zamanlanan olayın zamanı
        self.d_gen = []                   # iptal sayacı
        self.d_owner = []
        self.d_clock = []                 # saat yuvasıysa yarım periyot
        self._ext = {}                    # (sahip, net) → yuva
        # --- olay kuyruğu: zamanlar yığını + zaman → olay listesi ---
        self._times = []
        self._buckets = {}
        self._stamp = 0
        self._busy = False
        self._started = False
        self._starting = False
        self._deferred = []               # açılışta yüzen okunan (çip, net) çiftleri
        for name, v in (('GND', 0), ('VCC', 1)):
            n = self._net(name)
            s = self._driver(n, 'güç')
            self.d_val[s] = self.d_sched[s] = v
            self._settle(n)

    # ------------------------------------------------------------ yapı
    def _net(self, name):
        n = self.index.get(name)
        if n is None:
            n = len(self.names)
            self.index[name] = n
            self.names.append(name)
            for lst, v in ((self.val, None), (self.lv, 0), (self.lastch, NEVER),
                           (self.pullv, None), (self.inputs, None), (self._nmark, -1),
                           (self._cstart, -1), (self._cvi, -1)):
                lst.append(v)
            self.drivers.append([])
            self.fanout.append([])
            self.watchers.append([])
        return n

    def _driver(self, n, owner):
        s = len(self.d_net)
        self.d_net.append(n)
        self.d_val.append(None)
        self.d_sched.append(None)
        self.d_last.append(NEVER)
        self.d_gen.append(0)
        self.d_owner.append(owner)
        self.d_clock.append(0)
        self.drivers[n].append(s)
        return s

    def _listen(self, n, chip, pure):
        if chip not in self.fanout[n]:
            self.fanout[n].append(chip)
        if pure and self.inputs[n] is None:
            self.inputs[n] = chip.ref

    def _lookup(self, name):
        n = self.index.get(name)
        if n is None:
            raise KeyError(f'böyle bir net yok: {name!r}')
        return n

    def add(self, *chips):
        """Çip(ler)i devreye ekler; bağlanmamış giriş pini varsa hata verir."""
        if self._started:
            raise RuntimeError('simülasyon başladıktan sonra çip eklenemez')
        for c in chips:
            if c.ref in self.chips:
                raise ValueError(f'{c.ref} iki kez eklendi')
            c._attach(self)
            self.chips[c.ref] = c
            self._order.append(c)
        return chips[0] if len(chips) == 1 else chips

    def pull(self, net, value):
        """Nete pull-up (1) ya da pull-down (0) direnci ekler."""
        if self._started:
            raise RuntimeError('pull simülasyon başlamadan verilmeli')
        if value not in (0, 1):
            raise ValueError('pull değeri 0 ya da 1 olmalı')
        n = self._net(net)
        self.pullv[n] = value
        self._settle(n)

    def power_bits(self, nbits):
        """Açılışta bir kaydın içeriği: 'zero' → 0, 'random' → tohumlu rastgele."""
        return 0 if self.power_up == 'zero' else self.rng.getrandbits(nbits)

    # ------------------------------------------------------------ ihlaller
    def violation(self, t, kind, ref, desc):
        """İhlal kaydeder; indeksini (sınır aşıldıysa -1) döndürür."""
        if len(self.violations) >= self.max_violations:
            self.dropped += 1
            return -1
        self.violations.append(Violation(t, kind, ref, desc))
        return len(self.violations) - 1

    def summary(self):
        """Türe göre ihlal sayıları."""
        return Counter(v.kind for v in self.violations)

    def _conflict_begin(self, n, t):
        self._cstart[n] = t
        if self.checks:
            d_val, d_owner = self.d_val, self.d_owner
            active = [s for s in self.drivers[n] if d_val[s] is not None]
            refs = '/'.join(dict.fromkeys(d_owner[s] for s in active))
            parts = ', '.join(f'{d_owner[s]}={d_val[s]}' for s in active)
            self._cvi[n] = self.violation(t, 'cakisma', refs, f'{self.names[n]}: {parts}')

    def _conflict_end(self, n, t):
        i = self._cvi[n]
        if i >= 0:
            v = self.violations[i]
            self.violations[i] = v._replace(desc=f'{v.desc} ({t - self._cstart[n]} ns sürdü)')
        self._cstart[n] = self._cvi[n] = -1

    def _float(self, n, t):
        self.violation(t, 'yuzen', self.inputs[n],
                       f'{self.names[n]} yüzüyor (süren yok, pull yok); girişler 0 okuyor')

    # ------------------------------------------------------------ çözümleme
    def _settle(self, n):
        """Başlamadan önce bir netin değerini hemen çözer (olay üretmez)."""
        v = None
        conflict = False
        for s in self.drivers[n]:
            x = self.d_val[s]
            if x is not None:
                if v is None:
                    v = x
                elif x != v:
                    conflict = True
        if conflict:
            if self._cstart[n] < 0:
                self._conflict_begin(n, self.now)
            v = None
        else:
            if self._cstart[n] >= 0:
                self._conflict_end(n, self.now)
            if v is None:
                v = self.pullv[n]
        self.val[n] = v
        self.lv[n] = v or 0

    # ------------------------------------------------------------ zamanlama
    def _push(self, t, slot, v, g):
        b = self._buckets.get(t)
        if b is None:
            self._buckets[t] = [(slot, v, g)]
            heapq.heappush(self._times, t)
        else:
            b.append((slot, v, g))

    def _sched(self, slot, v, t):
        """Bir sürücünün t anında v olmasını zamanlar (taşıma gecikmesi).

        Aynı sürücüye, bekleyen bir olaydan daha erken bir zamana olay gelirse
        (farklı gecikmeli yollar) o sürücünün bekleyen olayları iptal edilir;
        en son karar geçerli olur (aradaki kısa darbe kaybolabilir).
        """
        if t < self.d_last[slot]:
            self.d_gen[slot] += 1
        elif self.d_sched[slot] == v:
            return
        self.d_sched[slot] = v
        self.d_last[slot] = t
        g = self.d_gen[slot]
        b = self._buckets.get(t)
        if b is None:
            self._buckets[t] = [(slot, v, g)]
            heapq.heappush(self._times, t)
        else:
            b.append((slot, v, g))

    def _process(self, t, evs):
        """Bir zaman adımı: güncellemeler → çözümleme → watch → evaluate."""
        self.now = t
        self._stamp += 1
        stamp = self._stamp
        d_val, d_gen, d_net, d_clock = self.d_val, self.d_gen, self.d_net, self.d_clock
        nmark = self._nmark
        touched = []
        for slot, v, g in evs:
            if g != d_gen[slot]:
                continue                                  # iptal edilmiş olay
            hp = d_clock[slot]
            if hp:                                        # saat: bir sonraki kenarı üret
                nv = 1 - v
                self.d_sched[slot] = nv
                self.d_last[slot] = t + hp
                self._push(t + hp, slot, nv, g)
            if d_val[slot] == v:
                continue
            d_val[slot] = v
            n = d_net[slot]
            if nmark[n] != stamp:
                nmark[n] = stamp
                touched.append(n)
        if not touched:
            return
        val, lv, lastch, pullv = self.val, self.lv, self.lastch, self.pullv
        drivers, fanout, watchers, cstart = self.drivers, self.fanout, self.watchers, self._cstart
        checks, inputs = self.checks, self.inputs
        evl = []
        wl = []
        for n in touched:
            drv = drivers[n]
            conflict = False
            if len(drv) == 1:
                v = d_val[drv[0]]
            else:
                v = None
                for s in drv:
                    x = d_val[s]
                    if x is not None:
                        if v is None:
                            v = x
                        elif x != v:
                            conflict = True
                            break
            if conflict:
                v = None
                if cstart[n] < 0:
                    self._conflict_begin(n, t)
            else:
                if cstart[n] >= 0:
                    self._conflict_end(n, t)
                if v is None:
                    v = pullv[n]
                    if v is None and checks and inputs[n] is not None and val[n] is not None:
                        self._float(n, t)
            if v == val[n]:
                continue
            val[n] = v
            lv[n] = v or 0
            lastch[n] = t
            for c in fanout[n]:
                if c._mark != stamp:
                    c._mark = stamp
                    evl.append(c)
            if watchers[n]:
                wl.append(n)
        self._busy = True
        try:
            for n in wl:
                v = val[n]
                for fn in watchers[n]:
                    fn(t, v)
            for c in evl:
                c.evaluate()
        finally:
            self._busy = False
        self.evals += len(evl)

    def _undriven(self, n, ref=None):
        """Netin (ref dışında) şu an ya da ileride süreni yok ve pull'u yok mu?"""
        if self.val[n] is not None or self.pullv[n] is not None or self._cstart[n] >= 0:
            return False
        return all(self.d_sched[s] is None or self.d_owner[s] == ref for s in self.drivers[n])

    def _start(self):
        self._started = True
        self._busy = self._starting = True
        try:
            for c in self._order:
                c._start()
            for c in self._order:
                c.evaluate()
        finally:
            self._busy = self._starting = False
        self.evals += len(self._order)
        for chip, n in self._deferred:                    # açılışta yüzen okunan pinler
            if self._undriven(n, chip.ref):
                self.violation(self.now, 'yuzen', chip.ref,
                               f'{self.names[n]} hiç sürülmüyor ve pull yok; 0 okundu')
        self._deferred.clear()
        if self.checks:                                   # hiç sürülmeyen giriş netleri
            for n, ref in enumerate(self.inputs):
                if ref is not None and self._undriven(n):
                    self.violation(self.now, 'yuzen', ref,
                                   f'{self.names[n]} hiç sürülmüyor ve pull yok; girişler 0 okuyor')

    # ------------------------------------------------------------ çalıştırma
    def run_until(self, t_end):
        if self._busy:
            raise RuntimeError('run_* bir watch geri çağrısının içinden çağrılamaz')
        if t_end < self.now:
            raise ValueError(f'geçmişe gidilemez: {t_end} < {self.now}')
        if not self._started:
            self._start()
        times, buckets, pop = self._times, self._buckets, heapq.heappop
        while times and times[0] <= t_end:
            t = pop(times)
            self._process(t, buckets.pop(t))
        self.now = t_end

    def run_for(self, ns):
        self.run_until(self.now + ns)

    # ------------------------------------------------------------ test tezgâhı
    def _ext_slot(self, n, who):
        s = self._ext.get((who, n))
        if s is None:
            s = self._ext[(who, n)] = self._driver(n, who)
        return s

    def _set_many(self, pairs, who, at):
        for _, v in pairs:
            if v not in (0, 1, None):
                raise ValueError(f'değer 0, 1 ya da None olmalı: {v!r}')
        t = self.now if at is None else at
        if t < self.now:
            raise ValueError(f'geçmişe olay konamaz: {t} < {self.now}')
        if not self._started and t == self.now:          # başlamadan: hemen uygula
            for name, v in pairs:
                n = self._net(name)
                s = self._ext_slot(n, who)
                self.d_val[s] = self.d_sched[s] = None if v is None else int(v)
                self._settle(n)
            return
        for name, v in pairs:
            s = self._ext_slot(self._net(name), who)
            self._sched(s, None if v is None else int(v), t)
        if self._started and t == self.now and not self._busy:
            self.run_until(self.now)

    def set(self, net, value, who='TB', at=None):
        """Dış sürücü (anahtar, buton, Arduino) olarak neti sürer.

        value None ise sürücü bırakılır (yüksek empedans). `who` farklı dış
        sürücüleri ayırır; `at` verilirse o mutlak zamana zamanlanır.
        """
        self._set_many([(net, value)], who, at)

    def set_bus(self, prefix, width, value, who='TB', at=None):
        """prefix0..prefix{width-1} netlerini aynı anda sürer (None: bırakır)."""
        if value is None:
            pairs = [(f'{prefix}{i}', None) for i in range(width)]
        else:
            pairs = [(f'{prefix}{i}', (value >> i) & 1) for i in range(width)]
        self._set_many(pairs, who, at)

    def add_clock(self, net, half_period_ns, start=0, offset=0):
        """Sürekli kare dalga: now + offset anında `start`, sonra her yarım periyotta ters."""
        if half_period_ns < 1:
            raise ValueError('yarım periyot ≥ 1 ns olmalı')
        n = self._net(net)
        if ('saat', n) in self._ext:
            raise ValueError(f'{net} için zaten saat var')
        s = self._ext[('saat', n)] = self._driver(n, f'saat:{net}')
        self.d_clock[s] = half_period_ns
        t0 = self.now + offset
        self.d_sched[s] = start
        self.d_last[s] = t0
        self._push(t0, s, start, self.d_gen[s])

    def stop_clock(self, net):
        """Saati o anki seviyesinde durdurur."""
        s = self._ext[('saat', self._lookup(net))]
        self.d_clock[s] = 0
        self.d_gen[s] += 1
        self.d_sched[s] = self.d_val[s]
        self.d_last[s] = self.now

    def watch(self, net, fn):
        """Net değişince fn(zaman, değer) çağrılır (çipler tepki vermeden önce)."""
        self.watchers[self._net(net)].append(fn)

    def get(self, net):
        return self.val[self._lookup(net)]

    def bus(self, prefix, width):
        """prefix0..prefix{width-1} netlerini tam sayı okur; biri None ise None."""
        v = 0
        for i in range(width):
            b = self.val[self._lookup(f'{prefix}{i}')]
            if b is None:
                return None
            v |= b << i
        return v

    def last_change(self, net):
        t = self.lastch[self._lookup(net)]
        return None if t == NEVER else t

    def drivers_of(self, net):
        """Hata ayıklama: [(sahip, şu anki değer)]."""
        return [(self.d_owner[s], self.d_val[s]) for s in self.drivers[self._lookup(net)]]
