import { useEffect, useState } from 'react';
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigation } from 'react-router-dom';
import {
  LayoutDashboard, FlaskConical, Images, Cpu, Milestone, ListChecks, Boxes, ShoppingCart, FileText, History,
  Settings, ScrollText, LogOut, Menu, X, ExternalLink, UserCircle2,
} from 'lucide-react';
import { useAuth } from '../auth/AuthProvider';
import { roleLabels } from '../lib/labels';
import { ErrorBoundary } from '../components/ErrorBoundary';
import logo from '../assets/sdu-logo.png';

export const adminNav = [
  { to: 'dashboard', label: 'Genel Bakış', icon: LayoutDashboard },
  { to: 'simulations', label: 'Simülasyonlar', icon: FlaskConical },
  { to: 'media', label: 'Medya', icon: Images },
  { to: 'components', label: 'Bileşenler', icon: Cpu },
  { to: 'phases', label: 'Aşamalar', icon: Milestone },
  { to: 'tasks', label: 'Görevler', icon: ListChecks },
  { to: 'progress', label: 'İlerleme Kayıtları', icon: History },
  { to: 'materials', label: 'Malzemeler', icon: Boxes },
  { to: 'purchases', label: 'Satın Almalar', icon: ShoppingCart },
  { to: 'documents', label: 'Belgeler', icon: FileText },
  { to: 'activity', label: 'Etkinlik Günlüğü', icon: ScrollText, need: 'edit' as const },
  { to: 'settings', label: 'Ayarlar', icon: Settings },
];

export default function AdminLayout() {
  const auth = useAuth();
  const loc = useLocation();
  const navigation = useNavigation();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [loc.pathname]);

  if (auth.loading) {
    return <div className="flex min-h-screen items-center justify-center" aria-busy="true"><span className="h-8 w-8 animate-spin rounded-full border-[3px] border-brand-line border-t-brand" aria-label="Oturum denetleniyor" /></div>;
  }
  if (!auth.session) return <Navigate to="/admin/login" replace state={{ from: loc.pathname + loc.search }} />;
  if (auth.recovery) return <Navigate to="/admin/parola" replace />;
  if (!auth.profile) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-brand-mist p-4">
        <div className="card max-w-md p-6 text-center">
          <h1 className="text-[20px] font-bold">Profil bulunamadı</h1>
          <p className="prose-body mt-2">Hesabınız için uygulama profili oluşturulmamış. Lütfen proje yöneticisiyle iletişime geçin.</p>
          <button className="btn-outline mt-4" onClick={() => void auth.signOut()}>Çıkış yap</button>
        </div>
      </div>
    );
  }
  const items = adminNav.filter((n) => !n.need || auth.canEdit);

  const nav = (
    <nav aria-label="Yönetim menüsü" className="flex flex-col gap-0.5 px-3">
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={`/admin/${to}`}
          className={({ isActive }) => `flex items-center gap-2.5 rounded-lg px-3 py-2 text-[14px] font-medium transition-colors ${isActive ? 'bg-brand text-white hover:text-white' : 'text-ink-2 hover:bg-brand-soft hover:text-ink'}`}>
          <Icon size={17} aria-hidden /> {label}
        </NavLink>
      ))}
    </nav>
  );
  const userBox = (
    <div className="border-t border-brand-line p-3">
      <div className="flex items-center gap-2.5 px-2 py-1.5">
        <UserCircle2 size={30} className="shrink-0 text-brand" aria-hidden />
        <div className="min-w-0 flex-1 leading-tight">
          <div className="truncate text-[14px] font-semibold text-ink">{auth.profile.full_name || auth.user?.email}</div>
          <div className="truncate text-[12px] text-ink-3">{roleLabels[auth.profile.role]} · {auth.user?.email}</div>
        </div>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <Link to="/" className="btn-ghost justify-center px-2 py-1.5 text-[13px]"><ExternalLink size={14} aria-hidden /> Site</Link>
        <button className="btn-ghost justify-center px-2 py-1.5 text-[13px]" onClick={() => void auth.signOut()}><LogOut size={14} aria-hidden /> Çıkış</button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#FCFAFA]">
      {navigation.state === 'loading' && <div className="fixed inset-x-0 top-0 z-[80] h-[3px] overflow-hidden bg-brand-soft"><div className="h-full w-1/3 animate-[nav_1s_ease-in-out_infinite] bg-brand" /></div>}
      <a href="#admin-icerik" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">İçeriğe geç</a>
      {/* Masaüstü kenar çubuğu */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] flex-col border-r border-brand-line bg-white lg:flex">
        <Link to="/admin/dashboard" className="flex items-center gap-2.5 border-b-[3px] border-brand px-4 py-4 text-ink hover:text-ink">
          <img src={logo} alt="" className="h-9 w-9" />
          <span className="leading-tight"><span className="block text-[10.5px] font-semibold tracking-[0.14em] text-brand">YÖNETİM PANELİ</span><span className="block text-[14px] font-bold">8-Bit Bilgisayar</span></span>
        </Link>
        <div className="flex-1 overflow-y-auto py-3">{nav}</div>
        {userBox}
      </aside>
      {/* Mobil üst çubuk */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-brand-line bg-white px-4 lg:hidden">
        <Link to="/admin/dashboard" className="flex items-center gap-2 text-ink hover:text-ink"><img src={logo} alt="" className="h-8 w-8" /><b className="text-[15px]">Yönetim Paneli</b></Link>
        <button className="btn-ghost p-2" onClick={() => setOpen(true)} aria-label="Menüyü aç" aria-expanded={open}><Menu size={22} /></button>
      </header>
      {open && (
        <div className="fixed inset-0 z-50 flex lg:hidden" role="dialog" aria-modal="true" aria-label="Yönetim menüsü">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
          <div className="relative flex h-full w-[280px] flex-col bg-white shadow-xl animate-rise">
            <div className="flex items-center justify-between border-b-[3px] border-brand px-4 py-3"><b>Menü</b><button className="btn-ghost p-1.5" onClick={() => setOpen(false)} aria-label="Menüyü kapat"><X size={20} /></button></div>
            <div className="flex-1 overflow-y-auto py-3">{nav}</div>
            {userBox}
          </div>
        </div>
      )}
      <main id="admin-icerik" className="lg:pl-[248px]">
        <div className="mx-auto max-w-[1240px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <ErrorBoundary><Outlet /></ErrorBoundary>
        </div>
      </main>
    </div>
  );
}
