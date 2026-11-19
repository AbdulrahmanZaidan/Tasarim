"""TA-8 Arduino hata ayıklama kartı: komut satırı (SISTEM-PLANI 10, kabul ölçütü 16.3).

!!! Bu sürüm gerçek kartla HİÇ denenmedi; yalnız --fake (sahte cihaz) ile sınandı. !!!

    py -3 ardu_cli.py trace PROGRAM.asm --port COM5 [--cycles N] [--dip 01] [--rom ROM.bin]
                                         [--no-load] [--save iz.txt]
        İz modu: (varsa RAM bölümünü yükler) → reset → N çevrim iz → MicroEmu ile karşılaştırır,
        farkın başladığı ilk çevrimi ve alanı yazar. Fark varsa çıkış kodu 1.
    py -3 ardu_cli.py load PROGRAM.asm --port COM5 [--no-verify] [--reset] [--mod serbest|iz]
        Yükleme modu: programın 8000–EFFF bölümünü RAM'e yazar ve geri okuyup doğrular.
    py -3 ardu_cli.py peek ADRES [N] --port COM5          bellekten N bayt okur (onaltılık)
    py -3 ardu_cli.py poke ADRES BAYT... --port COM5      belleğe yazar (onaltılık)
    py -3 ardu_cli.py reset --port COM5 [--mod serbest|iz]
    py -3 ardu_cli.py step [N] --port COM5                N tek çevrim (iz modu)
    py -3 ardu_cli.py clock N --port COM5                 N ham MCLK darbesi (faz faz)
    py -3 ardu_cli.py status --port COM5
    py -3 ardu_cli.py info --port COM5                    kimlik, durum, iz hızı tahmini

--port yerine --fake: gerçek kart yerine sahte cihaz (ta8/ardu.py FakeDevice; arkasında
MicroEmu + Bus). Sahte cihazın ROM'u: --fake-rom X.asm, verilmezse trace/load'daki programın
ROM bölümü. Hata eklemek için: --fake-db-flip ÇEVRİM:MASKE, --fake-cw-stuck BİT:0|1,
--fake-no-busack. Sahte cihaz her çalıştırmada sıfırdan kurulur (durum saklanmaz).
"""

import argparse
import sys
import time
from pathlib import Path

from ta8 import ardu, asm, microcode
from ta8.ardu import ArduError


def _assemble(path):
    try:
        source = Path(path).read_text(encoding='utf-8')
    except OSError as e:
        raise SystemExit(f'HATA: {path} okunamadı: {e}') from None
    try:
        return asm.assemble(source, filename=str(path))
    except asm.AsmError as e:
        raise SystemExit(f'HATA: {e}') from None


def _hex(text):
    """Onaltılık sayı: 8000, $8000, 0x8000."""
    t = text.strip().lstrip('$')
    if t[:2].lower() == '0x':
        t = t[2:]
    return int(t, 16)


def _fmt_row(row):
    cyc, ab, db, cw = row
    return f'{cyc:9d}  AB={ab:04X} DB={db:02X} CW={cw:06X}  {microcode.describe(cw)}'


def _ranges(segs):
    return ', '.join(f'{a:04X}–{a + len(d) - 1:04X}' for a, d in segs)


def _connect(args, rom=None):
    if args.fake:
        if args.fake_rom:
            rom = _assemble(args.fake_rom).image
        flips = {}
        for spec in args.fake_db_flip or ():
            cyc, mask = spec.split(':')
            flips[int(cyc, 0)] = int(mask, 0)
        stuck = None
        if args.fake_cw_stuck:
            bit, val = args.fake_cw_stuck.split(':')
            stuck = (int(bit, 0), int(val, 0))
        dev = ardu.FakeDevice(rom, dip=getattr(args, 'dip', 0), busack=not args.fake_no_busack,
                              db_flip=flips, cw_stuck=stuck)
        client = ardu.ArduClient(ardu.FakeTransport(dev), timeout=args.timeout)
        client.info = client.hello()
        notes = [f'DB çevrim {c}: ^{m:02X}' for c, m in flips.items()]
        if stuck:
            notes.append(f'CW bit {stuck[0]} = {stuck[1]} yapışık')
        if args.fake_no_busack:
            notes.append('BUSACK gelmiyor')
        print('Sahte cihaz (--fake): MicroEmu + Bus' + (' | eklenen hata: ' + '; '.join(notes)
                                                       if notes else ''))
        return client
    if not args.port:
        raise SystemExit('HATA: --port COMx (gerçek kart) ya da --fake (sahte cihaz) gerekli')
    client = ardu.open_serial(args.port, args.baud, timeout=args.timeout)
    h = client.info
    print(f'{args.port}: {h.ident} yazılım {h.fw}, protokol {h.proto}, '
          f'mod {ardu.MODE_NAMES.get(h.mode, h.mode)}')
    return client


def _mode(name):
    return ardu.MODE_TRACE if name == 'iz' else ardu.MODE_FREE


# ---------------------------------------------------------------------------

def cmd_trace(args):
    prog = _assemble(args.program)
    image = bytearray(prog.image)
    if args.rom:
        rom = Path(args.rom).read_bytes()[:0x8000]
        image[:len(rom)] = rom
    segs, other = ardu.ram_segments(prog)
    client = _connect(args, bytes(image[:0x8000]))
    with client:
        client.set_mode(ardu.MODE_TRACE)
        if any(region == 'ROM' for region, _, _ in other) or args.rom:
            print('ROM (0000–7FFF): flash\'taki içerik emülatördekiyle aynı olmalı '
                  f'({"--rom " + args.rom if args.rom else "programın ROM bölümü"})')
        if segs and not args.no_load:
            n = ardu.load_segments(client, segs)
            print(f'RAM: {n} bayt yüklendi ve doğrulandı ({_ranges(segs)})')
        pulses = client.reset()
        print(f'Reset: bırakıldıktan sonra {pulses} MCLK darbesinde C fazından çıktı')
        cmp = ardu.TraceCompare(image, dip=args.dip)
        sink = open(args.save, 'w', encoding='utf-8') if args.save else None
        if sink:
            sink.write(f'# Arduino izi: {args.program}\nCYC AB DB CW\n')
        state = {'next': 100_000, 't0': time.monotonic()}

        def on_rows(rows):
            if sink:
                sink.writelines(f'{c} 0x{ab:04X} 0x{db:02X} 0x{cw:06X}\n' for c, ab, db, cw in rows)
            ok = cmp.feed(rows)
            if args.cycles >= 200_000 and cmp.count >= state['next']:
                dt = time.monotonic() - state['t0']
                print(f'  ... {cmp.count} çevrim, {cmp.count / max(dt, 1e-9):.0f} çevrim/s', flush=True)
                state['next'] += 100_000
            return ok

        try:
            res = client.trace(args.cycles, on_rows=on_rows, first_index=0)
        finally:
            if sink:
                sink.close()
    rate = f', {res.done / res.seconds:.0f} çevrim/s' if res.seconds >= 0.05 else ''
    print(f'İz: {res.done} çevrim ({res.seconds:.2f} s{rate}), '
          f'bitiş: {ardu.END_TEXT.get(res.reason, res.reason)}')
    if args.save:
        print(f'{args.save}: iz kaydedildi (vectors.parse_trace ile okunur)')
    if cmp.diff is not None:
        d = cmp.diff
        print('MicroEmu ile karşılaştırma: FARK VAR')
        print(f'  ilk fark {d.message}')
        print(f'  farklı alanlar: {", ".join(d.fields)}')
        for row in d.before:
            print('  önce     ' + _fmt_row(row))
        if d.ref:
            print('  beklenen ' + _fmt_row(d.ref))
        if d.got:
            print('  gelen    ' + _fmt_row(d.got))
        sys.exit(1)
    if res.reason in (ardu.END_STALL, ardu.END_PHASE):
        print(f'MicroEmu ile karşılaştırma: {cmp.count} çevrim boyunca fark yok, ama iz '
              'beklenmedik biçimde bitti')
        sys.exit(1)
    halted = ', ikisi de HALT' if res.reason == ardu.END_HALT and cmp.emu.halted else ''
    print(f'MicroEmu ile karşılaştırma: SIFIR FARK ({cmp.count} çevrim{halted})')


def cmd_load(args):
    prog = _assemble(args.program)
    segs, other = ardu.ram_segments(prog)
    if not segs:
        raise SystemExit('HATA: programda 8000–EFFF aralığına düşen bayt yok '
                         '(RAM programı ".org $8000" ile başlamalı)')
    for region, a, n in other:
        print(f'Not: {region} bölgesindeki {n} bayt ({a:04X}–{a + n - 1:04X}) yüklenmedi')
    client = _connect(args, prog.image if args.fake else None)
    with client:
        client.set_mode(_mode(args.mod))
        t0 = time.monotonic()
        total = ardu.load_segments(client, segs, verify=not args.no_verify)
        dt = time.monotonic() - t0
        print(f'RAM: {total} bayt yüklendi'
              + ('' if args.no_verify else ' ve geri okunup doğrulandı')
              + f' ({_ranges(segs)}, {dt:.2f} s)')
        side = client.take_side_rows()
        if side:
            print(f'Not: iz modunda bus el sıkışması sırasında {len(side)} çevrim çalıştı')
        if args.reset:
            client.reset()
            print('Makine resetlendi. Programın 8000\'den başlaması için SW0 = 1 olmalı '
                  '(açılış ROM\'u SW0\'ı okuyup 8000\'e atlar).')


def cmd_peek(args):
    addr, n = _hex(args.addr), args.n
    with _connect(args) as client:
        data = client.read(addr, n)
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'{(addr + off) & 0xFFFF:04X}  {chunk.hex(" "):<47}  {text}')


def cmd_poke(args):
    addr = _hex(args.addr)
    data = bytes(_hex(b) & 0xFF for b in args.data)
    with _connect(args) as client:
        client.write(addr, data, verify=not args.no_verify)
    print(f'{addr:04X}: {len(data)} bayt yazıldı' + ('' if args.no_verify else ' ve doğrulandı'))


def cmd_reset(args):
    with _connect(args) as client:
        client.set_mode(_mode(args.mod))
        pulses = client.reset()
        st = client.status()
    print(f'Reset ({args.mod} mod): tamam; ' + (f'{pulses} MCLK darbesinde C\'den çıktı, '
                                                if args.mod == 'iz' else '')
          + ardu.describe_pins(st.pins))


def cmd_step(args):
    with _connect(args) as client:
        client.set_mode(ardu.MODE_TRACE)
        for _ in range(args.n):
            s = client.step()
            if s.reason == ardu.END_STALL:
                print(f'Durdu: {ardu.END_TEXT[s.reason]} [{ardu.describe_pins(s.pins)}]')
                break
            print(_fmt_row((s.cycle, s.ab, s.db, s.cw)))
            if s.reason != ardu.END_OK:
                print(f'Uyarı: {ardu.END_TEXT[s.reason]}')
                break


def cmd_clock(args):
    with _connect(args) as client:
        client.set_mode(ardu.MODE_TRACE)
        pins, cycle = client.clock(args.n)
        for row in client.take_side_rows():
            print('commit ' + _fmt_row(row))
    print(f'{args.n} MCLK darbesi; {ardu.describe_pins(pins)}; çevrim sayacı {cycle}')


def cmd_status(args):
    with _connect(args) as client:
        st = client.status()
    _print_status(st)


def _print_status(st):
    print(f'Mod: {ardu.MODE_NAMES.get(st.mode, st.mode)} | {ardu.describe_pins(st.pins)} | '
          f'çevrim sayacı {st.cycle} | bus tutuluyor: {"evet" if st.bus_hold else "hayır"}')
    print(f'Pinlerde: AB={st.ab:04X} DB={st.db:02X} CW={st.cw:06X}  {microcode.describe(st.cw)}')
    print(f'Gelen çerçeve hataları: CRC/uzunluk {st.rx_errors}, yarıda kesilen {st.rx_timeouts}')


def cmd_info(args):
    with _connect(args) as client:
        h = client.info
        st = client.status()
    print(f'Kimlik: {h.ident}, yazılım {h.fw}, protokol {h.proto}, en büyük yük {h.max_payload}, '
          f'blok {h.max_block}, çerçeve başına {h.recs_per_frame} kayıt')
    _print_status(st)
    print('İz hızı (tahmin, ölçülmedi):')
    for baud in (115_200, ardu.SERIAL_BAUD):
        wire = ardu.estimate_rate(baud)
        r = min(wire, ardu.ESTIMATED_DEVICE_RATE)
        print(f'  {baud} baud: seri hat sınırı {wire:,.0f}, beklenen ~{r:,.0f} çevrim/s; '
              f'1.000.000 çevrim ≈ {1e6 / r / 60:.1f} dk')


# ---------------------------------------------------------------------------

def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    g = common.add_argument_group('bağlantı')
    g.add_argument('--port', help='seri port, ör. COM5')
    g.add_argument('--baud', type=int, default=ardu.SERIAL_BAUD,
                   help=f'(varsayılan {ardu.SERIAL_BAUD}; sketch ile aynı olmalı)')
    g.add_argument('--timeout', type=float, default=1.0, help='yanıt bekleme süresi, s')
    g.add_argument('--fake', action='store_true', help='gerçek kart yerine sahte cihaz')
    g.add_argument('--fake-rom', metavar='X.asm', help='sahte cihazın flash ROM\'undaki program')
    g.add_argument('--fake-db-flip', action='append', metavar='ÇEVRİM:MASKE',
                   help='sahte cihaz: bu çevrimin kaydında DB bitlerini ters çevir')
    g.add_argument('--fake-cw-stuck', metavar='BİT:0|1',
                   help='sahte cihaz: kontrol kelimesinin bu biti yapışık')
    g.add_argument('--fake-no-busack', action='store_true', help='sahte cihaz: BUSACK hiç gelmez')

    p = argparse.ArgumentParser(prog='ardu_cli.py',
                                description='TA-8 Arduino iz ve yükleme aracı (donanımda denenmedi)')
    sub = p.add_subparsers(dest='cmd', required=True)

    t = sub.add_parser('trace', parents=[common], help='iz al, MicroEmu ile karşılaştır')
    t.add_argument('program')
    t.add_argument('--cycles', type=int, default=1_000_000, help='en fazla çevrim (HALT\'ta biter)')
    t.add_argument('--dip', type=_hex, default=0, help='makinedeki DIP anahtarları (KSTAT b5..b0)')
    t.add_argument('--rom', help='flash\'taki ROM imajı (.bin); verilmezse programın ROM bölümü')
    t.add_argument('--no-load', action='store_true', help='RAM bölümünü yükleme')
    t.add_argument('--save', metavar='DOSYA', help='alınan izi metin tablo olarak kaydet')
    t.set_defaults(func=cmd_trace)

    lo = sub.add_parser('load', parents=[common], help='RAM\'e yükle ve doğrula')
    lo.add_argument('program')
    lo.add_argument('--no-verify', action='store_true')
    lo.add_argument('--reset', action='store_true', help='yükledikten sonra makineyi resetle')
    lo.add_argument('--mod', choices=['serbest', 'iz'], default='serbest',
                    help='serbest: makine kendi saatinde (I0); iz: Arduino saatinde (I3)')
    lo.set_defaults(func=cmd_load)

    pk = sub.add_parser('peek', parents=[common], help='bellek oku')
    pk.add_argument('addr', help='onaltılık adres')
    pk.add_argument('n', nargs='?', type=int, default=16)
    pk.set_defaults(func=cmd_peek)

    po = sub.add_parser('poke', parents=[common], help='belleğe yaz')
    po.add_argument('addr', help='onaltılık adres')
    po.add_argument('data', nargs='+', help='onaltılık baytlar')
    po.add_argument('--no-verify', action='store_true', help='geri okuma (VRAM/I/O için)')
    po.set_defaults(func=cmd_poke)

    r = sub.add_parser('reset', parents=[common], help='makineyi resetle')
    r.add_argument('--mod', choices=['serbest', 'iz'], default='serbest')
    r.set_defaults(func=cmd_reset)

    s = sub.add_parser('step', parents=[common], help='tek çevrim adımla (iz modu)')
    s.add_argument('n', nargs='?', type=int, default=1)
    s.set_defaults(func=cmd_step)

    c = sub.add_parser('clock', parents=[common], help='ham MCLK darbeleri (iz modu)')
    c.add_argument('n', type=int)
    c.set_defaults(func=cmd_clock)

    sub.add_parser('status', parents=[common], help='durum').set_defaults(func=cmd_status)
    sub.add_parser('info', parents=[common], help='kimlik ve durum').set_defaults(func=cmd_info)

    args = p.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    try:
        args.func(args)
    except ArduError as e:
        raise SystemExit(f'HATA: {e}') from None


if __name__ == '__main__':
    main()
