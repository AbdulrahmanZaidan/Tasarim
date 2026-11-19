"""C kaynağını token'lara ayırır.

Token türleri: 'id', 'kw', 'num', 'chr', 'str', 'op', 'eof'.
Her token dosya/satır bilgisini, satır başında olup olmadığını (`bol`, ön işlemci
yönergeleri için) ve önünde boşluk olup olmadığını (`space`) taşır.
'num' token'ının değeri (değer, işaretsiz_mi, onluk_mu) üçlüsüdür.
"""

from .errors import CompileError

KEYWORDS = {
    'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
    'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if', 'int',
    'long', 'register', 'return', 'short', 'signed', 'sizeof', 'static',
    'struct', 'switch', 'typedef', 'union', 'unsigned', 'void', 'volatile',
    'while', 'inline', 'asm',
}

OPERATORS = sorted("""
<<= >>= ... -> ++ -- << >> <= >= == != && || += -= *= /= %= &= ^= |= ##
# ( ) [ ] { } , ; : ? . + - * / % & | ^ ~ ! < > =
""".split(), key=len, reverse=True)

ESCAPES = {'n': 10, 't': 9, 'r': 13, 'a': 7, 'b': 8, 'f': 12, 'v': 11,
           '\\': 92, "'": 39, '"': 34, '?': 63}


class Token:
    __slots__ = ('kind', 'value', 'text', 'file', 'line', 'bol', 'space')

    def __init__(self, kind, value, text, file, line, bol, space):
        self.kind, self.value, self.text = kind, value, text
        self.file, self.line, self.bol, self.space = file, line, bol, space

    def is_op(self, *ops):
        return self.kind == 'op' and self.value in ops

    def is_kw(self, *kws):
        return self.kind == 'kw' and self.value in kws

    def __repr__(self):
        return f'Token({self.kind}, {self.value!r}, {self.line})'


def _escape(src, i, file, line):
    """src[i] ters bölüden sonraki karakter. (değer, yeni i) döndürür."""
    ch = src[i] if i < len(src) else ''
    if ch in ESCAPES:
        return ESCAPES[ch], i + 1
    if ch and ch in '01234567':
        j = i
        while j < len(src) and j < i + 3 and src[j] in '01234567':
            j += 1
        return int(src[i:j], 8) & 0xFF, j
    if ch == 'x':
        j = i + 1
        while j < len(src) and src[j] in '0123456789abcdefABCDEF':
            j += 1
        if j == i + 1:
            raise CompileError('\\x kaçışından sonra onaltılık rakam bekleniyor', file, line)
        return int(src[i + 1:j], 16) & 0xFF, j
    raise CompileError(f'bilinmeyen kaçış dizisi: \\{ch}', file, line)


def _quoted(src, i, quote, file, line):
    """src[i] açılış tırnağı. (byte listesi, kapanıştan sonraki i) döndürür."""
    what = 'karakter sabiti' if quote == "'" else 'metin sabiti'
    j, n, out = i + 1, len(src), []
    while j < n and src[j] != quote:
        if src[j] == '\n':
            raise CompileError(f'kapanmamış {what}', file, line)
        if src[j] == '\\':
            v, j = _escape(src, j + 1, file, line)
        else:
            v, j = ord(src[j]), j + 1
            if v > 255:
                raise CompileError(f'{what} içinde ASCII dışı karakter', file, line)
        out.append(v)
    if j >= n:
        raise CompileError(f'kapanmamış {what}', file, line)
    return out, j + 1


def tokenize(src, file='<kaynak>'):
    toks = []
    i, n, line = 0, len(src), 1
    bol, space = True, False

    def add(kind, value, text):
        nonlocal bol, space
        toks.append(Token(kind, value, text, file, line, bol, space))
        bol = space = False

    while i < n:
        ch = src[i]
        if ch == '\n':
            line += 1
            i += 1
            bol, space = True, True
            continue
        if ch in ' \t\r\f\v':
            i += 1
            space = True
            continue
        if ch == '\\' and src[i + 1:i + 2] == '\n':        # satır devamı
            i += 2
            line += 1
            space = True
            continue
        if ch == '\\' and src[i + 1:i + 3] == '\r\n':
            i += 3
            line += 1
            space = True
            continue
        if src.startswith('//', i):
            while i < n and src[i] != '\n':
                i += 1
            space = True
            continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            if j < 0:
                raise CompileError('kapanmamış /* yorumu', file, line)
            line += src.count('\n', i, j)
            i = j + 2
            space = True
            continue
        if ch.isalpha() or ch == '_':
            j = i
            while j < n and (src[j].isalnum() or src[j] == '_'):
                j += 1
            word = src[i:j]
            add('kw' if word in KEYWORDS else 'id', word, word)
            i = j
            continue
        if ch.isdigit() or (ch == '.' and src[i + 1:i + 2].isdigit()):
            j = i
            while j < n and (src[j].isalnum() or src[j] in '._'):
                j += 1
            text = src[i:j]
            add('num', _number(text, file, line), text)
            i = j
            continue
        if ch == "'":
            vals, j = _quoted(src, i, "'", file, line)
            if len(vals) != 1:
                raise CompileError('karakter sabiti tam bir karakter olmalı', file, line)
            add('chr', vals[0], src[i:j])
            i = j
            continue
        if ch == '"':
            vals, j = _quoted(src, i, '"', file, line)
            add('str', bytes(vals), src[i:j])
            i = j
            continue
        for op in OPERATORS:
            if src.startswith(op, i):
                add('op', op, op)
                i += len(op)
                break
        else:
            raise CompileError(f'beklenmeyen karakter: {ch!r}', file, line)
    toks.append(Token('eof', None, '', file, line, True, True))
    return toks


def _number(text, file, line):
    """Tamsayı sabiti: (değer, işaretsiz_mi, onluk_mu)."""
    t = text.lower()
    is_hex = t.startswith('0x')
    if '.' in t or (not is_hex and ('e' in t or t.endswith('f'))):
        raise CompileError(f'kayan noktalı sayılar desteklenmiyor: {text}', file, line)
    suffix = ''
    while t and t[-1] in 'ul':
        suffix += t[-1]
        t = t[:-1]
    if 'l' in suffix:
        raise CompileError(f'long desteklenmiyor: {text}', file, line)
    try:
        if is_hex:
            v, dec = int(t[2:], 16), False
        elif t.startswith('0b'):
            v, dec = int(t[2:], 2), False
        elif t.startswith('0') and len(t) > 1:
            v, dec = int(t[1:], 8), False
        else:
            v, dec = int(t, 10), True
    except ValueError:
        raise CompileError(f'geçersiz sayı: {text}', file, line) from None
    if v > 0xFFFF:
        raise CompileError(f'sabit 16 bite sığmıyor: {text}', file, line)
    return (v, 'u' in suffix, dec)
