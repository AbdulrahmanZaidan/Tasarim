"""Assembly yazıcı ve işlenen (operand) gösterimi.

İşlenen = byte kaynaklarının listesi (en düşük byte önce). Her byte:
    imm: anında değer (#$05 ya da #<(etiket+2))
    mem: mutlak adres (etiket+ofset ya da $F800)
    acc: şu an A'da (yalnız 0. byte olabilir; hemen kullanılmalı)
16-bit değerler bellekte (değişkenin kendisi ya da bir geçici) durur; A yalnız
o an işlenen byte'ı taşır.
"""

import re


class Byte:
    __slots__ = ('kind', 'base', 'off', 'val', 'expr', 'part')

    def __init__(self, kind, base=None, off=0, val=None, expr=None, part=None):
        self.kind, self.base, self.off = kind, base, off
        self.val, self.expr, self.part = val, expr, part

    @property
    def text(self):
        if self.kind == 'imm':
            if self.val is not None:
                return f'#${self.val:02X}'
            return f'#{self.part}({self.expr})'
        if self.kind == 'mem':
            return addr_text(self.base, self.off)
        raise AssertionError('A içindeki byte için metin yok')

    def key(self):
        """Aynı bellek hücresi mi karşılaştırması için."""
        if self.kind != 'mem':
            return None
        if isinstance(self.base, int):
            return (None, (self.base + self.off) & 0xFFFF)
        return (self.base, self.off)

    def __repr__(self):
        return 'A' if self.kind == 'acc' else self.text


ACC = Byte('acc')


def addr_text(base, off=0):
    if isinstance(base, int):
        return f'${(base + off) & 0xFFFF:04X}'
    if off == 0:
        return base
    return f'{base}+{off}' if off > 0 else f'{base}-{-off}'


def imm(v, n=2):
    v &= 0xFFFF
    return [Byte('imm', val=(v >> (8 * i)) & 0xFF) for i in range(n)]


def imm_sym(expr, n=2):
    return [Byte('imm', expr=expr, part='<'), Byte('imm', expr=expr, part='>')][:n]


def mem(base, off=0, n=2):
    return [Byte('mem', base, off + i) for i in range(n)]


def has_acc(op):
    return op is not None and any(b.kind == 'acc' for b in op)


def is_imm_val(b, v):
    return b.kind == 'imm' and b.val == v


# Komutların A ve flag'lere etkisi (peephole için)
_KEEP_A_FLAGS = {'STA', 'LDX', 'INX', 'TAXL', 'TAXH', 'PHA', 'JMP', 'NOP',
                 'BEQ', 'BNE', 'BCS', 'BCC', 'BHS', 'BLO', 'BMI', 'BPL', 'BVS', 'BVC',
                 'BLT', 'BGE', 'BGT', 'BLE', 'BHI', 'BLS'}
_KEEP_A_SET_FLAGS = {'CMP', 'CPC', 'BIT'}
_A_FROM_RESULT = {'ADD', 'SUB', 'AND', 'OR', 'XOR', 'INC', 'DEC', 'NOT', 'NEG',
                  'SHL', 'ROL', 'SHR', 'ROR', 'ASR', 'SEX'}      # Z, N = sonuçtan
_TEMP_RE = re.compile(r'^_\w+\.\d+(\+\d+)?$')


def is_temp(text):
    return bool(_TEMP_RE.match(text))


class Emitter:
    def __init__(self):
        self.out = []           # ('ins', komut, işlenen) | ('label', ad) | ('text', satır) | işaret
        self._reset()

    def _reset(self):
        self.a_imm = None       # A'daki bilinen anında değer metni
        self.a_tmp = None       # A'ya eşit olan geçici
        self.flags_a = False    # Z/N, A'nın değerini mi gösteriyor

    # --- yazma ----------------------------------------------------------------
    def ins(self, m, opnd=''):
        if m == 'LDA':
            if opnd.startswith('#') and opnd == self.a_imm:
                return
            if self.a_tmp is not None and opnd == self.a_tmp:
                return
        if m == 'TST' and self.flags_a:
            return
        self.out.append(('ins', m, opnd))
        self._track(m, opnd)

    def _track(self, m, opnd):
        if m == 'LDA':
            self.a_imm = opnd if opnd.startswith('#') else None
            self.a_tmp = opnd if is_temp(opnd) else None
            self.flags_a = False
        elif m == 'STA':
            if is_temp(opnd):
                self.a_tmp = opnd
        elif m in _KEEP_A_FLAGS:
            pass
        elif m in _KEEP_A_SET_FLAGS:
            self.flags_a = False
        elif m in ('TST', 'CLC', 'SEC'):
            self.flags_a = True
        elif m in _A_FROM_RESULT:
            self.a_imm = self.a_tmp = None
            self.flags_a = True
        else:                   # ADC, SBC (zincirli Z), PLA, CALL, RET, INCW, ...
            self._reset()

    def label(self, name):
        if (self.out and self.out[-1][0] == 'ins'
                and self.out[-1][1] == 'JMP' and self.out[-1][2] == name):
            self.out.pop()      # kendinden hemen sonraki etikete atlama
        self.out.append(('label', name))
        self._reset()

    def text(self, line):
        self.out.append(('text', line))

    def comment(self, text):
        self.out.append(('text', f'        ; {text}'))

    def mark(self):
        """Koda bir işaret koyar (çıktıya yazılmaz). Sonradan buraya komut eklenebilir."""
        m = ('mark', object())
        self.out.append(m)
        return m

    def _find(self, mark):
        for i in range(len(self.out) - 1, -1, -1):
            if self.out[i] is mark:
                return i
        raise AssertionError('işaret bulunamadı')

    def since(self, mark):
        """İşaretten sonra komut ya da etiket yazıldı mı?"""
        i = self._find(mark)
        return any(e[0] in ('ins', 'label') for e in self.out[i + 1:])

    def insert(self, mark, m, opnd):
        """İşaretin yerine komut ekler (yalnız A'yı ve flag'leri değiştirmeyen STA)."""
        assert m == 'STA'
        self.out.insert(self._find(mark), ('ins', m, opnd))

    def last_is_exit(self):
        """Son komut RET/JMP mi (ardından etiket gelmediyse)?"""
        for entry in reversed(self.out):
            if entry[0] in ('text', 'mark'):
                continue
            return entry[0] == 'ins' and entry[1] in ('RET', 'JMP', 'HALT')
        return False

    def lines(self):
        out = []
        for entry in self.out:
            if entry[0] == 'ins':
                _, m, opnd = entry
                out.append(f'        {m} {opnd}'.rstrip())
            elif entry[0] == 'label':
                out.append(f'{entry[1]}:')
            elif entry[0] == 'text':
                out.append(entry[1])
        return out
