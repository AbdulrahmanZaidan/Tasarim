"""Mikroadım emülatörü: üretilen uROM ve ALU imajlarını aynen çalıştırır.

Her `cycle()` donanımdaki bir CPU çevrimidir (C→D latch, D, A, B, commit).
İmajlar donanımla aynı olduğu için bu emülatörün izi Digital'deki devreyle
ve breadboard'la çevrim çevrim karşılaştırılabilir.
"""

from . import alu, isa, microcode
from .bus import IO_BASE, VRAM_BASE


class MicroEmu:
    def __init__(self, bus, roms=None, alu_tables=None, bank=0):
        self.bus = bus
        self.urom = roms if roms is not None else microcode.build()
        self.alu_lo, self.alu_hi = alu_tables if alu_tables is not None else alu.build_tables()
        self.bank = bank
        self.trace = None                 # liste verilirse (çevrim, AB, DB, CW) eklenir
        self.reset()

    def reset(self):
        self.pc = self.ar = self.x = 0
        self.sp = 0xFF
        self.a = self.ir = 0              # donanımda belirsiz
        self.z = self.c = self.n = self.v = 0
        self.step = 0
        self.halted = False
        self.cycles = 0
        self.stall_cycles = 0

    def control_word(self):
        flags = self.z | self.c << 1 | self.n << 2 | self.v << 3
        addr = self.step | self.ir << 4 | flags << 12 | self.bank << 16
        u = self.urom
        return u[0][addr] | u[1][addr] << 8 | u[2][addr] << 16

    def cycle(self):
        cw = self.control_word()
        asrc, dsrc, ddst = cw & 3, (cw >> 2) & 7, (cw >> 5) & 7
        op = (cw >> 8) & 31
        ab = (self.pc, self.ar, self.x, isa.STACK_PAGE | self.sp)[asrc]

        if cw & isa.MEMW and VRAM_BASE <= ab < IO_BASE:
            wait = self.bus.cycles_until_window()     # WAIT: D fazında bekle
            if wait:
                self.stall_cycles += wait
                self.cycles += wait
                self.bus.tick(wait)

        if dsrc == 1:
            db = self.bus.read(ab)
        elif dsrc == 2:
            db = self.a
        elif dsrc == 3:
            db = self.pc & 0xFF
        elif dsrc == 4:
            db = self.pc >> 8
        else:
            db = 0                                     # pull-down'lar

        lv = self.alu_lo[alu.lo_addr(op, self.a, db, self.c)]
        c4, zlo, clo = (lv >> 4) & 1, (lv >> 5) & 1, (lv >> 6) & 1
        hv = self.alu_hi[alu.hi_addr(op, self.a, db, c4, zlo, self.z)]
        r = (lv & 15) | (hv & 15) << 4

        if self.trace is not None:
            self.trace.append((self.cycles, ab, db, cw))

        # --- commit (B→C) ---
        if cw & isa.MEMW:
            self.bus.write(ab, db)
        old_ar = self.ar
        if ddst == 1:
            self.ir = db
        elif ddst == 2:
            self.a = r
        elif ddst == 3:
            self.x = (self.x & 0xFF00) | db
        elif ddst == 4:
            self.x = (self.x & 0x00FF) | db << 8
        elif ddst == 5:
            self.ar = (self.ar & 0xFF00) | db
        elif ddst == 6:
            self.ar = (self.ar & 0x00FF) | db << 8
        if cw & isa.FL:
            self.z = (hv >> 4) & 1
            self.c = clo | ((hv >> 5) & 1)
            self.n = (hv >> 6) & 1
            self.v = hv >> 7
        if cw & isa.PCLD:
            self.pc = old_ar
        elif cw & isa.PCINC:
            self.pc = (self.pc + 1) & 0xFFFF
        if cw & isa.ARINC:
            self.ar = (self.ar + 1) & 0xFFFF
        if cw & isa.XINC:
            self.x = (self.x + 1) & 0xFFFF
        if cw & isa.SPCNT:
            self.sp = (self.sp + (-1 if cw & isa.SPDN else 1)) & 0xFF
        self.step = 0 if cw & isa.NEXT else (self.step + 1) & 15
        self.cycles += 1
        self.bus.tick(1)
        if cw & isa.HALT:
            self.halted = True
        return cw

    def instruction(self):
        """Bir komutu FETCH dahil çalıştırır; harcanan çevrimi döndürür."""
        start = self.cycles
        self.cycle()
        while self.step != 0:
            self.cycle()
        return self.cycles - start

    def run(self, max_cycles=10_000_000):
        while not self.halted and self.cycles < max_cycles:
            self.cycle()
        return self.cycles

    def state(self):
        return dict(pc=self.pc, a=self.a, x=self.x, sp=self.sp,
                    z=self.z, c=self.c, n=self.n, v=self.v)
