"""Mikrokod imajı üretici ve kural denetimi (SISTEM-PLANI 4.5).

uROM adresi: A0–3 = STEP, A4–11 = IR, A12 = Z, A13 = C, A14 = N, A15 = V, A16 = BANK.
Üç imaj üretilir: uROM0 (bit 0–7), uROM1 (bit 8–15), uROM2 (bit 16–23).
"""

from . import isa

ROM_SIZE = 0x20000
MAX_STEPS = 16


class MicrocodeError(Exception):
    pass


def check_step(st, where):
    """Tek adım kuralları. Hata varsa MicrocodeError."""
    bits = st.bits

    def fail(msg):
        raise MicrocodeError(f'{where}: {st.text!r}: {msg}')

    if bits & isa.MEMW and st.dsrc not in ('A', 'PCL', 'PCH'):
        fail('MEMW varken veri kaynağı A, PCL ya da PCH olmalı (kural 1)')
    if bits & isa.PCLD and bits & isa.PCINC:
        fail('PCLD ve PCINC aynı adımda olamaz (kural 3)')
    if bits & isa.PCLD and st.ddst in ('ARL', 'ARH'):
        fail('PCLD, AR yüklemesiyle aynı adımda olamaz (kural 3)')
    if st.ddst == 'A' and st.aluop is None:
        fail('A yükleniyorsa ALU işlemi açıkça yazılmalı (kural 4)')
    if bits & isa.FL and st.aluop is None:
        fail('FL varsa ALU işlemi yazılmalı')
    if st.ddst in ('ARL', 'ARH') and bits & isa.ARINC:
        fail('AR yüklenirken ARINC olamaz (kural 5)')
    if st.ddst in ('XL', 'XH') and bits & isa.XINC:
        fail('X yüklenirken XINC olamaz (kural 5)')
    if bits & isa.SPDN and not (bits & isa.SPCNT and bits & isa.MEMW):
        fail('SPDN yalnızca push adımında (SPCNT + MEMW) kullanılır (kural 6)')
    if st.dsrc == 'MEM' and st.ddst == '-' and st.aluop is None:
        fail('Bellek okunuyor ama sonuç hiçbir yere gitmiyor')


def check_sequence(seq, where):
    """Bir komutun adım dizisi kuralları (kural 8)."""
    if not seq:
        raise MicrocodeError(f'{where}: boş adım dizisi')
    if len(seq) > MAX_STEPS - 1:
        raise MicrocodeError(f'{where}: {len(seq)} adım; FETCH ile birlikte en fazla {MAX_STEPS}')
    for i, st in enumerate(seq):
        check_step(st, f'{where} adım {i + 1}')
        last = i == len(seq) - 1
        if bool(st.bits & isa.NEXT) != last:
            raise MicrocodeError(f'{where} adım {i + 1}: NEXT yalnızca son adımda olmalı')


def check_all():
    """Tüm komut tanımlarını denetler."""
    check_step(isa.step(isa.FETCH), 'FETCH')
    for code, ins in sorted(isa.INSTRUCTIONS.items()):
        where = f'{code:02X} {ins.mnemonic} {ins.mode}'
        if ins.cond is None:
            check_sequence(ins.steps, where)
        else:
            check_sequence(ins.taken, where + ' (alınır)')
            check_sequence(ins.not_taken, where + ' (alınmaz)')


def build(banks=(0, 1)):
    """Üç adet 128 KB uROM imajı döndürür. Bank 1 şimdilik bank 0'ın kopyası."""
    check_all()
    roms = [bytearray(ROM_SIZE) for _ in range(3)]
    fetch = isa.step(isa.FETCH).word()
    unused = isa.step(isa.UNUSED).word()
    for ir in range(256):
        ins = isa.INSTRUCTIONS.get(ir)
        for flags in range(16):
            z, c, n, v = flags & 1, (flags >> 1) & 1, (flags >> 2) & 1, flags >> 3
            if ins is None:
                words = [unused]
            else:
                words = [st.word() for st in ins.steps_for(z, c, n, v)]
            for s in range(MAX_STEPS):
                if s == 0:
                    w = fetch
                elif s <= len(words):
                    w = words[s - 1]
                else:
                    w = unused
                for bank in banks:
                    addr = s | ir << 4 | flags << 12 | bank << 16
                    roms[0][addr] = w & 0xFF
                    roms[1][addr] = (w >> 8) & 0xFF
                    roms[2][addr] = w >> 16
    return roms


def word_at(roms, step, ir, z, c, n, v, bank=0):
    """İmajlardan kontrol kelimesini okur (donanımın yaptığı arama)."""
    addr = step | ir << 4 | (z | c << 1 | n << 2 | v << 3) << 12 | bank << 16
    return roms[0][addr] | roms[1][addr] << 8 | roms[2][addr] << 16


def describe(word):
    """Kontrol kelimesini okunur yazıya çevirir (iz ve hata ayıklama için)."""
    asrc = {v: k for k, v in isa.ASRC.items()}[word & 3]
    dsrc = {v: k for k, v in isa.DSRC.items()}.get((word >> 2) & 7, f'?{(word >> 2) & 7}')
    ddst = {v: k for k, v in isa.DDST.items()}.get((word >> 5) & 7, f'?{(word >> 5) & 7}')
    op = (word >> 8) & 31
    opname = isa.ALUOPS[op] if op < len(isa.ALUOPS) else 'POISON'
    bits = [name for name, b in isa.BITS.items() if word & b]
    return f'{asrc}/{dsrc}/{ddst}/{opname} ' + ' '.join(bits)
