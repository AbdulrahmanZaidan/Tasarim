"""TD-8 komut satırı aracı.

    py cli.py roms                      build/ altına tüm ROM imajlarını üretir
    py cli.py asm program.asm [-o x.bin] programı çevirir, 32 KB ROM imajı yazar
    py cli.py run program.asm [...]     programı emülatörde çalıştırır, ekranı gösterir
    py cli.py vectors alu|urom [-n N]   Digital için test vektörleri yazar
"""

import argparse
import random
import sys
from pathlib import Path

from td8 import alu, asm, isa, microcode, vga
from td8.bus import Bus
from td8.emu_micro import MicroEmu
from td8.emu_ref import RefEmu

BUILD = Path(__file__).parent / 'build'


def write_rom(path, data):
    """.bin ve Digital/Logisim için .hex ('v2.0 raw') yazar."""
    path.with_suffix('.bin').write_bytes(bytes(data))
    lines = ['v2.0 raw']
    for i in range(0, len(data), 16):
        lines.append(' '.join(f'{b:x}' for b in data[i:i + 16]))
    path.with_suffix('.hex').write_text('\n'.join(lines) + '\n', encoding='ascii')


def cmd_roms(args):
    BUILD.mkdir(exist_ok=True)
    roms = microcode.build()
    for i, rom in enumerate(roms):
        write_rom(BUILD / f'urom{i}', rom)
    lo, hi = alu.build_tables()
    write_rom(BUILD / 'alu_lo', lo)
    write_rom(BUILD / 'alu_hi', hi)
    write_rom(BUILD / 'vga_timing', vga.timing_rom())
    if args.font:
        font = vga.font_from_c_header(Path(args.font).read_text(encoding='utf-8', errors='replace'))
    else:
        font = vga.test_font()
    write_rom(BUILD / 'font', font)
    print(f'{BUILD}: urom0-2, alu_lo, alu_hi, vga_timing, font (.bin + .hex, 128 KB)')
    print(f'Komut sayısı: {len(isa.MNEMONICS)}, opcode sayısı: {len(isa.INSTRUCTIONS)}')


def _assemble(path):
    source = Path(path).read_text(encoding='utf-8')
    try:
        return asm.assemble(source, filename=str(path))
    except asm.AsmError as e:
        sys.exit(f'HATA: {e}')


def cmd_asm(args):
    prog = _assemble(args.source)
    out = Path(args.output or Path(args.source).with_suffix('.bin'))
    out.write_bytes(prog.rom())
    for start, length in prog.ranges():
        print(f'  {start:04X}–{start + length - 1:04X}  {length} byte')
    if any(start >= 0x8000 for start, _ in prog.ranges()):
        print('Not: 8000 ve üstündeki byte\'lar ROM imajında yok; RAM\'e Arduino yükler.')
    print(f'{out}: 32 KB ROM imajı')
    if args.list:
        for no, addr, data, raw in prog.listing:
            print(f'{addr:04X}  {data.hex(" "):<12} {raw}')


def cmd_run(args):
    prog = _assemble(args.source)
    bus = Bus(vga_model=args.vga)
    bus.load(prog.image)
    bus.dip = args.dip
    if args.keys:
        bus.press(*[int(k, 16) for k in args.keys.split(',')])
    cpu = RefEmu(bus) if args.ref else MicroEmu(bus)
    if args.trace and not args.ref:
        cpu.trace = []
    cpu.run(args.cycles)
    print(f'{"durdu (HALT)" if cpu.halted else "çevrim sınırı doldu"} · {cpu.cycles} çevrim '
          f'({cpu.cycles / 1000:.2f} ms @ 1 MHz)')
    s = cpu.state()
    print(f'PC={s["pc"]:04X} A={s["a"]:02X} X={s["x"]:04X} SP={s["sp"]:02X} '
          f'Z={s["z"]} C={s["c"]} N={s["n"]} V={s["v"]} LED={bus.leds:08b}')
    if getattr(cpu, 'stall_cycles', 0):
        print(f'VRAM penceresi beklemesi: {cpu.stall_cycles} çevrim')
    if args.trace and not args.ref:
        for cyc, ab, db, cw in cpu.trace[:args.trace]:
            print(f'{cyc:8d}  AB={ab:04X} DB={db:02X}  {microcode.describe(cw)}')
    print('+' + '-' * 40 + '+')
    for line in bus.screen():
        print('|' + line + '|')
    print('+' + '-' * 40 + '+')


def cmd_vectors(args):
    """Digital'in test bileşenine yapıştırılacak vektörler (SISTEM-PLANI 12.3)."""
    rng = random.Random(args.seed)
    if args.what == 'alu':
        print('# M4 ALU testi: girişler OP A B Cin Zin, çıkışlar R Z C N V')
        print('OP A B Cin Zin R Z C N V')
        for _ in range(args.n):
            op = rng.randrange(len(isa.ALUOPS))
            a, b = rng.randrange(256), rng.randrange(256)
            c, z = rng.randrange(2), rng.randrange(2)
            r, nz, nc, n, v = alu.alu_ref(op, a, b, c, z)
            print(f'{op} 0x{a:02X} 0x{b:02X} {c} {z} 0x{r:02X} {nz} {nc} {n} {v}')
    else:
        roms = microcode.build()
        print('# M2 kontrol testi: girişler STEP IR Z C N V (BANK = 0), çıkışlar CW0 CW1 CW2')
        print('STEP IR Z C N V CW0 CW1 CW2')
        for _ in range(args.n):
            st, ir = rng.randrange(16), rng.randrange(256)
            z, c, n, v = (rng.randrange(2) for _ in range(4))
            w = microcode.word_at(roms, st, ir, z, c, n, v)
            print(f'{st} 0x{ir:02X} {z} {c} {n} {v} 0x{w & 0xFF:02X} 0x{(w >> 8) & 0xFF:02X} 0x{w >> 16:02X}')


def main(argv=None):
    p = argparse.ArgumentParser(prog='cli.py', description='TD-8 araçları')
    sub = p.add_subparsers(dest='cmd', required=True)

    r = sub.add_parser('roms', help='ROM imajlarını üret')
    r.add_argument('--font', help='font8x8_basic.h yolu (verilmezse test deseni)')
    r.set_defaults(func=cmd_roms)

    a = sub.add_parser('asm', help='assembly çevir')
    a.add_argument('source')
    a.add_argument('-o', '--output')
    a.add_argument('-l', '--list', action='store_true', help='listeyi yazdır')
    a.set_defaults(func=cmd_asm)

    u = sub.add_parser('run', help='emülatörde çalıştır')
    u.add_argument('source')
    u.add_argument('--cycles', type=int, default=2_000_000, help='en fazla çevrim')
    u.add_argument('--ref', action='store_true', help='komut seviyesi emülatör')
    u.add_argument('--vga', action='store_true', help='VRAM penceresini modelle')
    u.add_argument('--keys', help='scan code listesi, örn. 1C,F0,1C')
    u.add_argument('--dip', type=lambda s: int(s, 0), default=0)
    u.add_argument('--trace', type=int, default=0, help='ilk N çevrimin izini yaz')
    u.set_defaults(func=cmd_run)

    v = sub.add_parser('vectors', help='Digital test vektörleri')
    v.add_argument('what', choices=['alu', 'urom'])
    v.add_argument('-n', type=int, default=1000)
    v.add_argument('--seed', type=int, default=1)
    v.set_defaults(func=cmd_vectors)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
