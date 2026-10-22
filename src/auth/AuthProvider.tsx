import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured } from '../lib/supabase';
import { toAppError } from '../lib/errors';
import type { Profile } from '../services/entities';
import type { AppRole } from '../lib/labels';

interface AuthState {
  configured: boolean;
  loading: boolean;
  session: Session | null;
  user: User | null;
  profile: Profile | null;
  role: AppRole | null;
  /** Arayüz kolaylığı içindir; asıl yetki kontrolü veritabanı RLS ilkeleridir. */
  canEdit: boolean;
  isAdmin: boolean;
  /** Davet veya parola sıfırlama bağlantısıyla gelindi; yeni parola belirlenmeli */
  recovery: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  requestPasswordReset: (email: string) => Promise<void>;
  updatePassword: (password: string) => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(isSupabaseConfigured);
  const [recovery, setRecovery] = useState(() => typeof window !== 'undefined' && /type=(recovery|invite)/.test(window.location.hash));

  const loadProfile = useCallback(async (s: Session | null) => {
    if (!supabase || !s) { setProfile(null); return; }
    const { data } = await supabase.from('profiles').select('*').eq('id', s.user.id).maybeSingle();
    setProfile(data ?? null);
  }, []);

  useEffect(() => {
    if (!supabase) return;
    let alive = true;
    supabase.auth.getSession().then(async ({ data }) => {
      if (!alive) return;
      setSession(data.session);
      await loadProfile(data.session);
      if (alive) setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((event, s) => {
      setSession(s);
      if (event === 'PASSWORD_RECOVERY') setRecovery(true);
      if (event === 'SIGNED_OUT') { setProfile(null); setRecovery(false); }
      // Profil sorgusunu olay işleyicisinin dışında çalıştır (supabase-js önerisi)
      if (event === 'SIGNED_IN' || event === 'USER_UPDATED' || event === 'INITIAL_SESSION') setTimeout(() => void loadProfile(s), 0);
    });
    return () => { alive = false; sub.subscription.unsubscribe(); };
  }, [loadProfile]);

  const value = useMemo<AuthState>(() => {
    const role = profile?.role ?? null;
    return {
      configured: isSupabaseConfigured,
      loading,
      session,
      user: session?.user ?? null,
      profile,
      role,
      canEdit: role === 'admin' || role === 'editor',
      isAdmin: role === 'admin',
      recovery,
      async signIn(email, password) {
        if (!supabase) throw toAppError({ message: 'Supabase yapılandırılmamış', code: 'not_configured' });
        const { data, error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
        if (error) throw toAppError(error);
        setSession(data.session);
        await loadProfile(data.session);
      },
      async signOut() {
        if (!supabase) return;
        await supabase.auth.signOut({ scope: 'local' });
        setSession(null);
        setProfile(null);
      },
      async requestPasswordReset(email) {
        if (!supabase) return;
        const redirectTo = `${window.location.origin}${import.meta.env.BASE_URL}admin/parola`;
        const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo });
        if (error) throw toAppError(error);
      },
      async updatePassword(password) {
        if (!supabase) return;
        const { error } = await supabase.auth.updateUser({ password });
        if (error) throw toAppError(error);
        setRecovery(false);
      },
      refreshProfile: () => loadProfile(session),
    };
  }, [loading, session, profile, recovery, loadProfile]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth, AuthProvider içinde kullanılmalıdır.');
  return v;
}
