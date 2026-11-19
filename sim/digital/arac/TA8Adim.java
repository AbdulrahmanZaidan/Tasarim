import de.neemann.digital.cli.CircuitLoader;
import de.neemann.digital.core.Model;
import de.neemann.digital.core.ModelEventType;
import de.neemann.digital.core.ObservableValue;
import de.neemann.digital.core.Signal;

import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import de.neemann.digital.core.Node;
import de.neemann.digital.core.memory.RAMInterface;

/**
 * TA-8: bir Digital devresini (.dig) başsız kurar, saati adım adım çalıştırır ve
 * seçilen sinyalleri CSV olarak döker. Python'dan ta8.hw.digital.run_stepper çağırır.
 *
 * Kullanım:
 *   java -cp Digital.jar;DERLEME_KLASÖRÜ TA8Adim DEVRE.dig [seçenekler]
 *     -n N              N saat periyodu çalıştır (varsayılan 10)
 *     -c SAAT           sürülecek saat: Clock ya da In etiketi (varsayılan: ilk Clock)
 *     -s AD=DEĞER[@K]   girişi ayarla (DEĞER: ondalık, 0x.., Z); @K: K. periyottan önce
 *                       (varsayılan 0 = başta). Aynı giriş birden çok kez verilebilir.
 *     -w AD,AD,...      kaydedilecek sinyaller (Out/In/Clock etiketleri; varsayılan: bütün Out'lar)
 *     -t AD[:rise|fall] tetik: periyot sonları yerine AD'nin (varsayılan yükselen) kenarından
 *                       hemen ÖNCEKİ kararlı değerleri kaydet (yarım periyot çözünürlüğü)
 *     -o DOSYA          CSV'yi dosyaya yaz (varsayılan: standart çıkış)
 *     -e 1              en sona, son periyottan sonraki kararlı durumu CYC = -1 satırı olarak ekle
 *     -m ETİKET=DOSYA[@K]  etiketi ETİKET olan RAM'in içeriğini DOSYA'ya ham bayt olarak yaz
 *                       (kelime başına 1 bayt): @K verilirse K. periyodun başında (o periyodun
 *                       -s girişleri uygulanmadan önce), verilmezse koşu bitince. Alt devredeki
 *                       "*" etiketi örneğin etiketiyle değiştirilir (ör. U602). Tekrarlanabilir.
 *
 * Bir periyot: girişler ayarlanır, kararlı hale gelinir, (tetik yoksa) satır yazılır,
 * saat 1 yapılır, kararlı hale gelinir, saat 0 yapılır, kararlı hale gelinir.
 * Yani tetiksiz modda CYC = k satırı, k. yükselen kenardan hemen önceki değerlerdir
 * (Testcase'teki "C" satırının sonucu bir sonraki satırda görünür).
 *
 * Çıktı: ilk satır "CYC,ad,ad,..."; değerler 1 bit için 0/1, çok bit için 0x.. (onaltılı),
 * yüksek empedans Z, kısmen yüksek empedans X.
 * Standart hataya bir özet satırı yazılır: "TA8Adim: N periyot, R satır, T s, P periyot/sn".
 * Çıkış kodu: 0 tamam, 2 model hatası (kısa devre, besleme ...), 100 kullanım hatası.
 */
public class TA8Adim {
    static String err;

    static long parse(String s) {
        s = s.trim();
        if (s.startsWith("0x") || s.startsWith("0X")) return Long.parseLong(s.substring(2), 16);
        return Long.parseLong(s);
    }

    static String fmt(ObservableValue v) {
        int bits = v.getBits();
        long hz = v.getHighZ();
        if (hz != 0) {
            long all = bits >= 64 ? -1L : (1L << bits) - 1;
            return (hz & all) == all ? "Z" : "X";
        }
        if (bits == 1) return v.getValue() != 0 ? "1" : "0";
        String h = Long.toHexString(v.getValue()).toUpperCase();
        int digits = (bits + 3) / 4;
        StringBuilder b = new StringBuilder("0x");
        for (int i = h.length(); i < digits; i++) b.append('0');
        return b.append(h).toString();
    }

    static void usage(String msg) {
        System.err.println("TA8Adim: " + msg);
        System.exit(100);
    }

    static void check(Model m) {
        if (err != null || !m.isRunning()) {
            System.err.println("TA8Adim: MODEL HATASI: " + (err != null ? err : "model durdu"));
            System.exit(2);
        }
    }

    static void dump(Model m, String label, String file) throws java.io.IOException {
        RAMInterface found = null;
        List<String> labels = new ArrayList<>();
        for (Node node : m.getNodes()) {
            if (node instanceof RAMInterface) {
                String lab = ((RAMInterface) node).getLabel();
                labels.add(lab);
                if (label.equals(lab)) {
                    if (found != null) usage("aynı etiketli iki RAM: " + label);
                    found = (RAMInterface) node;
                }
            }
        }
        if (found == null) usage("RAM bulunamadı: " + label + " (bilinenler: " + labels + ")");
        int size = found.getSize();
        byte[] b = new byte[size];
        for (int i = 0; i < size; i++) b[i] = (byte) found.getMemory().getDataWord(i);
        try (FileOutputStream f = new FileOutputStream(file)) {
            f.write(b);
        }
    }

    static String[] sample(List<ObservableValue> rec) {
        String[] cur = new String[rec.size()];
        for (int i = 0; i < cur.length; i++) cur[i] = fmt(rec.get(i));
        return cur;
    }

    static void row(PrintWriter pw, int cyc, String[] vals) {
        StringBuilder r = new StringBuilder(Integer.toString(cyc));
        for (String c : vals) r.append(',').append(c);
        pw.println(r);
    }

    public static void main(String[] a) throws Exception {
        if (a.length < 1) usage("devre dosyası verilmedi");
        String circ = a[0], clockName = null, trig = null, out = null;
        int n = 10;
        boolean trigRise = true;
        List<String> want = null;
        List<String[]> sets = new ArrayList<>();
        List<String[]> dumps = new ArrayList<>();
        boolean endRow = false;
        for (int i = 1; i < a.length; i++) {
            String o = a[i];
            if (i + 1 >= a.length) usage("eksik değer: " + o);
            String v = a[++i];
            switch (o) {
                case "-n": n = Integer.parseInt(v); break;
                case "-c": clockName = v; break;
                case "-o": out = v; break;
                case "-e": endRow = !v.equals("0"); break;
                case "-m": {
                    int eq = v.indexOf('=');
                    if (eq < 0) usage("-m ETİKET=DOSYA bekleniyor: " + v);
                    String file = v.substring(eq + 1), when = "-1";
                    int at = file.lastIndexOf('@');
                    if (at > 0) {
                        when = file.substring(at + 1);
                        file = file.substring(0, at);
                    }
                    Integer.parseInt(when);
                    dumps.add(new String[]{v.substring(0, eq), file, when});
                    break;
                }
                case "-w": want = new ArrayList<>(List.of(v.split(","))); break;
                case "-t": {
                    String[] tp = v.split(":");
                    trig = tp[0];
                    if (tp.length > 1) {
                        if (tp[1].equals("fall")) trigRise = false;
                        else if (!tp[1].equals("rise")) usage("tetik kenarı rise ya da fall olmalı: " + v);
                    }
                    break;
                }
                case "-s": {
                    int eq = v.indexOf('=');
                    if (eq < 0) usage("-s AD=DEĞER bekleniyor: " + v);
                    String name = v.substring(0, eq), val = v.substring(eq + 1), at = "0";
                    int k = val.indexOf('@');
                    if (k >= 0) {
                        at = val.substring(k + 1);
                        val = val.substring(0, k);
                    }
                    sets.add(new String[]{name, val, at});
                    break;
                }
                default: usage("bilinmeyen seçenek: " + o);
            }
        }

        Model m = new CircuitLoader(circ).createModel();
        m.addObserver(ev -> {
            if (ev.getType() == ModelEventType.ERROR_OCCURRED && ev.getCause() != null)
                err = ev.getCause().getMessage();
        }, ModelEventType.ERROR_OCCURRED);

        Map<String, ObservableValue> sig = new LinkedHashMap<>();
        for (Signal s : m.getInputs()) sig.put(s.getName(), s.getValue());
        for (Signal s : m.getOutputs()) sig.put(s.getName(), s.getValue());
        for (Signal s : m.getSignals()) sig.putIfAbsent(s.getName(), s.getValue());

        ObservableValue clk;
        if (clockName == null) {
            if (m.getClocks().isEmpty()) usage("devrede Clock yok; -c ile bir giriş verin");
            clk = m.getClocks().get(0).getClockOutput();
        } else {
            clk = sig.get(clockName);
            if (clk == null) usage("saat bulunamadı: " + clockName);
        }
        if (want == null) {
            want = new ArrayList<>();
            for (Signal s : m.getOutputs()) want.add(s.getName());
        }
        List<ObservableValue> rec = new ArrayList<>();
        for (String w : want) {
            ObservableValue v = sig.get(w);
            if (v == null) usage("sinyal bulunamadı: " + w + " (bilinenler: " + sig.keySet() + ")");
            rec.add(v);
        }
        ObservableValue trv = null;
        if (trig != null) {
            trv = sig.get(trig);
            if (trv == null) usage("tetik sinyali bulunamadı: " + trig);
        }
        for (String[] s : sets) {
            if (sig.get(s[0]) == null) usage("giriş bulunamadı: " + s[0]);
            Integer.parseInt(s[2]);
            if (!s[1].equalsIgnoreCase("Z")) parse(s[1]);
        }

        PrintWriter pw = out == null
                ? new PrintWriter(new OutputStreamWriter(System.out, StandardCharsets.UTF_8))
                : new PrintWriter(new OutputStreamWriter(new FileOutputStream(out), StandardCharsets.UTF_8));
        StringBuilder h = new StringBuilder("CYC");
        for (String w : want) h.append(',').append(w);
        pw.println(h);

        long t0 = System.nanoTime();
        m.init();
        check(m);
        clk.setValue(0);
        String[] prev = null;
        long prevTrig = 0;
        int rows = 0;
        for (int cyc = 0; cyc <= n; cyc++) {
            for (String[] d : dumps)
                if (Integer.parseInt(d[2]) == cyc) dump(m, d[0], d[1]);
            for (String[] s : sets) {
                if (Integer.parseInt(s[2]) != cyc) continue;
                ObservableValue in = sig.get(s[0]);
                if (s[1].equalsIgnoreCase("Z")) in.setToHighZ();
                else in.setValue(parse(s[1]));
            }
            m.doStep();
            check(m);
            String[] cur = sample(rec);
            if (trv == null) {
                row(pw, cyc, cur);
                rows++;
            } else {
                long tv = trv.getValueHighZIsZero();
                if (prev != null && tv != prevTrig && (tv != 0) == trigRise) {
                    row(pw, cyc, prev);
                    rows++;
                }
                prev = cur;
                prevTrig = tv;
            }
            if (cyc == n) break;
            for (int half = 0; half < 2; half++) {
                clk.setValue(half == 0 ? 1 : 0);
                m.doStep();
                check(m);
                if (trv != null) {
                    String[] c2 = sample(rec);
                    long tv = trv.getValueHighZIsZero();
                    if (tv != prevTrig && (tv != 0) == trigRise) {
                        row(pw, cyc, prev);
                        rows++;
                    }
                    prev = c2;
                    prevTrig = tv;
                }
            }
        }
        if (endRow) row(pw, -1, sample(rec));
        pw.flush();
        if (out != null) pw.close();
        for (String[] d : dumps)
            if (Integer.parseInt(d[2]) < 0) dump(m, d[0], d[1]);
        double sec = (System.nanoTime() - t0) / 1e9;
        System.err.printf(java.util.Locale.ROOT, "TA8Adim: %d periyot, %d satır, %.3f s, %.0f periyot/sn%n",
                n, rows, sec, n / Math.max(sec, 1e-9));
        m.close();
        System.exit(0);
    }
}
