"""Devre simülatörleri için test vektörleri (SISTEM-PLANI 12.3).

Her `*_vectors` işlevi metin döndürür. İki biçim vardır:

    digital  Digital'in test bileşeni: '#' yorum satırları, ilk satır sinyal
             adları, değerler boşlukla ayrık, onaltılılar 0x.. biçiminde.
    csv      Aynı tablo virgülle ayrık; yorum satırı yok.

Aktif-düşük sinyallerin adları `/` yerine `_n` son ekiyle yazılır (/MRD -> MRD_n),
çünkü bu adlar Digital'de devre etiketleriyle birebir eşleşmek zorunda.
"""

import random

from . import alu as alu_model
from . import isa, microcode
from .bus import Bus
from .emu_micro import MicroEmu

FORMATS = ('digital', 'csv')


def render(names, rows, comments=(), fmt='digital', clock=None):
    """Tabloyu metne çevirir. `rows` hazır biçimlenmiş değer (str) dizileridir.

    `clock` verilirse (yalnız digital) ilk sütun bu adla eklenir ve her satırda
    değeri `C` (saat darbesi) olur.
    """
    if fmt not in FORMATS:
        raise ValueError(f'bilinmeyen biçim {fmt!r}')
    if clock and fmt != 'digital':
        raise ValueError('saat sütunu yalnız digital biçiminde')
    sep = ' ' if fmt == 'digital' else ','
    lines = [f'# {c}' for c in comments] if fmt == 'digital' else []
    lines.append(sep.join(([clock] if clock else []) + list(names)))
    pre = ['C'] if clock else []
    lines.extend(sep.join(pre + list(row)) for row in rows)
    return '\n'.join(lines) + '\n'


def _h(v, digits):
    return f'0x{v:0{digits}X}'


# ---------------------------------------------------------------------------
# M4 ALU ve M2 kontrol (uROM): rastgele vektörler
# ---------------------------------------------------------------------------

def alu_vectors(n=1000, seed=1, fmt='digital'):
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        op = rng.randrange(len(isa.ALUOPS))
        a, b = rng.randrange(256), rng.randrange(256)
        c, z = rng.randrange(2), rng.randrange(2)
        r, nz, nc, nn, v = alu_model.alu_ref(op, a, b, c, z)
        rows.append([str(op), _h(a, 2), _h(b, 2), str(c), str(z),
                     _h(r, 2), str(nz), str(nc), str(nn), str(v)])
    return render('OP A B Cin Zin R Z C N V'.split(), rows,
                  ['M4 ALU testi: girişler OP A B Cin Zin, çıkışlar R Z C N V'], fmt)


def urom_vectors(n=1000, seed=1, fmt='digital'):
    rng = random.Random(seed)
    roms = microcode.build()
    rows = []
    for _ in range(n):
        st, ir = rng.randrange(16), rng.randrange(256)
        z, c, nn, v = (rng.randrange(2) for _ in range(4))
        w = microcode.word_at(roms, st, ir, z, c, nn, v)
        rows.append([str(st), _h(ir, 2), str(z), str(c), str(nn), str(v),
                     _h(w & 0xFF, 2), _h((w >> 8) & 0xFF, 2), _h(w >> 16, 2)])
    return render('STEP IR Z C N V CW0 CW1 CW2'.split(), rows,
                  ['M2 kontrol testi: girişler STEP IR Z C N V (BANK = 0), çıkışlar CW0 CW1 CW2'],
                  fmt)


# ---------------------------------------------------------------------------
# M5 adres çözme (SISTEM-PLANI 7.2; /RD ve /WR bölüm 2)
# ---------------------------------------------------------------------------

DECODE_IN = ['AB', 'MRD_n', 'MEMW_L', 'WSTB']
DECODE_OUT = ['ROM_CE_n', 'FPAGE_n', 'RAM_CE_n', 'VRAMSEL_n', 'IOSEL_n', 'RD_n',
              'MWR_n', 'WR_n', 'KBD_RD_n', 'STAT_RD_n', 'LED_E_n', 'VRAM_WE_n']
# Her bölgenin ilk ve son adresi + I/O'nun 8'lik tekrarı
DECODE_ADDRS = [0x0000, 0x7FFF, 0x8000, 0xEFFF, 0xF000, 0xF7FF,
                0xF800, 0xF801, 0xF807, 0xF808, 0xF809, 0xFFFF]
DECODE_NOTES = [
    '/ARD_RD = /ARD_WR = 1 (Arduino takılı değil): RD_n = MRD_n, WR_n = MWR_n',
    'KBD_RD_n, STAT_RD_n: #IOR 74HC138 G1 = VCC varsayıldı (7.2 G1 ucunu yazmıyor; '
    'tasarim-taslaklari/ISA-v0-sentez.md 6.1: G1 = VCC)',
    'LED_E_n: OR(/IOSEL, /MEMW), /MEMW = 74HC04(MEMW_L) (4.2); A0..A2 çözülmez, '
    'her I/O adresine yazma LED latch\'ini izinler',
]


def decode(ab, mrd_n, memw_l, wstb, ard_rd_n=1, ard_wr_n=1):
    """M5 adres çözme, plandaki tablodan kapı kapı. Sinyal adı -> 0/1 sözlüğü."""
    a15, a14, a13, a12, a11 = ((ab >> k) & 1 for k in (15, 14, 13, 12, 11))
    rom_ce_n = a15                                         # doğrudan kablo
    fpage_n = 1 - (a15 & a14 & a13 & a12)                  # 74HC20 NAND4
    ram_ce_n = 1 - (a15 & fpage_n)                         # NAND(A15, /FPAGE)
    ms = a11 if fpage_n == 0 else None                     # 139 #MS: /G=/FPAGE, A=A11, B=GND
    vramsel_n = 0 if ms == 0 else 1                        # Y0
    iosel_n = 0 if ms == 1 else 1                          # Y1
    rd_n = mrd_n & ard_rd_n                                # AND(/MRD, /ARD_RD)
    mwr_n = 1 - (memw_l & wstb)                            # NAND(MEMW_L, WSTB)
    wr_n = mwr_n & ard_wr_n                                # AND(/MWR, /ARD_WR)
    ior = ab & 7 if iosel_n == 0 and rd_n == 0 else None   # 138 #IOR: /G2A=/IOSEL, /G2B=/RD
    kbd_rd_n = 0 if ior == 0 else 1                        # Y0
    stat_rd_n = 0 if ior == 1 else 1                       # Y1
    led_e_n = iosel_n | (1 - memw_l)                       # OR(/IOSEL, /MEMW)
    vram_we_n = wr_n | vramsel_n                           # OR(/WR, /VRAMSEL)
    return dict(zip(DECODE_OUT, (rom_ce_n, fpage_n, ram_ce_n, vramsel_n, iosel_n, rd_n,
                                 mwr_n, wr_n, kbd_rd_n, stat_rd_n, led_e_n, vram_we_n)))


def decode_vectors(n=1000, seed=1, fmt='digital'):
    """Sınır adresleri × (MRD_n, MEMW_L, WSTB)'nin 8 birleşimi, üstüne n rastgele satır."""
    rng = random.Random(seed)
    cases = [(ab, k >> 2 & 1, k >> 1 & 1, k & 1) for ab in DECODE_ADDRS for k in range(8)]
    cases += [(rng.randrange(0x10000), rng.randrange(2), rng.randrange(2), rng.randrange(2))
              for _ in range(n)]
    rows = []
    for ab, mrd_n, memw_l, wstb in cases:
        out = decode(ab, mrd_n, memw_l, wstb)
        rows.append([_h(ab, 4), str(mrd_n), str(memw_l), str(wstb)]
                    + [str(out[s]) for s in DECODE_OUT])
    comments = ['M5 adres çözme (SISTEM-PLANI 7.2): girişler ' + ' '.join(DECODE_IN)
                + ', çıkışlar ' + ' '.join(DECODE_OUT)] + DECODE_NOTES
    return render(DECODE_IN + DECODE_OUT, rows, comments, fmt)


# ---------------------------------------------------------------------------
# M2 kod çözücüler (SISTEM-PLANI 4.3)
# ---------------------------------------------------------------------------

CS_IN = ['DSRC', 'DDST', 'ASRC', 'BUSACK']
DS_OUT = ['MRD_n', 'OE_A_n', 'OE_PCL_n', 'OE_PCH_n']                          # #DS Y1..Y4
DD_OUT = ['DD_IR_n', 'DD_A_n', 'DD_XL_n', 'DD_XH_n', 'DD_ARL_n', 'DD_ARH_n']  # #DD Y1..Y6
AS_OUT = ['AB_PC_n', 'AB_AR_n', 'AB_X_n', 'AB_SP_n']                          # #AS Y0..Y3
CS_OUT = DS_OUT + DD_OUT + AS_OUT


def chip_selects(dsrc, ddst, asrc, busack):
    """#DS, #DD, #AS çıkışları. Sinyal adı -> 0/1 sözlüğü."""
    out = {}
    for k, name in enumerate(DS_OUT, 1):   # 74HC138: G1 = VCC, /G2A = BUSACK, /G2B = GND
        out[name] = 0 if not busack and dsrc == k else 1
    for k, name in enumerate(DD_OUT, 1):   # 74HC138: hep izinli
        out[name] = 0 if ddst == k else 1
    for k, name in enumerate(AS_OUT):      # 74HC139 yarısı: /G = BUSACK
        out[name] = 0 if not busack and asrc == k else 1
    return out


def cs_vectors(fmt='digital'):
    """Bütün birleşimler: 8 DSRC × 8 DDST × 4 ASRC × 2 BUSACK = 512 satır."""
    rows = []
    for busack in (0, 1):
        for dsrc in range(8):
            for ddst in range(8):
                for asrc in range(4):
                    out = chip_selects(dsrc, ddst, asrc, busack)
                    rows.append([str(dsrc), str(ddst), str(asrc), str(busack)]
                                + [str(out[s]) for s in CS_OUT])
    comments = [
        'M2 kod çözücüler (SISTEM-PLANI 4.3): girişler ' + ' '.join(CS_IN)
        + ', çıkışlar ' + ' '.join(CS_OUT),
        '#DS 74HC138 (G1 = VCC, /G2A = BUSACK, /G2B = GND), #DD 74HC138 (hep izinli), '
        '#AS 74HC139 (/G = BUSACK); G1 ve /G2B uçları 4.3\'te yok, ISA-v0-sentez 4.3\'ten',
    ]
    return render(CS_IN + CS_OUT, rows, comments, fmt)


# ---------------------------------------------------------------------------
# Bütün CPU: emülatör izi (çevrim çevrim AB / DB / CW)
# ---------------------------------------------------------------------------

CW_FIELDS = ['ASRC', 'DSRC', 'DDST', 'ALUOP'] + list(isa.BITS)
TRACE_COLS = ['CYC', 'AB', 'DB', 'CW'] + CW_FIELDS


def cw_fields(cw):
    """24 bitlik kontrol kelimesini alanlarına ayırır (SISTEM-PLANI 4.2)."""
    f = {'ASRC': cw >> isa.ASRC_SHIFT & 3, 'DSRC': cw >> isa.DSRC_SHIFT & 7,
         'DDST': cw >> isa.DDST_SHIFT & 7, 'ALUOP': cw >> isa.ALUOP_SHIFT & 31}
    f.update((name, int(bool(cw & bit))) for name, bit in isa.BITS.items())
    return f


def run_trace(image, cycles=2000):
    """Programı MicroEmu'da çalıştırır (klavye yok, DIP = 0, VRAM penceresi hep açık).

    HALT'ta ya da `cycles` çevrimde durur. Döner: [(çevrim, AB, DB, CW), ...].
    """
    bus = Bus()
    bus.load(image)
    cpu = MicroEmu(bus)
    cpu.trace = []
    cpu.run(cycles)
    return cpu.trace


def trace_vectors(image, cycles=2000, fmt='digital', clock=None):
    rows = run_trace(image, cycles)
    halted = bool(rows and rows[-1][3] & isa.HALT)
    table = []
    for cyc, ab, db, cw in rows:
        f = cw_fields(cw)
        table.append([str(cyc), _h(ab, 4), _h(db, 2), _h(cw, 6)]
                     + [str(f[k]) for k in CW_FIELDS])
    comments = [
        f'Bütün CPU izi (SISTEM-PLANI 12.3): MicroEmu, {len(rows)} çevrim, '
        + ('HALT ile bitti' if halted else 'çevrim sınırında kesildi'),
        'Her satır bir CPU çevrimi; AB, DB, CW o çevrimin commit (B->C) öncesi değerleri',
    ]
    return render(TRACE_COLS, table, comments, fmt, clock)


def _value(cell):
    if cell[:2].lower() == '0x':
        return int(cell, 16)
    try:
        return int(cell)
    except ValueError:
        return cell                       # C, X, Z ...


def parse_table(text):
    """Bu modülün yazdığı biçimdeki (digital ya da csv) bir tabloyu okur.

    Döner: (adlar, satırlar); sayılar int'e çevrilir, C/X/Z gibi değerler metin kalır.
    """
    names, rows = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        cells = [c.strip() for c in line.split(',')] if ',' in line else line.split()
        if not names:
            names = cells
        else:
            rows.append([_value(c) for c in cells])
    return names, rows


def parse_trace(text):
    """Bir iz tablosunu (en az AB, DB, CW sütunları; CYC yoksa satır no) okur.

    Döner: [(çevrim, AB, DB, CW), ...], yani `compare_traces`'in beklediği biçim.
    """
    names, rows = parse_table(text)
    col = {name: i for i, name in enumerate(names)}
    for need in ('AB', 'DB', 'CW'):
        if need not in col:
            raise ValueError(f'iz tablosunda {need} sütunu yok')
    return [(r[col['CYC']] if 'CYC' in col else i, r[col['AB']], r[col['DB']], r[col['CW']])
            for i, r in enumerate(rows)]


def compare_traces(ref_rows, got_rows):
    """İki izi satır satır karşılaştırır; satır = (çevrim, AB, DB, CW).

    Çevrim numarası karşılaştırılmaz (Arduino kendi sayacını tutar); sıra esastır.
    Döner: (ilk farklı satırın indeksi ya da None, açıklama).
    """
    for i, (r, g) in enumerate(zip(ref_rows, got_rows)):
        diffs = []
        if r[1] != g[1]:
            diffs.append(f'AB beklenen {r[1]:04X}, gelen {g[1]:04X}')
        if r[2] != g[2]:
            diffs.append(f'DB beklenen {r[2]:02X}, gelen {g[2]:02X}')
        if r[3] != g[3]:
            fr, fg = cw_fields(r[3]), cw_fields(g[3])
            changed = ', '.join(f'{k} {fr[k]}->{fg[k]}' for k in CW_FIELDS if fr[k] != fg[k])
            diffs.append(f'CW {r[3]:06X} -> {g[3]:06X} ({changed}); beklenen '
                         f'[{microcode.describe(r[3])}], gelen [{microcode.describe(g[3])}]')
        if diffs:
            return i, f'satır {i} (referans çevrim {r[0]}): ' + '; '.join(diffs)
    if len(ref_rows) != len(got_rows):
        i = min(len(ref_rows), len(got_rows))
        short = 'gelen' if len(got_rows) < len(ref_rows) else 'referans'
        return i, (f'satır {i}: {short} iz burada bitiyor '
                   f'(referans {len(ref_rows)}, gelen {len(got_rows)} satır)')
    return None, f'{len(ref_rows)} satır, fark yok'
