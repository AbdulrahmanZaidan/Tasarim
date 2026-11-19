"""examples/snake.c: yılan oyunu testleri.

Oyun tacc ile derlenir ve emülatörde (Bus(vga_model=True): VRAM penceresi ve kare
zamanlaması açık) koşturulur. Beklenen her şey C kodundan bağımsız, basit bir
Python modelinden gelir (aynı kurallar, aynı LFSR). Emülatörle model hamle hamle
eşlenir: oyunun RAM'deki `hamle_sayisi` sayacı artınca hamle bitmiştir; o anda
ekran (40x30), baş, uzunluk, skor, LED'ler ve board[] gölgesinin VRAM ile aynılığı
karşılaştırılır. Tuşlar hamlelerin arasında PS/2 byte'ları olarak gönderilir
(basma + bırakma kodları).

Çalıştırma (sim/ klasöründe): py -3 -m unittest tests.test_snake
"""

import contextlib
import copy
import io
import os
import sys
import unittest
from collections import deque
from pathlib import Path
from unittest import mock

from ta8.bus import COLS, FRAME_CYCLES, ROWS, STRIDE, VWR_END, VWR_START, Bus
from ta8.emu_micro import MicroEmu
from ta8.emu_ref import RefEmu
from tacc import build, code_size

SIM = Path(__file__).resolve().parent.parent
SNAKE = SIM / 'examples' / 'snake.c'
WINDOW = VWR_END - VWR_START                    # VRAM yazma penceresi: 1312 çevrim

# ---------------------------------------------------------------------------
# Bağımsız model
# ---------------------------------------------------------------------------

SAG, ASAGI, SOL, YUKARI = 0, 1, 2, 3
ADIM = {SAG: 1, ASAGI: STRIDE, SOL: -1, YUKARI: -STRIDE}
YON_ADI = {SAG: 'sag', ASAGI: 'asagi', SOL: 'sol', YUKARI: 'yukari'}
OYNUYOR, BITTI, KAZANDI = 0, 1, 2

# PS/2 set 2 basma kodları
TUS = {
    'yukari': (0xE0, 0x75), 'asagi': (0xE0, 0x72), 'sol': (0xE0, 0x6B), 'sag': (0xE0, 0x74),
    'w': (0x1D,), 's': (0x1B,), 'a': (0x1C,), 'd': (0x23,),
    'bosluk': (0x29,), 'enter': (0x5A,), 'kp_enter': (0xE0, 0x5A), 'x': (0x22,),
}
WASD = {SAG: 'd', ASAGI: 's', SOL: 'a', YUKARI: 'w'}


def bas_birak(ad):
    """Tuşa basıp bırakma: basma kodu, sonra (E0) F0 kod."""
    make = TUS[ad]
    return make + make[:-1] + (0xF0, make[-1])


def lfsr_ileri(v):
    """16-bit Galois LFSR, maske B400 (x^16 + x^14 + x^13 + x^11 + 1)."""
    return (v >> 1) ^ (0xB400 if v & 1 else 0)


class Model:
    """Oyun kuralları, C kodundan bağımsız olarak. Konum = satır * 64 + sütun."""

    BAS_KONUM = 15 * STRIDE + 20
    KUTU = (13, 10)                     # kutunun sol üst köşesi (satır, sütun)

    def __init__(self, hiz_bas=8, uzun_max=256, lfsr=0xACE1):
        self.hiz_bas, self.uzun_max, self.lfsr = hiz_bas, uzun_max, lfsr
        self.ekran = [[' '] * COLS for _ in range(ROWS)]
        self.yaz(0, 1, 'TA-8 YILAN OYUNU')
        self.yaz(0, 30, 'SKOR')
        for c in range(COLS):
            self.ekran[1][c] = self.ekran[29][c] = '#'
        for r in range(2, 29):
            self.ekran[r][0] = self.ekran[r][39] = '#'
        self.birak = False
        self.yeniden = False
        self.hamle_sayisi = 0
        self.oyun_sayisi = 0
        self.yeni_oyun()

    # --- ekran -------------------------------------------------------------
    def yaz(self, r, c, metin):
        for i, ch in enumerate(metin):
            self.ekran[r][c + i] = ch

    def hucre(self, p):
        return self.ekran[p // STRIDE][p % STRIDE]

    def koy(self, p, ch):
        self.ekran[p // STRIDE][p % STRIDE] = ch

    def satirlar(self):
        return [''.join(r) for r in self.ekran]

    def bos_mu(self, p):
        """Yem konabilir mi: oyun alanının içinde ve boş."""
        r, c = divmod(p, STRIDE)
        return 2 <= r <= 28 and 1 <= c <= 38 and self.ekran[r][c] == ' '

    def skor_metni(self):
        return f'{self.skor % 10000:04d}'

    # --- oyun --------------------------------------------------------------
    def yem_koy(self):
        while True:
            self.lfsr = lfsr_ileri(self.lfsr)
            p = (self.lfsr ^ self.lfsr >> 8) & 0x7FF
            if self.bos_mu(p):
                break
        self.yem = p
        self.koy(p, '*')

    def yeni_oyun(self):
        for r in range(2, 29):                  # alan bomboş
            for c in range(1, 39):
                self.ekran[r][c] = ' '
        b = self.BAS_KONUM
        self.govde = deque([b - 2, b - 1, b])   # kuyruktan başa
        self.koy(b - 2, 'o')
        self.koy(b - 1, 'o')
        self.koy(b, 'O')
        self.yon = self.istek = SAG
        self.hiz, self.hiz_yem = self.hiz_bas, 0
        self.skor = 0
        self.leds = 0
        self.yaz(0, 35, self.skor_metni())
        self.durum = OYNUYOR
        self.yem_koy()
        self.oyun_sayisi += 1

    def tus(self, k):
        if k == 0xF0:
            self.birak = True
            return
        if k == 0xE0:
            return
        if self.birak:
            self.birak = False
            return
        if self.durum != OYNUYOR:
            if k in (0x29, 0x5A):
                self.yeniden = True
            return
        y = {0x75: YUKARI, 0x1D: YUKARI, 0x72: ASAGI, 0x1B: ASAGI,
             0x6B: SOL, 0x1C: SOL, 0x74: SAG, 0x23: SAG}.get(k)
        if y is not None and y ^ 2 != self.yon:
            self.istek = y

    def kutu(self, baslik):
        r, c = self.KUTU
        self.yaz(r, c, '+------------------+')
        self.yaz(r + 1, c, baslik)
        self.yaz(r + 2, c, f'|    SKOR: {self.skor_metni()}    |')
        self.yaz(r + 3, c, '|  BOSLUK / ENTER  |')
        self.yaz(r + 4, c, '+------------------+')

    def hamle(self):
        self.lfsr = lfsr_ileri(self.lfsr)
        self.yon = self.istek
        bas = self.govde[-1]
        yeni = bas + ADIM[self.yon]
        ch = self.hucre(yeni)
        buyu = ch == '*'
        if not buyu and ch != ' ' and yeni != self.govde[0]:
            self.durum = BITTI
            self.kutu('|    OYUN BITTI    |')
        else:
            if not buyu:
                self.koy(self.govde.popleft(), ' ')
            self.koy(bas, 'o')
            self.govde.append(yeni)
            self.koy(yeni, 'O')
            if buyu:
                self.skor += 1
                self.leds = self.skor & 0xFF
                self.yaz(0, 35, self.skor_metni())
                if len(self.govde) == self.uzun_max:
                    self.durum = KAZANDI
                    self.kutu('|     KAZANDIN!    |')
                else:
                    self.hiz_yem += 1
                    if self.hiz_yem == 5:
                        self.hiz_yem = 0
                        self.hiz = max(self.hiz - 1, 4)
                    self.yem_koy()
        self.hamle_sayisi += 1

    def yem_tasi(self, p):
        """Test kurulumu: yemi p'ye taşı (Oyun.yem_tasi ile aynı)."""
        self.koy(self.yem, ' ')
        self.yem = p
        self.koy(p, '*')

    def kare(self):
        """Yalnız yeniden başlatma için (hamleleri testler tek tek sürer)."""
        if self.yeniden:
            self.yeniden = False
            self.yeni_oyun()

    # --- otomatik pilot (yem yemesi gereken senaryolar için) -----------------
    def guvenli(self, p):
        ch = self.hucre(p)
        return ch in ' *' or (p == self.govde[0] and ch != '*')

    def yon_sec(self):
        """Yeme doğru, ölümcül olmayan bir yön (açgözlü)."""
        bas = self.govde[-1]
        br, bc = divmod(bas, STRIDE)
        yr, yc = divmod(self.yem, STRIDE)
        adaylar = []
        if yc != bc:
            adaylar.append(SAG if yc > bc else SOL)
        if yr != br:
            adaylar.append(ASAGI if yr > br else YUKARI)
        adaylar += [self.yon, (self.yon + 1) % 4, (self.yon + 3) % 4]
        for y in adaylar:
            if y ^ 2 != self.yon and self.guvenli(bas + ADIM[y]):
                return y
        return self.yon


# ---------------------------------------------------------------------------
# Emülatör sürücüsü
# ---------------------------------------------------------------------------

_derlenmis = {}


def derle(**defines):
    key = tuple(sorted(defines.items()))
    if key not in _derlenmis:
        _derlenmis[key] = build(SNAKE.read_text(encoding='utf-8'), str(SNAKE),
                                defines=defines or None)
    return _derlenmis[key]


class Oyun:
    """snake.c, emülatörde. Hamleler RAM'deki sayaçlarla eşlenir."""

    ADIM_CEVRIM = 2000                  # sayaçlara bu aralıkla bakılır

    def __init__(self, micro=False, vga=True, **defines):
        self.res = derle(**defines)
        self.sym = self.res.program.symbols
        self.bus = Bus(vga_model=vga)
        self.bus.load(bytes(self.res.program.image[:0x8000]))
        self.cpu = MicroEmu(self.bus) if micro else RefEmu(self.bus)
        self.kareler = []               # her hamlenin yapıldığı kare (pencere) numarası
        self.bekle(lambda: self.u8('oyun_sayisi') == 1, 60)

    # --- RAM ---------------------------------------------------------------
    def adres(self, ad):
        return self.sym['_' + ad]

    def u8(self, ad, i=0):
        return self.bus.mem[self.adres(ad) + i]

    def u16(self, ad, i=0):
        a = self.adres(ad) + 2 * i
        return self.bus.mem[a] | self.bus.mem[a + 1] << 8

    def yaz8(self, ad, v, i=0):
        self.bus.mem[self.adres(ad) + i] = v

    def yaz16(self, ad, v):
        a = self.adres(ad)
        self.bus.mem[a], self.bus.mem[a + 1] = v & 0xFF, v >> 8

    def skor_k(self):
        return bytes(self.bus.mem[self.adres('skor_k'):self.adres('skor_k') + 4]).decode()

    def yem_tasi(self, p):
        """Test kurulumu: yemi p'ye taşı (gölge, VRAM, yem_konum)."""
        b, eski = self.adres('board'), self.u16('yem_konum')
        self.bus.mem[b + eski] = self.bus.vram[eski] = 0x20
        self.yaz16('yem_konum', p)
        self.bus.mem[b + p] = self.bus.vram[p] = 0x2A

    # --- zaman -------------------------------------------------------------
    def bekle(self, kosul, en_cok_kare):
        sinir = self.cpu.cycles + en_cok_kare * FRAME_CYCLES
        while not kosul():
            if self.cpu.cycles > sinir:
                raise AssertionError(f'{en_cok_kare} karede koşul sağlanmadı')
            self.cpu.run(self.cpu.cycles + self.ADIM_CEVRIM)

    def hamle(self, n=1, en_cok_kare=10):
        """n hamle bitene kadar koştur (bir hamle en çok 8 kare sürer). Yem yiyen
        hamlede yeni yem sonraki karede konur; o da beklenir."""
        for _ in range(n):
            hedef = (self.u16('hamle_sayisi') + 1) & 0xFFFF
            self.bekle(lambda: self.u16('hamle_sayisi') == hedef, en_cok_kare)
            self.kareler.append((self.cpu.cycles - VWR_START) // FRAME_CYCLES)
            self.bekle(lambda: self.u8('yem_bekliyor') == 0, 2)

    def kareler_kos(self, n):
        self.cpu.run(self.cpu.cycles + n * FRAME_CYCLES)

    def tus(self, ad):
        self.bus.press(*bas_birak(ad))

    def ekran(self):
        return self.bus.screen()


# ---------------------------------------------------------------------------
# Testler
# ---------------------------------------------------------------------------

class SnakeTest(unittest.TestCase):
    def esit(self, oyun, model, ne=''):
        """Emülatördeki oyun modelle aynı durumda mı?"""
        self.assertEqual(oyun.ekran(), model.satirlar(), ne)
        self.assertEqual(oyun.u16('bas_konum'), model.govde[-1], ne)
        self.assertEqual(oyun.u16('uzunluk'), len(model.govde), ne)
        self.assertEqual(oyun.u16('skor'), model.skor, ne)
        self.assertEqual(oyun.skor_k(), model.skor_metni(), ne)
        self.assertEqual(oyun.bus.leds, model.leds, ne)
        self.assertEqual(oyun.u8('durum'), model.durum, ne)
        self.assertEqual(oyun.u8('hiz'), model.hiz, ne)
        self.assertEqual(oyun.u16('lfsr'), model.lfsr, ne)
        if model.durum == OYNUYOR:
            self.assertEqual(oyun.u16('yem_konum'), model.yem, ne)
            # halka tampon: kuyruktan başa yılanın konumları
            k = oyun.u8('kuyruk')
            govde = [oyun.u16('govde', (k + i) & 0xFF) for i in range(len(model.govde))]
            self.assertEqual(govde, list(model.govde), ne)
            self.assertEqual((oyun.u8('bas') - k) & 0xFF, len(model.govde) - 1, ne)
        self.golge_dogru(oyun, ne)

    def golge_dogru(self, oyun, ne=''):
        """board[]: satır 1..29, sütun 0..39'da VRAM'in aynısı; başka her yer DIS (0)."""
        b = oyun.adres('board')
        mem, vram = oyun.bus.mem, oyun.bus.vram
        for r in range(ROWS):
            for c in range(STRIDE):
                beklenen = vram[r * STRIDE + c] if 1 <= r <= 29 and c < COLS else 0
                if mem[b + r * STRIDE + c] != beklenen:
                    self.fail(f'{ne}: board[{r},{c}] = {mem[b + r * STRIDE + c]:02X}, '
                              f'beklenen {beklenen:02X}')

    def oyna(self, oyun, model, plan, ne=''):
        """plan: her hamle için basılacak tuş adları listesi (None/[] = tuş yok).
        Tuşlar bir önceki hamle bittikten sonra gönderilir."""
        for i, tuslar in enumerate(plan):
            for ad in tuslar or ():
                oyun.tus(ad)
                for k in bas_birak(ad):
                    model.tus(k)
            oyun.hamle()
            model.hamle()
            self.esit(oyun, model, f'{ne} hamle {i + 1}')

    def pilot(self, oyun, model, yem_sayisi, en_cok=400, wasd=False):
        """Otomatik pilotla `yem_sayisi` yem ye (her hamle karşılaştırılır)."""
        hedef = model.skor + yem_sayisi
        n = 0
        while model.skor < hedef and model.durum == OYNUYOR:
            y = model.yon_sec()
            tuslar = [] if y == model.yon else [WASD[y] if wasd else YON_ADI[y]]
            self.oyna(oyun, model, [tuslar], f'pilot {n}')
            self.assertNotEqual(model.durum, BITTI, 'pilot öldü')
            n += 1
            self.assertLess(n, en_cok, 'pilot yemi bulamadı')
        return n

    def kare_plani(self, oyun, model, carpmali):
        """Başı 2x2'lik bir karede döndüren plan (saat yönünde ya da tersine).
        carpmali=False: 4 hamle, yol boş ve yemsiz (kuyruğun boşalttığı hücreye girilir).
        carpmali=True: yılan kendi gövdesine çarpana kadar.
        Uygun yön yoksa yılan bir hamle ilerletilip yeniden denenir."""
        for _ in range(40):
            for donus in (1, 3):
                m = copy.deepcopy(model)
                y, plan = m.yon, []
                while len(plan) < 4 and m.durum == OYNUYOR:
                    y = (y + donus) % 4
                    hedef = m.hucre(m.govde[-1] + ADIM[y])
                    if hedef in '#*':
                        break
                    plan.append([YON_ADI[y]])
                    for k in bas_birak(YON_ADI[y]):
                        m.tus(k)
                    m.hamle()
                    if m.durum == BITTI and hedef != 'o':
                        break
                else:
                    if (m.durum == BITTI) == carpmali:
                        return plan
            y = model.yon_sec()
            self.oyna(oyun, model, [[] if y == model.yon else [YON_ADI[y]]], 'kare arama')
        self.fail('kare çizilecek yer bulunamadı')


class TestOyun(SnakeTest):
    """RefEmu + VGA modeli (pencere/kare zamanlaması açık)."""

    def test_baslangic(self):
        oyun, model = Oyun(), Model()
        self.esit(oyun, model, 'açılış')
        ekran = oyun.ekran()
        self.assertEqual(ekran[0], ' TA-8 YILAN OYUNU             SKOR 0000 ')
        self.assertEqual(ekran[1], '#' * 40)
        self.assertEqual(ekran[15][17:22], ' ooO ')
        self.assertEqual(ekran[29], '#' * 40)
        self.assertEqual(oyun.bus.leds, 0)
        # açılış (crt0 + kurulum) birkaç kare sürer, hamle yok
        self.assertEqual(oyun.u16('hamle_sayisi'), 0)

    def test_duz_ve_donusler(self):
        oyun, model = Oyun(), Model()
        plan = ([[]] * 3 + [['yukari']] + [[]] * 2 + [['sol']] + [[]] * 3 +
                [['asagi']] + [[]] * 4 + [['d']] + [[]] * 2 + [['w']] + [['a']] +
                [['s']] + [[]])
        self.oyna(oyun, model, plan, 'dönüşler')
        self.assertEqual(model.durum, OYNUYOR)

    def test_ters_yon_reddi(self):
        oyun, model = Oyun(), Model()
        p0 = model.govde[-1]
        # sağa giderken sol (ve A) yok sayılır
        self.oyna(oyun, model, [['sol'], ['a'], []], 'ters')
        self.assertEqual(oyun.u16('bas_konum'), p0 + 3)
        # bir hamle içinde yukarı + sol: sol, son hamlenin (sağ) tersi olduğu için reddedilir
        self.oyna(oyun, model, [['yukari', 'sol']], 'iki tuş')
        self.assertEqual(oyun.u16('bas_konum'), p0 + 3 - STRIDE)
        # yukarı giderken aşağı + sağ: aşağı reddedilir, sonuncu (sağ) geçerli
        self.oyna(oyun, model, [['asagi', 'sag']], 'son tuş')
        self.assertEqual(oyun.u16('bas_konum'), p0 + 4 - STRIDE)
        # sağa giderken aşağı + yukarı: ikisi de sağın tersi değil, sonuncu (yukarı) geçerli
        self.oyna(oyun, model, [['asagi', 'yukari'], []], 'son tuş 2')
        self.assertEqual(oyun.u16('bas_konum'), p0 + 4 - 3 * STRIDE)
        # tanımsız tuşlar ve sayısal tuş takımı Enter'ı oyunda etkisiz
        self.oyna(oyun, model, [['x', 'kp_enter'], ['bosluk']], 'etkisiz')
        self.assertEqual(oyun.u16('bas_konum'), p0 + 4 - 5 * STRIDE)

    def test_yem_ve_uzama(self):
        """Hızlanma (5. yemde) ve kare aralıkları TestZamanlama'da."""
        oyun, model = Oyun(), Model()
        self.pilot(oyun, model, 3)
        self.assertEqual(oyun.u16('uzunluk'), 6)
        self.assertEqual(oyun.skor_k(), '0003')
        self.assertEqual(oyun.bus.leds, 3)
        self.assertEqual(oyun.u8('hiz'), 8)
        self.assertEqual(oyun.ekran()[0][30:39], 'SKOR 0003')

    def test_skor_gecisleri(self):
        # 9999 -> 0000: elde dört basamağı da geçer (999 -> 1000'i de kapsar)
        for once, sonra in ((9, '0010'), (99, '0100'), (9999, '0000')):
            oyun, model = Oyun(), Model()
            oyun.yaz16('skor', once)
            for i, ch in enumerate(f'{once:04d}'):
                oyun.yaz8('skor_k', ord(ch), i)
            model.skor = once
            self.pilot(oyun, model, 1, wasd=True)
            self.assertEqual(oyun.skor_k(), sonra)
            self.assertEqual(oyun.ekran()[0][35:39], sonra)
            self.assertEqual(oyun.bus.leds, (once + 1) & 0xFF)

    def test_duvara_carpma_ve_yeniden(self):
        oyun, model = Oyun(), Model()
        n = 0
        while model.durum == OYNUYOR:                  # dümdüz sağa: sütun 38'den sonra duvar
            self.oyna(oyun, model, [[]], 'sağa')
            n += 1
        self.assertEqual(model.durum, BITTI)
        ekran = oyun.ekran()
        self.assertEqual(ekran[14][10:30], '|    OYUN BITTI    |')
        self.assertEqual(ekran[15][10:30], f'|    SKOR: {model.skor_metni()}    |')
        self.assertEqual(ekran[16][10:30], '|  BOSLUK / ENTER  |')
        self.assertEqual(oyun.u16('bas_konum') % STRIDE, 38)
        # oyun durdu: kareler geçer, hamle yok; yön tuşları ve bırakma kodu etkisiz
        hs = oyun.u16('hamle_sayisi')
        for ad in ('yukari', 'w', 'x'):
            oyun.tus(ad)
            for k in bas_birak(ad):
                model.tus(k)
        oyun.kareler_kos(20)
        self.assertEqual(oyun.u16('hamle_sayisi'), hs)
        self.esit(oyun, model, 'bitti')
        # boşlukla yeniden: alan temiz, yılan baştan, yem LFSR'nin devamından
        oyun.tus('bosluk')
        for k in bas_birak('bosluk'):
            model.tus(k)
        model.kare()
        oyun.bekle(lambda: oyun.u8('oyun_sayisi') == 2, 5)
        self.esit(oyun, model, 'yeniden')
        self.assertEqual(oyun.skor_k(), '0000')
        self.assertEqual(oyun.bus.leds, 0)
        self.oyna(oyun, model, [['asagi'], [], ['sol'], []], 'ikinci oyun')

    def test_kendine_carpma_ve_enter(self):
        oyun, model = Oyun(), Model()
        self.pilot(oyun, model, 1)
        # uzunluk 4: 2x2 karede dönmek serbest (baş, kuyruğun o hamlede boşalttığı hücreye girer)
        plan = self.kare_plani(oyun, model, carpmali=False)
        self.oyna(oyun, model, plan + plan, 'kuyruğu kovala')
        self.assertEqual(model.durum, OYNUYOR)
        self.assertEqual(len(model.govde), 4)
        # uzunluk 6: aynı kare artık gövdeye çarpar
        self.pilot(oyun, model, 2)
        plan = self.kare_plani(oyun, model, carpmali=True)
        self.oyna(oyun, model, plan, 'çarpma')
        self.assertEqual(model.durum, BITTI)
        self.assertEqual(oyun.ekran()[14][10:30], '|    OYUN BITTI    |')
        oyun.tus('enter')
        for k in bas_birak('enter'):
            model.tus(k)
        model.kare()
        oyun.bekle(lambda: oyun.u8('oyun_sayisi') == 2, 5)
        self.esit(oyun, model, 'enter ile yeniden')

    def test_kazanma(self):
        """UZUN_MAX = 5 ile derlenince 2 yemde kazanılır."""
        oyun, model = Oyun(UZUN_MAX=5), Model(uzun_max=5)
        self.pilot(oyun, model, 2)
        self.assertEqual(model.durum, KAZANDI)
        self.assertEqual(oyun.ekran()[14][10:30], '|     KAZANDIN!    |')
        self.assertEqual(oyun.ekran()[15][10:30], '|    SKOR: 0002    |')
        oyun.tus('enter')
        for k in bas_birak('enter'):
            model.tus(k)
        model.kare()
        oyun.bekle(lambda: oyun.u8('oyun_sayisi') == 2, 5)
        self.esit(oyun, model, 'kazandıktan sonra yeniden')


class TestZamanlama(SnakeTest):
    def pencere_olc(self, oyun, kosul, kayit, vram_son):
        """kosul() sağlanana kadar koşturur. Her karede pencerenin açıldığı bölgeyi
        komut komut yürütür: hamle ve yem_ara çağrılarının süresi kayit'e
        (ad, çevrim), o karedeki son VRAM yazmasının pencere açıldıktan kaç çevrim
        sonra olduğu vram_son'a eklenir."""
        girisler = {oyun.sym['_hamle']: 'hamle', oyun.sym['_yem_ara']: 'yem_ara'}
        cpu, bus = oyun.cpu, oyun.bus
        son = [None]
        yaz = bus.write

        def izle(addr, v):
            if 0xF000 <= addr < 0xF800:
                son[0] = cpu.cycles
            yaz(addr, v)
        bus.write = izle
        try:
            while not kosul():
                kare = (cpu.cycles - VWR_START) // FRAME_CYCLES + 1
                pencere = VWR_START + kare * FRAME_CYCLES
                cpu.run(pencere - 100)          # bu çağrılar yalnız pencere açılınca başlar
                son[0] = None
                yigin = []                      # (ad, başlangıç, sp)
                while cpu.cycles < pencere + 3000 or yigin:
                    ad = girisler.get(cpu.pc)
                    # aynı sp ile girişe dönmek çağrı değil, döngüdür (yem_ara `do {` ile başlar)
                    if ad is not None and not (yigin and yigin[-1][2] == cpu.sp):
                        yigin.append((ad, cpu.cycles, cpu.sp))
                    cpu.instruction()
                    # RET, CALL'ın 2 byte'ını geri alınca çağrı biter
                    while yigin and cpu.sp == (yigin[-1][2] + 2) & 0xFF:
                        ad, c0, _ = yigin.pop()
                        kayit.append((ad, cpu.cycles - c0))
                if son[0] is not None:
                    vram_son.append(son[0] - pencere)
        finally:
            bus.write = yaz

    def test_kare_sayisi_ve_hamle_suresi(self):
        oyun, model = Oyun(), Model()
        # 5. yemde hız 8 -> 7 kare: o hamleye kadar aralıklar 8, sonra 7. Süre için
        # 4 yem yenmiş sayılır (RAM'e ve modele hiz_yem = 4), 5. yem pilotla yenir.
        oyun.yaz8('hiz_yem', 4)
        model.hiz_yem = 4
        self.pilot(oyun, model, 1)
        k5 = len(oyun.kareler) - 1                     # 5. yemi yiyen hamle
        for _ in range(3):                             # pilotun yönettiği 3 hamle daha
            y = model.yon_sec()
            self.oyna(oyun, model, [[] if y == model.yon else [YON_ADI[y]]], 'hızlı')
        aralik = [b - a for a, b in zip(oyun.kareler, oyun.kareler[1:])]
        self.assertEqual(aralik, [8] * k5 + [7] * 3)
        self.assertEqual(oyun.u8('hiz'), 7)
        # ölçüm: pilotun yönlendirdiği 3 yemlik bölümde her hamle ve yem araması
        olcum = {'hamle': [], 'yiyen hamle (arama dahil)': [], 'yem_ara': []}
        vram_son = []
        hedef = model.skor + 3
        while model.skor < hedef:
            y = model.yon_sec()
            if y != model.yon:
                oyun.tus(YON_ADI[y])
                for k in bas_birak(YON_ADI[y]):
                    model.tus(k)
            n = oyun.u16('hamle_sayisi') + 1
            kayit = []
            self.pencere_olc(oyun, lambda: oyun.u16('hamle_sayisi') == n and
                             oyun.u8('yem_bekliyor') == 0, kayit, vram_son)
            skor = model.skor
            model.hamle()
            self.esit(oyun, model, 'ölçüm')
            for ad, cevrim in kayit:
                if ad == 'hamle' and model.skor != skor:
                    ad = 'yiyen hamle (arama dahil)'
                olcum[ad].append(cevrim)
        satirlar = [f'{ad}: {min(v)}-{max(v)} çevrim (ort. {sum(v) / len(v):.0f}, {len(v)} kez)'
                    for ad, v in olcum.items()]
        print('\n  ' + '; '.join(satirlar) + f'; son VRAM yazması pencere açıldıktan en geç '
              f'{max(vram_son)} çevrim sonra (pencere {WINDOW} çevrim)', file=sys.stderr)
        self.assertLess(max(olcum['hamle']), 700)
        self.assertLess(max(vram_son), WINDOW - 300, 'VRAM yazmaları pencereye rahat sığmıyor')

    def test_vga_yok(self):
        """VGA kartı yokken (VWIN hep 1) oyun yine ilerler: tur sayarak kare."""
        oyun, model = Oyun(vga=False), Model()
        for i, tuslar in enumerate([[], ['asagi'], []]):
            for ad in tuslar:
                oyun.tus(ad)
                for k in bas_birak(ad):
                    model.tus(k)
            oyun.hamle(en_cok_kare=20)
            model.hamle()
            self.esit(oyun, model, f'VGA yok, hamle {i + 1}')
        c0 = oyun.cpu.cycles
        oyun.hamle(8, en_cok_kare=20)
        kare_basina = (oyun.cpu.cycles - c0) / 8 / 8
        self.assertTrue(10_000 < kare_basina < 25_000, kare_basina)


class TestMikroadim(SnakeTest):
    def test_micro_vga_ayni_ekran(self):
        """MicroEmu (gerçek mikrokod, VRAM'e pencere dışında yazan CPU bekletilir)
        ve RefEmu aynı senaryoda aynı ekranı, aynı kare zamanlamasıyla verir."""
        ref, mic, model = Oyun(), Oyun(micro=True), Model()
        self.assertEqual(mic.ekran(), ref.ekran())
        plan = [[], ['yukari'], [], ['sol'], ['asagi'], []]
        for i, tuslar in enumerate(plan):
            for ad in tuslar:
                ref.tus(ad)
                mic.tus(ad)
                for k in bas_birak(ad):
                    model.tus(k)
            ref.hamle()
            mic.hamle()
            model.hamle()
            self.esit(mic, model, f'micro hamle {i + 1}')
            self.assertEqual(mic.ekran(), ref.ekran())
        # açılış MicroEmu'da daha uzun sürer (bekletmeler); hamle aralıkları aynı
        aralik = [[b - a for a, b in zip(o.kareler, o.kareler[1:])] for o in (ref, mic)]
        self.assertEqual(aralik[1], aralik[0])
        self.assertEqual(set(aralik[0]), {8})
        # açılıştan sonra hamleler (yem yiyen dahil) pencerenin içinde biter: CPU hiç
        # bekletilmez. Yem, süre için başın iki önüne taşınır (RAM + VRAM + model).
        self.assertGreater(mic.cpu.stall_cycles, 0)        # açılışta (crt0, kurulum) bekler
        dur = mic.cpu.stall_cycles
        hedef = model.govde[-1] + 2 * ADIM[model.yon]
        for o in (ref, mic):
            o.yem_tasi(hedef)
        model.yem_tasi(hedef)
        for i in range(3):
            ref.hamle()
            mic.hamle()
            model.hamle()
            self.esit(mic, model, f'micro yem hamle {i + 1}')
            self.assertEqual(mic.ekran(), ref.ekran())
        self.assertEqual(model.skor, 1)
        self.assertEqual(mic.cpu.stall_cycles, dur)

    def test_micro_bitti_ve_yeniden(self):
        """Oyun bitti kutusu ve yeniden başlatma çok VRAM yazar; MicroEmu'da pencere
        dışındakiler bekletilir, sonuç yine aynı. Süre için HIZ_BAS=1 (her karede hamle)."""
        ref, mic, model = Oyun(HIZ_BAS=1), Oyun(micro=True, HIZ_BAS=1), Model(hiz_bas=1)
        # İlk hamle: açılışta `pencere` 0'dır; MicroEmu'da kurulumun son VRAM yazması
        # pencereye kadar bekletildiği için ilk kare hemen sayılır. İkisi de 1. hamleden
        # sonra eşlenir; tuş ve yem taşıma ondan sonra (hamleler arası 1 kare).
        for o in (ref, mic):
            o.bekle(lambda: o.u16('hamle_sayisi') == 1, 5)
        model.hamle()
        kenar = 27 * STRIDE + 3                            # yem yoldan çekilir (sol alt)
        for o in (ref, mic, model):
            o.yem_tasi(kenar)
        self.esit(mic, model, 'micro ilk hamle')
        for o in (ref, mic):
            o.tus('yukari')
        for k in bas_birak('yukari'):
            model.tus(k)
        while model.durum == OYNUYOR:                      # yukarı, üst duvara
            for o in (ref, mic):
                o.hamle()
            model.hamle()
            self.esit(mic, model, 'micro yukarı')
            self.assertEqual(mic.ekran(), ref.ekran())
        self.assertEqual(mic.ekran()[14][10:30], '|    OYUN BITTI    |')
        dur = mic.cpu.stall_cycles
        for o in (ref, mic):
            o.tus('bosluk')
        for k in bas_birak('bosluk'):
            model.tus(k)
        model.kare()
        for o in (ref, mic):
            o.bekle(lambda: o.u8('oyun_sayisi') == 2, 10)
        self.esit(mic, model, 'micro yeniden')
        self.assertEqual(mic.ekran(), ref.ekran())
        self.assertGreater(mic.cpu.stall_cycles, dur)       # kutu/temizlik bekletildi
        for o in (ref, mic, model):
            o.yem_tasi(kenar)
        for _ in range(3):
            for o in (ref, mic):
                o.hamle()
            model.hamle()
            self.esit(mic, model, 'micro ikinci oyun')


class TestBoyut(unittest.TestCase):
    def test_rom_ram(self):
        res = derle()
        rom = code_size(res.program)
        ram = res.ram_end - 0x8020
        print(f'\n  snake.c: ROM {rom} byte, RAM {ram} byte (8020-{res.ram_end - 1:04X})',
              file=sys.stderr)
        self.assertLess(rom, 4096)
        self.assertLess(res.ram_end, 0xEF00)


def play_modulu():
    if str(SIM) not in sys.path:
        sys.path.insert(0, str(SIM))
    import play
    return play


class SahteKonsol(io.StringIO):
    def isatty(self):
        return True


class SahteMsvcrt:
    def __init__(self):
        self.buf = deque()

    def kbhit(self):
        return bool(self.buf)

    def getwch(self):
        return self.buf.popleft()


class TestPlay(unittest.TestCase):
    def test_demo_sonlu(self):
        """--demo --frames: senaryo 232. karede 2. yemi yer (play.py'deki DEMO yorumu)."""
        play = play_modulu()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = play.main([str(SNAKE), '--demo', '--frames', '240', '--speed', '0'])
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn('| TA-8 YILAN OYUNU             SKOR 0002 |', out)
        self.assertIn('LED ......*. ($02)   kare 240', out)
        self.assertNotIn('OYUN BITTI', out)

    def test_scan_codes(self):
        play = play_modulu()
        self.assertEqual(play.scan_codes('sag'), (0xE0, 0x74, 0xE0, 0xF0, 0x74))
        self.assertEqual(play.scan_codes('W'), (0x1D, 0xF0, 0x1D))
        self.assertEqual(play.scan_codes(' '), (0x29, 0xF0, 0x29))
        self.assertEqual(play.scan_codes('\r'), (0x5A, 0xF0, 0x5A))
        self.assertEqual(play.scan_codes('enter'), (0x5A, 0xF0, 0x5A))
        self.assertIsNone(play.scan_codes('~'))

    def test_etkilesimli_kip_sahte_konsol(self):
        """Etkileşimli yol (msvcrt + ANSI) sahte konsolla: 40. karede yukarı ok
        (msvcrt '\\xe0' 'H'), 90. karede 'a', 150. karede Esc. Son ekran, aynı scan
        code'ların aynı karelerde doğrudan gönderildiği bir koşuyla aynı olmalı."""
        play = play_modulu()
        betik = {40: '\xe0H', 90: 'a', 150: '\x1b'}

        class BetikKlavye(play.Keyboard):
            def __init__(self):
                self.msvcrt = SahteMsvcrt()
                self.kare = 0

            def read(self):
                self.msvcrt.buf.extend(betik.get(self.kare, ''))
                self.kare += 1
                return super().read()

        out = SahteKonsol()
        stdin = SahteKonsol()
        eski_klavye, play.Keyboard = play.Keyboard, BetikKlavye
        eski_stdin, sys.stdin = sys.stdin, stdin
        try:
            with contextlib.redirect_stdout(out), mock.patch.object(
                    play.shutil, 'get_terminal_size', return_value=os.terminal_size((120, 50))):
                rc = play.main([str(SNAKE), '--speed', '0'])
        finally:
            play.Keyboard, sys.stdin = eski_klavye, eski_stdin
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn('\x1b[?25l', text)                   # imleç gizlendi
        self.assertTrue(text.rstrip().endswith('\x1b[?25h'))  # ve geri geldi
        son = text[text.rindex('\x1b[H'):].split('\n')
        ekran = [l.replace('\x1b[K', '')[1:-1] for l in son[1:31]]
        self.assertIn('kare 150', son[32])
        # aynı tuşlar, aynı karelerde, doğrudan
        res = derle()
        bus = Bus(vga_model=True)
        bus.load(bytes(res.program.image[:0x8000]))
        cpu = RefEmu(bus)
        for kare in range(150):
            if kare == 40:
                bus.press(*bas_birak('yukari'))
            if kare == 90:
                bus.press(*bas_birak('a'))
            cpu.run((cpu.cycles // FRAME_CYCLES + 1) * FRAME_CYCLES)
        self.assertEqual(ekran, bus.screen())
        bas = res.program.symbols['_bas_konum']
        satir = (bus.mem[bas] | bus.mem[bas + 1] << 8) // STRIDE
        self.assertLess(satir, 15)                          # yukarı döndü

    def test_pencere_boyu(self):
        """Kısa terminalde görünüm kısalır: 35 / 33 / 31 / 30 satır; ekran hep içinde."""
        play = play_modulu()
        res = derle()
        bus = Bus(vga_model=True)
        bus.load(bytes(res.program.image[:0x8000]))
        cpu = RefEmu(bus)
        cpu.run(10 * FRAME_CYCLES)
        for rows, n in ((50, 35), (35, 35), (34, 33), (33, 33), (32, 31), (31, 31), (30, 30),
                        (25, 30)):
            lines = play.frame_text(bus, 10, cpu, 1.0, 'bilgi', 'yardım', rows)
            self.assertEqual(len(lines), n, rows)
            self.assertIn('|' + bus.screen()[0] + '|', lines)
            self.assertEqual(any(l.startswith(' LED ') for l in lines), n > 30, rows)

    def test_asm_programi(self):
        play = play_modulu()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = play.main([str(SIM / 'examples' / 'merhaba.asm'), '--frames', '5', '--speed', '0'])
        self.assertEqual(rc, 0)
        self.assertIn('MERHABA', buf.getvalue())
        self.assertIn('HALT', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
