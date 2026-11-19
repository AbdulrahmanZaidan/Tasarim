"""examples/acilis_testi.asm: açılış kendi kendini testi (POST).

Sağlam makinede iki emülatörde de "TEST TAMAM" ve aynı çevrim sayısı; sonra hata
enjeksiyonu: bozuk RAM (Bus alt sınıfları), bozuk ALU tablosu ve bozuk mikrokod imajı
(MicroEmu) ile testin hatayı gerçekten yakaladığı gösterilir.

Çalıştırma (sim/ klasöründen):  py -m unittest tests.test_acilis -v
Kapsam özetleri (-v ile) stdout'a yazılır.
"""

import unittest
from pathlib import Path

from ta8 import alu, asm, isa, microcode
from ta8.bus import Bus
from ta8.emu_micro import MicroEmu
from ta8.emu_ref import RefEmu

SIM = Path(__file__).resolve().parent.parent
SRC = SIM / 'examples' / 'acilis_testi.asm'
PROG = asm.assemble(SRC.read_text(encoding='utf-8'), filename=str(SRC))
ROMS = microcode.build()
ALU = alu.build_tables()

BASARI = 0x3C
TAM_LIMIT = 3_000_000          # tam test ~1,5 M çevrim
KISA_LIMIT = 300_000           # SW0 = 1 (3b atlanır) ~64 bin çevrim


def makine(micro=False, bus=None, dip=0, roms=None, tables=None, vga=False):
    bus = bus if bus is not None else Bus(vga_model=vga)
    bus.load(PROG.image[:0x8000])
    bus.dip = dip
    if micro:
        return MicroEmu(bus, roms or ROMS, tables or ALU)
    return RefEmu(bus)


def calistir(micro=False, limit=TAM_LIMIT, **kw):
    cpu = makine(micro, **kw)
    cpu.run(limit)
    return cpu


def basarili(cpu):
    return cpu.halted and cpu.bus.leds == BASARI


def ozet(cpu):
    """Bir koşunun sonucu: 'TAMAM', 'HATA n' (LED E0+n), 'takıldı LED=xx' ya da 'durdu LED=xx'."""
    led = cpu.bus.leds
    if cpu.halted and led == BASARI:
        return 'TAMAM'
    if cpu.halted and 0xE1 <= led <= 0xE6:
        return f'HATA {led & 0x0F}'
    return f'{"durdu" if cpu.halted else "takıldı"} LED={led:02X}'


# ---------------------------------------------------------------------------
# Bozuk RAM modelleri
# ---------------------------------------------------------------------------
class YapisikBitBus(Bus):
    """Bir hücrenin bir biti hep 0 ya da hep 1 okunur."""

    def __init__(self, adres, bit, deger, **kw):
        super().__init__(**kw)
        self.adres, self.maske, self.deger = adres, 1 << bit, deger

    def read(self, addr):
        v = super().read(addr)
        if addr == self.adres:
            v = v | self.maske if self.deger else v & ~self.maske
        return v


class TakmaAdBus(Bus):
    """İki adres aynı hücreye düşer (adres hattı kısa devresinin sonucu)."""

    def __init__(self, gercek, takma, **kw):
        super().__init__(**kw)
        self.gercek, self.takma = gercek, takma

    def _map(self, addr):
        return self.gercek if addr == self.takma else addr

    def read(self, addr):
        return super().read(self._map(addr))

    def write(self, addr, value):
        super().write(self._map(addr), value)


class AdresHattiBus(Bus):
    """RAM çipinin bir adres hattı yapışık (0 ya da 1): 8000–EFFF içinde."""

    def __init__(self, hat, deger, **kw):
        super().__init__(**kw)
        self.maske, self.deger = 1 << hat, deger

    def _map(self, addr):
        if 0x8000 <= addr < 0xF000:
            return addr | self.maske if self.deger else addr & ~self.maske
        return addr

    def read(self, addr):
        return super().read(self._map(addr))

    def write(self, addr, value):
        super().write(self._map(addr), value)


class TestSaglam(unittest.TestCase):
    def test_iki_emulator_ayni(self):
        ref = calistir(False)
        mic = calistir(True)
        for cpu in (ref, mic):
            name = type(cpu).__name__
            self.assertTrue(basarili(cpu), f'{name}: {ozet(cpu)}')
            rows = cpu.bus.screen()
            self.assertEqual(rows[27].strip('| '), 'TEST TAMAM', name)
            self.assertIn('3 RAM 8000-EFFF .......... TAMAM', rows[5])
            self.assertIn('HEP ACIK', rows[8])           # VGA modeli kapalı: pencere hep açık
            self.assertEqual(rows[0], '0123456789' * 4)
            self.assertEqual(rows[29], '0123456789' * 4)
            self.assertTrue(all(r[0] == '|' and r[39] == '|' for r in rows[1:29]))
            self.assertEqual(rows[11][4:36], ''.join(map(chr, range(0x20, 0x40))))
        self.assertEqual(ref.cycles, mic.cycles)
        print(f'\n  POST: {ref.cycles} çevrim = {ref.cycles / 1e6:.2f} s @ 1 MHz; ROM: '
              + ', '.join(f'{s:04X}+{n}' for s, n in PROG.ranges()) + ' byte')

    def test_vga_modeli_acik(self):
        for micro in (False, True):
            cpu = calistir(micro, vga=True)
            self.assertTrue(basarili(cpu), ozet(cpu))
            rows = cpu.bus.screen()
            self.assertIn('6 VRAM PENCERESI ......... TAMAM', rows[8])
            self.assertEqual(rows[27].strip('| '), 'TEST TAMAM')
            if micro:
                self.assertGreater(cpu.stall_cycles, 0)

    def test_pencere_hic_acilmiyor(self):
        """b6 bir an 0 görülüp hiç 1 olmazsa $E6; VRAM'e hiç yazılmaz (WAIT'te kalmamak için)."""
        class KapaliBus(Bus):
            def vwr(self):
                return 0

        cpu = calistir(False, bus=KapaliBus(), dip=1, limit=KISA_LIMIT)
        self.assertEqual(ozet(cpu), 'HATA 6')
        self.assertFalse(any(cpu.bus.vram))

    def test_sw0_programa_atlar(self):
        user = asm.assemble('.org $8000\nLDA #$77\nSTA $F800\nHALT\n')
        bus = Bus()
        bus.load(bytes(user.image[0x8000:0x8010]), 0x8000)
        for a in range(0x8010, 0xEF00, 97):            # yüklenmiş programın geri kalanı
            bus.mem[a] = (a * 7) & 0xFF
        before = bytes(bus.mem[0x8000:0xEF00])
        for micro in (False, True):
            b = Bus()
            b.mem[:] = bus.mem
            cpu = calistir(micro, bus=b, dip=1, limit=KISA_LIMIT)
            self.assertTrue(cpu.halted)
            self.assertEqual(b.leds, 0x77, 'yüklenen program çalışmadı')
            self.assertEqual(cpu.pc, 0x8006)              # HALT 8005'te
            self.assertEqual(bytes(b.mem[0x8000:0xEF00]), before, '8000–EEFF bozuldu')
            rows = b.screen()
            self.assertIn('3 RAM EF00-EFFF (SW0=1) .. TAMAM', rows[5])
            self.assertEqual(rows[27].strip('| '), 'TEST TAMAM')


class TestRamHatalari(unittest.TestCase):
    def kos(self, bus, dip=0):
        cpu = calistir(False, bus=bus, dip=dip)
        self.assertEqual(ozet(cpu), 'HATA 3', bus.screen()[0])
        return cpu

    def adres_dogru(self, cpu, adres):
        self.assertEqual(cpu.x, adres)
        self.assertEqual(cpu.a, adres >> 8)
        self.assertEqual(cpu.bus.screen()[0][:17], f'HATA 3 ADRES {adres:04X}')

    def test_yapisik_bit(self):
        # (adres, bit, değer): ilk ikisi M1'de (d0 = H), son ikisi M2'de (d1 = ~H) yakalanır
        for adres, bit, deger in [(0xC155, 7, 0), (0xB2F0, 0, 1), (0x9A3C, 2, 0), (0x8001, 6, 1)]:
            with self.subTest(adres=hex(adres), bit=bit, deger=deger):
                self.adres_dogru(self.kos(YapisikBitBus(adres, bit, deger)), adres)

    def test_yigin_sayfasi(self):
        for adres, bit, deger, dip in [(0xEF80, 6, 0, 0), (0xEF00, 0, 1, 0), (0xEFFF, 3, 0, 1)]:
            with self.subTest(adres=hex(adres), dip=dip):
                self.adres_dogru(self.kos(YapisikBitBus(adres, bit, deger), dip), adres)

    def test_iki_adres_ayni_hucre(self):
        for gercek, takma in [(0x8123, 0x8133), (0xA000, 0xA800), (0xEF10, 0xEF11), (0x8000, 0xEEFF)]:
            with self.subTest(gercek=hex(gercek), takma=hex(takma)):
                cpu = self.kos(TakmaAdBus(gercek, takma))
                self.assertIn(cpu.x, (gercek, takma))

    def test_adres_hatti(self):
        for hat in range(15):
            for deger in (0, 1):
                with self.subTest(hat=hat, deger=deger):
                    self.kos(AdresHattiBus(hat, deger))


# ---------------------------------------------------------------------------
# ALU tablosu bozma
# ---------------------------------------------------------------------------
class KayitliMicro(MicroEmu):
    """ALU sonucunun kullanıldığı (A'ya yazılan ya da FL'li) her çevrimin tablo adreslerini
    aşamayla (o anki LED) birlikte kaydeder."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.kayit = {}                 # op -> [(aşama, lo_adr, hi_adr)]

    def cycle(self):
        cw = self.control_word()
        if (cw >> 5) & 7 == 2 or cw & isa.FL:
            op = (cw >> 8) & 31
            dsrc, asrc = (cw >> 2) & 7, cw & 3
            ab = (self.pc, self.ar, self.x, isa.STACK_PAGE | self.sp)[asrc]
            db = {1: None, 2: self.a, 3: self.pc & 0xFF, 4: self.pc >> 8}.get(dsrc, 0)
            if db is None:
                db = self.bus.mem[ab] if ab < 0xF000 else None
            if db is not None:
                lo = alu.lo_addr(op, self.a, db, self.c)
                lv = self.alu_lo[lo]
                hi = alu.hi_addr(op, self.a, db, (lv >> 4) & 1, (lv >> 5) & 1, self.z)
                self.kayit.setdefault(op, []).append(
                    (self.bus.leds, lo, hi, (cw >> 5) & 7 == 2, bool(cw & isa.FL), self.x))
        return super().cycle()


def asama_bitene_kadar(cpu, sonraki, limit):
    """LED 'sonraki' ilerleme koduna geçene, makine durana ya da limite kadar çalıştırır."""
    while not cpu.halted and cpu.cycles < limit and cpu.bus.leds != sonraki:
        cpu.cycle()
    return cpu


class TestAluHatalari(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cpu = KayitliMicro(Bus(), ROMS, ALU)
        cpu.bus.load(PROG.image[:0x8000])
        cpu.bus.dip = 1
        cpu.run(KISA_LIMIT)
        assert basarili(cpu)
        cls.kayit = cpu.kayit

    def bozuk_kos(self, tablo, adres, maske, asama):
        lo, hi = bytearray(ALU[0]), bytearray(ALU[1])
        t = lo if tablo == 'L' else hi
        for bank in (0, 0x10000):
            t[adres | bank] ^= maske
        cpu = makine(True, dip=1, tables=(lo, hi))
        if asama == 1:
            asama_bitene_kadar(cpu, 0x02, 50_000)
        else:
            cpu.run(KISA_LIMIT)
        return cpu

    def test_her_islem_icin_bir_giris(self):
        """Her ALU işlemi için testin kullandığı ilk girişte, iki tablonun her çıkış biti
        tek tek ters çevrilir (L: 7 bit, H: 8 bit). Tablo satırı: kaç bozma yakalandı."""
        kapsanan, satirlar = [], []
        for op, name in enumerate(isa.ALUOPS):
            uses = self.kayit.get(op, [])
            # 1. aşamada X = alt test no; X = 0 dallanma testidir (sonuç değeri denetlenmez)
            stage1 = [u for u in uses if u[0] == 0x01 and u[5] != 0]
            full = [u for u in (stage1 or uses) if u[3] and u[4]]
            pick = (full or stage1 or uses or [None])[0]
            if pick is None:
                satirlar.append(f'    {name:<6} POST kullanmıyor')
                continue
            asama = 1 if stage1 else pick[0]
            beklenen = f'HATA {asama}'
            yakalandi, kacan = 0, []
            for tablo, adres, bitler in (('L', pick[1], range(7)), ('H', pick[2], range(8))):
                for bit in bitler:
                    cpu = self.bozuk_kos(tablo, adres, 1 << bit, asama)
                    sonuc = 'geçti' if (asama == 1 and not cpu.halted
                                        and cpu.bus.leds == 0x02) else ozet(cpu)
                    if sonuc == beklenen:
                        yakalandi += 1
                    else:
                        kacan.append(f'{tablo}{bit}:{sonuc}')
            # A'ya yazılan ve FL'li bir girişte sonuç bitleri (L0–3, H0–3), Z (H4) ve
            # N (H6) her vektörde denetlenir: bunların hepsi yakalanmalı
            # (5. aşamadaki INCB/ADCB0/DECB/SBCB0 INCW/DECW'nin ara adımlarıdır: ara Z
            # zincirde maskelenebilir, orada yalnız sayılır)
            if asama == 1 and pick[3] and pick[4]:
                for k in kacan:
                    self.assertNotRegex(k, r'^(L[0-3]|H[0-46]):', f'{name}: {k}')
            if yakalandi:
                kapsanan.append(name)
            satirlar.append(f'    {name:<6} aşama {asama}: {yakalandi}/15 yakalandı'
                            + (f'; kaçan: {" ".join(kacan)}' if kacan else ''))
        print(f'\n  ALU: {len(kapsanan)}/{len(isa.ALUOPS)} işlem kapsanıyor (POISON ayrıca yok)')
        print('\n'.join(satirlar))
        self.assertGreaterEqual(len(kapsanan), 24)


# ---------------------------------------------------------------------------
# Mikrokod bozma
# ---------------------------------------------------------------------------
def bozuk_urom(degisiklik):
    """degisiklik(ir, step, flags, word) -> yeni word ya da None. Tüm adreslere uygulanır."""
    roms = [bytearray(r) for r in ROMS]
    for ir in range(256):
        for flags in range(16):
            for s in range(16):
                a = s | ir << 4 | flags << 12
                w = roms[0][a] | roms[1][a] << 8 | roms[2][a] << 16
                n = degisiklik(ir, s, flags, w)
                if n is not None and n != w:
                    for bank in (0, 0x10000):
                        roms[0][a | bank] = n & 0xFF
                        roms[1][a | bank] = (n >> 8) & 0xFF
                        roms[2][a | bank] = n >> 16
    return roms


def adim(ir, step, f):
    """Belirli opcode ve adımın kontrol kelimesine f uygulayan değişiklik."""
    return lambda i, s, fl, w: f(w) if (i == ir and s == step) else None


def aluop(w, name):
    return (w & ~(31 << isa.ALUOP_SHIFT)) | isa.ALUOP[name] << isa.ALUOP_SHIFT


def ters_dallanma(cc, sadece=None):
    """B0+cc'nin alınır/alınmaz adımlarını yer değiştirir (sadece: tek bayrak birleşimi)."""
    ins = isa.INSTRUCTIONS[0xB0 + cc]
    taken = [s.word() for s in ins.taken]
    not_taken = [s.word() for s in ins.not_taken]
    unused = isa.step(isa.UNUSED).word()

    def f(i, s, fl, w):
        if i != 0xB0 + cc or s == 0 or (sadece is not None and fl != sadece):
            return None
        z, c, n, v = fl & 1, (fl >> 1) & 1, (fl >> 2) & 1, fl >> 3
        seq = not_taken if ins.cond(z, c, n, v) else taken
        return seq[s - 1] if s <= len(seq) else unused
    return f


OP = isa.BY_NAME
HEDEFLI = [   # (açıklama, değişiklik)
    ('ADD # FL yok', adim(OP['ADD', '#'], 1, lambda w: w & ~isa.FL)),
    ('CMP # SUB yerine ADD', adim(OP['CMP', '#'], 1, lambda w: aluop(w, 'ADD'))),
    ('DEC yerine INC', adim(OP['DEC', 'imp'], 1, lambda w: aluop(w, 'INC'))),
    ('NOT işlemsiz (PASSA)', adim(OP['NOT', 'imp'], 1, lambda w: aluop(w, 'PASSA'))),
    ('LDA (X+) XINC yok', adim(OP['LDA', '(X+)'], 1, lambda w: w & ~isa.XINC)),
    ('LDA (X) fazladan XINC', adim(OP['LDA', '(X)'], 1, lambda w: w | isa.XINC)),
    ('STA abs MEMW yok', adim(OP['STA', 'abs'], 3, lambda w: w & ~isa.MEMW)),
    ('STA (X) MEMW yok', adim(OP['STA', '(X)'], 1, lambda w: w & ~isa.MEMW)),
    ('INX XINC yok', adim(OP['INX', 'imp'], 1, lambda w: w & ~isa.XINC)),
    ('TAXH XL\'ye yazar', adim(OP['TAXH', 'imp'], 1,
                               lambda w: (w & ~(7 << isa.DDST_SHIFT)) | 3 << isa.DDST_SHIFT)),
    ('LDX abs ARINC yok', adim(OP['LDX', 'abs'], 3, lambda w: w & ~isa.ARINC)),
    ('PHA SPDN yok', adim(OP['PHA', 'imp'], 1, lambda w: w & ~isa.SPDN)),
    ('PLA SPCNT yok', adim(OP['PLA', 'imp'], 1, lambda w: w & ~isa.SPCNT)),
    ('CALL PCL yazmaz', adim(OP['CALL', 'abs'], 4, lambda w: w & ~isa.MEMW)),
    ('RET ARL/ARH ters', lambda i, s, fl, w: (
        None if i != OP['RET', 'imp'] or s not in (2, 3) else
        (w & ~(7 << isa.DDST_SHIFT)) | (6 if s == 2 else 5) << isa.DDST_SHIFT)),
    ('JMPI ARINC yok', adim(OP['JMPI', 'ind'], 3, lambda w: w & ~isa.ARINC)),
    ('INCW 2. byte FL yok', adim(OP['INCW', 'abs'], 5, lambda w: w & ~isa.FL)),
    ('DECW SBCB0 yerine ADCB0', adim(OP['DECW', 'abs'], 5, lambda w: aluop(w, 'ADCB0'))),
    ('BIT abs FL yok', adim(OP['BIT', 'abs'], 3, lambda w: w & ~isa.FL)),
    ('JMP PCLD yok', adim(OP['JMP', 'abs'], 3, lambda w: w & ~isa.PCLD)),
]


class TestMikrokodHatalari(unittest.TestCase):
    """SW0 = 1 ile koşulur (3b march'ı atlanır; hızlı). Sonuç 'TAMAM' olmamalı."""

    def kos(self, roms):
        return ozet(calistir(True, dip=1, roms=roms, limit=KISA_LIMIT))

    def test_dallanma_kosulu_ters(self):
        satir = []
        for cc, (name, _) in enumerate(isa.BRANCHES):
            sonuc = self.kos(bozuk_urom(ters_dallanma(cc)))
            self.assertNotEqual(sonuc, 'TAMAM', name)
            satir.append(f'{name}:{sonuc}')
        print('\n  dallanma ters (tüm bayraklar): ' + ' '.join(satir))

    def test_dallanma_tek_bayrak_birlesimi(self):
        """Her dallanmada yalnız bir bayrak birleşimi ters: POST'un o birleşimi gerçekten
        denediği (kayıtla belirlenir) her durumda yakalanmalı."""
        cpu = MicroEmu(Bus(), ROMS, ALU)
        cpu.bus.load(PROG.image[:0x8000])
        cpu.bus.dip = 1
        gorulen = set()
        while not cpu.halted and cpu.cycles < KISA_LIMIT:
            if cpu.step == 1 and 0xB0 <= cpu.ir <= 0xBD:
                gorulen.add((cpu.ir - 0xB0, cpu.z | cpu.c << 1 | cpu.n << 2 | cpu.v << 3))
            cpu.cycle()
        kacan = []
        for cc, fl in sorted(gorulen):
            if self.kos(bozuk_urom(ters_dallanma(cc, fl))) == 'TAMAM':
                kacan.append((isa.BRANCHES[cc][0], fl))
        print(f'\n  dallanma × bayrak birleşimi: {len(gorulen)}/{14 * 16} deneniyor '
              f'(Z=1,N=1 hiç oluşmaz), ters çevrilince kaçan: {kacan or "yok"}')
        self.assertEqual(kacan, [])

    def test_hedefli_bozmalar(self):
        satir = []
        for ad, deg in HEDEFLI:
            sonuc = self.kos(bozuk_urom(deg))
            satir.append(f'    {ad}: {sonuc}')
            self.assertNotEqual(sonuc, 'TAMAM', ad)
        print('\n  hedefli mikrokod bozmaları:\n' + '\n'.join(satir))

    def test_opcode_kapsami(self):
        """POST'un çalıştırdığı opcode'lar (SW0 = 0, tam koşu)."""
        class Sayan(RefEmu):
            def instruction(self):
                self.gorulen.add(self.bus.read(self.pc))
                return super().instruction()
        bus = Bus()
        bus.load(PROG.image[:0x8000])
        cpu = Sayan(bus)
        cpu.gorulen = set()
        cpu.run(TAM_LIMIT)
        tanimli = set(isa.INSTRUCTIONS)
        eksik = sorted(f'{c:02X} {isa.INSTRUCTIONS[c].mnemonic} {isa.INSTRUCTIONS[c].mode}'
                       for c in tanimli - cpu.gorulen)
        print(f'\n  opcode: {len(cpu.gorulen & tanimli)}/{len(tanimli)} çalıştırılıyor; '
              f'eksik: {eksik}')
        self.assertLessEqual(len(eksik), 2)


if __name__ == '__main__':
    unittest.main()
