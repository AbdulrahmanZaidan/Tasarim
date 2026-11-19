"""ALU: 8-bit referans ve iki flash'a yazılan nibble tabloları.

Donanımda ALU iki SST39SF010'dur (SISTEM-PLANI 5.2):
  ALU-L adres: A0–3 = A[3:0], A4–7 = DB[3:0], A8 = C, A9 = A[4],
               A10–14 = ALUOP, A15 = A[7], A16 = jumper
        veri : D0–3 = R[3:0], D4 = c4 (üst nibble'a bağlantı), D5 = Zlo, D6 = Clo
  ALU-H adres: A0–3 = A[7:4], A4–7 = DB[7:4], A8 = c4, A9 = Zlo, A10 = Z,
               A11–15 = ALUOP, A16 = jumper
        veri : D0–3 = R[7:4], D4 = Z, D5 = Chi, D6 = N, D7 = V
  C = Clo OR Chi

`alu_ref` nibble bölmesinden bağımsız yazılmıştır. Testler iki tablonun birlikte
her girişte `alu_ref` ile aynı sonucu verdiğini tek tek kontrol eder.
"""

from .isa import ALUOPS, CHAINED_Z

ROM_SIZE = 0x20000


def _name(op):
    return ALUOPS[op] if op < len(ALUOPS) else 'POISON'


def alu_ref(op, a, b, c, z):
    """8-bit referans: (sonuç, Z, C, N, V). b = veri yolu (DB)."""
    name = _name(op)
    if name == 'POISON':
        return 0xA5, 1, 1, 1, 1
    nc, v = c, 0
    if name == 'PASSB':
        r = b
        v = (b >> 6) & 1
    elif name in ('ADD', 'ADC'):
        x = a + b + (c if name == 'ADC' else 0)
        r, nc = x & 0xFF, x >> 8
        v = int((a ^ r) & (b ^ r) & 0x80 != 0)
    elif name in ('SUB', 'SBC'):
        x = a - b - ((1 - c) if name == 'SBC' else 0)
        r, nc = x & 0xFF, int(x >= 0)
        v = int((a ^ b) & (a ^ r) & 0x80 != 0)
    elif name == 'AND':
        r = a & b
    elif name == 'OR':
        r = a | b
    elif name == 'XOR':
        r = a ^ b
    elif name == 'INC':
        r = (a + 1) & 0xFF
        v = int(a == 0x7F)
    elif name == 'DEC':
        r = (a - 1) & 0xFF
        v = int(a == 0x80)
    elif name == 'NOT':
        r = ~a & 0xFF
    elif name == 'NEG':
        r = -a & 0xFF
        nc = int(a == 0)
        v = int(a == 0x80)
    elif name == 'SHL':
        r, nc = (a << 1) & 0xFF, a >> 7
    elif name == 'ROL':
        r, nc = ((a << 1) | c) & 0xFF, a >> 7
    elif name == 'SHR':
        r, nc = a >> 1, a & 1
    elif name == 'ROR':
        r, nc = (a >> 1) | (c << 7), a & 1
    elif name == 'ASR':
        r, nc = (a >> 1) | (a & 0x80), a & 1
    elif name == 'PASSA':
        r = a
    elif name == 'CLC':
        r, nc = a, 0
    elif name == 'SEC':
        r, nc = a, 1
    elif name == 'SEX':
        r = 0xFF if a & 0x80 else 0
    elif name in ('INCB', 'ADCB0'):
        x = b + (1 if name == 'INCB' else c)
        r, nc = x & 0xFF, x >> 8
        v = int(b == 0x7F and r == 0x80)
    elif name in ('DECB', 'SBCB0'):
        x = b - (1 if name == 'DECB' else 1 - c)
        r, nc = x & 0xFF, int(x >= 0)
        v = int(b == 0x80 and r == 0x7F)
    else:
        raise AssertionError(name)
    nz = int(r == 0)
    if name in CHAINED_Z:
        nz &= z
    return r, nz, nc, r >> 7, v


def _lo(op, al, bl, c, a4, a7):
    """Alt nibble: (r, c4, zlo, clo)."""
    name = _name(op)
    c4, clo = 0, c                       # varsayılan: C korunur (Clo = C, Chi = 0)
    if name == 'POISON':
        return 0x5, 0, 0, 1
    if name == 'PASSB':
        r = bl
    elif name in ('ADD', 'ADC', 'INC', 'INCB', 'ADCB0'):
        x = {'ADD': al + bl, 'ADC': al + bl + c, 'INC': al + 1,
             'INCB': bl + 1, 'ADCB0': bl + c}[name]
        r, c4 = x & 15, x >> 4
        if name != 'INC':
            clo = 0
    elif name in ('SUB', 'SBC', 'DEC', 'DECB', 'SBCB0', 'NEG'):
        x = {'SUB': al - bl, 'SBC': al - bl - (1 - c), 'DEC': al - 1,
             'DECB': bl - 1, 'SBCB0': bl - (1 - c), 'NEG': -al}[name]
        r, c4 = x & 15, int(x < 0)      # c4 = borç
        if name != 'DEC':
            clo = 0
    elif name == 'AND':
        r = al & bl
    elif name == 'OR':
        r = al | bl
    elif name == 'XOR':
        r = al ^ bl
    elif name == 'NOT':
        r = ~al & 15
    elif name in ('SHL', 'ROL'):
        r = ((al << 1) | (c if name == 'ROL' else 0)) & 15
        c4, clo = al >> 3, 0            # c4 = A3 üst nibble'ın bit 0'ına
    elif name in ('SHR', 'ROR', 'ASR'):
        r = (al >> 1) | (a4 << 3)
        c4 = c if name == 'ROR' else 0  # ROR: C üst nibble'ın bit 3'üne
        clo = al & 1                    # dışarı kayan A0
    elif name in ('PASSA', 'CLC', 'SEC'):
        r = al
        clo = {'PASSA': c, 'CLC': 0, 'SEC': 1}[name]
    elif name == 'SEX':
        r = 15 if a7 else 0
    else:
        raise AssertionError(name)
    return r, c4, int(r == 0), clo


def _hi(op, ah, bh, c4, zlo, z):
    """Üst nibble: (r, Z, Chi, N, V)."""
    name = _name(op)
    if name == 'POISON':
        return 0xA, 1, 1, 1, 1
    chi, v = 0, 0
    a7, b7 = ah >> 3, bh >> 3
    if name == 'PASSB':
        r = bh
        v = (bh >> 2) & 1               # B6 (BIT için)
    elif name in ('ADD', 'ADC'):
        x = ah + bh + c4
        r, chi = x & 15, x >> 4
        v = int(a7 == b7 and (r >> 3) != a7)
    elif name == 'INC':
        r = (ah + c4) & 15
        v = int(a7 == 0 and r >> 3 == 1)
    elif name in ('INCB', 'ADCB0'):
        x = bh + c4
        r, chi = x & 15, x >> 4
        v = int(b7 == 0 and r >> 3 == 1)
    elif name in ('SUB', 'SBC'):
        x = ah - bh - c4
        r, chi = x & 15, int(x >= 0)
        v = int(a7 != b7 and (r >> 3) != a7)
    elif name == 'DEC':
        r = (ah - c4) & 15
        v = int(a7 == 1 and r >> 3 == 0)
    elif name in ('DECB', 'SBCB0'):
        x = bh - c4
        r, chi = x & 15, int(x >= 0)
        v = int(b7 == 1 and r >> 3 == 0)
    elif name == 'NEG':
        x = -ah - c4
        r, chi = x & 15, int(x >= 0)
        v = int(a7 == 1 and r >> 3 == 1)
    elif name == 'AND':
        r = ah & bh
    elif name == 'OR':
        r = ah | bh
    elif name == 'XOR':
        r = ah ^ bh
    elif name == 'NOT':
        r = ~ah & 15
    elif name in ('SHL', 'ROL'):
        r, chi = ((ah << 1) | c4) & 15, a7
    elif name == 'SHR':
        r = ah >> 1
    elif name == 'ROR':
        r = (ah >> 1) | (c4 << 3)
    elif name == 'ASR':
        r = (ah >> 1) | (ah & 8)
    elif name in ('PASSA', 'CLC', 'SEC'):
        r = ah
    elif name == 'SEX':
        r = 15 if a7 else 0
    else:
        raise AssertionError(name)
    nz = zlo & int(r == 0)
    if name in CHAINED_Z:
        nz &= z
    return r, nz, chi, r >> 3, v


def lo_addr(op, a, b, c):
    """ALU-L adresi (A16 jumper = 0)."""
    return ((a & 15) | (b & 15) << 4 | c << 8 | ((a >> 4) & 1) << 9
            | op << 10 | (a >> 7) << 15)


def hi_addr(op, a, b, c4, zlo, z):
    """ALU-H adresi (A16 jumper = 0)."""
    return (a >> 4) | (b >> 4) << 4 | c4 << 8 | zlo << 9 | z << 10 | op << 11


def build_tables():
    """İki 128 KB imaj: (ALU-L, ALU-H). Üst yarı (jumper = 1) alt yarının kopyası."""
    lo = bytearray(ROM_SIZE)
    hi = bytearray(ROM_SIZE)
    for addr in range(0x10000):
        r, c4, zlo, clo = _lo(op=(addr >> 10) & 31, al=addr & 15, bl=(addr >> 4) & 15,
                              c=(addr >> 8) & 1, a4=(addr >> 9) & 1, a7=addr >> 15)
        lo[addr] = r | c4 << 4 | zlo << 5 | clo << 6
        r, nz, chi, n, v = _hi(op=addr >> 11, ah=addr & 15, bh=(addr >> 4) & 15,
                               c4=(addr >> 8) & 1, zlo=(addr >> 9) & 1, z=(addr >> 10) & 1)
        hi[addr] = r | nz << 4 | chi << 5 | n << 6 | v << 7
    lo[0x10000:] = lo[:0x10000]
    hi[0x10000:] = hi[:0x10000]
    return lo, hi


def alu_tables(lo, hi, op, a, b, c, z):
    """Tablolar üzerinden 8-bit sonuç: donanımın yaptığı hesap."""
    lv = lo[lo_addr(op, a, b, c)]
    c4, zlo, clo = (lv >> 4) & 1, (lv >> 5) & 1, (lv >> 6) & 1
    hv = hi[hi_addr(op, a, b, c4, zlo, z)]
    r = (lv & 15) | (hv & 15) << 4
    return r, (hv >> 4) & 1, clo | ((hv >> 5) & 1), (hv >> 6) & 1, hv >> 7
