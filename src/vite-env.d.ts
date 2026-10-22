/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Supabase proje adresi, ör. https://abcd.supabase.co */
  readonly VITE_SUPABASE_URL?: string;
  /** Supabase "anon / publishable" anahtarı (herkese açık anahtar; yetki RLS ile sağlanır) */
  readonly VITE_SUPABASE_ANON_KEY?: string;
  /** "true" ise Supabase görüntü dönüştürme (küçük resim) kullanılır — ücretli plan gerektirir */
  readonly VITE_SUPABASE_IMAGE_TRANSFORM?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
