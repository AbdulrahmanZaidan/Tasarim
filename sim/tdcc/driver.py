"""Derleme hattı: ön işlemci -> lexer -> parser -> sema -> codegen -> (assembler)."""

import random
from pathlib import Path

from td8 import asm
from td8.bus import Bus
from td8.emu_ref import RefEmu

from .codegen import CodeGen
from .errors import CompileError
from .parser import parse
from .preproc import preprocess
from .sema import analyze


class Result:
    def __init__(self, asm_text, unit, codegen):
        self.asm = asm_text
        self.unit = unit
        self.codegen = codegen
        self.program = None             # assemble() sonrası td8.asm.Program

    @property
    def ram_end(self):
        return self.codegen.ram_end


def compile_c(source, filename='<kaynak>', asm_dir=None, include_dirs=None, defines=None):
    """C kaynağını TD-8 assembly metnine çevirir. Hata: CompileError."""
    if filename != '<kaynak>' and include_dirs is None:
        include_dirs = []
    toks = preprocess(source, filename, include_dirs, defines)
    prog = parse(toks)
    unit = analyze(prog)
    cg = CodeGen(unit, source, filename, asm_dir)
    text = cg.generate()
    return Result(text, unit, cg)


def assemble(result, asm_filename='<kaynak>'):
    """Üretilen assembly'yi çevirir; ROM taşmasını denetler."""
    try:
        prog = asm.assemble(result.asm, filename=asm_filename)
    except asm.AsmError as e:
        raise CompileError(f'assembler hatası (derleyici hatası olabilir): {e}') from None
    used_high = [a for a in range(0x8000, 0x10000) if prog.used[a]]
    if used_high:
        raise CompileError(f'program ROM\'a sığmıyor (32 KB): ${used_high[0]:04X} adresine taşıyor')
    result.program = prog
    return prog


def build(source, filename='<kaynak>', **kw):
    result = compile_c(source, filename, **kw)
    assemble(result)
    return result


def code_size(prog):
    """ROM'da kullanılan byte sayısı."""
    return sum(prog.used[:0x8000])


def run(prog, micro=False, max_cycles=5_000_000, garbage_ram=True, keys=None, bus=None):
    """Programı reset'ten çalıştırır. RAM rastgele çöple başlar (crt0 testi için)."""
    bus = bus or Bus()
    bus.load(bytes(prog.image[:0x8000]))
    if garbage_ram:
        rng = random.Random(1234)
        bus.mem[0x8000:0xF000] = bytes(rng.randrange(256) for _ in range(0x7000))
    if keys:
        bus.press(*keys)
    if micro:
        from td8.emu_micro import MicroEmu
        cpu = MicroEmu(bus)
    else:
        cpu = RefEmu(bus)
    cpu.run(max_cycles)
    return bus, cpu
