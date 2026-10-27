"""Komut seviyesi referans emülatörü.

Mikrokoddan ve ALU tablolarından bağımsız yazılmıştır: komutların anlamı burada
doğrudan Python ile tanımlı. Testler iki emülatörü aynı programlarla çalıştırıp
her komuttan sonra durumu karşılaştırır; fark mikrokod ya da tablo hatası demektir.
"""

from . import isa
from .alu import alu_ref

_ALU = {
    'ADD': 'ADD', 'ADC': 'ADC', 'SUB': 'SUB', 'SBC': 'SBC',
    'AND': 'AND', 'OR': 'OR', 'XOR': 'XOR',
    'CMP': 'SUB', 'CPC': 'SBC', 'BIT': 'PASSB',
}
_UNARY = {'INC', 'DEC', 'NOT', 'NEG', 'SHL', 'ROL', 'SHR', 'ROR', 'ASR', 'SEX'}


class RefEmu:
    def __init__(self, bus):
        self.bus = bus
        self.reset()

    def reset(self):
        self.pc = 0
        self.x = 0
        self.sp = 0xFF
        self.a = 0
        self.z = self.c = self.n = self.v = 0
        self.halted = False
        self.cycles = 0

    # --- yardımcılar -----------------------------------------------------
    def _rd(self, addr):
        return self.bus.read(addr & 0xFFFF)

    def _fetch(self):
        b = self._rd(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return b

    def _fetch16(self):
        lo = self._fetch()
        return lo | self._fetch() << 8

    def _alu(self, name, b):
        r, z, c, n, v = alu_ref(isa.ALUOP[name], self.a, b, self.c, self.z)
        self.z, self.c, self.n, self.v = z, c, n, v
        return r

    def _push(self, value):
        self.bus.write(isa.STACK_PAGE | self.sp, value)
        self.sp = (self.sp - 1) & 0xFF

    def _pop(self):
        self.sp = (self.sp + 1) & 0xFF
        return self._rd(isa.STACK_PAGE | self.sp)

    # --- yürütme ---------------------------------------------------------
    def instruction(self):
        """Bir komut çalıştırır; harcanan çevrimi döndürür."""
        opcode = self._fetch()
        ins = isa.INSTRUCTIONS.get(opcode)
        if ins is None:                               # tanımsız: HALT + MARK
            self.halted = True
            self.cycles += 2
            return 2
        m, mode = ins.mnemonic, ins.mode
        cycles = ins.cycles()

        if m in _ALU or m in ('LDA', 'STA'):
            addr = None
            if mode == '#':
                b = self._fetch()
            else:
                addr = self._fetch16() if mode == 'abs' else self.x
            if m == 'STA':
                self.bus.write(addr, self.a)
            else:
                if addr is not None:
                    b = self._rd(addr)
                if m == 'LDA':
                    self.a = b
                elif m in ('CMP', 'CPC', 'BIT'):
                    self._alu(_ALU[m], b)
                else:
                    self.a = self._alu(_ALU[m], b)
            if mode == '(X+)':
                self.x = (self.x + 1) & 0xFFFF
        elif m in _UNARY:
            self.a = self._alu(m, 0)
        elif m == 'TST':
            self._alu('PASSA', 0)
        elif m in ('CLC', 'SEC'):
            self._alu(m, 0)
        elif m == 'LDX':
            if mode == '#16':
                self.x = self._fetch16()
            else:
                addr = self._fetch16()
                self.x = self._rd(addr) | self._rd(addr + 1) << 8
        elif m == 'INX':
            self.x = (self.x + 1) & 0xFFFF
        elif m == 'TAXL':
            self.x = (self.x & 0xFF00) | self.a
        elif m == 'TAXH':
            self.x = (self.x & 0x00FF) | self.a << 8
        elif m in ('INCW', 'DECW'):
            addr = self._fetch16()
            first, second = ('INCB', 'ADCB0') if m == 'INCW' else ('DECB', 'SBCB0')
            self.a = self._alu(first, self._rd(addr))
            self.bus.write(addr, self.a)
            addr = (addr + 1) & 0xFFFF
            self.a = self._alu(second, self._rd(addr))
            self.bus.write(addr, self.a)
        elif m == 'PHA':
            self._push(self.a)
        elif m == 'PLA':
            self.a = self._pop()
        elif m == 'JMP':
            self.pc = self._fetch16()
        elif m == 'CALL':
            target = self._fetch16()
            self._push(self.pc >> 8)
            self._push(self.pc & 0xFF)
            self.pc = target
        elif m == 'RET':
            lo = self._pop()
            self.pc = lo | self._pop() << 8
        elif m == 'JMPI':
            addr = self._fetch16()
            self.a = self._rd(addr)
            self.pc = self.a | self._rd(addr + 1) << 8
        elif ins.cond is not None:
            target = self._fetch16()
            taken = bool(ins.cond(self.z, self.c, self.n, self.v))
            if taken:
                self.pc = target
            cycles = ins.cycles(taken)
        elif m == 'NOP':
            pass
        elif m == 'HALT':
            self.halted = True
        else:
            raise AssertionError(m)

        self.cycles += cycles
        self.bus.tick(cycles)
        return cycles

    def run(self, max_cycles=10_000_000):
        while not self.halted and self.cycles < max_cycles:
            self.instruction()
        return self.cycles

    def state(self):
        return dict(pc=self.pc, a=self.a, x=self.x, sp=self.sp,
                    z=self.z, c=self.c, n=self.n, v=self.v)
