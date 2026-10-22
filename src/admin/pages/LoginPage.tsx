import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { LogIn, Mail, ArrowLeft } from 'lucide-react';
import { useAuth } from '../../auth/AuthProvider';
import { TextInput } from '../../components/form';
import { errorMessage } from '../../lib/errors';
import logo from '../../assets/sdu-logo.png';

export default function LoginPage() {
  const auth = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const from = (loc.state as { from?: string } | null)?.from ?? '/admin/dashboard';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<'login' | 'reset'>('login');
  const [sent, setSent] = useState(false);

  if (!auth.loading && auth.session && !auth.recovery) return <Navigate to={from} replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) { setErr('Geçerli bir e-posta adresi girin.'); return; }
    if (mode === 'login' && !password) { setErr('Parolanızı girin.'); return; }
    setBusy(true);
    try {
      if (mode === 'login') { await auth.signIn(email, password); nav(from, { replace: true }); }
      else { await auth.requestPasswordReset(email); setSent(true); }
    } catch (x) {
      setErr(errorMessage(x));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-mist p-4">
      <div className="w-full max-w-md">
        <div className="card overflow-hidden">
          <div className="border-b-[3px] border-brand bg-white px-6 pb-4 pt-6 text-center">
            <img src={logo} alt="Süleyman Demirel Üniversitesi logosu" className="mx-auto h-16 w-16" />
            <div className="mt-2 text-[11px] font-semibold tracking-[0.14em] text-brand">SÜLEYMAN DEMİREL ÜNİVERSİTESİ</div>
            <h1 className="mt-1 text-[22px] font-bold">{mode === 'login' ? 'Ekip Girişi' : 'Parola Sıfırlama'}</h1>
            <p className="mt-1 text-[13.5px] text-ink-3">8-Bit Breadboard Bilgisayar · Yönetim Paneli</p>
          </div>
          <form onSubmit={submit} className="space-y-4 px-6 py-6" noValidate>
            {sent ? (
              <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-[14px] text-ink-2">
                Bu e-posta adresi kayıtlıysa parola sıfırlama bağlantısı gönderildi. Gelen kutunuzu kontrol edin.
              </div>
            ) : (
              <>
                <TextInput label="E-posta" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
                {mode === 'login' && <TextInput label="Parola" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />}
                {err && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13.5px] text-red-800">{err}</div>}
                <button type="submit" className="btn-primary w-full py-3" disabled={busy}>
                  {mode === 'login' ? <><LogIn size={17} aria-hidden /> {busy ? 'Giriş yapılıyor…' : 'Giriş yap'}</> : <><Mail size={17} aria-hidden /> {busy ? 'Gönderiliyor…' : 'Sıfırlama bağlantısı gönder'}</>}
                </button>
              </>
            )}
            <div className="flex items-center justify-between text-[13px]">
              <button type="button" className="text-brand hover:text-brand-dark" onClick={() => { setMode(mode === 'login' ? 'reset' : 'login'); setErr(null); setSent(false); }}>
                {mode === 'login' ? 'Parolamı unuttum' : 'Girişe dön'}
              </button>
              <Link to="/" className="inline-flex items-center gap-1 text-ink-3 hover:text-brand"><ArrowLeft size={13} aria-hidden /> Siteye dön</Link>
            </div>
          </form>
        </div>
        <p className="mt-4 text-center text-[12.5px] text-ink-3">Kayıt herkese açık değildir. Hesaplar yalnızca proje yöneticisinin daveti ile oluşturulur.</p>
      </div>
    </div>
  );
}
