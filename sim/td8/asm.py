"""TD-8 assembler (iki geçişli).

Yazım:
    ; yorum
    SABIT = $F800             sabit tanımı (ya da: .equ SABIT, $F800)
    etiket: LDA #$41          etiket ve komut aynı satırda olabilir
            LDA #<mesaj       < alt byte, > üst byte
            STA $F000+64*2+5
            LDA (X+)
            JMPI (tablo)
            .org $0000
            .byte 1, 2, "metin"
            .word etiket, $1234
            .text "metin"     (sonlandırıcısız)
            .asciz "metin"    (0 ile biter)
            .res 16           (16 sıfır byte)

Sayılar: $1F, 0x1F, %1010, 0b1010, 31, 'A'. İşlemler: + - * / & | ^ << >> ~ ( ).
Komut adları büyük-küçük harf duyarsız; etiketler duyarlı.
"""

import re

from . import isa


class AsmError(Exception):
    def __init__(self, line_no, msg, filename='<kaynak>'):
        super().__init__(f'{filename}:{line_no}: {msg}')
        self.line_no = line_no


class Program:
    def __init__(self):
        self.image = bytearray(0x10000)
        self.used = bytearray(0x10000)    # 1 = bu adrese byte yazıldı
        self.symbols = {}
        self.listing = []                 # (satır no, adres, byte'lar, kaynak satır)

    def rom(self, size=0x8000):
        """ROM bölgesi (0000'dan başlayarak), flash'a yazılacak imaj."""
        return bytes(self.image[:size])

    def ranges(self):
        """Yazılmış adres aralıkları: [(başlangıç, uzunluk), ...]."""
        out, start = [], None
        for addr in range(0x10001):
            on = addr < 0x10000 and self.used[addr]
            if on and start is None:
                start = addr
            elif not on and start is not None:
                out.append((start, addr - start))
                start = None
        return out


# ---------------------------------------------------------------------------
# İfade çözümleyici
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"""\s*(?:
    (?P<num>\$[0-9A-Fa-f]+|0[xX][0-9A-Fa-f]+|%[01]+|0[bB][01]+|\d+)
  | (?P<chr>'(?:\\.|[^'\\])')
  | (?P<id>[A-Za-z_.][\w.]*)
  | (?P<op><<|>>|[-+*/&|^~()<>])
)""", re.VERBOSE)

_ESCAPES = {'n': 10, 'r': 13, 't': 9, '0': 0, '\\': 92, "'": 39, '"': 34}


def _char_value(lit):
    body = lit[1:-1]
    if body.startswith('\\'):
        return _ESCAPES[body[1]]
    return ord(body)


def _number(text):
    if text.startswith('$'):
        return int(text[1:], 16)
    if text[:2].lower() == '0x':
        return int(text[2:], 16)
    if text.startswith('%'):
        return int(text[1:], 2)
    if text[:2].lower() == '0b':
        return int(text[2:], 2)
    return int(text)


class _Expr:
    def __init__(self, text, symbols, final):
        self.tokens = []
        pos = 0
        text = text.strip()
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if not m or m.end() == pos:
                raise ValueError(f'ifade çözülemedi: {text[pos:]!r}')
            kind = m.lastgroup
            self.tokens.append((kind, m.group(kind)))
            pos = m.end()
        self.i = 0
        self.symbols = symbols
        self.final = final
        self.unresolved = False

    def peek(self):
        return self.tokens[self.i][1] if self.i < len(self.tokens) else None

    def take(self):
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def parse(self):
        if not self.tokens:
            raise ValueError('boş ifade')
        v = self._binary(0)
        if self.i != len(self.tokens):
            raise ValueError(f'fazla ifade parçası: {self.peek()!r}')
        return v

    _LEVELS = [('|',), ('^',), ('&',), ('<<', '>>'), ('+', '-'), ('*', '/')]

    def _binary(self, level):
        if level == len(self._LEVELS):
            return self._unary()
        v = self._binary(level + 1)
        while self.peek() in self._LEVELS[level]:
            op = self.take()[1]
            rhs = self._binary(level + 1)
            if op == '|':
                v |= rhs
            elif op == '^':
                v ^= rhs
            elif op == '&':
                v &= rhs
            elif op == '<<':
                v <<= rhs
            elif op == '>>':
                v >>= rhs
            elif op == '+':
                v += rhs
            elif op == '-':
                v -= rhs
            elif op == '*':
                v *= rhs
            elif op == '/':
                v = v // rhs if rhs else 0
        return v

    def _unary(self):
        tok = self.peek()
        if tok in ('-', '~', '<', '>', '+'):
            self.take()
            v = self._unary()
            return {'-': -v, '~': ~v, '<': v & 0xFF, '>': (v >> 8) & 0xFF, '+': v}[tok]
        return self._primary()

    def _primary(self):
        if self.i >= len(self.tokens):
            raise ValueError('ifade eksik')
        kind, text = self.take()
        if kind == 'num':
            return _number(text)
        if kind == 'chr':
            return _char_value(text)
        if kind == 'id':
            if text in self.symbols:
                return self.symbols[text]
            if self.final:
                raise ValueError(f'tanımsız etiket: {text}')
            self.unresolved = True
            return 0
        if text == '(':
            v = self._binary(0)
            if self.peek() != ')':
                raise ValueError("')' eksik")
            self.take()
            return v
        raise ValueError(f'beklenmeyen {text!r}')


def evaluate(text, symbols, final=True):
    return _Expr(text, symbols, final).parse()


# ---------------------------------------------------------------------------
# Satır çözümleme
# ---------------------------------------------------------------------------

_LABEL = re.compile(r'^\s*([A-Za-z_.][\w.]*)\s*:(?!=)')
_CONST = re.compile(r'^\s*([A-Za-z_][\w.]*)\s*=\s*(.+)$')


def _strip_comment(line):
    out, quote = [], None
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote and (len(out) < 2 or out[-2] != '\\'):
                quote = None
        elif ch in '"\'':
            quote = ch
            out.append(ch)
        elif ch == ';':
            break
        else:
            out.append(ch)
    return ''.join(out).rstrip()


def _split_args(text):
    """Virgülle ayırır; tırnak içindeki virgülleri korur."""
    args, cur, quote = [], [], None
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote and cur[-2:-1] != ['\\']:
                quote = None
        elif ch in '"\'':
            quote = ch
            cur.append(ch)
        elif ch == ',':
            args.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur or args:
        args.append(''.join(cur).strip())
    return [a for a in args if a != '']


def _string_bytes(lit):
    body = lit[1:-1]
    out, i = [], 0
    while i < len(body):
        ch = body[i]
        if ch == '\\' and i + 1 < len(body):
            out.append(_ESCAPES[body[i + 1]])
            i += 2
        else:
            out.append(ord(ch))
            i += 1
    return out


def _mode(mnemonic, operand):
    op = operand.replace(' ', '').upper()
    if operand == '':
        return 'imp', None
    if operand.startswith('#'):
        return ('#16' if mnemonic == 'LDX' else '#'), operand[1:]
    if op == '(X)':
        return '(X)', None
    if op == '(X+)':
        return '(X+)', None
    if mnemonic == 'JMPI':
        inner = operand.strip()
        if not (inner.startswith('(') and inner.endswith(')')):
            raise ValueError('JMPI yazımı: JMPI (adres)')
        return 'ind', inner[1:-1]
    return 'abs', operand


def assemble(source, filename='<kaynak>'):
    """Kaynağı çevirir, Program döndürür. Hata varsa AsmError."""
    lines = source.splitlines()
    symbols = {}
    for final in (False, True):
        prog = Program()
        prog.symbols = symbols
        pc = 0
        for no, raw in enumerate(lines, 1):
            line = _strip_comment(raw)
            try:
                pc = _line(prog, line, raw, no, pc, symbols, final)
            except AsmError:
                raise
            except (ValueError, KeyError) as e:
                raise AsmError(no, str(e), filename) from None
    return prog


def _emit(prog, addr, data, final, no, raw):
    if final:
        for i, b in enumerate(data):
            a = (addr + i) & 0xFFFF
            if prog.used[a]:
                raise ValueError(f'{a:04X} adresine iki kez yazılıyor')
            prog.image[a] = b & 0xFF
            prog.used[a] = 1
        prog.listing.append((no, addr, bytes(b & 0xFF for b in data), raw))
    return (addr + len(data)) & 0xFFFF


def _line(prog, line, raw, no, pc, symbols, final):
    m = _LABEL.match(line)
    if m:
        name = m.group(1)
        if not final:
            if name in symbols:
                raise ValueError(f'etiket iki kez tanımlı: {name}')
            symbols[name] = pc
        line = line[m.end():]
    m = _CONST.match(line)
    if m:
        name, expr = m.groups()
        e = _Expr(expr, symbols, final)
        value = e.parse()
        if not final and name in symbols and not e.unresolved and symbols[name] != value:
            raise ValueError(f'sabit iki kez tanımlı: {name}')
        symbols[name] = value
        return pc
    text = line.strip()
    if not text:
        return pc
    parts = text.split(None, 1)
    word = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ''

    if word.startswith('.'):
        d = word.lower()
        if d == '.org':
            return evaluate(rest, symbols, True) & 0xFFFF
        if d == '.equ':
            name, expr = _split_args(rest)
            symbols[name] = evaluate(expr, symbols, final)
            return pc
        if d in ('.byte', '.db', '.text', '.asciz'):
            data = []
            for arg in _split_args(rest):
                if arg.startswith('"'):
                    data.extend(_string_bytes(arg))
                else:
                    v = evaluate(arg, symbols, final)
                    if final and not -128 <= v <= 255:
                        raise ValueError(f'byte aralık dışı: {v}')
                    data.append(v & 0xFF)
            if d == '.asciz':
                data.append(0)
            return _emit(prog, pc, data, final, no, raw)
        if d in ('.word', '.dw'):
            data = []
            for arg in _split_args(rest):
                v = evaluate(arg, symbols, final) & 0xFFFF
                data += [v & 0xFF, v >> 8]
            return _emit(prog, pc, data, final, no, raw)
        if d in ('.res', '.ds'):
            return _emit(prog, pc, [0] * evaluate(rest, symbols, True), final, no, raw)
        raise ValueError(f'bilinmeyen yönerge: {word}')

    mnemonic = isa.ALIASES.get(word.upper(), word.upper())
    if mnemonic not in isa.MNEMONICS:
        raise ValueError(f'bilinmeyen komut: {word}')
    mode, expr = _mode(mnemonic, rest)
    code = isa.BY_NAME.get((mnemonic, mode))
    if code is None:
        raise ValueError(f'{mnemonic} komutu bu adresleme modunu desteklemiyor: {rest or "(operand yok)"}')
    data = [code]
    size = isa.MODE_SIZE[mode]
    if size > 1:
        v = evaluate(expr, symbols, final)
        if size == 2:
            if final and not -128 <= v <= 255:
                raise ValueError(f'8-bit değer aralık dışı: {v}')
            data.append(v & 0xFF)
        else:
            if final and not -32768 <= v <= 0xFFFF:
                raise ValueError(f'16-bit değer aralık dışı: {v}')
            data += [v & 0xFF, (v >> 8) & 0xFF]
    return _emit(prog, pc, data, final, no, raw)
