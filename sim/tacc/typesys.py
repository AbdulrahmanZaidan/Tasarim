"""C tipleri (TA-8: char 8 bit işaretsiz, int 16 bit işaretli, işaretçi 16 bit)."""


class CType:
    const = False
    volatile = False

    def qualified(self, const=False, volatile=False):
        """Niteleyicileri eklenmiş bir kopya."""
        if (const or self.const) == self.const and (volatile or self.volatile) == self.volatile:
            return self
        t = self._copy()
        t.const = self.const or const
        t.volatile = self.volatile or volatile
        return t

    def unqualified(self):
        if not self.const and not self.volatile:
            return self
        t = self._copy()
        t.const = t.volatile = False
        return t

    def _quals(self):
        return ('const ' if self.const else '') + ('volatile ' if self.volatile else '')

    is_int = is_ptr = is_array = is_func = is_void = False

    @property
    def is_scalar(self):
        return self.is_int or self.is_ptr

    @property
    def is_arith(self):
        return self.is_int


class IntT(CType):
    is_int = True

    def __init__(self, size, signed, name):
        self.size, self.signed, self.name = size, signed, name

    def _copy(self):
        return IntT(self.size, self.signed, self.name)

    def same(self, other):
        return other.is_int and other.size == self.size and other.signed == self.signed

    def __str__(self):
        return self._quals() + self.name

    @property
    def bits(self):
        return 8 * self.size

    def wrap(self, v):
        """Değeri bu tipe sarar (C dönüşüm kuralı)."""
        m = 1 << self.bits
        v %= m
        if self.signed and v >= m >> 1:
            v -= m
        return v


class VoidT(CType):
    is_void = True
    size = 0

    def _copy(self):
        return VoidT()

    def same(self, other):
        return other.is_void

    def __str__(self):
        return self._quals() + 'void'


class PtrT(CType):
    is_ptr = True
    size = 2
    signed = False

    def __init__(self, base):
        self.base = base

    def _copy(self):
        return PtrT(self.base)

    def same(self, other):
        return other.is_ptr and same_type(self.base, other.base, quals=True)

    def __str__(self):
        q = (' const' if self.const else '') + (' volatile' if self.volatile else '')
        return f'{self.base}*{q}'

    def wrap(self, v):
        return v & 0xFFFF


class ArrT(CType):
    is_array = True

    def __init__(self, base, n):
        self.base, self.n = base, n

    def _copy(self):
        return ArrT(self.base, self.n)

    @property
    def size(self):
        return 0 if self.n is None else self.n * self.base.size

    def same(self, other):
        return other.is_array and other.n == self.n and same_type(self.base, other.base, quals=True)

    def __str__(self):
        return f'{self.base}[{"" if self.n is None else self.n}]'

    def elem_quals(self):
        """Dizinin en içteki eleman tipi const mu?"""
        t = self
        while t.is_array:
            t = t.base
        return t.const, t.volatile


class FuncT(CType):
    is_func = True
    size = 0

    def __init__(self, ret, params, variadic=False):
        self.ret, self.params, self.variadic = ret, params, variadic

    def _copy(self):
        return FuncT(self.ret, self.params, self.variadic)

    def same(self, other):
        return (other.is_func and same_type(self.ret, other.ret)
                and len(self.params) == len(other.params)
                and all(same_type(a, b) for a, b in zip(self.params, other.params)))

    def __str__(self):
        return f'{self.ret} (' + ', '.join(str(p) for p in self.params) + ')'


def same_type(a, b, quals=False):
    if quals and (a.const != b.const or a.volatile != b.volatile):
        return False
    return a.same(b)


CHAR = IntT(1, False, 'char')
SCHAR = IntT(1, True, 'signed char')
INT = IntT(2, True, 'int')
UINT = IntT(2, False, 'unsigned int')
VOID = VoidT()


def promote(t):
    """Tamsayı terfisi: 8 bitlik tipler int olur."""
    if t.is_int and t.size < 2:
        return INT
    return t.unqualified()


def arith_conv(a, b):
    """Olağan aritmetik dönüşümler (iki işlenen de tamsayı)."""
    a, b = promote(a), promote(b)
    if not a.signed or not b.signed:
        return UINT
    return INT


def decay(t):
    """Dizi -> eleman işaretçisi (ifade içinde)."""
    if t.is_array:
        return PtrT(t.base)
    return t
