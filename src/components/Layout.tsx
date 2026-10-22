import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigation } from 'react-router-dom';
import { Menu, X, ExternalLink, FileText, LogIn, LayoutDashboard } from 'lucide-react';
import { useCore } from '../data/public';
import { useAuth } from '../auth/AuthProvider';
import { isSupabaseConfigured } from '../lib/supabase';
import { ErrorBoundary } from './ErrorBoundary';

import logo from '../assets/sdu-logo.png';

export const navItems = [
  { to: '/', label: 'Ana Sayfa', end: true },
  { to: '/proje', label: 'Proje Planı', end: true },
  { to: '/proje/mimari-sema', label: 'Mimari ve Şema' },
  { to: '/proje/simulasyon', label: 'Simülasyon' },
  { to: '/proje/github', label: 'GitHub' },
  { to: '/proje/malzeme-maliyet', label: 'Malzeme ve Maliyet' },
  { to: '/proje/ilerleme', label: 'İlerleme Durumu' },
  { to: '/proje/tasarim-ii', label: 'Tasarım II' },
];

export default function Layout() {
  const [open, setOpen] = useState(false);
  const { pathname, hash } = useLocation();
  const navigation = useNavigation();
  const { data: core } = useCore();
  const { session } = useAuth();
  const st = core.settings;

  useEffect(() => {
    setOpen(false);
    if (!hash) window.scrollTo({ top: 0 });
    else document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView({ behavior: 'smooth' });
  }, [pathname, hash]);

  return (
    <div className="flex min-h-screen flex-col">
      {navigation.state === 'loading' && (
        <div className="fixed inset-x-0 top-0 z-[80] h-[3px] overflow-hidden bg-brand-soft" role="progressbar" aria-label="Sayfa yükleniyor">
          <div className="h-full w-1/3 animate-[nav_1s_ease-in-out_infinite] bg-brand" />
        </div>
      )}
      <a href="#icerik" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">İçeriğe geç</a>
      <header className="sticky top-0 z-40 border-b border-brand-line/70 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-[64px] w-full max-w-[1320px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex min-w-0 items-center gap-3 text-ink hover:text-ink">
            <img src={logo} alt="Süleyman Demirel Üniversitesi logosu" className="h-10 w-10 shrink-0" />
            <span className="min-w-0 leading-tight">
              <span className="block truncate text-[11px] font-semibold tracking-[0.14em] text-brand">SÜLEYMAN DEMİREL ÜNİVERSİTESİ</span>
              <span className="block truncate text-[15px] font-bold">8-Bit Breadboard Bilgisayar</span>
            </span>
          </Link>
          <nav aria-label="Ana menü" className="hidden xl:block">
            <ul className="flex items-center gap-0.5">
              {navItems.map((n) => (
                <li key={n.to}>
                  <NavLink to={n.to} end={n.end}
                    className={({ isActive }) => `relative whitespace-nowrap rounded-md px-2 py-2 text-[13.5px] font-medium transition-colors ${isActive ? 'text-brand after:absolute after:inset-x-2 after:-bottom-[13px] after:h-[3px] after:bg-brand' : 'text-ink-2 hover:bg-brand-mist hover:text-ink'}`}>
                    {n.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <button className="btn-ghost xl:hidden" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="mobil-menu" aria-label={open ? 'Menüyü kapat' : 'Menüyü aç'}>
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
        <div id="mobil-menu" className={`overflow-hidden border-t border-brand-line/70 bg-white transition-[max-height] duration-300 xl:hidden ${open ? 'max-h-[520px]' : 'max-h-0 border-t-0'}`}>
          <ul className="container-x grid gap-1 py-3 sm:grid-cols-2">
            {navItems.map((n) => (
              <li key={n.to}>
                <NavLink to={n.to} end={n.end} className={({ isActive }) => `block rounded-md px-3 py-2.5 text-[15px] font-medium ${isActive ? 'bg-brand-soft text-brand' : 'text-ink-2 hover:bg-brand-mist'}`}>{n.label}</NavLink>
              </li>
            ))}
          </ul>
        </div>
      </header>

      <main id="icerik" className="flex-1" key={pathname}>
        <div className="animate-rise"><ErrorBoundary><Outlet /></ErrorBoundary></div>
      </main>

      <footer className="mt-auto border-t-[3px] border-brand bg-brand-mist">
        <div className="container-x grid gap-8 py-10 text-[14px] text-ink-2 md:grid-cols-3">
          <div className="flex gap-3">
            <img src={logo} alt="" className="h-12 w-12" />
            <div>
              <div className="text-[11px] font-semibold tracking-[0.14em] text-brand">SÜLEYMAN DEMİREL ÜNİVERSİTESİ</div>
              <div className="mt-1 font-semibold text-ink">{st.course}</div>
              <div className="text-ink-3">{st.title}</div>
            </div>
          </div>
          <div>
            <div className="mb-1 font-semibold text-ink">Danışman</div>
            <div>{st.supervisor}</div>
            <div className="mb-1 mt-3 font-semibold text-ink">Proje Ekibi</div>
            {st.team.map((s) => <div key={s.studentId || s.name}>{s.name}{s.studentId && <> · <span className="mono">{s.studentId}</span></>}</div>)}
          </div>
          <div>
            <div className="mb-1 font-semibold text-ink">Bağlantılar</div>
            <ul className="space-y-1">
              {st.githubUrl && <li><a href={st.githubUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1">Proje GitHub deposu <ExternalLink size={12} aria-hidden /></a></li>}
              <li><Link to="/proje/belgeler" className="inline-flex items-center gap-1"><FileText size={13} aria-hidden /> Teknik belgeler</Link></li>
              {isSupabaseConfigured && (
                <li>
                  <Link to={session ? '/admin/dashboard' : '/admin/login'} className="inline-flex items-center gap-1">
                    {session ? <><LayoutDashboard size={13} aria-hidden /> Yönetim paneli</> : <><LogIn size={13} aria-hidden /> Ekip girişi</>}
                  </Link>
                </li>
              )}
            </ul>
          </div>
        </div>
      </footer>
    </div>
  );
}
