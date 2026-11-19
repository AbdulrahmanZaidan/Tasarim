"""TA-8 komut satırı aracı.

    py cli.py roms                      build/ altına tüm ROM imajlarını üretir
    py cli.py asm program.asm [-o x.bin] [--ihex]  programı çevirir, 32 KB ROM imajı yazar
    py cli.py run program.asm [...]     programı emülatörde çalıştırır, ekranı gösterir
    py cli.py vectors alu|urom|decode|cs|trace [...]  devre testi vektörleri yazar
    py cli.py hw run program.asm [--cycles N] [--corner typ|max] [--seed S] [--mclk 4|6|8]
                                        çip seviyesindeki devrede çalıştırır, MicroEmu ile
                                        karşılaştırır, zamanlama özetini yazar
    py cli.py hw wiring [-o DOSYA]      pin pin kablolama tablosu (Markdown)
    py cli.py hw digital [-o KLASÖR] [--program X.asm] [--run N]
                                        Digital (.dig): modül dosyaları + ta8.dig; --run ile
                                        Digital'de N çevrim koşar, MicroEmu ile karşılaştırır
"""

import argparse
import sys
from pathlib import Path

from ta8 import alu, asm, ihex, isa, microcode, vectors, vga
from ta8.bus import Bus
from ta8.emu_micro import MicroEmu
from ta8.emu_ref import RefEmu

BUILD = Path(__file__).parent / 'build'


def write_rom(path, data, fmt='digital'):
    """.bin yazar; yanına .hex: fmt='digital' ise Digital/Logisim ('v2.0 raw'),
    fmt='ihex' ise Proteus için Intel HEX."""
    path.with_suffix('.bin').write_bytes(bytes(data))
    if fmt == 'ihex':
        path.with_suffix('.hex').write_text(ihex.dump(data), encoding='ascii', newline='\r\n')
        return
    lines = ['v2.0 raw']
    for i in range(0, len(data), 16):
        lines.append(' '.join(f'{b:x}' for b in data[i:i + 16]))
    path.with_suffix('.hex').write_text('\n'.join(lines) + '\n', encoding='ascii')


def cmd_roms(args):
    proteus_size = 0x10000      # Proteus'ta 27C512 (64K×8); flash'ların A16'sı 0 (bank 0)
    BUILD.mkdir(exist_ok=True)
    images = {f'urom{i}': rom for i, rom in enumerate(microcode.build())}
    images['alu_lo'], images['alu_hi'] = alu.build_tables()
    images['vga_timing'] = vga.timing_rom()
    if args.font:
        font = vga.font_from_c_header(Path(args.font).read_text(encoding='utf-8', errors='replace'))
    else:
        font = vga.test_font()
    images['font'] = font
    proteus = BUILD / 'proteus'
    proteus.mkdir(exist_ok=True)
    upper_differs = []
    for name, data in images.items():
        write_rom(BUILD / name, data)
        write_rom(proteus / name, data[:proteus_size], fmt='ihex')
        if data[proteus_size:] and data[proteus_size:] != data[:len(data) - proteus_size]:
            upper_differs.append(name)
    print(f'{BUILD}: urom0-2, alu_lo, alu_hi, vga_timing, font (.bin + .hex, 128 KB)')
    print(f'{proteus}: aynı imajların alt 64 KB\'ı, Proteus için (.bin + Intel HEX, 27C512)')
    if upper_differs:
        print(f'  proteus/ imajları bank 0\'dır (A16 = 0); üst 64 KB\'ı farklı olan: '
              f'{", ".join(upper_differs)}')
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
    if args.ihex:
        hx = out.with_suffix('.hex')
        if hx == out:
            sys.exit('HATA: --ihex ile -o dosyası .hex olamaz')
        hx.write_text(ihex.dump(prog.rom()), encoding='ascii', newline='\r\n')
        print(f'{hx}: aynı imaj, Intel HEX (Proteus)')
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
    """Devre simülatörünün test bileşeni için vektörler (SISTEM-PLANI 12.3)."""
    if args.clock and (args.what != 'trace' or args.format != 'digital'):
        sys.exit('HATA: --clock yalnız "vectors trace ... --format digital" ile kullanılır')
    if (args.what == 'trace') != bool(args.source):
        sys.exit('HATA: .asm dosyası yalnız trace için ve trace için zorunlu: '
                 'vectors trace PROGRAM.asm')
    if args.what == 'trace':
        text = vectors.trace_vectors(_assemble(args.source).image, args.cycles,
                                     args.format, args.clock)
    elif args.what == 'cs':
        text = vectors.cs_vectors(args.format)
    else:
        gen = {'alu': vectors.alu_vectors, 'urom': vectors.urom_vectors,
               'decode': vectors.decode_vectors}[args.what]
        text = gen(args.n, args.seed, args.format)
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
        rows = len(vectors.parse_table(text)[1])
        print(f'{args.output}: {args.what}, {rows} vektör ({args.format})')
    else:
        sys.stdout.write(text)


def cmd_hw(args):
    """Çip seviyesindeki netlist (ta8/hw): çalıştırma ve kablolama tablosu."""
    from ta8.hw import harness, wiring
    from ta8.hw.cpu import build
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')        # Windows konsolunda → gibi işaretler
    if args.hw_cmd == 'wiring':
        text = wiring.wiring_table(build(wait_fix=not args.plan_wait))
        if args.output:
            Path(args.output).write_text(text, encoding='utf-8')
            print(f'{args.output}: {len(text.splitlines())} satır')
        else:
            sys.stdout.write(text)
        return
    prog = _assemble(args.source)
    keys = tuple(int(k, 16) for k in args.keys.split(',')) if args.keys else ()
    hw = harness.HwCpu(prog.image, corner=args.corner, mclk_mhz=args.mclk,
                       power_up='random' if args.seed is not None else 'zero',
                       seed=args.seed or 1, keys=keys, dip=args.dip, wait_fix=not args.plan_wait,
                       vwr=0 if args.wait else 1)
    if args.wait:                                   # pencere 17 µs kapalı / 3 µs açık
        p = 2 * hw.half
        for k in range(args.cycles // 20 + 2):
            hw.set('VWR_s', 1, at=(k * 20000 + 17000) // p * p)
            hw.set('VWR_s', 0, at=(k * 20000 + 20000) // p * p)
    import time
    t0 = time.perf_counter()
    hw.run(args.cycles)
    dt = time.perf_counter() - t0
    emu = harness.emu_like(hw, prog.image, hw.n if not hw.halted else args.cycles, keys)
    diffs = harness.compare(hw, emu)
    mhz = 1000 / (8 * hw.half)
    print(f'TA-8 çip seviyesi: {args.source} | köşe {args.corner} | MCLK {4 * mhz:.2f} MHz '
          f'(CPU {mhz:.2f} MHz) | açılış {"rastgele, tohum %d" % args.seed if args.seed is not None else "sıfır"}'
          + (' | WAIT: planın yazdığı hâli' if args.plan_wait else ''))
    print(f'{"durdu (HALT)" if hw.halted else "çevrim sınırı doldu"} · {hw.n} çevrim · '
          f'{len(hw.board.chips)} çip · simülasyon {dt:.1f} s ({hw.n / max(dt, 1e-9):.0f} çevrim/s)')
    if diffs:
        print('MicroEmu ile karşılaştırma: FARK VAR')
        for d in diffs:
            print('  ' + d)
    else:
        print(f'MicroEmu ile karşılaştırma: SIFIR FARK ({len(hw.trace)} çevrim; iz'
              + (', registerlar, RAM, VRAM, LED' if hw.halted and emu.halted else ' (ortak kısım)')
              + ')')
    s = hw.state()
    print(f'PC={s["pc"]:04X} AR={s["ar"]:04X} X={s["x"]:04X} SP={s["sp"]:02X} A={s["a"]:02X} '
          f'IR={s["ir"]:02X} STEP={s["step"]} Z={s["z"]} C={s["c"]} N={s["n"]} V={s["v"]} '
          f'LED={hw.leds():08b}')
    if args.wait:
        print(f'WAIT: D fazında bekleme {hw.stall_ns / 1000:.1f} µs, VRAM yazması '
              f'{len(hw.vram_writes)}, pencere kapalıyken yazma {len(hw.wait_errors)}')
    cl = harness.classify_violations(hw)
    hs = harness.handover_summary(cl['devir_teslim'])
    print(f'İhlaller: açılış (reset basılıyken) {len(cl["acilis"])}, C->D devir-teslim '
          f'{len(cl["devir_teslim"])}, diğer {len(cl["diger"])}')
    for ref, (n, m) in hs.items():
        print(f'  devir-teslim {ref}: {n} kez, en uzun {m} ns')
    for v in cl['diger'][:10]:
        print(f'  {v.time} ns {v.kind} {v.ref}: {v.desc}')
    tr = hw.timing_report()
    print('Zamanlama (yaklaşık; gecikme tablosunun bir kısmı tahmin) - en kötü oturma / pencere, ns:')
    rows = [('yol1', 'yol 1 okuma + ALU -> A/F (LCLK\'ten)', 'elle 254/403, 161 kurulumu dahil'),
            ('yol2', 'yol 2 uROM araması (CLK\'ten)', 'elle 94/152, 273 kurulumu dahil'),
            ('yol3', 'yol 3 WAIT kararı (LCLK\'ten)', 'elle ~236 (138\'li)'),
            ('yol3_mclk', 'yol 3 WAIT kararı (C->D MCLK kenarından)', '74HC74 kurulumu hariç'),
            ('wait', '/WAIT çıkışı (LCLK\'ten)', '')]
    for key, label, hand in rows:
        settle, cyc, window, _ = tr[key]
        if cyc is None:
            print(f'  {label:44s}: ölçülmedi' + (' (WAIT olmadı; --wait ile deneyin)'
                                                if key in ('yol3', 'yol3_mclk', 'wait') else ''))
        else:
            print(f'  {label:44s}: {settle:4d} / {window} (çevrim {cyc}){"; " + hand if hand else ""}')
    if diffs or cl['diger'] or hw.wait_errors:
        sys.exit(1)


def cmd_hw_digital(args):
    """Digital dosyaları (SISTEM-PLANI 12.2): m1_saat … m5_bellek, aux, tb ve ta8.dig."""
    import time
    from ta8.hw import digital as dg, digital_cpu as dc
    src = Path(args.program)
    prog = _assemble(src)
    out = Path(args.output)
    t0 = time.perf_counter()
    files = dc.export_cpu(out, prog.image, src.stem, modules=not args.no_modules)
    total = 0
    for f in files:
        total += f.stat().st_size
        print(f'  {f}  {f.stat().st_size // 1024} KB')
    print(f'{len(files)} dosya, {total // 1024} KB, {time.perf_counter() - t0:.1f} s '
          f'(program ROM\'u: {src.name}; ROM içerikleri gömülü)')
    if not args.run:
        return
    setup = dg.find_digital()
    if setup is None:
        sys.exit('HATA: Digital bulunamadı (TA8_DIGITAL_HOME ya da ../araclar)')
    run = dc.digital_trace(out / 'ta8.dig', args.run, setup=setup)
    emu = dc.emu_reference(prog.image, args.run, run)
    diffs = dc.compare_run(run, emu)
    print(f'Digital: {len(run.trace)} çevrim, {"HALT" if run.halted else "çevrim sınırı"}, '
          f'{run.step.seconds:.1f} s ({run.step.rate} MCLK/s); MicroEmu: {len(emu.trace)} çevrim')
    if diffs:
        print('FARK VAR:')
        for d in diffs:
            print('  ' + d)
        sys.exit(1)
    print('MicroEmu ile karşılaştırma: SIFIR FARK (iz'
          + (', LED, RAM, VRAM)' if run.halted and emu.halted else ')'))


def main(argv=None):
    p = argparse.ArgumentParser(prog='cli.py', description='TA-8 araçları')
    sub = p.add_subparsers(dest='cmd', required=True)

    r = sub.add_parser('roms', help='ROM imajlarını üret')
    r.add_argument('--font', help='font8x8_basic.h yolu (verilmezse test deseni)')
    r.set_defaults(func=cmd_roms)

    a = sub.add_parser('asm', help='assembly çevir')
    a.add_argument('source')
    a.add_argument('-o', '--output')
    a.add_argument('-l', '--list', action='store_true', help='listeyi yazdır')
    a.add_argument('--ihex', action='store_true', help='Proteus için Intel HEX de yaz (aynı ad, .hex)')
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

    v = sub.add_parser('vectors', help='devre simülatörü test vektörleri')
    v.add_argument('what', choices=['alu', 'urom', 'decode', 'cs', 'trace'])
    v.add_argument('source', nargs='?', help='trace için .asm programı')
    v.add_argument('-n', type=int, default=1000, help='rastgele vektör sayısı (alu, urom, decode)')
    v.add_argument('--seed', type=int, default=1)
    v.add_argument('-o', '--output', help='çıktı dosyası (verilmezse ekrana)')
    v.add_argument('--format', choices=vectors.FORMATS, default='digital')
    v.add_argument('--cycles', type=int, default=2000, help='trace: en fazla çevrim (HALT\'ta durur)')
    v.add_argument('--clock', metavar='CLK',
                   help='trace, digital: bu adla ilk sütun ekler, her satırda C (saat darbesi)')
    v.set_defaults(func=cmd_vectors)

    h = sub.add_parser('hw', help='çip seviyesindeki devre (ta8/hw)')
    hsub = h.add_subparsers(dest='hw_cmd', required=True)
    hr = hsub.add_parser('run', help='devrede çalıştır, MicroEmu ile karşılaştır')
    hr.add_argument('source')
    hr.add_argument('--cycles', type=int, default=200_000, help='en fazla çevrim (HALT\'ta durur)')
    hr.add_argument('--corner', choices=['typ', 'max'], default='typ', help='gecikme köşesi')
    hr.add_argument('--seed', type=int, help='verilirse açılışta rastgele FF/register/SRAM içeriği')
    hr.add_argument('--mclk', type=int, choices=[4, 6, 8], default=4,
                    help='MCLK MHz (CPU = MCLK/4); 6 ve 8 yaklaşık (83 / 62 ns yarım periyot)')
    hr.add_argument('--keys', help='scan code listesi, örn. 1C,F0,1C')
    hr.add_argument('--dip', type=lambda s: int(s, 0), default=0)
    hr.add_argument('--wait', action='store_true',
                    help='VRAM penceresini 17 µs kapalı / 3 µs açık sür (WAIT yolunu ölçer)')
    hr.add_argument('--plan-wait', action='store_true',
                    help='WAIT kapısını planın yazdığı gibi kur (düzeltmesiz)')
    hr.set_defaults(func=cmd_hw)
    hw_ = hsub.add_parser('wiring', help='kablolama tablosu (Markdown)')
    hw_.add_argument('-o', '--output', help='çıktı dosyası (verilmezse ekrana)')
    hw_.add_argument('--plan-wait', action='store_true', help='düzeltmesiz WAIT kapısıyla')
    hw_.set_defaults(func=cmd_hw)
    hd = hsub.add_parser('digital', help='Digital (.dig) dosyalarını üret (modüller + ta8.dig)')
    hd.add_argument('-o', '--output', default=str(Path(__file__).parent / 'digital'),
                    help='çıktı klasörü (varsayılan sim/digital)')
    hd.add_argument('--program', default=str(Path(__file__).parent / 'examples' / 'merhaba.asm'),
                    help='program ROM\'una yüklenecek .asm (varsayılan examples/merhaba.asm)')
    hd.add_argument('--no-modules', action='store_true', help='yalnız ta8.dig')
    hd.add_argument('--run', type=int, metavar='N', default=0,
                    help='Digital\'de N çevrime kadar koş, MicroEmu ile karşılaştır')
    hd.set_defaults(func=cmd_hw_digital)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
