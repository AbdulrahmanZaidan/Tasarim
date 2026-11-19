"""Küçük ön işlemci (token düzeyinde).

Desteklenen yönergeler:
    #include "dosya"   önce kaynağın klasöründe, sonra sim/lib'de aranır
    #include <dosya>   yalnız sim/lib'de aranır
    #define AD değer   nesne benzeri makro (fonksiyon benzeri makro hata verir)
    #undef AD
    #ifdef / #ifndef / #if <sabit> / #else / #endif
    #pragma            yok sayılır
    #error ileti
Önceden tanımlı: __TACC__ = 1.
"""

from pathlib import Path

from .errors import CompileError
from .lexer import Token, tokenize

LIB_DIR = Path(__file__).resolve().parent.parent / 'lib'


def _directive_lines(toks, i):
    """toks[i] '#' token'ı. Yönerge token'larını ve sonraki indeksi döndürür."""
    j = i + 1
    while toks[j].kind != 'eof' and not toks[j].bol:
        j += 1
    return toks[i + 1:j], j


class Preprocessor:
    def __init__(self, include_dirs=None, defines=None):
        self.include_dirs = [Path(d) for d in (include_dirs or [])] + [LIB_DIR]
        self.macros = {'__TACC__': [Token('num', (1, False, True), '1', '<tacc>', 0, False, True)]}
        for name, value in (defines or {}).items():
            self.macros[name] = tokenize(str(value), '<-D>')[:-1]
        self.depth = 0
        self.files = []

    def run(self, src, file='<kaynak>'):
        out = []
        self._file(src, file, out)
        out.append(Token('eof', None, '', file, 0, True, True))
        return out

    def _file(self, src, file, out):
        self.depth += 1
        if self.depth > 16:
            raise CompileError('#include çok derin (döngü olabilir)', file, 0)
        self.files.append(file)
        toks = tokenize(src, file)
        conds = []          # (bu dal etkin mi, önceden bir dal seçildi mi, üst etkin mi)
        active = True
        i = 0
        while toks[i].kind != 'eof':
            t = toks[i]
            if t.is_op('#') and t.bol:
                line, i = _directive_lines(toks, i)
                active = self._directive(t, line, conds, active, out)
                continue
            i += 1
            if active:
                self._expand(t, out, set())
        if conds:
            raise CompileError('#endif eksik', file, toks[-1].line)
        self.depth -= 1

    def _directive(self, hash_tok, line, conds, active, out):
        if not line:
            return active                       # boş yönerge
        name_tok = line[0]
        name = name_tok.value if name_tok.kind in ('id', 'kw') else None
        args = line[1:]
        if name in ('ifdef', 'ifndef', 'if'):
            if not active:
                conds.append((False, True, False))
                return False
            if name == 'if':
                value = self._if_value(args, hash_tok)
            else:
                if not args or args[0].kind != 'id':
                    raise CompileError(f'#{name} bir ad bekliyor', hash_tok.file, hash_tok.line)
                value = (args[0].value in self.macros) == (name == 'ifdef')
            conds.append((value, value, True))
            return value
        if name == 'else':
            if not conds:
                raise CompileError('#else için #if yok', hash_tok.file, hash_tok.line)
            cur, taken, parent = conds.pop()
            new = parent and not taken
            conds.append((new, True, parent))
            return new
        if name == 'endif':
            if not conds:
                raise CompileError('#endif için #if yok', hash_tok.file, hash_tok.line)
            _, _, parent = conds.pop()
            return parent
        if name == 'elif':
            raise CompileError('#elif desteklenmiyor', hash_tok.file, hash_tok.line)
        if not active:
            return False
        if name == 'include':
            self._include(hash_tok, args, out)
        elif name == 'define':
            if not args or args[0].kind not in ('id', 'kw'):
                raise CompileError('#define bir ad bekliyor', hash_tok.file, hash_tok.line)
            mname = args[0].value
            body = args[1:]
            if body and body[0].is_op('(') and not body[0].space:
                raise CompileError(f'fonksiyon benzeri makro desteklenmiyor: {mname}',
                                   hash_tok.file, hash_tok.line)
            self.macros[mname] = body
        elif name == 'undef':
            if args:
                self.macros.pop(args[0].value, None)
        elif name == 'pragma':
            pass
        elif name == 'error':
            text = ' '.join(a.text for a in args)
            raise CompileError(f'#error {text}', hash_tok.file, hash_tok.line)
        else:
            raise CompileError(f'bilinmeyen ön işlemci yönergesi: #{name_tok.text}',
                               hash_tok.file, hash_tok.line)
        return True

    def _if_value(self, args, where):
        expanded = []
        for t in args:
            self._expand(t, expanded, set())
        if len(expanded) == 1 and expanded[0].kind == 'num':
            return expanded[0].value[0] != 0
        raise CompileError('#if yalnız tek bir tamsayı sabiti kabul eder', where.file, where.line)

    def _include(self, hash_tok, args, out):
        here = Path(hash_tok.file).parent if hash_tok.file not in ('<kaynak>', '<tacc>') else None
        if len(args) == 1 and args[0].kind == 'str':
            name = args[0].value.decode('latin-1')
            dirs = ([here] if here else []) + self.include_dirs
        elif args and args[0].is_op('<') and args[-1].is_op('>'):
            name = ''.join(a.text for a in args[1:-1])
            dirs = self.include_dirs
        else:
            raise CompileError('#include yazımı: #include "dosya"', hash_tok.file, hash_tok.line)
        for d in dirs:
            path = d / name
            if path.is_file():
                self._file(path.read_text(encoding='utf-8'), str(path), out)
                return
        raise CompileError(f'#include dosyası bulunamadı: {name}', hash_tok.file, hash_tok.line)

    def _expand(self, t, out, active_macros):
        if t.kind in ('id', 'kw') and t.value in self.macros and t.value not in active_macros:
            for m in self.macros[t.value]:
                # Hata iletileri makronun kullanıldığı satırı göstersin
                copy = Token(m.kind, m.value, m.text, t.file, t.line, False, m.space)
                self._expand(copy, out, active_macros | {t.value})
            return
        out.append(t)


def preprocess(src, file='<kaynak>', include_dirs=None, defines=None):
    return Preprocessor(include_dirs, defines).run(src, file)
