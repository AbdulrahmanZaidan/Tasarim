/*
  td8_debug.ino : TD-8 hata ayıklama kartı (Arduino Mega 2560), iz ve yükleme yazılımı.
  Sürüm 0.1, ilk sürüm (Kasım 2026).

  !!! BU SÜRÜM DONANIMDA HİÇ ÇALIŞTIRILMADI. Yalnızca arduino:avr:mega için derlendi.
  Bilgisayar tarafı (sim/td8/ardu.py) aynı protokolü konuşan sahte bir cihazla
  (yine sim/td8/ardu.py, FakeDevice) sınandı. Pin eşlemesi TASLAKTIR; kart
  kablolanınca kesinleşecek. !!!

  Görevler (SISTEM-PLANI bölüm 10; tasarim-taslaklari/ISA-v0-sentez.md 4.10 ve 6.5):

  * İz modu: MCLK'yı Arduino üretir (makinenin 74HC153 saat seçicisi I3'te, SLOW).
    Bir CPU çevrimi normalde 4 MCLK'dir; ama çevrimi MCLK saymakla değil Q1/Q2'den
    okunan fazla izleriz (WAIT D'de, STOP C'de bekletebilir). Her commit kenarından
    (CLK yükselişi = B→C) hemen önce AB, DB ve 24 bitlik kontrol kelimesi (CW)
    örneklenir ve bilgisayara 6 baytlık ikili kayıt olarak gönderilir.

  * Yükleme modu: /BUSREQ indirilir → BUSACK beklenir (zaman aşımlı) → AB ve DB
    çıkış yapılıp /ARD_WR darbesiyle RAM'e yazılır, /ARD_RD ile geri okunup
    doğrulanır → pinler yüksek empedansa alınır → /BUSREQ bırakılır.
    BUSACK = 1 görülmeden bus pinleri ASLA çıkış yapılmaz.

  Protokol ve kullanım: arduino/README.md. Bilgisayar tarafı: sim/td8/ardu.py,
  sim/ardu_cli.py. Protokol sabitleri iki tarafta aynı olmalı; sim/tests/test_ardu.py
  bu dosyadaki ">>> PROTOKOL" bloğunu ayrıştırıp Python'dakilerle karşılaştırır.
*/

#include <Arduino.h>
#include <avr/io.h>
#include <string.h>

// >>> PROTOKOL SABİTLERİ: sim/td8/ardu.py ile birebir AYNI (tests/test_ardu.py denetler)
#define PROTO_VERSION       1
#define FW_MAJOR            0
#define FW_MINOR            1
#define DEVICE_ID           "TD8-ARDU"
#define SERIAL_BAUD         1000000UL   // 16 MHz'de U2X ile tam 1 Mbaud (UBRR = 1)
#define FRAME_SYNC1         0xA5
#define FRAME_SYNC2         0x5A
#define MAX_PAYLOAD         250         // çerçeve yükü en fazla (bayt)
#define MAX_BLOCK           128         // tek READ/WRITE'ta en fazla veri baytı
#define REC_SIZE            6           // iz kaydı: AB lo, AB hi, DB, CW0, CW1, CW2
#define RECS_PER_FRAME      40          // TRACE_DATA çerçevesi başına kayıt (4 + 240 bayt yük)
#define FRAME_TIMEOUT_MS    100         // çerçeve içinde iki bayt arası en fazla
#define BUSACK_TIMEOUT_MS   500
#define RESET_HOLD_MS       50          // /RESET düşük tutma (RC kondansatörü boşalsın)
#define RESET_TIMEOUT_MS    1000        // reset bırakılınca makinenin C'den çıkması için
#define FREE_CLOCK_CHECK_MS 5           // iz modunda "başka saat var mı" denetimi
#define STALL_PULSES        1024        // bir çevrim için en fazla MCLK darbesi
#define CW_HALT_BIT         23

#define CMD_HELLO           0x01        // kimlik ve sürüm
#define CMD_STATUS          0x02        // pinler, faz, sayaçlar
#define CMD_MODE            0x03        // [mod]  MODE_FREE / MODE_TRACE
#define CMD_RESET           0x04        // makineyi resetle (moda göre)
#define CMD_TRACE           0x05        // [N u32]  N çevrimlik iz
#define CMD_STEP            0x06        // tek çevrim (tek adım)
#define CMD_CLOCK           0x07        // [n u16]  n ham MCLK darbesi (faz faz adım)
#define CMD_READ            0x08        // [adres u16][uzunluk u8]
#define CMD_WRITE           0x09        // [adres u16][bayraklar u8][veri...]
#define CMD_BUS             0x0A        // [1 = bus'ı al ve tut, 0 = bırak]
#define RSP_FLAG            0x80        // yanıt tipi = komut | RSP_FLAG
#define TRACE_DATA          0xA0        // [ilk çevrim u32][kayıtlar...]
#define RSP_ERROR           0xFF        // [komut][hata kodu][pinler][ek...]

#define MODE_FREE           0           // makine kendi saatinde; Arduino MCLK vermez
#define MODE_TRACE          1           // Arduino MCLK verir (153 → I3)
#define WRITE_VERIFY        0x01

#define ERR_CRC             1
#define ERR_UNKNOWN_CMD     2
#define ERR_BAD_LEN         3
#define ERR_BAD_ARG         4
#define ERR_MODE            5
#define ERR_BUS_HELD        6
#define ERR_BUSACK_TIMEOUT  7
#define ERR_BUSACK_LOST     8
#define ERR_VERIFY          9
#define ERR_RESET_NOT_C     10
#define ERR_RESET_TIMEOUT   11
#define ERR_FREE_CLOCK      12

#define END_OK              0           // istenen çevrim sayısı bitti
#define END_HALT            1           // HALT'lı adım commit edildi; makine C'de durdu
#define END_STALL           2           // faz STALL_PULSES darbede B'ye gelmedi
#define END_ABORT           3           // bilgisayar araya bayt gönderdi
#define END_PHASE           4           // commit darbesinden sonra faz C değil

#define PIN_Q1              0x01
#define PIN_CLK             0x02
#define PIN_STOP            0x04
#define PIN_BUSACK          0x08
#define PIN_BUSREQ_OUT      0x10        // Arduino /BUSREQ'i indiriyor
#define PIN_RESET_OUT       0x20        // Arduino /RESET'i indiriyor
#define PIN_BUS_DRIVEN      0x40        // AB ya da DB Arduino'dan sürülüyor
#define PIN_TRACE_MODE      0x80
// <<< PROTOKOL SABİTLERİ

// ============================================================================
// Pin eşlemesi: TASLAK (kart kablolanınca kesinleşecek; arduino/README.md ile aynı)
// ============================================================================
// Bus ve kontrol kelimesi bayt bayt okunsun diye her bayt tam bir porta oturur.
// Mega'da 8 biti de dışarı çıkan portlar: A, B, C, F, K, L. B'nin 7. biti (pin 13)
// kartın LED'idir ve açılışta bootloader onu sürer; o yüzden CW23 PD7'ye alındı.
//
//  Sinyal          Yön              Mega pinleri              Port
//  AB0..AB7        giriş / çıkış    22, 23, ..., 29           PORTA PA0..PA7
//  AB8..AB15       giriş / çıkış    37, 36, ..., 30           PORTC PC0..PC7
//  DB0..DB7        giriş / çıkış    49, 48, ..., 42           PORTL PL0..PL7
//  CW0..CW7        giriş            A0..A7  (54..61)          PORTF PF0..PF7  uROM0
//  CW8..CW15       giriş            A8..A15 (62..69)          PORTK PK0..PK7  uROM1
//  CW16..CW22      giriş            53, 52, 51, 50, 10, 11, 12  PORTB PB0..PB6  uROM2
//  CW23 (HALT)     giriş            38                        PORTD PD7
//  Q1              giriş            6                         PORTH PH3
//  CLK (= Q2)      giriş            7                         PORTH PH4
//  STOP            giriş            8                         PORTH PH5
//  BUSACK          giriş            9                         PORTH PH6
//  MCLK            çıkış            41                        PORTG PG0  → 74HC153 I3
//  /ARD_RD         çıkış            40                        PORTG PG1
//  /ARD_WR         çıkış            39                        PORTG PG2
//  /BUSREQ         açık-drain       4                         PORTG PG5
//  /RESET          açık-drain       2                         PORTE PE4
//  Kullanılmayan: 0 ve 1 (USB seri), 13 (LED), diğerleri boş. GND makineyle ortak.

#define AB_LO_DDR    DDRA
#define AB_LO_OUT    PORTA
#define AB_LO_IN     PINA
#define AB_HI_DDR    DDRC
#define AB_HI_OUT    PORTC
#define AB_HI_IN     PINC
#define DB_DDR       DDRL
#define DB_OUT       PORTL
#define DB_IN        PINL
#define CW0_DDR      DDRF
#define CW0_OUT      PORTF
#define CW0_IN       PINF
#define CW1_DDR      DDRK
#define CW1_OUT      PORTK
#define CW1_IN       PINK
#define CW2_LO_DDR   DDRB          // PB0..PB6 = CW16..CW22
#define CW2_LO_OUT   PORTB
#define CW2_LO_IN    PINB
#define CW2_LO_MASK  0x7F
#define CW2_HI_DDR   DDRD          // PD7 = CW23, kayıttaki CW2 baytının 7. biti
#define CW2_HI_OUT   PORTD
#define CW2_HI_IN    PIND
#define CW2_HI_MASK  0x80

#define ST_DDR       DDRH          // durum girişleri: tek okumada faz, STOP, BUSACK
#define ST_OUT       PORTH
#define ST_IN        PINH
#define ST_Q1        _BV(PH3)
#define ST_CLK       _BV(PH4)
#define ST_STOP      _BV(PH5)
#define ST_BUSACK    _BV(PH6)
#define ST_ALL       (ST_Q1 | ST_CLK | ST_STOP | ST_BUSACK)

#define CTL_DDR      DDRG          // PORTG I/O alanında: sbi/cbi ile tek komutta değişir
#define CTL_OUT      PORTG
#define CTL_MCLK     _BV(PG0)
#define CTL_RD       _BV(PG1)      // /ARD_RD (itme-çekme, boşta 1)
#define CTL_WR       _BV(PG2)      // /ARD_WR (itme-çekme, boşta 1)
#define CTL_BUSREQ   _BV(PG5)      // /BUSREQ: PORT biti hep 0; DDR=1 → 0, DDR=0 → yüksek empedans

#define RST_DDR      DDRE          // /RESET: PORT biti hep 0; DDR=1 → 0, DDR=0 → yüksek empedans
#define RST_OUT      PORTE
#define RST_BIT      _BV(PE4)

// Faz = (Q1, Q2): A = 00, B = 10, C = 11, D = 01 (SISTEM-PLANI 2 ve 3.1). CLK = Q2.
#define PHASE_MASK   (ST_Q1 | ST_CLK)
#define PHASE_A      0
#define PHASE_B      ST_Q1
#define PHASE_C      (ST_Q1 | ST_CLK)
#define PHASE_D      ST_CLK

// Zamanlama (16 MHz'de 1 çevrim = 62,5 ns). Makinenin 4 MHz'deki fazı 250 ns'dir;
// burada her faz en az ~1 µs sürer, yani her şey rahatça oturur.
#define MCLK_HIGH_CYC      8      // 0,5 µs: 74HC74 en kısa saat darbesi ~20 ns
#define MCLK_LOW_CYC       8      // 0,5 µs: kenardan sonra Q1/Q2 ve 470 Ω'luk hatlar otursun
#define SAMPLE_SETTLE_CYC  16     // 1 µs: B fazında örneklemeden önce ek bekleme
#define BUS_SETUP_CYC      8      // 0,5 µs: Arduino'nun sürdüğü adres/veri otursun
#define BUS_ACCESS_CYC     16     // 1 µs: /ARD_RD ya da /ARD_WR darbesi (RAM 70 ns, ROM 70–90 ns)

// ============================================================================
// Durum
// ============================================================================
static uint8_t  g_mode = MODE_FREE;
static bool     g_bus_hold = false;     // bilgisayar CMD_BUS 1 ile bus'ı tutuyor
static bool     g_bus_driven = false;   // AB ya da DB şu an Arduino'dan sürülüyor
static uint32_t g_cycle = 0;            // reset'ten beri commit sayısı (iz modunda)
static uint16_t g_rx_errors = 0;        // CRC/uzunluk hatalı gelen çerçeveler
static uint16_t g_rx_timeouts = 0;      // yarıda kesilen gelen çerçeveler

// Giden TRACE_DATA çerçevesi: [ilk çevrim u32][RECS_PER_FRAME × 6 bayt]
static uint8_t  g_tbuf[4 + RECS_PER_FRAME * REC_SIZE];
static uint8_t  g_tcount = 0;
static uint8_t  g_tseq = 0;             // bu kayıtlara yol açan komutun sıra numarası

// ============================================================================
// Yardımcılar: bayt dizme, CRC, çerçeve gönderme
// ============================================================================
static void put16(uint8_t *p, uint16_t v) { p[0] = v; p[1] = v >> 8; }
static void put32(uint8_t *p, uint32_t v) { p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24; }
static uint16_t get16(const uint8_t *p) { return p[0] | (uint16_t)p[1] << 8; }
static uint32_t get32(const uint8_t *p) {
  return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

// CRC-16, polinom 0x8408 (yansıtılmış CCITT), başlangıç 0xFFFF, son XOR yok
// (avr-libc _crc_ccitt_update'in C karşılığı; "123456789" → 0x6F91).
static uint16_t crc_update(uint16_t crc, uint8_t data) {
  data ^= (uint8_t)(crc & 0xFF);
  data ^= (uint8_t)(data << 4);
  return ((((uint16_t)data << 8) | (crc >> 8)) ^ (uint8_t)(data >> 4) ^ ((uint16_t)data << 3));
}

// Çerçeve: SYNC1 SYNC2 TİP SIRA UZUNLUK YÜK[UZUNLUK] CRC_lo CRC_hi
// CRC; TİP, SIRA, UZUNLUK ve YÜK üzerinden hesaplanır.
static void send_frame(uint8_t type, uint8_t seq, const uint8_t *payload, uint8_t len) {
  uint8_t head[5] = {FRAME_SYNC1, FRAME_SYNC2, type, seq, len};
  uint16_t crc = 0xFFFF;
  crc = crc_update(crc, type);
  crc = crc_update(crc, seq);
  crc = crc_update(crc, len);
  for (uint8_t i = 0; i < len; i++) crc = crc_update(crc, payload[i]);
  Serial.write(head, 5);
  if (len) Serial.write(payload, len);
  Serial.write((uint8_t)(crc & 0xFF));
  Serial.write((uint8_t)(crc >> 8));
}

static uint8_t pins_byte(void) {
  uint8_t s = ST_IN, v = 0;
  if (s & ST_Q1) v |= PIN_Q1;
  if (s & ST_CLK) v |= PIN_CLK;
  if (s & ST_STOP) v |= PIN_STOP;
  if (s & ST_BUSACK) v |= PIN_BUSACK;
  if (CTL_DDR & CTL_BUSREQ) v |= PIN_BUSREQ_OUT;
  if (RST_DDR & RST_BIT) v |= PIN_RESET_OUT;
  if (g_bus_driven) v |= PIN_BUS_DRIVEN;
  if (g_mode == MODE_TRACE) v |= PIN_TRACE_MODE;
  return v;
}

static void send_error(uint8_t cmd, uint8_t seq, uint8_t code, const uint8_t *extra, uint8_t n) {
  uint8_t p[3 + 8];
  p[0] = cmd;
  p[1] = code;
  p[2] = pins_byte();
  if (n > 8) n = 8;
  for (uint8_t i = 0; i < n; i++) p[3 + i] = extra[i];
  send_frame(RSP_ERROR, seq, p, 3 + n);
}

// Bloklayan bekleme yerine millis() ile ölçülen kısa bekleme (yalnız reset tutmada).
static void hold_ms(uint16_t ms) {
  uint32_t t0 = millis();
  while ((uint32_t)(millis() - t0) < ms) { /* RC'nin dolması/boşalması */ }
}

// ============================================================================
// Saat ve iz
// ============================================================================
static inline uint8_t phase_now(void) { return ST_IN & PHASE_MASK; }
static inline bool busack_now(void) { return (ST_IN & ST_BUSACK) != 0; }

// Bir MCLK darbesi. Makinedeki bütün flip-flop'lar (Johnson sayacı, BRQ senkronlayıcı,
// BUSACK, reset senkronlayıcı) MCLK'nın YÜKSELEN kenarında saatlenir.
static inline void mclk_pulse(void) {
  CTL_OUT |= CTL_MCLK;
  __builtin_avr_delay_cycles(MCLK_HIGH_CYC);
  CTL_OUT &= ~CTL_MCLK;
  __builtin_avr_delay_cycles(MCLK_LOW_CYC);
}

// AB, DB ve CW'yi okur. CW2'nin 0..6. bitleri PB0..PB6'dan, 7. biti (HALT) PD7'den.
static void sample(uint8_t *rec) {
  rec[0] = AB_LO_IN;
  rec[1] = AB_HI_IN;
  rec[2] = DB_IN;
  rec[3] = CW0_IN;
  rec[4] = CW1_IN;
  rec[5] = (CW2_LO_IN & CW2_LO_MASK) | (CW2_HI_IN & CW2_HI_MASK);
}

// İz modunda bütün MCLK darbeleri buradan geçer, böylece hiçbir commit kaçmaz.
// Okuma anı (SISTEM-PLANI 3.1 faz tablosu):
//   C→D (LCLK↑)  kontrol latch'i yeni kelimeyi alır
//   D            kod çözücüler, AB/DB kaynakları oturur, bellek erişimi başlar
//   A            yazma darbesi (/WE)
//   B            "her şey bir faz boyunca sabit": okuma verisi ve ALU sonucu oturmuş
//   B→C (CLK↑)   COMMIT: registerlar yüklenir, hemen ardından CW değişmeye başlar
// Yani faz B'deyken (Q1 = 1, Q2 = 0) bir sonraki yükselen kenar her koşulda commit'tir
// (Johnson: B'den sonra hep C gelir; STOP ve WAIT B→C'yi etkilemez). AB, DB ve CW'yi bu
// kenardan HEMEN ÖNCE, B fazının içinde okuruz: o anki değerler commit'in kullanacağı
// değerlerin ta kendisidir ve emülatörün izindeki (çevrim, AB, DB, CW) satırıyla aynıdır.
// Döner: true = bu darbe commit idi; kayıt rec'e, çevrim numarası *idx'e yazıldı.
static bool mclk_tick(uint8_t *rec, uint32_t *idx) {
  bool commit = (phase_now() == PHASE_B);
  if (commit) {
    __builtin_avr_delay_cycles(SAMPLE_SETTLE_CYC);
    sample(rec);
    *idx = g_cycle;
  }
  mclk_pulse();
  if (commit) g_cycle++;
  return commit;
}

// Bir CPU çevrimi: B fazına gelene kadar darbe ver, örnekle, commit darbesini ver.
// Döner: END_OK ya da END_PHASE (ikisinde de commit oldu, kayıt geçerli) / END_STALL.
static uint8_t run_cycle(uint8_t *rec, uint32_t *idx) {
  for (uint16_t n = 0; n < STALL_PULSES; n++) {
    if (mclk_tick(rec, idx)) {
      return (phase_now() == PHASE_C) ? END_OK : END_PHASE;
    }
  }
  return END_STALL;
}

static void flush_trace(void) {
  if (g_tcount == 0) return;
  send_frame(TRACE_DATA, g_tseq, g_tbuf, 4 + g_tcount * REC_SIZE);
  g_tcount = 0;
}

static void emit_record(const uint8_t *rec, uint32_t idx) {
  if (g_tcount == 0) put32(g_tbuf, idx);
  memcpy(g_tbuf + 4 + g_tcount * REC_SIZE, rec, REC_SIZE);
  if (++g_tcount == RECS_PER_FRAME) flush_trace();
}

// ============================================================================
// Bus erişimi (yükleme modu). Kural: BUSACK = 1 görülmeden AB/DB çıkış yapılmaz.
// ============================================================================
// Bütün bus pinlerini yüksek empedansa alır. Önce DDR (sürmeyi bırak), sonra PORT
// (iç pull-up'lar kapalı kalsın: AB'de makinenin 10k pull-up'ı, DB'de pull-down'ı var).
static void bus_float(void) {
  DB_DDR = 0;
  AB_LO_DDR = 0;
  AB_HI_DDR = 0;
  DB_OUT = 0;
  AB_LO_OUT = 0;
  AB_HI_OUT = 0;
  CTL_OUT |= CTL_RD | CTL_WR;
  g_bus_driven = false;
}

// AB'yi sürer. Önce PORT (değer), sonra DDR (çıkış): yanlış adres görünmez.
static bool ab_drive(uint16_t addr) {
  if (!busack_now()) {            // çakışma koruması: CPU'nun sürücüleri açık olabilir
    bus_float();
    return false;
  }
  AB_LO_OUT = addr & 0xFF;
  AB_HI_OUT = addr >> 8;
  AB_LO_DDR = 0xFF;
  AB_HI_DDR = 0xFF;
  g_bus_driven = true;
  return true;
}

static bool read_byte(uint16_t addr, uint8_t *val) {
  if (!ab_drive(addr)) return false;
  DB_DDR = 0;                     // DB giriş; bellek (ya da KSTAT/KBD) sürecek
  DB_OUT = 0;
  __builtin_avr_delay_cycles(BUS_SETUP_CYC);
  CTL_OUT &= ~CTL_RD;             // /ARD_RD = 0 → /RD = 0
  __builtin_avr_delay_cycles(BUS_ACCESS_CYC);
  *val = DB_IN;
  CTL_OUT |= CTL_RD;
  return busack_now();            // erişim sırasında BUSACK düştüyse veri geçersiz
}

static bool write_byte(uint16_t addr, uint8_t val) {
  if (!ab_drive(addr)) return false;
  DB_OUT = val;
  DB_DDR = 0xFF;                  // BUSACK ab_drive'da denetlendi
  __builtin_avr_delay_cycles(BUS_SETUP_CYC);
  CTL_OUT &= ~CTL_WR;             // /ARD_WR = 0 → /WR = 0 (RAM /WE; VRAM yalnız SLOW'da)
  __builtin_avr_delay_cycles(BUS_ACCESS_CYC);
  CTL_OUT |= CTL_WR;
  __builtin_avr_delay_cycles(BUS_SETUP_CYC);   // veri tutma
  DB_DDR = 0;
  DB_OUT = 0;
  return busack_now();
}

// /BUSREQ'i indirir, BUSACK'ı bekler. İz modunda makinenin saatini biz verdiğimiz için
// beklerken MCLK darbesi veririz; bu sırada olan commit'ler (en çok 1) iz kaydı olarak
// gönderilir, iz kopmaz. Serbest modda makine kendi saatiyle ilerler.
static uint8_t bus_acquire(void) {
  CTL_DDR |= CTL_BUSREQ;          // PORT biti 0: hat düşük
  uint32_t t0 = millis();
  uint8_t rec[REC_SIZE];
  uint32_t idx;
  while (!busack_now()) {
    if (g_mode == MODE_TRACE && mclk_tick(rec, &idx)) emit_record(rec, idx);
    if ((uint32_t)(millis() - t0) > BUSACK_TIMEOUT_MS) {
      CTL_DDR &= ~CTL_BUSREQ;
      return ERR_BUSACK_TIMEOUT;
    }
  }
  return 0;
}

// Pinleri yüzdürür ve /BUSREQ'i bırakır. Serbest modda BUSACK'ın düşmesini bekler
// (yoksa sonraki istekte bayat BUSACK = 1 görülebilirdi). İz modunda saat bizde:
// darbe vermeyiz; makine bir sonraki izde C'den kendiliğinden çıkar.
static void bus_release(void) {
  bus_float();
  CTL_DDR &= ~CTL_BUSREQ;
  if (g_mode == MODE_FREE) {
    uint32_t t0 = millis();
    while (busack_now() && (uint32_t)(millis() - t0) <= BUSACK_TIMEOUT_MS) { }
  }
}

static void bus_release_all(void) {
  bus_release();
  g_bus_hold = false;
}

// ============================================================================
// Komutlar
// ============================================================================
static void cmd_hello(uint8_t seq) {
  uint8_t p[7 + sizeof(DEVICE_ID) - 1];
  p[0] = PROTO_VERSION;
  p[1] = FW_MAJOR;
  p[2] = FW_MINOR;
  p[3] = MAX_PAYLOAD;
  p[4] = MAX_BLOCK;
  p[5] = RECS_PER_FRAME;
  p[6] = g_mode;
  memcpy(p + 7, DEVICE_ID, sizeof(DEVICE_ID) - 1);
  send_frame(CMD_HELLO | RSP_FLAG, seq, p, sizeof(p));
}

static void cmd_status(uint8_t seq) {
  uint8_t p[17];
  p[0] = g_mode;
  p[1] = pins_byte();
  put32(p + 2, g_cycle);
  sample(p + 6);                  // AB, DB, CW: makine dururken anlamlı
  put16(p + 12, g_rx_errors);
  put16(p + 14, g_rx_timeouts);
  p[16] = g_bus_hold;
  send_frame(CMD_STATUS | RSP_FLAG, seq, p, sizeof(p));
}

static void cmd_mode(uint8_t seq, const uint8_t *p, uint8_t len) {
  if (len != 1) { send_error(CMD_MODE, seq, ERR_BAD_LEN, 0, 0); return; }
  if (p[0] > MODE_TRACE) { send_error(CMD_MODE, seq, ERR_BAD_ARG, p, 1); return; }
  bus_release_all();
  g_mode = p[0];
  uint8_t r[1] = {g_mode};
  send_frame(CMD_MODE | RSP_FLAG, seq, r, 1);
}

// Reset (SISTEM-PLANI 3.4): kaynaklar 74HC14'ten geçip 74HC74'te senkronlanır.
// Reset hemen etki eder (Johnson C'ye, latch NOP'a), bırakılması MCLK'ya senkrondur.
// İz modunda bırakmayı yürütecek MCLK'yı biz veririz ve makine C'den çıkana (C→D,
// FETCH latch'lendi) kadar darbe veririz: makine 0. çevrimin D fazında kalır.
static void cmd_reset(uint8_t seq) {
  bus_release_all();
  RST_OUT &= ~RST_BIT;
  RST_DDR |= RST_BIT;             // /RESET = 0
  hold_ms(RESET_HOLD_MS);
  if (g_mode == MODE_TRACE && phase_now() != PHASE_C) {
    RST_DDR &= ~RST_BIT;
    send_error(CMD_RESET, seq, ERR_RESET_NOT_C, 0, 0);   // reset etki etmiyor: kablo?
    return;
  }
  RST_DDR &= ~RST_BIT;            // bırak: hat pull-up/RC ile yükselir
  uint32_t pulses = 0;
  if (g_mode == MODE_TRACE) {
    uint32_t t0 = millis();
    while (phase_now() == PHASE_C) {   // C'de commit olmaz; düz darbe yeterli
      mclk_pulse();
      pulses++;
      if ((uint32_t)(millis() - t0) > RESET_TIMEOUT_MS) {
        send_error(CMD_RESET, seq, ERR_RESET_TIMEOUT, 0, 0);  // STOP = 1 (STEP?) ya da reset takılı
        return;
      }
    }
    // Saat gerçekten bizde mi? Darbe vermeden faz değişiyorsa makine başka saatle koşuyor.
    uint8_t ph = phase_now();
    uint32_t t1 = millis();
    while ((uint32_t)(millis() - t1) < FREE_CLOCK_CHECK_MS) {
      if (phase_now() != ph) {
        send_error(CMD_RESET, seq, ERR_FREE_CLOCK, 0, 0);
        return;
      }
    }
  }
  g_cycle = 0;
  uint8_t r[5];
  r[0] = pins_byte();
  put32(r + 1, pulses);
  send_frame(CMD_RESET | RSP_FLAG, seq, r, sizeof(r));
}

static void cmd_trace(uint8_t seq, const uint8_t *p, uint8_t len) {
  if (len != 4) { send_error(CMD_TRACE, seq, ERR_BAD_LEN, 0, 0); return; }
  if (g_mode != MODE_TRACE) { send_error(CMD_TRACE, seq, ERR_MODE, 0, 0); return; }
  if (g_bus_hold) { send_error(CMD_TRACE, seq, ERR_BUS_HELD, 0, 0); return; }
  uint32_t count = get32(p), done = 0;
  uint8_t reason = END_OK, rec[REC_SIZE];
  uint32_t idx;
  g_tseq = seq;
  while (done < count) {
    reason = run_cycle(rec, &idx);
    if (reason == END_STALL) break;
    emit_record(rec, idx);
    done++;
    if (reason != END_OK) break;                                    // END_PHASE
    if (rec[5] & (1 << (CW_HALT_BIT - 16))) { reason = END_HALT; break; }
    if (Serial.available()) { reason = END_ABORT; break; }          // bilgisayar durdurdu
  }
  flush_trace();
  uint8_t r[10];
  r[0] = reason;
  put32(r + 1, done);
  put32(r + 5, g_cycle);
  r[9] = pins_byte();
  send_frame(CMD_TRACE | RSP_FLAG, seq, r, sizeof(r));
}

static void cmd_step(uint8_t seq, uint8_t len) {
  if (len != 0) { send_error(CMD_STEP, seq, ERR_BAD_LEN, 0, 0); return; }
  if (g_mode != MODE_TRACE) { send_error(CMD_STEP, seq, ERR_MODE, 0, 0); return; }
  if (g_bus_hold) { send_error(CMD_STEP, seq, ERR_BUS_HELD, 0, 0); return; }
  uint8_t r[12];
  uint32_t idx = g_cycle;
  memset(r, 0, sizeof(r));
  r[0] = run_cycle(r + 6, &idx);
  r[1] = pins_byte();
  put32(r + 2, idx);
  send_frame(CMD_STEP | RSP_FLAG, seq, r, sizeof(r));
}

static void cmd_clock(uint8_t seq, const uint8_t *p, uint8_t len) {
  if (len != 2) { send_error(CMD_CLOCK, seq, ERR_BAD_LEN, 0, 0); return; }
  if (g_mode != MODE_TRACE) { send_error(CMD_CLOCK, seq, ERR_MODE, 0, 0); return; }
  if (g_bus_hold) { send_error(CMD_CLOCK, seq, ERR_BUS_HELD, 0, 0); return; }
  uint16_t n = get16(p);
  uint8_t rec[REC_SIZE];
  uint32_t idx;
  g_tseq = seq;
  for (uint16_t i = 0; i < n; i++) {
    if (mclk_tick(rec, &idx)) emit_record(rec, idx);
  }
  flush_trace();
  uint8_t r[5];
  r[0] = pins_byte();
  put32(r + 1, g_cycle);
  send_frame(CMD_CLOCK | RSP_FLAG, seq, r, sizeof(r));
}

// Bellek işleminin başı/sonu: bus tutulmuyorsa bu işlem için alınır ve bırakılır.
static uint8_t mem_begin(uint8_t seq) {
  g_tseq = seq;
  if (g_bus_hold) return busack_now() ? 0 : ERR_BUSACK_LOST;
  return bus_acquire();
}

static void mem_fail(uint8_t cmd, uint8_t seq, uint8_t code, const uint8_t *extra, uint8_t n) {
  bus_release_all();
  flush_trace();
  send_error(cmd, seq, code, extra, n);
}

static void cmd_read(uint8_t seq, const uint8_t *p, uint8_t len) {
  if (len != 3) { send_error(CMD_READ, seq, ERR_BAD_LEN, 0, 0); return; }
  uint16_t addr = get16(p);
  uint8_t n = p[2];
  if (n == 0 || n > MAX_BLOCK) { send_error(CMD_READ, seq, ERR_BAD_ARG, p + 2, 1); return; }
  uint8_t err = mem_begin(seq);
  if (err) { mem_fail(CMD_READ, seq, err, 0, 0); return; }
  uint8_t r[2 + MAX_BLOCK];
  put16(r, addr);
  for (uint8_t i = 0; i < n; i++) {
    if (!read_byte(addr + i, r + 2 + i)) { mem_fail(CMD_READ, seq, ERR_BUSACK_LOST, 0, 0); return; }
  }
  bus_float();
  if (!g_bus_hold) bus_release();
  flush_trace();
  send_frame(CMD_READ | RSP_FLAG, seq, r, 2 + n);
}

static void cmd_write(uint8_t seq, const uint8_t *p, uint8_t len) {
  if (len < 4 || len > 3 + MAX_BLOCK) { send_error(CMD_WRITE, seq, ERR_BAD_LEN, 0, 0); return; }
  uint16_t addr = get16(p);
  uint8_t flags = p[2], n = len - 3;
  const uint8_t *data = p + 3;
  uint8_t err = mem_begin(seq);
  if (err) { mem_fail(CMD_WRITE, seq, err, 0, 0); return; }
  for (uint8_t i = 0; i < n; i++) {
    uint16_t a = addr + i;
    if (!write_byte(a, data[i])) { mem_fail(CMD_WRITE, seq, ERR_BUSACK_LOST, 0, 0); return; }
    if (flags & WRITE_VERIFY) {
      uint8_t got;
      if (!read_byte(a, &got)) { mem_fail(CMD_WRITE, seq, ERR_BUSACK_LOST, 0, 0); return; }
      if (got != data[i]) {
        uint8_t x[4];
        put16(x, a);
        x[2] = data[i];
        x[3] = got;
        mem_fail(CMD_WRITE, seq, ERR_VERIFY, x, 4);
        return;
      }
    }
  }
  bus_float();
  if (!g_bus_hold) bus_release();
  flush_trace();
  uint8_t r[3];
  put16(r, addr);
  r[2] = n;
  send_frame(CMD_WRITE | RSP_FLAG, seq, r, 3);
}

static void cmd_bus(uint8_t seq, const uint8_t *p, uint8_t len) {
  if (len != 1) { send_error(CMD_BUS, seq, ERR_BAD_LEN, 0, 0); return; }
  g_tseq = seq;
  if (p[0]) {
    if (!g_bus_hold) {
      uint8_t err = bus_acquire();
      if (err) { mem_fail(CMD_BUS, seq, err, 0, 0); return; }
      g_bus_hold = true;
    }
  } else {
    bus_release_all();
  }
  flush_trace();
  uint8_t r[2] = {(uint8_t)g_bus_hold, pins_byte()};
  send_frame(CMD_BUS | RSP_FLAG, seq, r, 2);
}

static void handle_command(uint8_t type, uint8_t seq, const uint8_t *p, uint8_t len) {
  switch (type) {
    case CMD_HELLO:  cmd_hello(seq); break;
    case CMD_STATUS: cmd_status(seq); break;
    case CMD_MODE:   cmd_mode(seq, p, len); break;
    case CMD_RESET:  cmd_reset(seq); break;
    case CMD_TRACE:  cmd_trace(seq, p, len); break;
    case CMD_STEP:   cmd_step(seq, len); break;
    case CMD_CLOCK:  cmd_clock(seq, p, len); break;
    case CMD_READ:   cmd_read(seq, p, len); break;
    case CMD_WRITE:  cmd_write(seq, p, len); break;
    case CMD_BUS:    cmd_bus(seq, p, len); break;
    default:         send_error(type, seq, ERR_UNKNOWN_CMD, 0, 0); break;
  }
}

// ============================================================================
// Gelen çerçeve çözücü (durum makinesi). Bozuk çerçevede SYNC aramaya döner.
// sim/td8/ardu.py içindeki DeviceParser bunun Python ikizidir.
// ============================================================================
enum { RX_SYNC1, RX_SYNC2, RX_TYPE, RX_SEQ, RX_LEN, RX_DATA, RX_CRC_L, RX_CRC_H };
static uint8_t  rx_state = RX_SYNC1;
static uint8_t  rx_type, rx_seq, rx_len, rx_pos, rx_crc_l;
static uint8_t  rx_buf[MAX_PAYLOAD];
static uint32_t rx_last_ms = 0;

static void rx_byte(uint8_t b) {
  switch (rx_state) {
    case RX_SYNC1:
      if (b == FRAME_SYNC1) rx_state = RX_SYNC2;
      break;
    case RX_SYNC2:
      if (b == FRAME_SYNC2) rx_state = RX_TYPE;
      else if (b != FRAME_SYNC1) rx_state = RX_SYNC1;
      break;
    case RX_TYPE:
      rx_type = b;
      rx_state = RX_SEQ;
      break;
    case RX_SEQ:
      rx_seq = b;
      rx_state = RX_LEN;
      break;
    case RX_LEN:
      if (b > MAX_PAYLOAD) { g_rx_errors++; rx_state = RX_SYNC1; break; }
      rx_len = b;
      rx_pos = 0;
      rx_state = b ? RX_DATA : RX_CRC_L;
      break;
    case RX_DATA:
      rx_buf[rx_pos++] = b;
      if (rx_pos == rx_len) rx_state = RX_CRC_L;
      break;
    case RX_CRC_L:
      rx_crc_l = b;
      rx_state = RX_CRC_H;
      break;
    case RX_CRC_H: {
      rx_state = RX_SYNC1;
      uint16_t crc = 0xFFFF;
      crc = crc_update(crc, rx_type);
      crc = crc_update(crc, rx_seq);
      crc = crc_update(crc, rx_len);
      for (uint8_t i = 0; i < rx_len; i++) crc = crc_update(crc, rx_buf[i]);
      if (crc != (uint16_t)(rx_crc_l | (uint16_t)b << 8)) {
        g_rx_errors++;
        send_error(rx_type, rx_seq, ERR_CRC, 0, 0);   // bilgisayar yeniden gönderir
      } else {
        handle_command(rx_type, rx_seq, rx_buf, rx_len);
      }
      break;
    }
  }
}

// ============================================================================
void setup() {
  // JTAG'i kapat: PF4..PF7 (CW4..CW7) sıradan giriş olsun. JTD 4 çevrim içinde iki kez yazılır.
  uint8_t m = MCUCR | _BV(JTD);
  MCUCR = m;
  MCUCR = m;

  // Girişler: pull-up yok (makinenin kendi pull-up/pull-down'ları ve HC çıkışları sürer).
  bus_float();
  CW0_DDR = 0;  CW0_OUT = 0;
  CW1_DDR = 0;  CW1_OUT = 0;
  CW2_LO_DDR &= ~CW2_LO_MASK;  CW2_LO_OUT &= ~CW2_LO_MASK;
  CW2_HI_DDR &= ~CW2_HI_MASK;  CW2_HI_OUT &= ~CW2_HI_MASK;
  ST_DDR &= ~ST_ALL;           ST_OUT &= ~ST_ALL;

  // Kontrol çıkışları: önce seviye (PORT), sonra yön (DDR); arada yanlış seviye görünmez.
  CTL_OUT = (CTL_OUT & ~(CTL_MCLK | CTL_BUSREQ)) | CTL_RD | CTL_WR;
  CTL_DDR = (CTL_DDR | CTL_MCLK | CTL_RD | CTL_WR) & ~CTL_BUSREQ;   // /BUSREQ bırakılmış
  RST_OUT &= ~RST_BIT;
  RST_DDR &= ~RST_BIT;                                               // /RESET bırakılmış

  Serial.begin(SERIAL_BAUD);
  cmd_hello(0);                   // açılış duyurusu (sıra 0): bilgisayar hazır olduğumuzu görür
}

void loop() {
  // Yarıda kalmış gelen çerçeveyi zaman aşımıyla at (kesik çerçeve sonrakini yutmasın).
  if (rx_state != RX_SYNC1 && (uint32_t)(millis() - rx_last_ms) > FRAME_TIMEOUT_MS) {
    rx_state = RX_SYNC1;
    g_rx_timeouts++;
  }
  while (Serial.available() > 0) {
    rx_last_ms = millis();
    rx_byte((uint8_t)Serial.read());
  }
}
