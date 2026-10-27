# Design proposal "MIN-CHIP": ISA v0 + datapath + control unit
Priority: minimum chip count and wiring (team of 2, ~16 build weeks, 30k TRY).

## 0. Key decisions (skeleton, written first; details below)
1. One user accumulator A + hidden temp T. ALU = 2x SST39SF010A nibble ROMs (X=A, Y=T) that drive the data bus directly; they also produce C/Z/N/V and constants.
2. Data bus has only two CPU-side sources: ALU or MEMORY (ROM/RAM/IO). One control bit DS selects -> contention impossible, no 74HC154.
3. Address bus: PC (4x 74HC161 + 2x 74HC541) or MAR (2x 74HCT574, tri-state). PC loads 16 bits from the address bus (jump = PC <- MAR).
4. No hardware stack pointer: non-recursive C, static locals; CALL writes an explicit return address into the callee's static return slot; RET = indirect jump.
5. Control bit F forces memory A0=1 -> 16-bit pointer/slot reads from 2-byte-aligned variables without any incrementer hardware.
6. 16-bit control word from 2 microcode flashes (addr = opcode 8 + step 4 + flags 4 + bank 1), latched by 2x 74HCT273 on the falling edge (cleared at reset = safe NOP); one 74HC138 decodes the destination; fetch = 1 microstep.
7. One 25.175 MHz oscillator for everything: CPU clock = dot clock / 8 = 1.573 MHz (synchronous to VGA), or 555 / single step / Arduino; HALT, breakpoint and VRAM-write stall stop the clock in its low phase; BUSREQ = Arduino holds reset and takes the buses.
8. ROM 32K + RAM AS6C62256 + VRAM AS6C62256 (2K used) behind 3x 74HC157 address mux + 74HCT541 data buffer; a CPU write to VRAM outside the vertical write window stalls the clock until the window opens.
9. VGA sync/blank/write-window from a timing ROM (SST39SF010A) + 74HCT377 register that loads on the same dot-clock edge as the 74HC166 (pipeline aligned for free); 74HC161 mod-8 dot counter + 2x 74HC4040; font ROM -> 74HC166; green monochrome.
10. PS/2: 2x 74HC164 start-bit-marker receiver, 74HC540 read buffer, clear-on-read via the 164 reset; keyboard inhibited (KCLK held low by a 2N7000) while a byte waits.

(sections 1-10 follow)

## 1. Programmer's model

| Register | Width | Visible | Implementation / notes |
|---|---|---|---|
| A | 8 | yes | Accumulator, the only user data register. ALU X operand. |
| PC | 16 | yes (jumps) | 4x 74HC161. Reset -> 0000h. |
| Flags C Z N V | 4 | yes (branches) | Written only by ALU steps that assert FL. |
| T | 8 | hidden | ALU Y operand; holds every memory/immediate operand. |
| MAR | 16 | hidden | MARH:MARL, data-address register, tri-state onto address bus. |
| IR | 8 | hidden | opcode, feeds microcode ROM address. |
| STEP | 4 | hidden | microstep counter. |

No stack pointer, no index register, no interrupts. Return addresses live in static per-function slots (Section 9).

Flags (ALU-generated, so the definitions are free):
- C: carry out of bit 7 for ADD/ADC/INC; for SUB/SBC/CMP/CPC/DEC C=1 means no borrow (A >= operand unsigned, 6502/ARM convention); shifted-out bit for shifts; unchanged by AND/OR/XOR/NOT/TST/PASS.
- Z: result == 0. For the carry-chained ops ADC, SBC, CPC: Z = Z_old AND (result == 0) (AVR-style), so after a 2-byte operation Z describes the whole 16-bit result.
- N: bit 7 of result. V: two's-complement overflow for ADD/ADC/SUB/SBC/CMP/CPC/INC/DEC, 0 for logic/shift ops.
- Signed less-than = N XOR V (evaluated in microcode, BLT/BGE).
- Loads (LDA) and stores do NOT change flags (the ALU is not in the path); use TST after a load if needed. Instructions marked "clobbers flags" use the ALU for address arithmetic.

Addressing modes:
| Mode | Syntax | Effective address / operand |
|---|---|---|
| implied | `SHL` | A |
| immediate | `#n` | next byte |
| absolute | `abs` | 16-bit address in the instruction |
| absolute + A | `abs,A` | abs + A (A = unsigned 8-bit index; carry ripples into the high byte). Loads only. |
| pointer | `[p]` | mem16[p]; p = address of a 2-byte-aligned (even) pointer variable |
| pointer, high byte | `[p]` with LDAH/STAH | mem16[p] OR 1 (= +1 for the even address of a 16-bit object) |
| pointer + A | `[p],A` | mem16[p] + A. Loads only. |
| memory-indirect jump | `JMP [p]` | PC = mem16[p] (used for RET; also jump tables in assembly) |

Alignment rule enforced by the compiler/assembler: every 2-byte object (int, pointer, return slot) sits at an even address. This is what lets one control bit (F, forces memory A0=1) replace an address incrementer.

## 2. Instruction set (53 instructions)

"Steps" = total clock cycles including the 1-step fetch. 1 step = 1 CPU clock (0.636 us at 1.573 MHz).
Opcode map: binary ALU ops are `k<<4 | mode` (k=1..9, mode 0=#imm, 1=abs); the rest are grouped by row. The microcode decodes all 8 bits, so the numbering is only for readability. 00h = NOP and FFh = HLT, so running into erased flash (FFh) halts the machine.

| Opcode | Mnemonic | Bytes | Steps | Effect | Flags |
|---|---|---|---|---|---|
| 10/11 | ADD #n / abs | 2/3 | 3/5 | A = A + M | C Z N V |
| 20/21 | ADC #n / abs | 2/3 | 3/5 | A = A + M + C | C Zc N V |
| 30/31 | SUB #n / abs | 2/3 | 3/5 | A = A - M | C Z N V |
| 40/41 | SBC #n / abs | 2/3 | 3/5 | A = A - M - !C | C Zc N V |
| 50/51 | AND #n / abs | 2/3 | 3/5 | A = A & M | Z N, V=0 |
| 60/61 | OR #n / abs | 2/3 | 3/5 | A = A \| M | Z N, V=0 |
| 70/71 | XOR #n / abs | 2/3 | 3/5 | A = A ^ M | Z N, V=0 |
| 80/81 | CMP #n / abs | 2/3 | 3/5 | flags of A - M | C Z N V |
| 90/91 | CPC #n / abs | 2/3 | 3/5 | flags of A - M - !C | C Zc N V |
| A0 | LDA #n | 2 | 2 | A = n | - |
| A1 | LDA abs | 3 | 4 | A = mem[abs] | - |
| A2 | LDA abs,A | 3 | 7 | A = mem[abs + A] | clobbered |
| A3 | LDA [p] | 3 | 7 | A = mem[mem16[p]] | - |
| A4 | LDAH [p] | 3 | 7 | A = mem[mem16[p] \| 1] | - |
| A5 | LDA [p],A | 3 | 9 | A = mem[mem16[p] + A] | clobbered |
| B1 | STA abs | 3 | 4 | mem[abs] = A | - |
| B3 | STA [p] | 3 | 7 | mem[mem16[p]] = A | - |
| B4 | STAH [p] | 3 | 7 | mem[mem16[p] \| 1] = A | - |
| B8 | STI abs,#n | 4 | 5 | mem[abs] = n (A untouched) | - |
| C0 | INC | 1 | 2 | A = A + 1 | C Z N V |
| C1 | DEC | 1 | 2 | A = A - 1 | C Z N V |
| C2 | NOT | 1 | 2 | A = ~A | Z N, V=0 |
| C3 | SHL | 1 | 2 | C <- A7..A0 <- 0 | C Z N, V=0 |
| C4 | ROL | 1 | 2 | C <- A7..A0 <- C | C Z N, V=0 |
| C5 | SHR | 1 | 2 | 0 -> A7..A0 -> C | C Z N, V=0 |
| C6 | ROR | 1 | 2 | C -> A7..A0 -> C | C Z N, V=0 |
| C7 | ASR | 1 | 2 | A7 -> A7..A0 -> C | C Z N, V=0 |
| C8 | TST | 1 | 2 | flags of A | Z N, V=0 |
| C9 | INC abs | 3 | 5 | mem[abs] += 1 (A untouched) | C Z N V |
| CA | DEC abs | 3 | 5 | mem[abs] -= 1 (A untouched) | C Z N V |
| CB | INS | 1 | 2 | A = KRDY<<7 \| VWIN (I/O status, Section 6.2) | Z N, V=0 |
| D0 | JMP abs | 3 | 4 | PC = abs | - |
| D1 | JMP [p] | 3 | 7 | PC = mem16[p] (RET = `JMP [f_ret]`, jump tables) | - |
| D2 | CALL slot,ret,f | 7 | 10 | mem16[slot] = ret; PC = f | - |
| E0 | BEQ abs | 3 | 4 / 3 | if Z | - |
| E1 | BNE abs | 3 | 4 / 3 | if !Z | - |
| E2 | BCS abs (=BHS, unsigned >=) | 3 | 4 / 3 | if C | - |
| E3 | BCC abs (=BLO, unsigned <) | 3 | 4 / 3 | if !C | - |
| E4 | BMI abs | 3 | 4 / 3 | if N | - |
| E5 | BPL abs | 3 | 4 / 3 | if !N | - |
| E6 | BLT abs (signed <) | 3 | 4 / 3 | if N != V | - |
| E7 | BGE abs (signed >=) | 3 | 4 / 3 | if N == V | - |
| 00 | NOP | 1 | 2 | - | - |
| FF | HLT | 1 | 2 | stop clock after this instruction; CONTINUE resumes, RESET restarts | - |

Count: 18 ALU-binary + 6 loads + 4 stores + 9 accumulator ops + INS + 2 memory INC/DEC + 3 jumps/calls + 8 branches + NOP + HLT = **53**.
Zc = chained zero flag (Z_old AND result==0). Branch "4 / 3" = taken / not taken. Branches are absolute (no PC-relative adder needed).
`CALL slot,ret,f` is normally written `CALL f` and the assembler fills in `slot = f_ret` (the callee's static return slot) and `ret = address of the next instruction`. The CPU cannot read PC onto the data bus (that would cost 2x 74HC541), so the return address is carried as an immediate.
Deliberately absent: stack/PUSH/POP, interrupts, PC-relative branches, hardware multiply. Compares cover all six C relations: `>` and `<=` are emitted with the operands swapped. 16-bit compare = `CMP lo` + `CPC hi`, after which Z, C and N^V describe the whole 16-bit comparison.

## 3. Datapath

### 3.1 Buses
- **Data bus D7..0** (8 lines). CPU-side drivers: (a) memory/IO devices when DS=0 (one device at a time, chosen by address decode), (b) the two ALU ROMs when DS=1. DS is one control bit, so the ALU's /OE and the memory /OE are complementary and **cannot both be active**. The baseline's 4-bit source field + 74HC154 is dropped: there are only two source classes, and the 74HC154 in DIP is now scarce and expensive (TI DIP versions obsolete; ~116 TRY locally). Loaders: A, T, IR, MARL, MARH, RAM, VRAM buffer, LED port.
- **Address bus A15..0** (16 lines). Drivers: PC through 2x 74HC541 (AS=0) or MAR (2x 74HCT574 tri-state outputs, AS=1); the Arduino during BUSREQ. Listeners: ROM/RAM/IO decode, PC D-inputs (jump), VRAM address mux, breakpoint comparators, Arduino.
- Private nets (no bus): A->ALU X, T->ALU Y, ALU carry chain (Cmid, Zlo, Aux), ALU-H flags->flag register, flags->microcode ROM + ALU, IR->microcode ROM, memory A0' = A0 OR F (ROM and RAM A0 pins only).

### 3.2 Registers
| Reg | Part | Load (all synchronous) | Inc/dec | Output goes to |
|---|---|---|---|---|
| A | 74HCT377 | D = data bus, /E = /LD_A (138 Y1), CP = CLK rising | via ALU (INC/DEC) | ALU-L/ALU-H X inputs (always on) |
| T | 74HCT377 | D = data bus, /E = /LD_T (Y2), CP = CLK rising | via ALU (INCY/DECY) | ALU Y inputs (always on) |
| IR | 74HCT377 | D = data bus, /E = /LD_IR (Y3), CP = CLK rising | - | microcode ROM A4..A11 |
| MARL, MARH | 2x 74HCT574 | D = data bus; CP = NOR(/CLK, /LD_MARx) (138 Y4/Y5 + one 74HC02 gate each) | - (F bit gives +1 on even addresses) | address bus, /OE = NOT AS |
| PC | 4x 74HC161 | /PE = /LD_PC (Y6), D = **address bus** (jump = PC <- MAR in one step); CP = /CLK (counts and loads on the CLK **falling** edge) | CEP = PCI on all four, CET chained from RCO | 2x 74HC541 -> address bus, /OE1 = AS, /OE2 = BUSREQ (no gate) |
| Flags | 74HCT173 | D = ALU-H D4..D7 (C,Z,N,V), /E1 = /FL, /E2 = 0, OE pins = 0, MR = 0 | - | microcode ROM A12..A15; C,Z -> ALU-L Cin, Zin |
| STEP | 74HC161 | /PE = /SR (D = 0000), /MR = /RESET, CP = CLK rising | counts every cycle | microcode ROM A0..A3 |

Readable back onto the data bus: **A** (ALU op PASSX) and **T** (PASSY) only. PC, MAR, IR, flags and STEP are not readable by software; branches test the flags. The Arduino sees PC/MAR on the address bus and the control word on its own pins.

Deviations, justified:
1. **MAR = 74HCT574 with a gated clock** (2 chips + 2 NOR gates instead of 2x 74HCT377 + 2x 74HC541). Nothing in 74HC DIP gives both a clock enable and tri-state outputs in 8 bits. Safety argument: /LD_MARx changes only just after the falling edge, while /CLK=1, so NOR(/CLK, /LD) is held at 0 and cannot glitch. The resulting MAR clock edge lags CLK by about 15 ns (inverter + NOR), which is harmless because (a) the PC changes on the falling edge, so a PC-addressed byte stays valid well past the rising edge; (b) when the MAR loads from MAR-addressed memory, its own output change is what moves the address (self-timed, longer than the hold time); (c) a microcode rule, checked by the generator: **a step with DST=MARL/MARH never asserts FL**, so the ALU inputs cannot change under a MAR load. If the team wants zero gated clocks: replace each 574 with 377+541 (+2 chips), nothing else changes.
2. **PC counts on the falling edge** (/CLK). The rising edge captures `mem[PC]` (opcode/operand) and the following falling edge advances PC, which removes the classic same-edge hold race. A PC-addressed read still gets a full half-cycle (Section 5).

### 3.3 ALU: 2x SST39SF010A as nibble lookup tables (ALU-L, ALU-H)
| ALU-L pin | signal | ALU-H pin | signal |
|---|---|---|---|
| A0-A3 | A0..A3 (X lo) | A0-A3 | A4..A7 (X hi) |
| A4-A7 | T0..T3 (Y lo) | A4-A7 | T4..T7 (Y hi) |
| A8 | Cin = flag C | A8 | Cmid (from ALU-L D4) |
| A9 | Zin = flag Z | A9 | Zlo (from ALU-L D5) |
| A10 | X4 = A4 (for right shifts) | A10 | Aux (from ALU-L D6) |
| A11-A15 | AOP0..4 (control word) | A11-A15 | AOP0..4 |
| A16 | VWIN_s (status) | A16 | KRDY_s (status) |
| D0-D3 | **data bus D0..D3** | D0-D3 | **data bus D4..D7** |
| D4/D5/D6 | Cmid / Zlo / Aux (private, 10k pull-downs) | D4/D5/D6/D7 | C / Z / N / V -> 74HCT173 (10k pull-downs) |
| /OE | ALU_OE_n = NOT DS | /OE | same |
| /CE, /WE | GND, VCC | | |

Both ROMs output straight onto the data bus, so no 74HC541 is needed. Their private outputs float when DS=0, so 7 pull-down resistors hold them; they are only consumed in steps with DS=1. Cmid carries the carry into bit 4 (or C for ROR, or X3 for SHL/ROL); Aux = X0 for right shifts, which becomes the final C; Zlo = (R3..0 == 0) AND (Zin if op is chained).

ALU op codes (AOP, 5 bits, 21 used; the table generator in isa.yaml produces both ROM images):
| AOP | name | R | C out | Z | N | V |
|---|---|---|---|---|---|---|
| 0 | PASSX | X | Cin | R==0 | R7 | 0 |
| 1 | PASSY | Y | Cin | R==0 | R7 | 0 |
| 2 | ADD | X+Y | carry | R==0 | R7 | ovf |
| 3 | ADC | X+Y+Cin | carry | Zin & R==0 | R7 | ovf |
| 4 | SUB | X+~Y+1 | no-borrow | R==0 | R7 | ovf |
| 5 | SBC | X+~Y+Cin | no-borrow | Zin & R==0 | R7 | ovf |
| 6/7/8 | AND/OR/XOR | X op Y | Cin | R==0 | R7 | 0 |
| 9 | NOTX | ~X | Cin | R==0 | R7 | 0 |
| 10/11 | INCX/DECX | X+1 / X-1 | carry / no-borrow | R==0 | R7 | ovf |
| 12/13 | INCY/DECY | Y+1 / Y-1 | carry / no-borrow | R==0 | R7 | ovf |
| 14 | YADDC | Y+Cin | carry | R==0 | R7 | ovf |
| 15/16 | SHL/ROL | X<<1 \| (0 or Cin) | X7 | R==0 | R7 | 0 |
| 17/18/19 | SHR/ROR/ASR | X>>1 with b7 = 0 / Cin / X7 | X0 | R==0 | R7 | 0 |
| 20 | ZERO | 0 | Cin | 1 | 0 | 0 |
| 21 | IOST | KRDY<<7 \| VWIN (ROM A16 pins) | Cin | R==0 | R7 | 0 |
| 22-31 | spare | | | | | |

ALU ROM A16: ALU-H A16 = KRDY_s, ALU-L A16 = VWIN_s (= WIN_s1). For every AOP except IOST the image is identical in both A16 halves, and both inputs only change right after a CPU falling edge (synchronized), so they never disturb other operations.

CMP = SUB and CPC = SBC with no destination (flags only). TST = PASSX + FL. Constraint of the nibble split: no operation may need data from the other nibble except X4->ALU-L, and Cmid/Zlo/Aux->ALU-H. All ops above satisfy this.

### 3.4 Flag generation
All four flags come out of ALU-H (D4..D7) and are captured by the 74HCT173 at the rising edge when /FL=0. No XOR/NOR gate trees and no 74HC283: the ROM tables compute carry, chained zero, sign and overflow (V = (X7 == Y7') AND (R7 != X7), where Y7' is Y7 inverted for subtraction). The logic ops keep C by passing Cin through Cmid.

### 3.5 Address-bus sources and 16-bit moves
- AS = 0: PC (via 541s). AS = 1: MAR. BUSREQ forces both off (MAR is off because BUSREQ holds the CPU in reset, so AS=0; see Section 4.7).
- MAR is filled one byte per step from the data bus (operand bytes, pointer bytes, or ALU results such as index sums).
- PC is loaded 16 bits at once **from the address bus** while MAR drives it (DST=PC, AS=MAR). Every jump, branch, call and return therefore ends with `PC <- MAR`, and the PC needs no data-bus path at all.
- 16-bit data never moves as a unit. The compiler emits byte pairs; carry and chained Z make the pairs behave like 16-bit operations.
- Memory A0' = A0 OR F (one 74HC32 gate): with F=1 a MAR access reaches address|1, which is "+1" for the even addresses where all 2-byte objects live. This replaces a 16-bit incrementer (4 counter chips + 2 buffers).

## 4. Control unit

### 4.1 Microcode ROMs (2x SST39SF010A, MC0 and MC1, address lines bused together)
| ROM address | A0-A3 | A4-A11 | A12 | A13 | A14 | A15 | A16 |
|---|---|---|---|---|---|---|---|
| source | STEP0..3 | IR0..7 | C | Z | N | V | BANK (DIP switch, 0 = normal, 1 = test microcode) |

/CE = /OE = GND, /WE = VCC (programmed off-board with a TL866/T48). Image index = BANK<<16 \| V<<15 \| N<<14 \| Z<<13 \| C<<12 \| IR<<4 \| STEP. The generator writes the same sequence into all 16 flag copies except for the conditional branches.

### 4.2 Control word (16 bits, 2 ROMs, latched by 2x 74HCT273)
| Bit | Name | Active | Meaning |
|---|---|---|---|
| CW0-4 | AOP0..4 | - | ALU operation (Section 3.3); 0 in non-ALU steps |
| CW5 | DS | 1 = ALU | data-bus source: 0 = memory/IO (/OE active), 1 = ALU ROMs |
| CW6 | WR | high | memory write this step (only with DS=1, AS=1) |
| CW7 | AS | 1 = MAR | address-bus source: 0 = PC, 1 = MAR |
| CW8-10 | DST0..2 | - | 74HC138: 0 none, 1 A, 2 T, 3 IR, 4 MARL, 5 MARH, 6 PC<-address bus, 7 spare |
| CW11 | /FL | low | load C,Z,N,V from ALU-H |
| CW12 | PCI | high | PC+1 at the end of this step |
| CW13 | F | high | memory A0 forced to 1 |
| CW14 | /SR | low | step counter <- 0 at this rising edge (last step of the instruction) |
| CW15 | HLT | high | stop the clock |

The polarities are chosen so that the **all-zero word after reset is safe**: memory read at PC, no register load (DST=0), no write, no PC change, step held at 0 (/SR=0), flags <- 0 (pulled-down ALU lines), no halt. Active-low /FL and /SR drive the 74HCT173 /E1 and the 74HC161 /PE directly, so no inverters are needed.

Decode and glue that the control word needs: one **74HC138** (DST: Y1../LD_A, Y2 /LD_T, Y3 /LD_IR, Y4 /LD_MARL, Y5 /LD_MARH, Y6 /LD_PC; G1 = VCC, /G2A = /G2B = GND), 2 NOR gates (MAR clocks), 1 inverter (ALU_OE_n = NOT DS), 1 inverter (MAR_OE_n = NOT AS), 1 OR (A0' = A0 OR F). The PC buffers use their two enables (/OE1 = AS, /OE2 = BUSREQ), so they need no gate. Decoder glitches after the falling edge are harmless: the 377/161/173 enables are only sampled at the rising edge, and the NOR-gated MAR clocks are held low while /CLK = 1.

### 4.3 Step counter
74HC161 clocked by CLK rising edge, /MR = /RESET (asynchronous), /PE = /SR with D3..0 = 0000 (synchronous restart), CEP = CET = 1. Variable-length instructions: the last step asserts /SR together with its own action. The longest instruction (CALL) uses 10 of 16 steps.

### 4.4 Microsequences (exact; every sequence starts with step 0 = fetch)
Notation: `M[PC]->X+` = AS0 DS0 DST=X PCI. `M[MAR]->X` = AS1 DS0 DST=X. `M[MAR|1]` adds F. `op->X` = DS1 AOP=op DST=X. `op->M[MAR]` = AS1 DS1 WR AOP=op. `FL` = /FL low. `END` = /SR low. Non-memory steps keep DS=1 (ALU PASSX on the bus), so I/O ports with read side effects are never read by accident.

| Instruction | Steps after fetch (step 0 = `M[PC]->IR+` for all) |
|---|---|
| LDA #n | 1 `M[PC]->A+ END` |
| LDA abs | 1 `M[PC]->MARL+` 2 `M[PC]->MARH+` 3 `M[MAR]->A END` |
| LDA abs,A | 1 `M[PC]->T+` 2 `ADD->A FL` 3 `M[PC]->T+` 4 `YADDC->MARH` 5 `PASSX->MARL` 6 `M[MAR]->A END` |
| LDA [p] / LDAH [p] | 1 `M[PC]->MARL+` 2 `M[PC]->MARH+` 3 `M[MAR]->T` 4 `M[MAR\|1]->MARH` 5 `PASSY->MARL` 6 `M[MAR]->A END` (LDAH: `M[MAR\|1]->A END`) |
| LDA [p],A | 1-2 as above, 3 `M[MAR]->T` 4 `ADD->A FL` 5 `M[MAR\|1]->T` 6 `YADDC->MARH` 7 `PASSX->MARL` 8 `M[MAR]->A END` |
| STA abs | 1 `M[PC]->MARL+` 2 `M[PC]->MARH+` 3 `PASSX->M[MAR] END` |
| STA [p] / STAH [p] | 1-5 as LDA [p], 6 `PASSX->M[MAR] END` (STAH: `PASSX->M[MAR\|1] END`) |
| STI abs,#n | 1 `M[PC]->MARL+` 2 `M[PC]->MARH+` 3 `M[PC]->T+` 4 `PASSY->M[MAR] END` |
| op #n (ADD..XOR) | 1 `M[PC]->T+` 2 `op->A FL END` (CMP/CPC: `SUB/SBC->none FL END`) |
| op abs | 1 `M[PC]->MARL+` 2 `M[PC]->MARH+` 3 `M[MAR]->T` 4 `op->A FL END` |
| INC/DEC/NOT/shifts | 1 `op->A FL END` (TST: `PASSX->none FL END`) |
| INS | 1 `IOST->A FL END` |
| INC/DEC abs | 1 `M[PC]->MARL+` 2 `M[PC]->MARH+` 3 `M[MAR]->T` 4 `INCY/DECY->M[MAR] FL END` |
| JMP abs, Bcc taken | 1 `M[PC]->MARL+` 2 `M[PC]->MARH+` 3 `AS1 DS1 DST=PC END` |
| Bcc not taken | 1 `DS1 PCI` 2 `DS1 PCI END` |
| JMP [p] | 1-5 as LDA [p], 6 `AS1 DS1 DST=PC END` |
| CALL slot,ret,f | 1 `M[PC]->MARL+` 2 `M[PC]->MARH+` 3 `M[PC]->T+` 4 `PASSY->M[MAR]` 5 `M[PC]->T+` 6 `PASSY->M[MAR\|1]` 7 `M[PC]->MARL+` 8 `M[PC]->MARH+` 9 `AS1 DS1 DST=PC END` |
| NOP / HLT | 1 `DS1 END` / 1 `DS1 HLT END` |

Rules the microcode generator checks (each is a hazard argument from Sections 3 and 5): (R1) WR implies DS=1, AS=1, DST not MARx. (R2) DST=MARx implies no FL. (R3) FL implies DS=1. (R4) DST=PC and F each imply AS=1. (R5) a write step with FL must use an AOP whose result ignores Cin/Zin (INCY/DECY only). (R6) step 0 = fetch for all IR/flag values. (R7) every path reaches END within 16 steps. (R8) idle steps use DS=1.

### 4.5 Fetch
One cycle. The rising edge loads IR from mem[PC] and moves STEP 0->1. During the high phase, MC0/MC1 look up (new IR, step 1) in 70 ns, and the falling edge latches that word while PC increments. Because the step-0 word is identical for every opcode, it does not matter that the old IR is still in place while it is looked up.

### 4.6 Conditional branches
No condition-select hardware: C, Z, N, V are microcode address bits, so the generator writes the taken sequence for the flag combinations that satisfy the condition (BLT: N!=V, etc.) and the 2-step skip for the others. Taken = 4 cycles, not taken = 3.

### 4.7 Reset, HALT, BUSREQ
- **Reset**: /RESET = RC node (10k/10uF power-on + button + Arduino open-drain pull) through two 74HC14 Schmitt inverters (RESET and /RESET). It clears PC = 0000h, STEP = 0 and the control latch (safe word above). A/T/IR/MAR are don't-care because step 0 is fetch for every IR. Execution starts at ROM 0000h, with no vector. There is no SP to initialize. Reset release is benign at any clock phase: PCI=0 and /SR=0 while the latch is cleared.
- **HALT**: CLK = SRC AND RUN AND /WAIT (Section 5.1). The RUN flip-flop samples NOT(HLT OR BRK) at every CLK falling edge and is only set again by the CONTINUE button (synchronized) or RESET. HLT is executed (its END takes effect), RUN drops at the falling edge that ends the HLT step, so the clock freezes low with the next instruction's fetch word already latched. CONTINUE resumes after the HLT (so HLT doubles as a software breakpoint); RESET restarts at 0000h.
- **BUSREQ (Arduino program loading)**: the Arduino (1) pulls /RESET low, so the control latch reads AS=0, DS=0, WR=0, F=0 (MAR off because AS=0, ALU off because DS=0); (2) drives BUSREQ high into the PC buffers' /OE2; (3) overrides the MEM_OE_n and RAM_WE_n nodes, which the CPU drives through 1k series resistors (pull MEM_OE_n high while writing, pulse RAM_WE_n low per byte). It drives A15..0 and D7..0, writes RAM, optionally reads it back, then releases. The CPU restarts at 0000h, and the boot ROM jumps to 8002h if RAM 8000h/8001h holds A5h/5Ah. Unplugged, a 10k pull-down on BUSREQ makes the header inert, so the Arduino is not needed for the demo. Cost: 0 chips (resistors only).
- Passive tracing: the Arduino reads A15..0, D7..0 and CW15..0 at every rising edge, or supplies the CPU clock itself (clock-mux input 3) for slow cycle-by-cycle diffing against the microstep emulator.

## 5. Clocking and timing

### 5.1 Clock module
- **Sources** (one half of a 74HC153, select = 2 DIP switches with 10k pull-ups): I0 = CCLK = 1.573 MHz (25.175 MHz can -> 74HC74 /2 = 12.5875 MHz dot clock -> mod-8 74HC161 Q2 = dot/8, Section 7.1; exactly 50 % duty and synchronous to VGA); I1 = NE555 astable (~1 Hz-5 kHz pot) through a 74HC14; I2 = STEP push-button (RC + 74HC14 debounce); I3 = Arduino pin. SRC = mux output. Change the selector only while halted or in reset (a source switch can make a runt pulse).
- **Gating**: CLK = SRC AND RUN AND /WAIT (two 74HC08 gates), /CLK = 74HC04. RUN, /WAIT and the VRAM window synchronizer change only while SRC is low, so CLK never gets a runt pulse:
  - RUN = 74HC74 FF, CP = /CLK (CPU falling edge), D = NOR(HLT, BRK), /PRE = CONT_PULSE_n. It is clocked only while CLK runs, so once cleared it stays cleared. BRK = breakpoint match (Section 6.6).
  - CONTINUE one-shot = 2 FFs clocked by /SRC: K1 <- debounced CONTINUE button, K2 <- K1; CONT_PULSE_n = NAND(K1, /K2) is low for exactly one SRC cycle, starting right after an SRC falling edge, so holding the button cannot run past later breakpoints (in STEP mode: hold CONTINUE while pressing STEP). Reset: K1 /PRE = /RESET and K2 /CLR = /RESET force CONT_PULSE_n low, so RESET also sets RUN (no extra gate).
  - Window synchronizer, 3 FFs: WIN_s0 <- VWIN (from the VGA timing register) on the SRC **rising** edge, then WIN_s1 <- WIN_s0 and WIN_s2 <- WIN_s1 on SRC falling edges. In crystal mode VWIN changes at a character boundary, i.e. right at the SRC falling edge, so sampling it there would be a deterministic setup-time race; sampling at mid-cycle first gives 300 ns of margin, and in the asynchronous modes the pair WIN_s0/WIN_s1 is a normal two-stage synchronizer. WIN_s1 changes only just after SRC falling edges. /WAIT = OR(/VWR, WIN_s1) (/VWR = IO-decoder output for "VRAM write step", Section 6.1): a VRAM write step outside the window freezes CLK low until the window opens. VRAM address-mux select CPUSEL = WIN_s1 OR WIN_s2 (the mux stays on the CPU side for one extra cycle after the window closes, so a write that finished at the closing edge is never disturbed).
- This upgrades the baseline's "block writes outside the window" from **drop** to **stall**: a VRAM store simply waits for the window, so no write is ever lost and the C code needs no polling (polling VWIN with `INS` is still used for frame timing and to batch writes). Cost: 1.5x 74HC74 + two gates.
- Clock distribution: CLK net (3x 377, 173, STEP 161, RAM /WE NAND, LED-port 377: 7 loads) and /CLK net (2x 273, 4x PC 161, 2 MAR NORs, RUN FF, KRDY_s FF, VRAM /WE OR, 164 clear OR: 12 loads, so /CLK is split over two parallel 74HC04 gates), each net driven through a 47 ohm series resistor, wired as a short star; 100 nF on every chip. Logic levels: see the HCT note at the end of Section 5.

### 5.2 What happens on each edge (1 step = 1 CLK cycle, T = 636 ns at 1.573 MHz)
| Moment | Events |
|---|---|
| CLK falling | 2x 74HCT273 latch the next control word; PC (4x 161 on /CLK) counts (PCI) or loads from the address bus (DST=PC); RUN samples HLT/BRK; any write pulse ends (/WE rises). |
| low phase (T/2) | AS/F/DS settle; the address bus is driven by PC or MAR; memory, I/O or the ALU ROMs drive the data bus; MAR clocks are held low by /CLK. |
| CLK rising | A, T, IR (377), flags (173), STEP (161) capture; MARL/MARH capture ~15 ns later (NOR-gated); /WE goes low if WR=1. |
| high phase (T/2) | MC0/MC1 look up the word for (IR, STEP, flags); a write keeps /WE low for the whole phase. |

Main RAM /WE = NAND(CLK, WR) (via 1k, Arduino override); VRAM /WE = OR(/VWR, /CLK) (the stall guarantees the window is open). Safety: the address and F are set at the previous falling edge (T/2 = 318 ns before /WE falls; tAS = 0 for AS6C62256), WR steps never load MAR (rule R1), and /WE rises one gate delay after CLK falls while the address can only change after /CLK -> 273 -> buffer enable (>= 3 gate delays, ~35 ns typ); tAH = 0. Data comes from the ALU, which keeps driving until the 273 changes DS/AOP (tDH = 0). /WE therefore never overlaps an address change.

### 5.3 Critical paths (typical 74HC @ 5 V, 15-50 pF: gate 8, 74HC04 8, 273 17, 161 20, 541 10/15 enable, 574 15 enable, 138 18, 157 11, 377 setup 12 ns; flash tAA 70 / tOE 35; AS6C62256 tAA 55 / tOE 25)
| Path (must fit in one half-cycle) | Chain | ns |
|---|---|---|
| ALU step (low phase) | /CLK 8 + 273 17 + ALU-L 70 + ALU-H 70 + 377 setup 12 | **177** (worst-case datasheet max ~205) |
| RAM read via MAR | 8 + 17 + inverter 8 + 574 enable 15 + A0 OR 8 + decode 26 + RAM 55 + 12 | 149 |
| ROM read via MAR | same with flash 70 | 164 |
| Fetch / operand via PC | 8 + 161 20 + 541 10 + decode 26 + flash 70 + 12 | 146 |
| Microcode lookup (high phase) | 161/377/173 20 + MC flash 70 + 273 setup 12 - 8 (273 clocks on /CLK) | 94 |
| VGA char pipeline | see Section 7 | per dot |

Worst half-cycle need ~205 ns -> maximum 50 %-duty CPU clock ~2.4 MHz. **1.573 MHz (demo) has 55 % margin; 2 MHz (250 ns half-cycle) works** with an external 4 MHz can + spare FF /2 on source I3 or I0. dot/4 = 3.15 MHz does NOT (159 ns < 205 ns). The VRAM write window synchronizer makes any CPU clock frequency legal.

Hold races (all positive by construction): (1) registers capture on the rising edge while PC/control change only on the falling edge; (2) PC samples /PE, CEP and its D inputs (address bus) at the same falling edge where the 273 updates, but the 273 output and the bus switch arrive >= 25 ns after the edge vs. a 161 hold time of a few ns; (3) MAR's gated clock (Section 3.2); (4) /WE vs. address (5.2).

Logic levels (verified): SST39SF010A guarantees only VOH = 2.4 V @ -400 uA (TTL-compatible), below the 74HC VIH of 3.5 V. The flash output stage is CMOS and the loads here are pure CMOS (uA), so in practice it swings to ~5 V, but for a guaranteed design the chips that **receive flash/SRAM outputs** should be 74HCT: 2x HCT273 (control word), 3x HCT377 (A, T, IR), 2x HCT574 (MAR), HCT173 (flags), HCT377 (LED port), HCT541 (VRAM data), HCT377 (VGA timing register), and HCT166 (font shift register) if obtainable. HCT outputs are rail-to-rail CMOS, so mixing is free. If an HCT part cannot be found, HC works in practice: check VOH > 4.5 V with the scope on the first prototype. (74HC161 hold: 3 ns D->CP, 0 ns enables, per TI CD74HC161; 74HCT377 hold is a few ns at 4.5 V; it matters only for the A->ALU->A and flags->ALU->flags self-loops, see Section 10.)

## 6. Memory and I/O

### 6.1 Address decode (one 74HC20 + one 74HC138; no other gates)
| Region | Device | Select logic |
|---|---|---|
| 0000-7FFF | Program ROM SST39SF010A (32K window; ROM A15/A16 from 2 DIP switches = 4 program images) | /CE = A15; /OE = MEM_OE_n; /WE = VCC; A0 pin = A0' |
| 8000-EFFF | RAM AS6C62256 (28K used) | /CE = /RAM_CE = NAND4(A15, /HI, 1, 1); /OE = MEM_OE_n; /WE = RAM_WE_n; A0 pin = A0' |
| F000-F7FF | VRAM (write-only, second AS6C62256) | 138 Y6 = /VWR |
| F800-FFFF | I/O page (all addresses alias) | 138 Y1 = /KBD_RD (read), Y7 = /IOWR (write) |
- /HI = NAND4(A15, A14, A13, A12) (74HC20 gate 1). /RAM_CE = 74HC20 gate 2.
- 74HC138 #2 ("IO decoder"): A = A11, B = WR, C = DS, G1 = VCC, /G2A = /HI, /G2B = GND. Y1 = read of F800-FFFF (DS=0, WR=0, A11=1), Y6 = VRAM write step (DS=1, WR=1, A11=0), Y7 = I/O write step. Y0 (read F000-F7FF) is unused: VRAM reads return 00h from the 8x 10k data-bus pull-downs. Because DS and WR are inputs, no read/write qualification gates are needed and idle steps (DS=1, WR=0) select nothing.
- MEM_OE_n = DS through a 1k series resistor; RAM_WE_n = NAND(CLK, WR) through a 1k series resistor (the Arduino overrides both nodes during BUSREQ; Section 4.7 updated accordingly).

### 6.2 I/O registers (exact)
| Address | Access | Meaning |
|---|---|---|
| F000 + 64*row + col | write | VRAM: character code at row 0-29, col 0-39 (cols 40-63 exist but are never displayed). Writes stall until the vertical write window (6.4). |
| F800 (F800-FFFF) | read | KBD: last PS/2 scan-code byte (set 2, raw: make code, F0 = break prefix, E0 = extended prefix). Reading clears KRDY and releases the keyboard. |
| F800 (F800-FFFF) | write | LED port: 8 LEDs, bit 7 = left. |
| (instruction) | `INS` | A = KRDY<<7 \| VWIN; N = KRDY, Z = (A==0). VWIN = 1 during the vertical write window. Status bits enter the CPU through the spare A16 pins of the two ALU ROMs (ALU-H A16 = KRDY_s, ALU-L A16 = VWIN_s), so they cost **zero chips** instead of a 74HC125/541 + decode. |

Deviation, justified: the status bits are read with one instruction (`INS`, AOP 21 = IOST) instead of a memory-mapped status byte. Both inputs are synchronized to the CPU falling edge (KRDY_s, WIN_s1), so they never change the ALU ROM address in the middle of a step (an asynchronous ROM address change would corrupt every ALU operation, not only INS).

### 6.3 LED port
1x 74HCT377: D = data bus, /E = 138 Y7 (/IOWR), CP = CLK; Q0-7 -> 8 LEDs via 1k. Synchronous, no gated clock.

### 6.4 VRAM write path (stall-until-window)
- VRAM = AS6C62256: A0-A10 from 3x 74HC157 (A11-A14 = GND), /CE = GND, D0-7 = private VRAM bus (font ROM address + 74HCT541 output; never floating, because VRAM /OE is active whenever the 541 is not).
- 74HC157 select S = CPUSEL = WIN_s1 OR WIN_s2 (= NAND of the two FF /Q outputs, 74HC00). S=0: VGA address {row4..0 = V8..V4, col5..0 = H5..H0}; S=1: CPU A10..A0 (A10..A6 = row, A5..A0 = col). /G = GND.
- 74HCT541: D bus -> VRAM data, /OE1 = /VWR, /OE2 = /WIN_s1 (FF /Q): drives only in a VRAM write step whose window is open.
- VRAM /OE = NOR(/VWR, /WIN_s1) = high exactly while the 541 drives (no contention, no floating VRAM bus otherwise). VRAM /WE = OR(/VWR, /CLK) = low only in the high phase of the write step.
- Stall: /WAIT = OR(/VWR, WIN_s1) feeds the clock gate (Section 5.1). A VRAM store issued outside the window freezes CLK low with the address and data already on the buses; the CPU resumes at the first SRC rising edge after WIN_s1 rises, and that rising edge starts the /WE pulse. Address setup >= T/2 (mux switched at the falling edge before). At the closing edge WIN_s1 falls together with the end of the write, but CPUSEL stays high for one more cycle (WIN_s2), so the address cannot move under the ending /WE.
- Window = VGA lines 481-523 inclusive (43 lines = 1.37 ms per frame = ~2150 CPU cycles), from the VGA timing register (VWIN bit). It closes one full line before line 0 is fetched, so CPUSEL's extra cycle never shows on screen in crystal mode. With a slow (555/step) clock the display may show junk while CPUSEL is held, but writes stay correct.

### 6.5 PS/2 keyboard receiver (2x 74HC164, 74HC540, 2N7000, 1 FF)
- Inputs: KCLK, KDATA with 4.7k pull-ups to 5 V, each through a 74HC14 Schmitt inverter: /KCLK and /KDATA.
- Shift register: SR1, SR2 = 74HC164, CP = /KCLK (shifts on the KCLK falling edge, when PS/2 data is valid), SR1 DSA = /KDATA, DSB = VCC; SR2 DSA = SR1 Q7. Inverted data is shifted into a cleared (all-0) register, so the start bit (0) arrives as a 1 "marker".
- After exactly 11 clocks: SR2.Q2 = marker = **KRDY**; data bits D0..D7 sit at SR2.Q1, SR2.Q0, SR1.Q7 ... SR1.Q2 (inverted); parity at SR1.Q1, stop at SR1.Q0. The 74HC540 (inverting tri-state) restores true polarity: inputs from those 8 outputs -> D0..D7, /OE1 = 138 Y1 (/KBD_RD), /OE2 = GND.
- Inhibit: KRDY drives a 2N7000 that pulls KCLK low (PS/2 host inhibit). The keyboard buffers further keys and the register freezes, so a byte can never be overwritten.
- Clear on read: SR1/SR2 /MR = OR(Y1, /CLK) (74HC32): asserted during the high phase of the read step, i.e. after A captured the byte at the rising edge (164 /MR->Q ~20 ns + 540 ~10 ns >> 377 hold). KRDY falls, the inhibit releases, the keyboard sends the next byte.
- Synchronization: KRDY_s = 74HC74 FF, D = KRDY, CP = /CLK -> ALU-H A16. Data is frozen before KRDY_s can be seen, so the 8 data bits need no synchronizer.
- Resync: a spurious KCLK edge makes the marker arrive one clock early; the inhibit then lands inside the frame, the keyboard aborts and retransmits that byte (PS/2 rule for a host inhibit before the 11th clock), the CPU reads one bad byte, and the read clears the register, so the next frame is aligned again. Boot code does one dummy read of F800 (the 164s power up random).

### 6.6 Hardware breakpoint
2x 74HC688: P = A7..0 / A15..8, Q = 16 DIP switches (2x SIP 10k pull-ups). #1 /G = /LD_IR (138 #1 Y3, active only in fetch steps), #1 /P=Q -> #2 /G, #2 /P=Q = BRK_n, through an enable DIP switch (open = 10k pull-up = no break). BRK = NOT BRK_n (74HC04) -> RUN D = NOR(HLT, BRK). The CPU stops after fetching the opcode at the breakpoint address (IR shows the opcode, PC = address+1); CONTINUE resumes.

### 6.7 Arduino Mega debug header (not needed for the demo)
Reads: A15..0, D7..0, CW15..0, CLK (rising-edge interrupt or Arduino-generated clock on mux input I3). Drives (all through 1k series resistors or into pulled lines, so an unplugged header is inert): /RESET node (pull low), BUSREQ (10k pull-down) -> 74HC541 PC buffer /OE2 pins, MEM_OE_n node (pull high = inhibit reads while loading), RAM_WE_n node (pull low = write strobe), A15..0 and D7..0 (only during BUSREQ). Load sequence: assert /RESET and BUSREQ, write bytes, release; boot ROM checks a signature at 8000h/8001h (A5h, 5Ah) and jumps to 8002h.

## 7. VGA module (40x30 text, monochrome)

### 7.1 Clocks and counters
| Function | Part | Wiring |
|---|---|---|
| 25.175 MHz | oscillator can (ECS-100A-251.7 or equivalent, DIP-14/8) | -> 74HC74 /2 |
| Dot clock DCLK 12.5875 MHz | 74HC74 half (D = /Q) | 50 % duty |
| Dot counter (mod 8) | 74HC161, CP = DCLK, D3..0 = 1000, /PE = /TC (74HC04), CEP = CET = 1 | counts 8..15, reloads 8; TC = 1 during dot 7 of each character; **CCLK = Q2** (1.573 MHz, 50 %), also CPU clock source I0 |
| Character counter H (0..49) | 74HC4040 #1, CP = CCLK (counts on the falling edge = character boundary), MR = AND3(Q5, Q4, Q1) (count 50 -> async reset to 0) | Q0..Q5 = column |
| Line counter V (0..524) | 74HC4040 #2, CP = H.Q5 (falls once per line, at the 50 -> 0 reset), MR = AND4(Q9, Q3, Q2, Q0) (count 525 -> 0) | Q0..Q9 = line |
| Reset decode | 74HC21 (dual 4-input AND; AND3 = one input tied high) | |
The ripple counters' transient states never match the reset decodes (49->50 passes through 48; 524->525 changes only Q0), and the brief 50/525 states only exist for ~30 ns right after a character boundary, long before anything samples them.

### 7.2 Sync and blank: timing ROM (no comparators)
- SST39SF010A "TROM": A0..A5 = H, A6..A15 = V, A16 = GND (or a DIP switch for a test pattern image). Image generated by Python from the timing table, natural coordinates:
  - BLANK_n = 1 for H 0..39 and V 0..479.
  - /HSYNC = 0 for H 41..46 (front porch H = 40 = 8 dots, sync 6 chars = 48 dots, back porch H 47..49 = 24 dots; 400 dots total).
  - /VSYNC = 0 for V 490..491 (front porch 480..489 = 10 lines, back porch 492..524 = 33 lines).
  - VWIN = 1 for V 481..523 (CPU write window, 43 lines = 1.37 ms).
- Register: 74HCT377, D = TROM D0..D3 (+4 spare outputs), CP = DCLK, /E = /TC. It loads on exactly the same DCLK edge as the 74HC166 (the character boundary). Hold is safe: TROM's address only starts to change >= 35 ns after that edge (161 Q2 -> 4040 ripple), vs. a hold time of a few ns.

### 7.3 Character pipeline (one character of latency, compensated for free)
1. Boundary E0 (DCLK rising edge at the end of dot 7): the 166 loads the font byte prepared during the previous slot; the timing register loads TROM(previous H, V); Q2 falls, so H increments (and V, at the end of a line).
2. During the slot: H/V settle (<= 130 ns incl. reset ripple), 3x 74HC157 present {row = V8..V4, col = H5..H0} to the VRAM (11 ns), VRAM outputs the character code (55 ns), font ROM (A0..A2 = V3..V1 = font row, A3..A10 = character code, A11..A16 = GND) outputs the pixel row (70 ns). Ready ~270-370 ns after E0, needed at E0 + 636 ns.
3. Next boundary: the 166 loads it (/PE = /TC, CP = DCLK, DS = GND, /CE = GND, /MR = VCC) and shifts it out MSB first on Q7 over the next 8 dots (font bit 7 = leftmost pixel).
Because the video data and the registered sync/blank both lag the counters by exactly one character, the TROM is programmed in natural coordinates and everything lines up: no delay flip-flops.

### 7.4 Output
- Video: one 74HC08 gate, G = Q7 AND BLANK_n (blanked = black, aligned to the character boundary because the 166 and the timing register load on the same edge), through **430 ohm** into the monitor's 75 ohm (HC output ~4.6 V at 9 mA -> 4.6 x 75/505 = 0.68 V); R and B pins to GND. Green text on black. The spare 4th gate can drive B too (cyan); white needs one more gate, because one HC output cannot source 3 x 9 mA. (Colour per character later: attribute RAM, not in v1.)
- /HSYNC, /VSYNC: timing-register outputs through 100 ohm to DE-15 pins 13/14 (negative polarity per the table above). GND pins 5-8, 10.
- VRAM address mux, data buffer and write gating: Section 6.4. Software clears the 40x30 area at boot (VRAM powers up random); columns 40-63 are fetched only during blanking and never shown.
- Pixel geometry: 1 dot = 2 VGA pixels wide, each font row is shown on 2 lines (font row = V3..V1), character row = V8..V4, so 40x30 characters of 16x16 VGA pixels.

## 8. Chip count, breadboards, wiring

### 8.1 Per module
| Module | Parts (qty) | ICs |
|---|---|---|
| Registers + PC + MAR | HCT377 x3 (A, T, IR), HCT574 x2 (MARL/H), 74HC161 x4 (PC), 74HC541 x2 (PC -> address bus), HCT173 (flags), 74HC161 (STEP) | 13 |
| ALU | SST39SF010A x2 (ALU-L, ALU-H) | 2 |
| Control | SST39SF010A x2 (MC0, MC1), HCT273 x2 (control word), 74HC138 (DST) | 5 |
| Memory + decode | SST39SF010A (program ROM), AS6C62256 (RAM), 74HC20 (/HI, /RAM_CE), 74HC138 (I/O decoder) | 4 |
| I/O | HCT377 (LED port), 74HC164 x2 + 74HC540 (PS/2), 74HC688 x2 (breakpoint) | 6 |
| VGA | 74HC161 (dot), 74HC4040 x2, 74HC21, SST39SF010A (timing), HCT377 (timing register), 74HC157 x3, AS6C62256 (VRAM), HCT541 (VRAM data), SST39SF010A (font), 74HC166 | 13 |
| Clock, reset, glue | 74HC153 (clock mux), NE555, 74HC74 x4 (DCLK/2 + KRDY_s, RUN + K1, K2 + WIN_s0, WIN_s1 + WIN_s2), 74HC14, 74HC04, 74HC00, 74HC02, 74HC32, 74HC08 | 11 |
| **Total** | | **54 ICs** + 25.175 MHz can + 2N7000 |

Glue gate allocation (every gate used once, so the netlist is checkable):
- 74HC04: /CLK driver a, /CLK driver b, BRK = NOT BRK_n, /SRC, /TC (VGA), NOT AS (MAR /OE).
- 74HC00: RAM /WE = NAND(CLK, WR); CONT_PULSE_n = NAND(K1, /K2); ALU_OE_n = NAND(DS, DS); CPUSEL = NAND(/WIN_s1, /WIN_s2).
- 74HC02: MARL clock, MARH clock, RUN D = NOR(HLT, BRK), VRAM /OE = NOR(/VWR, /WIN_s1).
- 74HC32: A0' = A0 OR F, /WAIT = /VWR OR WIN_s1, VRAM /WE = /VWR OR /CLK, PS/2 clear = Y1 OR /CLK.
- 74HC08: CLK = SRC AND RUN, then AND /WAIT (2 gates), video G = Q7 AND BLANK_n, 1 spare (second colour channel, e.g. B for cyan; white needs a third gate because one HC output cannot source 3x 9 mA).
- 74HC14: RESET, /RESET, STEP debounce, CONTINUE debounce, KCLK, KDATA.
- 74HC20: /HI = NAND4(A15..A12), /RAM_CE = NAND4(A15, /HI, 1, 1). 74HC21: H reset AND3, V reset AND4.

Single part types for stocking: 7x SST39SF010A (ALU x2, microcode x2, program, timing, font: one programmer setting, one Python image generator), 2x AS6C62256.

Comparison with the baseline: no 74HC154 (DS is one bit), no 74HC283/74HC181/XOR tree (ROM ALU), no SP (2-4 chips), no PC-to-data-bus buffers (2 chips), no 16-bit address incrementer (F bit), no status-port buffer (ALU A16 pins), no sync/blank comparators (timing ROM), no pipeline-delay flip-flops (registered TROM shares the 166's load edge).

### 8.2 Breadboards (830-point; ~4 DIP-14/20 chips or ~2 DIP-28/32 + 1 small chip per board with room for wiring)
| Module | Boards |
|---|---|
| Clock, reset, run/halt, glue | 2 |
| PC + PC buffers + MAR | 2 |
| A, T, IR, flags, STEP | 2 |
| ALU ROMs | 1 |
| Microcode ROMs + control latch + DST decoder + CW LEDs | 2 |
| ROM, RAM, decode | 2 |
| PS/2, LED port, breakpoint + DIP switches | 2 |
| VGA timing (dot counter, 4040s, TROM, register) | 2 |
| VGA VRAM, mux, buffer, font ROM, 166, DAC | 2 |
| Bus LEDs / manual control panel: 16 DIP switches + 10k pull-downs that plug into the 273 D inputs in place of the (removed) microcode ROMs, so every single-step executes the hand-set control word; used to test each module before microcode exists | 1 |
| **Total** | **18** (buy 20: spares for prototyping) |

### 8.3 Wiring estimate
Data bus 8 lines x ~12 taps, address bus 16 x ~8, microcode address 17 x 2 ROMs, control word 16 x (ROM->latch + latch->loads ~3), ALU ROM pins ~40, VGA ~170, glue ~80, PS/2 ~30, LEDs + resistors ~90, power/decoupling ~110 (2 per IC) -> **~950 hand-cut jumpers**. At ~25 wires per person-hour incl. checking, ~40 person-hours of pure wiring: fits easily in 16 weeks for two people; most time goes to testing.

### 8.4 Rough cost (TRY, local prices found Oct 2026, incl. VAT)
ICs ~2,400 (7x SST39SF010A ~690, 2x AS6C62256 ~140, the rest 74HC/HCT ~1,350, 25.175 MHz can ~200) + 20 breadboards ~1,600 + wire/LEDs/switches/resistors/caps ~1,200 + PS/2 keyboard ~640 + connectors ~80 + Arduino Mega clone ~830 + T48 programmer ~4,360 + 5 V 3 A supply ~400 = **~11,500 TRY** (buy 1 spare of every 74xx type and 2 spare flashes: +~800). Leaves >15k TRY reserve.

## 9. C mapping

### 9.1 Supported subset ("C-lite", compiled by the team's Python compiler)
- Types: `char` / `unsigned char` (8-bit), `int` / `unsigned` (16-bit, two's complement), pointers (16-bit) to char/int, global 1-D and 2-D arrays with constant sizes, string literals, `const` tables in ROM. No `long`, float, struct (v2 candidate), union, bit-fields.
- Statements: if/else, while, do/while, for, break, continue, return (no goto); expressions: all arithmetic/logic/shift operators, all 6 relations signed and unsigned, `&&` `||` `!` (short-circuit), `?:`, assignment and compound assignment, `++`/`--`, unary `-` `~` `*` `&`, indexing, casts. `*` `/` `%` call runtime routines (`__mul16`, `__divmod16`, shift-and-add in assembly, ~300-700 cycles); multiplications by constant powers of 2 become shifts.
- Functions: any number of parameters, int/char/void return, **no recursion** (the compiler builds the call graph and rejects cycles) and no function pointers in v1 (no interrupts either, so no re-entrancy).
- Intrinsics (header `hw.h`): `KBD` = `*(volatile char*)0xF800`, `LEDS` (same address, write), `VRAM` = `(char*)0xF000` (row stride 64), `kbd_ready()` -> `INS; BMI`, `vwin()` -> `INS; AND #1`, `halt()` -> `HLT`.

### 9.2 Storage and calling convention: static frames ("compiled stack")
- Every function `f` gets a static frame in RAM: `f_ret` (2-byte return slot), parameters `f_p0, f_p1, ...`, locals, and compiler temporaries `f_t0, ...`. Every 2-byte object is at an even address (alignment rule from Section 1). The linker overlays the frames of functions that can never be active at the same time (call-graph analysis), as 8051/PIC C compilers do; with 28 KB of RAM even no overlay at all is fine for Snake.
- Call: the caller stores the arguments straight into the callee's parameter slots, then `CALL f` (= `CALL f_ret, <return address>, f`). Return: 16-bit results in the global `__rv` (2 bytes), 8-bit results in A (CALL and `JMP [p]` do not touch A, so a char result survives); then `JMP [f_ret]`.
- Why static instead of a stack: this CPU has no SP and no indexed-by-register addressing (deliberately, to save ~4-6 chips), so a stack local would cost a pointer access (7-9 cycles + pointer arithmetic) for every byte, while a static local is a plain 3-byte absolute operand (4-5 cycles). Recursion is not needed for Snake or the demo programs; a recursive function could later be supported by a software stack in the runtime (deliberately out of scope).
- Code conventions that make the ISA work: loads/stores never change flags (so carry survives `LDA`/`STA` between the byte halves of 16-bit arithmetic), but a load does not set Z/N either: the compiler emits `TST` before testing a freshly loaded byte.

### 9.3 Required code sequences (cycles at 1 step = 1 clock = 0.636 us)
`int a = b + c;` (globals):
```
LDA b       ; 4
ADD c       ; 5   C = carry out of the low byte
STA a       ; 4   (no flag change)
LDA b+1     ; 4   (no flag change)
ADC c+1     ; 5
STA a+1     ; 4
```
18 bytes, **26 cycles** (16.5 us).

`*p = x;` (`char *p`, `char x`; p is any pointer variable, the target may be any address):
```
LDA x       ; 4
STA [p]     ; 7
```
**11 cycles**. For `int *p`: `LDA x / STA [p] / LDA x+1 / STAH [p]` = 22 cycles (STAH writes to `*p | 1`, i.e. the high byte of the aligned int).

`if (x < y)` (signed int):
```
LDA x       ; 4
CMP y       ; 5   low bytes, C = no borrow
LDA x+1     ; 4
CPC y+1     ; 5   high bytes with borrow; N, V, chained Z describe the 16-bit compare
BGE else    ; 4 taken / 3 not taken   (N == V  <=>  x >= y)
  ...then part...
else:
```
**21-22 cycles**. Unsigned `<` uses `BCC` / `BCS`; `==` uses `BNE` on the chained Z; `>` and `<=` swap the operands.

`r = add(a, b);` with `int add(int u, int v) { return u + v; }`:
```
; caller                                  ; callee
LDA a     / STA add_p0                    add: LDA add_p0   ; 4
LDA a+1   / STA add_p0+1                       ADD add_p1   ; 5
LDA b     / STA add_p1                         STA __rv     ; 4
LDA b+1   / STA add_p1+1   ; 8 x 4 = 32        LDA add_p0+1 ; 4
CALL add                   ; 10                ADC add_p1+1 ; 5
LDA __rv  / STA r                              STA __rv+1   ; 4
LDA __rv+1/ STA r+1        ; 16                JMP [add_ret]; 7
```
Caller 58 + callee 33 = **91 cycles** (58 us), 45 bytes. (A peephole pass can make the callee store into `r` directly when it is called once.)

String to VRAM (`char *s, *v` static locals; `v = VRAM + row*64 + col`; `while (*s) *v++ = *s++;`):
```
loop: LDA [s]     ; 7
      TST         ; 2
      BEQ done    ; 3 (not taken)
      STA [v]     ; 7 (+ stall if outside the write window)
      INC s       ; 5
      BNE n1      ; 4 (taken except on page crossing)
      INC s+1     ;   (5, rarely)
n1:   INC v       ; 5
      BNE n2      ; 4
      INC v+1     ;   (5, rarely)
n2:   JMP loop    ; 4
done:
```
**41 cycles per character** (26 us); a 40-character line takes 1,640 cycles, which fits in one 2,150-cycle write window if the code first waits for the window (`INS / AND #1 / BEQ`).

### 9.4 Snake performance check
Per move (compiled, unoptimized estimate): keyboard poll + decode ~200 cycles, new head position + wall test ~150, board lookup `board[y][x]` with a 64-byte row stride (`y<<6 | x`, two 16-bit shifts or a row-pointer table, then `LDA [p],A`) ~150, ring-buffer head/tail update ~300, 2-3 VRAM writes ~150 + stall, food placement with an 8-bit LFSR ~300 -> **~1,500-5,000 cycles per move** (1-3 ms). At 8 moves/s the budget is 196,000 cycles per move, so the CPU is >95 % idle; the game loop paces itself by counting frames (rising edges of VWIN, 60 per second: one move every 6-7 frames). A full-screen clear (1,200 characters, ~40 cycles each incl. loop) takes ~23 frames = 0.4 s, done once per game.

## 10. Risks, omissions, early prototypes

### 10.1 Risks and mitigations
| # | Risk | Mitigation |
|---|---|---|
| 1 | ROM ALU = two cascaded 70 ns flash accesses, the critical path (177 ns typ, ~205 ns worst) | Prototype ALU-L/ALU-H + A/T first and measure at 1.573 and 2 MHz; 1.573 MHz leaves ~55 % margin. Fallback: CCLK/2 = 0.79 MHz (still >20x the Snake budget). |
| 2 | Flash/SRAM outputs are only TTL-level guaranteed (VOH 2.4 V) | HCT on every flash/SRAM-fed input (Section 5 note); scope-check VOH on day 1. |
| 3 | Gated MAR clock (NOR of /CLK and /LD) | Glitch-free by construction (enable changes only while /CLK = 1) and generator rule R2; fallback 2x 377 + 2x 541 (+2 chips, no other change). |
| 4 | Same-edge self-loops: A -> ALU -> A and flags -> ALU -> flags at the rising edge | New data reaches the D inputs only after 377/173 tpd + flash output hold, well above the few-ns hold time; verify on the scope; fallback: 330 ohm series resistors in the A/T/C/Z -> ALU ROM address lines (a few ns of extra delay against the input capacitance, no chips). |
| 5 | 25 MHz / 12.6 MHz signals on breadboards (ringing, crosstalk) | Oscillator, /2 FF, dot counter, 166 and timing register on one board with short wires, 47 ohm series resistors on DCLK, solid ground rails on both sides, 100 nF per chip. |
| 6 | Ripple-counter reset decoding in the VGA timing | Checked: no transient state matches 50 or 525; TROM outputs are only used through the timing register, which samples them at the next character boundary, ~500 ns after they settle. Scope HSYNC/VSYNC jitter early. |
| 7 | Clock gating (RUN, VRAM stall, CONTINUE) and the window synchronizer | All gate inputs change only while SRC is low; simulate in Digital with crystal, 555 and step sources, including a VRAM write that waits a whole frame. |
| 8 | PS/2 keyboards vary (some draw >100 mA, some USB keyboards need an active adapter) | Buy a genuine PS/2 keyboard; test the receiver standalone with LEDs/Arduino before CPU integration. |
| 9 | No recursion / no function pointers in C | Compile-time call-graph check with a clear error; Snake needs neither. A software stack can be added later in the runtime. |
| 10 | Microcode or ALU table bug | Everything is generated from `isa.yaml` by one Python script that also generates the emulator tables; the generator enforces rules R1-R8; the Arduino trace is diffed against the microstep emulator. BANK DIP switch (MC A16) selects a test microcode image without reprogramming. |
| 11 | Power: ~54 ICs incl. 7 flashes (~25 mA each active), 2 SRAMs, ~60 LEDs, keyboard -> ~0.7 A | 5 V 3 A regulated supply, power fed to every board from both ends, 10-47 uF per board. |
| 12 | Floating CMOS inputs | All unused gate inputs tied; DIP switches with pull-ups/downs; 8x 10k pull-downs on the data bus (only "nobody drives" case: reads of F000-F7FF); 7x 10k on the ALU private outputs; BUSREQ pull-down when the Arduino is absent. |

### 10.2 Deliberately left out (each would cost chips without being needed for the Snake demo)
Stack pointer, PUSH/POP and recursion; index registers; interrupts; PC-relative branches; reading PC/MAR/flags onto the data bus (CALL carries its return address as an immediate); a hardware 16-bit incrementer (the F bit plus 2-byte alignment replaces it); hardware multiply; colour and attributes; CPU reads of VRAM (the game keeps its own board array in RAM) and CPU VRAM writes outside vertical blanking; a memory-mapped status byte (the `INS` instruction via the ALU ROMs' A16 pins replaces it); PS/2 parity checking and host-to-keyboard commands (LEDs on the keyboard); 7-segment decoding (the LED port can drive one 7-segment digit directly with software-generated segment patterns). The 74HC154 bus-source decoder is replaced by the single DS bit.

### 10.3 Prototype early (in this order)
1. **Simulation weeks**: the full machine in Digital (74xx DIL library, ROMs loaded from the generated images), first with the instruction-level emulator as the reference, then microstep-level. Simulate the asynchronous clock modes and the VRAM stall explicitly.
2. **Build week 1-2, independent tracks**: (a) person 1: clock module + VGA timing chain alone (osc, 74, 161, 4040s, 74HC21, TROM, 377) until a monitor locks to a test pattern from TROM's spare outputs; (b) person 2: control latch + step counter + manual DIP control panel, then A/T + ALU ROMs; measure the ALU path and flash VOH on the scope.
3. PS/2 receiver on its own (LEDs on KRDY and the byte), then the VRAM/font path with the Arduino writing VRAM.
4. Then PC/MAR/memory, microcode, first programs from the Arduino (BUSREQ load), finally C programs and Snake.
