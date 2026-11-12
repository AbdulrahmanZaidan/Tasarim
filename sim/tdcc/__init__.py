"""tdcc: TD-8 için C alt kümesi derleyicisi (SISTEM-PLANI 11.2, 11.3).

    from tdcc import build, run
    result = build(open('prog.c').read(), 'prog.c')   # assembly + td8 Program
    bus, cpu = run(result.program)

Komut satırı: py -3 -m tdcc prog.c -o prog.asm [--run]
"""

from .driver import Result, assemble, build, code_size, compile_c, run
from .errors import CompileError

__all__ = ['CompileError', 'Result', 'assemble', 'build', 'code_size', 'compile_c', 'run']
