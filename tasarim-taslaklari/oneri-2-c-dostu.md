# Design proposal "C-friendly" - ISA v0 + datapath + control unit

## 0. Key decisions (skeleton)
1. Machine model = accumulator machine tuned for a C compiler: 16-bit accumulator D = B:A (B = high byte), 16-bit pointer register X (counter: post-increment for free, loaded from D+offset by LEAX, not readable back), 8-bit hardware SP (fixed page 0xEF) for return addresses and push/pop temporaries.
2. Locals and params STATIC (compiler-allocated fixed RAM block per function, non-reentrant; call-graph overlay optional); expression temporaries on the hardware stack. No SP-relative mode: it would cost ~5 ICs, is no faster per access and ~35 % slower per call; recursion = compiler error.
3. Two internal buses: DB (8-bit data bus; drivers MEM, A, B, PCL, PCH, panel DIP) feeds ALU input X; ALU result bus R (always driven) feeds A, B, MARL, MARH, XL, XH. IR loads from DB.
4. ALU = 2x SST39SF010A nibble lookup ROMs (X = DB, Y = A or B via 2x 74HC157); ROM produces Z C N V incl. 16-bit Z chaining; shifts/rotates both ways in 1 step.
5. Address bus sources: PC, MAR, X (each 4x 74HC161), SP (2x 74HC191, high byte fixed 0xEF), each via 2x 74HC541; 2-bit field -> 74HC139.
6. Microcode: 3x SST39SF010A, 24-bit control word in 3x 74HC574 (tri-stateable -> manual DIP panel can drive the control lines). ROM address = flags(4) + opcode(8) + step(4); A16 = microcode-bank jumper.
7. Clock (deviation): control word AND all registers/counters change on the FALLING edge (end of microcycle); only IR and the step counter use the RISING edge (mid-cycle) so the microcode ROM has the new opcode/step before the next falling edge. RAM /WE = WR AND CLK-high (2nd half) -> pointer post-increment in the same step as a write. HOLD freezes CLK low (HALT, single-step, breakpoint, BUSREQ, VRAM wait).
8. VRAM write outside the window STALLS the CPU (no lost writes) - deviation from baseline "drop".
9. 74HC154 replaced by 74HC138 (TI DIP 154 obsolete; 3-bit fields).
10. Memory map = baseline; I/O registers at F800-F803.

## 1. Programmer's model

| Register | Width | Visible | Notes |
|---|---|---|---|
| A | 8 | yes | low byte of D; 8-bit accumulator (char) |
| B | 8 | yes | high byte of D |
| D = B:A | 16 | yes | int accumulator; function return value |
| X | 16 | load-only | pointer register; post-increment ([X+]) is free (counter chip); loaded by LDX or LEAX (X <- D + offset); cannot be read back |
| SP | 8 | push/pop only | stack in fixed page EF00-EFFF; empty-descending (SP points at the next FREE byte); reset to FF |
| PC | 16 | jumps only | reset to 0000 |
| F = Z C N V | 4 | via branches | see below |
| IR, MAR (16), step | - | hidden | MAR = temp address for absolute/indirect modes |

Flags (set only by instructions marked so; one LF bit loads all four):
- Z: result == 0. 16-bit ops chain it (Z = Z_hi & Z_lo), so Z is the true 16-bit Z.
- C: carry out of add; for subtract/compare C = 1 means NO borrow (6502/ARM convention: unsigned left >= right <=> C=1); shifts: the bit shifted out. Loads/logic ops preserve C.
- N: bit 7 of the (high) result byte.
- V: two's-complement overflow of add/sub; 0 after loads/logic/shifts.
- Conditions available as branches (all decoded in microcode, zero hardware): EQ NE CS/HS CC/LO MI PL VS VC, signed LT (N^V) GE GT (!Z & N==V) LE, unsigned HI (C & !Z) LS.

Addressing modes:
- implied/register (TAB, INCD, SHLD ...)
- immediate: #imm8 for A ops, #imm16 for D/X ops (little-endian: low byte first)
- absolute abs16 (all static variables, I/O registers, VRAM cells with constant address)
- pointer [X] and post-increment [X+] (byte: X+=1; word: X+=2); address arithmetic LEAX (X <- D + imm16 or D + mem16) gives base+index in one instruction
- indirect through a static pointer variable: LDAI/STAI abs (7 cycles, clobbers B) - a second pointer without a second register
- stack (PUSH/POP and pop-operand ALU ops, Small-C style expression temporaries)
- branches/calls: absolute 16-bit target (no relative mode: relative needs PC+offset through the ALU and is not faster here)

Deliberately NOT included: SP-relative / frame-pointer addressing (see section 9 for the numbers), interrupts, multiply/divide (library routines; Snake needs only shifts).

## 2. Instruction set (91 instructions)

### Encoding
- One opcode byte, then 0/1/2 operand bytes (little-endian). The opcode is used *directly* as 8 bits of the microcode ROM address, so there are no instruction fields to decode in hardware; the high nibble only groups instructions for humans: 0x misc/transfers, 1x-2x byte ops on A, 3x word load/store, 4x word ALU, 5x unary D, 6x stack, 7x-8x control flow. All 165 unused opcodes are microcoded as `F; HALT` (illegal-opcode trap, visible on the LEDs).
- Every instruction starts with the common fetch microstep **F** = `IR <- M[PC]; PC++` (1 cycle). "Cycles" below = total microcycles incl. F. 1 microcycle = 1 CPU clock (1 us at 1 MHz).

### Microstep notation (each `;`-separated item = one microcycle)
`aP/aM/aX/aS` address source PC / MAR / X / EF:SP (default aP). `M` = memory read onto DB. `src op -> dst` = DB source through ALU op into destination (PASS if no op given). `W(r)` = write register r to memory. `+P +M +X` = increment PC/MAR/X at the end of the step. `S` = SP count: down in a write step, up otherwise. `f` = load flags. `z` = 16-bit Z chaining. `$` = end of instruction. `L` = `aP M->MARL +P` (fetch low byte of an abs16 operand), `H` = `aP M->MARH +P` (high byte). `PCLD` = PCL <- MARL and PCH <- R bus simultaneously.

### Table
| Op | Mnemonic | B | Cyc | Microsteps after F | Flags |
|---|---|---|---|---|---|
| 00 | NOP | 1 | 2 | `$` | - |
| 01 | HALT | 1 | 2 | `HALT $` (clock stops with this word latched; CONTINUE resumes) | - |
| 02 | TAB (B<-A) | 1 | 2 | `A->B $` | - |
| 03 | TBA (A<-B) | 1 | 2 | `B->A $` | - |
| 04 | CLRB (zero-extend char) | 1 | 2 | `ZERO->B $` | - |
| 05 | SEXB (sign-extend A into B) | 1 | 2 | `SEXT(Y=A)->B $` | - |
| 06 | TDX (X<-D) | 1 | 3 | `A->XL; B->XH $` | - |
| 08 | LEAX #i16 (X <- D + imm: &array[i]) | 3 | 3 | `M ADD(Y=A)->XL +P f; M ADC(Y=B)->XH +P f z $` | Z C N V |
| 09 | LEAX abs (X <- D + mem16: p[i]) | 3 | 5 | `L; H; aM M ADD(Y=A)->XL +M f; aM M ADC(Y=B)->XH f z $` | Z C N V |
| 0B | INX | 1 | 2 | `+X $` | - |
| 0C | TSTD | 1 | 3 | `A f; B f z $` | Z N, V=0 |
| 0D | TSTA | 1 | 2 | `A f $` | Z N, V=0 |
| 10 | LDA #i8 | 2 | 2 | `M->A +P f $` | Z N, V=0 |
| 11 | LDA abs | 3 | 4 | `L; H; aM M->A f $` | Z N, V=0 |
| 12 | LDA [X] | 1 | 2 | `aX M->A f $` | Z N, V=0 |
| 13 | LDA [X+] | 1 | 2 | `aX M->A +X f $` | Z N, V=0 |
| 14 | STA abs | 3 | 4 | `L; H; aM W(A) $` | - |
| 15 | STA [X] | 1 | 2 | `aX W(A) $` | - |
| 16 | STA [X+] | 1 | 2 | `aX W(A) +X $` | - |
| 17 | STAI abs (store A through the static pointer variable at abs; clobbers B) | 3 | 7 | `L; H; aM M->B +M; aM M->MARH; B->MARL; aM W(A) $` | - |
| 26 | LDAI abs (load A through the static pointer variable at abs; clobbers B) | 3 | 7 | `L; H; aM M->B +M; aM M->MARH; B->MARL; aM M->A f $` | Z N, V=0 |
| 18/19 | ADDA #i8 / abs | 2/3 | 2/4 | `M ADD(Y=A)->A +P f $` / `L; H; aM M ADD->A f $` | Z C N V |
| 1A/1B | SUBA #/abs (A-=m) | 2/3 | 2/4 | as ADDA with SUB (R=Y-X) | Z C N V |
| 1C/1D | ANDA #/abs | 2/3 | 2/4 | AND | Z N, V=0 |
| 1E/1F | ORA #/abs | 2/3 | 2/4 | OR | Z N, V=0 |
| 20/21 | XORA #/abs | 2/3 | 2/4 | XOR | Z N, V=0 |
| 22/23 | CMPA #/abs | 2/3 | 2/4 | SUB, no destination | Z C N V |
| 24 | INCA | 1 | 2 | `A INC->A f $` | Z C N V |
| 25 | DECA | 1 | 2 | `A DEC->A f $` | Z C N V |
| 30 | LDD #i16 | 3 | 3 | `M->A +P f; M->B +P f z $` | Z N (16-bit), V=0 |
| 31 | LDD abs | 3 | 5 | `L; H; aM M->A +M f; aM M->B f z $` | Z N, V=0 |
| 32 | LDD [X+] | 1 | 3 | `aX M->A +X f; aX M->B +X f z $` | Z N, V=0 |
| 33 | STD abs | 3 | 5 | `L; H; aM W(A) +M; aM W(B) $` | - |
| 34 | STD [X+] | 1 | 3 | `aX W(A) +X; aX W(B) +X $` | - |
| 35 | LDX #i16 | 3 | 3 | `M->XL +P; M->XH +P $` | - |
| 36 | LDX abs | 3 | 5 | `L; H; aM M->XL +M; aM M->XH $` | - |
| 40/41 | ADDD #i16 / abs | 3/3 | 3/5 | `M ADD(Y=A)->A +P f; M ADC(Y=B)->B +P f z $` / `L; H; aM M ADD->A +M f; aM M ADC->B f z $` | Z C N V |
| 42/43 | SUBD # / abs (D-=m) | 3 | 3/5 | SUB / SBC | Z C N V |
| 44/45 | RSBD # / abs (D=m-D) | 3 | 3/5 | RSB / RSC | Z C N V |
| 46/47 | ANDD # / abs | 3 | 3/5 | AND / AND | Z N, V=0 |
| 48/49 | ORD # / abs | 3 | 3/5 | OR | Z N, V=0 |
| 4A/4B | XORD # / abs | 3 | 3/5 | XOR | Z N, V=0 |
| 4C/4D | CPD # / abs | 3 | 3/5 | SUB / SBC, no destination | Z C N V |
| 50 | INCD | 1 | 3 | `A INC->A f; B INCC->B f z $` | Z C N V |
| 51 | DECD | 1 | 3 | `A DEC->A f; B DECC->B f z $` | Z C N V |
| 52 | NEGD | 1 | 3 | `A NEG->A f; B NGC->B f z $` | Z C N V |
| 53 | COMD | 1 | 3 | `A NOT->A f; B NOT->B f z $` | Z N |
| 54 | SHLD | 1 | 3 | `A SHL->A f; B ROL->B f z $` | Z C N |
| 55 | SHRD (unsigned) | 1 | 3 | `B SHR->B f; A ROR->A f z $` | Z C N |
| 56 | ASRD (signed) | 1 | 3 | `B ASR->B f; A ROR->A f z $` | Z C N |
| 57 | CLRD | 1 | 3 | `ZERO->A f; ZERO->B f z $` | Z=1 |
| 58 | INCW abs (clobbers A) | 3 | 7 | `L; H; aM M INC->A f; aM W(A) +M; aM M INCC->A f z; aM W(A) $` | Z C N V |
| 59 | DECW abs (clobbers A) | 3 | 7 | same with DEC/DECC | Z C N V |
| 60 | PUSHD | 1 | 3 | `aS W(B) S; aS W(A) S $` | - |
| 61 | POPD | 1 | 4 | `S; aS M->A S f; aS M->B f z $` | Z N |
| 64 | ADDS (D=pop+D) | 1 | 4 | `S; aS M ADD(Y=A)->A S f; aS M ADC(Y=B)->B f z $` | Z C N V |
| 65 | SUBS (D=pop-D) | 1 | 4 | RSB / RSC | Z C N V |
| 66/67/68 | ANDS / ORS / XORS | 1 | 4 | AND / OR / XOR | Z N |
| 69 | CPS (flags of pop-D) | 1 | 4 | RSB / RSC, no destination | Z C N V |
| 70 | JMP abs | 3 | 3 | `L; M->R PCLD $` | - |
| 71-7E | Bcc abs: BEQ BNE BCS(BHS) BCC(BLO) BMI BPL BVS BVC BLT BGE BGT BLE BHI BLS | 3 | 3 | taken: `L; M->R PCLD $`  not taken: `+P; +P $` (choice made by the flag bits of the microcode address) | - |
| 7F | CALL abs | 3 | 5 | `L; aS W(PCH) S; aS W(PCL) S; M->R PCLD $` (pushes address of the target's high byte = return-1, like 6502 JSR) | - |
| 80 | RET | 1 | 5 | `S; aS M->MARL S; aS M->R PCLD; +P $` | - |

Count: 12 misc + 23 byte (incl. LDAI/STAI) + 7 word load/store + 14 word ALU + 8 unary + 2 memory inc/dec + 8 stack + 17 control = **91 instructions** (91 opcodes; 165 free for later, e.g. `LDD [X]`, `LDAZ abs`, a MUL step). X cannot be read back (no TXD/STX/PUSHX: saves 2 chips, see section 3); the compiler treats X as a scratch pointer that is recomputed, never spilled.

ALU op codes used above (5-bit field, section 3): PASS ADD ADC SUB SBC RSB RSC AND OR XOR INC INCC DEC DECC NOT NEG NGC SHL ROL SHR ROR ASR ZERO SEXT (24 of 32).

Rules the microcode generator checks (isa.yaml -> microcode.py asserts):
1. A write step (W) must not load the register that is driving DB, and must not use the IR destination.
2. No step may branch on flags written by the immediately preceding step of the same instruction (flags register updates on the same edge as the next control word is latched; see section 4).
3. Exactly one EOI per path; max 8 steps (step 0..7) for now (counter supports 16).

## 3. Datapath

### Buses
| Bus | Width | Driven by | Read by |
|---|---|---|---|
| DB (data bus) | 8 | exactly one of: MEM (ROM/RAM/IO /OE), A, B, PCL, PCH (each a 74HC541), panel DIP 541 (manual mode only) - chosen by the 3-bit DBS field through a 74HC138 | ALU input X, IR, RAM/VRAM/IO data inputs, LED bar, Arduino |
| R (ALU result) | 8 | ALU ROM data outputs, permanently enabled (never tri-stated, no contention possible) | A, B (377 D), MARL, MARH, XL, XH, PCH (161 P inputs), LED bar |
| Y (ALU 2nd operand) | 8 | 2x 74HC157: A or B (ALUY bit) | ALU ROM address |
| AB (address bus) | 16 | one 74HC541 pair: PC, MAR, X, or SP (low byte = SP, high byte = constant 0xEF from a 541 with hard-wired inputs) - 2-bit ABS field through half a 74HC139 | memory, address decode, breakpoint 688s, VRAM CPU-side mux, Arduino |
| MARL -> PCL | 8 | MARL 161 outputs (always on) | PCL 161 P inputs (for PCLD) |

DB has an 8x10k pull-down network so "no source" (DBS=0) reads 00 and no CMOS input floats. Every transfer between registers goes DB -> ALU(op) -> R -> register, so "move", "add", "shift" are the same kind of microstep and the ALU op simply defaults to PASS.

16-bit values move as two byte transfers, low byte first (little-endian in memory). Readable onto DB: A, B, PCL, PCH, MEM. Not readable (by design, not needed by C): X, MAR, SP, flags, IR (all shown on LEDs; flags testable by branches).

### Registers (all edge-triggered, no gated clocks)
| Reg | Chips | Clock | Load | Count | Drives |
|---|---|---|---|---|---|
| A, B | 1x 74HC377 each | /CLK (rises at CLK falling edge) | D <- R; /E (sync data enable) <- DST decoder | - | 157 (Y mux) always; DB via 1x 541 each |
| IR | 1x 74HC377 | CLK (rising) | D <- DB; /E <- DST decoder Y7 | - | microcode ROM A4-A11 |
| Flags ZCNV | 1x 74HC377 (4 bits used) | /CLK | D <- ALU flag outputs; /E <- /LF | - | microcode ROM A12-A15; Z->ALU-hi A15; C->ALU-lo A13 |
| MAR | 4x 74HC161 | /CLK | /PE (sync) <- DST Y3 (MARL chips) / Y4 (MARH chips); P <- R | CEP=MARI, CET chained from TC (sync 16-bit) | 2x 541 -> AB; MARL -> PCL inputs |
| PC | 4x 74HC161 | /CLK | /PE <- /PCLD (all 4 chips): PCL <- MARL, PCH <- R | CEP=PCI, CET chained | 2x 541 -> AB; 2x 541 -> DB |
| X | 4x 74HC161 | /CLK | /PE <- DST Y5 (XL) / Y6 (XH); P <- R | CEP=XI, CET chained | 2x 541 -> AB only (no DB readback: -2 chips; LEAX makes it unnecessary) |
| SP | 2x 74HC191 | /CLK | /PL (ASYNC) <- /RESET only, P tied 1 -> SP=FF | lower /CTEN <- NOT SPE; D/U <- WR (HIGH = down); upper /CTEN = NAND(SPE, MAX/MIN_lo) | 1x 541 -> AB low; constant-0xEF 541 -> AB high |

Datasheet facts relied on (checked): 74HC161 - synchronous parallel load (/PE low at rising CP), asynchronous /MR, count needs CEP=CET=1, TC = Q==15 AND CET. 74HC377 - /E is a synchronous data enable, outputs always active (no tri-state, which is why each needs a 541 to reach DB). 74HC191 - parallel load is ASYNCHRONOUS (/PL), counting on the LOW-to-HIGH CP edge; Nexperia: the LOW-to-HIGH transition of CE (/CTEN) must occur only while CP is HIGH and U/D may change only while CE or CP is HIGH. Here the 191 CP is /CLK and the control word changes ~20 ns *after* /CLK rises, i.e. while CP is HIGH - satisfied. (This is also why SP is the only register where an async load is acceptable: it is used only at reset.)

Why X is a counter and not a plain latch: `[X+]` post-increment costs 0 extra cycles, which makes string/array loops 2 cycles per byte (section 9). Why PCL loads from MARL while PCH loads from R: a taken jump/branch needs no extra "PC <- MAR" step (3 cycles instead of 4).

### ALU: two SST39SF010A lookup ROMs (nibble-sliced), 2x 74HC157 operand mux
Low ROM (bits 3..0)
- address: A0-A3 = X[3:0] (DB), A4-A7 = Y[3:0], A8-A12 = OP[4:0], A13 = Cin (C flag), A14 = X4, A15 = X7, A16 = 0
- data: D0-D3 = R[3:0], D4 = K (link to high nibble), D5 = Zlo (R[3:0]==0), D6 = Clo (C contribution), D7 unused

High ROM (bits 7..4)
- address: A0-A3 = X[7:4], A4-A7 = Y[7:4], A8-A12 = OP, A13 = K, A14 = Zlo, A15 = Z flag (registered), A16 = ZC (chain bit from control word)
- data: D0-D3 = R[7:4], D4 = Chi, D5 = Z, D6 = N, D7 = V

C_new = Chi OR Clo (one 74HC32 gate). Z = (R[7:4]==0) AND Zlo AND (ZC ? Zflag : 1). N = R7. V computed from X7, Y7, R7.

| OP | Name | R = | K (link) | C_new | V |
|---|---|---|---|---|---|
| 00 | PASS | X | - | C (preserved via Clo) | 0 |
| 01/02 | ADD / ADC | Y+X / Y+X+C | nibble carry | carry out | overflow |
| 03/04 | SUB / SBC | Y-X / Y-X-!C | nibble no-borrow | 1 = no borrow | overflow |
| 05/06 | RSB / RSC | X-Y / X-Y-!C | nibble no-borrow | 1 = no borrow | overflow |
| 07/08/09 | AND / OR / XOR | Y op X | - | preserved | 0 |
| 0A/0B | INC / INCC | X+1 / X+C | carry | carry | overflow |
| 0C/0D | DEC / DECC | X-1 / X-!C | no-borrow | no-borrow | overflow |
| 0E | NOT | ~X | - | preserved | 0 |
| 0F/10 | NEG / NGC | 0-X / 0-X-!C | no-borrow | no-borrow | overflow |
| 11/12 | SHL / ROL | X<<1 / X<<1 OR C | X3 | X7 | 0 |
| 13/14/15 | SHR / ROR / ASR | X>>1, bit7 = 0 / C / X7 | ROR: C | X0 (via Clo) | 0 |
| 16 | ZERO | 00 | - | preserved | 0 |
| 17 | SEXT | X7 ? FF : 00 | - | preserved | 0 |
| 18-1F | spare (future: MULSTEP, nibble swap, BCD) | | | | |

Right shifts: the low ROM sees X4 (A14) so it can produce R3 = X4; ASR/SEXT see X7 (low ROM A15). Delay: low ROM 70 ns -> K/Zlo -> high ROM 70 ns = 140 ns worst case + 157 (~15 ns). Compared with a 74HC283/86/157 ALU (about 10 chips for add/sub/logic/shift-left/shift-right/flags) this is 2 ROMs + 2 muxes + 1 gate, every op is single-cycle, and adding an op later is a re-flash. ROM outputs glitch while inputs change - harmless, R is only sampled at the clock edge.

### Flag generation
All four flags come from the high ROM (plus C via the OR gate) and are registered together in the flag 377 when LF is set. Signed compare = SUB low byte, SBC+ZC high byte; branch conditions (LT = N xor V, GT = !Z and N == V, unsigned HI = C and !Z, ...) are evaluated *inside the microcode ROM* because Z C N V are microcode address bits - no comparator or condition-mux chip exists.

### Address-bus sources
ABS field: 00 PC, 01 MAR, 10 X, 11 EF:SP -> 74HC139 (half), its /G = BUSACK (so all four pairs float during BUSREQ). Each source = 2x 74HC541 (74HC245 with DIR tied high is a drop-in substitute: TR stock of DIP 541 is thin).

## 4. Control unit

### Microcode ROM address (3x SST39SF010A in parallel, same address lines)
| ROM pin | A0-A3 | A4-A11 | A12 | A13 | A14 | A15 | A16 |
|---|---|---|---|---|---|---|---|
| signal | step (74HC163 Q0-Q3) | IR opcode | Z | C | N | V | jumper (microcode bank 0/1, default 0) |

16 steps x 256 opcodes x 16 flag combinations = 64K words per bank. The bank jumper lets the students keep a known-good microcode and an experimental one in the same chips.

### Control word (24 bits, 3 ROMs -> 3x 74HC574 clocked by /CLK)
| Bit | Name | Meaning |
|---|---|---|
| 0-2 | DBS | DB source: 0 none (panel DIP in manual mode), 1 MEM (/RD), 2 A, 3 B, 4 PCL, 5 PCH, 6-7 spare (reserved: XL/XH readback can be added later with 2x 541 and no other change) -> 74HC138 #1 |
| 3-4 | ABS | address source: 0 PC, 1 MAR, 2 X, 3 EF:SP -> 74HC139 |
| 5-7 | DST | R/DB destination: 0 none, 1 A, 2 B, 3 MARL, 4 MARH, 5 XL, 6 XH, 7 IR -> 74HC138 #2 (active-low outputs = /E or /PE directly) |
| 8-12 | ALUOP | ALU op (section 3), to both ALU ROMs A8-A12 |
| 13 | ALUY | 0: Y=A, 1: Y=B (157 select) |
| 14 | ZC | chain Z for the 2nd byte of a 16-bit op (ALU-hi A16) |
| 15 | /LF | load flags (active low, straight to flag 377 /E) |
| 16 | PCI | PC++ (161 CEP/CET) |
| 17 | /PCLD | PC <- {R, MARL} (active low, straight to 161 /PE) |
| 18 | MARI | MAR++ |
| 19 | XI | X++ |
| 20 | SPE | SP count enable (lower 191 /CTEN via inverter, upper via NAND with lower MAX/MIN) |
| 21 | WR | memory write (also selects SP direction: write steps count down) |
| 22 | EOI | end of instruction (step counter synchronous clear) |
| 23 | HALT | stop the clock with this word latched |

Every one of the 3x8 bits is used. The 574 /OE pins are tied to MANUAL: in manual mode the latches float and a panel of 24 DIP switches with 10k pull resistors drives the control lines (and the panel 541 drives DB when DBS=0), so every module can be tested with a hand-set control word and the single-step button before any microcode exists. LEDs on all 24 lines (via 3x ULN2803 or simply 2.2k series resistors on 74HC outputs).

### Step counter
74HC163 (synchronous clear) clocked by CLK (rising edge, mid-microcycle), CEP=CET=1, /CLR = NOR(EOI, RESET). Clear is synchronous, so EOI acts at the rising edge of the last step and the ROM then outputs step 0 (fetch) in time for the next falling edge.

### Fetch (step 0, identical for all 256 opcodes and all flag values)
`DBS=MEM, ABS=PC, DST=IR, PCI` -> at the rising edge IR <- M[PC] and step 0->1; the microcode ROMs see the new opcode and settle; at the falling edge PC++ and the control word for step 1 is latched. Fetch costs 1 cycle and needs no decode delay step.

### Conditional branches
No hardware: Z C N V are microcode address bits, so for `Bcc` the ROM simply contains a different step-1/step-2 word for flag combinations where the condition is true (`L; M->R PCLD $`) or false (`+P; +P $`). 14 conditions incl. signed LT/GE/GT/LE and unsigned HI/LS. Constraint: the flag register updates on the falling edge, the same edge that latches the next control word, so a microstep can only branch on flags produced two or more steps earlier - always true for Bcc (the fetch sits in between).

### Reset
Power-on RC (100k/1uF) + button -> 74HC14 -> 74HC74 synchronizer clocked by /CLK (assert any time, release only right after a falling edge, i.e. at the start of a microcycle). /RESET does: PC 161 /MR (async) -> PC = 0000; SP 191 /PL (async) -> SP = FF (first push lands at EFFF); step counter /CLR (sync, the clock keeps running during reset); /WE gate disabled; HOLD sources ignored (so a random power-up control word with HALT cannot freeze reset). While reset is held the latched word is the fetch word (step 0) but PC is pinned at 0; on release the first fetch reads 0000. No control-word clear is needed (hence 574 instead of 273).

### HALT
The HALT bit is latched with the control word at the falling edge; the clock module then keeps CLK low (see 5), so the machine sits in the HALT step with all LEDs valid. CONTINUE (or STEP) releases it; the HALT step also has EOI, so execution continues at the next instruction.

### BUSREQ / BUSACK (Arduino debug board)
/BUSREQ is sampled by the clock module only in the low half after a falling edge, it holds CLK low and asserts BUSACK. BUSACK disables: the 139 (all address buffers float), the DBS 138 (all DB drivers float), and a 74HC125 that buffers /RD and /WE (pull-ups keep them inactive). The Arduino then owns AB, DB, /RD, /WE and loads RAM or reads memory. Dropping /BUSREQ resumes the CPU exactly where it stopped. The Arduino is never needed to run: with /BUSREQ pulled up the CPU boots from ROM.

## 5. Clocking and timing

### Clock module
- OSC source = 2x CPU frequency: 2 MHz crystal-oscillator can (CPU 1 MHz) or 4 MHz can (CPU 2 MHz), or an adjustable 555 (0.5 Hz-2 kHz), chosen by a 74HC157 section and cleaned by a 74HC14.
- CPU clock = a 74HC74 flip-flop clocked by OSC with **D = NOR(CLK, HOLD)** (one 74HC02 gate): it toggles every OSC edge (50 % duty) but can only *stay low*. HOLD therefore never truncates a high half and the machine always stops in the low half of a microcycle, right after a falling edge, with a stable control word.
- HOLD = NOT RESET AND [ (HALT_cw OR STEPMODE OR BRK) AND NOT GO  OR  BUSREQ_sync OR VWAIT ].
- GO (single step / CONTINUE): debounced button (SR latch, 2x 74HC00 gates) sets a 74HC74 that is asynchronously cleared while CLK is high -> exactly one full microcycle per press. STEP-INSTRUCTION is a microcode-free extension: hold GO until the step counter is 0 again.
- BRK: 2x 74HC688 compare AB with 16 DIP switches, qualified by "fetch step" (DST==IR) and an enable switch; the 74HC688 /P=Q output sets a 74HC74 latch at the falling edge; CONTINUE clears it.
- Distribution: the 74HC74 Q feeds one 74HC04 package: 3 inverters in parallel make three /CLK branches (control+A/B/flags | PC/MAR | X/SP + misc), 2 inverters in series make CLK for IR and the step counter. 33 ohm series resistor at each branch source, branches routed as stars, 100 nF at every chip.

### What happens on each edge (microcycle k = falling edge F_k to falling edge F_k+1)
| Time | Event |
|---|---|
| F_k (/CLK rises) | control word k latched (574); A, B, flags, PC, MAR, X, SP take the values ordered by word k-1; any write pulse of word k-1 has just ended |
| F_k + ~60 ns | decoders settled: address source, DB source, ALU op valid; memory access starts |
| low half | memory read, ALU computes; HOLD is evaluated (VRAM wait, HALT, BUSREQ) |
| R_k (CLK rises) | IR loads (fetch only), step counter -> step+1 or 0 (EOI); microcode ROMs start producing word k+1; /WE goes low if WR |
| high half | write pulse; ALU result and next control word settle |
| F_k+1 | registers capture word k's results; next word latched |

### RAM /WE and why it is safe
`/WE = NAND3(WR, CLK, /RESET)`, combined with each chip's own /CE from the address decoder. /WE is low only during the HIGH half of a write microcycle. In this design **nothing that can affect the address or the write data changes during the high half**: address sources (PC/MAR/X/SP) and DB sources (A/B/PC) only change at falling edges, the control word only changes at falling edges; the only things that change at the rising edge are IR and the step counter, which never drive AB or DB. Margins: address/data valid ~60 ns after F and /WE starts 440 ns later at 1 MHz (AS6C62256 tAS = 0); at the end, /WE rises one NAND delay (~8 ns) after CLK falls, while address/data change only after inverter + 161/377 clock-to-Q + 541 (~35-40 ns) -> ~25 ns hold margin against tWR = tDH = 0. Write pulse 500 ns (1 MHz) / 250 ns (2 MHz) vs tWP(min) ~40 ns. The generator rule "a write step must not load its own DB source" keeps this true. The same strobe (decoded per address) clocks the I/O output latch and the VRAM write.

### Critical paths (typ 74HC at 5 V; pessimistic = 1.5x typ for 74HC, datasheet max for memories)
| Path | Window | typ | pessimistic | 1 MHz budget | 2 MHz budget |
|---|---|---|---|---|---|
| fetch: F -> 574 -> 139 -> 541 -> decode -> flash tACC 70 -> IR setup | half cycle (F->R) | ~160 ns | ~240 ns | 500 OK | 250 OK (tight) |
| microcode: R -> 163/377 clock-to-Q -> flash 70 -> 574 setup | half cycle (R->F) | ~110 ns | ~160 ns | 500 OK | 250 OK |
| data: F -> 574 -> 139/541 -> decode -> flash 70 (RAM 55) -> DB -> ALU-lo 70 -> ALU-hi 70 -> 161 setup | full cycle | ~310 ns | ~465 ns | 1000 OK | 500 OK (tight) |
| VRAM wait: F -> 574 -> 541 -> address decode -> HOLD gate, before next OSC edge | half cycle | ~110 ns | ~165 ns | 500 OK | 250 OK |

Conclusion: 1 MHz has >2x margin everywhere; 2 MHz is plausible with -70 flash and -55 RAM (not the 90 ns old-stock SST39SF010-90 found on n11 - fine at 1 MHz only). The ALU ROM ripple (140 ns) is the price for the 2-chip ALU; it sits in the full-cycle path, which is why data registers latch at the end of the microcycle.

Deviation from baseline: baseline loads all registers on the rising edge. Here A, B, flags, PC, MAR, X, SP load on the falling edge (same edge as the control word, standard pipeline: their enables come from the *old* word whose outputs change ~20 ns after the edge), IR and step counter on the rising edge. Gains: (1) the write pulse can use the whole high half with an unchanging address, so a write and a pointer increment happen in the same step (STD/STA [X+]/PUSH 1 cycle per byte instead of 2); (2) the memory->ALU-ROM->register path gets a full cycle instead of half, which is what makes a ROM ALU viable at 2 MHz.

## 6. Memory and I/O

### Map and decode
| Range | Device | Select |
|---|---|---|
| 0000-7FFF | program ROM, SST39SF010A (A15/A16 of the flash on 2 jumpers = 4 selectable 32K program banks, e.g. monitor / Snake / tests) | /CE = A15 (direct), /OE = /RD, /WE = 1 (programmed out of circuit) |
| 8000-EFFF | RAM AS6C62256 (lower 28K used; EF00-EFFF = stack page) | t = NAND4(A15,A14,A13,A12) (74HC20); /CE = NAND(A15, t) (74HC00); /OE = /RD; /WE = /WE |
| F000-F7FF | VRAM (write-only for the CPU) | 74HC139 half: /G = t, A = A11 -> Y0 = /VRAMSEL |
| F800-FFFF | I/O (registers mirrored every 4 bytes) | same 139 -> Y1 = /IOSEL |

I/O decoder: 74HC138, /G2A = /IOSEL, /G2B = AND(/RD, /WE) (strobe: active during a read step or the write pulse), inputs A = A0, B = A1, C = WR (control-word bit). Read outputs are active for the whole read step; write outputs are exactly the /WE pulse.

| Addr | R/W | Register | Bits |
|---|---|---|---|
| F800 | R | KBD_DATA | last PS/2 scan-code byte; **reading clears KBD_READY** |
| F801 | R | STATUS | bit7 = KBD_READY, bit6 = VWIN (VRAM writable now: inside the CPU window of vertical blanking), bits5-0 = 0 |
| F802 | W | LEDS | 8 LEDs (74HC574, clocked by the end of the write strobe) |
| F803 | W | spare | (e.g. beeper flip-flop) |

bit7 for READY means `LDA STATUS` puts it in N: the poll loop is `LDA STATUS; BPL loop` (4 + 3 = 7 cycles per iteration).

### VRAM write path and window gating
- VRAM = a second AS6C62256 (2K used; 6116 avoided). Address: 3x 74HC157 select CPU AB[10:0] or VGA {row[4:0], col[5:0]} (64-column stride, so CPU address F000 + row*64 + col). Data: CPU DB -> 74HC541 -> VRAM D (enabled during the window), VRAM D -> font ROM address otherwise.
- Two windows come from the VGA vertical decode ROM: WIN_MUX = lines 480-524 (all of vertical blanking): selects the CPU side of the 157 mux, disables VRAM /OE, enables the 541. WIN_CPU = lines 482-521 (40 lines = 1.27 ms per frame, ~1270 CPU cycles at 1 MHz): the only time the CPU may write. WIN_CPU sits strictly inside WIN_MUX with 2-3 lines (>60 us) of margin at each end, so a write that was granted just before WIN_CPU ended still finishes long before the mux switches back.
- WIN_CPU is synchronized to OSC by two 74HC74 flip-flops -> VWIN (also readable as STATUS bit6).
- **Deviation: stall, don't drop.** VWAIT = VRAMSEL AND WR AND NOT VWIN feeds HOLD, so a VRAM write outside the window freezes the clock in the low half of that microcycle until the window opens; the write then happens normally. Cost: one 3-input AND. Benefit: the C program can never silently lose a character; a careful program still polls VWIN first to avoid the wait (and writes all its cells in one burst). VRAM /WE = NAND3(VRAMSEL, WE_pulse, WIN_MUX) as a second safety. A jumper forces VWIN = 1 when the VGA board is absent (bring-up), otherwise VRAM writes would hang the CPU.
- CPU reads of F000-F7FF return 00 (pull-downs). Snake keeps a RAM shadow of the play field anyway (collision test), see section 9.

### PS/2 keyboard receiver (11-bit frames: start 0, D0..D7 LSB first, odd parity, stop 1; keyboard drives clock 10-16.7 kHz; data valid on the falling clock edge)
- KCLK and KDATA: 4.7k pull-ups, 74HC14 Schmitt inputs (the keyboard lines are slow and noisy). Mini-DIN-6 socket; keyboard powered from the 5 V rail (budget ~100 mA).
- Shift register: 2x 74HC164 clocked by NOT KCLK (shift on the falling KCLK edge), serial in = KDATA. After 11 bits: D0..D7 sit at Q9..Q2 (D1/D0 in the second 164), start bit at Q10.
- Bit counter: 74HC161 clocked by NOT KCLK. DONE = Q3 AND Q1 AND Q0 (count 11). /LOAD (synchronous) = NOT DONE with P = 0001, so the first falling edge of the next frame (its start bit) reloads 1 - the counter never needs a fast self-reset pulse and DONE stays high for the whole inter-frame gap.
- Resync: RC idle timeout - KCLK low discharges a 10 nF cap through a 1N4148, a 22k resistor recharges it; if KCLK stays high > ~200 us (longer than any in-frame high time, ~50 us max) a 74HC14 gate asserts the 161 async /MR. A frame corrupted by noise or a power-up mid-frame therefore resynchronizes at the next gap.
- Byte latch: 74HC574 clocked by DONE (rising), inputs from the 164 outputs Q2..Q9 (bit-reversed wiring), tri-state output to DB, /OE = /KBD_DATA_RD.
- READY: 74HC74 half, D = 1, clocked by DONE. Clear-on-read is synchronous: a second 74HC74 half clocked by /CLK samples "KBD_DATA is being read" at the falling edge that ends the read step, its /Q pulls READY's /CLR for one microcycle. Address-decode glitches at the start of a step can therefore never clear the flag. The STATUS bit7 is READY passed through one more flip-flop clocked by OSC (synchronizer), so the CPU never samples a changing level.
- Parity/stop not checked in v1 (software can ignore F0/E0 prefixes; Snake only needs make codes of 4 keys). Chips: 2x 164, 1x 161, 1x 574, 2x 74HC74 (shared with sync), 1x 74HC14 (shared), passives.

## 7. VGA module (640x480@60 timing, 40x30 text, monochrome v1)

- **Dot clock**: 25.175 MHz oscillator can -> 74HC74 toggle -> 12.5875 MHz (79.4 ns). All VGA flip-flops/counters run on this one clock (synchronous design, enables instead of ripple clocks).
- **Horizontal counter**: 3x 74HC161, synchronous: bits 0-2 = dot within character (0-7), bits 3-8 = character slot hc (0-49). 400 dots = 50 slots: 40 visible + 1 front porch + 6 sync + 3 back porch - every boundary is a multiple of 8 dots, so all horizontal decoding can be done once per character.
- **Vertical counter**: 3x 74HC161 (10 bits, 0-524), CEP = "end of line" (counts once per line, same dot clock). Text row = vc[8:4] (0-29), font row = vc[3:1] (each font row shown on 2 scan lines).
- **Sync/blank decode = one ROM**: SST39SF010A, address = {vc[9:0], hc[5:0]} (16 bits), 8 outputs: HSYNC, VSYNC, BLANK, HEND (reset H), VEND (reset V), WIN_MUX, WIN_CPU, spare. Registered by a 74HC574 once per character (at dot 7). The table already contains the pipeline delay (2 character slots) and a one-slot look-ahead for HEND/VEND, so sync/blank come out aligned with the pixels without extra delay chips; changing porches or windows = reflash. Counter resets: 161 synchronous /LOAD of 0 when (HEND_reg AND dot==7), V likewise with VEND_reg.
- **VRAM address mux**: 3x 74HC157: VGA side = {vc[8:4], hc[5:0]} (11 bits, the same 64-stride layout the CPU uses), CPU side = AB[10:0], select = WIN_MUX.
- **Character pipeline** (per 8-dot slot, events at the dot-7 clock edge):
  1. slot c: VRAM address = (row, c); AS6C62256 data valid after ~70 ns (mux + 55 ns).
  2. end of slot c: char latch 74HC574 <- VRAM data (char code).
  3. slot c+1: font ROM SST39SF010A address = {bank jumpers, char[6:0], fontrow[2:0]}; data valid after 70 ns.
  4. end of slot c+1: 74HC166 parallel-loads the glyph byte (synchronous load: /PE low at the rising dot-clock edge - checked), then shifts 8 pixels out of Q7 (D7 = leftmost pixel) during slot c+2.
  Each step has 635 ns available for <100 ns of work, so the pipeline is not timing-critical.
- **Pixel output**: Q7 AND NOT BLANK_reg (74HC08) -> 74HC74 pixel register on the dot clock (removes gate skew/glitches) -> 3 separate 74HC08 gates (one per colour, so each output carries ~9 mA) -> 470 ohm series -> monitor's 75 ohm: 5 V x 75/(470+75) = 0.69 V (spec 0.7 V). White on black. HSYNC/VSYNC (negative) from the 574 through 100 ohm to DB-15 pins 13/14; RGB on 1/2/3, grounds 5-8,10.
- **Colour later (v2)**: 2 bits/channel from an attribute byte = second VRAM byte; out of scope for v1.
- Chips: osc, 74HC74 x1 (/2 + pixel reg), 74HC161 x6, SST39SF010A x2 (timing, font), 74HC574 x2 (timing reg, char latch), 74HC157 x3, AS6C62256 x1, 74HC541 x1 (CPU data -> VRAM), 74HC166 x1, 74HC08 x2 (pixel gating, RGB drivers, dot==7 decode), 74HC00 x1 (counter load/enable gating) = **20 ICs + oscillator**.

## 8. Chip count

| Module | Parts (part x qty) | ICs |
|---|---|---|
| CPU registers | 74HC377 x4 (A, B, IR, flags); 74HC161 x12 (PC 4, MAR 4, X 4); 74HC191 x2 (SP) | 18 |
| CPU bus drivers | 74HC541 x13 (DB: A, B, PCL, PCH; AB: PC 2, MAR 2, X 2, SP 1, constant EF 1; panel DIP 1) - 74HC245 with DIR tied is the stock fallback | 13 |
| ALU | SST39SF010A x2, 74HC157 x2 | 4 |
| Control | SST39SF010A x3, 74HC574 x3, 74HC138 x2, 74HC139 x1 (2nd half used by memory decode), 74HC163 x1 | 10 |
| CPU glue + bus release | 74HC00, 74HC02, 74HC04, 74HC32, 74HC125 (one each) | 5 |
| **CPU subtotal** | | **50** |
| Clock / reset / debug | NE555 (or TLC555) x1, 74HC157 x1, 74HC74 x3, 74HC14 x1, 74HC00 x1, 74HC04 x1, 74HC08 x1, 74HC32 x1, 74HC688 x2; oscillator cans 2 MHz + 4 MHz | 12 |
| Memory + decode | SST39SF010A x1 (program ROM), AS6C62256 x1, 74HC20 x1, 74HC10 x1, 74HC138 x1, 74HC08 x1 | 6 |
| I/O | 74HC574 x2 (LED port, KBD byte), 74HC541 x1 (STATUS), 74HC164 x2, 74HC161 x1, 74HC74 x2 | 8 |
| VGA | 74HC74 x1, 74HC161 x6, SST39SF010A x2, 74HC574 x2, 74HC157 x3, AS6C62256 x1, 74HC541 x1, 74HC166 x1, 74HC08 x2, 74HC00 x1; 25.175 MHz can | 20 |
| **Total** | | **96 ICs + 3 oscillator cans** |

Per part: 74HC161 x19, 74HC541 x15, SST39SF010A x8, 74HC574 x7, 74HC74 x6, 74HC157 x6, 74HC377 x4, 74HC08 x4, 74HC00 x3, 74HC138 x3, 74HC04 x2, 74HC32 x2, 74HC688 x2, 74HC164 x2, 74HC191 x2, AS6C62256 x2, and one each of 74HC02, 74HC10, 74HC14, 74HC20, 74HC125, 74HC139, 74HC163, 74HC166, NE555. Buy ~15 % spares of every logic part (and 2 spare flashes).

What the C-friendly features cost: X pointer register 6 ICs (4x 161 + 2x 541); 8-bit SP with page constant 4 ICs (2x 191 + 2x 541); PC readback 2x 541 (needed for CALL); ROM ALU instead of discrete ALU saves ~6 ICs. Everything else that makes C fast (16-bit Z chaining, 14 branch conditions, LEAX, pop-operand ops, INCW) is microcode only.

Breadboards: ~4 ICs per 830-point board with LEDs and bus wiring -> CPU 13, clock/debug 3, memory/IO 4, VGA 5, power/bus-distribution 2 = **~27 boards** (buy 30).
Wires: ~1,400 signal + ~250 power + ~250 LED = **~1,900 hand-cut wires** (the 16-bit AB and the DB fan-out to ~15 chips each are the largest share).
Power: ~1 A at 5 V (7 always-enabled flashes ~140 mA, ~200 LEDs at 1.5 mA ~300 mA, keyboard ~100 mA, logic and RAM the rest) -> 5 V 3 A supply, feed every board pair from both ends, 100 nF per IC + 10-47 uF per board.
Rough part cost (TR retail / DigiKey, from the shop notes): logic ~1,800 TL, 8 flashes ~1,300 TL, 2 SRAM ~600 TL, 3 oscillators ~550 TL, 30 boards ~3,600 TL, wire/LED/resistor/DIP/sockets ~1,500 TL, Arduino Mega clone ~800 TL, PS/2 keyboard ~650 TL -> **~11,000 TL** plus a TL866II+/T48 programmer if not owned (~2,500 TL); leaves a large reserve for spares, one consolidated import and customs.

## 9. C mapping

### Supported C subset (v1 compiler, Python)
- Types: `char` (8-bit, **unsigned**), `int` (16-bit signed), `unsigned` (16-bit), pointers to char/int, 1-D global arrays, string and char literals. `volatile` accepted and ignored (the compiler never caches memory in registers across statements anyway). No struct/float/long in v1 (struct is the first v2 item; it needs only an offset add = LEAX).
- Statements: if/else, while, do-while, for, break, continue, return, expression statements; `switch` lowered to a compare chain.
- Operators: all arithmetic/logic/compare/assign ops incl. `+= ++ -- && || !`; `* / %` and variable shifts call library routines (`__mul16`, `__divmod16`, `__shl`), constant multiplies by powers of 2 become SHLD sequences.
- Functions: any number of int/char/pointer parameters, int/char/void return, **no recursion** (the compiler builds the call graph and reports a cycle as an error). Inline `asm("...")` for I/O tricks.
- Memory-mapped I/O by casts: `#define KBD (*(volatile char*)0xF800)`.

### Where things live - static frames (chosen) vs stack frames, with numbers
Every function gets a fixed RAM block (params, then locals) named `f.p`, `f.local`; the stack holds only return addresses and expression temporaries. Comparison on the operations Snake actually executes:

| Operation | Static (this design) | SP/FP-relative frames |
|---|---|---|
| read/write an int local or param | `LDD/STD abs` 5 cycles, 3 bytes | `LDD [FP+n]` = fetch + offset+FP -> MARL + EF -> MARH + 2 data = 5 cycles, 2 bytes |
| pass 2 int args + call + return | 2x STD (10) + CALL 5 + RET 5 = **20** | 2x PUSHD (6) + CALL 5 + prologue (push FP, FP<-SP, SP-=locals ~7) + epilogue (~5) + RET 5 + caller SP+=4 (~3) = **31** |
| extra hardware | 0 | SP/FP into the ALU (Y-mux 2x157 -> 4x153 = +2), SP readback 541 (+1), FP register 377+541 (+2), synchronously loadable up/down SP (the 191 load is asynchronous -> unusable mid-program) = **+5 ICs** |
| recursion / reentrancy | no | yes |

Per access the two are equal (the frame version saves 1 byte but needs an extra microstep to add the offset), per call static is ~35 % cheaper, and it costs 0 chips instead of ~5. Snake needs no recursion. Decision: **static frames**. Optional later: call-graph overlay (functions never active at the same time share RAM) - not needed, Snake's locals are < 200 bytes in 28 KB.

Calling convention:
- Caller evaluates each argument into D and stores it straight into the callee's parameter slot (`STD f.p1`). If an argument expression itself contains a call, all arguments are first evaluated onto the stack (PUSHD) and then popped into the slots (`POPD; STD f.pk`), so `f(1, f(2,3))` stays correct.
- `CALL f`; result in D (char results in A, B = 0). All registers (D, X, flags) are caller-saved; X is never live across a call or a statement boundary.
- Expression temporaries: Small-C style - left operand `PUSHD`, right operand into D, then `ADDS/SUBS/ANDS/ORS/XORS/CPS` (pop-operand ops, 4 cycles). If the right operand is a variable or constant (the common case) no temporary is used at all: `ADDD v` / `ADDD #k`.
- crt0: SP is already FF from reset; copy .data from ROM to RAM, clear .bss, `CALL main`, `HALT`.

### Requested code fragments (1 cycle = 1 us at 1 MHz)
**`a = b + c;`** (int globals)
```
LDD  b        ; 3 B  5 cyc
ADDD c        ; 3 B  5
STD  a        ; 3 B  5        -> 9 bytes, 15 cycles
```
**`*p = x;`** (char *p, char x)
```
LDX  p        ; 3 B  5   X <- p
LDA  x        ; 3 B  4
STA  [X]      ; 1 B  2        -> 7 bytes, 11 cycles   (*p++ = x: STA [X] + INCW p = 18)
```
**`if (x < y) {...}`** (signed int)
```
LDD  x        ; 5
CPD  y        ; 5   SUB low byte, SBC high byte with Z chaining -> true 16-bit Z,C,N,V
BGE  else     ; 3   (N == V); unsigned compare would use BHS, char compare LDA/CMPA
...then...
else:                                  -> 9 bytes, 13 cycles
```
**`r = add2(u, v);`** with `int add2(int a, int b) { return a + b; }`
```
LDD  u        ; 5
STD  add2.a   ; 5
LDD  v        ; 5
STD  add2.b   ; 5
CALL add2     ; 5
STD  r        ; 5        caller: 30 cycles, 18 bytes
add2:
LDD  add2.a   ; 5
ADDD add2.b   ; 5
RET           ; 5        callee: 15 cycles
```
Total 45 cycles, of which call overhead (arg stores + CALL + RET) = 20.

**String to VRAM** `void vputs(char *v, char *s) { while (*s) *v++ = *s++; }`
Straight compiler output (one pointer register: reload X per access):
```
loop: LDX  vputs.s   ; 5
      LDA  [X]       ; 2   Z set by the load
      BEQ  done      ; 3
      LDX  vputs.v   ; 5
      STA  [X]       ; 2
      INCW vputs.v   ; 7   (clobbers A - char already stored)
      INCW vputs.s   ; 7
      JMP  loop      ; 3   -> 34 cycles/char
```
With the zero-chip LDAI/STAI instructions the compiler keeps `s` in X and the second pointer in memory:
```
      LDX  vputs.s   ; 5 (once)
loop: LDA  [X+]      ; 2
      BEQ  done      ; 3
      STAI vputs.v   ; 7   store through pointer variable
      INCW vputs.v   ; 7
      JMP  loop      ; 3   -> 22 cycles/char
```
Filling/clearing the screen from one pointer (`*v++ = ' '` with X kept in the register) is `STA [X+]` + loop counter = 9 cycles/cell: a full 1200-cell redraw = ~11 k cycles = ~9 vertical-blank windows (~0.15 s); the stall mechanism splits it across frames automatically.

### Snake game-loop budget (compiled code, measured by hand from the table)
Data: `char field[30*64]` RAM shadow of the screen (VRAM is write-only, collision needs reads), `int body[512]` ring buffer of cell offsets (row*64+col), `int head, tail, dir, food`, `char grow`.
| Step of one game tick | Code shape | Cycles |
|---|---|---|
| nh = body[head] + dir | LDD head; SHLD; LEAX #body; LDD [X+]; ADDD dir; STD nh | 24 |
| collision: field[nh] == WALL or BODY | LDD nh; LEAX #field; LDA [X]; CMPA #W; BEQ; CMPA #B; BEQ | 20 |
| food: nh == food | LDD nh; CPD food; BNE | 13 |
| head = (head+1) & 511; body[head] = nh | LDD; INCD; ANDD #511; STD; SHLD; LEAX #body; LDD nh; STD [X+] | 35 |
| put(nh, BODY) incl. call | 2 arg stores + CALL + (2x LDD/LEAX/LDA/STA) + RET | 54 |
| erase tail: put(body[tail], ' '); tail = (tail+1)&511 | | 85 |
| keyboard: poll STATUS, read KBD, map 4 scan codes, F0-prefix skip | | ~60 |
| wait for VWIN, frame counter, tick every 6th frame | | ~20 |
| **total per tick** | | **~310 cycles = 0.31 ms** |

At 10 moves/s that is ~0.3 % of a 1 MHz CPU, and a whole tick (with its 2-4 VRAM writes) fits inside one 1,270-cycle VRAM window, so the game never stalls. Snake would even run at 50 kHz. Food placement (16-bit LFSR via SHRD/XORD, ~40 cycles per try) and the score (kept as 4 decimal digit chars, `++` with carry, no division) are rare. Conclusion for the design priority: on Snake-like code the CPU is never the bottleneck at 1 MHz; the C-friendly features are justified by **compiler simplicity and code size** (every C construct maps to 1-3 instructions, no register allocator needed, 16-bit compares/branches exact), not by raw speed - which is why nothing in this proposal adds chips for speed alone except the X register (6 ICs: without it every array/pointer/VRAM access needs a microcoded indirect through memory, 7 cycles and B clobbered instead of 2, and the compiler gets awkward).

## 10. Risks, omissions, early prototypes

### Risks (and mitigation)
| Risk | Mitigation |
|---|---|
| ROM ALU tables wrong in a corner case (flags, Z chain, ROR/ASR link bits) | tables generated from isa.yaml by Python and exhaustively compared (all 2x2^17 entries) with the emulator's ALU model; standalone ALU board tested from DIP switches |
| Hold time between control-word latch and registers that share the falling edge (enables change ~20 ns after the edge) | all /CLK branches from ONE 74HC04 package, star routing, 33 ohm series; measure skew (<10 ns) and /WE-vs-address margin (~25 ns) with the scope on the first prototype; fallback: one more inverter in the register-clock branches |
| 74HC191 enable timing and cascade | verified rule (CE rising only while CP high) is met by construction; simulate in Digital and bench-test push/pop across the 0x?0/0x?F boundaries |
| Keyboard byte overrun: the receiver holds ONE byte; arrow keys send E0 xx / E0 F0 xx 1-2 ms apart | software polls READY inside every wait loop (every 20-60 us, not once per frame); Snake uses WASD (single-byte make codes) by default |
| VRAM stall hangs the CPU when the VGA board is absent | jumper forces VWIN = 1 |
| 8 flashes reflashed many times; DIP pins wear in breadboards | machined-pin sockets as carriers, TL866II+/T48 (minipro supports SST39SF010A), keep microcode bank 1 for experiments |
| Breadboard scale (~27 boards, ~1,900 wires): bad contacts, rail drop, noise | build and test module by module with the manual control panel; rails fed from both ends; 100 nF per IC; LED on every bus line |
| Old-stock / counterfeit DIP parts from local marketplaces | test every logic IC in the programmer's logic-test mode before use; buy memories from distributors |
| Python C compiler is the largest software item | the ISA was shaped so a single-pass Small-C style code generator needs no register allocator: expression -> D, temporaries -> stack, variables -> abs; start it in week 1 of the simulation phase against the emulator |
| 2 MHz margins are tight on the fetch path (240 ns pessimistic vs 250 ns) | the target is 1 MHz; 2 MHz is a bonus experiment with -70/-55 memories |

### Deliberately left out
Interrupts (polling is enough for Snake), SP/FP-relative addressing and recursion (section 9 numbers), X readback and a second pointer register (6 ICs for ~12 cycles/char saved on rare string copies), relative branches, hardware multiply, colour, CPU reads of VRAM, dual-port VRAM, PS/2 parity checking and host-to-keyboard commands, sound (F803 is reserved for a beeper bit).

### Prototype early (in this order)
1. Simulation phase (now -> Jan 2027): isa.yaml -> microcode/ALU/timing ROM generators, instruction- and microstep-level emulator, the full CPU in Digital driven by the generated ROM images, trace diff emulator vs Digital; the C compiler running Snake in the emulator.
2. First build week: clock module + control-word latches + step counter + one register on a breadboard: scope the edges, skew, HOLD/step behaviour and the /WE window.
3. VGA counters + timing ROM alone on a monitor (stable sync and a test pattern from the font ROM) - independent of the CPU, highest "external acceptance" risk.
4. ALU board from DIP switches; then registers + buses with the manual panel.
5. Memory + Arduino BUSREQ loader; then PS/2 receiver read by the Arduino before the CPU reads it.
