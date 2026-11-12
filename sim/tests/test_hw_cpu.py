"""Çip seviyesindeki TD-8 netlist'i (td8.hw.cpu) ile MicroEmu'nun çevrim çevrim karşılaştırması.

K2 kilometre taşının yazılım tarafı: bütün CPU, gecikmeli simülatörde, emülatörle sıfır fark.

Çalıştırma (sim/ klasöründen):
    py -3 -m unittest tests.test_hw_cpu -v
    TD8_SLOW=1 py -3 -m unittest tests.test_hw_cpu -v     fibonacci max köşe ve 1.5 MHz de

Sınıflar: 1 sıfır fark (merhaba, komut_testi, __mul16/__divmod16; typ ve max), 2 fibonacci,
3 açılış/reset, 4 SP sınırları, 5 HALT/GO ve adımlama, 6 WAIT, 7 ihlaller, 8 entegre sayımı,
ayrıca 1.5 / 2 MHz denemesi ve klavye okuma yolu.
"""

import os
import unittest
from functools import lru_cache
from pathlib import Path

from td8 import asm, isa
from td8.hw import cpu, wiring
from td8.hw.harness import (HwCpu, classify_violations, compare, emu_like, emu_state,
                            emu_vram_writes, handover_summary, run_and_compare)

EXAMPLES = Path(__file__).resolve().parent.parent / 'examples'
SLOW = os.environ.get('TD8_SLOW') == '1'

MULDIV = """
        .org 0
        LDA #<1234          ; 1234 * 56 (çarpan < 256)
        STA __mul_a
        LDA #>1234
        STA __mul_a+1
        LDA #56
        STA __mul_b
        LDA #0
        STA __mul_b+1
        CALL __mul16
        LDA __rv
        STA $8100
        LDA __rv+1
        STA $8101
        LDA #$34            ; 1234h * 0567h (mod 65536)
        STA __mul_a
        LDA #$12
        STA __mul_a+1
        LDA #$67
        STA __mul_b
        LDA #$05
        STA __mul_b+1
        CALL __mul16
        LDA __rv
        STA $8102
        LDA __rv+1
        STA $8103
        LDA #<54321         ; 54321 / 123 = 441 kalan 78
        STA __div_n
        LDA #>54321
        STA __div_n+1
        LDA #123
        STA __div_d
        LDA #0
        STA __div_d+1
        CALL __divmod16
        HALT
        .include "../lib/runtime.asm"
"""

SP_TEST = """
        .org 0
        PLA                 ; SP FF -> 00 (pop, üst 191 F->0), EF00 okunur
        STA $8000
        PHA                 ; SP 00 -> FF (push, alt ve üst 191 0->F)
        LDA #0
itme:   PHA                 ; 256 push: FF..00 ve tekrar FF (bütün x0 -> (x-1)F geçişleri)
        INC
        BNE itme
        LDA #0
        STA $8001
        STA $8002
cekme:  PLA                 ; 256 pop: FF -> 00 -> ... -> FF (bütün xF -> (x+1)0 geçişleri)
        ADD $8001
        STA $8001
        LDA $8002
        INC
        STA $8002
        BNE cekme
        HALT
"""

HALT_GO = """
        .org 0
        LDA #$11
        STA $8000
        HALT
        LDA #$22
        STA $8001
        CALL alt
        HALT
        LDA #$33
        STA $F800
        HALT
alt:    INC
        STA $8002
        RET
"""

NO_WAIT = """
        .org 0
        LDA #$12
        STA $8000           ; RAM: beklemez
        STA $EFFF           ; RAM (stack sayfası): beklemez
        STA $F800           ; LED (I/O, A11 = 1): beklemez
        STA $FFFF           ; I/O aynası: beklemez
        LDX #$F7FF
        LDA #'K'
        STA $F005           ; VRAM: pencere açılana kadar D'de bekler
        STA (X)             ; VRAM son hücre
        HALT
"""


@lru_cache(maxsize=None)
def program(name):
    if name == 'muldiv':
        return asm.assemble(MULDIV, str(EXAMPLES / '_muldiv.asm'))
    src = {'sp': SP_TEST, 'haltgo': HALT_GO, 'nowait': NO_WAIT}.get(name)
    if src is not None:
        return asm.assemble(src)
    path = EXAMPLES / f'{name}.asm'
    return asm.assemble(path.read_text(encoding='utf-8'), str(path))


@lru_cache(maxsize=None)
def zero_diff_run(name, corner, mhz=4):
    """(hw, emu, farklar, saniye); aynı koşu ihlal testinde de kullanılır."""
    return run_and_compare(program(name).image, 200_000, corner=corner, mclk_mhz=mhz)


def window_pattern(hw, open_ns, closed_ns, count, start_closed=True):
    """VWR_s: kapalı/açık pencere dizisi. Değişimler MCLK düşen kenarlarına hizalı (yükselen
    kenardan yarım MCLK önce), böylece VWR_s → /WAIT yolu karar kenarına yetişir ve
    'pencere kapalıyken yazma' denetimi kesin olur."""
    p = 2 * hw.half
    t = 0
    for _ in range(count):
        if start_closed:
            t += closed_ns
            hw.set('VWR_s', 1, at=t // p * p)
            t += open_ns
            hw.set('VWR_s', 0, at=t // p * p)


@lru_cache(maxsize=None)
def windowed_run(corner, wait_fix=True, mhz=4):
    """merhaba.asm, VRAM penceresi 17 µs kapalı / 3 µs açık; (hw, emu)."""
    prog = program('merhaba')
    hw = HwCpu(prog.image, corner=corner, vwr=0, wait_fix=wait_fix, mclk_mhz=mhz)
    window_pattern(hw, open_ns=3000, closed_ns=17000, count=80)
    hw.run(5000)
    return hw, emu_like(hw, prog.image, 5000)


class HwCase(unittest.TestCase):
    def assertZeroDiff(self, diffs, what):
        self.assertEqual(diffs, [], f'{what}: {diffs}')


# ============================================================================
# 1. Sıfır fark
# ============================================================================
class TestZeroDiff(HwCase):
    def check(self, name, corner):
        hw, emu, diffs, dt = zero_diff_run(name, corner)
        self.assertTrue(hw.halted and emu.halted, f'{name} {corner}: HALT yok')
        self.assertEqual(len(hw.trace), len(emu.trace))
        self.assertZeroDiff(diffs, f'{name} {corner}')
        return hw, emu

    def test_merhaba(self):
        for corner in ('typ', 'max'):
            hw, emu = self.check('merhaba', corner)
            self.assertEqual(len(hw.trace), 573)
            self.assertEqual(hw.leds(), 0x55)
            self.assertEqual(hw.vram()[64 + 2:64 + 16], b'MERHABA, TD-8!')

    def test_komut_testi(self):
        for corner in ('typ', 'max'):
            hw, emu = self.check('komut_testi', corner)
            self.assertEqual(hw.leds(), 0xA5, 'komut_testi kendi denetiminde hata buldu')
            self.assertEqual(hw.state()['sp'], 0xFF)

    def test_komut_testi_kapsami(self):
        """88 opcode'un hepsi çalışıyor; 14 dallanmanın her biri hem alınıyor hem alınmıyor."""
        _, emu, _, _ = zero_diff_run('komut_testi', 'typ')
        fetch, op1 = isa.step(isa.FETCH).word(), isa.step(isa.OP1).word()
        ops, taken = set(), {}
        tr = emu.trace
        for i, (_, _, db, cw) in enumerate(tr):
            if cw == fetch:
                ops.add(db)
                if 0xB0 <= db <= 0xBD:
                    taken.setdefault(db, set()).add(tr[i + 1][3] == op1)
        self.assertEqual(ops, set(isa.INSTRUCTIONS), 'çalışmayan opcode var')
        self.assertEqual(len(ops), 88)
        for op in range(0xB0, 0xBE):
            self.assertEqual(taken.get(op), {True, False}, f'{op:02X}')

    def test_runtime_mul_div(self):
        for corner in ('typ', 'max'):
            hw, emu = self.check('muldiv', corner)
            ram = hw.ram()
            self.assertEqual(ram[0x100] | ram[0x101] << 8, 1234 * 56 & 0xFFFF)
            self.assertEqual(ram[0x102] | ram[0x103] << 8, 0x1234 * 0x0567 & 0xFFFF)
            self.assertEqual(ram[0] | ram[1] << 8, 441)               # __rv
            self.assertEqual(ram[0x0A] | ram[0x0B] << 8, 78)          # __div_r

    def test_klavye(self):
        """KBD/KSTAT okuma yolu: klavye.asm, 3 scan code (bus.py zamanlaması)."""
        keys = (0x1C, 0xF0, 0x1C)
        prog = program('klavye')
        hw = HwCpu(prog.image, keys=keys)
        hw.run(4200)
        emu = emu_like(hw, prog.image, hw.n, keys)
        self.assertZeroDiff(compare(hw, emu), 'klavye')
        self.assertEqual(hw.vram(), bytes(emu.bus.vram))
        self.assertEqual(hw.vram()[:9], b'1C F0 1C ')


# ============================================================================
# 2. Uzun koşu: fibonacci (~33 bin çevrim)
# ============================================================================
class TestFibonacci(HwCase):
    def test_fibonacci(self):
        for corner in (('typ', 'max') if SLOW else ('typ',)):
            hw, emu, diffs, dt = zero_diff_run('fibonacci', corner)
            self.assertTrue(hw.halted)
            self.assertGreater(len(hw.trace), 33_000)
            self.assertZeroDiff(diffs, f'fibonacci {corner}')
            self.assertEqual(classify_violations(hw)['diger'], [])


# ============================================================================
# 3. Açılış ve reset
# ============================================================================
class TestPowerUpReset(HwCase):
    def test_random_power_up(self):
        """Rastgele başlangıç (FF'ler, registerlar, SRAM): reset sonrası iz aynı."""
        ref = zero_diff_run('merhaba', 'typ')[0].trace
        prog = program('merhaba')
        for seed in (1, 2, 3, 4):
            hw = HwCpu(prog.image, power_up='random', seed=seed)
            hw.run(2000)
            self.assertEqual(hw.trace, ref, f'tohum {seed}')
            emu = emu_like(hw, prog.image, 2000)
            self.assertZeroDiff(compare(hw, emu), f'tohum {seed}')
            self.assertEqual(classify_violations(hw)['diger'], [], f'tohum {seed}')

    def test_reset_while_running(self):
        """Çalışırken reset (puts'un içinde, SP = FD), dört fazın her birinde: asenkron kurma
        Johnson'u C'ye atar (A/B'de erken bir CLK kenarı olur); bırakınca 0000'dan yeniden
        başlar, SP = FF, iz MicroEmu'nun baştan iziyle aynı."""
        prog = program('merhaba')
        phases = set()
        for k in (0, 1, 3, 5):                            # B, C, D, A
            hw = HwCpu(prog.image)
            hw.run(300)
            self.assertEqual(hw.state()['sp'], 0xFD)      # CALL puts'tan sonra
            hw.sim.run_for(k * hw.half + 60)
            phases.add(hw.phase())
            t_reset = hw.sim.now
            hw.reset(hold_mclk=4)
            mark = hw.reset_marks[-1]
            hw.sim.run_for(2 * hw.half)                   # bırakma senkronlanırken (C'de)
            st = hw.state()
            self.assertEqual((st['pc'], st['sp'], st['step'], st['ar'], st['x']),
                             (0, 0xFF, 0, 0, 0))
            self.assertEqual(hw.phase(), 'C')
            hw.run(5000)
            emu = emu_like(hw, prog.image, 5000)
            self.assertZeroDiff(compare(hw, emu, trace_from=mark), f'reset sonrası (k={k})')
            self.assertEqual(classify_violations(hw)['diger'], [], f'k={k}, t={t_reset}')
        self.assertEqual(phases, {'A', 'B', 'C', 'D'})


# ============================================================================
# 4. SP sınırları (74HC191 ×2, DOGRULAMA 3.6)
# ============================================================================
class TestStackPointer(HwCase):
    def test_sp_boundaries(self):
        hw, emu, diffs, _ = run_and_compare(program('sp').image, 20_000)
        self.assertTrue(hw.halted)
        self.assertZeroDiff(diffs, 'SP sınırları')
        self.assertEqual(hw.state()['sp'], 0xFF)
        # her push adımının adresi EF:SP; 256 push + 256 pop'ta SP'nin bütün değerleri görüldü
        push = [ab & 0xFF for _, ab, _, cw in hw.trace if cw & isa.SPCNT and cw & isa.SPDN]
        self.assertEqual(set(push), set(range(256)))
        ram = hw.ram()
        self.assertEqual(ram[0x6F00:0x7000], bytes(0xFF - a for a in range(256)))  # EF00..EFFF
        self.assertEqual(ram[1], sum(range(256)) & 0xFF)            # pop sağlaması
        self.assertEqual(classify_violations(hw)['diger'], [])


# ============================================================================
# 5. HALT, GO ve adımlama
# ============================================================================
class TestHaltGoStep(HwCase):
    def test_halt_and_go(self):
        prog = program('haltgo')
        hw = HwCpu(prog.image)
        hw.run(1000)
        emu = emu_like(hw, prog.image, 1000)               # ilk HALT'a kadar
        self.assertTrue(hw.halted)
        hw.sim.run_for(10 * hw.cycle_ns)                   # durmuş kalıyor mu
        self.assertEqual(hw.phase(), 'C')
        self.assertEqual(hw.sim.get('STOP'), 1)
        self.assertEqual(len(hw.trace), len(emu.trace))
        for k in range(2):                                 # GO → bir sonraki HALT'a kadar
            e0 = len(emu.trace)
            n = hw.go(max_cycles=200)
            emu.halted = False
            emu.run(1000)
            self.assertEqual(n, len(emu.trace) - e0, f'GO {k}')
            self.assertTrue(hw.halted, f'GO {k}')
            self.assertEqual(hw.phase(), 'C')
        self.assertZeroDiff(compare(hw, emu), 'HALT/GO')
        self.assertEqual(hw.leds(), 0x33)

    def test_micro_step(self):
        """STEPMODE = 1, MICRO = 1: her GO tam bir çevrim."""
        prog = program('komut_testi')
        hw = HwCpu(prog.image, stepmode=1, micro=1)
        hw.power_on()
        hw.sim.run_for(20 * hw.cycle_ns)
        self.assertEqual(hw.n, 0, 'adım kipinde GO beklemeden çalıştı')
        self.assertEqual(hw.phase(), 'C')
        for k in range(60):
            self.assertEqual(hw.go(), 1, f'GO {k}')
        emu = emu_like(hw, prog.image, 60)
        self.assertZeroDiff(compare(hw, emu), 'mikroadım')

    def test_instruction_step(self):
        """STEPMODE = 1, MICRO = 0: her GO tam bir komut (FETCH dahil).

        Not: reset sonrası latch'te NOP kelimesi var (NEXT_L = 0), STOP = 0; bu yüzden
        ilk komut GO beklemeden çalışır ve ilk NEXT'te durulur."""
        prog = program('komut_testi')
        hw = HwCpu(prog.image, stepmode=1, micro=0)
        hw.power_on()
        hw.sim.run_for(20 * hw.cycle_ns)
        emu = emu_like(hw, prog.image, 0)
        lengths = [emu.instruction()]
        self.assertEqual(hw.n, lengths[0])
        for k in range(110):                               # INCW/DECW'ye kadar
            n = hw.go()
            lengths.append(emu.instruction())
            self.assertEqual(n, lengths[-1], f'komut {k}')
        self.assertTrue({2, 3, 4, 7} <= set(lengths), set(lengths))   # farklı uzunluklar
        self.assertZeroDiff(compare(hw, emu), 'komut adımlama')


# ============================================================================
# 6. WAIT (VRAM penceresi)
# ============================================================================
class TestWait(HwCase):
    def test_wait_holds_and_writes_once(self):
        for corner in ('typ', 'max'):
            hw, emu = windowed_run(corner)
            self.assertZeroDiff(compare(hw, emu), f'WAIT {corner}')
            self.assertGreater(hw.stall_ns, 0, f'{corner}: hiç beklemedi')
            self.assertEqual(hw.wait_errors, [], f'{corner}: pencere kapalıyken yazma')
            self.assertEqual([(a, d) for a, d, _ in hw.vram_writes], emu_vram_writes(emu))
            self.assertEqual(hw.vram()[64 + 2:64 + 16], b'MERHABA, TD-8!')
            self.assertEqual(classify_violations(hw)['diger'], [], corner)

    def test_plan_version_misses_wait_at_max(self):
        """PLAN DÜZELTMESİ'nin kanıtı: planın yazdığı WAIT kapısı (138 G1 = VCC, Johnson'da
        OR(/WAIT, /Q2)) max köşede 1 MHz'de kararı geç verir; pencere kapalıyken yazar.
        Tipik köşede çalışır."""
        hw, _ = windowed_run('typ', wait_fix=False)
        self.assertEqual(hw.wait_errors, [])
        self.assertGreater(hw.stall_ns, 0)
        hw, _ = windowed_run('max', wait_fix=False)
        self.assertGreater(len(hw.wait_errors), 0)
        self.assertEqual(hw.stall_ns, 0)

    def test_non_vram_writes_do_not_wait(self):
        prog = program('nowait')
        hw = HwCpu(prog.image, vwr=0)
        t_open = 60_000
        hw.set('VWR_s', 1, at=t_open)
        commit_t = []
        hw.sim.watch('CLK', lambda t, v: v == 1 and hw.sim.get('/RESET_s') == 1
                     and commit_t.append(t))
        hw.run(200)
        emu = emu_like(hw, prog.image, 200)
        self.assertZeroDiff(compare(hw, emu), 'WAIT dışı yazmalar')
        first_vram = next(i for i, (_, ab, _, cw) in enumerate(hw.trace)
                          if cw & isa.MEMW and 0xF000 <= ab < 0xF800)
        steps = [b - a for a, b in zip(commit_t, commit_t[1:first_vram + 1])]
        self.assertEqual(set(steps[:-1]), {hw.cycle_ns}, 'VRAM dışı bir yazma bekledi')
        self.assertGreater(commit_t[first_vram], t_open)   # VRAM yazması pencereyi bekledi
        self.assertEqual(len(hw.vram_writes), 2)
        self.assertTrue(all(t > t_open for _, _, t in hw.vram_writes))
        self.assertEqual(hw.vram()[5], ord('K'))
        self.assertEqual(hw.vram()[0x7FF], ord('K'))
        self.assertEqual(hw.leds(), 0x12)


# ============================================================================
# 7. İhlaller
# ============================================================================
class TestViolations(HwCase):
    def test_no_unexplained_violations(self):
        """Sıfır fark koşularında 'diger' sınıfı boş. Kalanlar: açılış (reset basılıyken) ve
        C→D'de DB devir-teslim örtüşmesi (DOGRULAMA 3.5): yalnız DB'de, yarım fazdan kısa."""
        for name in ('merhaba', 'komut_testi', 'muldiv'):
            for corner in ('typ', 'max'):
                hw = zero_diff_run(name, corner)[0]
                cl = classify_violations(hw)
                self.assertEqual(cl['diger'], [], f'{name} {corner}: {cl["diger"][:3]}')
                hs = handover_summary(cl['devir_teslim'])
                self.assertTrue(all(m < hw.half for _, m in hs.values()), hs)
                for ref in hs:                             # eski kaynak bellek ya da I/O
                    self.assertTrue(any(r in ref for r in ('U601', 'U602', 'U606', 'X2')), ref)

    def test_timing_paths_1mhz(self):
        """1 MHz'de üç kritik yol penceresine sığıyor (her iki köşede)."""
        for corner in ('typ', 'max'):
            tr = zero_diff_run('komut_testi', corner)[0].timing_report()
            for path in ('yol1', 'yol2'):
                settle, _, window, _ = tr[path]
                self.assertLess(settle, window, f'{corner} {path}')
        for corner in ('typ', 'max'):
            hw, _ = windowed_run(corner)
            settle, _, window, _ = hw.timing_report()['yol3_mclk']
            self.assertLess(settle + (6 if corner == 'typ' else 15), window, corner)


# ============================================================================
# 8. Entegre sayımı ve netlist yapısı
# ============================================================================
class TestNetlist(HwCase):
    def test_chip_counts_match_plan(self):
        board = cpu.build()
        rows = wiring.count_rows(board)
        self.assertEqual([r for r in rows if r[5] != 0], [])  # açıklanmamış fark yok
        counts = wiring.chip_counts(board)
        self.assertEqual({m: sum(c.values()) for m, c in counts.items()},
                         {'M1': 9, 'M2': 11, 'M3': 22, 'M4': 8, 'AUX': 3, 'M5': 6, 'toplam': 59})
        # kurulmayanlar: M1'de 5 (NE555, 153, 14, BRK/BUSACK 74, BRQ/VWR 175), M2'de 2× 688,
        # AUX'ta gereksiz kalan 2. 74HC00
        self.assertEqual(sum(n for items in wiring.NOT_BUILT.values() for _, n, _ in items), 8)
        for m, plan in wiring.PLAN_COUNTS.items():          # plan sayısını aşan parça yok
            for part, n in counts[m].items():
                self.assertLessEqual(n, plan.get(part, 0), f'{m} {part}')

    def test_refs_notes_and_modules(self):
        board = cpu.build()
        prefix = {'M1': 'U1', 'M2': 'U2', 'M3': 'U3', 'M4': 'U4', 'AUX': 'U5', 'M5': 'U6',
                  'TB': 'X'}
        for c in board.chips:
            self.assertTrue(c.ref.startswith(prefix[c.module]), c.ref)
            self.assertTrue(c.note, f'{c.ref}: not yok')
        # modül kurucuları tek tek çağrılabilir; birleşimleri build() ile aynı
        refs = []
        for m, fn in cpu.MODULES.items():
            part = fn()
            self.assertTrue(all(c.module == m for c in part.chips), m)
            refs += [c.ref for c in part.chips]
            self.assertTrue(board.ports(m), m)
        self.assertEqual(refs, [c.ref for c in board.chips])
        # sözlükteki adlar
        users = board.net_users()
        for net in ['/MRD', '/DD_A', 'ASRC0', 'ASRC0_L', 'CLK', 'LCLK', 'WSTB', '/RESET_s',
                    'STOP', '/WAIT', '/FPAGE', '/VRAMSEL', '/IOSEL', '/KBD_RD', '/STAT_RD',
                    '/RD', '/WR', '/MWR', 'R0', 'DB7', 'AB15', 'HALT_L', 'NEXT_L']:
            self.assertIn(net, users, net)

    def test_plan_fix_marked(self):
        board = cpu.build()
        self.assertIn('PLAN DÜZELTMESİ', board.chip('U108').note)
        self.assertEqual(board.chip('U108').pins['E3'], 'CLK')
        plan = cpu.build(wait_fix=False)
        self.assertEqual(plan.chip('U108').pins['E3'], 'VCC')
        self.assertEqual(plan.chip('U103').pins['3B'], 'WAIT_OR')

    def test_wiring_table(self):
        board = cpu.build()
        text = wiring.wiring_table(board)
        for c in board.chips:
            self.assertIn(f'### {c.ref} · {c.KIND}', text)
        self.assertIn('| 9 | `2Q` | `CLK` |', text)            # U101 bacak 9
        self.assertIn('PLAN DÜZELTMESİ', text)


# ============================================================================
# Hız denemesi: MCLK 6 MHz (1.5 MHz CPU) ve 8 MHz (2 MHz CPU)
# ============================================================================
class TestClockRate(HwCase):
    def test_1_5_mhz(self):
        """Plan: 1.5 MHz WAIT yolu hariç her koşulda. (WAIT kapalıyken) sıfır fark."""
        names = ('komut_testi', 'muldiv') + (('fibonacci',) if SLOW else ())
        for name in names:
            for corner in ('typ', 'max'):
                hw, emu, diffs, _ = zero_diff_run(name, corner, 6)
                self.assertZeroDiff(diffs, f'{name} 1.5 MHz {corner}')
                self.assertEqual(classify_violations(hw)['diger'], [])

    def test_1_5_mhz_wait(self):
        """WAIT yolu 1.5 MHz'de tipik değerlerle çalışır, max'ta kararı kaçırır (plan da öyle)."""
        hw, emu = windowed_run('typ', mhz=6)
        self.assertEqual(hw.wait_errors, [])
        self.assertZeroDiff(compare(hw, emu), 'WAIT 1.5 MHz typ')
        hw, emu = windowed_run('max', mhz=6)
        self.assertGreater(len(hw.wait_errors), 0)

    def test_2_mhz(self):
        """Plan: 2 MHz yalnız tipik değerlerle. typ: sıfır fark (WAIT dahil); max: uROM araması
        (yol 2, ~152 ns) 124 ns'lik C fazına sığmaz, ikinci çevrimde bozulur."""
        for name in ('komut_testi', 'muldiv'):
            hw, emu, diffs, _ = zero_diff_run(name, 'typ', 8)
            self.assertZeroDiff(diffs, f'{name} 2 MHz typ')
        hw, emu = windowed_run('typ', mhz=8)
        self.assertEqual(hw.wait_errors, [])
        self.assertZeroDiff(compare(hw, emu), 'WAIT 2 MHz typ')
        hw, emu, diffs, _ = zero_diff_run('komut_testi', 'max', 8)
        self.assertTrue(diffs and diffs[0].startswith('iz: satır 1 '), diffs)
        setup = [v for v in hw.sim.violations if v.kind == 'setup' and v.ref in ('U204', 'U205',
                                                                                  'U206')]
        self.assertTrue(setup, 'kontrol latch\'inde kurulum ihlali bekleniyordu')


if __name__ == '__main__':
    unittest.main()
