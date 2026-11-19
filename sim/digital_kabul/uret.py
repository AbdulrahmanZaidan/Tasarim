"""Kabul testlerini Digital'de elle açılıp denenecek dosyalar olarak yazar.

Her .dig dosyasında modülün entegreleri ve test tablosu birlikte durur. Digital'de
dosyayı açıp "Run all tests" (F8) ile tablo satır satır denenir.

    cd sim
    py -3 digital_kabul/uret.py

Tablolar tests/test_hw_digital.py'deki kabul testleriyle (TestCpuModules) aynı.
"""

import sys
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SIM))

from ta8 import vectors                                  # noqa: E402
from ta8.hw import digital as dg                         # noqa: E402
from tests import test_hw_digital as t                   # noqa: E402

OUT = Path(__file__).resolve().parent


def urom():
    board = t.m2_urom_board()
    names, vrows = vectors.parse_table(vectors.urom_vectors(1000, seed=1))
    ins = ['STEP', 'IR', 'Z', 'C', 'N', 'V']
    steps = [({k: r[names.index(k)] for k in ins}, True) for r in vrows]
    rows, states, sim = dg.simulate(board, steps)
    assert not sim.violations, sim.violations[:5]
    return board, dg.testcase_text(board, steps, rows, states,
                                   comments=['vectors urom -n 1000 + LCLK darbesi (latch çıkışı)'])


def main():
    sets = [
        ('M2 mikrokod, 1.000 vektör', urom),
        ('M2 kod çözücüler, 512 satır', lambda: (t.m2_cs_board(), vectors.cs_vectors())),
        ('M4 ALU tabloları, 10.000 vektör',
         lambda: (t.m4_alu_board(), vectors.alu_vectors(10000, seed=1))),
        ('M5 adres çözme, 1.096 vektör',
         lambda: (t.m5_decode_board(), vectors.decode_vectors(1000, seed=1))),
    ]
    for title, make in sets:
        board, text = make()
        dg.export(board, OUT / f'{board.name}.dig', tests=[(board.name, text)])
        print(f'{board.name}.dig  {title}')


if __name__ == '__main__':
    main()
