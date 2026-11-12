"""tdcc: TD-8 C derleyicisi testleri.

Derleme -> assembler -> emülatör (RefEmu; bazıları MicroEmu'da da) -> bellek/ekran/LED.
En önemlisi fark testi: rastgele ifadeler ve yan etkili deyimler hem TD-8'de çalıştırılır
hem de C kurallarını (8/16-bit sarma, işaret, terfi) uygulayan bağımsız bir Python
referansında hesaplanır; sonuçlar eşit olmalı.

Çalıştırma (sim/ klasöründe): py -3 -m unittest tests.test_tdcc
"""

import random
import re
import unittest
from pathlib import Path

from td8 import isa
from td8.bus import Bus
from tdcc import CompileError, build, code_size, compile_c, run
from tdcc import nodes as N
from tdcc.lexer import tokenize
from tdcc.parser import parse
from tdcc.preproc import preprocess

SIM = Path(__file__).resolve().parent.parent
EXAMPLES = SIM / 'examples'


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def compile_run(src, micro=False, cycles=5_000_000, bus=None, keys=None):
    res = build(src)
    bus, cpu = run(res.program, micro=micro, max_cycles=cycles, bus=bus, keys=keys)
    if not cpu.halted:
        raise AssertionError(f'program durmadı ({cpu.cycles} çevrim)')
    return Machine(res, bus, cpu)


class Machine:
    def __init__(self, res, bus, cpu):
        self.res, self.bus, self.cpu = res, bus, cpu

    def addr(self, name):
        return self.res.program.symbols['_' + name]

    def get(self, name, size=2, signed=True, index=0):
        a = self.addr(name) + index * size
        v = int.from_bytes(self.bus.mem[a:a + size], 'little')
        if signed and v >= 1 << (8 * size - 1):
            v -= 1 << (8 * size)
        return v

    def i(self, name, index=0):
        return self.get(name, 2, True, index)

    def u(self, name, index=0):
        return self.get(name, 2, False, index)

    def c(self, name, index=0):
        return self.get(name, 1, False, index)

    def sc(self, name, index=0):
        return self.get(name, 1, True, index)

    def ints(self, name, n):
        return [self.i(name, k) for k in range(n)]

    def text(self, row):
        return self.bus.screen()[row]


def compile_error(src, filename='t.c'):
    try:
        compile_c(src, filename)
    except CompileError as e:
        return e
    raise AssertionError('derleme hatası bekleniyordu')


def parse_expr(text):
    prog = parse(preprocess(f'int x = {text};'))
    return prog.items[0].init


def shape(e):
    """İfade ağacını kısa metne çevirir (parser testleri için)."""
    if isinstance(e, N.Num):
        return str(e.value)
    if isinstance(e, N.Ident):
        return e.name
    if isinstance(e, (N.Binary, N.Logical)):
        return f'({shape(e.left)} {e.op} {shape(e.right)})'
    if isinstance(e, N.Unary):
        return f'({e.op}{shape(e.operand)})'
    if isinstance(e, N.Deref):
        return f'(*{shape(e.operand)})'
    if isinstance(e, N.AddrOf):
        return f'(&{shape(e.operand)})'
    if isinstance(e, N.Assign):
        return f'({shape(e.target)} = {shape(e.value)})'
    if isinstance(e, N.CompoundAssign):
        return f'({shape(e.target)} {e.op}= {shape(e.value)})'
    if isinstance(e, N.Cond):
        return f'({shape(e.cond)} ? {shape(e.then)} : {shape(e.other)})'
    if isinstance(e, N.Comma):
        return f'({shape(e.left)}, {shape(e.right)})'
    if isinstance(e, N.IncDec):
        return f'({e.op}{shape(e.target)})' if e.prefix else f'({shape(e.target)}{e.op})'
    if isinstance(e, N.Index):
        return f'{shape(e.base)}[{shape(e.index)}]'
    if isinstance(e, N.Call):
        return f'{shape(e.func)}(' + ', '.join(shape(a) for a in e.args) + ')'
    if isinstance(e, N.Cast):
        return f'(({e.to}){shape(e.operand)})'
    if isinstance(e, N.SizeofType):
        return f'sizeof({e.target})'
    if isinstance(e, N.SizeofExpr):
        return f'sizeof {shape(e.operand)}'
    return type(e).__name__


# ---------------------------------------------------------------------------
# Lexer, ön işlemci, parser
# ---------------------------------------------------------------------------

class TestLexer(unittest.TestCase):
    def kinds(self, src):
        return [(t.kind, t.value) for t in tokenize(src)[:-1]]

    def test_tokens(self):
        self.assertEqual(self.kinds('int x=0x1F;'), [
            ('kw', 'int'), ('id', 'x'), ('op', '='), ('num', (31, False, False)), ('op', ';')])
        self.assertEqual([t.value for t in tokenize('a<<=b>>c->d...e')[:-1]],
                         ['a', '<<=', 'b', '>>', 'c', '->', 'd', '...', 'e'])

    def test_numbers(self):
        vals = [t.value for t in tokenize('10 0x10 010 0b101 40000 7u 0xFFFFu')[:-1]]
        self.assertEqual(vals, [(10, False, True), (16, False, False), (8, False, False),
                                (5, False, False), (40000, False, True), (7, True, True),
                                (65535, True, False)])

    def test_chars_and_strings(self):
        toks = tokenize(r"'A' '\n' '\0' '\x41' '\\' " + r'"a\tb" "c\"d"')[:-1]
        self.assertEqual([t.value for t in toks],
                         [65, 10, 0, 65, 92, b'a\tb', b'c"d'])

    def test_comments_and_lines(self):
        toks = tokenize('a /* bir\niki */ b // yorum\nc')
        self.assertEqual([(t.value, t.line) for t in toks[:-1]], [('a', 1), ('b', 2), ('c', 3)])

    def test_errors(self):
        for src, msg in [('/* kapanmamış', 'kapanmamış /* yorumu'),
                         ('"abc', 'kapanmamış metin'), ("'ab'", 'tam bir karakter'),
                         ('1.5', 'kayan noktalı'), ('10L', 'long'), ('70000', '16 bite'),
                         ('a @ b', 'beklenmeyen karakter'), (r"'\q'", 'kaçış')]:
            with self.assertRaises(CompileError) as cm:
                tokenize('\n' + src, 'x.c')
            self.assertIn(msg, str(cm.exception))
            self.assertTrue(str(cm.exception).startswith('x.c:2:'), str(cm.exception))


class TestPreprocessor(unittest.TestCase):
    def values(self, src):
        return [t.value for t in preprocess(src)[:-1]]

    def test_define_and_conditionals(self):
        src = '#define A 5\n#define B (A + 1)\n#ifdef A\nx = B;\n#else\ny;\n#endif\n#ifndef A\nz;\n#endif\n'
        self.assertEqual(self.values(src), ['x', '=', '(', (5, False, True), '+',
                                            (1, False, True), ')', ';'])

    def test_undef_and_if(self):
        src = '#define A 1\n#undef A\n#ifdef A\nbad;\n#endif\n#if 0\nbad2;\n#else\nok;\n#endif\n'
        self.assertEqual(self.values(src), ['ok', ';'])

    def test_include_hw(self):
        toks = preprocess('#include "hw.h"\nLEDS = KRDY;')
        text = ' '.join(t.text for t in toks[:-1])
        self.assertEqual(text, '( * ( volatile char * ) 0xF800 ) = 0x80 ;')
        self.assertEqual(toks[0].line, 2)          # makro kullanıldığı satırı taşır

    def test_errors(self):
        for src, msg in [('#define F(x) x\n', 'fonksiyon benzeri makro'),
                         ('#include "yok_boyle.h"\n', 'bulunamadı'),
                         ('#ifdef X\n', '#endif eksik'), ('#endif\n', '#if yok'),
                         ('#foo\n', 'bilinmeyen ön işlemci'), ('#error dur\n', '#error dur')]:
            with self.assertRaises(CompileError) as cm:
                preprocess(src)
            self.assertIn(msg, str(cm.exception))


class TestParser(unittest.TestCase):
    def test_precedence(self):
        cases = {
            'a + b * c': '(a + (b * c))',
            'a - b - c': '((a - b) - c)',
            'a << 1 + 2': '(a << (1 + 2))',
            'a & b == c': '(a & (b == c))',
            'a | b ^ c & d': '(a | (b ^ (c & d)))',
            'a || b && c': '(a || (b && c))',
            'a < b == c > d': '((a < b) == (c > d))',
            'a ? b : c ? d : e': '(a ? b : (c ? d : e))',
            'a = b = c': '(a = (b = c))',
            'a += b -= 2': '(a += (b -= 2))',
            '-a * !b': '((-a) * (!b))',
            '*p++': '(*(p++))',
            '++*p': '(++(*p))',
            '&a[3]': '(&a[3])',
            '(char)a + 1': '(((char)a) + 1)',
            'sizeof(int) * 2': '(sizeof(int) * 2)',
            'sizeof a + 1': '(sizeof a + 1)',
            'f(a, b + 1)[2]': 'f(a, (b + 1))[2]',
            '~a % b / c': '(((~a) % b) / c)',
        }
        for src, want in cases.items():
            self.assertEqual(shape(parse_expr(src)), want, src)

    def test_comma_in_statement(self):
        prog = parse(preprocess('void f(void) { a = 1, b = 2; }'))
        self.assertEqual(shape(prog.items[0].body.items[0].expr), '((a = 1), (b = 2))')

    def test_declarations(self):
        prog = parse(preprocess(
            'const char *s; char *const t = 0; int a[3][4]; int *ap[5]; int (*pa)[4];\n'
            'volatile unsigned char v; signed char sc; unsigned u; short h;\n'
            'static int f(int x, char *p, int arr[]);'))
        types = {d.name: str(d.ctype) for d in prog.items if isinstance(d, N.VarDecl)}
        self.assertEqual(types['s'], 'const char*')
        self.assertEqual(types['t'], 'char* const')
        self.assertEqual(types['ap'], 'int*[5]')
        self.assertEqual(types['pa'], 'int[4]*')
        self.assertEqual(types['v'], 'volatile char')
        self.assertEqual(types['sc'], 'signed char')
        self.assertEqual(types['u'], 'unsigned int')
        self.assertEqual(types['h'], 'int')
        f = prog.items[-1]
        self.assertIsInstance(f, N.FuncDecl)
        self.assertEqual([str(t) for t in f.ctype.params], ['int', 'char*', 'int*'])

    def test_enum(self):
        m = compile_run('enum yon { SAG, SOL = 5, YUKARI };\nint a, b;\n'
                        'int main(void) { a = SOL; b = YUKARI + SAG; return 0; }')
        self.assertEqual((m.i('a'), m.i('b')), (5, 6))

    def test_errors(self):
        cases = [
            ('int main(void) {\n  int a = 3\n  return a;\n}', 3, "';' bekleniyor"),
            ('struct s { int a; };', 1, 'struct desteklenmiyor'),
            ('union u { int a; };', 1, 'union desteklenmiyor'),
            ('typedef int T;', 1, 'typedef desteklenmiyor'),
            ('long x;', 1, 'long desteklenmiyor'),
            ('float x;', 1, 'float desteklenmiyor'),
            ('int main(void) {\n goto son;\n}', 2, 'goto desteklenmiyor'),
            ('int (*fp)(int);', 1, 'fonksiyon işaretçisi'),
            ('int f(a, b) int a; { return 0; }', 1, 'K&R'),
            ('int f(int a, ...);', 1, 'değişken sayıda'),
            ('int main(void) {\n  p->x = 1;\n}', 2, 'struct/union üyesi'),
            ('int main(void) { return 0;', 1, "'}' eksik"),
            ('int main(void) {\n  x = (1 + ;\n}', 2, 'ifade bekleniyor'),
        ]
        for src, line, msg in cases:
            e = compile_error(src)
            self.assertIn(msg, e.msg, src)
            self.assertEqual(e.line, line, f'{src}: {e}')


# ---------------------------------------------------------------------------
# Fark testi: rastgele programlar, bağımsız Python referansı
# ---------------------------------------------------------------------------
# Tip: (C adı, bit, işaretli). Referans derleyicinin kodunu kullanmaz.

CH = ('char', 8, False)
SC = ('signed char', 8, True)
IN = ('int', 16, True)
UN = ('unsigned', 16, False)
CTYPES = [CH, SC, IN, UN]
LIMITS = {CH: [0, 1, 2, 127, 128, 254, 255], SC: [0, 1, -1, 127, -128, -2, 64],
          IN: [0, 1, -1, 2, 32767, -32768, 255, 256, -256, 1000, -1000],
          UN: [0, 1, 2, 65535, 32768, 32767, 255, 256, 40000]}
ARITH = ['+', '-', '*', '/', '%', '<<', '>>', '&', '|', '^']
RELS = ['<', '<=', '>', '>=', '==', '!=', '&&', '||']
MULCONST = [1, 2, 3, 4, 5, 7, 8, 10, 16, 64, 100, 128, 255, 256, 1000, 1024,
            -1, -2, -4, -8, 3]


def cwrap(v, t):
    m = 1 << t[1]
    v %= m
    if t[2] and v >= m >> 1:
        v -= m
    return v


def cpromote(t):
    return IN if t[1] == 8 else t


def cconv(a, b):
    a, b = cpromote(a), cpromote(b)
    return UN if (not a[2] or not b[2]) else IN


class DivByZero(Exception):
    pass


class Ref:
    """C ifadelerinin referans değerlendiricisi. env: ad -> değer ya da liste."""

    def __init__(self, env, ptrs):
        self.env = env
        self.ptrs = ptrs                # işaretçi adı -> (dizi adı, taban indeksi)

    def slot(self, lv):
        """Sol değerin (kap, indeks) çifti."""
        k = lv[0]
        if k == 'var':
            return self.env, lv[1]
        if k == 'arr':
            i, _ = self.ev(lv[3])
            return self.env[lv[1]], i
        arr, base = self.ptrs[lv[1]]                    # 'deref'
        return self.env[arr], base + lv[3]

    def ev(self, e):
        k = e[0]
        if k in ('var', 'arr', 'deref'):
            box, i = self.slot(e)
            return box[i], e[2]
        if k == 'const':
            return e[1], e[2]
        if k == 'cast':
            v, _ = self.ev(e[2])
            return cwrap(v, e[1]), e[1]
        if k == 'un':
            v, t = self.ev(e[2])
            if e[1] == '!':
                return int(v == 0), IN
            t = cpromote(t)
            v = cwrap(v, t)
            return cwrap(-v if e[1] == '-' else ~v, t), t
        if k == 'cond':
            c, _ = self.ev(e[1])
            a, ta = self.ev(e[2])
            b, tb = self.ev(e[3])
            t = cconv(ta, tb)
            return cwrap(a if c else b, t), t
        return self.binop(e[1], *self.ev(e[2]), *self.ev(e[3]))

    def binop(self, op, a, ta, b, tb):
        if op == '&&':
            return int(bool(a) and bool(b)), IN
        if op == '||':
            return int(bool(a) or bool(b)), IN
        if op in ('<<', '>>'):
            t = cpromote(ta)
            a, b = cwrap(a, t), cwrap(b, cpromote(tb))
            assert 0 <= b <= 15
            return cwrap(a << b if op == '<<' else a >> b, t), t
        t = cconv(ta, tb)
        a, b = cwrap(a, t), cwrap(b, t)
        if op in RELS:
            return int({'<': a < b, '<=': a <= b, '>': a > b, '>=': a >= b,
                        '==': a == b, '!=': a != b}[op]), IN
        if op in ('/', '%'):
            if b == 0:
                raise DivByZero
            q = abs(a) // abs(b)
            if (a < 0) != (b < 0):
                q = -q
            return cwrap(q if op == '/' else a - q * b, t), t
        r = {'+': a + b, '-': a - b, '*': a * b, '&': a & b, '|': a | b, '^': a ^ b}[op]
        return cwrap(r, t), t


def c_lit(v, t):
    if t == UN:
        return f'{v}u'
    if v == -32768:
        return '(-32767-1)'
    return f'({v})' if v < 0 else str(v)


def c_text(e):
    k = e[0]
    if k == 'var':
        return e[1]
    if k == 'arr':
        return f'{e[1]}[{c_text(e[3])}]'
    if k == 'deref':
        off = e[3]
        return f'*{e[1]}' if off == 0 else (f'{e[1]}[{off}]' if off > 0 else f'*({e[1]} - {-off})')
    if k == 'const':
        return c_lit(e[1], e[2])
    if k == 'cast':
        return f'(({e[1][0]})({c_text(e[2])}))'
    if k == 'un':
        return f'({e[1]}{c_text(e[2])})'
    if k == 'cond':
        return f'({c_text(e[1])} ? {c_text(e[2])} : {c_text(e[3])})'
    return f'({c_text(e[2])} {e[1]} {c_text(e[3])})'


class ProgramGen:
    """Rastgele program: globaller (başlangıç değerli), yereller, diziler, işaretçiler."""

    def __init__(self, rng):
        self.rng = rng
        self.env, self.ptrs = {}, {}
        self.decls, self.locals_ = [], []
        self.scalars = []               # (ad, tip)
        self.arrays = []                # (ad, tip)
        self.pointers = []              # (ad, tip)
        for t in CTYPES:
            tag = t[0][0] + str(t[1])
            for k in range(2):
                self.scalar(f'g{tag}{k}', t, glob=True)
            self.scalar(f'l{tag}', t, glob=False)
            arr = f'a{tag}'
            vals = [self.value(t) for _ in range(4)]
            self.env[arr] = vals
            self.arrays.append((arr, t))
            self.decls.append(f'{t[0]} {arr}[4] = {{' + ', '.join(c_lit(v, IN) for v in vals) + '};')
            ptr = f'p{tag}'
            self.ptrs[ptr] = (arr, 1)
            self.pointers.append((ptr, t))
            self.decls.append(f'{t[0]} *{ptr} = &{arr}[1];')

    def value(self, t):
        if self.rng.random() < .4:
            return self.rng.choice(LIMITS[t])
        return cwrap(self.rng.randrange(1 << t[1]), t)

    def scalar(self, name, t, glob):
        v = self.value(t)
        self.env[name] = v
        self.scalars.append((name, t))
        line = f'{t[0]} {name} = {c_lit(v, IN)};'
        (self.decls if glob else self.locals_).append(line)

    def index(self):
        if self.rng.random() < .5:
            return ('const', self.rng.randrange(4), IN)
        name, t = self.rng.choice(self.scalars)
        return ('bin', '&', ('var', name, t), ('const', 3, IN))

    def lvalue(self):
        r = self.rng.random()
        if r < .6:
            name, t = self.rng.choice(self.scalars)
            return ('var', name, t)
        if r < .85:
            name, t = self.rng.choice(self.arrays)
            return ('arr', name, t, self.index())
        name, t = self.rng.choice(self.pointers)
        return ('deref', name, t, self.rng.choice([-1, 0, 0, 1, 2]))

    def const(self):
        rng = self.rng
        if rng.random() < .7:
            v = rng.choice([rng.randrange(-40, 300), rng.choice(LIMITS[IN]),
                            rng.randrange(-32768, 32768)])
            return ('const', v, IN)
        return ('const', rng.choice([rng.randrange(300), rng.choice(LIMITS[UN]),
                                     rng.randrange(65536)]), UN)

    def expr(self, depth):
        rng = self.rng
        if depth <= 0 or rng.random() < .25:
            return self.lvalue() if rng.random() < .7 else self.const()
        r = rng.random()
        if r < .1:
            return ('un', rng.choice('-~!'), self.expr(depth - 1))
        if r < .18:
            return ('cast', rng.choice(CTYPES), self.expr(depth - 1))
        if r < .24:
            return ('cond', self.expr(depth - 1), self.expr(depth - 1), self.expr(depth - 1))
        if r < .4:
            return ('bin', rng.choice(RELS), self.expr(depth - 1), self.expr(depth - 1))
        op = rng.choice(ARITH)
        a = self.expr(depth - 1)
        if op in ('<<', '>>'):
            if rng.random() < .6:
                return ('bin', op, a, ('const', rng.randrange(16), IN))
            return ('bin', op, a, ('bin', '&', self.expr(depth - 1), ('const', 15, IN)))
        if op in ('*', '/', '%') and rng.random() < .5:
            k = rng.choice(MULCONST)
            b = ('const', k, IN) if rng.random() < .8 else ('const', k & 0xFFFF, UN)
            return ('bin', op, b, a) if op == '*' and rng.random() < .3 else ('bin', op, a, b)
        return ('bin', op, a, self.expr(depth - 1))

    def statement(self, ref, results):
        """Bir deyim üretir, referansta uygular. (C metni, beklenen sonuç ya da None)."""
        rng = self.rng
        kind = rng.random()
        if kind < .55:                                  # rK = ifade;
            e = self.expr(rng.randrange(1, 5))
            v, _ = ref.ev(e)
            rt = rng.choice(CTYPES)
            name = f'r{len(results)}'
            results.append((name, rt))
            self.decls.append(f'{rt[0]} {name};')
            return f'{name} = {c_text(e)};', (name, rt, cwrap(v, rt))
        lv = self.lvalue()
        box, i = ref.slot(lv)
        t = lv[2]
        lvt = c_text(lv)
        if kind < .7:                                   # x = ifade;
            e = self.expr(rng.randrange(1, 4))
            v, _ = ref.ev(e)
            box[i] = cwrap(v, t)
            return f'{lvt} = {c_text(e)};', None
        if kind < .9:                                   # x op= ifade;
            op = rng.choice(ARITH)
            if op in ('<<', '>>'):
                e = ('const', rng.randrange(16), IN)
            elif op in ('*', '/', '%') and rng.random() < .5:
                e = ('const', rng.choice(MULCONST), IN)
            else:
                e = self.expr(rng.randrange(1, 3))
            ev, et = ref.ev(e)
            cur = box[i]
            v, _ = ref.binop(op, cur, t, ev, et)
            box[i] = cwrap(v, t)
            return f'{lvt} {op}= {c_text(e)};', None
        op = rng.choice(['++', '--'])                   # ++x; x--; ...
        box[i] = cwrap(box[i] + (1 if op == '++' else -1), t)
        if lv[0] == 'deref':
            lvt = f'({lvt})'                            # *p++ işaretçiyi artırırdı
        return (f'{op}{lvt};' if rng.random() < .5 else f'{lvt}{op};'), None

    def program(self, nstmt):
        ref = Ref(self.env, self.ptrs)
        body, expect, results = [], [], []
        while len(body) < nstmt:
            snapshot = {k: (list(v) if isinstance(v, list) else v) for k, v in self.env.items()}
            try:
                text, exp = self.statement(ref, results)
            except DivByZero:
                self.env.clear()
                self.env.update(snapshot)
                continue
            body.append('    ' + text)
            if exp:
                expect.append(exp)
        finals = [(n, t) for n, t in self.scalars] + [(a, t) for a, t in self.arrays]
        src = '\n'.join(self.decls) + '\nint main(void)\n{\n' + \
            '\n'.join('    ' + d for d in self.locals_) + '\n' + '\n'.join(body)
        # yerellerin son değerlerini globallere kopyala ki okunabilsin
        for name, t in self.scalars:
            if name.startswith('l'):
                self.decls.append(f'{t[0]} out_{name};')
                src += f'\n    out_{name} = {name};'
        src = '\n'.join(self.decls) + src[src.index('\nint main'):] + '\n    return 0;\n}\n'
        return src, expect, finals


def check_program(tc, seed, nstmt=40, micro=False):
    rng = random.Random(seed)
    pg = ProgramGen(rng)
    src, expect, finals = pg.program(nstmt)
    m = compile_run(src, micro=micro, cycles=20_000_000)
    for name, rt, want in expect:
        got = m.get(name, rt[1] // 8, rt[2])
        tc.assertEqual(got, want, f'tohum {seed}: {name} ({rt[0]})\n' +
                       next(l for l in src.splitlines() if l.strip().startswith(name + ' =')))
    for name, t in finals:
        size = t[1] // 8
        if name.startswith('l'):
            tc.assertEqual(m.get('out_' + name, size, t[2]), pg.env[name], f'tohum {seed}: {name}')
        elif isinstance(pg.env[name], list):
            got = [m.get(name, size, t[2], k) for k in range(4)]
            tc.assertEqual(got, pg.env[name], f'tohum {seed}: {name}[]')
        else:
            tc.assertEqual(m.get(name, size, t[2]), pg.env[name], f'tohum {seed}: {name}')
    return len(expect), len(src.splitlines()), m.cpu.cycles


class TestDifferential(unittest.TestCase):
    """Rastgele ifade ve deyimler: TD-8 sonucu == Python referansı (sabit tohumlar)."""

    def test_random_programs(self):
        exprs = stmts = 0
        for seed in range(1, 201):
            n, lines, _ = check_program(self, seed)
            exprs += n
            stmts += 40
        self.assertGreater(exprs, 4000)         # ~4400 ifade + ~3600 yan etkili deyim

    def test_micro_emulator_agrees(self):
        """Birkaç rastgele program MicroEmu'da da (mikrokod + ALU tabloları) aynı."""
        for seed in (101, 102, 103):
            check_program(self, seed, nstmt=30, micro=True)


# ---------------------------------------------------------------------------
# Dil özellikleri (elle yazılmış programlar)
# ---------------------------------------------------------------------------

class TestControlFlow(unittest.TestCase):
    def test_loops_break_continue(self):
        m = compile_run('''
int w, f, d, brk, cont, nest;
int main(void) {
    int i, j;
    i = 0; while (i < 10) i += 3; w = i;
    for (i = 0; i < 5; i++) f += i;
    i = 0; do { d += 2; } while (++i < 4);
    do { d += 100; } while (0);
    for (i = 0; ; i++) { if (i == 7) break; brk = i; }
    for (i = 0; i < 10; i++) { if (i & 1) continue; cont += i; }
    for (i = 0; i < 4; i++)
        for (j = 0; j < 4; j++) { if (j > i) break; nest++; }
    return 0;
}''')
        self.assertEqual([m.i(n) for n in ('w', 'f', 'd', 'brk', 'cont', 'nest')],
                         [12, 10, 108, 6, 20, 10])

    def test_if_else_chain(self):
        m = compile_run('''
int r[6];
int sinif(int x) {
    if (x < 0) return -1;
    else if (x == 0) return 0;
    else if (x < 10) return 1;
    else return 2;
}
int main(void) {
    int k = 0;
    r[0] = sinif(-5); r[1] = sinif(0); r[2] = sinif(9); r[3] = sinif(10);
    if (k) r[4] = 1; else r[4] = 2;
    if (!k) { r[5] = 3; }
    return 0;
}''')
        self.assertEqual(m.ints('r', 6), [-1, 0, 1, 2, 2, 3])

    def test_switch(self):
        m = compile_run('''
int r[9];
int sw(int x) {
    switch (x) {
    case 0: return 100;
    case 1:
    case 2: return 200;
    case -5: return 300;
    case 1000: x = 7; break;
    default: return 400;
    }
    return x;
}
char swc(char c) {
    int n = 0;
    switch (c) {
    case 'a': n = 1;            /* düşer */
    case 'b': n += 10; break;
    case 255: n = 5; break;
    }
    return n;
}
int sws(signed char s) {
    switch (s) { case -1: return 1; case 127: return 2; case 300: return 9; }
    return 3;
}
int main(void) {
    int i, t = 0;
    r[0] = sw(0); r[1] = sw(2); r[2] = sw(-5); r[3] = sw(1000); r[4] = sw(9);
    r[5] = swc('a'); r[6] = swc('b') + swc(255) * 100 + swc('z') * 1000;
    r[7] = sws(-1) * 100 + sws(127) * 10 + sws(5);
    for (i = 0; i < 6; i++) {
        switch (i) { default: t += 1; break; case 2: t += 10; continue; case 4: t += 100; }
    }
    r[8] = t;
    return 0;
}''')
        self.assertEqual(m.ints('r', 9), [100, 200, 300, 7, 400, 11, 510, 123, 114])

    def test_short_circuit_side_effects(self):
        m = compile_run('''
int calls, r[8];
int t(int v) { calls++; return v; }
int main(void) {
    r[0] = t(0) && t(1);  r[1] = calls;
    r[2] = t(1) || t(1);  r[3] = calls;
    r[4] = t(1) && t(0) || t(5); r[5] = calls;
    if (t(0) && t(1)) r[6] = 99; else r[6] = calls;
    r[7] = (calls > 6) ? t(10) : t(20);
    return 0;
}''')
        self.assertEqual(m.ints('r', 8), [0, 1, 1, 2, 1, 5, 6, 20])
        self.assertEqual(m.i('calls'), 7)

    def test_comma_and_conditional(self):
        m = compile_run('''
int a, b, c, d;
char e;
int main(void) {
    a = (b = 3, b + 4);
    for (c = 0, d = 10; c < d; c++, d--) ;
    e = a > 5 ? 'Y' : 'N';
    b = a < 0 ? -a : a * 2;
    return 0;
}''')
        self.assertEqual((m.i('a'), m.i('b'), m.i('c'), m.i('d'), m.c('e')), (7, 14, 5, 5, ord('Y')))


class TestFunctions(unittest.TestCase):
    def test_params_and_returns(self):
        m = compile_run('''
int r[6];
char nxt(char c) { return c + 1; }
int add3(int a, int b, int c) { return a + b + c; }
unsigned mix(char a, signed char b, int *p) { return a + b + *p; }
void setv(int *p, int v) { *p = v; }
int g = 40;
int main(void) {
    r[0] = add3(add3(1, 2, 3), add3(4, 5, 6), nxt('A'));
    r[1] = nxt(1) + nxt(2);                 /* iki char dönüşü (A'da) */
    r[2] = mix(200, -1, &g);
    setv(&r[3], -77);
    r[4] = add3(nxt(9), add3(nxt(1), 2, 3), r[3]);
    r[5] = nxt(255);
    return 0;
}''')
        self.assertEqual(m.ints('r', 6), [87, 5, 239, -77, -60, 0])

    def test_static_local_and_globals(self):
        m = compile_run('''
int a, b, c;
int sayac(void) { static int n = 5; n++; return n; }
int main(void) { sayac(); a = sayac(); b = sayac(); c = sayac() - a; return 0; }''')
        self.assertEqual((m.i('a'), m.i('b'), m.i('c')), (7, 8, 2))

    def test_frame_overlay(self):
        """Birbirini çağırmayan fonksiyonların çerçeveleri üst üste biner;
        çağıran ile çağrılanınki asla çakışmaz."""
        src = '''
int out;
int c(int x) { int k = x * 3; return k + 1; }
int a(int x) { int t = x + 1; return c(t) + t; }
int b(int y) { int u = y - 1; return u * 2; }
int main(void) { int m = 5; out = a(m) + b(m) + m; return 0; }'''
        m = compile_run(src)
        self.assertEqual(m.i('out'), (6 * 3 + 1 + 6) + 8 + 5)
        s = m.res.program.symbols
        self.assertEqual(s['_a.x'], s['_b.y'])                  # kardeşler aynı adreste
        self.assertGreaterEqual(s['_a.x'], s['_main.m'] + 2)   # main'in çerçevesinden sonra
        self.assertGreaterEqual(s['_c.x'], s['_a.t'] + 2)      # a'nın çerçevesinden sonra
        self.assertEqual(s['_main.m'], 0x8022)                 # globallerden (out) hemen sonra

    def test_scopes_and_c99_for(self):
        m = compile_run('''
#include "hw.h"
int i = 100, r[4];
void setv(int *p, int v) { *p = v; }
int main(void) {
    int i = 1;
    { int i = 2; r[0] = i; }
    r[1] = i;
    for (int i = 0; i < 3; i++) r[2] += i;
    setv(&i, 42);
    r[3] = i + (NULL == (int *)0) * 1000;
    return 0;
}''')
        self.assertEqual(m.ints('r', 4), [2, 1, 3, 1042])
        self.assertEqual(m.i('i'), 100)

    def test_deep_call_chain_and_unreachable(self):
        m = compile_run('''
int r;
int f4(int x) { return x + 4; }
int f3(int x) { return f4(x) * 2; }
int f2(int x) { return f3(x) - f4(x); }
int f1(int x) { return f2(f3(x)) + f2(x); }
int hic_cagrilmayan(int x) { return x; }
int main(void) { r = f1(1); return 0; }''')
        f2 = lambda x: (x + 4) * 2 - (x + 4)
        self.assertEqual(m.i('r'), f2((1 + 4) * 2) + f2(1))
        self.assertNotIn('_hic_cagrilmayan', m.res.program.symbols)


class TestPointersArrays(unittest.TestCase):
    def test_pointer_arithmetic(self):
        m = compile_run('''
int arr[6] = {10, 20, 30, 40, 50, 60};
int *pa = &arr[2];
int r[8];
char s[] = "abc";
int main(void) {
    int *p = &arr[5], *q = arr;
    char *cp = s;
    r[0] = p - q;
    r[1] = *(p - 1) + pa[1] + *pa;
    r[2] = *pa++;  r[3] = *pa;
    p -= 2; r[4] = *p;
    r[5] = (p > q) + (p == &arr[3]) * 10 + (q != 0) * 100;
    cp += 2; r[6] = *cp - *(cp - 2);
    r[7] = sizeof(arr) + sizeof(s) + sizeof(*p);
    return 0;
}''')
        self.assertEqual(m.ints('r', 8), [5, 120, 30, 40, 40, 111, 2, 18])

    def test_2d_arrays_and_index_forms(self):
        m = compile_run('''
int t[3][4];
char g[4][5];
int r[5];
int sum(int (*row)[4], int n) { int s = 0, i, j; for (i = 0; i < n; i++) for (j = 0; j < 4; j++) s += row[i][j]; return s; }
int main(void) {
    int i, j;
    for (i = 0; i < 3; i++) for (j = 0; j < 4; j++) t[i][j] = i * 10 + j;
    for (i = 0; i < 4; i++) for (j = 0; j < 5; j++) g[i][j] = i + j;
    r[0] = t[2][3]; r[1] = t[1][0] + 1[t[0]];
    r[2] = sum(t, 3);
    r[3] = g[3][4] + *(*(g + 2) + 1);
    r[4] = sizeof t + sizeof t[0] + sizeof g;
    return 0;
}''')
        self.assertEqual(m.ints('t', 12), [0, 1, 2, 3, 10, 11, 12, 13, 20, 21, 22, 23])
        self.assertEqual(m.ints('r', 5), [23, 11, 138, 10, 24 + 8 + 20])

    def test_strings_and_vram(self):
        m = compile_run('''
#include "hw.h"
char buf[8];
int n;
int uzunluk(const char *s) { int k = 0; while (*s++) k++; return k; }
void kopyala(char *d, const char *s) { while ((*d++ = *s++)) ; }
int main(void) {
    char i;
    const char *m = "TD-8\\tC";
    n = uzunluk(m) + uzunluk("");
    kopyala(buf, "xyz");
    for (i = 0; m[i]; i++) VRAM[64 * 3 + 5 + i] = m[i];
    VRAM[0] = 'A'; VRAM[64 * 29 + 39] = 'Z';
    return 0;
}''')
        self.assertEqual(m.i('n'), 6)
        a = m.addr('buf')
        self.assertEqual(bytes(m.bus.mem[a:a + 4]), b'xyz\0')
        self.assertEqual(m.text(3)[5:9], 'TD-8')
        self.assertEqual(m.bus.vram[64 * 3 + 9], 9)
        self.assertEqual(m.text(0)[0], 'A')
        self.assertEqual(m.text(29)[39], 'Z')

    def test_pointer_to_pointer_and_void_ptr(self):
        m = compile_run('''
int x = 5, y = 7, r[3];
int *px = &x;
int main(void) {
    int **pp = &px;
    void *v = &y;
    **pp += 10;
    *pp = (int *)v;
    r[0] = x; r[1] = *px; r[2] = (px == &y);
    return 0;
}''')
        self.assertEqual(m.ints('r', 3), [15, 7, 1])


class TestData(unittest.TestCase):
    def test_initializers_and_bss(self):
        """crt0: .data kopyalanır, .bss sıfırlanır (RAM rastgele çöple başlar)."""
        m = compile_run('''
int a = -1234, z1, zarr[5];
unsigned u = 50000;
char c = 'q', zc;
signed char sc = -3;
int arr[5] = {1, 2, 3};
char str[6] = "hi";
char *ps = "metin";
int *pi = &arr[2];
int m2[2][3] = {{1, 2, 3}, {4}};
int flat[2][2] = {9, 8, 7};
int r;
int main(void) { r = *pi + ps[1]; return 0; }''')
        self.assertEqual((m.i('a'), m.u('u'), m.c('c'), m.sc('sc')), (-1234, 50000, ord('q'), -3))
        self.assertEqual((m.i('z1'), m.c('zc')), (0, 0))
        self.assertEqual(m.ints('zarr', 5), [0] * 5)
        self.assertEqual(m.ints('arr', 5), [1, 2, 3, 0, 0])
        self.assertEqual(bytes(m.bus.mem[m.addr('str'):m.addr('str') + 6]), b'hi\0\0\0\0')
        self.assertEqual(m.ints('m2', 6), [1, 2, 3, 4, 0, 0])
        self.assertEqual(m.ints('flat', 4), [9, 8, 7, 0])
        self.assertEqual(m.i('r'), 3 + ord('e'))

    def test_const_tables_in_rom(self):
        m = compile_run('''
const char kare[8] = {0, 1, 4, 9, 16, 25, 36, 49};
const int buyuk[] = {1000, -1000, 30000};
const char *const adlar[2] = {"bir", "iki"};
int r[4];
int main(void) {
    char i; int s = 0;
    for (i = 0; i < 8; i++) s += kare[i];
    r[0] = s; r[1] = buyuk[1] + buyuk[2]; r[2] = sizeof(buyuk);
    r[3] = adlar[1][2];
    return 0;
}''')
        self.assertEqual(m.ints('r', 4), [140, 29000, 6, ord('i')])
        for name in ('kare', 'buyuk', 'adlar'):
            self.assertLess(m.addr(name), 0x8000, name)          # ROM'da
        self.assertGreaterEqual(m.addr('r'), 0x8020)

    def test_local_arrays_and_init(self):
        m = compile_run('''
int r[6];
int f(int k) { int t[4] = {k, k + 1}; char s[] = "ab"; return t[0] + t[1] + t[2] + t[3] + s[1] + sizeof(s); }
int main(void) {
    int v[3]; int i;
    for (i = 0; i < 3; i++) v[i] = i * i;
    r[0] = v[2]; r[1] = f(10); r[2] = f(20);
    return 0;
}''')
        self.assertEqual(m.ints('r', 3), [4, 21 + 98 + 3, 41 + 98 + 3])


class TestIncDec(unittest.TestCase):
    def test_pre_post_all_types(self):
        m = compile_run('''
int i = 10; unsigned u = 0; char c = 255; signed char s = -128;
int arr[3] = {1, 2, 3}; int *p = arr;
int r[12];
int main(void) {
    r[0] = i++; r[1] = i; r[2] = ++i; r[3] = i--; r[4] = --i;
    r[5] = u--; r[6] = u;
    r[7] = c++; r[8] = c;
    r[9] = s--; r[10] = s;
    r[11] = *p++; r[11] += *++p; r[11] += (*p)++; r[11] += arr[2];
    return 0;
}''')
        self.assertEqual(m.ints('r', 12),
                         [10, 11, 12, 12, 10, 0, -1, 255, 0, -128, 127, 1 + 3 + 3 + 4])
        self.assertEqual((m.u('u'), m.c('c'), m.sc('s')), (65535, 0, 127))

    def test_compound_on_memory(self):
        m = compile_run('''
int a[4] = {1, 2, 3, 4}; char b[3] = {250, 5, 7};
int r[3];
int main(void) {
    int *p = &a[1]; char *q = b; int k = 2;
    *p += 100; a[k] *= 3; a[k + 1] <<= 2; a[0] -= a[3];
    *q += 10; q[1] |= 0x80; b[2] ^= 0xFF;
    r[0] = (*p *= 2); r[1] = (a[0] >>= 1); r[2] = (b[0] %= 3);
    return 0;
}''')
        self.assertEqual(m.ints('a', 4), [-8, 204, 9, 16])
        self.assertEqual([m.c('b', k) for k in range(3)], [1, 0x85, 0xF8])
        self.assertEqual(m.ints('r', 3), [204, -8, 1])


class CountingBus(Bus):
    def __init__(self):
        super().__init__()
        self.reads, self.writes = [], []

    def read(self, addr):
        if addr >= 0xF800:
            self.reads.append(addr)
        return super().read(addr)

    def write(self, addr, value):
        if addr >= 0xF800:
            self.writes.append((addr, value))
        super().write(addr, value)


class TestVolatile(unittest.TestCase):
    def test_every_access_happens(self):
        bus = CountingBus()
        m = compile_run('''
#include "hw.h"
char a, b;
int main(void) {
    LEDS = 1; LEDS = 2; LEDS = 3;
    a = KSTAT; b = KSTAT;
    KSTAT;
    a = a + (KSTAT & 0);
    return 0;
}''', bus=bus)
        self.assertEqual(bus.writes, [(0xF800, 1), (0xF800, 2), (0xF800, 3)])
        self.assertEqual(bus.reads, [0xF801] * 4)

    def test_keyboard_polling(self):
        m = compile_run('''
#include "hw.h"
char kodlar[3];
int main(void) {
    char n = 0;
    while (n < 3) {
        while (!(KSTAT & KRDY)) ;
        kodlar[n++] = KBD;
    }
    LEDS = kodlar[2];
    return 0;
}''', keys=[0x1C, 0xF0, 0x1C])
        self.assertEqual([m.c('kodlar', k) for k in range(3)], [0x1C, 0xF0, 0x1C])
        self.assertEqual(m.bus.leds, 0x1C)


# ---------------------------------------------------------------------------
# Hata iletileri
# ---------------------------------------------------------------------------

class TestErrors(unittest.TestCase):
    def check(self, src, line, *parts):
        e = compile_error(src, 'hata.c')
        for p in parts:
            self.assertIn(p, e.msg, src)
        self.assertEqual(e.line, line, f'{e}')
        self.assertTrue(str(e).startswith(f'hata.c:{line}: '), str(e))

    def test_recursion(self):
        self.check('int f(int n)\n{\n    if (n) return n * f(n - 1);\n    return 1;\n}\n'
                   'int main(void) { return f(3); }', 3, 'özyineleme', 'f -> f')
        self.check('int g(int x);\nint f(int x) { return g(x); }\n'
                   'int g(int x)\n{\n    return f(x - 1);\n}\nint main(void) { return f(1); }',
                   5, 'özyineleme', 'f -> g -> f')

    def test_unsupported(self):
        self.check('int a;\nstruct nokta { int x; };', 2, 'struct desteklenmiyor')
        self.check('int main(void)\n{\n    long x;\n}', 3, 'long')
        self.check('int f(void) { return 1; }\nint main(void)\n{\n    int x = f;\n}', 4,
                   'fonksiyon işaretçisi')
        self.check('int f(void) { return 1; }\nint main(void)\n{\n    return (&f)();\n}', 4,
                   'fonksiyon işaretçisi')

    def test_undefined(self):
        self.check('int main(void)\n{\n    int a;\n    a = b + 1;\n    return a;\n}', 4,
                   'tanımsız ad: b')
        self.check('int main(void)\n{\n    return f(1);\n}', 3, 'bildirilmemiş fonksiyon: f')
        self.check('int f(int x);\nint main(void)\n{\n    return f(1);\n}', 4,
                   'f fonksiyonu bildirilmiş ama tanımlanmamış')
        self.check('int f(void) { return 0; }', 1, 'main fonksiyonu tanımlı değil')

    def test_type_errors(self):
        self.check('int main(void)\n{\n    int a; char *p;\n    p = a;\n    return 0;\n}', 4,
                   'tamsayıdan işaretçiye')
        self.check('int main(void)\n{\n    int *p; char *q = 0;\n    p = q;\n}', 4,
                   'uyumsuz işaretçi tipleri')
        self.check('int main(void)\n{\n    int a = 1;\n    return *a;\n}', 4, "'*' işleci işaretçi ister")
        self.check('int f(int a, int b) { return a; }\nint main(void)\n{\n    return f(1);\n}', 4,
                   '2 argüman bekleniyor, 1 verildi')
        self.check('const int k = 3;\nint main(void)\n{\n    k = 4;\n}', 4, 'const')
        self.check('int main(void)\n{\n    int a;\n    a + 1 = 2;\n}', 4, 'değiştirilebilir')
        self.check('void f(void) { }\nint main(void)\n{\n    int a = f();\n}', 4, 'dönüştürülemez')
        self.check('const char *s = "x";\nint main(void)\n{\n    char *t = s;\n}', 4,
                   'niteleyici')
        self.check('int a[3];\nint main(void)\n{\n    a = 0;\n}', 4, 'diziye atama')

    def test_memory_limits(self):
        self.check('char buyuk[30000];\nint main(void) { buyuk[0] = 1; return 0; }', 0,
                   'RAM yetmiyor')
        with self.assertRaises(CompileError) as cm:
            build('const char t[33000] = {1};\nint main(void) { return t[5]; }')
        self.assertIn("ROM'a sığmıyor", str(cm.exception))

    def test_statement_errors(self):
        self.check('int main(void)\n{\n    break;\n}', 3, "'break'")
        self.check('int main(void)\n{\n    continue;\n}', 3, "'continue'")
        self.check('int main(void)\n{\n    case 1: ;\n}', 3, "'case' switch dışında")
        self.check('int main(void)\n{\n    int a = 1;\n    switch (a) { case 1: case 1: ; }\n}', 4,
                   'iki kez')
        self.check('int main(void)\n{\n    int x;\n    int x;\n}', 4, 'iki kez bildirilmiş')
        self.check('int main(void)\n{\n    return 5 / 0;\n}', 3, 'sıfıra bölme')
        self.check('int main(void)\n{\n    int a = 1;\n    return a << 16;\n}', 4, 'kaydırma')
        self.check('void f(void)\n{\n    return 1;\n}\nint main(void) { return 0; }', 3,
                   'değer döndüremez')
        self.check('int _gizli;\nint main(void) { return 0; }', 1, "'_'")


# ---------------------------------------------------------------------------
# Örnek programlar, komut satırı, maliyetler
# ---------------------------------------------------------------------------

def example(name, micro=False):
    path = EXAMPLES / name
    res = build(path.read_text(encoding='utf-8'), str(path))
    bus, cpu = run(res.program, micro=micro, max_cycles=2_000_000)
    if not cpu.halted:
        raise AssertionError(f'{name} durmadı')
    return Machine(res, bus, cpu)


class TestExamples(unittest.TestCase):
    def test_merhaba(self):
        m = example('merhaba.c')
        rows = m.bus.screen()
        self.assertEqual(rows[1], '  MERHABA, TD-8!' + ' ' * 24)
        self.assertTrue(all(r.strip() == '' for k, r in enumerate(rows) if k != 1))
        written = set(range(64 + 2, 64 + 16))
        self.assertTrue(all(b == 0x20 for k, b in enumerate(m.bus.vram) if k not in written))
        self.assertEqual(m.bus.leds, 0x55)
        mm = example('merhaba.c', micro=True)
        self.assertEqual(mm.bus.screen(), rows)
        self.assertEqual((mm.cpu.cycles, mm.bus.leds), (m.cpu.cycles, 0x55))

    def test_fib(self):
        fib = [0, 1]
        while len(fib) < 25:
            fib.append(fib[-1] + fib[-2])
        for micro in (False, True):
            m = example('fib.c', micro)
            rows = m.bus.screen()
            self.assertEqual(rows[0].strip(), 'FIBONACCI SAYILARI (C)')
            for n, f in enumerate(fib):
                self.assertEqual(rows[2 + n].rstrip(), f' F{n:>2} = {f:>5}', f'F{n}')
            self.assertEqual([m.u('fib', k) for k in range(25)], fib)
            self.assertEqual(m.bus.leds, 25)

    def test_sayac(self):
        m = example('sayac.c')
        rows = m.bus.screen()
        self.assertEqual([r.rstrip() for r in rows[1:5]],
                         [' SAYI      53', ' FIZZ      27', ' BUZZ      13', ' FIZZBUZZ   7'])
        self.assertEqual(m.bus.leds, 0x7B)
        tablo = [m.c('tablo', k) for k in range(100)]
        self.assertEqual(tablo, [(k % 3 == 0) | (k % 5 == 0) << 1 for k in range(100)])

    def test_cli(self):
        import contextlib
        import io
        import tempfile
        from tdcc.__main__ import main
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'merhaba_c.asm'
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                main([str(EXAMPLES / 'merhaba.c'), '-o', str(out), '--run'])
            text = buf.getvalue()
            self.assertTrue(out.is_file())
            self.assertIn('durdu (HALT)', text)
            self.assertIn('|  MERHABA, TD-8!', text)
            self.assertIn('LED=01010101', text)


def ins_cycles(line):
    from td8 import asm as tdasm
    parts = line.split(None, 1)
    m = isa.ALIASES.get(parts[0].upper(), parts[0].upper())
    mode, _ = tdasm._mode(m, parts[1].strip() if len(parts) > 1 else '')
    ins = isa.INSTRUCTIONS[isa.BY_NAME[(m, mode)]]
    if ins.cond is not None:
        return ins.cycles(False), ins.cycles(True)
    return ins.cycles(), ins.cycles()


def stmt_cost(asm_text, stmt):
    """Kaynak satırı yorumunun altındaki komutların çevrim toplamı (en az, en çok)."""
    lines = asm_text.splitlines()
    start = next(k for k, l in enumerate(lines)
                 if l.strip().startswith(';') and l.rstrip().endswith(': ' + stmt))
    lo = hi = 0
    for l in lines[start + 1:]:
        s = l.strip()
        if not s or s.startswith(';') or s.endswith(':'):
            break
        a, b = ins_cycles(s)
        lo, hi = lo + a, hi + b
    return lo, hi


class TestCosts(unittest.TestCase):
    """SISTEM-PLANI 11.3'teki örnek maliyetler (1 MHz'de µs = çevrim)."""

    SRC = '''
int a, b, c, r, x, y, z;
char cx, *p;
char ca, cb, cc;
int topla(int u, int v)
{
    return u + v;
}
int main(void)
{
    a = b + c;
    *p = cx;
    if (x < y)
        z = 1;
    r = topla(a, b);
    ca = cb + cc;
    a++;
    x = y * 64;
    return 0;
}'''

    def test_costs(self):
        text = compile_c(self.SRC).asm
        self.assertEqual(stmt_cost(text, 'a = b + c;'), (24, 24))
        self.assertEqual(stmt_cost(text, '*p = cx;'), (11, 11))
        self.assertEqual(stmt_cost(text, 'if (x < y)'), (19, 20))
        call = stmt_cost(text, 'r = topla(a, b);')[0] + stmt_cost(text, 'return u + v;')[0]
        self.assertEqual(call, 82)
        self.assertEqual(stmt_cost(text, 'ca = cb + cc;'), (12, 12))     # 8 bit işlem 8 bitte
        self.assertEqual(stmt_cost(text, 'a++;'), (7, 7))               # INCW
        self.assertLessEqual(stmt_cost(text, 'x = y * 64;')[0], 70)    # çarpma değil kaydırma
        self.assertNotIn('__mul16', text)

    def test_string_loop_per_char(self):
        """merhaba.c'deki `while (*s) *v++ = *s++;` döngüsü karakter başına 41 çevrim."""
        m = example('merhaba.c')
        text = m.res.asm
        body = stmt_cost(text, '*v++ = *s++;')[0]
        lines = text.splitlines()
        k = max(i for i, l in enumerate(lines) if l.rstrip().endswith(': while (*s)'))
        cond = sum(ins_cycles(l.strip())[1] for l in lines[k + 1:k + 5])
        self.assertEqual(body + cond, 41)

    SNAKE_SRC = '''
unsigned char s, y, d, i, h;
unsigned w, q, x;
int tablo[200];
int r[8];
int main(void)
{
    unsigned char k;
    for (k = 0; k < 200; k++)
        tablo[k] = k * 3 + 1;
    if (s & 0x80)
        r[0] = 1;
    if (w & 1)
        r[1] = 1;
    if ((y ^ 2) != d)
        r[2] = 1;
    r[3] = tablo[i];
    if (w & 0x0100)
        r[4] = 1;
    r[5] = (s & 0x0F) | 0x0F00;
    r[6] = tablo[i - 100];
    if ((w >> 8) == 1)
        r[7] = 1;
    h = w >> 8;
    q = w * 0x0300;
    x = (w ^ (w >> 8)) & 0x7FF;
    return 0;
}'''

    def test_snake_optimizations(self):
        """Yılan oyunu için eklenen iyileştirmeler (sim/examples/snake.c):
        `c & sabit` koşulu 8 bitte, üst byte'ı 0 olan karşılaştırma 8 bitte,
        int dizisinde char indeks SHL/ROL ile, 16-bit *p doğrudan hedefe,
        işaretsiz `x >> 8` kodsuz (üst byte)."""
        text = compile_c(self.SNAKE_SRC).asm
        self.assertEqual(stmt_cost(text, 'if (s & 0x80)'), (9, 10))       # LDA AND BEQ
        self.assertEqual(stmt_cost(text, 'if (w & 1)'), (9, 10))
        self.assertEqual(stmt_cost(text, 'if ((y ^ 2) != d)'), (13, 14))  # LDA XOR CMP BEQ
        self.assertEqual(stmt_cost(text, 'r[3] = tablo[i];'), (46, 46))   # önce 76
        self.assertEqual(stmt_cost(text, 'if ((w >> 8) == 1)'), (9, 10))  # LDA w+1 CMP BNE
        self.assertEqual(stmt_cost(text, 'h = w >> 8;'), (8, 8))          # LDA w+1 STA
        for s, w, y, d, i in ((0x80, 0x0101, 2, 0, 150), (0x7F, 0x00FE, 3, 1, 7),
                              (0xFF, 0x8001, 0, 2, 199), (0, 0, 255, 253, 128)):
            src = self.SNAKE_SRC.replace('unsigned char s, y, d, i, h;',
                                         f'unsigned char s = {s}, y = {y}, d = {d}, i = {i}, h;')
            src = src.replace('unsigned w, q, x;', f'unsigned w = {w}, q, x;')
            m = compile_run(src)
            want = [int(bool(s & 0x80)), w & 1, int((y ^ 2) != d), i * 3 + 1,
                    int(bool(w & 0x100)), (s & 0x0F) | 0x0F00, ((i - 100) & 0xFF) * 3 + 1,
                    int(w >> 8 == 1)]
            if i - 100 < 0:
                want[6] = None                  # dizi dışı: karşılaştırılmaz
            got = m.ints('r', 8)
            self.assertEqual([g for g, v in zip(got, want) if v is not None],
                             [v for v in want if v is not None], (s, w, y, d, i))
            self.assertEqual(m.c('h'), w >> 8)
            self.assertEqual(m.u('q'), w * 0x300 & 0xFFFF)
            self.assertEqual(m.u('x'), (w ^ (w >> 8)) & 0x7FF)

    def test_constant_folding_and_8bit(self):
        text = compile_c('char c, d; int i;\nint main(void)\n{\n    i = 3 * 4 + (1 << 4);\n'
                         '    c = d & 0x0F;\n    return 0;\n}').asm
        self.assertEqual(stmt_cost(text, 'i = 3 * 4 + (1 << 4);'), (12, 12))   # LDA #28, STA, LDA #0, STA
        self.assertEqual(stmt_cost(text, 'c = d & 0x0F;'), (10, 10))


if __name__ == '__main__':
    unittest.main()
