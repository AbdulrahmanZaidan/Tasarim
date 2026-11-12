"""Özyinelemeli iniş ayrıştırıcısı: token listesi -> AST (nodes.Program).

Alt kümenin tamamını tanır. Desteklenmeyen yapılar (struct, union, long,
float, typedef, goto, fonksiyon işaretçisi, ...) burada anlaşılır bir hatayla
reddedilir; sessizce yanlış kod üretilmez.
"""

from . import nodes as N
from . import typesys as T
from .errors import CompileError

TYPE_KWS = {'void', 'char', 'short', 'int', 'signed', 'unsigned', 'long', 'float',
            'double', 'struct', 'union', 'enum', 'const', 'volatile', 'static',
            'extern', 'register', 'auto', 'typedef', 'inline'}

UNSUPPORTED_TYPES = {
    'long': 'long desteklenmiyor (int 16 bittir)',
    'float': 'float desteklenmiyor',
    'double': 'double desteklenmiyor',
    'struct': 'struct desteklenmiyor',
    'union': 'union desteklenmiyor',
    'typedef': 'typedef desteklenmiyor',
}

BINARY_PREC = {
    '||': 1, '&&': 2, '|': 3, '^': 4, '&': 5, '==': 6, '!=': 6,
    '<': 7, '>': 7, '<=': 7, '>=': 7, '<<': 8, '>>': 8,
    '+': 9, '-': 9, '*': 10, '/': 10, '%': 10,
}

ASSIGN_OPS = {'=', '+=', '-=', '*=', '/=', '%=', '<<=', '>>=', '&=', '^=', '|='}


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0
        self.enum_consts = {}       # ad -> (değer, token)

    # --- token yardımcıları -------------------------------------------------
    @property
    def tok(self):
        return self.toks[self.i]

    def peek(self, k=1):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def next(self):
        t = self.toks[self.i]
        if t.kind != 'eof':
            self.i += 1
        return t

    def error(self, msg, tok=None):
        tok = tok or self.tok
        raise CompileError(msg, tok.file, tok.line)

    def describe(self, t):
        if t.kind == 'eof':
            return 'dosya sonu'
        return repr(t.text)

    def expect(self, op):
        if not self.tok.is_op(op):
            self.error(f"'{op}' bekleniyor, {self.describe(self.tok)} bulundu")
        return self.next()

    def accept(self, op):
        if self.tok.is_op(op):
            return self.next()
        return None

    def expect_ident(self):
        t = self.tok
        if t.kind != 'id':
            self.error(f'ad bekleniyor, {self.describe(t)} bulundu')
        return self.next()

    def starts_type(self, t=None):
        t = t or self.tok
        return t.kind == 'kw' and t.value in TYPE_KWS

    # --- program ------------------------------------------------------------
    def parse_program(self):
        items = []
        while self.tok.kind != 'eof':
            if self.accept(';'):
                continue
            items.extend(self.external_decl())
        return N.Program(items, file=self.toks[0].file, line=1)

    def external_decl(self):
        start = self.tok
        spec = self.decl_specs()
        if self.accept(';'):
            return []                           # yalnız enum bildirimi ya da boş
        out = []
        while True:
            name, ctype, params, dtok = self.declarator(spec['type'])
            if name is None:
                self.error('bildirimde ad eksik', dtok)
            if ctype.is_func:
                if self.tok.is_op('{'):
                    if out:
                        self.error('fonksiyon tanımı bildirim listesinde olamaz')
                    if params is None:
                        self.error(f'{name.value}: parametre adları eksik', name)
                    body = self.block()
                    return [N.FuncDef(name.value, ctype, params, body, spec['storage'],
                                      file=name.file, line=name.line)]
                out.append(N.FuncDecl(name.value, ctype, params, spec['storage'],
                                      file=name.file, line=name.line))
            else:
                init = self.initializer() if self.accept('=') else None
                out.append(N.VarDecl(name.value, ctype, init, spec['storage'],
                                     file=name.file, line=name.line))
            if not self.accept(','):
                break
        if not self.tok.is_op(';'):
            self.error(f"';' bekleniyor, {self.describe(self.tok)} bulundu")
        self.next()
        return out

    # --- bildirim belirteçleri ----------------------------------------------
    def decl_specs(self):
        start = self.tok
        storage = None
        const = volatile = False
        words = []
        etype = None
        while self.tok.kind == 'kw' and self.tok.value in TYPE_KWS:
            t = self.next()
            v = t.value
            if v in UNSUPPORTED_TYPES:
                self.error(UNSUPPORTED_TYPES[v], t)
            if v in ('static', 'extern', 'register', 'auto'):
                if storage and storage != v:
                    self.error('birden fazla saklama sınıfı', t)
                storage = v if v in ('static', 'extern') else storage
            elif v == 'inline':
                pass
            elif v == 'const':
                const = True
            elif v == 'volatile':
                volatile = True
            elif v == 'enum':
                etype = self.enum_spec(t)
                words.append('int')
            else:
                words.append(v)
        if not words:
            self.error(f'tip bekleniyor, {self.describe(self.tok)} bulundu', start)
        base = self.combine(words, start)
        return {'type': base.qualified(const, volatile), 'storage': storage}

    def combine(self, words, where):
        w = sorted(words)
        table = {
            ('void',): T.VOID,
            ('char',): T.CHAR, ('char', 'unsigned'): T.CHAR, ('char', 'signed'): T.SCHAR,
            ('int',): T.INT, ('signed',): T.INT, ('int', 'signed'): T.INT,
            ('short',): T.INT, ('int', 'short'): T.INT, ('short', 'signed'): T.INT,
            ('int', 'short', 'signed'): T.INT,
            ('unsigned',): T.UINT, ('int', 'unsigned'): T.UINT, ('short', 'unsigned'): T.UINT,
            ('int', 'short', 'unsigned'): T.UINT,
        }
        t = table.get(tuple(w))
        if t is None:
            self.error('geçersiz tip birleşimi: ' + ' '.join(words), where)
        return t

    def enum_spec(self, kw):
        if self.tok.kind == 'id':
            self.next()                         # etiket adı (yok sayılır)
        if not self.accept('{'):
            return T.INT
        value = 0
        while not self.tok.is_op('}'):
            name = self.expect_ident()
            if self.accept('='):
                e = self.conditional()
                value = self.const_value(e)
            if name.value in self.enum_consts:
                self.error(f'enum sabiti iki kez tanımlı: {name.value}', name)
            self.enum_consts[name.value] = (value, name)
            value += 1
            if not self.accept(','):
                break
        self.expect('}')
        return T.INT

    def const_value(self, e):
        """enum değerleri için küçük sabit hesaplayıcı."""
        if isinstance(e, N.Num):
            return e.value
        if isinstance(e, N.Ident) and e.name in self.enum_consts:
            return self.enum_consts[e.name][0]
        if isinstance(e, N.Unary) and e.op in '-+~':
            v = self.const_value(e.operand)
            return {'-': -v, '+': v, '~': ~v}[e.op]
        if isinstance(e, N.Binary) and e.op in ('+', '-', '*', '<<', '|', '&'):
            a, b = self.const_value(e.left), self.const_value(e.right)
            return {'+': a + b, '-': a - b, '*': a * b, '<<': a << b, '|': a | b, '&': a & b}[e.op]
        self.error('enum değeri sabit bir ifade olmalı', e)

    # --- bildiriciler ---------------------------------------------------------
    def declarator(self, base, abstract=False):
        """(ad token'ı ya da None, tip, parametreler ya da None, konum token'ı)."""
        start = self.tok
        name, wrap, params = self._declarator(abstract)
        t = wrap(base)
        self.check_type(t, start)
        return name, t, params, start

    def _declarator(self, abstract):
        ptrs = []
        while self.accept('*'):
            c = v = False
            while self.tok.is_kw('const', 'volatile'):
                if self.next().value == 'const':
                    c = True
                else:
                    v = True
            ptrs.append((c, v))
        inner = None
        name = None
        params = None
        if self.tok.is_op('(') and (self.peek().is_op('*', '(') or self.peek().kind == 'id'):
            self.next()
            name, inner, params = self._declarator(abstract)
            self.expect(')')
        elif self.tok.kind == 'id':
            name = self.next()
        elif not abstract:
            self.error(f'ad bekleniyor, {self.describe(self.tok)} bulundu')
        suffixes = []
        while True:
            if self.accept('['):
                if self.accept(']'):
                    suffixes.append(('arr', None))
                else:
                    e = self.expression()
                    self.expect(']')
                    suffixes.append(('arr', e.value if isinstance(e, N.Num) else e))
            elif self.tok.is_op('(') :
                t = self.next()
                plist, ptypes, variadic = self.param_list(t)
                suffixes.append(('func', ptypes, variadic))
                if params is None and inner is None:
                    params = plist
            else:
                break

        def wrap(base):
            t = base
            for c, v in ptrs:
                t = T.PtrT(t).qualified(c, v)
            for s in reversed(suffixes):
                if s[0] == 'arr':
                    t = T.ArrT(t, s[1])
                else:
                    t = T.FuncT(t, s[1], s[2])
            return inner(t) if inner else t
        return name, wrap, params

    def check_type(self, t, where):
        """Desteklenmeyen tip yapıları."""
        if t.is_ptr:
            if t.base.is_func:
                self.error('fonksiyon işaretçisi desteklenmiyor', where)
            self.check_type(t.base, where)
        elif t.is_array:
            if t.base.is_func:
                self.error('fonksiyon dizisi olamaz', where)
            if t.base.is_void:
                self.error('void dizisi olamaz', where)
            self.check_type(t.base, where)
        elif t.is_func:
            if t.ret.is_func or t.ret.is_array:
                self.error('fonksiyon dizi ya da fonksiyon döndüremez', where)
            self.check_type(t.ret, where)

    def param_list(self, open_tok):
        """'(' okundu. (parametre listesi [(ad token, tip)], tipler, variadic)."""
        if self.accept(')'):
            return [], [], False                # () = parametresiz kabul edilir
        if self.tok.is_kw('void') and self.peek().is_op(')'):
            self.next()
            self.next()
            return [], [], False
        plist, ptypes = [], []
        while True:
            if self.tok.is_op('...'):
                self.error('değişken sayıda parametre (...) desteklenmiyor')
            if not self.starts_type():
                if self.tok.kind == 'id':
                    self.error('K&R tarzı parametre listesi desteklenmiyor; tip yazın')
                self.error(f'parametre tipi bekleniyor, {self.describe(self.tok)} bulundu')
            spec = self.decl_specs()
            if spec['storage']:
                self.error('parametrede saklama sınıfı olamaz')
            name, t, _, where = self.declarator(spec['type'], abstract=True)
            if t.is_array:                       # int a[] -> int *a
                t = T.PtrT(t.base).qualified(t.const, t.volatile)
            if t.is_func:
                self.error('fonksiyon işaretçisi desteklenmiyor', where)
            if t.is_void:
                self.error('void parametre olamaz', where)
            plist.append((name, t))
            ptypes.append(t)
            if not self.accept(','):
                break
        self.expect(')')
        return plist, ptypes, False

    def type_name(self):
        """Cast ve sizeof içindeki tip adı."""
        spec = self.decl_specs()
        if spec['storage']:
            self.error('tip adında saklama sınıfı olamaz')
        name, t, _, where = self.declarator(spec['type'], abstract=True)
        if name is not None:
            self.error('tip adında değişken adı olamaz', name)
        return t

    def initializer(self):
        if self.tok.is_op('{'):
            t = self.next()
            items = []
            while not self.tok.is_op('}'):
                items.append(self.initializer())
                if not self.accept(','):
                    break
            self.expect('}')
            return N.InitList(items, file=t.file, line=t.line)
        return self.assignment()

    # --- deyimler -----------------------------------------------------------
    def block(self):
        t = self.expect('{')
        items = []
        while not self.tok.is_op('}'):
            if self.tok.kind == 'eof':
                self.error("'}' eksik (blok kapanmadı)", t)
            items.append(self.statement())
        self.next()
        return N.Block(items, file=t.file, line=t.line)

    def local_decl(self):
        t = self.tok
        spec = self.decl_specs()
        decls = []
        if self.tok.is_op(';'):
            self.next()
            return N.DeclStmt(decls, file=t.file, line=t.line)
        while True:
            name, ctype, params, where = self.declarator(spec['type'])
            if ctype.is_func:
                if self.tok.is_op('{'):
                    self.error('iç içe fonksiyon tanımı olamaz', name)
                decls.append(N.FuncDecl(name.value, ctype, params, spec['storage'],
                                        file=name.file, line=name.line))
            else:
                init = self.initializer() if self.accept('=') else None
                decls.append(N.VarDecl(name.value, ctype, init, spec['storage'],
                                       file=name.file, line=name.line))
            if not self.accept(','):
                break
        self.expect(';')
        return N.DeclStmt(decls, file=t.file, line=t.line)

    def statement(self):
        t = self.tok
        pos = dict(file=t.file, line=t.line)
        if t.is_op('{'):
            return self.block()
        if t.is_op(';'):
            self.next()
            return N.Empty(**pos)
        if self.starts_type():
            return self.local_decl()
        if t.kind == 'kw':
            v = t.value
            if v == 'if':
                self.next()
                self.expect('(')
                c = self.expression()
                self.expect(')')
                then = self.statement()
                other = self.statement() if self.tok.is_kw('else') and self.next() else None
                return N.If(c, then, other, **pos)
            if v == 'while':
                self.next()
                self.expect('(')
                c = self.expression()
                self.expect(')')
                return N.While(c, self.statement(), **pos)
            if v == 'do':
                self.next()
                body = self.statement()
                if not self.tok.is_kw('while'):
                    self.error("do gövdesinden sonra 'while' bekleniyor")
                self.next()
                self.expect('(')
                c = self.expression()
                self.expect(')')
                self.expect(';')
                return N.DoWhile(body, c, **pos)
            if v == 'for':
                self.next()
                self.expect('(')
                if self.starts_type():
                    init = self.local_decl()
                elif self.accept(';'):
                    init = None
                else:
                    init = N.ExprStmt(self.expression(), **pos)
                    self.expect(';')
                cond = None if self.tok.is_op(';') else self.expression()
                self.expect(';')
                step = None if self.tok.is_op(')') else self.expression()
                self.expect(')')
                return N.For(init, cond, step, self.statement(), **pos)
            if v == 'switch':
                self.next()
                self.expect('(')
                e = self.expression()
                self.expect(')')
                return N.Switch(e, self.statement(), **pos)
            if v == 'case':
                self.next()
                e = self.conditional()
                self.expect(':')
                return N.Case(e, **pos)
            if v == 'default':
                self.next()
                self.expect(':')
                return N.Default(**pos)
            if v == 'break':
                self.next()
                self.expect(';')
                return N.Break(**pos)
            if v == 'continue':
                self.next()
                self.expect(';')
                return N.Continue(**pos)
            if v == 'return':
                self.next()
                e = None if self.tok.is_op(';') else self.expression()
                self.expect(';')
                return N.Return(e, **pos)
            if v == 'goto':
                self.error('goto desteklenmiyor')
            if v == 'asm':
                self.error('satır içi assembly desteklenmiyor')
            if v == 'else':
                self.error("'else' için 'if' yok")
        if t.kind == 'id' and self.peek().is_op(':'):
            self.error('etiketli deyim (goto etiketi) desteklenmiyor')
        e = self.expression()
        self.expect(';')
        return N.ExprStmt(e, **pos)

    # --- ifadeler -----------------------------------------------------------
    def expression(self):
        e = self.assignment()
        while self.tok.is_op(','):
            t = self.next()
            e = N.Comma(e, self.assignment(), file=t.file, line=t.line)
        return e

    def assignment(self):
        lhs = self.conditional()
        t = self.tok
        if t.kind == 'op' and t.value in ASSIGN_OPS:
            self.next()
            rhs = self.assignment()
            if t.value == '=':
                return N.Assign(lhs, rhs, file=t.file, line=t.line)
            return N.CompoundAssign(t.value[:-1], lhs, rhs, file=t.file, line=t.line)
        return lhs

    def conditional(self):
        c = self.binary(1)
        if self.tok.is_op('?'):
            t = self.next()
            a = self.expression()
            self.expect(':')
            b = self.conditional()
            return N.Cond(c, a, b, file=t.file, line=t.line)
        return c

    def binary(self, min_prec):
        lhs = self.unary()
        while True:
            t = self.tok
            prec = BINARY_PREC.get(t.value) if t.kind == 'op' else None
            if prec is None or prec < min_prec:
                return lhs
            self.next()
            rhs = self.binary(prec + 1)
            if t.value in ('&&', '||'):
                lhs = N.Logical(t.value, lhs, rhs, file=t.file, line=t.line)
            else:
                lhs = N.Binary(t.value, lhs, rhs, file=t.file, line=t.line)

    def unary(self):
        t = self.tok
        pos = dict(file=t.file, line=t.line)
        if t.kind == 'op':
            if t.value in ('++', '--'):
                self.next()
                return N.IncDec(t.value, True, self.unary(), **pos)
            if t.value in ('-', '+', '~', '!'):
                self.next()
                return N.Unary(t.value, self.cast_expr(), **pos)
            if t.value == '*':
                self.next()
                return N.Deref(self.cast_expr(), **pos)
            if t.value == '&':
                self.next()
                return N.AddrOf(self.cast_expr(), **pos)
            if t.value == '(' and self.starts_type(self.peek()):
                return self.cast_expr()
        if t.is_kw('sizeof'):
            self.next()
            if self.tok.is_op('(') and self.starts_type(self.peek()):
                self.next()
                ty = self.type_name()
                self.expect(')')
                return N.SizeofType(ty, **pos)
            return N.SizeofExpr(self.unary(), **pos)
        return self.postfix()

    def cast_expr(self):
        t = self.tok
        if t.is_op('(') and self.starts_type(self.peek()):
            self.next()
            ty = self.type_name()
            self.expect(')')
            if self.tok.is_op('{'):
                self.error('bileşik sabitler (compound literal) desteklenmiyor')
            return N.Cast(ty, self.cast_expr(), False, file=t.file, line=t.line)
        return self.unary()

    def postfix(self):
        e = self.primary()
        while True:
            t = self.tok
            pos = dict(file=t.file, line=t.line)
            if t.is_op('['):
                self.next()
                i = self.expression()
                self.expect(']')
                e = N.Index(e, i, **pos)
            elif t.is_op('('):
                self.next()
                args = []
                if not self.tok.is_op(')'):
                    while True:
                        args.append(self.assignment())
                        if not self.accept(','):
                            break
                self.expect(')')
                e = N.Call(e, args, **pos)
            elif t.is_op('++', '--'):
                self.next()
                e = N.IncDec(t.value, False, e, **pos)
            elif t.is_op('.', '->'):
                self.error('struct/union üyesi (. ve ->) desteklenmiyor')
            else:
                return e

    def primary(self):
        t = self.tok
        pos = dict(file=t.file, line=t.line)
        if t.kind == 'num':
            self.next()
            v, unsigned, dec = t.value
            return N.Num(v, unsigned, dec, **pos)
        if t.kind == 'chr':
            self.next()
            return N.Num(t.value, False, True, **pos)
        if t.kind == 'str':
            data = b''
            while self.tok.kind == 'str':       # bitişik metinler birleşir
                data += self.next().value
            return N.Str(data, None, **pos)
        if t.kind == 'id':
            self.next()
            if t.value in self.enum_consts:
                return N.Num(self.enum_consts[t.value][0], False, True, **pos)
            return N.Ident(t.value, None, **pos)
        if t.is_op('('):
            self.next()
            e = self.expression()
            self.expect(')')
            return e
        if t.kind == 'kw' and t.value in UNSUPPORTED_TYPES:
            self.error(UNSUPPORTED_TYPES[t.value])
        self.error(f'ifade bekleniyor, {self.describe(t)} bulundu')


def parse(toks):
    return Parser(toks).parse_program()
