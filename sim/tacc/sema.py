"""Anlam çözümlemesi: tip denetimi, ad çözümleme, örtük dönüşümler, sabit katlama.

Çıktı: her ifade düğümünde `type`; örtük dönüşümler açık `Cast` düğümleri;
`a[i]` -> `*(a + i*boyut)`; dizi/metin -> `AddrOf` (decay); bileşik atama ve
++/-- için tam işlem ağacı (`LvRead` ile). Sabit ifadeler `Const` olur.
Ayrıca: global veri yerleşimi (rom/data/bss), çağrı grafiği, özyineleme denetimi.
"""

from . import nodes as N
from . import typesys as T
from .errors import CompileError

RELOPS = ('<', '>', '<=', '>=', '==', '!=')


class Symbol:
    def __init__(self, name, ctype, kind, asm, where, func=None):
        self.name, self.type, self.kind, self.asm = name, ctype, kind, asm
        self.file, self.line = where.file, where.line
        self.func = func                # yerel/parametre ise sahibi (FuncInfo)
        self.storage = None             # 'rom' | 'data' | 'bss' | 'frame'
        self.init = None                # global: byte listesi (int ya da '<(..)' metni)
        self.defined = False
        self.used = False

    def __repr__(self):
        return f'Symbol({self.name}, {self.type}, {self.kind})'


class FuncInfo:
    def __init__(self, sym, node):
        self.sym, self.node = sym, node
        self.name = sym.name
        self.params = []                # Symbol
        self.locals = []                # Symbol (frame)
        self.calls = []                 # (callee adı, Call düğümü)
        self.names = set()


class Unit:
    """Sema sonucu: codegen'in ihtiyaç duyduğu her şey."""

    def __init__(self):
        self.globals = []               # Symbol (global ve static yerel değişkenler)
        self.funcs = []                 # FuncInfo (tanım sırasıyla)
        self.strings = {}               # bytes -> etiket
        self.func_by_name = {}


def is_null_const(e):
    return isinstance(e, N.Const) and e.value == 0 and (e.type.is_int or
                                                         (e.type.is_ptr and e.type.base.is_void))


def scalar_leaves(t, off):
    """Bir nesnenin bütün skaler elemanları: (ofset, tip)."""
    if t.is_array:
        out = []
        for i in range(t.n):
            out += scalar_leaves(t.base, off + i * t.base.size)
        return out
    return [(off, t)]


def fold_int(op, a, b, t):
    """İki sabit tamsayı üzerinde C işlemi; işlenenler zaten `t` tipinde."""
    if op == '+':
        r = a + b
    elif op == '-':
        r = a - b
    elif op == '*':
        r = a * b
    elif op in ('/', '%'):
        q = abs(a) // abs(b)
        if (a < 0) != (b < 0):
            q = -q
        r = q if op == '/' else a - q * b
    elif op == '&':
        r = a & b
    elif op == '|':
        r = a | b
    elif op == '^':
        r = a ^ b
    elif op == '<<':
        r = a << b
    elif op == '>>':
        r = a >> b                      # Python: işaretliyse aritmetik
    else:
        raise AssertionError(op)
    return t.wrap(r)


def compare(op, a, b):
    return int({'<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b,
                '==': a == b, '!=': a != b}[op])


class Sema:
    def __init__(self):
        self.unit = Unit()
        self.scopes = [{}]
        self.func = None                # şu anki FuncInfo
        self.loops = 0                  # continue için
        self.breakables = 0             # break için
        self.switches = []              # [{'values': {}, 'default': None}]

    # --- yardımcılar ----------------------------------------------------------
    def error(self, msg, where):
        raise CompileError(msg, where.file, where.line)

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def const(self, value, t, where):
        c = N.Const(value).at(where)
        c.type = t.unqualified()
        return c

    def cast(self, e, to, implicit=True):
        """`e`yi `to` tipine dönüştüren düğüm (sabitse katlar)."""
        to = to.unqualified()
        if to.is_void:
            c = N.Cast(to, e, implicit).at(e)
            c.type = to
            return c
        if isinstance(e, N.Const) and (to.is_int or to.is_ptr):
            return self.const(to.wrap(e.value), to, e)
        if T.same_type(e.type.unqualified(), to):
            return e
        c = N.Cast(to, e, implicit).at(e)
        c.type = to
        return c

    def rvalue(self, e):
        """Değer bağlamı: dizi -> işaretçi, fonksiyon adı hata, niteleyiciler düşer."""
        t = e.type
        if t.is_array:
            a = N.AddrOf(e).at(e)
            a.type = T.PtrT(t.base)
            return a
        if t.is_func:
            self.error('fonksiyon işaretçisi desteklenmiyor (fonksiyon adı yalnız çağrılabilir)', e)
        return e

    def value(self, e):
        return self.rvalue(self.expr(e))

    def scalar(self, e, what):
        if not e.type.is_scalar:
            self.error(f'{what} için sayı ya da işaretçi gerekir ({e.type} verildi)', e)
        return e

    def is_lvalue(self, e):
        if isinstance(e, N.Ident):
            return e.sym.kind != 'func'
        return isinstance(e, (N.Deref, N.Str))

    def check_modifiable(self, e, what):
        if not self.is_lvalue(e) or isinstance(e, N.Str):
            self.error(f'{what}: sol taraf değiştirilebilir bir değişken değil', e)
        if e.type.is_array:
            self.error(f'{what}: diziye atama yapılamaz', e)
        if e.type.const:
            self.error(f'{what}: const bir nesne değiştirilemez', e)

    def convert(self, e, to, where, what):
        """Atama kuralları (örtük dönüşüm)."""
        src = e.type
        to_u = to.unqualified()
        if to_u.is_int and src.is_int:
            return self.cast(e, to_u)
        if to_u.is_ptr:
            if src.is_ptr:
                a, b = to_u.base, src.base
                if not (a.is_void or b.is_void or T.same_type(a.unqualified(), b.unqualified())):
                    self.error(f'{what}: uyumsuz işaretçi tipleri ({src} -> {to_u})', where)
                if (b.const and not a.const) or (b.volatile and not a.volatile):
                    self.error(f'{what}: niteleyici (const/volatile) kayboluyor ({src} -> {to_u})', where)
                return self.cast(e, to_u)
            if src.is_int and is_null_const(e):
                return self.const(0, to_u, e)
            self.error(f'{what}: tamsayıdan işaretçiye örtük dönüşüm yok ({src} -> {to_u}); cast kullanın',
                       where)
        if to_u.is_int and src.is_ptr:
            self.error(f'{what}: işaretçiden tamsayıya örtük dönüşüm yok ({src} -> {to_u}); cast kullanın',
                       where)
        self.error(f'{what}: {src} tipi {to_u} tipine dönüştürülemez', where)

    # --- tipler ---------------------------------------------------------------
    def resolve_type(self, t, where):
        """Dizi boyutu ifadelerini sabite çevirir."""
        if t.is_array:
            base = self.resolve_type(t.base, where)
            n = t.n
            if isinstance(n, N.Expr):
                c = self.value(n)
                if not isinstance(c, N.Const) or not c.type.is_int:
                    self.error('dizi boyutu sabit bir tamsayı olmalı', where)
                n = c.value
            if n is not None and n <= 0:
                self.error('dizi boyutu pozitif olmalı', where)
            if base.is_array and base.n is None:
                self.error('çok boyutlu dizide yalnız ilk boyut boş bırakılabilir', where)
            r = T.ArrT(base, n)
            return r.qualified(t.const, t.volatile)
        if t.is_ptr:
            return T.PtrT(self.resolve_type(t.base, where)).qualified(t.const, t.volatile)
        if t.is_func:
            return T.FuncT(self.resolve_type(t.ret, where),
                           [self.resolve_type(p, where) for p in t.params], t.variadic)
        return t

    # --- program --------------------------------------------------------------
    def program(self, prog):
        # 1. Fonksiyonları önceden bildir (tanım sırası serbest)
        for item in prog.items:
            if isinstance(item, (N.FuncDef, N.FuncDecl)):
                self.declare_func(item)
        # 2. Sırayla işle
        for item in prog.items:
            if isinstance(item, N.VarDecl):
                self.global_var(item)
            elif isinstance(item, N.FuncDef):
                self.func_def(item)
        self.finish(prog)
        return self.unit

    def declare_func(self, d):
        t = self.resolve_type(d.ctype, d)
        if d.name.startswith('_'):
            self.error(f"'_' ile başlayan adlar derleyiciye ayrılmıştır: {d.name}", d)
        g = self.scopes[0]
        sym = g.get(d.name)
        if sym is not None:
            if sym.kind != 'func':
                self.error(f'{d.name} hem değişken hem fonksiyon olarak bildirilmiş', d)
            if not T.same_type(sym.type, t):
                self.error(f'{d.name}: önceki bildirimle uyumsuz tip ({sym.type} / {t})', d)
            if isinstance(d, N.FuncDef):
                if sym.defined:
                    self.error(f'{d.name} fonksiyonu iki kez tanımlı', d)
                sym.defined = True
                sym.node = d
            return
        sym = Symbol(d.name, t, 'func', '_' + d.name, d)
        sym.defined = isinstance(d, N.FuncDef)
        sym.node = d if sym.defined else None
        g[d.name] = sym

    # --- global değişkenler ---------------------------------------------------
    def global_var(self, d, local_static=False):
        t = self.resolve_type(d.ctype, d)
        if t.is_void:
            self.error(f'{d.name}: void tipte değişken olamaz', d)
        if not local_static and d.name.startswith('_'):
            self.error(f"'_' ile başlayan adlar derleyiciye ayrılmıştır: {d.name}", d)
        scope = self.scopes[-1] if local_static else self.scopes[0]
        sym = scope.get(d.name)
        if sym is not None and not local_static:
            if sym.kind == 'func':
                self.error(f'{d.name} hem fonksiyon hem değişken olarak bildirilmiş', d)
            same = T.same_type(sym.type, t) or (sym.type.is_array and t.is_array and
                                               (sym.type.n is None or t.n is None) and
                                               T.same_type(sym.type.base, t.base))
            if not same:
                self.error(f'{d.name}: önceki bildirimle uyumsuz tip ({sym.type} / {t})', d)
            if t.is_array and t.n is not None:
                sym.type = t
        elif sym is not None:
            self.error(f'{d.name} bu blokta iki kez bildirilmiş', d)
        else:
            if local_static:
                asm = self.local_asm(d.name)
                sym = Symbol(d.name, t, 'static', asm, d, self.func)
            else:
                sym = Symbol(d.name, t, 'global', '_' + d.name, d)
            scope[d.name] = sym
            self.unit.globals.append(sym)
        d.sym = sym
        if d.storage == 'extern' and d.init is None:
            return sym
        if d.init is not None:
            if sym.init is not None:
                self.error(f'{d.name} iki kez başlangıç değeri almış', d)
            if sym.type.is_array and sym.type.n is None and isinstance(d.init, N.Str):
                sym.type = T.ArrT(sym.type.base, len(d.init.data) + 1).qualified(
                    sym.type.const, sym.type.volatile)
            items = self.flatten_init(sym.type, d.init, d)
            if sym.type.is_array and sym.type.n is None:
                n = (max((off for off, _, _ in items), default=-1) // sym.type.base.size) + 1
                sym.type = T.ArrT(sym.type.base, n)
            sym.init = self.static_bytes(sym.type, items, d)
        sym.defined = True
        if sym.type.is_array and sym.type.n is None:
            self.error(f'{d.name}: dizi boyutu belirtilmemiş', d)
        return sym

    def local_asm(self, name):
        f = self.func
        base = f'_{f.name}.{name}'
        asm, k = base, 1
        while asm in f.names:
            k += 1
            asm = f'{base}.{k}'
        f.names.add(asm)
        return asm

    # --- başlangıç değerleri --------------------------------------------------
    def flatten_init(self, t, init, where):
        """Başlangıç değerini (bayt ofseti, skaler tip, ifade) listesine açar."""
        out = []
        if isinstance(init, N.InitList):
            items = list(init.items)
            self._init_into(t, items, 0, out, where, top=True)
            if items:
                self.error('başlangıç listesinde fazla eleman var', items[0])
        elif t.is_array:
            if isinstance(init, N.Str) and t.base.is_int and t.base.size == 1:
                self._init_string(t, init, 0, out)
            else:
                self.error('dizi başlangıç değeri { ... } ya da metin olmalı', where)
        else:
            out.append((0, t, init))
        return out

    def _init_string(self, t, s, off, out):
        data = s.data + b'\0'
        if t.n is not None:
            if len(s.data) > t.n:
                self.error(f'metin diziye sığmıyor ({len(s.data)} > {t.n})', s)
            data = data[:t.n]
        for i, b in enumerate(data):
            out.append((off + i, t.base, self.const(b, T.INT, s)))

    def _init_into(self, t, items, off, out, where, top=False):
        """`items`'ten (baştan tüketerek) `t` tipindeki nesneyi doldurur."""
        if t.is_array:
            if items and isinstance(items[0], N.Str) and t.base.is_int and t.base.size == 1:
                self._init_string(t, items.pop(0), off, out)
                return
            if not top and items and isinstance(items[0], N.InitList):
                sub = list(items.pop(0).items)
                self._init_into(t, sub, off, out, where, top=True)
                if sub:
                    self.error('başlangıç listesinde fazla eleman var', sub[0])
                return
            i = 0
            while items and (t.n is None or i < t.n):
                self._init_into(t.base, items, off + i * t.base.size, out, where)
                i += 1
            return
        if not items:
            return
        item = items.pop(0)
        if isinstance(item, N.InitList):
            sub = list(item.items)
            if not sub:
                self.error('boş { } başlangıç değeri', item)
            self._init_into(t, sub, off, out, where)
            if sub:
                self.error('skaler için fazla başlangıç değeri', sub[0])
            return
        out.append((off, t, item))

    def static_bytes(self, t, items, where):
        """Sabit başlangıç değerlerini bayt listesine çevirir (int ya da asm ifadesi)."""
        data = [0] * t.size
        for off, st, e in items:
            v = self.convert(self.value(e), st, e, 'başlangıç değeri')
            if isinstance(v, N.Const):
                val = v.value & 0xFFFF
                data[off] = val & 0xFF
                if st.size == 2:
                    data[off + 1] = val >> 8
                continue
            ac = self.addr_const(v)
            if ac is None or st.size != 2:
                self.error('global başlangıç değeri sabit olmalı (sayı ya da global adres)', e)
            sym, k = ac
            expr = sym if k == 0 else f'{sym}+{k}' if k > 0 else f'{sym}-{-k}'
            data[off] = f'<({expr})'
            data[off + 1] = f'>({expr})'
        return data

    def addr_const(self, e):
        """Adres sabiti: (asm adı, ofset) ya da None."""
        if isinstance(e, N.Cast) and e.type.size == 2:
            return self.addr_const(e.operand)
        if isinstance(e, N.AddrOf):
            return self.lvalue_addr(e.operand)
        if isinstance(e, N.Binary) and e.op in '+-' and e.type.is_ptr:
            base = self.addr_const(e.left)
            if base is not None and isinstance(e.right, N.Const):
                k = e.right.value if e.op == '+' else -e.right.value
                return base[0], base[1] + k
        return None

    def lvalue_addr(self, e):
        if isinstance(e, N.Ident) and e.sym.kind in ('global', 'static'):
            return e.sym.asm, 0
        if isinstance(e, N.Str):
            return e.label, 0
        if isinstance(e, N.Deref) and not isinstance(e.operand, N.Const):
            return self.addr_const(e.operand)
        return None

    # --- fonksiyonlar ---------------------------------------------------------
    def func_def(self, d):
        sym = self.scopes[0][d.name]
        f = FuncInfo(sym, d)
        sym.info = f
        d.sym = sym
        self.unit.funcs.append(f)
        self.unit.func_by_name[d.name] = f
        self.func = f
        self.scopes.append({})
        for (ptok, ptype) in d.params:
            if ptok is None:
                self.error(f'{d.name}: parametre adı eksik', d)
            if ptok.value in self.scopes[-1]:
                self.error(f'parametre iki kez tanımlı: {ptok.value}', ptok)
            ptype = self.resolve_type(ptype, ptok)
            psym = Symbol(ptok.value, ptype, 'param', self.local_asm(ptok.value), ptok, f)
            psym.storage = 'frame'
            self.scopes[-1][ptok.value] = psym
            f.params.append(psym)
        self.block(d.body, new_scope=False)
        self.scopes.pop()
        self.func = None

    # --- deyimler ---------------------------------------------------------------
    def block(self, b, new_scope=True):
        if new_scope:
            self.scopes.append({})
        for s in b.items:
            self.stmt(s)
        if new_scope:
            self.scopes.pop()

    def local_decl(self, ds):
        for d in ds.decls:
            if isinstance(d, N.FuncDecl):
                self.declare_func(d)
                continue
            if d.storage == 'extern':
                self.error('yerel extern bildirimi desteklenmiyor; globali dışarıda bildirin', d)
            if d.storage == 'static':
                self.global_var(d, local_static=True)
                continue
            t = self.resolve_type(d.ctype, d)
            if t.is_void:
                self.error(f'{d.name}: void tipte değişken olamaz', d)
            if d.name in self.scopes[-1]:
                self.error(f'{d.name} bu blokta iki kez bildirilmiş', d)
            if t.is_array and t.n is None:
                if isinstance(d.init, N.Str):
                    t = T.ArrT(t.base, len(d.init.data) + 1)
                elif isinstance(d.init, N.InitList):
                    probe = self.flatten_init(t, d.init, d)
                    n = (max((off for off, _, _ in probe), default=-1) // t.base.size) + 1
                    t = T.ArrT(t.base, n)
                else:
                    self.error(f'{d.name}: dizi boyutu belirtilmemiş', d)
            sym = Symbol(d.name, t, 'local', self.local_asm(d.name), d, self.func)
            sym.storage = 'frame'
            self.func.locals.append(sym)
            d.sym = sym
            d.init_stores = []
            if d.init is not None:
                # Her girişte yapılan atamalar (const yerel de başlangıç değeri alabilir)
                items = self.flatten_init(t, d.init, d)
                if t.is_array:
                    covered = {off for off, _, _ in items}
                    for off, st in scalar_leaves(t, 0):
                        if off not in covered:
                            items.append((off, st, self.const(0, T.INT, d)))
                for off, st, e in items:
                    v = self.convert(self.value(e), st, e, 'başlangıç değeri')
                    d.init_stores.append((off, st, v))
            self.scopes[-1][d.name] = sym

    def cond_expr(self, e, what):
        return self.scalar(self.value(e), what)

    def stmt(self, s):
        if isinstance(s, N.Block):
            self.block(s)
        elif isinstance(s, N.DeclStmt):
            self.local_decl(s)
        elif isinstance(s, N.ExprStmt):
            s.expr = self.value(s.expr)
        elif isinstance(s, N.If):
            s.cond = self.cond_expr(s.cond, 'if koşulu')
            self.sub_stmt(s.then)
            if s.other is not None:
                self.sub_stmt(s.other)
        elif isinstance(s, N.While):
            s.cond = self.cond_expr(s.cond, 'while koşulu')
            self.loop_body(s.body)
        elif isinstance(s, N.DoWhile):
            self.loop_body(s.body)
            s.cond = self.cond_expr(s.cond, 'do-while koşulu')
        elif isinstance(s, N.For):
            self.scopes.append({})
            if isinstance(s.init, N.DeclStmt):
                self.local_decl(s.init)
            elif s.init is not None:
                s.init.expr = self.value(s.init.expr)
            if s.cond is not None:
                s.cond = self.cond_expr(s.cond, 'for koşulu')
            if s.step is not None:
                s.step = self.value(s.step)
            self.loop_body(s.body)
            self.scopes.pop()
        elif isinstance(s, N.Switch):
            e = self.value(s.expr)
            if not e.type.is_int:
                self.error(f'switch ifadesi tamsayı olmalı ({e.type} verildi)', s)
            s.expr = self.cast(e, T.promote(e.type))
            s.cases, s.default = [], None
            self.switches.append(s)
            self.breakables += 1
            self.sub_stmt(s.body)
            self.breakables -= 1
            self.switches.pop()
        elif isinstance(s, N.Case):
            if not self.switches:
                self.error("'case' switch dışında", s)
            sw = self.switches[-1]
            c = self.value(s.expr)
            if not isinstance(c, N.Const) or not c.type.is_int:
                self.error('case değeri sabit bir tamsayı olmalı', s)
            s.value = self.cast(c, sw.expr.type).value
            for other in sw.cases:
                if other.value == s.value:
                    self.error(f'case değeri iki kez kullanılmış: {s.value}', s)
            sw.cases.append(s)
        elif isinstance(s, N.Default):
            if not self.switches:
                self.error("'default' switch dışında", s)
            sw = self.switches[-1]
            if sw.default is not None:
                self.error("switch içinde iki 'default'", s)
            sw.default = s
        elif isinstance(s, N.Break):
            if not self.breakables:
                self.error("'break' döngü ya da switch dışında", s)
        elif isinstance(s, N.Continue):
            if not self.loops:
                self.error("'continue' döngü dışında", s)
        elif isinstance(s, N.Return):
            ret = self.func.sym.type.ret
            if s.expr is None:
                if not ret.is_void:
                    self.error(f'{self.func.name} bir değer döndürmeli ({ret})', s)
            else:
                v = self.value(s.expr)
                if ret.is_void:
                    if not v.type.is_void:
                        self.error(f'void fonksiyon {self.func.name} değer döndüremez', s)
                    s.expr = v
                else:
                    s.expr = self.convert(v, ret, s, 'return')
        elif isinstance(s, N.Empty):
            pass
        else:
            self.error(f'beklenmeyen deyim: {type(s).__name__}', s)

    def sub_stmt(self, s):
        """if/while gövdesi gibi alt deyim (kendi kapsamı)."""
        self.scopes.append({})
        self.stmt(s)
        self.scopes.pop()

    def loop_body(self, s):
        self.loops += 1
        self.breakables += 1
        self.sub_stmt(s)
        self.loops -= 1
        self.breakables -= 1

    # --- ifadeler -------------------------------------------------------------
    def expr(self, e):
        m = getattr(self, 'e_' + type(e).__name__, None)
        if m is None:
            self.error(f'desteklenmeyen ifade: {type(e).__name__}', e)
        return m(e)

    def e_Num(self, e):
        v = e.value
        if e.unsigned or v > 0x7FFF:
            t = T.UINT
        else:
            t = T.INT
        return self.const(t.wrap(v), t, e)

    def e_Const(self, e):
        return e

    def e_Str(self, e):
        lab = self.unit.strings.get(e.data)
        if lab is None:
            lab = f'__str{len(self.unit.strings)}'
            self.unit.strings[e.data] = lab
        e.label = lab
        e.type = T.ArrT(T.CHAR, len(e.data) + 1)
        return e

    def e_Ident(self, e):
        sym = self.lookup(e.name)
        if sym is None:
            self.error(f'tanımsız ad: {e.name}', e)
        sym.used = True
        e.sym = sym
        e.type = sym.type
        return e

    def e_Member(self, e):
        self.error('struct/union üyesi desteklenmiyor', e)

    def e_SizeofType(self, e):
        t = self.resolve_type(e.target, e)
        return self.sizeof(t, e)

    def e_SizeofExpr(self, e):
        inner = self.expr(e.operand)
        return self.sizeof(inner.type, e)

    def sizeof(self, t, where):
        if t.is_void or t.is_func or t.size == 0:
            self.error(f'sizeof uygulanamaz: {t}', where)
        return self.const(t.size, T.UINT, where)

    def e_Cast(self, e):
        to = self.resolve_type(e.to, e)
        self.check_cast_type(to, e)
        v = self.value(e.operand)
        if to.is_void:
            return self.cast(v, to, implicit=False)
        if not v.type.is_scalar:
            self.error(f'{v.type} tipi {to} tipine dönüştürülemez', e)
        if not to.is_scalar:
            self.error(f'{to} tipine dönüştürme yapılamaz', e)
        if isinstance(v, N.Const):
            return self.const(to.wrap(v.value), to, e)
        c = N.Cast(to.unqualified(), v, False).at(e)
        c.type = to.unqualified()
        return c

    def check_cast_type(self, t, where):
        if t.is_ptr and t.base.is_func:
            self.error('fonksiyon işaretçisi desteklenmiyor', where)
        if t.is_array or t.is_func:
            self.error(f'{t} tipine dönüştürme yapılamaz', where)

    def e_Unary(self, e):
        v = self.value(e.operand)
        op = e.op
        if op == '!':
            self.scalar(v, "'!'")
            if isinstance(v, N.Const):
                return self.const(int(v.value == 0), T.INT, e)
            e.operand = v
            e.type = T.INT
            return e
        if not v.type.is_int:
            self.error(f"'{op}' işleci tamsayı ister ({v.type} verildi)", e)
        t = T.promote(v.type)
        v = self.cast(v, t)
        if op == '+':
            return v
        if isinstance(v, N.Const):
            return self.const(t.wrap(-v.value if op == '-' else ~v.value), t, e)
        e.operand = v
        e.type = t
        return e

    def e_Deref(self, e):
        p = self.value(e.operand)
        if not p.type.is_ptr:
            self.error(f"'*' işleci işaretçi ister ({p.type} verildi)", e)
        if p.type.base.is_void:
            self.error('void* işaretçisi doğrudan okunamaz; önce cast edin', e)
        e.operand = p
        e.type = p.type.base
        return e

    def e_AddrOf(self, e):
        inner = self.expr(e.operand)
        if isinstance(inner, N.Ident) and inner.sym.kind == 'func':
            self.error('fonksiyon işaretçisi desteklenmiyor (&fonksiyon)', e)
        if isinstance(inner, N.Deref):              # &*p -> p
            return inner.operand
        if not self.is_lvalue(inner):
            self.error("'&' yalnız değişkene uygulanabilir", e)
        e.operand = inner
        e.type = T.PtrT(inner.type)
        return e

    def e_Index(self, e):
        a = self.value(e.base)
        i = self.value(e.index)
        if i.type.is_ptr and a.type.is_int:
            a, i = i, a
        if not a.type.is_ptr or not i.type.is_int:
            self.error('[] için bir işaretçi/dizi ve bir tamsayı gerekir', e)
        if a.type.base.is_void:
            self.error('void* indekslenemez', e)
        d = N.Deref(self.ptr_add(a, i, '+', e)).at(e)
        d.type = a.type.base
        return d

    def ptr_add(self, p, i, op, where):
        size = p.type.base.size
        if size == 0:
            self.error(f'{p.type} üzerinde işaretçi aritmetiği yapılamaz', where)
        i = self.cast(i, T.INT if T.promote(i.type).signed else T.UINT)
        if size != 1:
            i = self.binary_checked('*', i, self.const(size, T.INT, where), where)
        return self.padd(p, i, op, where)

    def padd(self, p, i, op, where):
        """İşaretçi + ölçeklenmiş indeks; sabit parçalar tabana toplanır."""
        if op == '+' and isinstance(i, N.Binary) and i.op == '+' and i.type.is_int:
            for c, rest in ((i.right, i.left), (i.left, i.right)):
                if isinstance(c, N.Const):
                    return self.padd(self.padd(p, c, '+', where), rest, '+', where)
        if isinstance(i, N.Const):
            k = i.value if op == '+' else -i.value
            if isinstance(p, N.Const):
                return self.const(p.type.wrap(p.value + k), p.type, where)
            if isinstance(p, N.Binary) and p.op in '+-' and p.type.is_ptr                     and isinstance(p.right, N.Const):
                k += p.right.value if p.op == '+' else -p.right.value
                return self.padd(p.left, self.const(T.INT.wrap(k), T.INT, where), '+', where)
            if k == 0:
                return p
        b = N.Binary(op, p, i).at(where)
        b.type = p.type.unqualified()
        return b

    def e_Binary(self, e):
        return self.binary_checked(e.op, self.value(e.left), self.value(e.right), e)

    def binary_checked(self, op, l, r, where):
        lt, rt = l.type, r.type
        if op in RELOPS:
            return self.relational(op, l, r, where)
        if op == '+':
            if lt.is_ptr and rt.is_int:
                return self.ptr_add(l, r, '+', where)
            if lt.is_int and rt.is_ptr:
                return self.ptr_add(r, l, '+', where)
        if op == '-':
            if lt.is_ptr and rt.is_int:
                return self.ptr_add(l, r, '-', where)
            if lt.is_ptr and rt.is_ptr:
                if not T.same_type(lt.base.unqualified(), rt.base.unqualified()):
                    self.error(f'uyumsuz işaretçilerin farkı ({lt} - {rt})', where)
                size = lt.base.size
                if size == 0:
                    self.error('void* farkı alınamaz', where)
                d = self.make_binary('-', self.cast(l, T.INT), self.cast(r, T.INT), T.INT, where)
                if size == 1:
                    return d
                q = self.make_binary('/', d, self.const(size, T.INT, where), T.INT, where)
                if isinstance(q, N.Binary):
                    q.exact = True
                return q
        if not lt.is_int or not rt.is_int:
            self.error(f"'{op}' işleci için geçersiz işlenenler ({lt}, {rt})", where)
        if op in ('<<', '>>'):
            t = T.promote(lt)
            r = self.cast(r, T.promote(rt))
            if isinstance(r, N.Const) and not 0 <= r.value <= 15:
                self.error(f'kaydırma miktarı 0–15 aralığında olmalı ({r.value})', where)
            return self.make_binary(op, self.cast(l, t), r, t, where)
        t = T.arith_conv(lt, rt)
        return self.make_binary(op, self.cast(l, t), self.cast(r, t), t, where)

    def make_binary(self, op, l, r, t, where):
        if isinstance(l, N.Const) and isinstance(r, N.Const) and t.is_int:
            if op in ('/', '%') and r.value == 0:
                self.error('sıfıra bölme', where)
            return self.const(fold_int(op, l.value, r.value, t), t, where)
        b = N.Binary(op, l, r, False).at(where)
        b.type = t
        return b

    def relational(self, op, l, r, where):
        lt, rt = l.type, r.type
        if lt.is_int and rt.is_int:
            t = T.arith_conv(lt, rt)
        elif lt.is_ptr and rt.is_ptr:
            a, b = lt.base.unqualified(), rt.base.unqualified()
            if not (a.is_void or b.is_void or T.same_type(a, b)):
                self.error(f'uyumsuz işaretçiler karşılaştırılıyor ({lt}, {rt})', where)
            t = T.UINT
        elif lt.is_ptr and is_null_const(r) or rt.is_ptr and is_null_const(l):
            t = T.UINT
        else:
            self.error(f"'{op}' için geçersiz işlenenler ({lt}, {rt})", where)
        l, r = self.cast(l, t), self.cast(r, t)
        if isinstance(l, N.Const) and isinstance(r, N.Const):
            return self.const(compare(op, l.value, r.value), T.INT, where)
        b = N.Binary(op, l, r, False).at(where)
        b.type = T.INT
        return b

    def e_Logical(self, e):
        l = self.scalar(self.value(e.left), f"'{e.op}'")
        r = self.scalar(self.value(e.right), f"'{e.op}'")
        if isinstance(l, N.Const):
            lv = l.value != 0
            if e.op == '&&' and not lv:
                return self.const(0, T.INT, e)
            if e.op == '||' and lv:
                return self.const(1, T.INT, e)
            if isinstance(r, N.Const):
                return self.const(int(r.value != 0), T.INT, e)
        e.left, e.right = l, r
        e.type = T.INT
        return e

    def e_Cond(self, e):
        c = self.scalar(self.value(e.cond), '?: koşulu')
        a, b = self.value(e.then), self.value(e.other)
        at, bt = a.type, b.type
        if at.is_int and bt.is_int:
            t = T.arith_conv(at, bt)
        elif at.is_void and bt.is_void:
            t = T.VOID
        elif at.is_ptr and bt.is_ptr:
            x, y = at.base.unqualified(), bt.base.unqualified()
            if not (x.is_void or y.is_void or T.same_type(x, y)):
                self.error(f'?: dallarında uyumsuz işaretçiler ({at}, {bt})', e)
            t = at.unqualified() if not x.is_void else bt.unqualified()
        elif at.is_ptr and is_null_const(b):
            t = at.unqualified()
        elif bt.is_ptr and is_null_const(a):
            t = bt.unqualified()
        else:
            self.error(f'?: dallarının tipleri uyumsuz ({at}, {bt})', e)
        a, b = self.cast(a, t), self.cast(b, t)
        if isinstance(c, N.Const):
            return a if c.value else b
        e.cond, e.then, e.other = c, a, b
        e.type = t
        return e

    def e_Comma(self, e):
        e.left = self.value(e.left)
        e.right = self.value(e.right)
        e.type = e.right.type
        return e

    def e_Assign(self, e):
        tgt = self.expr(e.target)
        self.check_modifiable(tgt, 'atama')
        v = self.convert(self.value(e.value), tgt.type, e, 'atama')
        e.target, e.value = tgt, v
        e.type = tgt.type.unqualified()
        return e

    def lvread(self, tgt, where):
        r = N.LvRead().at(where)
        r.type = tgt.type.unqualified()
        return r

    def update_expr(self, op, tgt, rhs, where):
        """`tgt op rhs` hesaplanıp tgt tipine dönüştürülmüş ağaç (LvRead ile)."""
        cur = self.lvread(tgt, where)
        if op in ('+', '-') and tgt.type.is_ptr:
            if not rhs.type.is_int:
                self.error(f"işaretçiye '{op}=' ile yalnız tamsayı eklenebilir", where)
            res = self.ptr_add(cur, rhs, op, where)
        else:
            if not tgt.type.is_int:
                self.error(f"'{op}=' işleci tamsayı ister ({tgt.type})", where)
            res = self.binary_checked(op, cur, rhs, where)
        return self.convert(res, tgt.type, where, f"'{op}='")

    def e_CompoundAssign(self, e):
        tgt = self.expr(e.target)
        self.check_modifiable(tgt, f"'{e.op}='")
        rhs = self.value(e.value)
        e.target, e.value = tgt, rhs
        e.expr = self.update_expr(e.op, tgt, rhs, e)
        e.type = tgt.type.unqualified()
        return e

    def e_IncDec(self, e):
        tgt = self.expr(e.target)
        self.check_modifiable(tgt, f"'{e.op}'")
        if not tgt.type.is_scalar:
            self.error(f"'{e.op}' sayı ya da işaretçi ister", e)
        one = self.const(1, T.INT, e)
        op = e.op[0]
        upd = self.update_expr(op, tgt, one, e)
        if e.prefix:
            c = N.CompoundAssign(op, tgt, one, upd).at(e)
            c.type = tgt.type.unqualified()
            return c
        e.target, e.expr = tgt, upd
        e.type = tgt.type.unqualified()
        return e

    def e_Call(self, e):
        f = e.func
        if not isinstance(f, N.Ident):
            self.error('yalnız adıyla fonksiyon çağrılabilir (fonksiyon işaretçisi desteklenmiyor)', e)
        sym = self.lookup(f.name)
        if sym is None:
            self.error(f'bildirilmemiş fonksiyon: {f.name}', e)
        if sym.kind != 'func':
            self.error(f'{f.name} bir fonksiyon değil', e)
        sym.used = True
        ft = sym.type
        if len(e.args) != len(ft.params):
            self.error(f'{f.name}: {len(ft.params)} argüman bekleniyor, {len(e.args)} verildi', e)
        args = []
        for k, (a, pt) in enumerate(zip(e.args, ft.params)):
            args.append(self.convert(self.value(a), pt, a, f'{f.name} argüman {k + 1}'))
        e.args = args
        e.sym = sym
        e.type = ft.ret.unqualified()
        if self.func is None:
            self.error('fonksiyon dışında çağrı yapılamaz', e)
        self.func.calls.append((f.name, e))
        return e

    def e_LvRead(self, e):
        return e

    # --- son denetimler ---------------------------------------------------------
    def finish(self, prog):
        g = self.scopes[0]
        main = g.get('main')
        if main is None or main.kind != 'func' or not main.defined:
            raise CompileError('main fonksiyonu tanımlı değil', prog.file, 1)
        if main.type.params:
            self.error('main parametre almamalı: int main(void)', main)
        for f in self.unit.funcs:
            for name, call in f.calls:
                callee = g[name]
                if not callee.defined:
                    self.error(f'{name} fonksiyonu bildirilmiş ama tanımlanmamış', call)
        for sym in self.unit.globals:
            if not sym.defined and sym.used:
                self.error(f'{sym.name} bildirilmiş (extern) ama tanımlanmamış', sym)
            if sym.type.is_array and sym.type.n is None:
                self.error(f'{sym.name}: dizi boyutu belirtilmemiş', sym)
            if sym.type.is_array:
                const = sym.type.elem_quals()[0]
            else:
                const = sym.type.const
            if const:
                sym.storage = 'rom'
            elif sym.init is not None and any(b != 0 for b in sym.init):
                sym.storage = 'data'
            else:
                sym.storage = 'bss'
        self.check_recursion()

    def check_recursion(self):
        funcs = self.unit.func_by_name
        state = {}                      # 1 = ziyarette, 2 = bitti

        def visit(name, path):
            state[name] = 1
            for callee, call in funcs[name].calls:
                if state.get(callee) == 1:
                    cyc = path[path.index(callee):] + [callee]
                    self.error('özyineleme (recursion) desteklenmiyor: ' + ' -> '.join(cyc), call)
                if state.get(callee) is None:
                    visit(callee, path + [callee])
            state[name] = 2

        for f in self.unit.funcs:
            if state.get(f.name) is None:
                visit(f.name, [f.name])


def analyze(prog):
    return Sema().program(prog)
