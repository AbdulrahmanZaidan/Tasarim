"""Sözdizim ağacı (AST) düğümleri.

Ayrıştırıcı düğümleri üretir; anlam çözümleyici (sema) ifadelere `type` yazar,
adları sembollere bağlar, örtük dönüşümleri `Cast(implicit=True)` olarak ekler.
"""


class Node:
    _fields = ()

    def __init__(self, *args, file='<kaynak>', line=0):
        for name, value in zip(self._fields, args):
            setattr(self, name, value)
        for name in self._fields[len(args):]:
            setattr(self, name, None)
        self.file, self.line = file, line

    def at(self, where):
        self.file, self.line = where.file, where.line
        return self

    def __repr__(self):
        inner = ', '.join(f'{f}={getattr(self, f)!r}' for f in self._fields)
        return f'{type(self).__name__}({inner})'


class Expr(Node):
    type = None


# --- ifadeler ---------------------------------------------------------------

class Num(Expr):            # tamsayı sabiti; sema sonrası Const olur
    _fields = ('value', 'unsigned', 'decimal')


class Const(Expr):          # tipi belli, katlanmış sabit (işaretçi tipli de olabilir)
    _fields = ('value',)


class Str(Expr):            # metin sabiti; sema bir ROM etiketi atar
    _fields = ('data', 'label')


class Ident(Expr):
    _fields = ('name', 'sym')


class Unary(Expr):          # op: '-', '+', '~', '!'
    _fields = ('op', 'operand')


class Deref(Expr):
    _fields = ('operand',)


class AddrOf(Expr):         # &x; dizi ve metin için sema da üretir (decay)
    _fields = ('operand',)


class Binary(Expr):         # aritmetik, bit, kaydırma, karşılaştırma
    _fields = ('op', 'left', 'right', 'exact')


class Logical(Expr):        # '&&', '||'
    _fields = ('op', 'left', 'right')


class Assign(Expr):
    _fields = ('target', 'value')


class CompoundAssign(Expr):
    """target op= value. Sema `expr`'i doldurur: target'ın tipine dönüştürülmüş
    tam işlem ağacı; içinde target'ın okunduğu yer `LvRead`."""
    _fields = ('op', 'target', 'value', 'expr')


class IncDec(Expr):
    """++/--. Sema, ön ek için CompoundAssign üretir; son ek için `expr` doldurulur."""
    _fields = ('op', 'prefix', 'target', 'expr')


class LvRead(Expr):         # bileşik atamada hedefin (bir kez hesaplanmış) değeri
    _fields = ()


class Cond(Expr):
    _fields = ('cond', 'then', 'other')


class Comma(Expr):
    _fields = ('left', 'right')


class Call(Expr):
    _fields = ('func', 'args', 'sym')


class Index(Expr):          # a[i]; sema *(a + i) yapar
    _fields = ('base', 'index')


class Member(Expr):         # a.b, a->b: desteklenmez, yalnız anlamlı hata için
    _fields = ('base', 'name', 'arrow')


class Cast(Expr):
    _fields = ('to', 'operand', 'implicit')


class SizeofType(Expr):
    _fields = ('target',)


class SizeofExpr(Expr):
    _fields = ('operand',)


# --- deyimler ---------------------------------------------------------------

class Block(Node):
    _fields = ('items',)


class DeclStmt(Node):
    _fields = ('decls',)


class ExprStmt(Node):
    _fields = ('expr',)


class If(Node):
    _fields = ('cond', 'then', 'other')


class While(Node):
    _fields = ('cond', 'body')


class DoWhile(Node):
    _fields = ('body', 'cond')


class For(Node):
    _fields = ('init', 'cond', 'step', 'body')


class Switch(Node):
    _fields = ('expr', 'body', 'cases', 'default')


class Case(Node):           # 'case K:' etiketi (switch gövdesi içinde)
    _fields = ('expr', 'value', 'label')


class Default(Node):
    _fields = ('label',)


class Break(Node):
    _fields = ()


class Continue(Node):
    _fields = ()


class Return(Node):
    _fields = ('expr',)


class Empty(Node):
    _fields = ()


# --- bildirimler ------------------------------------------------------------

class VarDecl(Node):
    """Değişken bildirimi. init: ifade, ya da InitList, ya da None."""
    _fields = ('name', 'ctype', 'init', 'storage', 'sym')


class InitList(Node):
    _fields = ('items',)


class FuncDef(Node):
    _fields = ('name', 'ctype', 'params', 'body', 'storage', 'sym')


class FuncDecl(Node):       # prototip
    _fields = ('name', 'ctype', 'params', 'storage')


class Program(Node):
    _fields = ('items',)
