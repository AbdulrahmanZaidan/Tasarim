"""Kablolama tablosu ve entegre sayımı (td8.hw.cpu Board'u için).

    from td8.hw import cpu, wiring
    board = cpu.build()
    print(wiring.wiring_table(board))      # Markdown: modül modül, bacak / pin / net
    wiring.chip_counts(board)              # {'M1': Counter({'74HC74': 2, ...}), ...}
    wiring.count_table(board)              # plan / netlist / kapsam dışı / fark (Markdown)
"""

from collections import Counter

from .cpu import MODULE_ORDER, MODULE_TITLES, PLAN_FIXES

# SISTEM-PLANI 15.1 (modüllere göre entegreler). Osilatörler, 2N7000, diyotlar hariç.
PLAN_COUNTS = {
    'M1': {'NE555': 1, '74HC153': 1, '74HC14': 1, '74HC74': 3, '74HC175': 2, '74HC00': 1,
           '74HC08': 1, '74HC32': 1, '74HC02': 1, '74HC138': 1, '74HC245': 1},
    'M2': {'SST39SF010': 3, '74HC273': 3, '74HC138': 2, '74HC139': 1, '74HC161': 1,
           '74HC04': 1, '74HC688': 2},
    'M3': {'74HC161': 12, '74HC191': 2, '74HC245': 8},
    'M4': {'74HC161': 1, '74HC377': 2, '74HC245': 3, 'SST39SF010': 2},
    'AUX': {'74HC00': 2, '74HC08': 1, '74HC32': 1},
    'M5': {'SST39SF010': 1, 'CY62256': 1, '74HC20': 1, '74HC138': 1, '74HC377': 1,
           '74HC245': 1},
}

# Plan sayısından netlist'e girmeyenler ve nedeni.
NOT_BUILT = {
    'M1': [('NE555', 1, 'kapsam dışı: yavaş saat kaynağı; MCLK test tezgâhından'),
           ('74HC153', 1, 'kapsam dışı: saat kaynağı seçici'),
           ('74HC14', 1, 'kapsam dışı: RC reset / buton debounce / 555 kare dalgası')],
    'AUX': [('74HC00', 1, 'kapsam dışı değil: 138\'li WAIT (DOGRULAMA 2.5) ve G1 = CLK '
                          'düzeltmesiyle NAND(MEMW_L, /VWR_s) ve OR kalktı; 12 NAND\'ın 7\'si '
                          'yetiyor, 2. yardımcı 74HC00 gereksiz')],
}


def chip_counts(board, include_tb=False):
    """{modül: Counter(parça → adet)}; TB taklitleri varsayılan olarak hariç.
    'toplam' anahtarı bütün modüllerin toplamıdır."""
    out = {}
    for c in board.chips:
        if c.module == 'TB' and not include_tb:
            continue
        out.setdefault(c.module, Counter())[c.KIND] += 1
    out = {m: out[m] for m in MODULE_ORDER if m in out}
    total = Counter()
    for cnt in out.values():
        total.update(cnt)
    out['toplam'] = total
    return out


def count_rows(board):
    """[(modül, parça, plan, netlist, kapsam dışı/kurulmayan, açıklanmamış fark), ...]"""
    have = chip_counts(board)
    rows = []
    for m, plan in PLAN_COUNTS.items():
        nb = Counter()
        for part, n, _ in NOT_BUILT.get(m, []):
            nb[part] += n
        parts = list(plan) + [p for p in have.get(m, {}) if p not in plan]
        for p in parts:
            pl, nl, x = plan.get(p, 0), have.get(m, Counter())[p], nb[p]
            rows.append((m, p, pl, nl, x, nl + x - pl))
    return rows


def count_table(board):
    """Markdown: modül başına plan / netlist / kurulmayan / fark."""
    rows = count_rows(board)
    lines = ['| Modül | Plan (15.1) | Netlist | Kurulmayan | Açıklanmamış fark |',
             '|---|---:|---:|---:|---:|']
    for m in PLAN_COUNTS:
        mr = [r for r in rows if r[0] == m]
        pl, nl, x, d = (sum(r[k] for r in mr) for k in (2, 3, 4, 5))
        lines.append(f'| {MODULE_TITLES[m]} | {pl} | {nl} | {x} | {d} |')
    pl, nl, x, d = (sum(r[k] for r in rows) for k in (2, 3, 4, 5))
    lines.append(f'| **Toplam (CPU, M6/M7 hariç)** | **{pl}** | **{nl}** | **{x}** | **{d}** |')
    lines.append('')
    lines.append('Kurulmayanlar:')
    for m, items in NOT_BUILT.items():
        for part, n, why in items:
            lines.append(f'- {m} {part} ×{n}: {why}')
    return '\n'.join(lines)


def _leg_rows(chip):
    rows = []
    for pin, leg in sorted(chip.PINOUT.items(), key=lambda kv: kv[1]):
        if pin in ('VCC', 'GND'):
            net = f'*{pin}* (güç)'
        elif pin in chip.pins:
            net = chip.pins[pin]
        else:
            net = '— (boş)'
        rows.append((leg, pin, net))
    return rows


def wiring_table(board, title='TD-8 CPU kablolama tablosu'):
    """Markdown: modül modül, her çip için bacak no / pin adı / net."""
    out = [f'# {title}', '',
           'Kaynak: `sim/td8/hw/cpu.py` (üretilmiştir, elle düzenlemeyin). Bacak numaraları '
           'DIP kılıf, pin adları datasheet adları (`sim/td8/hw/chips.py`). '
           '"— (boş)" bağlanmayan çıkış.', '']
    fixes = [n for n in board.notes if n.startswith('PLAN DÜZELTMESİ')]
    if fixes:
        out += ['## Plan düzeltmeleri', ''] + [f'- {n}' for n in fixes] + ['']
    out += ['## Entegre sayımı', '', count_table(board), '']
    for m, chips in board.modules().items():
        out += [f'## {MODULE_TITLES.get(m, m)}', '']
        for c in chips:
            out += [f'### {c.ref} · {c.KIND}', '', c.note, '',
                    '| Bacak | Pin | Net |', '|---:|---|---|']
            out += [f'| {leg} | `{pin}` | `{net}` |' if not net.startswith(('*', '—'))
                    else f'| {leg} | `{pin}` | {net} |' for leg, pin, net in _leg_rows(c)]
            out.append('')
    out += ['## Pull direnci, sabitler ve test tezgâhı girişleri', '',
            '| Net | Tür | Değer |', '|---|---|---|']
    out += [f'| `{n}` | pull ({"10k yukarı" if v else "10k aşağı"}) | {v} |'
            for n, v in board.pulls.items()]
    out += [f'| `{n}` | sabit (5. hafta, pasif değer) | {v} |' for n, v in board.ties.items()]
    out += [f'| `{n}` | test tezgâhı girişi | varsayılan {v} |' for n, v in board.inputs.items()]
    out += [f'| `{n}` | saat | yarım periyot {v} ns |' for n, v in board.clocks.items()]
    out += ['', '## Notlar', ''] + [f'- {n}' for n in board.notes
                                    if not n.startswith('PLAN DÜZELTMESİ')] + ['']
    return '\n'.join(out)


__all__ = ['PLAN_COUNTS', 'NOT_BUILT', 'PLAN_FIXES', 'chip_counts', 'count_rows', 'count_table',
           'wiring_table']
