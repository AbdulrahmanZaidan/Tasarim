# ISA v0: judgement of the three proposals and the unified specification

Status: COMPLETE. STEP 1 (scores and errors), STEP 2 (sections 1–10) and STEP 3 (open issues) are all written.

---

# STEP 1: Scores and errors

Scale: 10 = best. (a) chips, wires and build effort for 2 people. (b) electrical and timing risk on breadboards. (c) C-compiler friendliness and Snake performance at 1 MHz. (d) debuggability. (e) internal consistency and correctness.

| | (a) build | (b) risk | (c) C | (d) debug | (e) consistency | Sum |
|---|---|---|---|---|---|---|
| P1 MIN-CHIP | 9 | 6 | 5 | 5 | 7 | 32 |
| P2 C-FRIENDLY | 4 | 6 | 9 | 7 | 6 | 32 |
| P3 DEBUGGABLE | 3 | 8 | 7 | 10 | 8 | 36 |

## P1 MIN-CHIP (54 ICs, ~950 wires)

**Scores**
- (a) **9.** 54 ICs, 18 boards and about 950 wires. Nobody else comes close.
- (b) **6.** Three things raise the risk:
  - MAR uses a gated clock.
  - PC and the control latch share the falling edge.
  - The two cascaded ALU flashes must finish in half of a 636 ns cycle.
  
  It also uses 4040 ripple counters with self-reset.
- (c) **5.** The C mapping works, but it is the weakest of the three:
  - only one accumulator, no pointer register and no stack;
  - CALL is 7 bytes and 10 cycles;
  - copying a string to VRAM costs 41 cycles per character.
- (d) **5.** It has the manual panel, the breakpoint and the microcode bank. Weaknesses:
  - BUSREQ is "hold the CPU in reset", so the Arduino cannot pause and resume the CPU;
  - there is no instruction-step mode;
  - a VRAM stall in STEP-button mode needs many button presses.
- (e) **7.** Mostly sound. It has a few false claims and leaves out an SP, which the brief requires.

**Errors**
1. **The /FL polarity makes the "safe zero word" claim false.** CW11 /FL is active-low.
   - Every microword that leaves bit 11 at 0 loads the flags. This includes the reset word and any word set on the manual panel, whose switches have pull-downs.
   - In DS=0 steps the ALU is tri-stated, so the 74HCT173 loads 0000 from the pull-downs.
   - The generator must therefore set CW11=1 in every non-FL word, and the panel clears the flags on every step.
   - Fix: make FL active-high and add an inverter.
2. **The "no hold race" claim is false.** The PC (CP = /CLK) counts and loads on the same falling edge that latches the control word (273 on /CLK).
   - The two are driven from different 74HC04 gates.
   - PCI and /LD_PC must hold past that edge. The design is a same-edge pipeline that depends on skew being smaller than the 273 clk-to-Q time. That contradicts "removes the usual same-edge hold race".
3. **There is no stack pointer, PUSH or POP.** The brief requires PUSH/POP/CALL/RET microsteps and an SP reset value.
   - CALL writes into a static slot and is 7 bytes / 10 cycles.
   - Recursion and saved temporaries are impossible.
4. **The MAR clock is gated:** NOR(/CLK, /LD), about 15 ns behind CLK.
   - `M[MAR|1]->MARH` loads MAR from memory that MAR itself addresses.
   - Correctness relies on 574 tPD(min) + memory tOH being greater than the 574 hold time. With flash, tOH(min) = 0, so this is self-timed with only a few ns of margin.
   - This is a justified deviation, but a real risk.
5. **The VGA counters use asynchronous self-reset.** Each 74HC4040 is reset by an AND decode of its own outputs (50, 525).
   - The reset pulse lasts only about 4040 MR->Q plus one gate (~30 ns). That is close to the 4040 minimum MR pulse width, so a partial reset is possible.
   - Synchronous counters avoid this.
6. **BUSREQ abuses the reset line and creates deliberate contention.**
   - BUSREQ = hold RESET, which destroys CPU state, so there is no pause/inspect/resume.
   - The Arduino overrides CPU-driven MEM_OE_n and RAM_WE_n nodes through 1k resistors. This is contention by design.
7. **The window synchronizer is clocked by SRC.**
   - In STEP-button mode, a stalled VRAM write needs many presses: VWIN is sampled only on presses, and the window is open for about 8 % of the frame.
   - In 555 mode, CPUSEL can stay on the CPU side for seconds.
8. **The PS/2 read can destroy a frame in progress.** PS/2 clear-on-read is `/MR = OR(Y1, /CLK)`.
   - Any read of F800–FFFF clears the 164s, even when KRDY = 0.
   - Software that reads KBD without checking KRDY therefore destroys an in-progress frame, and the keyboard does not know it must retransmit.
9. **Indexing is limited to 8 bits.** `LDA [p],A` and `abs,A` use an 8-bit index.
   - The 1,920-byte Snake board needs 16-bit index arithmetic into a temporary pointer, so code is longer than the estimates assume.
10. **The CPU clock is fixed at dot/8 = 1.573 MHz.** There is no independent clock in crystal mode, and every VGA clock problem also stops the CPU.

## P2 C-FRIENDLY (96 ICs, ~1,900 wires)

**Scores**
- (a) **4.** 96 ICs, 13 of them 74HC541 (poorly stocked in Turkey), 27–30 boards and about 1,900 wires.
- (b) **6.** The memory -> ALU -> register path gets a full cycle, which is good. However, every data register shares the edge of the control latch (a same-edge pipeline), and the PS/2 latch has a race.
- (c) **9.** The best ISA for C:
  - a 16-bit D accumulator;
  - an X register with free post-increment, plus LEAX;
  - chained Z and all 14 branch conditions;
  - `a = b + c` in 15 cycles and a call plus return in 20 cycles.
- (d) **7.** It has a manual panel that drives the CW latch outputs, LEDs on all 24 CW lines, a breakpoint, a microcode bank and a resumable BUSREQ. It has no probe latches, no trace marker and no instruction-step mode.
- (e) **6.** Several real bugs (listed below).

**Errors**
1. **The PS/2 byte latch has a setup race.** The latch (74HC574) is clocked by DONE.
   - DONE rises one 161 clk-to-Q time plus one AND gate after the same KCLK edge that performs the 11th 164 shift.
   - The latch can therefore capture data from before the shift (bit-shifted bytes), because setup margin is about 0–15 ns against a 12–20 ns requirement.
2. **There is no keyboard inhibit, so bytes are lost.** The single byte latch is overwritten by the next frame.
   - Multi-byte sequences such as F0 xx and E0 F0 xx arrive 1–2 ms apart.
   - P2's own VRAM stall freezes the CPU for up to about 15 ms.
   - So break codes are lost and keys get stuck in Snake.
   - Fix: hold KCLK low while READY = 1.
3. **SEXB is wrong as written.** `SEXB = SEXT(Y=A)->B`, but SEXT is defined on X (= DB), and the low ROM sees X7, not Y7.
   - As written, it sign-extends DB = 00 (no source), so B is always 00.
   - Fix: DBS = A.
4. **N is wrong after the 16-bit right shifts.** After SHRD and ASRD, N is bit 7 of the low byte (the last ROR), not bit 15. Yet the table lists "Z C N" for both.
5. **The VGA timing register cannot be "registered once per character" as described.** It is a 74HC574, which has no clock enable.
   - Loading once per character therefore needs a decoded (gated) clock in the 12.6 MHz domain.
   - It must be a 377 with /E = dot 7.
6. **The PS/2 READY path and the 191 SP are workable**, but STATUS uses a one-stage synchronizer.
7. **In 555 mode the stall-not-drop promise breaks.** WIN_CPU is synchronized on OSC, which is the 555 in that mode, so the sample is stale for seconds.
   - The write is then blocked by the `WIN_MUX` term in VRAM /WE, i.e. silently dropped. That is exactly the failure P2 set out to avoid.
8. **Every data register clocks on the control latch's edge.** A, B, flags, PC, MAR, X and SP all clock on the same /CLK edge as the 574 control latch, and flags -> uROM -> 574 also share it.
   - Hold margin is therefore only (clk-to-Q + decode) minus skew. It is acknowledged and acceptable, but it is a real risk across ~27 boards.
9. **Minor:** the pixel register delays video by one dot relative to sync. This is harmless.

## P3 DEBUGGABLE (115 ICs, ~1,800–2,300 wires)

**Scores**
- (a) **3.** 115 ICs (plus 7 on the Arduino adapter), 28–34 boards and about 2,000 wires. That is too much for 2 people in 16 weeks.
- (b) **8.** The 4-phase cycle gives:
  - one commit edge;
  - a write strobe isolated by a full phase on each side;
  - stops only at cycle boundaries;
  - the 191 rules met by construction.
  
  The datapath gets 3/4 of the cycle.
- (c) **7.** A + X(+) + SP with static frames is good enough. But there is no Z chaining, so 16-bit `==`, `>` and `<=` need operand swaps or two branches. Copying a string costs 28 cycles per character.
- (d) **10.** Probes, a MARK bit, watchpoints, micro and instruction stepping, BUSREQ at a cycle boundary, a manual word through the real latch, and generated Digital test vectors.
- (e) **8.** Very consistent. Two real bugs in the VRAM gating, plus minor slips.

**Errors**
1. **VRAM data race at the end of the window.** The data buffer uses `/OE_245 = NAND3(MEMW_L, VRAMSEL, VWR_s)`, while WAIT is decided from VWR_s before the D->A edge.
   - VWR_s is clocked by MCLK, so it can fall on that same D->A edge.
   - Phase A then runs with VRAM /WE low but the buffer disabled and VRAM /OE high. Floating data is written.
   - Fix: gate the buffer with the registered VMUX (one line of guard), never with the synchronizer output.
2. **The synchronizer runs on MCLK.** With MCLK = 555 or the Arduino (seconds per phase), a write is granted on a stale VWR_s, and phase A can outlast VMUX. The write then goes to the VGA-side address, with no data driven.
   - Fix: in slow clock modes, force the CPU to own VRAM.
3. **No Z input on ALU-H.** Z after SUB/SBC describes only the high byte, so BGT/BLE/BHI/BLS are 8-bit only and a 16-bit `==` needs two compares and two branches. It is acknowledged, but it is a C-mapping cost that can be avoided.
4. **CLC/SEC, INC/DEC and loads cannot keep N (or Z).**
   - The text says "Unchanged flags are copied through from old C and old V". The ROMs have no old-Z or old-N inputs, and FL loads all 4 flags.
   - So any FL step recomputes Z and N. CLC/SEC therefore cannot be "C only" as the table claims.
5. **Wrong pin name on the 74HC191.** P3 calls the carry output "TC_lo", but the 74HC191 has no TC pin. It has MAX/MIN, which depends on U/D, and /RC. The design must use MAX/MIN.
6. **STATUS polling needs an AND.** KBD_READY is in STATUS bit 0, so polling needs `AND #1` (LDA sets Z and N from all 8 bits). Putting READY in bit 7 lets a load or BIT go straight to BPL.
7. **2 MHz is not guaranteed.** The uROM path (phase C) and the WAIT path (phase D) have zero worst-case margin at 2 MHz. The read+ALU path is about 380 ns at datasheet maximums (three 70 ns flashes in series), not 360. This is acknowledged.
8. **Chip-count inflation.** The design includes:
   - 3 probe latches;
   - 3 manual-word buffers;
   - 2 seven-segment latches;
   - 9 PS/2 chips (an oversampled receiver);
   - 22 VGA chips (3 pipeline registers).
   
   Each is justifiable alone, but together they push the build past what 2 people can wire in 16 weeks.

## Verdict
**P3 is the base.** It has the cleanest timing model and the best debug story, and it is consistent.

Grafts:
- **From P1:**
  - Z chained by the ALU tables, and loads that do not touch flags, which together give exact 16-bit compares;
  - the 74HC164 start-bit-marker PS/2 receiver with keyboard inhibit;
  - VGA counters that step at the character boundary, so a single timing register aligns sync/blank with the pixels;
  - the manual control panel without buffer chips;
  - checking VOH of the flash and SRAM.
- **From P2:**
  - INCW/DECW;
  - the full set of 14 branch conditions, all valid for 16-bit;
  - X as a load-only register (no readback; 2 chips saved);
  - KBD_READY in bit 7;
  - a jumper that forces the VRAM window.
- **Fixes:** every error listed above.
- **Chip count:** brought down from 115 to about 92.

---

# STEP 2: Unified specification "ISA v0"

Name: **TD-8**. Base: P3, with grafts from P1 and P2 and all the fixes above.

## 1. Programmer's model

| Register | Width | Visible | Notes |
|---|---|---|---|
| **A** | 8 | yes | Accumulator. It is the only ALU destination: `A <- ALU(A, DB)`. It is the left operand of every binary op. |
| **X** | 16 | load-only | Pointer register (4x 74HC161).<br>Loaded from DB byte by byte (`LDX`, `TAXL`, `TAXH`).<br>Post-increment `(X+)` and `INX` cost no extra cycles.<br>**Not readable**, so it is scratch: the compiler reloads it and never spills it.<br>DSRC codes 5/6 are reserved, so 2x 245 can add readback later with no other change. |
| **SP** | 8 | implicit | Stack pointer in page EF (EF00–EFFF).<br>Empty-descending: push writes [EF:SP] and then decrements SP; pop increments SP and then reads.<br>Reset value FF, so the first push lands at EFFF. |
| **PC** | 16 | via jumps | Reset value 0000 (ROM). Always loaded as 16 bits at once from AR. |
| **F** = Z C N V | 4 | via branches and ADC/SBC/CPC/ROL/ROR | Loaded as a group only by microsteps with FL set. |
| IR | 8 | hidden | Opcode; microcode address bits A4–A11. |
| AR | 16 | hidden | Operand / target address register (4x 74HC161). Loaded byte by byte from DB, can increment, drives AB, feeds the PC load inputs. |
| STEP | 4 | hidden | Microstep counter, 16 steps maximum. The longest instruction uses 7. |

**Flags.** Only ALU steps change flags. Loads, stores, transfers, stack operations and jumps never do (taken from P1). This is what makes byte-pair arithmetic exact.

| Flag | Meaning |
|---|---|
| **Z** | Result == 0.<br>**Chained** for ADC, SBC, CPC, and the second byte of INCW/DECW: `Z = Z_old AND (result == 0)`.<br>After a lo/hi pair, Z is therefore the true 16-bit Z, because an `LDA` between the two halves does not touch flags. |
| **C** | Carry out for ADD/ADC.<br>For SUB/SBC/CMP/CPC/NEG, **C = 1 means no borrow** (6502/ARM convention: unsigned `a >= b` <=> C = 1).<br>For shifts, C is the bit shifted out.<br>Kept by logic ops, INC/DEC, TST, BIT and SEX. |
| **N** | Bit 7 of the result. For BIT, N = M7. |
| **V** | Two's-complement overflow for ADD, ADC, SUB, SBC, CMP, CPC, INC, DEC and NEG.<br>For BIT, V = M6.<br>0 for logic ops, shifts, TST, SEX and CLC/SEC. |

- Signed less-than is `N XOR V`.
- All 14 conditions are decoded in microcode, because the flags are microcode address bits A12–A15. No condition multiplexer exists.
- CLC/SEC set C, but they also set Z and N from A and set V = 0. There is no old-N input, so N cannot be preserved; the same holds for Z on these two ops.

**Addressing modes** (16-bit operands are little-endian):

| Mode | Syntax | Operand bytes | Use |
|---|---|---|---|
| implied | `INC`, `RET` | 0 | unary A ops, stack, control |
| immediate | `#n` / `#nn` (LDX) | 1 / 2 | constants |
| absolute | `abs` | 2 | globals, static frames, memory-mapped I/O, VRAM cells |
| X-indirect | `(X)` | 0 | `*p`, `p[i]` once the address is formed in X |
| X-indirect, post-increment | `(X+)` | 0 | string/array walks, `*p++` |
| memory-indirect jump | `JMPI (abs)` | 2 | switch tables (clobbers A) |
| stack | implicit EF:SP | 0 | return addresses, PHA/PLA |
| absolute target | `JMP/CALL/Bcc abs` | 2 | every control transfer. No relative branches, so no PC adder and no branch-range limit. |

**Memory map**

| Range | Contents |
|---|---|
| 0000–7FFF | ROM 32K (SST39SF010A; flash A15/A16 on jumpers give 4 program banks) |
| 8000–EFFF | RAM 28K (AS6C62256-55); EF00–EFFF is the stack page |
| F000–F7FF | VRAM, write-only: `F000 + row*64 + col` |
| F800–FFFF | I/O (section 6) |

**Reset state:** PC=0000, SP=FF, X=0000, AR=0000, F=0000, STEP=0, control latch = all-zero NOP. A and IR are undefined; the emulator marks A as "unknown until written".

## 2. Instruction set (53 mnemonics, 88 opcodes)

### 2.1 Opcode encoding
The opcode is used directly as microcode address bits A4–A11, so the hardware decodes no fields. The grouping below exists only so that the 8 IR LEDs can be read by eye.

| Range | Group | Encoding |
|---|---|---|
| `00` | HALT | |
| `01` | NOP | |
| `40–6F` | **M** (memory/ALU) | `0x40 + 4*op + mode`<br>op: 0 LDA, 1 STA, 2 ADD, 3 ADC, 4 SUB, 5 SBC, 6 AND, 7 OR, 8 XOR, 9 CMP, 10 CPC, 11 BIT<br>mode: 0 `#n`, 1 `abs`, 2 `(X)`, 3 `(X+)`<br>`44` (STA #) and `6C` (BIT #) are illegal |
| `80–8C` | **U** (unary on A) | 80 INC, 81 DEC, 82 NOT, 83 NEG, 84 SHL, 85 ROL, 86 SHR, 87 ROR, 88 ASR, 89 TST, 8A CLC, 8B SEC, 8C SEX |
| `90–94` | **X** | 90 LDX #nn, 91 LDX abs, 92 INX, 93 TAXL, 94 TAXH |
| `98–99` | **W** (16-bit memory) | 98 INCW abs, 99 DECW abs |
| `A0–A5` | **S** (stack/flow) | A0 PHA, A1 PLA, A2 JMP abs, A3 CALL abs, A4 RET, A5 JMPI (abs) |
| `B0–BD` | **B** (branch, absolute) | `B0 + cc` (table 2.3) |
| all other codes, incl. `FF` | illegal | `HALT + MARK`. Erased flash (FF) and zeroed RAM (00) both stop the machine instead of running wild. |

### 2.2 Instruction table
Cycle counts include the 1-cycle fetch. At 1 MHz, 1 cycle = 1 µs.

| Mnemonic | Opcodes (#/abs/(X)/(X+)) | Bytes | Cycles | Effect | Flags |
|---|---|---|---|---|---|
| LDA | 40/41/42/43 | 2/3/1/1 | 2/4/2/2 | A <- M | – |
| STA | –/45/46/47 | –/3/1/1 | –/4/2/2 (+VRAM wait) | M <- A | – |
| ADD | 48–4B | 2/3/1/1 | 2/4/2/2 | A <- A+M | Z C N V |
| ADC | 4C–4F | same | same | A <- A+M+C | Zc C N V |
| SUB | 50–53 | same | same | A <- A−M | Z C N V |
| SBC | 54–57 | same | same | A <- A−M−!C | Zc C N V |
| AND / OR / XOR | 58–5B / 5C–5F / 60–63 | same | same | A <- A op M | Z N, V=0 |
| CMP | 64–67 | same | same | flags of A−M | Z C N V |
| CPC | 68–6B | same | same | flags of A−M−!C | Zc C N V |
| BIT | –/6D/6E/6F | –/3/1/1 | –/4/2/2 | flags of M; A unchanged | N=M7, V=M6, Z=(M==0) |
| INC / DEC | 80 / 81 | 1 | 2 | A <- A±1 | Z N V |
| NOT | 82 | 1 | 2 | A <- ~A | Z N, V=0 |
| NEG | 83 | 1 | 2 | A <- 0−A | Z C N V |
| SHL / ROL | 84 / 85 | 1 | 2 | C <- A7; A <- A<<1, bit 0 = 0 / C | Z C N, V=0 |
| SHR / ROR / ASR | 86 / 87 / 88 | 1 | 2 | C <- A0; A <- A>>1, bit 7 = 0 / C / A7 | Z C N, V=0 |
| TST | 89 | 1 | 2 | flags of A | Z N, V=0 |
| CLC / SEC | 8A / 8B | 1 | 2 | C <- 0 / 1 | C; Z N from A; V=0 |
| SEX | 8C | 1 | 2 | A <- (A7 ? FF : 00), i.e. the high byte of (int)(signed char)A | Z N, V=0 |
| LDX | #nn 90 / abs 91 | 3 / 3 | 3 / 5 | X <- nn / X <- M16 | – |
| INX | 92 | 1 | 2 | X <- X+1 (16-bit) | – |
| TAXL / TAXH | 93 / 94 | 1 | 2 | XL <- A / XH <- A | – |
| INCW / DECW | 98 / 99 | 3 | 7 | M16 <- M16 ± 1; **A is clobbered** (= new high byte) | Zc (16-bit) C N V |
| PHA | A0 | 1 | 2 | [EF:SP] <- A; SP−1 | – |
| PLA | A1 | 1 | 3 | SP+1; A <- [EF:SP] | – |
| JMP | A2 | 3 | 4 | PC <- abs | – |
| CALL | A3 | 3 | 5 | push PCH, push PCL (PC = return address); PC <- abs | – |
| RET | A4 | 1 | 5 | pop PCL, pop PCH | – |
| JMPI | A5 | 3 | 7 | PC <- M16[abs]; **A is clobbered** | – |
| Bcc | B0–BD | 3 | 4 taken / 3 not taken | if cc: PC <- abs | – |
| NOP / HALT | 01 / 00 | 1 | 2 / 2 | – / stop in phase C after this instruction; GO resumes | – |

**Count**

| Group | Mnemonics | Opcodes |
|---|---|---|
| M | 12 | 46 |
| U | 13 | 13 |
| X | 4 | 5 |
| W | 2 | 2 |
| S | 6 | 6 |
| B | 14 | 14 |
| misc (NOP, HALT) | 2 | 2 |
| **Total** | **53** | **88** |

168 opcodes are free.

### 2.3 Branch conditions (`B0 + cc`)
| cc | Mnemonic | Taken if | C meaning (after `CMP lo` / `CPC hi`) |
|---|---|---|---|
| 0 / 1 | BEQ / BNE | Z / !Z | `==` / `!=` (16-bit exact thanks to chained Z) |
| 2 / 3 | BCS=BHS / BCC=BLO | C / !C | unsigned `>=` / `<` |
| 4 / 5 | BMI / BPL | N / !N | sign; KBD ready poll |
| 6 / 7 | BVS / BVC | V / !V | VRAM-window poll after BIT |
| 8 / 9 | BLT / BGE | N≠V / N=V | signed `<` / `>=` |
| A / B | BGT / BLE | !Z & N=V / Z \| N≠V | signed `>` / `<=` |
| C / D | BHI / BLS | C & !Z / !C \| Z | unsigned `>` / `<=` |

### 2.4 What the C subset needs, and where it lives in the ISA
| C need | ISA support |
|---|---|
| 16-bit add/sub | ADD+ADC / SUB+SBC pairs. Loads and stores keep C. |
| All 6 relations, signed and unsigned | `LDA lo; CMP lo; LDA hi; CPC hi; Bcc` |
| 16-bit shifts | `SHL/ROL`, `SHR/ROR`, `ASR/ROR` on byte pairs, using `LDA/STA` between them |
| char -> int | `SEX` (signed), or `LDA #0` (unsigned) for the high byte |
| Pointers | `LDX p; LDA (X)` / `STA (X)`; `p++` via `INCW p` |
| `p[i]` | form the address in A with ADD/ADC, then `TAXL/TAXH` |
| Calls | `CALL/RET` with the hardware stack; arguments in static slots |
| I/O polling | `BIT KSTAT; BPL wait` (keyboard) and `BIT KSTAT; BVC wait` (VRAM window) |
| switch / jump tables | `JMPI` |
| Halt / software breakpoint | `HALT` |

## 3. Datapath

### 3.1 Buses
| Bus | Width | Driven by (exactly one) | Selection | Listeners | Undriven state |
|---|---|---|---|---|---|
| **DB** data | 8 | MEM (ROM/RAM/I/O via /RD), A, PCL, PCH. Each register source has its own 74HC245 with DIR tied A->B. | DSRC (3 bits) -> 74HC138 **#DS**:<br>Y1 = /MRD, Y2 = /OE_A, Y3 = /OE_PCL, Y4 = /OE_PCH<br>Y5/Y6 reserved (XL/XH readback), Y0/Y7 = none<br>The chip is disabled by BUSACK. | ALU B input (both ALU ROMs), IR, ARL, ARH, XL, XH, RAM, the VRAM data 245, the LED latch, the Arduino | 8x 10k pull-downs, so it reads **00** (the emulator models "no source" as 00) |
| **AB** address | 16 | PC, AR, X (2x 245 each), or SP (low byte 245, plus a 245 with inputs strapped to **EF** for the high byte) | ASRC (2 bits) -> half of a 74HC139, **#AS** (/G = BUSACK):<br>Y0 PC, Y1 AR, Y2 X, Y3 SP | ROM, RAM, address decode, VRAM address mux, breakpoint 688s, Arduino | 16x 10k pull-ups, so it reads FFFF (only during BUSACK when the Arduino is absent) |
| **R** ALU result | 8 | the ALU ROM data outputs D0–3, always enabled | – | A only | never floats |
| **PCIN** | 16 | AR outputs, always on | – | the PC 161 P inputs | – |

Only decoder outputs drive the bus-buffer /OE pins. Two DB drivers, or two AB drivers, can therefore never be on at the same time: this is guaranteed by construction, not by microcode discipline.

**Manual data entry.** The DB listens to a passive panel of 8 DIP switches, each switching the line to VCC through 2.2 kΩ against the 10 kΩ pull-down:
- closed switch: about 4.1 V, a valid HIGH;
- an active driver overrides it, sinking at most 2.3 mA;
- with DSRC = none, the bus therefore shows the switch value. No buffer chip is needed (P3 had one).

### 3.2 Registers
All registers are edge-triggered on **CLK rising** (the single commit edge) and use synchronous enables. There are no gated clocks.

| Reg | Parts | Load | Count | Reset | Outputs go to |
|---|---|---|---|---|---|
| PC | 4x 74HC161 | `/PE = /PCLD` on all four; P = AR outputs (16-bit parallel) | CEP = PCINC; CET chained from TC | /MR -> 0000 | AB (2x 245, /OE = #AS.Y0), DB (PCL and PCH 245s), 16 LEDs |
| AR | 4x 74HC161 | P = DB<br>low pair /PE = /DD_ARL (#DD.Y5)<br>high pair /PE = /DD_ARH (#DD.Y6) | CEP = ARINC; CET chained | /MR -> 0000 | PC P inputs, AB (2x 245, #AS.Y1), 16 LEDs |
| X | 4x 74HC161 | P = DB<br>/PE = /DD_XL (Y3) or /DD_XH (Y4) | CEP = XINC; CET chained | /MR -> 0000 | AB (2x 245, #AS.Y2), 16 LEDs |
| SP | 2x 74HC191 | not loadable from DB; D inputs tied high | low /CE = NOT SPCNT<br>high /CE = NAND(SPCNT, MAX/MIN_low)<br>D/U = SPDN (1 = down)<br>CP = CLK | /PL = /RESET_s (asynchronous) -> FF | AB low (245); AB high = the EF-strapped 245 (both /OE = #AS.Y3); 8 LEDs |
| A | 74HC377 | D = R; /E = /DD_A (#DD.Y2) | via ALU | undefined | ALU inputs, DB (245, #DS.Y2), 8 LEDs |
| IR | 74HC377 | D = DB; /E = /DD_IR (#DD.Y1) | – | undefined (step 0 ignores IR) | uROM A4–A11, 8 LEDs |
| F (Z C N V) | 74HC161 used as a 4-bit register | P0..3 = Z_new, C_new, N_new, V_new; /PE = NOT FL | CEP = CET = 0 | /MR -> 0000 | uROM A12–A15; C -> ALU-L A8; Z -> ALU-H A10; 4 LEDs |
| STEP | 74HC161 (section 4) | | | | |

**Datasheet behaviour relied on**
- **74HC161:** load and count are synchronous on the rising CP edge. Load overrides count. /MR is asynchronous. `TC = CET AND Q==1111`.
- **74HC377:** /E is a synchronous enable (the clock is not gated internally).
- **74HC191:**
  - It counts on the rising CP edge, and its parallel load is **asynchronous**. Here it is used only at reset.
  - CE LOW->HIGH may only occur while CP is HIGH, and U/D may only change while CE or CP is HIGH.
  - Both are met: SPCNT and SPDN change at the C->D edge, while CLK = 1. MAX/MIN_low changes just after CLK rises, also while CLK = 1.
  - P3 called this output "TC_lo"; the 191 has no TC pin, so MAX/MIN is used.
- **Cascades with separate byte loads:** when ARL loads with ARINC = 0, CEP = 0 on all four chips, so neither half counts.

### 3.3 ALU: 2x SST39SF010A nibble lookup ROMs
| ROM | Address pins | Data pins |
|---|---|---|
| **ALU-L** | A0–3 = A[3:0]<br>A4–7 = DB[3:0]<br>A8 = C (flag)<br>A9 = A[4]<br>A10–14 = ALUOP0–4<br>A15 = A[7]<br>A16 = table jumper (0) | D0–3 = R[3:0]<br>D4 = **c4** (link)<br>D5 = **Zlo** (R[3:0]==0)<br>D6 = **Clo**<br>D7 = n.c. |
| **ALU-H** | A0–3 = A[7:4]<br>A4–7 = DB[7:4]<br>A8 = c4<br>A9 = Zlo<br>A10 = Z (flag)<br>A11–15 = ALUOP0–4<br>A16 = table jumper (0) | D0–3 = R[7:4]<br>D4 = **Z_new**<br>D5 = **Chi**<br>D6 = **N_new**<br>D7 = **V_new** |

- /CE = /OE = GND and /WE = VCC on both ROMs. Their outputs never reach a shared bus.
- **C_new = Clo OR Chi**, using one 74HC32 gate. The ALU-L table produces Clo, and the ALU-H table produces Chi.
- The link bit c4 carries one of: the nibble carry, the nibble borrow, C (for ROR), or A3 (for SHL/ROL).
- Every op satisfies the nibble-split rule. The only cross-nibble paths are A4 and A7 into ALU-L, and c4, Zlo and Z into ALU-H.

**ALUOP codes** (5 bits; 25 used; both images are generated from `isa.yaml`)

| Code | Name | R = | Z | C | N | V |
|---|---|---|---|---|---|---|
| 00 | PASSB | B (=DB) | B==0 | kept | B7 | **B6** (for BIT) |
| 01 / 02 | ADD / ADC | A+B / A+B+C | R==0 / **chained** | carry | R7 | ovf |
| 03 / 04 | SUB / SBC | A−B / A−B−!C | R==0 / **chained** | no-borrow | R7 | ovf |
| 05 / 06 / 07 | AND / OR / XOR | A op B | R==0 | kept | R7 | 0 |
| 08 / 09 | INC / DEC | A±1 | R==0 | kept | R7 | ovf |
| 0A | NOT | ~A | R==0 | kept | R7 | 0 |
| 0B | NEG | 0−A | R==0 | no-borrow (= A==0) | R7 | A==80 |
| 0C / 0D | SHL / ROL | A<<1, bit 0 = 0 / C | R==0 | A7 (Chi) | R7 | 0 |
| 0E / 0F / 10 | SHR / ROR / ASR | A>>1, bit 7 = 0 / C (via c4) / A7 | R==0 | A0 (Clo) | R7 | 0 |
| 11 | PASSA | A | R==0 | kept | R7 | 0 |
| 12 / 13 | CLC / SEC | A | R==0 | 0 / 1 | R7 | 0 |
| 14 | SEX | A7 ? FF : 00 | R==0 | kept | R7 | 0 |
| 15 / 16 | INCB / ADCB0 | B+1 / B+C | R==0 / **chained** | carry | R7 | ovf |
| 17 / 18 | DECB / SBCB0 | B−1 / B−!C | R==0 / **chained** | no-borrow | R7 | ovf |
| 19–1F | POISON | A5 | 1 | 1 | 1 | 1 |

- **"Kept"** means: Clo = the C input and Chi = 0.
- **CMP** = SUB, **CPC** = SBC, **BIT** = PASSB, each with FL and no destination.
- **Loads** = PASSB with a destination and **no FL**.
- **POISON** codes make a wrong ALUOP visible at once on the A and F LEDs (taken from P3).

**Why a ROM ALU** (all three proposals agree):
- 2 chips instead of about 10–12 (74HC283/86/157 plus a shifter and flag logic).
- Every op, including shifts and a correct V, takes one cycle.
- The same Python function builds the ROM image and the emulator's ALU, so hardware and emulator cannot disagree.
- The cost is two flash delays in series: 140 ns maximum.

### 3.4 Flag generation
- Z, N and V come from ALU-H D4/D6/D7. C comes from the OR of Clo and Chi.
- All four are registered in F at the commit edge when FL = 1. There are no separate gate trees.
- Branch conditions are evaluated by the microcode ROMs, which see Z C N V as address bits.

### 3.5 Address sources and 16-bit moves
| ASRC | Source | Notes |
|---|---|---|
| 00 | PC | The all-zero reset word therefore addresses PC. |
| 01 | AR | |
| 10 | X | |
| 11 | EF:SP | |

**Moving 16-bit values**
- **Into AR or X:** two steps, low byte first. Each DD_xx loads only one half.
- **Into PC:** only from AR, all 16 bits in one step (PCLD). JMP, CALL, Bcc, RET and JMPI all build the target in AR first, so PC never holds a half-updated value.
- **Out of PC:** PCH, then PCL onto DB (for CALL).

**Readable onto DB:** MEM, A, PCL, PCH (plus the passive panel switches).

**Not readable:** X, AR, SP, F, IR and STEP. They are visible on LEDs and in the Arduino trace.

### 3.6 Datapath chips
| Function | Parts | ICs |
|---|---|---|
| PC, AR, X | 74HC161 x12 | 12 |
| F | 74HC161 | 1 |
| SP | 74HC191 x2 | 2 |
| A, IR | 74HC377 x2 | 2 |
| AB drivers (PC 2, AR 2, X 2, SP 1, EF constant 1) | 74HC245 x8 | 8 |
| DB drivers (A, PCL, PCH) | 74HC245 x3 | 3 |
| ALU | SST39SF010A x2 | 2 |
| **Total** | | **30** |

The ALU's C OR gate and the SP carry NAND come from the shared glue chips (section 8).

## 4. Control unit

### 4.1 Microcode ROM address (3x SST39SF010A: uROM0/1/2, address lines in parallel)
| Pin | A0–A3 | A4–A11 | A12 | A13 | A14 | A15 | A16 |
|---|---|---|---|---|---|---|---|
| Signal | STEP[3:0] | IR[7:0] | Z | C | N | V | BANK jumper (0 = known-good, 1 = experimental) |

- **Pins:** /CE = GND and /WE = VCC. **/OE = MANUAL**: in panel mode the ROM outputs float (section 4.10).
- **Programming:** the ROMs are programmed off-board on the T48/TL866II+.
- **Layout:** STEP sits in the low address bits, so a hex dump shows one instruction per 16-byte line.
- **Generator:** it writes every non-branch sequence into all 16 flag combinations. For `Bcc`, it writes either the taken or the not-taken sequence according to the condition.

### 4.2 Control word
24 bits, **active-high in the ROM**. The word is latched by 3x 74HC273 on **LCLK** (the C->D edge). /MR = /RESET_s.

| ROM | Bit | Name | Meaning |
|---|---|---|---|
| uROM0 | 0–1 | ASRC | address source: 0 PC, 1 AR, 2 X, 3 EF:SP (-> #AS) |
| | 2–4 | DSRC | DB source: 0 none, 1 MEM (/MRD), 2 A, 3 PCL, 4 PCH, 5–6 reserved (XL/XH readback), 7 none/panel (-> #DS) |
| | 5–7 | DDST | DB/R destination: 0 none, 1 IR, 2 A (from R), 3 XL, 4 XH, 5 ARL, 6 ARH, 7 forbidden (-> #DD) |
| uROM1 | 8–12 | ALUOP | section 3.3 |
| | 13 | FL | load Z C N V at commit |
| | 14 | MEMW | memory/I/O write; the strobe is made in phase A |
| | 15 | MARK | scope-trigger test point, LED and trace marker |
| uROM2 | 16 | PCINC | PC+1 at commit |
| | 17 | PCLD | PC <- AR (16 bits) at commit |
| | 18 | ARINC | AR+1 |
| | 19 | XINC | X+1 |
| | 20 | SPCNT | SP counts at commit |
| | 21 | SPDN | 1 = down (push), 0 = up (pop) |
| | 22 | NEXT | STEP <- 0 at commit (last step of the instruction) |
| | 23 | HALT | stop in phase C after this step |

- **The all-zero word is a true NOP:** ASRC = PC, nothing driven, nothing loaded, and no flag load. This fixes P1's /FL bug.
- **Unused step words** are `HALT MARK NEXT`.
- **One 74HC04 fixes polarities:** FL -> F /PE, PCLD -> PC /PE, NEXT -> STEP /PE, SPCNT -> SP /CE_lo, MEMW -> /MEMW. The sixth gate is spare.
- **24 LEDs** (3.3k, ~1 mA each) sit on the latch outputs.

### 4.3 Decoders
| Decoder | Part | Inputs | Outputs | Enable |
|---|---|---|---|---|
| **#DS** | 74HC138 | DSRC | Y1 /MRD, Y2 /OE_A, Y3 /OE_PCL, Y4 /OE_PCH | G1 = VCC, /G2A = BUSACK, /G2B = GND |
| **#DD** | 74HC138 | DDST | Y1 /DD_IR, Y2 /DD_A, Y3 /DD_XL, Y4 /DD_XH, Y5 /DD_ARL, Y6 /DD_ARH | always enabled |
| **#AS** | half of a 74HC139 | ASRC | Y0–Y3 -> the /OE pairs of the AB 245s | /G = BUSACK |

The #DD outputs are synchronous load enables, never clocks. Decoder glitches in phases D and A are therefore harmless: the enables only have to be stable at the commit edge.

The other half of the 74HC139 is the memory-page decoder (section 6).

### 4.4 Step counter
- **Part:** 74HC161, CP = CLK (commit edge), CEP = CET = 1.
- **Return to step 0:** `/PE = NOT NEXT` with P = 0000. This is a synchronous load, so there is no glitchy "decode N -> /CLR".
- **Reset:** /MR = /RESET_s.
- **Indicators:** 4 LEDs.
- **Longest instructions:** INCW, DECW and JMPI use 7 of the 16 steps.

### 4.5 Fetch (step 0, identical for all 256 opcodes, all 16 flag values and both banks)
`ASRC=PC DSRC=MEM DDST=IR PCINC`

1. **Phases D/A/B:** M[PC] reaches DB.
2. **Commit edge:** IR <- M[PC], PC <- PC+1, STEP <- 1.
3. **Phase C:** the uROMs look up (new IR, step 1, current flags).
4. **C->D edge:** the first execute word is latched.

Fetch is 1 cycle; there is no separate decode step.

### 4.6 Microstep tables
Notation:
- Columns hold ASRC / DSRC / DDST / ALUOP, then the other active bits. A dash means 0 or none.
- `op` stands for the instruction's ALUOP (section 3.3).
- **Each step is one full cycle: C->D latch, D, A, B, commit.**

**Fetch and common operand steps**
| Step | ASRC | DSRC | DDST | ALUOP | Other bits |
|---|---|---|---|---|---|
| S0 FETCH | PC | MEM | IR | – | PCINC |
| OP1 (abs low) | PC | MEM | ARL | – | PCINC |
| OP2 (abs high) | PC | MEM | ARH | – | PCINC |

**Group M: loads, stores, ALU ops, compares, BIT** (op = PASSB for LDA and BIT; SUB for CMP; SBC for CPC)
| Instruction / mode | S1 | S2 | S3 | Cycles |
|---|---|---|---|---|
| LDA #n | PC / MEM / A / PASSB · PCINC NEXT | | | 2 |
| ALU #n (ADD…XOR) | PC / MEM / A / op · FL PCINC NEXT | | | 2 |
| CMP, CPC #n | PC / MEM / – / op · FL PCINC NEXT | | | 2 |
| LDA abs | OP1 | OP2 | AR / MEM / A / PASSB · NEXT | 4 |
| ALU abs | OP1 | OP2 | AR / MEM / A / op · FL NEXT | 4 |
| CMP, CPC, BIT abs | OP1 | OP2 | AR / MEM / – / op · FL NEXT | 4 |
| STA abs | OP1 | OP2 | AR / A / – / – · MEMW NEXT | 4 (+wait) |
| LDA (X) | X / MEM / A / PASSB · NEXT | | | 2 |
| ALU (X) | X / MEM / A / op · FL NEXT | | | 2 |
| CMP, CPC, BIT (X) | X / MEM / – / op · FL NEXT | | | 2 |
| STA (X) | X / A / – / – · MEMW NEXT | | | 2 (+wait) |
| any (X+) | as (X), plus XINC | | | 2 |

**Group U: unary on A** (DB is undriven and reads 00; ALU input B is ignored)
| Instruction | S1 | Cycles |
|---|---|---|
| INC DEC NOT NEG SHL ROL SHR ROR ASR SEX | – / – / A / op · FL NEXT | 2 |
| TST | – / – / – / PASSA · FL NEXT | 2 |
| CLC, SEC | – / – / – / CLC, SEC · FL NEXT | 2 |

**Groups X and W**
| Instruction | S1 | S2 | S3 | S4 | S5 | S6 | Cycles |
|---|---|---|---|---|---|---|---|
| LDX #nn | PC/MEM/XL · PCINC | PC/MEM/XH · PCINC NEXT | | | | | 3 |
| LDX abs | OP1 | OP2 | AR/MEM/XL · ARINC | AR/MEM/XH · NEXT | | | 5 |
| INX | XINC NEXT | | | | | | 2 |
| TAXL / TAXH | –/A/XL · NEXT (XH for TAXH) | | | | | | 2 |
| INCW abs | OP1 | OP2 | AR/MEM/A/INCB · FL | AR/A/–/– · MEMW ARINC | AR/MEM/A/ADCB0 · FL | AR/A/–/– · MEMW NEXT | 7 |
| DECW abs | OP1 | OP2 | …/DECB · FL | as INCW | …/SBCB0 · FL | as INCW | 7 |

**Group S: stack and flow (PUSH, POP, CALL, RET, JMP)**
| Instruction | S1 | S2 | S3 | S4 | S5 | S6 | Cycles |
|---|---|---|---|---|---|---|---|
| PHA (push) | SP/A/–/– · MEMW SPCNT SPDN NEXT | | | | | | 2 |
| PLA (pop) | SPCNT | SP/MEM/A/PASSB · NEXT | | | | | 3 |
| JMP abs | OP1 | PC/MEM/ARH | PCLD NEXT | | | | 4 |
| CALL abs | OP1 | OP2 (PC = return address) | SP/PCH/–/– · MEMW SPCNT SPDN | SP/PCL/–/– · MEMW SPCNT SPDN **PCLD** NEXT | | | 5 |
| RET | SPCNT | SP/MEM/ARL · SPCNT | SP/MEM/ARH | PCLD NEXT | | | 5 |
| JMPI (abs) | OP1 | OP2 | AR/MEM/A/PASSB · ARINC | AR/MEM/ARH | –/A/ARL | PCLD NEXT | 7 |

- **CALL S4** writes the *old* PCL in phase A. The PC is replaced only at the commit edge that ends that step.
- **Stack after CALL:** PCH is at [EF:SP0], PCL is at [EF:SP0−1], and SP = SP0−2. RET reverses this exactly.

**Group B: conditional branches** (the flags are uROM address bits; flags never change inside a Bcc)
| Case | S1 | S2 | S3 | Cycles |
|---|---|---|---|---|
| taken | OP1 | OP2 | PCLD NEXT | 4 |
| not taken | PCINC | PCINC NEXT | | 3 |

**Misc**
| Instruction | S1 | Cycles |
|---|---|---|
| NOP | NEXT | 2 |
| HALT | HALT NEXT | 2 (then stopped) |
| illegal | HALT MARK NEXT | 2 |

**I/O polling, loads and stores of I/O (no special opcodes; memory-mapped)**
| Code | Microsteps | Cycles |
|---|---|---|
| `w: BIT KSTAT` (F801) | OP1, OP2, `AR/MEM/–/PASSB · FL NEXT`. The STATUS 245 drives DB, giving N = KRDY and V = VWR. | 4 |
| `BPL w` | Bcc | 4 / 3 |
| `LDA KBD` (F800) | the LDA abs microsteps. At the commit the KCLR flip-flop captures `KBD read AND KRDY`, and the next cycle clears the receiver (6.4). | 4 |
| `STA $F000+n` | the STA abs microsteps. In phase D, `WAIT = MEMW & VRAMSEL & !VWR_s` holds the machine in D until the window opens; the write then happens in phase A. | 4 + wait |

The poll loop is 8 cycles per iteration.

**Rules checked by the microcode generator** (from `isa.yaml`):
1. MEMW implies DSRC ∈ {A, PCL, PCH}. MEM is never a source in a write step, so memory /OE is never active during /WE.
2. DDST ≠ 7. DSRC ∈ {5, 6} is forbidden until X readback exists.
3. PCLD and PCINC are never set together.
4. DDST=A always comes with an explicit ALUOP (PASSB for loads).
5. A step without a memory access uses DSRC=none, so a read side effect (the KBD clear) can never happen by accident.
6. Push steps use SPDN=1 with MEMW. Pop steps use SPDN=0 before a read.
7. Step 0 is FETCH for every IR, flag and bank combination.
8. Every path reaches NEXT within 16 steps. Unused words are `HALT MARK NEXT`.
9. Flags written in step k are visible to the lookup of step k+1. The commit happens before phase C, so P2's "no branch on the previous step's flags" restriction does not exist here.

### 4.7 Conditional branches
- There is no condition hardware. For opcode B0+cc, the generator evaluates cc on each of the 16 (Z, C, N, V) address combinations and writes the taken or not-taken sequence.
- Signed conditions (LT/GE/GT/LE) and unsigned conditions (HI/LS) are pure table content.

### 4.8 Reset
**Synchronizer**
- A power-on RC (10k/10 µF), the RESET button and an Arduino open-drain line feed a 74HC14.
- They then pass through 2 flip-flops of a 74HC74 on MCLK.
- Assertion is asynchronous. Release is synchronous to MCLK.

**What /RESET_s does (asynchronously)**
- The Johnson counter is preset to **phase C**.
- The control latch is cleared to the NOP word.
- STEP, PC, AR, X and F are cleared to 0.
- SP is loaded with FF (191 /PL).
- The BRK and BUSACK flip-flops are cleared.
- The PS/2 shift registers are cleared.

**After release**
- The next C->D edge latches FETCH, and execution starts at **0000** with **SP = FF**.
- In STEP mode, the machine waits for GO first.
- The VGA counters are not reset; they recover within one frame.

**Boot ROM at 0000**
- It clears VRAM, copies .data and clears .bss, then calls `main`.
- If DIP switch SW0 = 1 (STATUS bit 0), it jumps to 8000 instead. That is where the Arduino has loaded a program.

### 4.9 HALT, stepping, breakpoint (all stops happen in phase C, at a cycle boundary)
```
STOP = BRQ_s | ( (HALT_L | BRK_L | (STEPMODE_s & (MICRO | NEXT_L))) & !GO )
```
| Signal | Meaning |
|---|---|
| **HALT_L, NEXT_L** | Bits of the still-latched word, i.e. the step that just committed. HALT also has NEXT, so GO continues with the next instruction. `HALT` is therefore also a software breakpoint. |
| **STEPMODE_s** | The RUN/STEP switch, synchronized. |
| **MICRO** | A switch that chooses between stopping after every step and stopping only after NEXT, i.e. after each whole instruction. |
| **GO** | The STEP/CONTINUE button -> RC + 74HC14 -> 74HC175 (sync1, sync2, prev). `GO = sync2 & !prev` lasts exactly one MCLK, so exactly one cycle runs. |
| **BRK_L** | The breakpoint/watchpoint flip-flop (described below). |

**Breakpoint and watchpoint (BRK_L)**
- **Address compare:** 74HC688 #1 compares AB[7:0] with 8 DIP switches. Its /G is the BP-enable switch. Its /P=Q output feeds the /G of 74HC688 #2 (AB[15:8]), whose /P=Q output is /MATCH (16-bit, no extra gate).
- **Access qualifier:** `/ACCESS = AND(/MRD, /MEMW)`.
- **Flip-flop:** clocked by CLK, with `D = NOR(/MATCH, /ACCESS)`.
- **Effect:** the machine stops after any fetch, operand read or write of that address. The same hardware gives instruction breakpoints and data watchpoints. GO continues.

**Indicator LEDs:** phase Q1 and Q2, STOP, WAIT, HALT, BRK, BUSACK, MARK.

### 4.10 BUSREQ, and the manual control panel
**BUSREQ (taken from P3)**
1. The Arduino's /BUSREQ (10k pull-up, so it is inert when the Arduino is absent) passes through a 2-FF synchronizer and becomes BRQ_s, which forces STOP.
2. The BUSACK flip-flop (on MCLK) has `D = BRQ_s & Q1 & Q2`, so it rises only once the CPU is parked in C.
3. BUSACK disables #DS and #AS.
   - Since the CPU is parked in C, no commit happens and WSTB = 0. All CPU drivers of AB, DB, /RD and /WR are therefore off.
4. The Arduino drives AB and DB through 470 Ω series resistors, plus /ARD_RD and /ARD_WR, which are ANDed into /RD and /WR.

Protocol: assert -> wait for BUSACK -> load or inspect -> release the pins -> deassert. The CPU resumes exactly where it stopped. **No chips on the Arduino side.**

**Manual control panel (0 chips)**
1. The MANUAL switch drives uROM /OE high.
2. Each of the 24 latch input lines has a 47k pull-down and a DIP switch to VCC through 4.7k.
   - When the ROMs are enabled they override closed switches, sinking about 1 mA. A forgotten switch is therefore harmless.
3. Together with the passive DB data switches and GO in MICRO mode, any hand-set word goes through the real latch, decoders and timing.
   - Example: `DSRC=none DDST=A ALUOP=PASSB FL` with data 80, then GO, gives A = 80 and N = 1.

### 4.11 Control-unit chips
| Function | Parts | ICs |
|---|---|---|
| Microcode ROMs | SST39SF010A x3 | 3 |
| Control latch | 74HC273 x3 | 3 |
| #DS, #DD | 74HC138 x2 | 2 |
| #AS (+ memory page decode) | 74HC139 | 1 |
| STEP | 74HC161 | 1 |
| Polarity fix-ups | 74HC04 | 1 |
| Breakpoint | 74HC688 x2 | 2 |
| **Total** | | **13** |

The BRK flip-flop is in the clock module.

## 5. Clocking and timing

### 5.1 Clock module: a 4-phase cycle (taken from P3)
**MCLK** is 4x the CPU clock. One half of a 74HC153 selects the source; the select switch only changes while stopped (phase C holds its state, so runts are harmless).

| Select | Source | CPU clock |
|---|---|---|
| I0 | 4.000 MHz oscillator can | **1 MHz** (default) |
| I1 | socket for a 6 MHz or 8 MHz can | 1.5 / 2 MHz |
| I2 | NE555 astable, squared by a 74HC14 | ~0.25 Hz–1 kHz |
| I3 | Arduino pin | trace mode |

- The select bit **S1 = 1 means a slow source**. It is routed as the signal **SLOW** to the VGA timing ROM A16 (section 6.3).
- **Johnson counter.** Two 74HC74 flip-flops on MCLK step through **A=00 -> B=10 -> C=11 -> D=01**. Next-state logic uses four gates of a 74HC00:
  - `Q1' = !Q2 | (STOP & Q1)` holds in **C** while STOP = 1.
  - `Q2' = Q1 | (WAIT & Q2)` holds in **D** while WAIT = 1.
  - /RESET_s presets both flip-flops, which parks the counter in C.
- **Derived signals.** All are glitch-free, because neighbouring states differ in one bit.

| Signal | Definition | Behaviour |
|---|---|---|
| CLK | Q2 | rises at **B->C**: the only commit edge |
| LCLK | /Q1 | rises at **C->D**: loads the control latch |
| WSTB | NOR(Q1, Q2) | phase A |

- **Distribution**
  - CLK goes through one 74HC245, used as an 8-output clock buffer.
  - Each output carries a 47 Ω series resistor and feeds a star branch of at most 4 loads: PC | AR | X | SP + STEP | **A + F + IR** | LED latch + BRK + KCLR | test point.
  - A and F must sit on the same branch: the A -> ALU -> F self-loop has only the A clk-to-Q time (~8 ns minimum) as hold margin.
  - LCLK drives the three 273s directly from the 74HC74 through 33 Ω.
  - Every chip has a 100 nF capacitor; every board has 10–47 µF.
- **Why 4 phases.** It satisfies the baseline's intent (control word registered away from the register edge, registers loaded with enables), but with a cleaner split:
  - one commit edge;
  - the control word changes **1/4 cycle after** the commit, so there is no same-edge race (P1 and P2 both have one);
  - /WE gets a full phase of address setup and a full phase of hold;
  - every stop and BUSREQ happens at a cycle boundary;
  - the VRAM stall has a phase to wait in (D);
  - the 191 rules are met for free.
  
  The cost over a 2-phase clock is about 1 chip.

### 5.2 One CPU cycle (1 MHz: MCLK = 4 MHz, phase = 250 ns)
| Edge / phase | What happens |
|---|---|
| **C->D** (LCLK rises) | The control latch loads the next word, unless STOP. CLK stays high. SPCNT/SPDN change while the 191 CP (= CLK) is high, as the 191 requires. |
| **D** | Decoders switch. The AB and DB sources settle and memory access starts. WAIT is evaluated and sampled at D->A. |
| D->A (CLK falls) | Nothing is clocked. WSTB rises. |
| **A** | /WE is low if MEMW. A VRAM write only gets here when VWR_s = 1. |
| A->B | /WE rises. |
| **B** | Everything stays stable for a whole phase. Read data and the ALU result settle. |
| **B->C** (CLK rises) | **Commit.** PC, AR, X, SP, A, IR, F, STEP, the LED latch, BRK and KCLR each load if enabled. |
| **C** | The uROMs look up (new STEP, IR, flags). STOP is evaluated. A stopped machine always rests here. |

### 5.3 RAM /WE and why it is safe
| Signal | Logic |
|---|---|
| /MWR | NAND(MEMW_L, WSTB) |
| /WR | AND(/MWR, /ARD_WR) |
| RAM /WE | /WR (RAM /CE from the decoder) |
| VRAM /WE | OR(/WR, /VRAMSEL) |
| ROM /WE | tied high |
| LED latch | uses an enable sampled at commit, not a strobe |

| AS6C62256-55 parameter | Spec | Provided at 1 MHz | Provided at 2 MHz |
|---|---|---|---|
| tAS (address setup to /WE low) | 0 | ≥ 150 ns (AB settles ≤ 100 ns into D) | ≥ 25 ns |
| tWP (/WE width) | 45 ns | 250 ns | 125 ns |
| tDW (data setup to /WE high) | 25 ns | ≥ 400 ns | ≥ 150 ns |
| tWR, tDH (hold after /WE high) | 0 | 250 ns (all of phase B) | 125 ns |

**Why /WE is safe**
- Address and data sources change only at C->D (new control word) and at B->C (commit). Both are a full phase away from phase A.
- Generator rule 1 keeps memory /OE off in write steps.
- At C->D, bus turnaround (e.g. MEM -> A) overlaps for a few ns at low current. That is at least 2 phases before anything samples.

### 5.4 Critical paths
Typical / maximum 74HC delays at 5 V, 25 °C:
- 273 or 377 clk->Q: 14 / 30; 161 clk->Q: 17 / 40
- 138/139: 15 / 35
- 245: enable 18 / 38, through 10 / 22
- gate: 9 / 25
- setup: 161 15 / 30, 273 12 / 20

Memories: SST39SF010A 70 ns maximum (≈55 typical); AS6C62256 55 ns.

| Path | Window | typ | max | 1 MHz | 1.5 MHz (6 MHz MCLK) | 2 MHz (8 MHz MCLK) |
|---|---|---|---|---|---|---|
| 1. Read + ALU into A/F: 273 -> 139 -> 245 enable -> 74HC20/00 decode -> flash 70 -> ALU-L 70 -> ALU-H 70 -> OR -> 161 setup | D+A+B | 254 | 403 | 750 ✔ | 500 ✔ | 375: typ ✔, max ✘ |
| 2. uROM lookup: CLK buffer -> 161/377 clk->Q -> uROM 70 -> 273 setup | C | 94 | 152 | 250 ✔ | 167 ✔ | 125: typ ✔, max ✘ |
| 3. WAIT decision: 273 -> 139 -> 245 -> 74HC20 -> **74HC27** -> 2x NAND (Johnson) -> 74 setup | D | ~100 | ~223 | 250 ✔ | 167: typ ✔ | 125: typ ✔ |
| 4. Fetch into IR (no ALU) | D+A+B | 135 | 245 | ✔ | ✔ | ✔ |
| 5. 16-bit 161 TC ripple (PC/AR/X) | full cycle | 60 | 135 | ✔ | ✔ | ✔ |

**Fix applied for path 3.** The WAIT gate is a single 3-input NOR: `WAIT = NOR3(/FPAGE, A11, NAND(MEMW_L, /VWR_s))`, using a 74HC27.
- This avoids the 74HC139 page decode on the timing path.
- It brings the worst case to about 223 ns. That is below the 250 ns available at 1 MHz, even with every delay at its 25 °C maximum.

**Clock-rate verdict**
- **1 MHz** is guaranteed at worst-case values on every path.
- **1.5 MHz** is guaranteed except the WAIT path, which is fine at typical values.
- **2 MHz** works at typical values on every path, but must be confirmed on the scope.
- The fallback for 2 MHz is a 6-state counter: one more 74HC74 and a 12 MHz can, giving phases C and D two MCLKs each.
- SST39SF010-**90** old stock (n11) adds 20 ns per flash. That is fine at ≤ 1.5 MHz.
- **Hold margins:** every register samples at the commit edge, and its data can change only at the earliest one clk->Q time (~8 ns) after that edge. With one clock-buffer package (skew 2–5 ns) and hold times of ≤ 5 ns, all hold margins are positive.

### 5.5 Clock / reset / stop chips
| Function | Parts | ICs |
|---|---|---|
| 555 astable | NE555 | 1 |
| Source select | 74HC153 | 1 |
| Debounce, reset RC, 555 squaring | 74HC14 | 1 |
| Johnson counter + reset synchronizer | 74HC74 x2 | 2 |
| BRK + BUSACK flip-flops | 74HC74 | 1 |
| Synchronizers (BRQ x2, VWR x2, GO sync1/sync2/prev, STEPMODE) | 74HC175 x2 | 2 |
| Johnson next-state | 74HC00 | 1 |
| STOP, WSTB, BUSACK D, /ACCESS, BRK D | 74HC08, 74HC32, 74HC02 | 3 |
| WAIT | 74HC27 | 1 |
| CLK buffer | 74HC245 | 1 |
| **Total** | | **14** |

Plus the 4 MHz can (and an optional 6 or 8 MHz can).

## 6. Memory and I/O

### 6.1 Address decode
| Signal | Logic | Part |
|---|---|---|
| ROM /CE | = A15 | wire |
| /FPAGE (F000–FFFF) | NAND4(A15, A14, A13, A12) | 74HC20 (half) |
| RAM /CE (8000–EFFF) | NAND(A15, /FPAGE) | 74HC00 gate |
| /VRAMSEL, /IOSEL | 74HC139 half **#MS**: /G = /FPAGE, A = A11, B = GND.<br>Y0 = /VRAMSEL (F000–F7FF), Y1 = /IOSEL (F800–FFFF) | 74HC139 (shared with #AS) |
| /RD | AND(/MRD, /ARD_RD) | 74HC08 gate |
| /WR | AND(/MWR, /ARD_WR) | 74HC08 gate |
| **#IOR** | 74HC138: A, B, C = A0, A1, A2; G1 = VCC; /G2A = /IOSEL; /G2B = /RD.<br>Y0 = /KBD_RD (F800), Y1 = /STAT_RD (F801), Y2–Y7 reserved | 74HC138 |
| /LED_E | OR(/IOSEL, /MEMW). This is a synchronous enable of the LED 74HC377, sampled at commit (CP = CLK). | 74HC32 gate |
| WAIT | NOR3(/FPAGE, A11, NAND(MEMW_L, /VWR_s)) | 74HC27 + 74HC00 gate |
| VRAM /WE | OR(/WR, /VRAMSEL) | 74HC32 gate |

- **ROM** (SST39SF010A): A0–A14 from AB; A15/A16 from jumpers (4 program banks); /OE = /RD; /WE = VCC. An AT28C256 is a drop-in alternative.
- **RAM** (AS6C62256-55): A0–A14 from AB; /OE = /RD; /WE = /WR.
- Memory data pins connect directly to DB.

### 6.2 I/O registers
I/O occupies F800–FFFF. A2..A0 are decoded, so each register is mirrored every 8 bytes.

| Address | R/W | Name | Bits / meaning |
|---|---|---|---|
| F000–F7FF | W | VRAM | Character code at `F000 + 64*row + col`, with row 0–29 and col 0–39. Columns 40–63 are stored but never shown. The write stalls until the window opens. Reads return 00. |
| F800 | R | KBD | PS/2 scan-code byte (set 2, raw). Reading it while KRDY = 1 clears KRDY and releases the keyboard. Reading it while KRDY = 0 has no side effect. |
| F801 | R | KSTAT | **b7 = KRDY** (`BIT` -> N, so BPL/BMI test it)<br>**b6 = VWR_s**, VRAM window open (`BIT` -> V, so BVC/BVS test it)<br>**b5–b0 = user DIP switches SW5..SW0**; SW0 = "boot the program in RAM at 8000" |
| F802–F807 | R | reserved | read 00 |
| F800 | W | LEDS | 8 LEDs (74HC377). Every write to F800–FFFF currently lands here; software uses F800 only. |

### 6.3 VRAM write path and window gating
**Windows.** The VGA timing ROM produces two signals, registered in T1 (VGA domain):

| Window | Lines | Meaning |
|---|---|---|
| **VMUX** | 481–523 | The CPU owns VRAM. |
| **VWR** | 482–522 | The CPU may start a write. |

There is one whole line (31.8 µs) of guard on each side. VWR is open for 41 lines = **1.30 ms per frame**, about 1,300 CPU cycles at 1 MHz.

**Synchronizer.** VWR passes through 2 flip-flops of a 74HC175 on MCLK, giving VWR_s and /VWR_s. VWR_s feeds KSTAT b6 and WAIT.

**Stall, don't drop** (all three proposals agree). `WAIT = MEMW & VRAMSEL & !VWR_s` holds the machine in phase D until the window opens. The write then happens normally in phase A, so a write is never lost. The WAIT LED shows when software is too slow.

**Data path**
- **Address:** 3x 74HC157 with select = VMUX. When VMUX = 1 the CPU side (AB[10:0]) is selected. When VMUX = 0 the VGA side ({V8..V4, H5..H0}) is selected.
- **Data:** a 74HC245 copies DB to the VRAM, with **/OE = /BUFEN**, a third registered window from the timing ROM.
  - /BUFEN starts at line 481, character 10, and ends at line 523, character 40.
  - That is strictly inside VMUX: about 6 µs after the VRAM outputs turn off (VRAM /OE = VMUX), and 6 µs before they turn back on. The VRAM outputs and the 245 can therefore never overlap.
  - It contains the whole VWR window, with at least 25 µs of margin on each side.
- **Write:** VRAM /WE = OR(/WR, /VRAMSEL). It is low only in phase A of a granted write.
- **Fix of P3 error 1:** no synchronizer output is in the data path. Only registered VGA-domain windows (VMUX, /BUFEN) gate the data. Both are register outputs that change at least 25 µs away from any granted write.

**Safety argument**
1. VWR_s lags VWR by at most 2 MCLK (0.5 µs).
2. A granted write's phase A starts at most 1 MCLK after VWR_s was seen as 1 and lasts 1 MCLK.
3. So /WE is low no more than ~1 µs after VWR was last 1.
4. VMUX remains 1 for at least 31 µs after VWR ends. At the start of the window, VMUX rises one line before VWR.

**Slow clock modes (fix of P3 error 2)**
- SLOW is 1 when the MCLK source is the 555 or the Arduino. It drives timing-ROM A16.
- Timing-ROM bank 1 has identical sync timing, but with VMUX = VWR = 1 at all times.
  - The CPU then owns VRAM permanently: the picture is garbage, but the syncs stay valid.
  - A write that takes seconds therefore cannot outlast the window.
- SLOW changes only while the CPU is stopped.
- A **NO-VGA jumper** forces VWR_s = 1 (P2's idea), so the CPU never hangs when the VGA board is unplugged.

### 6.4 PS/2 receiver
Parts: 2x 74HC164, 74HC540, 74HC14, 74HC74, 74HC11, a 2N7000, 3x 1N4148, 22k, 10 nF, 100k, and 2x 4.7k.

| Function | Implementation |
|---|---|
| Line interface | KCLK and KDATA each have a 4.7k pull-up and go into the 74HC14. Mini-DIN-6: pin 1 = data, 3 = GND, 4 = +5 V (≤ 100 mA), 5 = clock. |
| Shift clock | KCLK -> 14 -> 14 = KCLK_b. The 164s shift on the **rising** KCLK edge. The keyboard holds data valid at least 5 µs after the rising edge, and a rising-edge shift gives the timeout at least 30 µs to release first. |
| Serial data | /KDATA (one 74HC14 gate) enters SR1. SR1.Q7 feeds SR2. Both registers start cleared. |
| Frame marker (taken from P1) | The start bit (0) enters inverted as a 1.<br>After the 11th rising edge, it sits at bit 10 = **SR2.Q2 = KRDY**.<br>The inverted data bits are at d0 = SR2.Q1, d1 = SR2.Q0, d2..d7 = SR1.Q7..Q2.<br>Parity is SR1.Q1 and the stop bit is SR1.Q0 (= 0 for a good frame). |
| Read buffer | The 74HC540 (inverting, tri-state) puts the true byte on DB. /OE1 = /KBD_RD, /OE2 = GND. |
| Inhibit | KRDY and KCLR are diode-ORed (2x 1N4148, 100k pull-down) into the 2N7000 gate. The drain pulls KCLK low.<br>While a byte is waiting or being cleared, the keyboard is inhibited and buffers keys internally, and the register cannot change while the CPU reads it. **This fixes P2 errors 1 and 2.** |
| Clear on read | KCLR is a 74HC74 flip-flop with CP = CLK (commit) and `D = AND(KBD_RD, KRDY)`.<br>It is set at the commit of a read step that saw KRDY = 1, and cleared at the next commit.<br>`/CLR164 = AND3(/RESET_s, /KCLR, /TIMEOUT)` (74HC11).<br>The register is therefore cleared for exactly one cycle, **after** A has captured the byte. A read with KRDY = 0 does nothing. **This fixes P1 error 8.** |
| Resync timeout | 22k from KCLK_b to a node with 10 nF to GND; a 1N4148 from the node to KCLK_b discharges it.<br>When KCLK stays high for about 190 µs, the node crosses V_T+, a 74HC14 gate drives /TIMEOUT low, and the partial frame is discarded.<br>Any KCLK low discharges the node in about 1 µs. The longest high time inside a frame is about 50 µs, so a valid frame is never cut.<br>While KRDY = 1, KCLK is held low, so a waiting byte can never time out. |

**Synchronization to the CPU clock**
- KRDY changes only at a KCLK rising edge, together with the data bits, and then stays 1 until the CPU clears it.
- The CPU samples KRDY once, through KSTAT, at a commit edge. A sample that coincides with the transition reads 0 or 1; both are valid, and the flip-flop resolves in nanoseconds while the next use is 250 ns away.
- Software rule: read F800 only after seeing KRDY = 1. By then the data is frozen by the inhibit. No synchronizer chip is needed.

**Software side (in the runtime, not hardware).** A small state machine:
- ignores `F0 xx` (break codes) and the `E0` prefix;
- maps W/A/S/D and the arrow keys;
- boot code does one dummy poll-and-read.

### 6.5 Arduino debug board (optional; unplugged for the demo)
- **Connections (about 58 Mega pins):**
  - AB16, DB8, CW24;
  - Q1, Q2, CLK, STOP, BUSACK;
  - /BUSREQ, /ARD_RD, /ARD_WR, /RESET (open drain), MCLK out (into 153 input I3).
- AB, DB and the strobes go through 470 Ω series resistors. No chips are used.
- **Trace mode:** the Arduino supplies MCLK, 4 pulses per cycle. It logs AB, DB and CW at each commit and diffs them against the Python microstep emulator.
- **Load mode:** BUSREQ, then write RAM from 8000, then release. Then RESET with SW0 = 1.
- **Arduino VRAM writes:** use them only in SLOW mode. In SLOW mode the CPU side owns VRAM, which also holds during BUSACK.

### 6.6 Memory / I/O / PS/2 chips
| Board | Parts | ICs |
|---|---|---|
| Memory + I/O | SST39SF010A (ROM), AS6C62256 (RAM), 74HC20, 74HC138 (#IOR), 74HC377 (LEDs), 74HC245 (KSTAT + switches) | 6 |
| PS/2 | 74HC164 x2, 74HC540, 74HC14, 74HC74, 74HC11 | 6 |

The VRAM path (VRAM, 3x 157, 245) sits on the VGA board and is counted in section 7.

## 7. VGA module (640x480@60 timing, 40x30 text, 8x8 font doubled to 16x16, monochrome v1)

### 7.1 Clocks and the character load pulse
- **Dot clock (DCLK).** A 25.175 MHz can drives a 74HC74 toggle flip-flop, giving 12.5875 MHz (79.4 ns). One DCLK is one font pixel, i.e. 2 VGA pixels.
- **Dot counter.** A 74HC163 runs free on DCLK. Q2..Q0 is the dot index; Q3 is unused.
- **Load pulse flip-flop (LD).** The second half of the 74HC74, on DCLK, with `D = AND3(Q2, Q1, Q0)` (one 74HC11 gate; this is index 7).
  - LD is high for exactly one dot, index 0 of the next slot.
  - **/LD** is the synchronous load enable for everything at the character boundary, which is the E(0->1) DCLK edge. It is registered (P3's idea), so no combinational decode feeds a dot-rate enable.
- **CCLK = /LD** (rising at E(0->1) + clk->Q). The H and V counters step about 40 ns **after** the boundary registers have sampled, and the next boundary is a whole slot (635 ns) later (P1's idea).

### 7.2 Counters (all synchronous, 74HC163, on CCLK)
| Counter | Parts | Range | Control |
|---|---|---|---|
| HCHAR | 2x 163 (6 bits used) | 0–49 | ENP = ENT = 1; /CLR (synchronous) = /HEND from the timing ROM |
| VLINE | 3x 163 (10 bits used) | 0–524 | ENP = HEND = NOT /HEND (one 74HC04 gate); ENT chained from TC; /CLR (synchronous) = /VEND |

- The ROM outputs are combinational, but they are sampled only at the next CCLK edge, so glitches do not matter.
- Unused ROM entries (H ≥ 50, V ≥ 525) assert /HEND and /VEND, so the counters recover from any power-up state within one frame.
- No asynchronous self-reset is used. **This fixes P1 error 5.**

### 7.3 Timing ROM (SST39SF010A)
**Address:** A0–A5 = H, A6–A15 = V, A16 = SLOW.

| Bit | Signal | Bank 0 (normal) | Bank 1 (SLOW) |
|---|---|---|---|
| D0 | /HSYNC | 0 for H 41–46 (48 dots) | same |
| D1 | /VSYNC | 0 for V 490–491 | same |
| D2 | BLANK_n | 1 for H 0–39 and V 0–479 | same |
| D3 | /BUFEN | 0 from (V 481, H 10) to (V 523, H 40): the VRAM data-buffer window | always 0 |
| D4 | /HEND | 0 at H = 49 (and H ≥ 50) | same |
| D5 | /VEND | 0 at V = 524 and H = 49 (and V ≥ 525) | same |
| D6 | VMUX | 1 for V 481–523 | always 1 |
| D7 | VWR | 1 for V 482–522 | always 1 |

- **Horizontal:** 40 visible + 1 front porch + 6 sync + 3 back porch = 50 characters = **400 dots** = 320 + 8 + 48 + 24.
- **Vertical:** 480 + 10 + 2 + 33 = **525 lines**.
- Both syncs are negative.
- Porches and windows change with a reflash only.

**T1 register** (74HC377, CP = DCLK, /E = /LD) registers /HSYNC, /VSYNC, BLANK_n, /BUFEN, VMUX and VWR at the boundary. Its other 2 bits are spare.

### 7.4 Character pipeline
H = n during slot n.

| When | Action |
|---|---|
| Slot n, from about 40 ns after the boundary | The VRAM address is {V8..V4, H5..H0 = n}, through the 157s with VMUX = 0. The character code is ready after about 40 + 20 + 55 ≈ 115 ns. |
| Slot n | The **font ROM** sees A0–A2 = V3..V1 (font row; each row is shown on 2 lines), A3–A10 = VRAM D0–7 (the character), A11–A16 = jumpers (font banks). The glyph is ready about 185 ns (typ) / 260 ns (max) after the boundary. The timing ROM is ready about 120 ns after it. |
| Boundary E(0->1) at the end of slot n | The **74HC166** loads the glyph: SH/LD = /LD, H input = font D7 = leftmost pixel, CP = DCLK, CE = GND. **T1** loads ROM(H=n). |
| Slot n+1 | The 166 shifts 8 pixels out of QH. T1 outputs the matching sync and blank. Then H becomes n+1. |

- Pixels and sync/blank pass through exactly one boundary register each, so they stay aligned with no table offsets and no delay flip-flops (P1's idea).
- The character-to-dot-counter offset of one dot is invisible.
- Budget: data is needed 615 ns after the boundary and arrives within 260 ns.
- Hold: the counters change at least 35 ns after the sampling edge.

### 7.5 Output stage
| Output | Circuit | Level |
|---|---|---|
| RGB | 74HC08: `R/G/B = AND(QH, BLANK_n_T1)`, one gate per colour (about 9 mA each). Colour jumpers choose white, green or amber. Each gate goes through **470 Ω** into the monitor's 75 Ω. Blanking forces 0. | 5 x 75/545 ≈ 0.69 V; about 0.65 V at the loaded VOH |
| HSYNC, VSYNC | from T1, negative polarity, through 100 Ω | DE-15 pins 13 and 14 |
| RGB pins / grounds | | DE-15 pins 1/2/3; grounds 5–8 and 10 |

### 7.6 Dot-rate timing (DCLK period 79.4 ns)
| Path | typ | max | Note |
|---|---|---|---|
| 163 clk->Q -> 74HC11 -> 74 setup (LD flip-flop) | ~37 | ~85 | The only path near the limit. Max is 25 °C / 4.5 V datasheet maximum; at 5 V real parts run ~2x faster. **Scope it first.** Fallback: a 74HCT/74AC part for the dot counter, or swap the decode for the 163 TC (count 8..15 with load). |
| /LD -> 166 SH/LD and 377 /E setup | ~30 | ~65 | OK |
| 166, 74 and 163 at 12.6 MHz | | | f_max(min) of 25–30 MHz at 4.5 V. OK |
| VRAM/ROM -> 166 and T1 | ~185 | ~260 | budget 615. OK |

### 7.7 VGA chips
| Function | Parts | ICs |
|---|---|---|
| Dot clock and LD flip-flop | 74HC74 (+ 25.175 MHz can) | 1 |
| Dot counter | 74HC163 | 1 |
| H counter | 74HC163 x2 | 2 |
| V counter | 74HC163 x3 | 3 |
| Timing ROM | SST39SF010A | 1 |
| T1 register | 74HC377 | 1 |
| VRAM address mux | 74HC157 x3 | 3 |
| VRAM | AS6C62256 | 1 |
| VRAM data buffer | 74HC245 | 1 |
| Font ROM | SST39SF010A | 1 |
| Shift register | 74HC166 | 1 |
| RGB gates | 74HC08 | 1 |
| LD decode | 74HC11 | 1 |
| HEND inverter + spares | 74HC04 | 1 |
| **Total** | | **19** |

## 8. Chip count, breadboards, wiring, budget

### 8.1 By module
| Module | Parts | ICs | 830-pt boards |
|---|---|---|---|
| Datapath: PC, AR, X, SP, F, A, IR, buffers, ALU | 74HC161 x13, 74HC191 x2, 74HC377 x2, 74HC245 x11, SST39SF010A x2 | 30 | 8 (PC+AR 3, X+SP 3, ALU+A+F+IR 2) |
| Control | SST39SF010A x3, 74HC273 x3, 74HC138 x2, 74HC139, 74HC161, 74HC04, 74HC688 x2 | 13 | 4 (with 24 CW LEDs and the panel) |
| Clock / reset / stop | NE555, 74HC153, 74HC14, 74HC74 x3, 74HC175 x2, 74HC00, 74HC08, 74HC32, 74HC02, 74HC27, 74HC245 | 14 | 3 |
| CPU glue | 74HC00 x2, 74HC08, 74HC32 | 4 | (on the clock and memory boards) |
| Memory + I/O | SST39SF010A, AS6C62256, 74HC20, 74HC138, 74HC377, 74HC245 | 6 | 2 |
| PS/2 | 74HC164 x2, 74HC540, 74HC14, 74HC74, 74HC11 (+2N7000) | 6 | 1 |
| VGA | 74HC74, 74HC163 x6, SST39SF010A x2, 74HC377, 74HC157 x3, AS6C62256, 74HC245, 74HC166, 74HC08, 74HC11, 74HC04 | 19 | 5 |
| Power / bus LEDs | – | – | 1 |
| **Total** | | **92 ICs** + 2 oscillator cans | **24** (buy 28) |

**Gate allocation for glue**

| Chip | Gates |
|---|---|
| 74HC00 x3 | Johnson x4; SP high /CE; RAM /CE; NAND(MEMW_L, /VWR_s); /MWR; /GO; 3 spare |
| 74HC02 | WSTB; BRK D; 2 spare |
| 74HC08 x2 (CPU) | /RD; /WR; /ACCESS; STEPMODE term; STOP & /GO; BUSACK D x2; 1 spare |
| 74HC32 x2 | C_new; /LED_E; VRAM /WE; STOP ORs x4; 1 spare |
| 74HC27 | WAIT; 2 spare |
| 74HC04 (control) | FL, PCLD, NEXT, SPCNT, MEMW; 1 spare |

**Compared with the inputs**
- P3 had 115 ICs. This design saves 23 by dropping or replacing:
  - the probe latches (3);
  - the manual-word buffers (3);
  - the switch buffer (1);
  - the X readback (2);
  - the 7-segment latches (2);
  - the oversampled PS/2 receiver (9 -> 6 chips);
  - the VGA pipeline registers (22 -> 19);
  - and making smaller glue savings.
- P2 had 96, P1 had 54.
- The extra ~38 ICs over P1 buy:
  - a hardware stack (PUSH/POP/CALL/RET, as the brief requires);
  - the X pointer register;
  - a single commit edge with no gated clocks;
  - a resumable BUSREQ;
  - synchronous VGA counters.

### 8.2 By part number
| Part | Qty | Part | Qty |
|---|---|---|---|
| 74HC161 | 14 | 74HC74 | 5 |
| 74HC245 | 14 | 74HC00 | 3 |
| SST39SF010A | 8 | 74HC08 | 3 |
| 74HC163 | 6 | 74HC688 | 2 |
| 74HC377 | 4 | 74HC191 | 2 |
| 74HC138 | 3 | 74HC164 | 2 |
| 74HC157 | 3 | 74HC175 | 2 |
| 74HC273 | 3 | 74HC04 | 2 |
| AS6C62256-55 | 2 | 74HC11 | 2 |
| 74HC14 | 2 | 74HC32 | 2 |
| 74HC139, 74HC166, 74HC540, 74HC153, 74HC20, 74HC27, 74HC02, NE555 | 1 each | | |

**Sum: 92.** Other parts:
- Oscillator cans: 25.175 MHz and 4.000 MHz, plus an optional 6 or 8 MHz.
- 2N7000 and 3x 1N4148.

**Non-IC parts**
- About 170 LEDs with 3.3k resistors.
- 4x 8-way DIP switches for the panel (24 control + 8 data), 2 for the breakpoint, and 1 for KSTAT/user. That is 7 in total.
- Resistor networks: 10k SIPs for the bus pulls, 47k/4.7k for the panel.
- About 110x 100 nF, plus 25 electrolytics.
- About 6 buttons and toggles, a Mini-DIN-6 and a DE-15.
- A 5 V 3 A supply. Expected draw is 0.7–0.9 A: 8 flashes at ~15 mA, LEDs at ~170 mA, the keyboard at ~100 mA.

**HCT note (P1's datasheet finding).** The SST39SF010A and AS6C62256 guarantee only VOH = 2.4 V, below the 74HC VIH (3.15 V at 4.5 V).
- Plan: use HC parts, and on day 1 measure VOH at the flash and SRAM outputs under real load. CMOS outputs at a 1–3 HC load normally sit above 4.5 V.
- Keep an HCT fallback list for every flash- or SRAM-fed input: 273, 377, 161, 166 and 245.

### 8.3 Wiring and effort
- About **1,400 signal + 200 power + 250 LED jumpers ≈ 1,850 wires**.
- That is roughly 75 person-hours at about 2.5 minutes per wire, or about 2.5 weeks of evenings per person, spread over the 16-week build.
- The 16-bit AB, and the DB fan-out to about 12 chips, are the largest share.
- Wire colours: one per bus; yellow is reserved for clocks.

### 8.4 Budget (TRY, from the shop notes of 27 Oct 2026)
| Item | Approx. TL |
|---|---|
| Logic ICs + about 20 % spares: n11 lots of 25x 161 (463) and 25x 163 (562); local 245/138/273/164/74/glue; DigiKey for 377/166/175/688 | 2,900 |
| 10x SST39SF010A (DigiKey/AliExpress ~99 each) + 3x AS6C62256 | 1,400 |
| Oscillators: 25.175 MHz (DigiKey 202); 4 MHz (n11 lot 555); optional 8 MHz | 900 |
| XGecu T48 programmer | 4,360 |
| Arduino Mega 2560 clone | 834 |
| PS/2 keyboard + Mini-DIN + DE-15 | 720 |
| 28 breadboards (~110 each) | 3,100 |
| Wire, LEDs, resistors, DIP switches, capacitors, 5 V 3 A supply | 2,500 |
| One consolidated import (courier, customs broker, KDV): 4,000–6,000 per parcel according to the notes | 5,000 |
| **Total** | **≈ 21,700 TL** |

That leaves about 8,300 TL (28 %) in reserve against the 30,000 TL budget.

- **Rule: exactly one import parcel.** Each extra parcel costs about 5k TL in fixed fees.
- Everything that is in stock locally (direnc, robotistan, motorobit, Ozdisan, n11 lots) is bought locally.

## 9. C mapping

### 9.1 Supported C subset (Python compiler v1)
**Types**
- `char` is unsigned 8-bit by default. `signed char` is supported through `SEX`.
- `int` is 16-bit signed; `unsigned` is 16-bit.
- Pointers to char and int.
- Global 1-D and 2-D arrays, string literals, `const` tables in ROM, and `volatile` for I/O.

**Statements**
- if/else, while, do/while, for, break, continue, return, and expression statements.
- `switch` compiles to a compare chain, or to a `JMPI` table when the cases are dense.

**Operators**
- All arithmetic, bitwise, logical and relational operators, signed and unsigned, chosen from the operand types.
- `&&` and `||` short-circuit. `?:`, compound assignment, `++`/`--`, unary `*` and `&`, casts and `sizeof`.
- `* / %` and variable shifts call runtime routines:
  - `__mul16`: about 250–400 cycles;
  - `__divmod16`: about 600–900 cycles;
  - `__shl16` / `__shr16`: loops.
- Constant shifts and multiplies by powers of 2 are compiled inline.

**Functions**
- Any number of char, int or pointer parameters. Return types are char, int, pointer or void.
- **No recursion:** the compiler builds the call graph and reports a cycle as an error.
- No function pointers in v1. `JMPI` makes them a v2 item.
- No struct, long or float in v1.
- `asm("...")` is available.

**`hw.h`**

| Name | Definition |
|---|---|
| `KBD` | `(*(volatile unsigned char*)0xF800)` |
| `KSTAT` | `0xF801` |
| `LEDS` | `0xF800` |
| `VRAM` | `((unsigned char*)0xF000)`, row stride 64 |
| `kbd_ready()` | `BIT KSTAT` / `BMI` |
| `vram_window()` | `BIT KSTAT` / `BVS` |
| `halt()` | `HALT` |

### 9.2 Calling convention: static frames (a "compiled stack")
**Rules**
- **Frames:** each function `f` owns a fixed RAM frame holding its parameters `f_p0, f_p1…`, its locals and its temporaries. The linker overlays the frames of functions that can never be active at the same time, using the call graph.
- **Arguments:** the caller evaluates each argument and stores it straight into the callee's parameter slot. Arguments that themselves contain calls are evaluated into caller temporaries first, so `f(g(1), 2)` stays correct.
- **The call:** `CALL f`. The hardware stack holds only the 2-byte return address. PHA/PLA are used only by runtime routines.
- **Return values:** char in **A**; int or pointer in the pseudo-register **`__rv`** (2 bytes at a fixed address).
- **Registers:** A, X and the flags are all caller-saved. X is never live across a statement or a call.
- **Memory layout:**
  - 8000–80FF: runtime pseudo-registers (`__rv`, `__t0..__t7`);
  - from 8100: globals, .data, .bss and the overlaid frames, including the 1,920-byte Snake board;
  - EF00–EFFF: stack.
- **crt0:** SP is already FF after reset. It clears VRAM, copies .data, clears .bss, then `CALL main` and `HALT`.

**Why static (decision)**
- **No SP-relative or indexed address mode.** One would need a 16-bit address adder (4x 74HC283 plus muxes, about 6 ICs, plus a new timing path).
- **Cost per access:** a static access is `LDA/STA abs`, 4 cycles and 3 bytes. A stack-frame access would have to build SP+offset in A, then do TAXL/TAXH and the access: about 15 cycles.
- **Readable traces:** every variable sits at a fixed, symbol-mapped address, so the Arduino trace viewer can print `snake_len = 5` straight from the bus log.
- **Nothing is lost for Snake:** it needs no recursion and there are no interrupts. A 256-byte stack holding only return addresses allows 128 nested calls.

### 9.3 Required code sequences (cycles = µs at 1 MHz)
**`int a = b + c;`** (16-bit globals): 18 bytes, **24 cycles**.
```
LDA b      ; 4
ADD c      ; 4
STA a      ; 4
LDA b+1    ; 4   C survives: loads and stores never touch flags
ADC c+1    ; 4
STA a+1    ; 4
```

**`*p = x;`** (`char *p`, `char x`, both static): 7 bytes, **11 cycles**.
```
LDX p      ; 5
LDA x      ; 4
STA (X)    ; 2
```
- `*p++ = x` adds `INCW p` (7), for 18 cycles.
- For `int *p`: `LDX p; LDA x; STA (X+); LDA x+1; STA (X)`, 17 cycles.

**`if (x < y)`** (signed int): 15 bytes, **19–20 cycles**.
```
LDA x      ; 4
CMP y      ; 4
LDA x+1    ; 4
CPC y+1    ; 4   now N, V, C and the chained Z describe x−y as a 16-bit value
BGE else   ; 4 taken / 3 not taken
```
The same chain serves every relation:
- unsigned `<`: `BHS else`;
- `x > y`: `BLE else`;
- `x <= y`: `BGT else`;
- `==`: `BNE else`.

These are all exact, thanks to the chained Z. No operand swapping is needed (unlike P3).

**`r = add(a, b);`** with `int add(int u, int v) { return u + v; }`: **82 cycles** in total, caller 53 + callee 29.
```
; caller
LDA a / STA add_u / LDA a+1 / STA add_u+1     ; 16
LDA b / STA add_v / LDA b+1 / STA add_v+1     ; 16
CALL add                                      ; 5
LDA __rv / STA r / LDA __rv+1 / STA r+1       ; 16
; callee
add: LDA add_u / ADD add_v / STA __rv
     LDA add_u+1 / ADC add_v+1 / STA __rv+1   ; 24
     RET                                      ; 5
```

**String to VRAM:** `void puts_at(unsigned char *v, const char *s) { while (*s) *v++ = *s++; }`

Straight compiler output reloads X for each access, because X is the only pointer register: **37 cycles per character**.
```
loop: LDX  ps_s     ; 5
      LDA  (X)      ; 2
      TST           ; 2   loads do not set Z
      BEQ  done     ; 3 not taken
      LDX  ps_v     ; 5
      STA  (X)      ; 2   (stalls until the VRAM window if necessary)
      INCW ps_v     ; 7
      INCW ps_s     ; 7
      JMP  loop     ; 4
done:
```
- A 40-character line takes 1,480 cycles (1.5 ms). That is slightly more than one 1.30 ms window; the hardware stall splits it over two frames automatically and correctly.
- **Screen clear** (runtime routine): per row, `LDX #row_addr` followed by 40 unrolled `STA (X+)`, about 90 cycles. The whole screen takes about 2,700 cycles, i.e. about 3 frames.

### 9.4 Snake at 1 MHz
**Data layout**
- `unsigned char board[30*64]`: a RAM shadow of the play field with the same stride as VRAM. VRAM is write-only, and collision checks need to read.
- `int body[256]`: a ring buffer of cell offsets.
- `int head, tail, dir, food`.
- A position is `pos = row*64 + col`, so a move is `pos += dir` with dir ∈ {+1, −1, +64, −64}. The board address is `board + pos`, and the VRAM address is `0xF000 + pos`. Each takes about 18 cycles: an ADD/ADC pair, then TAXL/TAXH.

| Work per tick | Cycles |
|---|---|
| Keyboard: `BIT KSTAT; BPL`; `LDA KBD`; set-2 state machine (W/A/S/D and arrows; skip F0/E0) | ~40–60 |
| `nh = body[head] + dir` (index ×2, form address, load, 16-bit add) | ~60 |
| Collision: `X = board + nh`; `LDA (X)`; 2x CMP/BEQ | ~35 |
| Food compare (16-bit CMP/CPC/BNE) | ~20 |
| Ring update, store nh, mark board | ~70 |
| Draw head, erase tail (2–3 VRAM writes + board writes) | ~100 |
| Function-call overhead (3–4 calls) | ~150 |
| **Total** | **≈ 500–700 cycles ≈ 0.6 ms** |

- **Load:** at 8 moves/s there are 125,000 cycles per move, so the CPU is more than 99 % idle.
- **VRAM:** every VRAM write of a tick fits in one window.
- **Pacing:** the game counts VWR edges (60 per second) and makes one move every 6–8 frames.
- **Food:** placement uses a 16-bit LFSR (`SHR/ROR/XOR`, about 40 cycles per try).
- **Score:** kept as 4 decimal digit characters with carry, so no division is needed.

## 10. Risks, deliberate omissions, early prototypes

### 10.1 Risks
| # | Risk | Mitigation | Fallback |
|---|---|---|---|
| 1 | **Build volume:** 92 ICs, ~1,850 wires, 24 boards for 2 people in 16 weeks | Module-by-module bring-up with the manual panel. Split the work: person A builds clock, VGA and PS/2; person B builds control, datapath and memory. Fixed descope list. | Descope in this order: LED port -> breakpoint -> optional 2 MHz -> colour |
| 2 | Dot-rate LD path (85 ns max vs a 79.4 ns period) | Registered LD; scope it first | 74HCT/AC for the dot counter, or the 163-TC decode |
| 3 | Flash and SRAM VOH are only guaranteed to 2.4 V | Measure on day 1 | HCT for every flash/SRAM-fed input |
| 4 | WAIT path is about 223 ns worst case against 250 ns at 1 MHz | Single-gate 74HC27; scope it | 3.6 MHz MCLK (0.9 MHz CPU) |
| 5 | Hold margin of the A -> ALU -> F self-loop at the commit edge | A and F share one clock-buffer branch | 100 Ω series on the ALU-H flag outputs (adds ~5 ns of hold) |
| 6 | PS/2 receiver: rising-edge sampling, inhibit right after the 11th clock, RC timeout | Prototype with the real keyboard in the simulation phase | Shift on the falling edge and drop the RC timeout; resync then relies on inhibit plus software (P1 behaviour) |
| 7 | Errors in the ROM ALU, microcode or timing tables | Everything is generated from isa.yaml. The ALU tables are checked exhaustively against the emulator (2x 2^17 entries). Generator rules 1–9. Trace diff. | Bank jumpers keep a known-good image |
| 8 | Clock ringing or double clocking | One clock buffer, 47 Ω series resistors, star wiring with a ground return, Schmitt on the 555. Count 10^6 cycles on a counter test. | Run at 500 kHz |
| 9 | Supply drop across 24 boards | Feed both ends of every rail; check ≥ 4.75 V at the farthest chip | Second supply feed |
| 10 | Old-stock or fake ICs (n11 lots) | Test each one in the T48 logic tester before use | Buy from DigiKey in the single parcel |
| 11 | Import delays or customs | **One** DigiKey parcel, ordered by mid-November 2026 | Local substitutes: 377 -> 2x 161 as a register; 166 -> 165 + sync-load trick (to be verified) |
| 12 | Software workload: compiler, emulators, generators, Digital model | Start in simulation week 1; isa.yaml is the single source; the ISA needs no register allocator | Hand-written assembly for Snake as a last resort |
| 13 | Monitor rejects or mis-samples the signal | Test the VGA board on the actual demo monitor first | Adjust the porches in the timing ROM |
| 14 | "PS/2" keyboard that is really USB-only | Buy a native PS/2 keyboard now | – |

### 10.2 Deliberately left out of v1
**CPU**
- Interrupts.
- SP-relative or indexed addressing, and the 16-bit address adder it needs.
- X readback: DSRC 5/6 are reserved, so it costs +2x 245 later.
- A second pointer register.
- Relative branches.
- Hardware multiply/divide.

**Display, keyboard and sound**
- VRAM read-back, dual-port VRAM and cycle stealing.
- Colour attributes.
- Sound.
- PS/2 parity/stop checking and host-to-keyboard commands.

**C language:** struct, long, float, recursion and function pointers.

**Debug extras:** probe latches (optional add-on: 3x 74HC273 at the commit edge) and the 7-segment display.

**Tools:** in-circuit flash programming.

### 10.3 Prototype early
**During the simulation phase (Nov 2026 – Jan 2027)**
1. **Software:**
   - generators that turn isa.yaml into microcode, ALU, timing and font images plus customasm rules;
   - the instruction-level and microstep emulators;
   - the full Digital model (74xx DIL library) running the same images, with trace diffs;
   - the C compiler running Snake in the emulator.
2. **Bench prototypes** from locally bought parts:
   - a. the 4-phase clock, one 161 and one 245, with STOP/GO;
   - b. the flash workflow, plus one ALU ROM on DIP switches (measure VOH);
   - c. DCLK -> LD -> 166 on the real monitor;
   - d. the PS/2 receiver with LEDs and the real keyboard;
   - e. an SRAM write with the phase-A strobe.

**Build order (16 weeks)**

| Weeks | Work |
|---|---|
| 1–2 | Power, clock/stop. In parallel: VGA timing until the monitor locks. |
| 2–4 | Control latch + manual panel. In parallel: VGA data path with a test font. |
| 4–6 | ALU + A + F + IR (using DB switches). PS/2 alone. |
| 6–8 | PC, AR, X, SP. |
| 8–9 | Memory and I/O, Arduino adapter. |
| 9–11 | Microcode in; trace diff against the emulator. |
| 11–12 | Join VGA and PS/2 to the CPU. |
| 12–16 | C programs, Snake, demo without the Arduino. |

---

# STEP 3: Open issues and assumptions for the verification pass

## Timing
1. **WAIT path (5.4, path 3).** The estimate is about 223 ns worst case against a 250 ns phase.
   - Re-add the delays using the actual datasheet parts: 74HC27 (DigiKey CD74HC27E?), 74HC20, 139 and 245 enable.
   - Confirm the 74HC27 is purchasable. If it is not: rewrite WAIT with available gates without adding a level.
2. **Dot-rate LD flip-flop path (7.6).** 163 clk->Q + 74HC11 + 74 setup, against 79.4 ns. Check against the actual vendor (TI CD74HC vs Nexperia) maximum values at 5 V.
3. **uROM lookup in phase C** (152 ns max) at 1.5 and 2 MHz.
   - Confirm the 74HC161 clk->Q and 273 setup numbers.
   - Confirm the SST39SF010A tACC is 70 ns for the -70 part. If the -90 old stock is used: 172 ns, which breaks 1.5 MHz.
4. **Same-edge hold paths at commit:**
   - A -> ALU-L/H -> F (flash tOH(min) = 0);
   - AR/X/PC -> AB -> memory -> DB -> IR/AR loads;
   - the 161 /PE and P hold times.
   
   Also confirm that A and F on one 245 branch keeps skew below the A clk->Q minimum.
5. **Bus turnaround at C->D.** When the source changes (e.g. MEM -> A), the memory tDF (flash /OE->high-Z up to 25 ns) overlaps the 245 tPZH (~18 ns).
   - Estimate the contention current. Is a non-overlap phase needed?
   - Same question for VRAM /OE versus the /BUFEN window (designed apart by 6 µs; verify the ROM table).
6. **74HC191 rules (Nexperia).** CE and U/D change only while CP is high; MAX/MIN cascade into the upper /CE. Verify this in Digital with push/pop across the 0x?0/0x?F and FF/00 boundaries.
7. **Path 1 at 2 MHz** is about 403 ns max against 375 ns. Is 2 MHz a "typical-only" claim, or does it need the 6-phase counter?

## PS/2 synchronization and framing
8. **Rising-edge sampling.** Verify that the keyboard holds DATA ≥ 5 µs after the rising KCLK edge (IBM timing). Scope the real keyboard.
9. **Inhibit right after the 11th rising edge.** Does the keyboard treat it as a completed frame, or as an abort followed by a retransmit?
   - A retransmit would make every byte arrive twice.
   - P1's falling-edge marker has the same exposure.
   - If needed, delay the inhibit by about 50 µs (an RC on the 2N7000 gate).
10. **Inhibit release.** Releasing the inhibit produces a KCLK rising edge that shifts one 0 into the just-cleared register.
    - Confirm the ordering: /CLR164 is released at commit + ~20 ns, and KCLK rises µs later.
    - Confirm that a released keyboard waits ≥ 50 µs before its start bit.
11. **RC timeout.** 22k/10 nF gives about 190 µs, against the 74HC14 V_T+ spread (2.0–3.5 V across vendors). The longest in-frame clock-high time is about 50 µs, and the minimum inter-frame idle time must also be checked. Does a bad frame resync within one byte time?
12. **KRDY sampling.** Unsynchronized single-bit sampling of KRDY through KSTAT. Check the flash ALU path: KRDY -> DB -> ALU-H -> F (BIT). Is the metastability window acceptable at 1 MHz?
13. **Software.** The boot dummy read of the BAT byte (AA), and F0/E0 handling.

## VRAM gating
14. **Window and synchronizer worst case.** VWR is synchronized on MCLK (2 FFs), with one line of guard to VMUX and about 25 µs to /BUFEN.
    - Simulate in Digital with a random MCLK/DCLK phase, with a write granted on the last possible cycle and on the first possible cycle.
15. **SLOW mode.** The timing-ROM A16 bank switch is tied to the MCLK source switch.
    - Is the rule "switch only while stopped" enforced or documented?
    - What happens to a write that is in progress when SLOW changes?
    - Is there an Arduino path for VRAM writes during BUSACK?
16. **NO-VGA jumper.** It forces VWR_s = 1. Confirm that it also keeps VRAM /WE harmless (the VGA board is absent).

## Compiler mapping
17. **Flags after loads.** Loads never set flags, so the compiler must emit TST or BIT before byte tests (`while(*s)`).
18. **Chained Z.** It applies to ADC, SBC, CPC, ADCB0 and SBCB0. The compiler must never test Z after a lone ADC/SBC without first establishing Z = 1 (e.g. a preceding ADD/SUB or CMP).
19. **Instructions that clobber flags or A.**
    - CLC/SEC clobber Z, N and V.
    - INCW, DECW and JMPI clobber A.
    - Check the register-liveness rules in the code generator.
20. **Cycle counts.** Recount every sequence in 9.3 and 9.4 against the microstep tables in the emulator: 24 / 11 / 19–20 / 82 / 37 per character.
21. **Static frames.** Overlay correctness with nested argument calls, `__rv` copies, and `char` defaulting to unsigned. Do Snake's sources compile within the subset?
22. **Opcode map consistency.** Check the opcode map against `isa.yaml`: 88 opcodes, illegal `44`/`6C`/`FF`, BIT = 6D–6F.

## Chip count and budget fit
23. **Recount 92 ICs** against sections 3–7. Recheck the glue-gate allocation in 8.1 after the final schematic (KiCad).
24. **Availability.**
    - Local stock: 74HC245 (17 incl. spares), 273, 138, 164, 191, 540, 157.
    - n11 lots still listed: 25x 161 and 25x 163.
    - DigiKey items for the single parcel: 377 x5, 166 x2, 175 x3, 688 x3, 27, 11 x2, 20, 153.
    - 25.175 MHz can.
    - SST39SF010A-70 (10 pcs).
    - AS6C62256 (3 pcs).
25. **Budget.**
    - Is the ≈ 21.7k TL total right? It includes about 5k for one import parcel, the 4.36k T48 and 28 breadboards.
    - Do the team already own a programmer? If so, about 4.4k is freed.
    - Confirm the reserve of at least 15 %.
26. **Power.** 0.7–0.9 A estimated. Check the supply and the breadboard rail current (≤ 1 A per rail pair).
27. **Board count.** 24 boards; check the layout, especially 3 DIP-32 flashes plus 24 LEDs plus the panel on 4 control boards.
