"""M6 VGA zamanlaması (SISTEM-PLANI 8.1–8.2): netlist, Digital dosyası, testler, ölçümler.

Devre artık projenin netlist'inde: sim/ta8/hw/cpu.py m6_vga() (19 Kasım). Bu dosya yalnız
Digital dosyasını, testleri, kare ölçümlerini ve gecikme analizini üretir.
Çip modelleri (ta8.hw.chips) ve Digital dışa aktarıcısı (ta8.hw.digital) projenin araçları.

Çalıştırma (depo kökünden):  py Abdurrahman/hafta5/m6_uret.py
Digital'i bulmak için TA8_DIGITAL_HOME (Digital.jar'ın üst klasörü) ayarlı olmalı.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'sim'))
from ta8 import vga                                                  # noqa: E402
from ta8.hw import cpu                                                # noqa: E402
from ta8.hw import digital as dg                                      # noqa: E402
from ta8.hw.kernel import Sim                                         # noqa: E402

NAME = 'M6_vga_zamanlama'
M = 'M6'
OSC_HALF_NS = 20                                     # 25.000 MHz
H_TOTAL, V_TOTAL = vga.H_TOTAL, vga.V_TOTAL          # 50 karakter, 525 satır
FRAME_CHARS = H_TOTAL * V_TOTAL                      # 26.250 karakter
FRAME_OSC = FRAME_CHARS * 8 * 2                      # 420.000 osilatör periyodu


def chips(dclk_ext=False):
    """M6'nın zamanlama kısmı: 11 entegre (U701–U711). Artık projenin netlist'inde:
    sim/ta8/hw/cpu.py m6_vga() (tek kaynak). dclk_ext: ÷2 FF'si boşta, DCLK dışarıdan."""
    return cpu.m6_vga(dclk_ext, timing_only=True).chips


P = lambda l, n, d=0: dg.Port(l, n, d)
OUTPUTS = [P('DOT', ['DOT0', 'DOT1', 'DOT2']), P('DCLK', 'DCLK'), P('CCLK', 'CCLK'), P('LD', 'LD'),
           P('H', dg.bus_nets('H', 6)), P('V', dg.bus_nets('V', 10)),
           P('HSYNC_n', '/HSYNC'), P('VSYNC_n', '/VSYNC'), P('BLANK_n', 'BLANK_n'),
           P('BUFEN_n', '/BUFEN'), P('VMUX', 'VMUX'), P('VWR', 'VWR'),
           P('HEND_n', '/HEND'), P('VEND_n', '/VEND')]


def board():
    return dg.Board(NAME, chips(), {}, [P('SLOW', 'SLOW')], OUTPUTS, 'OSC25',
                    {'U710': Path('vga_zamanlama.hex')},
                    'M6 VGA zamanlaması: saatler, nokta/karakter/satır sayaçları, zamanlama ROM\'u, T1 '
                    '(Abdurrahman, hafta 5)', clock_hz=1000)


SAMPLE = ['H', 'V', 'HSYNC_n', 'VSYNC_n', 'BLANK_n', 'BUFEN_n', 'VMUX', 'VWR']
NET = {'HSYNC_n': '/HSYNC', 'VSYNC_n': '/VSYNC', 'BLANK_n': 'BLANK_n', 'BUFEN_n': '/BUFEN',
       'VMUX': 'VMUX', 'VWR': 'VWR'}


def sim_frames(frames, corner='typ', power_up='zero', seed=1, slow=0, dclk_ext=False):
    """Gerçek 25 MHz saatle, gecikmeli çip modelleriyle koşu. Her CCLK düşüşünde (karakterin
    0. noktası; H, V ve T1 çıkışları o an kararlı) bir satır kaydedilir."""
    sim = Sim(corner=corner, power_up=power_up, seed=seed)
    sim.add(*chips(dclk_ext))
    sim.set('SLOW', slow)
    rows = []

    def on_cclk(t, v):
        if v == 0:
            r = {'t': t, 'H': sim.bus('H', 6), 'V': sim.bus('V', 10)}
            r.update({k: sim.get(n) for k, n in NET.items()})
            rows.append(r)

    sim.watch('CCLK', on_cclk)
    if dclk_ext:
        sim.add_clock('DCLK', 2 * OSC_HALF_NS)
    else:
        sim.add_clock('OSC25', OSC_HALF_NS)
    t0 = time.perf_counter()
    sim.run_for(frames * FRAME_OSC * 2 * OSC_HALF_NS)
    return rows, sim, time.perf_counter() - t0


def digital_frames(dig, frames):
    st = dg.run_stepper(dig, int(frames * FRAME_OSC) + 64, clock='OSC25', trigger='CCLK:fall',
                        signals=SAMPLE, sets=[('SLOW', 0, 0)])
    return st.as_dicts(), st


def analyse(rows, skip=100):
    """Bir karenin ölçümleri: `skip`. satırdan sonraki ilk (V, H) = (0, 0)'dan başlayan tam kare.
    Açılıştaki ilk karakterler T1'in açılış değerini (00) taşıdığı için atlanır."""
    start = next(i for i, r in enumerate(rows) if i >= skip and r['H'] == 0 and r['V'] == 0)
    nxt = next(i for i in range(start + 1, len(rows)) if rows[i]['H'] == 0 and rows[i]['V'] == 0)
    fr = rows[start:nxt]
    lines = {}
    for r in fr:
        lines.setdefault(r['V'], []).append(r)

    def where(sig, val, key):
        return sorted({r[key] for r in fr if r[sig] == val})

    hs_lines = {v: [r['H'] for r in ls if r['HSYNC_n'] == 0] for v, ls in lines.items()}
    vis = {v: sum(r['BLANK_n'] for r in ls) for v, ls in lines.items()}
    m = {
        'kare_karakter': len(fr),
        'satir_sayisi': len(lines),
        'satir_uzunlugu': sorted({len(ls) for ls in lines.values()}),
        'H_araligi': [min(r['H'] for r in fr), max(r['H'] for r in fr)],
        'HSYNC_0_H': sorted({h for hs in hs_lines.values() for h in hs}),
        'HSYNC_her_satirda_6': all(len(hs) == 6 for hs in hs_lines.values()),
        'VSYNC_0_V': where('VSYNC_n', 0, 'V'),
        'VSYNC_0_karakter': sum(1 for r in fr if r['VSYNC_n'] == 0),
        'gorunur_satir': sorted(v for v, n in vis.items() if n),
        'gorunur_karakter_satirda': sorted({n for n in vis.values() if n}),
        'VMUX_V': where('VMUX', 1, 'V'),
        'VWR_V': where('VWR', 1, 'V'),
        'BUFEN_0_karakter': sum(1 for r in fr if r['BUFEN_n'] == 0),
    }
    def span(sig, val):
        idx = [i for i, r in enumerate(fr) if r[sig] == val]
        if not idx:
            return None
        a, b = fr[idx[0]], fr[idx[-1]]
        return {'ilk': [a['V'], a['H']], 'son': [b['V'], b['H']], 'karakter': len(idx)}
    for sig, val in (('VSYNC_n', 0), ('VMUX', 1), ('VWR', 1), ('BUFEN_n', 0)):
        m[f'{sig}={val}'] = span(sig, val)
    rng = lambda xs: [xs[0], xs[-1], len(xs)] if xs else []
    for k in ('VSYNC_0_V', 'gorunur_satir', 'VMUX_V', 'VWR_V'):
        m[k] = rng(m[k])
    return m, start


def lock_frame(rows):
    """Rastgele açılıştan sonra ilk (V, H) = (0, 0): kaçıncı karakterde (kare cinsinden)."""
    i = next(i for i, r in enumerate(rows) if r['H'] == 0 and r['V'] == 0)
    return i, i / FRAME_CHARS


def testcases():
    """Digital test case'leri (beklenenler Sim'den, gecikmesiz adımlarla)."""
    b = board()
    steps = [({}, True)] * 40
    rows, states, sim = dg.simulate(b, steps)
    t1 = dg.testcase_text(b, steps, rows, states, comments=['1_nokta_karakter: 25 MHz → DCLK, CCLK, LD'])
    b = board()                                       # yeni çipler: ilk koşunun durumu taşınmasın
    steps2 = [({}, True)] * (2 * H_TOTAL * 16 + 32)
    rows2, states2, sim2 = dg.simulate(b, steps2)
    t2 = dg.testcase_text(b, steps2, rows2, states2,
                          comments=['2_iki_satir: H 0..49, /HSYNC, BLANK_n, /HEND, V artışı'])
    return [('1_nokta_karakter', t1), ('2_iki_satir', t2)], (rows, rows2)


def main():
    out = {}
    tests, (r1, r2) = testcases()
    dig = HERE / f'{NAME}.dig'
    dg.export(board(), dig, tests)
    t = dg.run_test(dig, None, verbose=False)
    out['digital_testleri'] = {'gecti': t.passed, 'ozet': t.summary()}
    print('Digital testleri:', t.summary(), flush=True)

    drows, st = digital_frames(dig, 2.2)
    dm, ds = analyse(drows)
    out['digital_kare'] = {'olcum': dm, 'sure_s': round(st.seconds, 1)}
    print('Digital kare:', json.dumps(dm), flush=True)

    key = lambda rs: [tuple(r[k] for k in SAMPLE) for r in rs]
    runs = [('typ', 'typ', False), ('max_dclk_dis', 'max', True)]
    # en kötü köşe, 25 MHz osilatörle: karakter periyodunu ölç
    srows, sim, dt = sim_frames(0.05, 'max')
    per = [b['t'] - a['t'] for a, b in zip(srows[10:], srows[11:])]
    out['sim_max_25MHz'] = {'karakter_periyodu_ns': sorted(set(per)), 'beklenen_ns': 640,
                            'ihlal': [str(v) for v in sim.violations[:5]]}
    print('Sim max 25 MHz:', out['sim_max_25MHz'], flush=True)
    for label, corner, ext in runs:
        srows, sim, dt = sim_frames(2.2, corner, dclk_ext=ext)
        sm, ss = analyse(srows)
        n = min(len(drows) - ds, len(srows) - ss)
        same = key(drows[ds:ds + n]) == key(srows[ss:ss + n])
        corner = label
        late = [v for v in sim.violations if v.time >= 1000]
        out[f'sim_{corner}'] = {'olcum': sm, 'olcum_digital_ile_ayni': sm == dm, 'ihlal': len(late),
                                'acilis_ihlal_ilk_1us': [str(v) for v in sim.violations if v.time < 1000],
                                'ilk_ihlaller': [str(v) for v in late[:5]],
                                'digital_ile_ayni': same, 'karsilastirilan_karakter': n,
                                'sure_s': round(dt, 1)}
        print(f'Sim {corner}:', json.dumps(out[f"sim_{corner}"], ensure_ascii=False), flush=True)

    rec = {}
    for seed in (1, 2, 3):
        srows, sim, dt = sim_frames(3.1, 'typ', 'random', seed)
        i, f = lock_frame(srows)
        sm, _ = analyse(srows, skip=i + 1)
        rec[seed] = {'ilk_0_0_karakter': i, 'kare': round(f, 3), 'sonraki_kare_dogru': sm == dm,
                     'ihlal_1us_sonra': len([v for v in sim.violations if v.time >= 1000])}
        print('rastgele açılış', seed, rec[seed], flush=True)
    out['rastgele_acilis'] = rec

    (HERE / 'images').mkdir(exist_ok=True)
    (HERE / 'images' / 'sonuclar.json').write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                    encoding='utf-8')
    import pickle
    (HERE / 'images' / '.rows.pkl').write_bytes(pickle.dumps({'digital': drows[ds:ds + FRAME_CHARS + 60],
                                                              'r1': r1, 'r2': r2}))


if __name__ == '__main__':
    main()
