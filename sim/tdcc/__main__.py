"""Komut satırı:

    py -3 -m tdcc prog.c                      prog.asm yazar
    py -3 -m tdcc prog.c -o build/prog.asm    çıktı yolu
    py -3 -m tdcc prog.c --run                ayrıca çevirir, RefEmu'da çalıştırır, ekranı gösterir
    py -3 -m tdcc prog.c --run --micro        mikroadım emülatöründe çalıştırır
"""

import argparse
import sys
from pathlib import Path

from td8 import asm

from . import code_size, compile_c, run
from .errors import CompileError


def main(argv=None):
    p = argparse.ArgumentParser(prog='tdcc', description='TD-8 C derleyicisi')
    p.add_argument('source')
    p.add_argument('-o', '--output', help='assembly çıktısı (varsayılan: kaynak.asm)')
    p.add_argument('--run', action='store_true', help='çevir ve emülatörde çalıştır')
    p.add_argument('--micro', action='store_true', help='mikroadım emülatörü (MicroEmu)')
    p.add_argument('--cycles', type=int, default=5_000_000, help='en fazla çevrim')
    p.add_argument('--keys', help='scan code listesi, örn. 1C,F0,1C')
    args = p.parse_args(argv)

    src_path = Path(args.source)
    out = Path(args.output) if args.output else src_path.with_suffix('.asm')
    try:
        source = src_path.read_text(encoding='utf-8')
    except OSError as e:
        sys.exit(f'HATA: {e}')
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = compile_c(source, str(src_path), asm_dir=str(out.parent.resolve()))
    except CompileError as e:
        sys.exit(f'HATA: {e}')
    out.write_text(result.asm, encoding='utf-8')
    try:
        prog = asm.assemble(result.asm, filename=str(out))
    except asm.AsmError as e:
        sys.exit(f'HATA (assembler): {e}')
    print(f'{out}: {len(result.asm.splitlines())} satır assembly, ROM {code_size(prog)} byte, '
          f'RAM 8020-{result.ram_end - 1:04X} ({result.ram_end - 0x8020} byte)')
    if not args.run:
        return
    keys = [int(k, 16) for k in args.keys.split(',')] if args.keys else None
    bus, cpu = run(prog, micro=args.micro, max_cycles=args.cycles, keys=keys)
    emu = 'MicroEmu' if args.micro else 'RefEmu'
    state = 'durdu (HALT)' if cpu.halted else 'çevrim sınırı doldu'
    print(f'{emu}: {state} · {cpu.cycles} çevrim ({cpu.cycles / 1000:.2f} ms @ 1 MHz) · '
          f'LED={bus.leds:08b} (${bus.leds:02X})')
    print('+' + '-' * 40 + '+')
    for line in bus.screen():
        print('|' + line + '|')
    print('+' + '-' * 40 + '+')


if __name__ == '__main__':
    main()
