import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { KeyRound } from 'lucide-react';
import { useAuth } from '../../auth/AuthProvider';
import { TextInput } from '../../components/form';
import { useToast } from '../../components/feedback';
import { errorMessage } from '../../lib/errors';

/** Davet bağlantısı veya parola sıfırlama bağlantısıyla gelen kullanıcı yeni parola belirler. */
export default function PasswordPage() {
  const auth = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (auth.loading) return null;
  if (!auth.session) return <Navigate to="/admin/login" replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (pw.length < 10 || !/[A-Za-zÇĞİÖŞÜçğıöşü]/.test(pw) || !/\d/.test(pw)) { setErr('Parola en az 10 karakter olmalı; harf ve rakam içermelidir.'); return; }
    if (pw !== pw2) { setErr('Parolalar eşleşmiyor.'); return; }
    setBusy(true);
    try {
      await auth.updatePassword(pw);
      toast.success('Parolanız güncellendi.');
      nav('/admin/dashboard', { replace: true });
    } catch (x) { setErr(errorMessage(x)); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-mist p-4">
      <form onSubmit={submit} className="card w-full max-w-md space-y-4 p-6" noValidate>
        <div className="flex items-center gap-2"><KeyRound className="text-brand" aria-hidden /><h1 className="text-[20px] font-bold">Yeni parola belirleyin</h1></div>
        <p className="text-[14px] text-ink-3">{auth.user?.email} hesabı için yeni bir parola girin.</p>
        <TextInput label="Yeni parola" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} hint="En az 10 karakter; harf ve rakam içermeli." />
        <TextInput label="Yeni parola (tekrar)" type="password" autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} />
        {err && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13.5px] text-red-800">{err}</div>}
        <button className="btn-primary w-full py-3" disabled={busy}>{busy ? 'Kaydediliyor…' : 'Parolayı kaydet'}</button>
      </form>
    </div>
  );
}
