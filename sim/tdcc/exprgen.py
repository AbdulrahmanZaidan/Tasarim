"""İfadeler için kod üretimi (CodeGen'e karışan sınıf).

    gen(e, n)          e'yi değerlendirir, en düşük n byte'ını işlenen olarak döndürür
                       (n = 0: yalnız yan etkiler). Sonuç: sabit, değişkenin kendisi,
                       bir geçici ya da 8-bit ise A.
    gen_into(e, dest)  sonucu doğrudan dest'e (bellek byte'ları) yazar; toplama gibi
                       işlemlerde ara geçici kullanılmaz.
    cond(e, L, j)      e'nin doğruluğu j ise L'ye dallanır (kısa devre dahil).
"""

from . import nodes as N
from .emit import ACC, has_acc, imm, imm_sym, is_imm_val, mem
from .typesys import INT

RELOPS = ('<', '>', '<=', '>=', '==', '!=')
MIRROR = {'<': '>', '>': '<', '<=': '>=', '>=': '<=', '==': '==', '!=': '!='}
NEGATE = {'<': '>=', '>=': '<', '>': '<=', '<=': '>', '==': '!=', '!=': '=='}
BRANCH_S = {'<': 'BLT', '>=': 'BGE', '>': 'BGT', '<=': 'BLE', '==': 'BEQ', '!=': 'BNE'}
BRANCH_U = {'<': 'BLO', '>=': 'BHS', '>': 'BHI', '<=': 'BLS', '==': 'BEQ', '!=': 'BNE'}


class LV:
    """Sol değer. direct: adresi derleme anında belli (base+off).
    indirect: adres çalışma anında; `addr` (2 byte işlenen) ya da `parts`
    (taban, indeks, '+'/'-'), X'e TAXL/TAXH ile doğrudan yüklenir."""

    def __init__(self, kind, ctype, base=None, off=0, addr=None, parts=None):
        self.kind, self.type = kind, ctype
        self.base, self.off, self.addr, self.parts = base, off, addr, parts

    @property
    def volatile(self):
        return self.type.volatile

    def bytes(self, n=None):
        return mem(self.base, self.off, self.type.size if n is None else n)


def popcount(v):
    return bin(v).count('1')


def contains_call(e):
    if isinstance(e, N.Call):
        return True
    for f in e._fields:
        v = getattr(e, f, None)
        if isinstance(v, N.Expr) and contains_call(v):
            return True
        if isinstance(v, list):
            if any(isinstance(x, N.Expr) and contains_call(x) for x in v):
                return True
    return False


class ExprGen:
    # --- küçük yardımcılar ----------------------------------------------------
    def load(self, b):
        if b.kind != 'acc':
            self.e.ins('LDA', b.text)

    def alu(self, m, b):
        assert b.kind != 'acc', m
        self.e.ins(m, b.text)

    def spill(self, op):
        if op and op[0].kind == 'acc':
            t = self.temp(1)
            self.e.ins('STA', t[0].text)
            return [t[0]] + op[1:]
        return op

    def place(self, op, dest):
        if dest is None:
            return op
        self.store_bytes(op, dest)
        return dest

    def to_temp(self, op):
        t = self.temp(len(op))
        self.store_bytes(op, t)
        return t

    def conflicts(self, dest, *ops):
        """dest[i] yazıldıktan sonra bir işlenenin j > i byte'ı aynı hücreyi okur mu?"""
        for i, d in enumerate(dest):
            k = d.key()
            for op in ops:
                for j in range(i + 1, len(op)):
                    if op[j].key() == k:
                        return True
        return False

    def store_bytes(self, op, dest):
        assert len(op) >= len(dest), (op, dest)
        if self.conflicts(dest, op):
            op = self.to_temp(op[:len(dest)])
        for i, d in enumerate(dest):
            b = op[i]
            if b.kind == 'mem' and b.key() == d.key():
                continue
            self.load(b)
            self.e.ins('STA', d.text)

    def gen_pair(self, a, na, b, nb):
        """İki ifadeyi sırayla üretir; ilki A'da kalmışsa ve ikincisi kod
        üretiyorsa ilki geriye dönük olarak bir geçiciye saklanır."""
        A = self.gen(a, na)
        mark = self.e.mark()
        B = self.gen(b, nb)
        # B kod ürettiyse A bozulmuş olabilir; B de A'daysa (LDA peephole ile
        # atlanmış olabilir) iki işlenen birden A'da kalamaz.
        if has_acc(A) and (self.e.since(mark) or has_acc(B)):
            t = self.temp(1)
            self.e.insert(mark, 'STA', t[0].text)
            A = [t[0]] + A[1:]
        return A, B

    def size(self, e):
        return e.type.size

    # --- dağıtıcılar ------------------------------------------------------------
    def gen(self, e, n):
        m = getattr(self, 'g_' + type(e).__name__, None)
        if m is None:
            self.error(f'bu ifade için kod üretilemiyor: {type(e).__name__}', e)
        return m(e, n)

    def gen_into(self, e, dest):
        m = getattr(self, 'i_' + type(e).__name__, None)
        if m is not None and m(e, dest):
            return
        op = self.gen(e, len(dest))
        self.store_bytes(op, dest)

    # --- yapraklar ----------------------------------------------------------------
    def g_Const(self, e, n):
        return imm(e.value, n) if n else None

    def g_Ident(self, e, n):
        return self.read_lv(self.lvalue(e), n)

    def g_Deref(self, e, n):
        return self.read_lv(self.lvalue(e), n)

    def g_AddrOf(self, e, n):
        lv = self.lvalue(e.operand)
        if not n:
            return None
        return self.lv_address(lv)[:n]

    def bind(self, op):
        """Bileşik atamada hedefin değerini LvRead'e bağlar."""
        self.lv_stack.append([op, self.e.mark()])

    def g_LvRead(self, e, n):
        entry = self.lv_stack[-1]
        op, mark = entry
        if has_acc(op) and self.e.since(mark):
            # A'daki değer bu arada bozulmuş olabilir: bağlandığı yerde sakla
            t = self.temp(1)
            self.e.insert(mark, 'STA', t[0].text)
            op = entry[0] = [t[0]] + op[1:]
        return op[:n] if n else None

    # --- dönüşümler -------------------------------------------------------------
    def g_Cast(self, e, n):
        src = e.operand.type
        if e.type.is_void or n == 0:
            self.gen(e.operand, 0)
            return None
        ss = src.size
        if n <= ss:
            return self.gen(e.operand, n)
        op = self.gen(e.operand, 1)                 # 1 -> 2 byte genişletme
        if not src.signed:
            return op + imm(0, 1)
        return self.sign_extend(op)

    def i_Cast(self, e, dest):
        src = e.operand.type
        if e.type.is_void:
            return False
        if len(dest) <= src.size:
            self.gen_into(e.operand, dest)
            return True
        self.gen_into(e.operand, dest[:1])
        if src.signed:
            self.e.ins('LDA', dest[0].text)
            self.e.ins('SEX')
        else:
            self.e.ins('LDA', '#$00')
        self.e.ins('STA', dest[1].text)
        return True

    def sign_extend(self, op):
        b = op[0]
        if b.kind == 'imm' and b.val is not None:
            return [b] + imm(0xFF if b.val & 0x80 else 0, 1)
        if b.kind == 'acc':
            b = self.temp(1)[0]
            self.e.ins('STA', b.text)
        else:
            self.load(b)
        hi = self.temp(1)[0]
        self.e.ins('SEX')
        self.e.ins('STA', hi.text)
        return [b, hi]

    # --- tekli işlemler -----------------------------------------------------------
    def g_Unary(self, e, n):
        if e.op == '!':
            return self.bool_value(e, n)
        if n == 0:
            return self.gen(e.operand, 0)
        return self.unary(e, n, None)

    def i_Unary(self, e, dest):
        if e.op == '!':
            return False
        self.unary(e, len(dest), dest)
        return True

    def unary(self, e, n, dest):
        x = self.gen(e.operand, n)
        if e.op == '-':
            if n == 1:
                self.load(x[0])
                self.e.ins('NEG')
                return self.place([ACC], dest)
            return self.bytewise('-', imm(0, n), x, n, dest)
        # '~'
        if n == 1:
            self.load(x[0])
            self.e.ins('NOT')
            return self.place([ACC], dest)
        out = dest if dest is not None and not self.conflicts(dest, x) else self.temp(n)
        for i in range(n):
            self.load(x[i])
            self.e.ins('NOT')
            self.e.ins('STA', out[i].text)
        return self.place(out, dest) if out is not dest else dest

    # --- ikili işlemler -------------------------------------------------------------
    def g_Binary(self, e, n):
        if e.op in RELOPS:
            return self.bool_value(e, n)
        if e.type.is_ptr and n:
            ca = self.const_addr(e)
            if ca is not None:
                return self.lv_imm(ca)[:n]
        if n == 0:
            self.gen(e.left, 0)
            self.gen(e.right, 0)
            return None
        return self.arith(e, n, None)

    def i_Binary(self, e, dest):
        if e.op in RELOPS:
            return False
        self.arith(e, len(dest), dest)
        return True

    def arith(self, e, n, dest):
        op = e.op
        if op in ('+', '-', '&', '|', '^'):
            L, R = self.gen_pair(e.left, n, e.right, n)
            return self.bytewise(op, L, R, n, dest)
        if op == '*':
            return self.mul(e, n, dest)
        if op in ('/', '%'):
            return self.divmod(e, n, dest)
        return self.shift(e, n, dest)

    def bytewise(self, op, L, R, n, dest):
        """Byte byte toplama/çıkarma/mantık işlemi. n == 1 ve dest yoksa sonuç A'da."""
        if has_acc(R):
            if op != '-':
                L, R = R, L
            else:
                R = self.spill(R)
        if dest is None and n > 1:
            dest = self.temp(n)
        out = dest
        if dest is not None and self.conflicts(dest, L, R):
            out = self.temp(n)
        carry = False
        for i in range(n):
            l, r = L[i], R[i]
            last = i == n - 1
            if op in ('+', '-'):
                if not carry and is_imm_val(r, 0):
                    self.load(l)
                elif not carry and op == '+' and is_imm_val(l, 0):
                    self.load(r)
                elif not carry and last and is_imm_val(r, 1):
                    self.load(l)
                    self.e.ins('INC' if op == '+' else 'DEC')
                else:
                    self.load(l)
                    if op == '+':
                        self.alu('ADC' if carry else 'ADD', r)
                    else:
                        self.alu('SBC' if carry else 'SUB', r)
                    carry = True
            elif op == '&':
                if is_imm_val(r, 0) or is_imm_val(l, 0):
                    self.e.ins('LDA', '#$00')
                elif is_imm_val(r, 0xFF):
                    self.load(l)
                elif is_imm_val(l, 0xFF):
                    self.load(r)
                else:
                    self.load(l)
                    self.alu('AND', r)
            elif op == '|':
                if is_imm_val(r, 0xFF) or is_imm_val(l, 0xFF):
                    self.e.ins('LDA', '#$FF')
                elif is_imm_val(r, 0):
                    self.load(l)
                elif is_imm_val(l, 0):
                    self.load(r)
                else:
                    self.load(l)
                    self.alu('OR', r)
            else:   # '^'
                if is_imm_val(r, 0):
                    self.load(l)
                elif is_imm_val(l, 0):
                    self.load(r)
                elif is_imm_val(r, 0xFF):
                    self.load(l)
                    self.e.ins('NOT')
                elif is_imm_val(l, 0xFF):
                    self.load(r)
                    self.e.ins('NOT')
                else:
                    self.load(l)
                    self.alu('XOR', r)
            if out is not None:
                self.e.ins('STA', out[i].text)
        if out is None:
            return [ACC]
        if out is not dest:
            self.store_bytes(out, dest)
        return dest

    # --- çarpma ---------------------------------------------------------------
    def const_side(self, e):
        """(sabit, diğer ifade) ya da None (çarpma değişmeli)."""
        if isinstance(e.right, N.Const):
            return e.right.value, e.left
        if isinstance(e.left, N.Const):
            return e.left.value, e.right
        return None

    def mul(self, e, n, dest):
        cs = self.const_side(e)
        if cs is not None:
            mask = 0xFF if n == 1 else 0xFFFF
            k, x = cs[0] & mask, cs[1]
            if k == 0:
                self.gen(x, 0)
                return self.place(imm(0, n), dest)
            if k == 1:
                if dest is not None:
                    self.gen_into(x, dest)
                    return dest
                return self.gen(x, n)
            neg = False
            if popcount((-k) & mask) < popcount(k):
                k, neg = (-k) & mask, True
            if popcount(k) <= 3:
                if neg:
                    prod = self.shift_add(x, k, n, None)
                    return self.bytewise('-', imm(0, n), prod, n, dest)
                return self.shift_add(x, k, n, dest)
        L, R = self.gen_pair(e.left, 2, e.right, 2)
        return self.runtime2('__mul16', L, '__mul_a', R, '__mul_b', '__rv', n, dest)

    def runtime2(self, routine, L, la, R, ra, result, n, dest, rtc=False):
        """İki 16-bit argümanlı runtime çağrısı; sonuç `result` yuvasında."""
        first, second = ((R, ra), (L, la)) if has_acc(R) else ((L, la), (R, ra))
        self.store_bytes(first[0], mem(first[1], 0, len(first[0])))
        self.store_bytes(second[0], mem(second[1], 0, len(second[0])))
        self.e.ins('CALL', routine)
        self.needs_runtime = True
        if rtc:
            self.needs_rtc = True
        res = mem(result, 0, n)
        return self.place(res, dest) if dest is not None else self.to_temp(res)

    def shift_add(self, x, k, n, dest):
        bits = [b for b in range(16) if k >> b & 1]
        X = self.gen(x, n)
        if n == 1:
            self.load(X[0])
            for _ in range(bits[0]):
                self.e.ins('SHL')
            if len(bits) > 1:
                s = self.temp(1)[0]
                c = self.temp(1)[0]
                self.e.ins('STA', s.text)
                for i in range(1, len(bits)):
                    if i >= 2:
                        self.e.ins('LDA', c.text)
                    for _ in range(bits[i] - bits[i - 1]):
                        self.e.ins('SHL')
                    if i < len(bits) - 1:
                        self.e.ins('STA', c.text)
                    self.alu('ADD', s)
                    if i < len(bits) - 1:
                        self.e.ins('STA', s.text)
            return self.place([ACC], dest)
        if len(bits) == 1:
            return self.shl16(X, bits[0], dest)
        cur = self.shl16(X, bits[0], None)
        total = self.to_temp(cur)
        for i in range(1, len(bits)):
            cur = self.shl16(cur, bits[i] - bits[i - 1], cur)
            last = i == len(bits) - 1
            total = self.bytewise('+', total, cur, 2, dest if last else total)
        return total

    # --- bölme --------------------------------------------------------------------
    def nonneg(self, e):
        """Değeri kesinlikle >= 0 mı (işaretli bölmeyi işaretsize indirmek için)?"""
        if isinstance(e, N.Const):
            return e.value >= 0
        if isinstance(e, N.Cast) and e.operand.type.is_int:
            src = e.operand.type
            return src.size < e.type.size and not src.signed
        if isinstance(e, N.Binary) and e.op == '&':
            return self.nonneg(e.left) or self.nonneg(e.right)
        return False

    def divmod(self, e, n, dest):
        op = e.op
        signed = e.type.signed and not (self.nonneg(e.left) and self.nonneg(e.right))
        if isinstance(e.right, N.Const):
            k = e.right.value
            if signed:
                if k in (1, -1):
                    if op == '%':
                        self.gen(e.left, 0)
                        return self.place(imm(0, n), dest)
                    if k == 1:
                        return self.place(self.gen(e.left, n), dest)
                    return self.bytewise('-', imm(0, n), self.gen(e.left, n), n, dest)
                a = abs(k)
                if a & (a - 1) == 0 and a < 0x8000:
                    j = a.bit_length() - 1
                    X = self.spill(self.gen(e.left, 2))
                    if op == '/':
                        if e.exact:
                            res = self.shr16(X, j, True, None)
                        else:
                            res = self.sdiv_pow2(X, j)
                        if k < 0:
                            return self.bytewise('-', imm(0, n), res, n, dest)
                        return self.place(res[:n], dest)
                    return self.place(self.smod_pow2(X, a)[:n], dest)
            else:
                k &= 0xFFFF
                if k and k & (k - 1) == 0:
                    j = k.bit_length() - 1
                    if op == '%':
                        L = self.gen(e.left, n)
                        return self.bytewise('&', L, imm(k - 1, n), n, dest)
                    if j == 0:
                        return self.place(self.gen(e.left, n), dest)
                    return self.shr_expr(e.left, j, False, n, dest)
        L, R = self.gen_pair(e.left, 2, e.right, 2)
        result = '__rv' if op == '/' else '__div_r'
        if signed:
            return self.runtime2('__sdiv16', L, '__div_n', R, '__div_d', result, n, dest, rtc=True)
        return self.runtime2('__divmod16', L, '__div_n', R, '__div_d', result, n, dest)

    def sdiv_pow2(self, X, j):
        """İşaretli x / 2^j (sıfıra doğru): negatifse önce 2^j - 1 eklenir."""
        t = self.to_temp(X)
        skip = self.new_label()
        self.e.ins('LDA', t[1].text)
        self.e.ins('TST')
        self.e.ins('BPL', skip)
        self.bytewise('+', t, imm((1 << j) - 1), 2, t)
        self.e.label(skip)
        return self.shr16(t, j, True, t)

    def smod_pow2(self, X, a):
        """İşaretli x % a (a = 2^j): kalan bölünenin işaretini alır."""
        t = self.bytewise('&', X, imm(a - 1), 2, self.temp(2))
        done = self.new_label()
        self.load(X[1])
        self.e.ins('TST')
        self.e.ins('BPL', done)
        self.e.ins('LDA', t[0].text)
        self.e.ins('OR', t[1].text)
        self.e.ins('BEQ', done)
        self.bytewise('|', t, imm(~(a - 1)), 2, t)
        self.e.label(done)
        return t

    # --- kaydırma -------------------------------------------------------------------
    def shift(self, e, n, dest):
        left_t = e.type
        if isinstance(e.right, N.Const):
            k = e.right.value
            if k == 0:
                if dest is not None:
                    self.gen_into(e.left, dest)
                    return dest
                return self.gen(e.left, n)
            if e.op == '<<':
                if n == 1:
                    X = self.gen(e.left, 1)
                    if k >= 8:
                        self.gen(e.left, 0)
                        return self.place(imm(0, 1), dest)
                    self.load(X[0])
                    for _ in range(k):
                        self.e.ins('SHL')
                    return self.place([ACC], dest)
                return self.shl16(self.gen(e.left, 2), k, dest)
            return self.shr_expr(e.left, k, left_t.signed, n, dest)
        L, R = self.gen_pair(e.left, 2, e.right, 1)
        if e.op == '<<':
            routine = '__shl16'
        else:
            routine = '__asr16' if left_t.signed and not self.nonneg(e.left) else '__shr16'
        return self.runtime2(routine, L, '__rv', R, '__cnt', '__rv', n, dest, rtc=True)

    def shr_expr(self, x, k, signed, n, dest):
        """x >> k (sabit k). x 8 bitten genişletilmişse 8 bitte yapılır."""
        if isinstance(x, N.Cast) and x.operand.type.is_int and x.operand.type.size == 1 \
                and x.type.size == 2 and (signed or not x.operand.type.signed):
            # 8 bitte: sıfır genişletme, ya da işaret genişletme + aritmetik kaydırma
            src = x.operand.type
            X = self.gen(x.operand, 1)
            self.load(X[0])
            for _ in range(min(k, 8)):
                self.e.ins('ASR' if src.signed else 'SHR')
            if n == 1:
                return self.place([ACC], dest)
            if src.signed:
                return self.place(self.sign_extend([ACC]), dest)
            return self.place([ACC] + imm(0, 1), dest)
        if dest is not None and len(dest) == 2:
            return self.shr16(self.gen(x, 2), k, signed, dest)
        res = self.shr16(self.gen(x, 2), k, signed, None)
        return self.place(res[:n], dest)

    def _out16(self, X, dest, reads_after):
        """Yazılacak 2 byte'lık hedef: dest uygun değilse yeni geçici."""
        if dest is None:
            return self.temp(2)
        for i, d in enumerate(dest):
            for b in reads_after.get(i, ()):
                if b.key() == d.key():
                    return self.temp(2)
        return dest

    def shl16(self, X, k, dest):
        """16-bit x << k (sabit). X: kararlı 2 byte'lık işlenen."""
        X = self.spill(X)
        if k >= 16:
            return self.place(imm(0, 2), dest)
        if 1 <= k <= 7 and is_imm_val(X[1], 0):
            # sıfır genişletilmiş 8-bit değer: hi = x >> (8-k), lo = x << k
            out = self._out16(X, dest, {1: [X[0]]})
            self.load(X[0])
            for _ in range(8 - k):
                self.e.ins('SHR')
            self.e.ins('STA', out[1].text)
            self.load(X[0])
            for _ in range(k):
                self.e.ins('SHL')
            self.e.ins('STA', out[0].text)
            if dest is not None and out is not dest:
                self.store_bytes(out, dest)
                return dest
            return out
        if k >= 8:
            out = self._out16(X, dest, {})
            self.load(X[0])
            for _ in range(k - 8):
                self.e.ins('SHL')
            self.e.ins('STA', out[1].text)
            self.e.ins('LDA', '#$00')
            self.e.ins('STA', out[0].text)
        elif k <= 2:
            out = dest if dest is not None else self.temp(2)
            self.store_bytes(X, out)
            for _ in range(k):
                self.e.ins('LDA', out[0].text)
                self.e.ins('SHL')
                self.e.ins('STA', out[0].text)
                self.e.ins('LDA', out[1].text)
                self.e.ins('ROL')
                self.e.ins('STA', out[1].text)
        else:
            out = self._out16(X, dest, {1: [X[0]]})
            t = self.temp(1)[0]
            self.load(X[0])
            for _ in range(8 - k):
                self.e.ins('SHR')
            self.e.ins('STA', t.text)
            self.load(X[1])
            for _ in range(k):
                self.e.ins('SHL')
            self.e.ins('OR', t.text)
            self.e.ins('STA', out[1].text)
            self.load(X[0])
            for _ in range(k):
                self.e.ins('SHL')
            self.e.ins('STA', out[0].text)
        if dest is not None and out is not dest:
            self.store_bytes(out, dest)
            return dest
        return out

    def shr16(self, X, k, signed, dest):
        """16-bit x >> k (sabit); signed ise aritmetik."""
        X = self.spill(X)
        sh = 'ASR' if signed else 'SHR'
        k = min(k, 16)
        if k >= 8:
            out = self._out16(X, dest, {})
            self.load(X[1])
            for _ in range(min(k, 15) - 8 if signed else k - 8):
                self.e.ins(sh)
            if k == 16 and not signed:
                self.e.ins('LDA', '#$00')
            self.e.ins('STA', out[0].text)
            if signed:
                self.e.ins('SEX')
            else:
                self.e.ins('LDA', '#$00')
            self.e.ins('STA', out[1].text)
        elif k <= 2:
            out = dest if dest is not None else self.temp(2)
            self.store_bytes(X, out)
            for _ in range(k):
                self.e.ins('LDA', out[1].text)
                self.e.ins(sh)
                self.e.ins('STA', out[1].text)
                self.e.ins('LDA', out[0].text)
                self.e.ins('ROR')
                self.e.ins('STA', out[0].text)
        else:
            out = self._out16(X, dest, {0: [X[1]]})
            t = self.temp(1)[0]
            self.load(X[1])
            for _ in range(8 - k):
                self.e.ins('SHL')
            self.e.ins('STA', t.text)
            self.load(X[0])
            for _ in range(k):
                self.e.ins('SHR')
            self.e.ins('OR', t.text)
            self.e.ins('STA', out[0].text)
            self.load(X[1])
            for _ in range(k):
                self.e.ins(sh)
            self.e.ins('STA', out[1].text)
        if dest is not None and out is not dest:
            self.store_bytes(out, dest)
            return dest
        return out

    # --- karşılaştırma ve koşullar ------------------------------------------------
    def bool_value(self, e, n):
        """Koşul ifadesini 0/1 değerine çevirir."""
        if n == 0:
            done = self.new_label()
            self.cond(e, done, True)
            self.e.label(done)
            return None
        lf, le = self.new_label(), self.new_label()
        self.cond(e, lf, False)
        self.e.ins('LDA', '#$01')
        self.e.ins('JMP', le)
        self.e.label(lf)
        self.e.ins('LDA', '#$00')
        self.e.label(le)
        return [ACC] + imm(0, n - 1)

    def flush_deferred(self):
        if self.defer:
            for (m, k), text in self.defer:
                for _ in range(k):
                    self.e.ins(m, text)
            self.defer.clear()

    def cond(self, e, label, jump_if):
        saved, self.defer = self.defer, None
        try:
            self._cond(e, label, jump_if)
        finally:
            self.defer = saved

    def _cond(self, e, label, jump_if):
        if isinstance(e, N.Const):
            if bool(e.value) == jump_if:
                self.e.ins('JMP', label)
            return
        if isinstance(e, N.Unary) and e.op == '!':
            return self.cond(e.operand, label, not jump_if)
        if isinstance(e, N.Logical):
            is_and = e.op == '&&'
            if is_and != jump_if:
                # && ile "yanlışsa atla" ya da || ile "doğruysa atla": iki taraf da aynı hedefe
                self.cond(e.left, label, jump_if)
                self.cond(e.right, label, jump_if)
            else:
                skip = self.new_label()
                self.cond(e.left, skip, not jump_if)
                self.cond(e.right, label, jump_if)
                self.e.label(skip)
            return
        if isinstance(e, N.Binary) and e.op in RELOPS:
            return self.compare(e, label, jump_if)
        if isinstance(e, N.Comma):
            self.gen(e.left, 0)
            return self.cond(e.right, label, jump_if)
        if isinstance(e, N.Cast) and not e.type.is_void and e.type.size >= e.operand.type.size:
            return self.cond(e.operand, label, jump_if)
        op = self.gen(e, self.size(e))
        self.test_nonzero(op, label, jump_if)

    def test_nonzero(self, op, label, jump_if):
        br = 'BNE' if jump_if else 'BEQ'
        if len(op) == 2 and is_imm_val(op[1], 0):
            op = op[:1]
        elif len(op) == 2 and is_imm_val(op[0], 0):
            op = op[1:]
        if all(b.kind == 'imm' and b.val is not None for b in op):
            if any(b.val for b in op) == jump_if:
                self.e.ins('JMP', label)
            return
        self.load(op[0])
        if len(op) == 1:
            self.e.ins('TST')
        else:
            self.alu('OR', op[1])
        self.e.ins(br, label)

    def narrow(self, e):
        """8 bitten genişletilmiş değer: ('z'|'s', iç ifade) ya da sabit için ('c', değer)."""
        if isinstance(e, N.Cast) and e.operand.type.is_int and e.operand.type.size == 1 \
                and e.type.size == 2:
            return ('s' if e.operand.type.signed else 'z'), e.operand
        if isinstance(e, N.Const):
            return 'c', e.value & 0xFFFF
        return None, None

    def compare(self, e, label, jump_if):
        op = e.op
        t = e.left.type
        signed = t.is_int and t.signed
        kl, xl = self.narrow(e.left)
        kr, xr = self.narrow(e.right)
        width = 2
        kind = None
        if kl in ('z', 's') and kr == kl:
            kind = kl
        elif kl in ('z', 's') and kr == 'c':
            kind = kl if self.fits(xr, kl) else None
        elif kr in ('z', 's') and kl == 'c':
            kind = kr if self.fits(xl, kr) else None
        if kind is not None:
            width = 1
            signed = signed and kind == 's'
            a = xl if kl != 'c' else N.Const(xl).at(e)
            b = xr if kr != 'c' else N.Const(xr).at(e)
            if kl == 'c':
                a.type = t
            if kr == 'c':
                b.type = t
            L, R = self.gen_pair(a, 1, b, 1)
        else:
            L, R = self.gen_pair(e.left, 2, e.right, 2)
        if has_acc(R):
            L, R = R, L
            op = MIRROR[op]
        if not jump_if:
            op = NEGATE[op]
        # sıfırla karşılaştırma
        if all(is_imm_val(b, 0) for b in R):
            if op in ('==', '!='):
                return self.test_nonzero(L, label, op == '!=')
            if signed and op in ('<', '>='):
                self.load(L[-1])
                self.e.ins('TST')
                self.e.ins('BMI' if op == '<' else 'BPL', label)
                return
            if not signed:
                if op == '>':
                    return self.test_nonzero(L, label, True)
                if op == '<=':
                    return self.test_nonzero(L, label, False)
                if op == '>=':
                    self.e.ins('JMP', label)
                    return
                if op == '<':
                    return
        self.load(L[0])
        self.alu('CMP', R[0])
        if width == 2:
            self.load(L[1])
            self.alu('CPC', R[1])
        self.e.ins((BRANCH_S if signed else BRANCH_U)[op], label)

    def fits(self, v, kind):
        """16-bit sabit deseni `kind` genişletmesiyle 8 bitten elde edilebilir mi?"""
        if kind == 'z':
            return v <= 0xFF
        return v <= 0x7F or v >= 0xFF80

    def g_Logical(self, e, n):
        saved, self.defer = self.defer, None
        try:
            return self._g_logical(e, n)
        finally:
            self.defer = saved

    def _g_logical(self, e, n):
        if n == 0:
            done = self.new_label()
            self.cond(e.left, done, e.op == '||')
            self.gen(e.right, 0)
            self.e.label(done)
            return None
        return self.bool_value(e, n)

    # --- ?: ve virgül -------------------------------------------------------------
    def g_Cond(self, e, n):
        saved, self.defer = self.defer, None
        try:
            return self._g_cond(e, n)
        finally:
            self.defer = saved

    def _g_cond(self, e, n):
        lf, le = self.new_label(), self.new_label()
        if n == 0:
            self.cond(e.cond, lf, False)
            self.gen(e.then, 0)
            self.e.ins('JMP', le)
            self.e.label(lf)
            self.gen(e.other, 0)
            self.e.label(le)
            return None
        if n == 1:
            self.cond(e.cond, lf, False)
            self.load(self.gen(e.then, 1)[0])
            self.e.ins('JMP', le)
            self.e.label(lf)
            self.load(self.gen(e.other, 1)[0])
            self.e.label(le)
            return [ACC]
        t = self.temp(n)
        self._i_cond(e, t)
        return t

    def i_Cond(self, e, dest):
        saved, self.defer = self.defer, None
        try:
            return self._i_cond(e, dest)
        finally:
            self.defer = saved

    def _i_cond(self, e, dest):
        lf, le = self.new_label(), self.new_label()
        self.cond(e.cond, lf, False)
        self.gen_into(e.then, dest)
        self.e.ins('JMP', le)
        self.e.label(lf)
        self.gen_into(e.other, dest)
        self.e.label(le)
        return True

    def g_Comma(self, e, n):
        self.gen(e.left, 0)
        self.flush_deferred()           # virgül bir sıra noktasıdır
        return self.gen(e.right, n)

    def i_Comma(self, e, dest):
        self.gen(e.left, 0)
        self.flush_deferred()
        self.gen_into(e.right, dest)
        return True

    # --- atamalar -------------------------------------------------------------------
    def g_Assign(self, e, n):
        lv = self.lvalue(e.target)
        size = e.target.type.size
        if lv.kind == 'direct' and not lv.volatile:
            dest = lv.bytes()
            self.gen_into(e.value, dest)
            return dest[:n] if n else None
        val = self.gen(e.value, size)
        if n:
            val = self.spill(val)
        self.store_lv(lv, val)
        return val[:n] if n else None

    def i_Assign(self, e, dest):
        self.store_bytes(self.g_Assign(e, len(dest)), dest)
        return True

    def incw_step(self, e):
        """x += k / x -= k (k küçük sabit, x 16 bit): INCW/DECW sayısı ya da None."""
        if e.op not in ('+', '-') or not isinstance(e.value, N.Const):
            return None
        t = e.target.type
        if t.size != 2:
            return None
        k = e.value.value * (t.base.size if t.is_ptr else 1)
        if e.op == '-':
            k = -k
        if 1 <= k <= 3:
            return 'INCW', k
        if -3 <= k <= -1:
            return 'DECW', -k
        return None

    def g_CompoundAssign(self, e, n):
        lv = self.lvalue(e.target)
        size = e.target.type.size
        if lv.kind == 'direct' and not lv.volatile:
            dest = lv.bytes()
            step = self.incw_step(e)
            if step is not None:
                for _ in range(step[1]):
                    self.e.ins(step[0], dest[0].text)
                return dest[:n] if n else None
            self.bind(dest)
            self.gen_into(e.expr, dest)
            self.lv_stack.pop()
            return dest[:n] if n else None
        cur = self.read_lv(lv, size)
        self.bind(cur)
        val = self.gen(e.expr, size)
        self.lv_stack.pop()
        if n:
            val = self.spill(val)
        self.store_lv(lv, val)
        return val[:n] if n else None

    def i_CompoundAssign(self, e, dest):
        self.store_bytes(self.g_CompoundAssign(e, len(dest)), dest)
        return True

    def as_compound(self, e):
        one = N.Const(1).at(e)
        one.type = INT
        c = N.CompoundAssign(e.op[0], e.target, one, e.expr).at(e)
        c.type = e.type
        return c

    def g_IncDec(self, e, n):
        """Son ek ++/-- (ön ek sema'da CompoundAssign oldu)."""
        if n == 0:
            return self.g_CompoundAssign(self.as_compound(e), 0)
        lv = self.lvalue(e.target)
        size = e.target.type.size
        if lv.kind == 'direct' and not lv.volatile:
            step = self.incw_step(self.as_compound(e))
            if step is not None:
                old = self.to_temp(lv.bytes())
                for _ in range(step[1]):
                    self.e.ins(step[0], lv.bytes()[0].text)
                return old[:n]
        old = self.to_temp(self.read_lv(lv, size))
        self.bind(old)
        val = self.gen(e.expr, size)
        self.lv_stack.pop()
        self.store_lv(lv, val)
        return old[:n]

    # --- çağrı ------------------------------------------------------------------------
    def g_Call(self, e, n, dest=None):
        callee = self.unit.func_by_name[e.sym.name]
        params = callee.params
        vals = [None] * len(e.args)
        for i, a in enumerate(e.args):            # çağrı içeren argümanlar önce geçiciye
            if contains_call(a):
                vals[i] = self.temp(params[i].type.size)
                self.gen_into(a, vals[i])
        for i, a in enumerate(e.args):
            if vals[i] is None:
                self.gen_into(a, mem(params[i].asm, 0, params[i].type.size))
        for i, v in enumerate(vals):
            if v is not None:
                self.store_bytes(v, mem(params[i].asm, 0, params[i].type.size))
        self.flush_deferred()           # çağrıdan önce sıra noktası
        self.e.ins('CALL', callee.sym.asm)
        ret = e.type
        if ret.is_void or n == 0:
            return None
        if ret.size == 1:
            return self.place([ACC], dest)
        res = mem('__rv', 0, n)
        return self.place(res, dest) if dest is not None else self.to_temp(res)

    def i_Call(self, e, dest):
        self.g_Call(e, len(dest), dest)
        return True

    # --- sol değerler ---------------------------------------------------------------
    def const_addr(self, e):
        """Adresi derleme anında belli işaretçi ifadesi: (taban, ofset) ya da None."""
        if isinstance(e, N.Const):
            return e.value & 0xFFFF, 0
        if isinstance(e, N.AddrOf):
            return self.static_lv(e.operand)
        if isinstance(e, N.Cast) and e.type.size == 2 and e.operand.type.size == 2:
            return self.const_addr(e.operand)
        if isinstance(e, N.Binary) and e.op in ('+', '-') and e.type.is_ptr                 and isinstance(e.right, N.Const):
            base = self.const_addr(e.left)
            if base is not None:
                k = e.right.value if e.op == '+' else -e.right.value
                return base[0], base[1] + k
        return None

    def static_lv(self, e):
        """Adresi derleme anında belli sol değer: (taban, ofset) ya da None. Kod üretmez."""
        if isinstance(e, N.Ident):
            return e.sym.asm, 0
        if isinstance(e, N.Str):
            return e.label, 0
        if isinstance(e, N.Deref):
            return self.const_addr(e.operand)
        return None

    def lvalue(self, e):
        t = e.type
        if isinstance(e, N.Ident):
            return LV('direct', t, e.sym.asm, 0)
        if isinstance(e, N.Str):
            return LV('direct', t, e.label, 0)
        if isinstance(e, N.Deref):
            p = e.operand
            if self.defer is not None and isinstance(p, N.IncDec) and not p.prefix:
                plv = self.lvalue(p.target)
                step = self.incw_step(self.as_compound(p))
                if plv.kind == 'direct' and not plv.volatile and step is not None:
                    # C: artırma bir sonraki sıra noktasına kadar yapılabilir -> deyim sonu
                    self.defer.append((step, plv.bytes()[0].text))
                    return LV('indirect', t, addr=plv.bytes())
            ca = self.const_addr(p)
            if ca is not None:
                return LV('direct', t, ca[0], ca[1])
            if isinstance(p, N.Binary) and p.op in ('+', '-') and p.type.is_ptr:
                base = self.const_addr(p.left)
                if base is not None:
                    if isinstance(p.right, N.Const):
                        k = p.right.value if p.op == '+' else -p.right.value
                        return LV('direct', t, base[0], base[1] + k)
                    B = self.lv_imm(base)
                    I = self.spill(self.gen(p.right, 2))
                    return LV('indirect', t, parts=(B, I, p.op))
                P, I = self.gen_pair(p.left, 2, p.right, 2)
                return LV('indirect', t, parts=(self.spill(P), self.spill(I), p.op))
            return LV('indirect', t, addr=self.spill(self.gen(p, 2)))
        self.error('sol değer bekleniyor', e)

    def lv_imm(self, base_off):
        base, off = base_off
        if isinstance(base, int):
            return imm(base + off)
        return imm_sym(base if off == 0 else f'{base}+{off}' if off > 0 else f'{base}-{-off}')

    def lv_address(self, lv):
        """Sol değerin adresi (2 byte'lık işlenen)."""
        if lv.kind == 'direct':
            return self.lv_imm((lv.base, lv.off))
        if lv.addr is not None:
            return lv.addr
        B, I, op = lv.parts
        return self.bytewise(op, B, I, 2, None)

    def load_x_uses_a(self, lv):
        if lv.parts is not None:
            return True
        a = lv.addr
        if all(b.kind == 'imm' for b in a):
            return False
        return not (a[0].kind == 'mem' and a[1].kind == 'mem' and a[0].base == a[1].base
                    and a[1].off == a[0].off + 1)

    def load_x(self, lv):
        if lv.parts is not None:
            B, I, op = lv.parts
            carry = False
            for i, reg in enumerate(('TAXL', 'TAXH')):
                b, x = B[i], I[i]
                if not carry and is_imm_val(x, 0):
                    self.load(b)
                elif not carry and op == '+' and is_imm_val(b, 0):
                    self.load(x)
                else:
                    self.load(b)
                    if op == '+':
                        self.alu('ADC' if carry else 'ADD', x)
                    else:
                        self.alu('SBC' if carry else 'SUB', x)
                    carry = True
                self.e.ins(reg)
            return
        a = lv.addr
        if all(b.kind == 'imm' for b in a):
            if a[0].val is not None and a[1].val is not None:
                self.e.ins('LDX', f'#${a[0].val | a[1].val << 8:04X}')
            elif a[0].expr is not None and a[0].expr == a[1].expr and a[0].part == '<':
                self.e.ins('LDX', f'#{a[0].expr}')
            else:
                self.load(a[0])
                self.e.ins('TAXL')
                self.load(a[1])
                self.e.ins('TAXH')
            return
        if not self.load_x_uses_a(lv):
            self.e.ins('LDX', a[0].text)
            return
        self.load(a[0])
        self.e.ins('TAXL')
        self.load(a[1])
        self.e.ins('TAXH')

    def read_lv(self, lv, n):
        size = lv.type.size
        if lv.type.is_array:
            self.error('dizi değer olarak okunamaz', None)
        if lv.kind == 'direct':
            if not lv.volatile:
                return lv.bytes(n) if n else None
            src = lv.bytes()
            if size == 1:
                self.e.ins('LDA', src[0].text)
                return [ACC] if n else None
            t = self.temp(2)
            for i in range(2):
                self.e.ins('LDA', src[i].text)
                self.e.ins('STA', t[i].text)
            return t[:n] if n else None
        self.load_x(lv)
        if size == 1:
            self.e.ins('LDA', '(X)')
            return [ACC] if n else None
        if n == 1 and not lv.volatile:
            self.e.ins('LDA', '(X)')
            return [ACC]
        t = self.temp(2)
        self.e.ins('LDA', '(X+)')
        self.e.ins('STA', t[0].text)
        self.e.ins('LDA', '(X)')
        self.e.ins('STA', t[1].text)
        return t[:n] if n else None

    def store_lv(self, lv, val):
        size = lv.type.size
        if lv.kind == 'direct':
            self.store_bytes(val, lv.bytes())
            return
        if has_acc(val) and self.load_x_uses_a(lv):
            val = self.spill(val)
        self.load_x(lv)
        for i in range(size):
            self.load(val[i])
            self.e.ins('STA', '(X+)' if i < size - 1 else '(X)')
