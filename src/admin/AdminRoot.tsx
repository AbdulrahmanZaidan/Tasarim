import { Outlet } from 'react-router-dom';
import { Database, ExternalLink } from 'lucide-react';
import { isSupabaseConfigured } from '../lib/supabase';
import logo from '../assets/sdu-logo.png';

/** /admin altındaki tüm sayfalar. Supabase yapılandırılmamışsa kurulum yönergesi gösterilir. */
export default function AdminRoot() {
  if (!isSupabaseConfigured) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-brand-mist p-4">
        <div className="card w-full max-w-xl p-7">
          <div className="flex items-center gap-3"><img src={logo} alt="" className="h-11 w-11" /><div><div className="eyebrow">Yönetim paneli</div><h1 className="text-[22px] font-bold">Veritabanı bağlantısı yapılandırılmamış</h1></div></div>
          <p className="prose-body mt-4">Yönetim paneli Supabase ile çalışır. Bu derlemede <code className="mono rounded bg-brand-mist px-1">VITE_SUPABASE_URL</code> ve <code className="mono rounded bg-brand-mist px-1">VITE_SUPABASE_ANON_KEY</code> ortam değişkenleri tanımlı değil; genel site depodaki statik verilerle çalışmaya devam ediyor.</p>
          <ol className="mt-4 list-decimal space-y-1.5 pl-5 text-[14px] text-ink-2">
            <li>Supabase’de yeni bir proje oluşturun.</li>
            <li>SQL Editor’da <code className="mono">supabase/setup.sql</code> dosyasını çalıştırın.</li>
            <li>Proje kökünde <code className="mono">.env</code> dosyası oluşturup iki değişkeni doldurun (bkz. <code className="mono">.env.example</code>).</li>
            <li>Vercel’de aynı değişkenleri Project Settings → Environment Variables bölümüne ekleyin.</li>
          </ol>
          <p className="mt-4 flex items-center gap-1.5 text-[13px] text-ink-3"><Database size={14} aria-hidden /> Ayrıntılı adımlar depodaki <b>SETUP.md</b> dosyasındadır.</p>
          <a href={`${import.meta.env.BASE_URL}`} className="btn-outline mt-5">Siteye dön <ExternalLink size={14} aria-hidden /></a>
        </div>
      </div>
    );
  }
  return <Outlet />;
}
