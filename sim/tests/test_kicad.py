"""KiCad dışa aktarıcısı: her bacak bir yere bağlı, dosyalar sözdizimce sağlam, netler aynı."""
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from ta8.hw import cpu, kicad


def balanced(text):
    depth, in_str, esc = 0, False, False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not in_str


class TestKicad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = cpu.build(vga="netlist", kbd="netlist")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.proj, cls.files = kicad.write_project(cls.board, cls.tmp.name)
        cls.text = {f: (Path(cls.tmp.name) / f).read_text(encoding='utf-8') for f in cls.files}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_files_balanced(self):
        for f, t in self.text.items():
            if f.endswith('.kicad_sch'):
                self.assertTrue(balanced(t), f)

    def test_every_chip_once(self):
        refs = Counter()
        for s in self.proj.sheets:
            refs.update(re.findall(r'\(property "Reference" "((?:U|D|Q|RC)\d+)"', self.text[s.file]))
        want = Counter(c.ref for c in self.board.chips if c.module != 'TB')
        self.assertEqual(refs, want)

    def test_every_leg_terminated(self):
        """Her bacak ucunda tam olarak bir şey var: etiket, güç sembolü ya da no-connect."""
        for s in self.proj.sheets:
            t = self.text[s.file]
            ends = Counter(re.findall(r'\((?:label|global_label) "[^"]*" (?:\(shape \w+\) )?\(at ([-\d.]+ [-\d.]+)', t))
            ends.update(re.findall(r'\(no_connect \(at ([-\d.]+ [-\d.]+)\)', t))
            ends.update(re.findall(r'\(symbol \(lib_id "ta8:(?:VCC|GND)"\) \(at ([-\d.]+ [-\d.]+) 0\)', t))
            ends.update(re.findall(r'\(wire \(pts \(xy ([-\d.]+ [-\d.]+)\)', t))
            legs = sum(len(self.proj.sym(c).at) for c in s.chips)
            self.assertEqual(sum(ends.values()), legs, s.file)
            self.assertEqual(max(ends.values()), 1, f'{s.file}: iki şey aynı noktada')

    def test_labels_match_netlist(self):
        """Etiket metinleri = netlist'teki netler (VCC/GND hariç, üst çizgi çevrilerek)."""
        nets = {kicad.overbar(n) for c in self.board.chips if c.module != 'TB'
                for n in c.pins.values()} - {'VCC', 'GND'}
        seen = set()
        for s in self.proj.sheets:
            seen |= set(re.findall(r'\((?:label|global_label) "([^"]*)"', self.text[s.file]))
        self.assertEqual(seen, nets)

    def test_cross_module_nets_are_global(self):
        by = {}
        for c in self.board.chips:
            if c.module == 'TB':
                continue
            for n in c.pins.values():
                by.setdefault(n, set()).add(c.module)
        for n, ms in by.items():
            if len(ms) > 1 and n not in ('VCC', 'GND'):
                self.assertIn(n, self.proj.glob, n)

    def test_overbar(self):
        self.assertEqual(kicad.overbar('/MR'), '~{MR}')
        self.assertEqual(kicad.overbar('/1RD'), '~{1RD}')
        self.assertEqual(kicad.overbar('D/U'), 'D/U')          # ortadaki / ayraç (MAX/MIN gibi)
        self.assertEqual(kicad.overbar('/RESET_s'), '~{RESET}_s')
        self.assertEqual(kicad.overbar('AB0'), 'AB0')


if __name__ == '__main__':
    unittest.main()
