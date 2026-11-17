"""TD-8 işlemcisinin çip seviyesindeki netlist'i (td8.hw.cpu) → Digital (SISTEM-PLANI 12.2–12.3).

    files = export_cpu('sim/digital', program=prog.image, program_tag='merhaba')
        → m1_saat.dig m2_kontrol.dig m3_adres.dig m4_alu.dig aux_kapilar.dig m5_bellek.dig
          tb_taklitler.dig td8.dig + bellek alt devreleri (TD8_SST39SF010_*.dig, TD8_CY62256.dig)
    run = digital_trace('sim/digital/td8.dig', cycles=1000)
        → Digital'de reset + koşu; her CLK↑'de (commit) (çevrim, AB, DB, CW) — harness.HwCpu.trace
          ve MicroEmu.trace ile aynı anlam; vectors.compare_traces ile karşılaştırılır.

td8.dig'in dış bağlantıları:
  girişler  RESET_n (/RESET, 1), GO_BTN, STEPMODE, MICRO, DIP (6 bit), VWR_s (1), KRDY, KSR (8 bit),
            BP (16 bit, breakpoint adresi), BP_EN_n (1), BUSREQ_n (1; gerçekte Arduino'nun
            açık-drain hattı + 10k pull-up)
  saat      MCLK (Digital Clock; CPU çevrimi = 4 MCLK periyodu)
  gözlem    AB DB CW(24 bit, latch çıkışları) CLK LCLK Q1 RESET_s_n STOP BRK BUSACK LED PC AR X
            SP ACC IR STEP Z C N V
Modül dosyalarında (dg.module_board) modül sınırındaki her net bir In ya da Out'tur; td8.dig'in
gözlem çıkışları modül dosyalarında da (o modülün sürdüğü netler) Out olur.

ROM içerikleri gömülüdür (td8.hw.digital.render, rom_mode='embed'): uROM0–2, ALU-L/H ve
program ROM'u chip.data'dan; RAM ve VRAM açılışta 0 (Sim'in power_up='zero'su ile aynı).
Digital gecikmeleri modellemez: yalnız işlev doğrulanır, zamanlama (WAIT payı vb.) değil.
"""

import tempfile
from pathlib import Path

from .. import vectors
from . import cpu
from . import digital as dg

MODULE_FILES = {'M1': 'm1_saat', 'M2': 'm2_kontrol', 'M3': 'm3_adres', 'M4': 'm4_alu',
                'AUX': 'aux_kapilar', 'M5': 'm5_bellek', 'TB': 'tb_taklitler'}
ROM_TAGS = {'UROM0': 'urom0', 'UROM1': 'urom1', 'UROM2': 'urom2',
            'ALU_L': 'alu_lo', 'ALU_H': 'alu_hi'}
TRACE_SIGNALS = ['AB', 'DB', 'CW', 'RESET_s_n', 'LED']
RESET_MCLK = 6                                   # harness.HwCpu.power_on ile aynı
GUI_MCLK_HZ = 2000                               # GUI'de gerçek zamanlı MCLK (CPU 500 çevrim/sn)


def _bus(label, prefix, n, default=0):
    return dg.Port(label, cpu.nets(prefix, n), default)


INPUTS = [dg.Port('RESET_n', '/RESET', 1), dg.Port('GO_BTN', 'GO_BTN'),
          dg.Port('STEPMODE', 'STEPMODE'), dg.Port('MICRO', 'MICRO'), _bus('DIP', 'DIP', 6),
          dg.Port('VWR_s', 'VWR_s', 1), dg.Port('KRDY', 'KRDY'), _bus('KSR', 'KSR', 8),
          _bus('BP', 'BP', 16), dg.Port('BP_EN_n', '/BP_EN', 1)]
# Arduino'nun açık-drain hatları: Sim'de yalnız pull-up (Board.pulls), Digital'de varsayılanı
# pull değeri olan bir In (GUI'de elle ve digital_trace(sets=...) ile sürülebilsin diye).
ARD_INPUTS = [dg.Port('BUSREQ_n', '/BUSREQ', 1)]

OUTPUTS = [_bus('AB', 'AB', 16), _bus('DB', 'DB', 8), dg.Port('CW', cpu.CW_L),
           dg.Port('CLK', 'CLK'), dg.Port('LCLK', 'LCLK'), dg.Port('Q1', 'Q1'),
           dg.Port('RESET_s_n', '/RESET_s'), dg.Port('STOP', 'STOP'), dg.Port('BRK', 'BRK_L'),
           dg.Port('BUSACK', 'BUSACK'), _bus('LED', 'LED', 8),
           _bus('PC', 'PC', 16), _bus('AR', 'AR', 16), _bus('X', 'X', 16), _bus('SP', 'SP', 8),
           _bus('ACC', 'ACC', 8), _bus('IR', 'IR', 8), _bus('STEP', 'STEP', 4),
           dg.Port('Z', 'Z'), dg.Port('C', 'C'), dg.Port('N', 'N'), dg.Port('V', 'V')]


def td8_board(program=b'', program_tag='program', name='td8', **build_kw):
    """cpu.build(...) → (td8.hw.digital.Board, cpu.Board)."""
    cb = cpu.build(program=program, **build_kw)
    covered = {n for p in INPUTS for n in p.nets}
    if covered != set(cb.inputs):
        raise dg.DigitalError(f'cpu.Board.inputs değişmiş: {sorted(set(cb.inputs) ^ covered)}')
    if set(cb.clocks) != {'MCLK'}:
        raise dg.DigitalError(f'beklenmeyen saatler: {cb.clocks}')
    inputs = [dg.Port(p.label, p.nets, cb.inputs[p.nets[0]] if p.bits == 1 else p.default)
              for p in INPUTS]
    inputs += [dg.Port(p.label, p.nets, cb.pulls[p.nets[0]]) for p in ARD_INPUTS]
    pulls = {**cb.pulls, **cb.ties}                # tie = 5. haftaya kalan sürücünün pasif değeri
    rom_files = {chip.ref: Path(f'{ROM_TAGS[k]}.hex') for k, chip in cb.memories.items()
                 if k in ROM_TAGS}
    rom_files[cb.memories['ROM'].ref] = Path(f'prog_{dg.safe_name(program_tag)}.hex')
    title = ('TD-8 işlemci: çip seviyesinde netlist (td8.hw.cpu, ' f'{len(cb.chips)} çip; '
             f'program: {program_tag})')
    board = dg.Board(name, cb.chips, pulls, inputs, [dg.Port(p.label, p.nets) for p in OUTPUTS],
                     'MCLK', rom_files, title, clock_hz=GUI_MCLK_HZ)
    return board, cb


def export_cpu(out_dir, program=b'', program_tag='program', modules=True, tests=None,
               **build_kw):
    """Modül dosyalarını ve td8.dig'i yazar; yazılan yolları döndürür.

    tests: {dosya adı (uzantısız): Testcase metni}. Her modül dosyası kendi Board'undan
    (dg.module_board) üretilir; çip nesneleri her dosya için yeniden kurulur.
    """
    out_dir = Path(out_dir)
    tests = tests or {}
    written = []
    if modules:
        for mod, fname in MODULE_FILES.items():
            board, _ = td8_board(program, program_tag, **build_kw)
            mb = dg.module_board(board, mod, fname, cpu.MODULE_TITLES.get(mod, mod))
            written += dg.export(mb, out_dir / f'{fname}.dig', tests.get(fname))
    board, _ = td8_board(program, program_tag, **build_kw)
    written += dg.export(board, out_dir / f'{board.name}.dig', tests.get(board.name))
    return list(dict.fromkeys(written))


def module_board(module, program=b'', **build_kw):
    """Tek modülün Board'u (td8.dig'in modül dosyasıyla aynı portlar)."""
    board, _ = td8_board(program, **build_kw)
    return dg.module_board(board, module, MODULE_FILES[module], cpu.MODULE_TITLES.get(module))


class DigitalRun:
    """digital_trace sonucu: trace [(çevrim, AB, DB, CW)], leds/ram/vram (son durum),
    leds0/ram0/vram0 (reset bırakılırken), step (StepRun)."""

    def __init__(self, trace, leds, ram, vram, leds0, ram0, vram0, step):
        self.trace, self.leds, self.ram, self.vram, self.step = trace, leds, ram, vram, step
        self.leds0, self.ram0, self.vram0 = leds0, ram0, vram0

    @property
    def halted(self):
        from .. import isa
        return bool(self.trace) and bool(self.trace[-1][3] & isa.HALT)


def digital_trace(dig, cycles, setup=None, reset_mclk=RESET_MCLK, extra_mclk=64, sets=None):
    """td8.dig'i Digital'de çalıştırır: RESET_n reset_mclk MCLK periyodu 0, sonra 1; toplam
    4·cycles + reset_mclk + extra_mclk MCLK periyodu. Her CLK↑'den hemen önceki AB, DB, CW
    kaydedilir (/RESET_s = 1 olanlar; harness ile aynı). HALT'tan sonra makine C'de durduğu için
    iz kendiliğinden biter. RAM (8000–EFFF) ve VRAM içerikleri reset bırakılırken ve koşu
    sonunda dökülür.

    Açılış: Digital modeli ilk kurarken (reset basılıyken) bütün çipler aynı anda değerlendirilir
    ve kod çözücüler oturana kadar SRAM/VRAM'e ya da LED latch'ine sahte bir yazma olabilir
    (harness'te 'acilis' sınıfı; Digital'de ilk yayılımın sırası koşudan koşuya değiştiği için
    yalnız bazı koşularda). Gerçekte de açılış içeriği belirsizdir; bu yüzden karşılaştırma reset
    bırakılırken alınan içerikle başlatılan emülatörle yapılır (harness.emu_like gibi)."""
    with tempfile.TemporaryDirectory(prefix='td8iz_') as d:
        d = Path(d)
        st = dg.run_stepper(dig, 4 * cycles + reset_mclk + extra_mclk, clock='MCLK',
                            trigger='CLK', signals=TRACE_SIGNALS, setup=setup, end_row=True,
                            sets=[('RESET_n', 0, 0), ('RESET_n', 1, reset_mclk)] + list(sets or ()),
                            dumps=[('U602', d / 'ram0.bin', reset_mclk), ('X1', d / 'vram0.bin', reset_mclk),
                                   ('U602', d / 'ram.bin', None), ('X1', d / 'vram.bin', None)])
        ram = (d / 'ram.bin').read_bytes()[:0x7000]
        vram = (d / 'vram.bin').read_bytes()[:0x800]
        ram0 = (d / 'ram0.bin').read_bytes()[:0x7000]
        vram0 = (d / 'vram0.bin').read_bytes()[:0x800]
    rows = st.as_dicts()
    end = rows.pop()                                       # CYC = -1: son durum
    trace, leds0 = [], None
    for r in rows:
        if r['RESET_s_n'] == 1:
            if leds0 is None:
                leds0 = r['LED']                           # ilk commit'ten önce: açılış değeri
            trace.append((len(trace), r['AB'], r['DB'], r['CW']))
    return DigitalRun(trace[:cycles] if len(trace) > cycles else trace, end['LED'], ram, vram,
                      leds0, ram0, vram0, st)


def emu_reference(image, cycles, run=None):
    """Aynı programın MicroEmu izi ve son durumu (klavye yok, DIP = 0, VRAM penceresi açık).
    run (DigitalRun) verilirse RAM, VRAM ve LED reset bırakılırkenki Digital içeriğiyle
    başlar, yoksa 0. Döner: MicroEmu."""
    from ..bus import Bus
    from ..emu_micro import MicroEmu
    bus = Bus()
    bus.load(bytes(image[:0x8000]))
    if run is not None:
        bus.mem[0x8000:0xF000] = run.ram0
        bus.vram[:] = run.vram0
        bus.leds = run.leds0 or 0
    emu = MicroEmu(bus, cpu.default_urom(), cpu.default_alu())
    emu.trace = []
    emu.run(cycles)
    return emu


def compare_run(run, emu):
    """Farklar listesi (boş = sıfır fark): iz, LED, RAM, VRAM."""
    out = []
    i, msg = vectors.compare_traces(emu.trace, run.trace)
    if i is not None:
        out.append(f'iz: {msg}')
    if run.halted and emu.halted:
        if run.leds != emu.bus.leds:
            out.append(f'LED: emu {emu.bus.leds:02X}, Digital {run.leds}')
        eram = bytes(emu.bus.mem[0x8000:0xF000])
        if run.ram != eram:
            bad = [a for a in range(len(eram)) if run.ram[a] != eram[a]]
            out.append(f'RAM {len(bad)} bayt farklı, ilk {0x8000 + bad[0]:04X}')
        if run.vram != bytes(emu.bus.vram):
            out.append('VRAM farklı')
    else:
        out.append(f'HALT: emu {emu.halted}, Digital {run.halted}')
    return out
