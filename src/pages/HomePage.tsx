import { Link } from 'react-router-dom';
import { ArrowRight, BarChart3, Target, ClipboardList, BookOpen, MousePointerClick, BadgeCheck, CalendarCheck } from 'lucide-react';
import { useCore, useTimeline } from '../data/public';
import { seedSettings } from '../data/fallback';
import { fmtDate } from '../lib/format';
import BreadboardArt from '../components/BreadboardArt';
import { Figure, Section, StatusBadge } from '../components/ui';
import { iconFor } from '../components/Timeline';

import logo from '../assets/sdu-logo.png';

const legend = [
  { icon: Target, title: 'Proje hedefleri', text: 'Bitirme projesi kapsamında ulaşılması amaçlanan sonuçlar.' },
  { icon: ClipboardList, title: 'Planlanan çalışmalar', text: 'Henüz başlamamış veya sürmekte olan iş paketleri.' },
  { icon: BookOpen, title: 'Referans bilgiler', text: 'Ben Eater’ın eğitsel tasarımından alınan teknik bilgiler.' },
  { icon: MousePointerClick, title: 'Eğitsel simülasyonlar', text: 'Tarayıcıda çalışan, kavramı açıklayan etkileşimli örnekler.' },
  { icon: BadgeCheck, title: 'Gerçekleşen çalışmalar', text: 'Yalnızca kanıtı (dosya, bağlantı) eklendiğinde işaretlenir.' },
];

export default function HomePage() {
  const { data } = useCore();
  const st = data.settings;
  const timeline = useTimeline();
  const recent = timeline.data.updates.slice(0, 3);
  const customDescription = st.description && st.description !== seedSettings.project_description ? st.description : null;
  return (
    <>
      <section className="pt-10 sm:pt-14">
        <div className="container-x">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
            <img src={logo} alt="Süleyman Demirel Üniversitesi logosu" className="h-[88px] w-[88px] sm:h-[104px] sm:w-[104px]" />
            <div className="animate-rise">
              <div className="text-[13px] font-semibold tracking-[0.16em] text-brand">SÜLEYMAN DEMİREL ÜNİVERSİTESİ</div>
              <div className="mt-1 text-[13px] font-semibold tracking-[0.12em] text-ink-3">TASARIM I · BİTİRME PROJESİ</div>
              <h1 className="mt-2 text-[34px] font-bold leading-[1.1] sm:text-[48px]">{st.title}</h1>
              <p className="mt-2 text-[17px] text-ink-3 sm:text-[19px]">{st.subtitle}</p>
            </div>
          </div>
          <div className="rule mt-7" />

          <div className="mt-8 grid gap-8 lg:grid-cols-[1.05fr_1fr] lg:items-start">
            <div>
              {customDescription ? <p className="lead whitespace-pre-line">{customDescription}</p> : <p className="lead">
                Bu bitirme projesinin amacı, yalnızca temel dijital mantık entegre devreleri kullanılarak programlanabilir bir
                8-bit bilgisayarın tasarlanması ve ikinci dönemde breadboard’lar üzerinde fiziksel olarak gerçekleştirilmesidir.
                Bilgisayar; saat devresi, yazmaçlar, aritmetik mantık birimi, RAM, program sayacı, EEPROM tabanlı kontrol birimi
                ve 7 segment çıkış göstergesinden oluşacak, tüm modüller 8-bit ortak veri yolu üzerinden haberleşecektir.
              </p>}
              <p className="prose-body mt-4">
                Mimari, Ben Eater’ın eğitsel “8-bit breadboard computer” tasarımını referans alır. <b>Tasarım I</b> dönemi
                mimari tasarım, simülasyon, dokümantasyon ve malzeme hazırlığını; <b>Tasarım II</b> dönemi ise donanımın kurulması
                ve bütünleştirilmesini kapsar.{st.projectStatus && <> Proje durumu: <b>{st.projectStatus}</b>.</>}
              </p>

              <div className="card-soft mt-6 grid gap-5 p-5 sm:grid-cols-[auto_1fr]">
                <div>
                  <div className="text-[12px] font-semibold tracking-[0.12em] text-brand">PROJE DANIŞMANI</div>
                  <div className="mt-1.5 text-[17px] font-semibold">{st.supervisor}</div>
                </div>
                <div className="sm:border-l sm:border-brand-line sm:pl-5">
                  <div className="text-[12px] font-semibold tracking-[0.12em] text-brand">PROJE EKİBİ</div>
                  <ul className="mt-1.5 space-y-1 text-[15px]">
                    {st.team.map((s) => <li key={s.studentId || s.name}><b>{s.name}</b>{s.studentId && <> · <span className="mono text-ink-3">{s.studentId}</span></>}</li>)}
                  </ul>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <Link to="/proje" className="btn-primary px-5 py-3 text-[16px]">Projeyi İncele <ArrowRight size={18} aria-hidden /></Link>
                <Link to="/proje/ilerleme" className="btn-outline px-5 py-3 text-[16px]"><BarChart3 size={18} aria-hidden /> Proje İlerleme Durumu</Link>
              </div>
            </div>

            <Figure n="1" kind="kavramsal" caption="8-bit breadboard bilgisayarın modül yerleşimi: sol sütunda saat, program sayacı, bellek, komut yazmacı ve kontrol birimi; sağ sütunda A/B yazmaçları, ALU ve çıkış; ortada 8-bit veri yolu.">
              <BreadboardArt />
            </Figure>
          </div>
        </div>
      </section>

      <Section eyebrow="Dönem yapısı" title="İki dönemlik proje planı">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-[10px] bg-brand p-5 text-white">
            <div className="text-[12px] font-semibold tracking-[0.12em] text-white/80">1. DÖNEM · BU DÖNEM</div>
            <div className="mt-1 text-[20px] font-bold">Tasarım I — Hazırlık</div>
            <p className="mt-2 text-[14px] leading-6 text-white/90">Mimari ve şema, simülasyon, GitHub deposu ile malzeme ve maliyet analizi.</p>
          </div>
          <div className="rounded-[10px] border border-dashed border-brand-line bg-white p-5">
            <div className="text-[12px] font-semibold tracking-[0.12em] text-ink-3">2. DÖNEM · PLANLANAN</div>
            <div className="mt-1 text-[20px] font-bold">Tasarım II — Uygulama</div>
            <p className="mt-2 text-[14px] leading-6 text-ink-2">Modüllerin breadboard üzerinde kurulması, test edilmesi ve tek bir sistemde birleştirilmesi.</p>
          </div>
        </div>
        <div className={`mt-6 grid gap-3 sm:grid-cols-2 ${data.phases.length === 5 ? 'lg:grid-cols-5' : 'lg:grid-cols-4'}`}>
          {data.phases.map((s) => {
            const Icon = iconFor(s.slug);
            return (
              <Link key={s.id} to={s.path} className="card group flex flex-col gap-2 p-4 text-ink transition-all hover:-translate-y-0.5 hover:border-brand hover:text-ink">
                <div className="flex items-center justify-between"><span className="mono text-[13px] font-semibold text-brand">{s.number}</span><Icon size={18} className="text-brand" aria-hidden /></div>
                <div className="font-semibold leading-5">{s.title}</div>
                <div className="mt-auto pt-1"><StatusBadge status={s.status} /></div>
              </Link>
            );
          })}
        </div>
      </Section>

      {recent.length > 0 && (
        <Section eyebrow="Son gelişmeler" title="Proje günlüğünden">
          <div className="grid gap-3 md:grid-cols-3">
            {recent.map((u) => (
              <Link key={u.id} to="/proje/ilerleme#zaman-cizelgesi" className="card group flex flex-col gap-1.5 p-4 text-ink hover:border-brand hover:text-ink">
                <span className="flex items-center gap-1.5 text-[12px] text-ink-3"><CalendarCheck size={14} className="text-brand" aria-hidden />{fmtDate(u.update_date)}</span>
                <b className="leading-5">{u.title}</b>
                {u.description && <p className="line-clamp-3 text-[13px] leading-5 text-ink-3">{u.description}</p>}
              </Link>
            ))}
          </div>
        </Section>
      )}

      <Section eyebrow="Okuma rehberi" title="Bu sitedeki bilgilerin türleri" intro="Projenin henüz hazırlık aşamasında olması nedeniyle sitedeki her içerik türü açıkça ayrıştırılmıştır.">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {legend.map(({ icon: Icon, title, text }) => (
            <div key={title} className="card-soft p-4">
              <Icon size={20} className="text-brand" aria-hidden />
              <div className="mt-2 font-semibold">{title}</div>
              <p className="mt-1 text-[13px] leading-5 text-ink-3">{text}</p>
            </div>
          ))}
        </div>
      </Section>
    </>
  );
}
