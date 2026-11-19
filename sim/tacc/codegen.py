"""Kod üretimi: program yerleşimi, fonksiyonlar, deyimler.

Bellek (SISTEM-PLANI 7.1, 11.3):
    ROM 0000-   crt0 (reset), fonksiyonlar, sabit tablolar, metinler, .data kopyası,
                gerekiyorsa runtime.asm + rt_c.asm
    RAM 8000-801F runtime yuvaları (__rv = 8000)
        8020-   .data, .bss (globaller), sonra fonksiyon çerçeveleri
    Çerçeve = parametreler + yereller + geçiciler (sabit adresler). Birbirini
    çağırmayan fonksiyonların çerçeveleri çağrı grafiğine göre üst üste biner.
"""

import os
from pathlib import Path

from . import nodes as N
from .emit import Emitter, mem
from .errors import CompileError
from .exprgen import ExprGen

LIB_DIR = Path(__file__).resolve().parent.parent / 'lib'
RAM_START = 0x8020
RAM_END = 0xEF00            # stack sayfası


def c_decl(t, name):
    return f'{t} {name}'


class CodeGen(ExprGen):
    def __init__(self, unit, source=None, filename='<kaynak>', asm_dir=None):
        self.unit = unit
        self.e = Emitter()
        self.nlabels = 0
        self.needs_runtime = False
        self.needs_rtc = False
        self.func = None
        self.temp_top = 0
        self.loops = []                 # (break etiketi, continue etiketi ya da None)
        self.lv_stack = []
        self.defer = None               # ertelenmiş son ek artırmalar (yalnız deyim düzeyinde)
        self.filename = filename
        self.sources = {}
        if source is not None:
            self.sources[filename] = source.splitlines()
        self.last_loc = None
        self.asm_dir = asm_dir

    # --- yardımcılar ------------------------------------------------------------
    def error(self, msg, where):
        if where is None:
            raise CompileError(msg, self.filename, 0)
        raise CompileError(msg, where.file, where.line)

    def new_label(self):
        self.nlabels += 1
        return f'.L{self.nlabels}'

    def temp(self, n):
        f = self.func
        off = self.temp_top
        self.temp_top += n
        f.temp_size = max(f.temp_size, self.temp_top)
        name = f'{f.sym.asm}.{off}'
        f.temp_names[name] = off
        return mem(name, 0, n)

    def reset_temps(self):
        self.temp_top = 0

    def source_line(self, file, line):
        if file not in self.sources:
            try:
                self.sources[file] = Path(file).read_text(encoding='utf-8').splitlines()
            except OSError:
                self.sources[file] = []
        lines = self.sources[file]
        return lines[line - 1].strip() if 0 < line <= len(lines) else ''

    def loc(self, node):
        key = (node.file, node.line)
        if key == self.last_loc or not node.line:
            return
        self.last_loc = key
        text = self.source_line(node.file, node.line)
        self.e.comment(f'{os.path.basename(node.file)}:{node.line}: {text}')

    def lib_path(self, name):
        path = LIB_DIR / name
        if self.asm_dir is not None:
            try:
                return os.path.relpath(path, self.asm_dir).replace('\\', '/')
            except ValueError:
                pass
        return path.as_posix()

    # --- program ----------------------------------------------------------------
    def reachable(self):
        funcs = self.unit.func_by_name
        seen, order = set(), []

        def visit(name):
            seen.add(name)
            for callee, _ in funcs[name].calls:
                if callee not in seen:
                    visit(callee)
            order.append(name)
        visit('main')
        return list(reversed(order))        # çağıranlar önce (topolojik)

    def generate(self):
        order = self.reachable()
        reach = set(order)
        for f in self.unit.funcs:
            if f.name in reach:
                self.gen_func(f)
        skipped = [f.name for f in self.unit.funcs if f.name not in reach]
        return self.assemble_text(order, skipped)

    def gen_func(self, f):
        self.func = f
        f.temp_size = 0
        f.temp_names = {}
        t = f.sym.type
        params = ', '.join(c_decl(p.type, p.name) for p in f.params) or 'void'
        self.e.text('')
        self.e.text(f'; ---- {t.ret} {f.name}({params}) ----')
        self.last_loc = None
        self.e.label(f.sym.asm)
        self.s_Block(f.node.body)
        if not self.e.last_is_exit():
            self.e.ins('RET')
        self.func = None

    # --- deyimler ---------------------------------------------------------------
    def stmt(self, s):
        if not isinstance(s, (N.Block, N.Empty)):
            self.loc(s)
        getattr(self, 's_' + type(s).__name__)(s)

    def s_Block(self, s):
        for item in s.items:
            self.stmt(item)

    def s_Empty(self, s):
        pass

    def s_DeclStmt(self, s):
        for d in s.decls:
            if not isinstance(d, N.VarDecl) or d.sym.kind != 'local':
                continue
            for off, st, v in d.init_stores:
                self.reset_temps()
                self.gen_into(v, mem(d.sym.asm, off, st.size))

    def s_ExprStmt(self, s):
        self.reset_temps()
        self.defer = []
        self.gen(s.expr, 0)
        self.flush_deferred()
        self.defer = None

    def s_If(self, s):
        self.reset_temps()
        if isinstance(s.cond, N.Const):
            if s.cond.value:
                self.stmt(s.then)
            elif s.other is not None:
                self.stmt(s.other)
            return
        lelse = self.new_label()
        self.cond(s.cond, lelse, False)
        self.stmt(s.then)
        if s.other is not None:
            lend = self.new_label()
            if not self.e.last_is_exit():
                self.e.ins('JMP', lend)
            self.e.label(lelse)
            self.stmt(s.other)
            self.e.label(lend)
        else:
            self.e.label(lelse)

    def loop(self, body, lbreak, lcont):
        self.loops.append((lbreak, lcont))
        self.stmt(body)
        self.loops.pop()

    def s_While(self, s):
        lbody, lcond, lend = self.new_label(), self.new_label(), self.new_label()
        self.e.ins('JMP', lcond)
        self.e.label(lbody)
        self.loop(s.body, lend, lcond)
        self.e.label(lcond)
        self.loc(s)
        self.reset_temps()
        self.cond(s.cond, lbody, True)
        self.e.label(lend)

    def s_DoWhile(self, s):
        lbody, lcond, lend = self.new_label(), self.new_label(), self.new_label()
        self.e.label(lbody)
        self.loop(s.body, lend, lcond)
        self.e.label(lcond)
        self.reset_temps()
        self.cond(s.cond, lbody, True)
        self.e.label(lend)

    def s_For(self, s):
        if isinstance(s.init, N.DeclStmt):
            self.s_DeclStmt(s.init)
        elif s.init is not None:
            self.reset_temps()
            self.gen(s.init.expr, 0)
        lbody, lstep, lcond, lend = (self.new_label() for _ in range(4))
        self.e.ins('JMP', lcond)
        self.e.label(lbody)
        self.loop(s.body, lend, lstep)
        self.e.label(lstep)
        self.loc(s)
        if s.step is not None:
            self.reset_temps()
            self.gen(s.step, 0)
        self.e.label(lcond)
        if s.cond is not None:
            self.reset_temps()
            self.cond(s.cond, lbody, True)
        else:
            self.e.ins('JMP', lbody)
        self.e.label(lend)

    def s_Switch(self, s):
        self.reset_temps()
        lend = self.new_label()
        for c in s.cases:
            c.label = self.new_label()
        if s.default is not None:
            s.default.label = self.new_label()
        kind, inner = self.narrow(s.expr)
        if kind in ('z', 's'):
            op = self.gen(inner, 1)
            self.load(op[0])
            for c in s.cases:
                v = c.value & 0xFFFF
                if self.fits(v, kind):
                    self.e.ins('CMP', f'#${v & 0xFF:02X}')
                    self.e.ins('BEQ', c.label)
        else:
            op = self.spill(self.gen(s.expr, 2))
            for c in s.cases:
                v = c.value & 0xFFFF
                self.load(op[0])
                self.e.ins('CMP', f'#${v & 0xFF:02X}')
                self.load(op[1])
                self.e.ins('CPC', f'#${v >> 8:02X}')
                self.e.ins('BEQ', c.label)
        self.e.ins('JMP', s.default.label if s.default is not None else lend)
        self.loop(s.body, lend, None)
        self.e.label(lend)

    def s_Case(self, s):
        self.e.label(s.label)

    def s_Default(self, s):
        self.e.label(s.label)

    def s_Break(self, s):
        self.e.ins('JMP', self.loops[-1][0])

    def s_Continue(self, s):
        for _, lcont in reversed(self.loops):
            if lcont is not None:
                self.e.ins('JMP', lcont)
                return
        self.error("'continue' döngü dışında", s)

    def s_Return(self, s):
        if s.expr is not None:
            self.reset_temps()
            rt = self.func.sym.type.ret
            if rt.is_void:
                self.gen(s.expr, 0)
            elif rt.size == 1:
                self.load(self.gen(s.expr, 1)[0])
            else:
                self.gen_into(s.expr, mem('__rv', 0, 2))
        self.e.ins('RET')

    # --- çıktı ------------------------------------------------------------------
    def frame_layout(self, order):
        """Çerçeve tabanları (çerçeve alanının başına göre) ve toplam boyut."""
        funcs = self.unit.func_by_name
        size = {}
        for name in order:
            f = funcs[name]
            f.frame_size = (sum(p.type.size for p in f.params) +
                            sum(v.type.size for v in f.locals) + f.temp_size)
            size[name] = f.frame_size
        base = {name: 0 for name in order}
        for name in order:                   # topolojik sıra: çağıran önce
            for callee, _ in funcs[name].calls:
                base[callee] = max(base[callee], base[name] + size[name])
        total = max((base[n] + size[n] for n in order), default=0)
        return base, total

    def data_bytes(self, items):
        out = []
        for i in range(0, len(items), 12):
            chunk = items[i:i + 12]
            out.append('        .byte ' + ', '.join(
                f'${b:02X}' if isinstance(b, int) else b for b in chunk))
        return out

    def assemble_text(self, order, skipped):
        u = self.unit
        L = [f'; tacc çıktısı: {os.path.basename(self.filename)}',
             '; Bellek: kod ROM 0000-, değişkenler RAM 8020-, runtime yuvaları 8000-801F.',
             f'        .include "{self.lib_path("crt0.asm")}"']
        if skipped:
            L.append('; main\'den ulaşılmayan, üretilmeyen fonksiyonlar: ' + ', '.join(skipped))
        L += self.e.lines()

        # ROM verileri
        L += ['', '; ---- ROM: sabit tablolar ve metinler ----']
        for g in u.globals:
            if g.storage == 'rom':
                L.append(f'{g.asm}:' + f'                ; {c_decl(g.type, g.name)}')
                L += self.data_bytes(g.init if g.init is not None else [0] * g.type.size)
        for data, lab in u.strings.items():
            shown = data.decode('latin-1').encode('unicode_escape').decode('ascii')
            L.append(f'{lab}:                ; "{shown}"')
            L += self.data_bytes(list(data) + [0])
        L.append('__data_rom:')
        data_syms = [g for g in u.globals if g.storage == 'data']
        for g in data_syms:
            L.append(f'        ; {c_decl(g.type, g.name)}')
            L += self.data_bytes(g.init)
        if self.needs_runtime or self.needs_rtc:
            L += ['', f'        .include "{self.lib_path("runtime.asm")}"']
        if self.needs_rtc:
            L.append(f'        .include "{self.lib_path("rt_c.asm")}"')

        # RAM
        L += ['', '; ---- RAM ----']
        addr = RAM_START
        L.append(f'__data_ram = ${addr:04X}')
        for g in data_syms:
            L.append(f'{g.asm} = ${addr:04X}        ; {c_decl(g.type, g.name)}')
            addr += g.type.size
        L.append(f'__data_size = {addr - RAM_START}')
        L.append(f'__bss_start = ${addr:04X}')
        bss_start = addr
        for g in u.globals:
            if g.storage == 'bss':
                L.append(f'{g.asm} = ${addr:04X}        ; {c_decl(g.type, g.name)}')
                addr += g.type.size
        L.append(f'__bss_size = {addr - bss_start}')

        base, total = self.frame_layout(order)
        frames = addr
        L.append(f'; çerçeveler: ${frames:04X}-, toplam {total} byte (bindirme ile)')
        for name in order:
            f = u.func_by_name[name]
            a = frames + base[name]
            L.append(f'; {name}: ${a:04X}, {f.frame_size} byte')
            for v in f.params + f.locals:
                L.append(f'{v.asm} = ${a:04X}        ; {c_decl(v.type, v.name)}')
                a += v.type.size
            for tname, off in sorted(f.temp_names.items(), key=lambda kv: kv[1]):
                L.append(f'{tname} = ${a + off:04X}')
        end = frames + total
        if end > RAM_END:
            raise CompileError(f'RAM yetmiyor: değişkenler ${end:04X} adresine kadar uzanıyor '
                               f'(sınır ${RAM_END:04X})', self.filename, 0)
        self.ram_end = end
        return '\n'.join(L) + '\n'
