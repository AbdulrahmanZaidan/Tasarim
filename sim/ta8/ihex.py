"""Intel HEX yazıcı ve okuyucu (Proteus'un ROM bileşenleri için).

Kayıt: ':' LL AAAA TT veri... CC. CC, LL'den son veri byte'ına kadar
bütün byte'ların toplamının ikiye tümleyenidir (mod 256).
Tipler: 00 veri, 01 dosya sonu, 04 genişletilmiş doğrusal adres (üst 16 bit).
"""

LINE_BYTES = 16


def record(addr, rtype, data=b''):
    """Tek bir kaydı ':' ile başlayan metin olarak döndürür (satır sonu yok)."""
    body = bytes([len(data), (addr >> 8) & 0xFF, addr & 0xFF, rtype]) + bytes(data)
    return ':' + body.hex().upper() + f'{-sum(body) & 0xFF:02X}'


def dump(data):
    """Bütün imajı 0 adresinden başlayarak Intel HEX metnine çevirir.

    64 KB'ı aşan imajlarda her 64 KB sınırında bir tip 04 kaydı yazılır.
    """
    data = bytes(data)
    lines = []
    for i in range(0, len(data), LINE_BYTES):
        if i and i % 0x10000 == 0:
            lines.append(record(0, 4, (i >> 16).to_bytes(2, 'big')))
        lines.append(record(i & 0xFFFF, 0, data[i:i + LINE_BYTES]))
    lines.append(record(0, 1))
    return '\n'.join(lines) + '\n'


def load(text, fill=0xFF):
    """Intel HEX metnini byte'lara çevirir (0 adresinden en yüksek adrese kadar).

    Boşluklar `fill` ile doldurulur. Sağlama toplamı ya da biçim hatasında ValueError.
    """
    mem = {}
    upper = 0
    for no, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if not line.startswith(':'):
            raise ValueError(f'satır {no}: ":" ile başlamıyor')
        try:
            raw = bytes.fromhex(line[1:])
        except ValueError:
            raise ValueError(f'satır {no}: onaltılı olmayan karakter') from None
        if len(raw) < 5 or len(raw) != raw[0] + 5:
            raise ValueError(f'satır {no}: uzunluk tutmuyor')
        if sum(raw) & 0xFF:
            raise ValueError(f'satır {no}: sağlama toplamı hatalı')
        addr, rtype, payload = raw[1] << 8 | raw[2], raw[3], raw[4:-1]
        if rtype == 0:
            base = upper + addr
            for k, b in enumerate(payload):
                mem[base + k] = b
        elif rtype == 1:
            break
        elif rtype == 2:                          # genişletilmiş segment adresi
            upper = int.from_bytes(payload, 'big') << 4
        elif rtype == 4:
            upper = int.from_bytes(payload, 'big') << 16
        elif rtype not in (3, 5):                 # başlangıç adresleri: yok sayılır
            raise ValueError(f'satır {no}: bilinmeyen kayıt tipi {rtype:02X}')
    out = bytearray([fill]) * (max(mem) + 1 if mem else 0)
    for a, b in mem.items():
        out[a] = b
    return bytes(out)
