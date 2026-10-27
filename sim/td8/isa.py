"""TD-8 komut seti: tek kaynak.

Mikrokod imajı, assembler ve iki emülatör bu dosyadaki tanımları kullanır.
Komut setinde bir şey değişecekse önce burası değişir, sonra
`py gen_roms.py` ve `py -m unittest` çalıştırılır.

Açıklamalar: ../../SISTEM-PLANI.md bölüm 4–6.
"""

# ---------------------------------------------------------------------------
# Kontrol kelimesi: 24 bit, ROM'da aktif-yüksek (SISTEM-PLANI 4.2)
# uROM0 = bit 0–7, uROM1 = bit 8–15, uROM2 = bit 16–23
# ---------------------------------------------------------------------------

ASRC_SHIFT = 0    # 2 bit: adres kaynağı
DSRC_SHIFT = 2    # 3 bit: veri yolu kaynağı
DDST_SHIFT = 5    # 3 bit: hedef register
ALUOP_SHIFT = 8   # 5 bit: ALU işlemi

FL = 1 << 13
MEMW = 1 << 14
MARK = 1 << 15
PCINC = 1 << 16
PCLD = 1 << 17
ARINC = 1 << 18
XINC = 1 << 19
SPCNT = 1 << 20
SPDN = 1 << 21
NEXT = 1 << 22
HALT = 1 << 23

BITS = {
    'FL': FL, 'MEMW': MEMW, 'MARK': MARK,
    'PCINC': PCINC, 'PCLD': PCLD, 'ARINC': ARINC, 'XINC': XINC,
    'SPCNT': SPCNT, 'SPDN': SPDN, 'NEXT': NEXT, 'HALT': HALT,
}

ASRC = {'PC': 0, 'AR': 1, 'X': 2, 'SP': 3}
DSRC = {'-': 0, 'MEM': 1, 'A': 2, 'PCL': 3, 'PCH': 4}   # 5, 6 ayrılmış; 7 = yok/panel
DDST = {'-': 0, 'IR': 1, 'A': 2, 'XL': 3, 'XH': 4, 'ARL': 5, 'ARH': 6}   # 7 yasak

# ALU işlem kodları (SISTEM-PLANI 5.3). 0x19–0x1F = POISON.
ALUOPS = [
    'PASSB', 'ADD', 'ADC', 'SUB', 'SBC', 'AND', 'OR', 'XOR',
    'INC', 'DEC', 'NOT', 'NEG', 'SHL', 'ROL', 'SHR', 'ROR',
    'ASR', 'PASSA', 'CLC', 'SEC', 'SEX', 'INCB', 'ADCB0', 'DECB', 'SBCB0',
]
ALUOP = {name: code for code, name in enumerate(ALUOPS)}
POISON = 0x19
CHAINED_Z = {'ADC', 'SBC', 'ADCB0', 'SBCB0'}

STACK_PAGE = 0xEF00


class Step:
    """Bir mikroadım (bir CPU çevrimi)."""

    __slots__ = ('asrc', 'dsrc', 'ddst', 'aluop', 'bits', 'text')

    def __init__(self, asrc, dsrc, ddst, aluop, bits, text):
        self.asrc, self.dsrc, self.ddst = asrc, dsrc, ddst
        self.aluop, self.bits, self.text = aluop, bits, text

    def word(self):
        """24 bitlik kontrol kelimesi."""
        return (ASRC[self.asrc] << ASRC_SHIFT
                | DSRC[self.dsrc] << DSRC_SHIFT
                | DDST[self.ddst] << DDST_SHIFT
                | ALUOP.get(self.aluop, 0) << ALUOP_SHIFT
                | self.bits)

    def __repr__(self):
        return f'Step({self.text!r})'


def step(text):
    """Mikroadım yazımını çözer.

    Yazım: 'adres/kaynak/hedef/ALU bitler...', örnek 'AR/MEM/A/ADD FL NEXT'.
    '-' boş demek (adres için PC). Yalnızca bitler de yazılabilir: 'PCLD NEXT'.
    """
    tokens = text.split()
    asrc, dsrc, ddst, aluop = 'PC', '-', '-', None
    if tokens and '/' in tokens[0]:
        fields = tokens.pop(0).split('/')
        if len(fields) != 4:
            raise ValueError(f'{text!r}: 4 alan bekleniyor (adres/kaynak/hedef/ALU)')
        a, dsrc, ddst, o = fields
        asrc = 'PC' if a == '-' else a
        aluop = None if o == '-' else o
    if asrc not in ASRC:
        raise ValueError(f'{text!r}: bilinmeyen adres kaynağı {asrc!r}')
    if dsrc not in DSRC:
        raise ValueError(f'{text!r}: bilinmeyen veri kaynağı {dsrc!r}')
    if ddst not in DDST:
        raise ValueError(f'{text!r}: bilinmeyen hedef {ddst!r}')
    if aluop is not None and aluop not in ALUOP:
        raise ValueError(f'{text!r}: bilinmeyen ALU işlemi {aluop!r}')
    bits = 0
    for tok in tokens:
        if tok not in BITS:
            raise ValueError(f'{text!r}: bilinmeyen kontrol biti {tok!r}')
        bits |= BITS[tok]
    return Step(asrc, dsrc, ddst, aluop, bits, text)


FETCH = 'PC/MEM/IR/- PCINC'
OP1 = 'PC/MEM/ARL/- PCINC'      # mutlak adresin alt byte'ı
OP2 = 'PC/MEM/ARH/- PCINC'      # mutlak adresin üst byte'ı
UNUSED = 'HALT MARK NEXT'       # tanımsız opcode ve kullanılmayan adımlar

# Adresleme modu -> komut uzunluğu (byte)
MODE_SIZE = {'imp': 1, '#': 2, '#16': 3, 'abs': 3, '(X)': 1, '(X+)': 1, 'ind': 3}


class Instr:
    """Bir opcode'un tanımı."""

    def __init__(self, opcode, mnemonic, mode, steps=None, cond=None):
        self.opcode = opcode
        self.mnemonic = mnemonic
        self.mode = mode
        self.size = MODE_SIZE[mode]
        self.cond = cond                # yalnız dallanmalarda: koşul(z, c, n, v)
        if cond is None:
            self.steps = [step(s) for s in steps]
        else:
            self.taken = [step(s) for s in BRANCH_TAKEN]
            self.not_taken = [step(s) for s in BRANCH_NOT_TAKEN]

    def steps_for(self, z, c, n, v):
        """FETCH'ten sonraki adımlar; dallanmada flag'lere göre seçilir."""
        if self.cond is None:
            return self.steps
        return self.taken if self.cond(z, c, n, v) else self.not_taken

    def cycles(self, taken=True):
        """FETCH dahil çevrim sayısı (1 MHz'de µs)."""
        if self.cond is None:
            return 1 + len(self.steps)
        return 1 + len(self.taken if taken else self.not_taken)

    def __repr__(self):
        return f'Instr({self.opcode:#04x}, {self.mnemonic} {self.mode})'


# ---------------------------------------------------------------------------
# M grubu: bellek/ALU, opcode = 0x40 + 4*işlem + mod
# ---------------------------------------------------------------------------

M_GROUP = [   # (komut, ALU işlemi, hedef, flag yükler mi)
    ('LDA', 'PASSB', 'A', False),
    ('STA', None, None, False),
    ('ADD', 'ADD', 'A', True),
    ('ADC', 'ADC', 'A', True),
    ('SUB', 'SUB', 'A', True),
    ('SBC', 'SBC', 'A', True),
    ('AND', 'AND', 'A', True),
    ('OR', 'OR', 'A', True),
    ('XOR', 'XOR', 'A', True),
    ('CMP', 'SUB', '-', True),
    ('CPC', 'SBC', '-', True),
    ('BIT', 'PASSB', '-', True),
]
M_MODES = ['#', 'abs', '(X)', '(X+)']


def _m_steps(name, op, dst, fl, mode):
    if name == 'STA':
        if mode == '#':
            return None                 # 0x44 yasak
        if mode == 'abs':
            return [OP1, OP2, 'AR/A/-/- MEMW NEXT']
        inc = ' XINC' if mode == '(X+)' else ''
        return [f'X/A/-/- MEMW{inc} NEXT']
    if name == 'BIT' and mode == '#':
        return None                     # 0x6C yasak
    flags = ' FL' if fl else ''
    if mode == '#':
        return [f'PC/MEM/{dst}/{op}{flags} PCINC NEXT']
    if mode == 'abs':
        return [OP1, OP2, f'AR/MEM/{dst}/{op}{flags} NEXT']
    inc = ' XINC' if mode == '(X+)' else ''
    return [f'X/MEM/{dst}/{op}{flags}{inc} NEXT']


# ---------------------------------------------------------------------------
# Diğer gruplar
# ---------------------------------------------------------------------------

U_GROUP = ['INC', 'DEC', 'NOT', 'NEG', 'SHL', 'ROL', 'SHR', 'ROR',
           'ASR', 'TST', 'CLC', 'SEC', 'SEX']          # 0x80–0x8C


def _u_steps(name):
    if name == 'TST':
        return ['-/-/-/PASSA FL NEXT']
    if name in ('CLC', 'SEC'):
        return [f'-/-/-/{name} FL NEXT']
    return [f'-/-/A/{name} FL NEXT']


OTHERS = [   # (opcode, komut, mod, adımlar)
    (0x00, 'HALT', 'imp', ['HALT NEXT']),
    (0x01, 'NOP', 'imp', ['NEXT']),
    (0x90, 'LDX', '#16', ['PC/MEM/XL/- PCINC', 'PC/MEM/XH/- PCINC NEXT']),
    (0x91, 'LDX', 'abs', [OP1, OP2, 'AR/MEM/XL/- ARINC', 'AR/MEM/XH/- NEXT']),
    (0x92, 'INX', 'imp', ['XINC NEXT']),
    (0x93, 'TAXL', 'imp', ['-/A/XL/- NEXT']),
    (0x94, 'TAXH', 'imp', ['-/A/XH/- NEXT']),
    (0x98, 'INCW', 'abs', [OP1, OP2, 'AR/MEM/A/INCB FL', 'AR/A/-/- MEMW ARINC',
                           'AR/MEM/A/ADCB0 FL', 'AR/A/-/- MEMW NEXT']),
    (0x99, 'DECW', 'abs', [OP1, OP2, 'AR/MEM/A/DECB FL', 'AR/A/-/- MEMW ARINC',
                           'AR/MEM/A/SBCB0 FL', 'AR/A/-/- MEMW NEXT']),
    (0xA0, 'PHA', 'imp', ['SP/A/-/- MEMW SPCNT SPDN NEXT']),
    (0xA1, 'PLA', 'imp', ['SPCNT', 'SP/MEM/A/PASSB NEXT']),
    (0xA2, 'JMP', 'abs', [OP1, 'PC/MEM/ARH/-', 'PCLD NEXT']),
    (0xA3, 'CALL', 'abs', [OP1, OP2, 'SP/PCH/-/- MEMW SPCNT SPDN',
                           'SP/PCL/-/- MEMW SPCNT SPDN PCLD NEXT']),
    (0xA4, 'RET', 'imp', ['SPCNT', 'SP/MEM/ARL/- SPCNT', 'SP/MEM/ARH/-', 'PCLD NEXT']),
    (0xA5, 'JMPI', 'ind', [OP1, OP2, 'AR/MEM/A/PASSB ARINC', 'AR/MEM/ARH/-',
                           '-/A/ARL/-', 'PCLD NEXT']),
]

BRANCH_TAKEN = [OP1, OP2, 'PCLD NEXT']
BRANCH_NOT_TAKEN = ['PCINC', 'PCINC NEXT']

BRANCHES = [   # cc = sıra; opcode = 0xB0 + cc
    ('BEQ', lambda z, c, n, v: z),
    ('BNE', lambda z, c, n, v: not z),
    ('BCS', lambda z, c, n, v: c),
    ('BCC', lambda z, c, n, v: not c),
    ('BMI', lambda z, c, n, v: n),
    ('BPL', lambda z, c, n, v: not n),
    ('BVS', lambda z, c, n, v: v),
    ('BVC', lambda z, c, n, v: not v),
    ('BLT', lambda z, c, n, v: n != v),
    ('BGE', lambda z, c, n, v: n == v),
    ('BGT', lambda z, c, n, v: not z and n == v),
    ('BLE', lambda z, c, n, v: z or n != v),
    ('BHI', lambda z, c, n, v: c and not z),
    ('BLS', lambda z, c, n, v: not c or z),
]

ALIASES = {'BHS': 'BCS', 'BLO': 'BCC'}


def _build():
    table = {}
    for i, (name, op, dst, fl) in enumerate(M_GROUP):
        for m, mode in enumerate(M_MODES):
            steps = _m_steps(name, op, dst, fl, mode)
            if steps is not None:
                code = 0x40 + 4 * i + m
                table[code] = Instr(code, name, mode, steps)
    for i, name in enumerate(U_GROUP):
        table[0x80 + i] = Instr(0x80 + i, name, 'imp', _u_steps(name))
    for code, name, mode, steps in OTHERS:
        table[code] = Instr(code, name, mode, steps)
    for cc, (name, cond) in enumerate(BRANCHES):
        table[0xB0 + cc] = Instr(0xB0 + cc, name, 'abs', cond=cond)
    return table


INSTRUCTIONS = _build()          # opcode -> Instr
BY_NAME = {(ins.mnemonic, ins.mode): code for code, ins in INSTRUCTIONS.items()}
MNEMONICS = sorted({ins.mnemonic for ins in INSTRUCTIONS.values()})
