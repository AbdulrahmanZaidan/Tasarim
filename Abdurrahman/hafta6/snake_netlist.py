"""Snake bütün sistemde: CPU + M6 (VGA) + M7 (PS/2), çip seviyesinde netlist (~5 dk).

Çalıştırma (depo kökünden):  py -3 Abdurrahman/hafta6/snake_netlist.py
- snake.c HIZ_BAS=2 ile derlenir (2 turda bir hamle), ana döngü 34 tur koşturulur.
- 22. turda aşağı, 28. turda sol ok tuşu sanal PS/2 klavyeden (KCLK/KDATA) gönderilir.
- Emülatörle iz karşılaştırması (KRDY ve VWR_s devreden oynatılır), her karenin VIDEO
  çıkışı o kareden önceki pencerenin sonundaki VRAM'le nokta nokta karşılaştırılır,
  ihlaller sınıflandırılır; bazı kareler images/ altına PNG olarak yazılır.
"""
import sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'sim'))
from pathlib import Path
from collections import Counter
from ta8 import vga
from ta8.bus import FRAME_CYCLES
from ta8.hw import harness, screen
from tacc import build
SP = HERE / 'images'
SN = HERE.parents[1] / 'sim' / 'examples' / 'snake.c'
res = build(SN.read_text(encoding='utf-8'), str(SN), defines={'HIZ_BAS': 2})
img, sym = res.program.image, res.program.symbols
AS = (0xE0, 0x72, 0xE0, 0xF0, 0x72)     # asagi bas/birak
SOL = (0xE0, 0x6B, 0xE0, 0xF0, 0x6B)
t0 = time.perf_counter()
hw = harness.HwCpu(img, vga='netlist', kbd='netlist')
cap = screen.Capture(hw.sim)
snaps = []                                   # VMUX düşünce (pencere bitti) VRAM'in kopyası
vram_chip = hw.board.memories['VRAM']
def on_vmux(t, v):
    if v == 0:
        snaps.append((len(cap.frames), bytes(vram_chip.data[:0x800])))
hw.sim.watch('VMUX', on_vmux)
sent = []
u = lambda n: (lambda a: hw.ram()[a - 0x8000] | hw.ram()[a - 0x7FFF] << 8)(sym['_' + n])
FR = 34
for f in range(1, FR + 1):
    if f == 22: hw.ps2.press(*AS); sent += AS
    if f == 28: hw.ps2.press(*SOL); sent += SOL
    hw.run(f * FRAME_CYCLES, idle_limit=40000)
    print(f'frame {f}: cycles {hw.n} t={hw.sim.now/1e6:.1f} ms  hamle {u("hamle_sayisi")}  wall {time.perf_counter()-t0:.0f} s', flush=True)
hw.keys = tuple(sent)
emu = harness.emu_like(hw, img, hw.n, tuple(sent))
d = harness.compare(hw, emu)
print('compare:', d or 'SIFIR FARK', ' emu hamle', emu.bus.mem[sym['_hamle_sayisi']])
print('vram == emu', hw.vram() == bytes(emu.bus.vram))
want = screen.render(hw.vram(), vga.default_font())
print('frames captured', len(cap.frames), 'last frame pixel diff', len(screen.diff(cap.frames[-1], want)))
# her kare, kendisinden önceki pencerenin sonundaki VRAM ile çizilmeli
font = vga.default_font()
bad = []
for nframes, snap in snaps:
    if nframes < len(cap.frames):            # bu anlık görüntüden sonra çizilen kare
        fr = cap.frames[nframes]
        dd = screen.diff(fr, screen.render(snap + bytes(32768 - 0x800), font))
        if dd: bad.append((nframes, len(dd)))
print('frames checked vs VRAM-at-window-end:', sum(1 for n, _ in snaps if n < len(cap.frames)), 'mismatching:', bad[:10])
cl = harness.classify_violations(hw)
print('classified:', {k: len(v) for k, v in cl.items()})
other = cl.get('diger', [])
FRAME_NS = 525 * 32000
print('diger by ref:', Counter(v.ref for v in other).most_common(5))
print('diger U7 outside blanking:', [v for v in other if v.ref.startswith('U7') and v.time > 2000 and (v.time % FRAME_NS) / 32000 < 480][:3])
print('diger non-U7:', [v for v in other if not v.ref.startswith('U7')][:6])
for k in (-1, -13):
    screen.write_png(cap.frames[k], str(SP / f'snake_kare{len(cap.frames)+k}.png'))
print(Counter((v.kind, v.ref[:2]) for v in hw.sim.violations).most_common(8))
print('total wall', round(time.perf_counter() - t0), 's')
