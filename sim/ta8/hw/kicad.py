"""Netlist → KiCad şeması (KiCad 8/9, .kicad_sch).

    from ta8.hw import cpu, kicad
    kicad.write_project(cpu.build().chips, 'kicad/')        # ya da: py cli.py hw kicad

Her modül ayrı bir sayfa, kök sayfada hepsi. Teller çizilmez: her bacağın ucunda
net adıyla bir etiket var (Digital dışa aktarıcısıyla aynı fikir). Yalnız o modülde
kalan netler yerel etiket (label), modüller arası netler ve dışarıdan sürülenler
global etikettir. VCC/GND bacakları güç sembolü, boş çıkışlar "no connect" alır.

Semboller çip modellerinden (chips.py: PINOUT, DIRS) üretilir: bacak numarası
DIP bacağıdır, girişler solda, çıkışlar sağda, VCC üstte, GND altta. Aktif-düşük
adlar (/MR) KiCad'de üst çizgili yazılır (~{MR}).

Dosyalar netlist'ten üretilir: elle düzenlemeyin, netlist'i değiştirip yeniden üretin.
"""

import math
import re
import uuid
from collections import Counter, defaultdict
from pathlib import Path

GRID = 2.54
PROJECT = 'ta8'
NS = uuid.UUID('6d1f3c2a-5b7e-4a90-9c1d-2e8f7a6b5c4d')

TITLES = {
    'M1': 'M1 Saat / reset / durdurma',
    'M2': 'M2 Kontrol ünitesi',
    'M3': 'M3 Adres registerları',
    'M4': 'M4 Veri ve ALU',
    'AUX': 'CPU yardımcı kapıları',
    'M5': 'M5 Bellek + I/O',
    'M6': 'M6 VGA',
    'M7': 'M7 PS/2 klavye',
}
ORDER = ('M1', 'M2', 'M3', 'M4', 'AUX', 'M5', 'M6', 'M7')
ETYPE = {'in': 'input', 'out': 'output', 'tri': 'tri_state', 'bidir': 'bidirectional'}
SHAPE = {'in': 'input', 'out': 'output', 'tri': 'tri_state', 'bidir': 'bidirectional'}
PAGES = [('A4', 297, 210), ('A3', 420, 297), ('A2', 594, 420), ('A1', 841, 594), ('A0', 1189, 841)]


def uid(*parts):
    return str(uuid.uuid5(NS, '/'.join(map(str, parts))))


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def g(v):
    """Izgaraya (1.27 mm) yuvarla, KiCad biçiminde yaz."""
    v = round(v / 1.27) * 1.27
    return f'{v:.2f}'.rstrip('0').rstrip('.') if v else '0'


def overbar(name):
    """'/MR' → '~{MR}', '/1RD' → '~{1RD}', '/RESET_s' → '~{RESET}_s'. Ortadaki / (D/U,
    MAX/MIN) ayraçtır, dokunulmaz."""
    return re.sub(r'(^|(?<=[^A-Za-z0-9]))/([A-Za-z0-9]+)', r'\1~{\2}', name)


def font(size=1.27, extra=''):
    return f'(effects (font (size {size} {size})){extra})'


# ---------------------------------------------------------------- semboller

class Sym:
    """Bir çip türünün KiCad sembolü ve bacak uçlarının yerleri."""

    def __init__(self, cls):
        self.kind = cls.KIND
        self.legs = max(cls.PINOUT.values())
        pins = sorted(cls.PINOUT, key=cls.PINOUT.get)
        self.left = [p for p in pins if cls.DIRS.get(p) == 'in']
        self.right = [p for p in pins if cls.DIRS.get(p) in ('out', 'tri', 'bidir')]
        self.dirs = dict(cls.DIRS, VCC='pwr', GND='pwr')
        rows = max(len(self.left), len(self.right))
        wl = max((len(p) for p in self.left), default=0)
        wr = max((len(p) for p in self.right), default=0)
        self.w = max(4, math.ceil((wl + wr) * 0.45 + 2)) * GRID       # gövde genişliği
        self.h = (rows + 1) * GRID                                       # gövde yüksekliği
        top = (rows - 1) / 2 * GRID
        self.at = {}                                   # pin → (x, y, açı); y yukarı pozitif
        for i, p in enumerate(self.left):
            self.at[p] = (-self.w / 2 - GRID, top - i * GRID, 0)
        for i, p in enumerate(self.right):
            self.at[p] = (self.w / 2 + GRID, top - i * GRID, 180)
        self.at['VCC'] = (0, self.h / 2 + GRID, 270)
        self.at['GND'] = (0, -self.h / 2 - GRID, 90)
        self.pinout = cls.PINOUT

    @property
    def lib_id(self):
        return f'{PROJECT}:{self.kind}'

    @property
    def footprint(self):
        wide = '15.24' if self.legs >= 24 else '7.62'
        return f'Package_DIP:DIP-{self.legs}_W{wide}mm'

    def end(self, pin, x0, y0):
        """Bacağın bağlantı ucu, şema koordinatında (y aşağı pozitif)."""
        x, y, _ = self.at[pin]
        return x0 + x, y0 - y

    def lib(self, embedded=True):
        n = self.kind
        out = [f'(symbol {q(self.lib_id if embedded else n)} (pin_names (offset 1.016)) (exclude_from_sim no) '
               f'(in_bom yes) (on_board yes)',
               f'(property "Reference" "U" (at 0 {g(self.h / 2 + 1.27)} 0) {font()})',
               f'(property "Value" {q(n)} (at 0 {g(-self.h / 2 - 1.27)} 0) {font()})',
               f'(property "Footprint" {q(self.footprint)} (at 0 0 0) {font(extra=" (hide yes)")})',
               f'(property "Datasheet" "" (at 0 0 0) {font(extra=" (hide yes)")})',
               f'(symbol "{n}_0_1" (rectangle (start {g(-self.w / 2)} {g(self.h / 2)}) '
               f'(end {g(self.w / 2)} {g(-self.h / 2)}) (stroke (width 0.254) (type default)) '
               f'(fill (type background))))',
               f'(symbol "{n}_1_1"']
        for p, (x, y, a) in self.at.items():
            et = 'power_in' if p in ('VCC', 'GND') else ETYPE[self.dirs[p]]
            out.append(f'(pin {et} line (at {g(x)} {g(y)} {a}) (length 2.54) '
                       f'(name {q(overbar(p))} {font()}) (number {q(self.pinout[p])} {font()}))')
        out.append('))')
        return '\n'.join(out)


POWER_LIB = {
    'VCC': '''(symbol "ta8:VCC" (power) (pin_names (offset 0)) (exclude_from_sim no) (in_bom yes) (on_board yes)
(property "Reference" "#PWR" (at 0 -3.81 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Value" "VCC" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(symbol "VCC_0_1" (polyline (pts (xy -0.762 1.27) (xy 0 2.54) (xy 0.762 1.27)) (stroke (width 0) (type default)) (fill (type none)))
(polyline (pts (xy 0 0) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none))))
(symbol "VCC_1_1" (pin power_in line (at 0 0 90) (length 0) (hide yes) (name "VCC" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))''',
    'GND': '''(symbol "ta8:GND" (power) (pin_names (offset 0)) (exclude_from_sim no) (in_bom yes) (on_board yes)
(property "Reference" "#PWR" (at 0 -6.35 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Value" "GND" (at 0 -3.81 0) (effects (font (size 1.27 1.27))))
(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(symbol "GND_0_1" (polyline (pts (xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27)) (stroke (width 0) (type default)) (fill (type none))))
(symbol "GND_1_1" (pin power_in line (at 0 0 270) (length 0) (hide yes) (name "GND" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))''',
    'PWR_FLAG': '''(symbol "ta8:PWR_FLAG" (power) (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes)) (exclude_from_sim no) (in_bom yes) (on_board yes)
(property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
(symbol "PWR_FLAG_0_0" (pin power_out line (at 0 0 90) (length 0) (name "pwr" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27))))))
(symbol "PWR_FLAG_0_1" (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) (xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none)))))''',
}


# ---------------------------------------------------------------- sayfa

class Sheet:
    def __init__(self, project, module, chips, global_nets, notes):
        self.p = project
        self.module = module
        self.chips = chips
        self.glob = global_nets
        self.notes = notes
        self.file = f'{module.lower()}.kicad_sch'
        self.uuid = uid('sheet', module)
        self.items = []
        self.syms = {}
        self.page = 'A3'

    def path(self):
        return f'/{self.p.root_uuid}/{self.uuid}'

    def power(self, net, x, y, rot=0, show=True):
        ref = self.p.next_pwr()
        u = uid(self.module, 'pwr', ref)
        self.items.append(
            f'(symbol (lib_id "ta8:{net}") (at {g(x)} {g(y)} {rot}) (unit 1) (exclude_from_sim no) '
            f'(in_bom yes) (on_board yes) (dnp no) (uuid {q(u)})\n'
            f'(property "Reference" {q(ref)} (at {g(x)} {g(y)} 0) {font(extra=" (hide yes)")})\n'
            f'(property "Value" {q(net)} (at {g(x)} {g(y - 3.81 if net == "VCC" else y + 3.81)} 0) '
            f'{font(1.0, "" if show else " (hide yes)")})\n'
            f'(property "Footprint" "" (at {g(x)} {g(y)} 0) {font(extra=" (hide yes)")})\n'
            f'(property "Datasheet" "" (at {g(x)} {g(y)} 0) {font(extra=" (hide yes)")})\n'
            f'(pin "1" (uuid {q(uid(u, "p"))}))\n'
            f'(instances (project {q(PROJECT)} (path {q(self.path())} (reference {q(ref)}) (unit 1)))))')

    def label(self, net, x, y, side, d):
        text = overbar(net)
        ang, just = (180, 'right') if side == 'L' else (0, 'left')
        u = uid(self.module, 'lbl', net, x, y)
        if net in self.glob:
            self.items.append(
                f'(global_label {q(text)} (shape {SHAPE[d]}) (at {g(x)} {g(y)} {ang}) '
                f'(fields_autoplaced yes) {font(extra=f" (justify {just})")} (uuid {q(u)})\n'
                f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {g(x)} {g(y)} 0) '
                f'{font(extra=" (hide yes)")}))')
        else:
            self.items.append(f'(label {q(text)} (at {g(x)} {g(y)} {ang}) (fields_autoplaced yes) '
                              f'{font(extra=f" (justify {just} bottom)")} (uuid {q(u)}))')

    def place(self, c, sym, x0, y0):
        u = uid('chip', c.ref)
        note = c.note.replace('\n', ' ')
        self.items.append(
            f'(symbol (lib_id {q(sym.lib_id)}) (at {g(x0)} {g(y0)} 0) (unit 1) (exclude_from_sim no) '
            f'(in_bom yes) (on_board yes) (dnp no) (uuid {q(u)})\n'
            f'(property "Reference" {q(c.ref)} (at {g(x0 - sym.w / 2)} {g(y0 - sym.h / 2 - 0.635)} 0) '
            f'{font(1.27, " (justify left bottom)")})\n'
            f'(property "Value" {q(sym.kind)} (at {g(x0)} {g(y0 + sym.h / 2 + 6.35)} 0) {font()})\n'
            f'(property "Footprint" {q(sym.footprint)} (at {g(x0)} {g(y0)} 0) {font(extra=" (hide yes)")})\n'
            f'(property "Datasheet" "" (at {g(x0)} {g(y0)} 0) {font(extra=" (hide yes)")})\n'
            f'(property "Description" {q(note)} (at {g(x0)} {g(y0)} 0) {font(extra=" (hide yes)")})\n'
            + ''.join(f'(pin {q(sym.pinout[p])} (uuid {q(uid(u, p))}))\n' for p in sym.at)
            + f'(instances (project {q(PROJECT)} (path {q(self.path())} (reference {q(c.ref)}) (unit 1)))))')
        for p, (_, _, _) in sym.at.items():
            x, y = sym.end(p, x0, y0)
            side = 'L' if p in sym.left else 'R'
            if p in ('VCC', 'GND'):
                self.power(p, x, y, show=False)          # şekli yeterli; yazısı çip adıyla çakışmasın
            elif p not in c.pins:
                self.items.append(f'(no_connect (at {g(x)} {g(y)}) (uuid {q(uid(c.ref, "nc", p))}))')
            elif c.pins[p] in ('VCC', 'GND'):
                # kısa tel + yatay güç sembolü: komşu bacaklardaki semboller üst üste binmesin
                net = c.pins[p]
                xe = x - GRID if side == 'L' else x + GRID
                self.items.append(f'(wire (pts (xy {g(x)} {g(y)}) (xy {g(xe)} {g(y)})) '
                                  f'(stroke (width 0) (type default)) (uuid {q(uid(c.ref, "w", p))}))')
                rot = {('L', 'VCC'): 90, ('L', 'GND'): 270, ('R', 'VCC'): 270, ('R', 'GND'): 90}[side, net]
                self.power(net, xe, y, rot, show=False)
            else:
                self.label(c.pins[p], x, y, side, sym.dirs[p])

    def layout(self):
        """Çipleri sütunlara diz; sayfa boyutunu sığacak en küçük A boyutu seç."""
        syms = [self.p.sym(c) for c in self.chips]
        lab = max((len(n) for c in self.chips for n in c.pins.values()), default=8) * 1.0 + 8
        colw = max(s.w for s in syms) + 2 * (GRID + lab) + 10
        import textwrap
        lines = []
        for c in self.chips:
            if c.note:
                lines += textwrap.wrap(f'{c.ref} ({c.KIND}): {c.note}', 95, subsequent_indent='    ')
        for n in self.notes:
            lines += [''] + textwrap.wrap(n, 95, subsequent_indent='    ')
        notew = 125 if lines else 0
        for name, pw, ph in PAGES:
            usable = ph - 60
            cols, colh, y = 1, 0, 0
            for s in syms:
                hh = s.h + 15
                if y + hh > usable and y:
                    cols, y = cols + 1, 0
                y += hh
            if (30 + cols * colw + notew <= pw and len(lines) * 2.2 <= ph - 60) or name == 'A0':
                self.page = name
                break
        x = 25 + colw / 2
        y = 30
        _, _, ph = next(p for p in PAGES if p[0] == self.page)
        for c, s in zip(self.chips, syms):
            hh = s.h + 15
            if y + hh > ph - 30 and y > 30:
                x, y = x + colw, 30
            self.place(c, s, x, y + s.h / 2 + 5)
            y += hh
        # notlar: çip açıklamaları ve kapsam dışı bağlantılar
        tx, ty = x + colw / 2 + 5, 30
        if lines:
            text = '\n'.join(lines).replace('"', "'")
            self.items.append(f'(text {q(text)} (exclude_from_sim no) (at {g(tx)} {g(ty)} 0) '
                              f'{font(1.0, " (justify left top)")} (uuid {q(uid(self.module, "notes"))}))')

    def render(self, date):
        self.layout()
        libs = {self.p.sym(c).lib_id: self.p.sym(c).lib() for c in self.chips}
        libs.update({f'ta8:{k}': v for k, v in POWER_LIB.items() if k != 'PWR_FLAG'})
        return (f'(kicad_sch (version 20231120) (generator "ta8_kicad") (generator_version "8.0")\n'
                f'(uuid {q(self.uuid)})\n(paper {q(self.page)})\n'
                f'(title_block (title {q(TITLES.get(self.module, self.module))}) (date {q(date)}) '
                f'(company "TA-8 · SDÜ Bitirme Projesi") '
                f'(comment 1 "Netlist\'ten üretildi (sim/ta8/hw/kicad.py). Elle düzenlemeyin."))\n'
                f'(lib_symbols\n' + '\n'.join(libs.values()) + ')\n'
                + '\n'.join(self.items) + '\n)\n')


class Project:
    def __init__(self, chips, ties=None, pulls=None, inputs=None, clocks=None, date='2026-11-19'):
        self.date = date
        self.root_uuid = uid('root')
        self._syms = {}
        self._pwr = 0
        by_mod = defaultdict(list)
        for c in chips:
            if c.module in ('TB',):
                continue
            by_mod[c.module].append(c)
        self.modules = [m for m in ORDER if m in by_mod] + sorted(set(by_mod) - set(ORDER))
        ext = set(ties or {}) | set(pulls or {}) | set(inputs or {}) | set(clocks or {})
        users = defaultdict(set)
        drv, rd = defaultdict(set), defaultdict(set)          # (modül, net): sürülüyor / okunuyor
        for m, cs in by_mod.items():
            for c in cs:
                for p, n in c.pins.items():
                    users[n].add(m)
                    (rd if c.DIRS[p] == 'in' else drv)[m].add(n)
                    if c.DIRS[p] == 'bidir':
                        rd[m].add(n)
        # global: birden çok modülde, dışarıdan sürülen, ya da modül içinde sürücüsü/okuyanı olmayan
        lonely = {n for m in by_mod for n in (rd[m] ^ drv[m])}
        self.glob = {n for n, ms in users.items() if len(ms) > 1 or n in ext or n in lonely} - {'VCC', 'GND'}
        self.sheets = []
        for m in self.modules:
            nets = {n for c in by_mod[m] for n in c.pins.values()}
            notes = []
            t = sorted(n for n in nets if n in (ties or {}))
            pl = sorted(n for n in nets if n in (pulls or {}))
            ins = sorted(n for n in nets if n in (inputs or {}) or n in (clocks or {}))
            if pl:
                notes.append('Pull dirençleri (10k): ' + ', '.join(f'{n}{"↑" if pulls[n] else "↓"}' for n in pl))
            if t:
                notes.append('Kapsam dışı sürücü yerine sabit değer: ' + ', '.join(f'{n}={ties[n]}' for n in t))
            if ins:
                notes.append('Dışarıdan (buton/anahtar/osilatör/taklit) sürülenler: ' + ', '.join(ins))
            self.sheets.append(Sheet(self, m, by_mod[m], self.glob, notes))

    def sym(self, c):
        k = type(c)
        if k not in self._syms:
            self._syms[k] = Sym(k)
        return self._syms[k]

    def next_pwr(self):
        self._pwr += 1
        return f'#PWR{self._pwr:04d}'

    def root(self):
        items = []
        x, y = 25.4, 38.1
        for i, s in enumerate(self.sheets):
            w, h = 50.8, 15.24
            items.append(
                f'(sheet (at {g(x)} {g(y)}) (size {g(w)} {g(h)}) (fields_autoplaced yes) '
                f'(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000)) (uuid {q(s.uuid)})\n'
                f'(property "Sheetname" {q(TITLES.get(s.module, s.module))} (at {g(x)} {g(y - 1.27)} 0) '
                f'{font(extra=" (justify left bottom)")})\n'
                f'(property "Sheetfile" {q(s.file)} (at {g(x)} {g(y + h + 1.27)} 0) '
                f'{font(extra=" (justify left top)")})\n'
                f'(instances (project {q(PROJECT)} (path {q("/" + self.root_uuid)} (page {q(i + 2)})))))')
            x += 63.5
            if x > 340:
                x, y = 25.4, y + 30.48
        for j, net in enumerate(('VCC', 'GND')):
            fx, y0 = 25.4 + j * 25.4, 160.02
            items.append(f'(wire (pts (xy {g(fx)} {g(y0)}) (xy {g(fx)} {g(y0 + 7.62)})) '
                         f'(stroke (width 0) (type default)) (uuid {q(uid("root", "w", net))}))')
            for kind, ref, fy in (('PWR_FLAG', f'#FLG0{j + 1}', y0), (net, f'#PWR_ROOT{j + 1}', y0 + 7.62)):
                u = uid('root', kind, net)
                items.append(
                    f'(symbol (lib_id "ta8:{kind}") (at {g(fx)} {g(fy)} 0) (unit 1) (exclude_from_sim no) '
                    f'(in_bom yes) (on_board yes) (dnp no) (uuid {q(u)})\n'
                    f'(property "Reference" {q(ref)} (at {g(fx)} {g(fy)} 0) {font(extra=" (hide yes)")})\n'
                    f'(property "Value" {q(kind)} (at {g(fx)} {g(fy + 3.81)} 0) {font()})\n'
                    f'(property "Footprint" "" (at {g(fx)} {g(fy)} 0) {font(extra=" (hide yes)")})\n'
                    f'(property "Datasheet" "" (at {g(fx)} {g(fy)} 0) {font(extra=" (hide yes)")})\n'
                    f'(pin "1" (uuid {q(uid(u, "p"))}))\n'
                    f'(instances (project {q(PROJECT)} (path {q("/" + self.root_uuid)} (reference {q(ref)}) (unit 1)))))')
        text = ('TA-8: 8 bitlik breadboard bilgisayarı. Her modül ayrı sayfa; sayfalar global etiketlerle '
                'bağlı.\nKaynak: sim/ta8/hw/cpu.py (netlist). Yeniden üretmek için: cd sim → py cli.py hw kicad')
        items.append(f'(text {q(text)} (exclude_from_sim no) (at 25.4 20.32 0) '
                     f'{font(1.5, " (justify left top)")} (uuid {q(uid("root", "text"))}))')
        libs = '\n'.join(POWER_LIB.values())
        return (f'(kicad_sch (version 20231120) (generator "ta8_kicad") (generator_version "8.0")\n'
                f'(uuid {q(self.root_uuid)})\n(paper "A4")\n'
                f'(title_block (title "TA-8 8-bit breadboard bilgisayarı") (date {q(self.date)}) '
                f'(company "TA-8 · SDÜ Bitirme Projesi"))\n'
                f'(lib_symbols\n{libs})\n' + '\n'.join(items) + '\n'
                f'(sheet_instances (path "/" (page "1")))\n)\n')

    def pro(self):
        return ('{\n  "meta": {"filename": "ta8.kicad_pro", "version": 1},\n'
                '  "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},\n'
                '  "sheets": [' + ', '.join(f'["{s}", ""]' for s in [self.root_uuid] + [x.uuid for x in self.sheets])
                + ']\n}\n')

    def write(self, out):
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        files = []
        for s in self.sheets:
            (out / s.file).write_text(s.render(self.date), encoding='utf-8')
            files.append(s.file)
        (out / f'{PROJECT}.kicad_sch').write_text(self.root(), encoding='utf-8')
        (out / f'{PROJECT}.kicad_pro').write_text(self.pro(), encoding='utf-8')
        syms = '\n'.join([self._syms[k].lib(embedded=False) for k in sorted(self._syms, key=lambda k: k.KIND)]
                         + [v.replace(f'"ta8:{k}"', f'"{k}"', 1) for k, v in POWER_LIB.items()])
        (out / f'{PROJECT}.kicad_sym').write_text(
            f'(kicad_symbol_lib (version 20231120) (generator "ta8_kicad") (generator_version "8.0")\n{syms}\n)\n',
            encoding='utf-8')
        (out / 'sym-lib-table').write_text(
            '(sym_lib_table\n  (version 7)\n'
            f'  (lib (name "{PROJECT}")(type "KiCad")(uri "${{KIPRJMOD}}/{PROJECT}.kicad_sym")(options "")'
            '(descr "TA-8 entegreleri, netlist\'ten üretildi"))\n'
            ')\n',
            encoding='utf-8')
        (out / 'fp-lib-table').write_text(
            '(fp_lib_table\n  (version 7)\n'
            '  (lib (name "Package_DIP")(type "KiCad")(uri "${KICAD10_FOOTPRINT_DIR}/Package_DIP.pretty")'
            '(options "")(descr ""))\n)\n', encoding='utf-8')
        return [f'{PROJECT}.kicad_pro', f'{PROJECT}.kicad_sch', f'{PROJECT}.kicad_sym',
                'sym-lib-table', 'fp-lib-table'] + files

    def bom(self):
        """[(parça, adet, referanslar, kılıf)] — bütün sayfalar."""
        rows = defaultdict(list)
        for s in self.sheets:
            for c in s.chips:
                rows[c.KIND].append(c.ref)
        return [(k, len(v), ' '.join(sorted(v)), self._syms[next(t for t in self._syms if t.KIND == k)].footprint
                 if any(t.KIND == k for t in self._syms) else '') for k, v in sorted(rows.items())]


def write_project(board, out, extra_chips=(), date='2026-11-19'):
    """board: cpu.build() sonucu. extra_chips: netlist'te henüz olmayan modüller (ör. M6)."""
    p = Project(list(board.chips) + list(extra_chips), board.ties, board.pulls, board.inputs,
                board.clocks, date)
    return p, p.write(out)
