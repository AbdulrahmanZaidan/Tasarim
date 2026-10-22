/** Uygulama genelinde Türkçe, kullanıcıya gösterilebilir hata. */
export class AppError extends Error {
  code: string;
  constructor(message: string, code = 'unknown') {
    super(message);
    this.name = 'AppError';
    this.code = code;
  }
}

interface RawError { message?: string; code?: string; details?: string | null; hint?: string | null; status?: number; statusCode?: string | number; error?: string; name?: string }

const constraintMessages: Record<string, string> = {
  result_needs_evidence: '“Başarılı” veya “Başarısız” sonucu için gözlenen çıktı ve deney tarihi girilmelidir.',
  phase_dates_ok: 'Hedef tarih, başlangıç tarihinden önce olamaz.',
  rate_has_date: 'Döviz kuru girildiğinde kur tarihi de girilmelidir.',
  ref_price_order: 'Referans fiyat aralığı geçersiz.',
};

/** Supabase / PostgREST / Storage / Auth hatalarını anlaşılır Türkçe iletiye çevirir. */
export function toAppError(e: unknown): AppError {
  if (e instanceof AppError) return e;
  const err = (e ?? {}) as RawError;
  const msg = String(err.message ?? (e instanceof Error ? e.message : '') ?? '');
  const code = String(err.code ?? err.statusCode ?? '');

  if (/Failed to fetch|NetworkError|Load failed|fetch failed|ERR_NETWORK/i.test(msg)) {
    return new AppError('Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.', 'network');
  }
  // Kimlik doğrulama
  if (/Invalid login credentials/i.test(msg)) return new AppError('E-posta adresi veya parola hatalı.', 'auth_invalid');
  if (/Email not confirmed/i.test(msg)) return new AppError('E-posta adresi henüz doğrulanmamış.', 'auth_unconfirmed');
  if (/Signups not allowed|signup.*disabled/i.test(msg)) return new AppError('Kayıt kapalıdır. Hesaplar yalnızca yönetici daveti ile oluşturulur.', 'auth_signup_disabled');
  if (/rate limit|too many requests/i.test(msg) || err.status === 429) return new AppError('Çok fazla deneme yapıldı. Lütfen birkaç dakika sonra tekrar deneyin.', 'rate_limited');
  if (/Password should be at least|weak.?password/i.test(msg)) return new AppError('Parola yeterince güçlü değil (en az 8 karakter; harf ve rakam içermeli).', 'auth_weak_password');
  if (/JWT expired|invalid JWT|PGRST301|PGRST303/i.test(msg + code)) return new AppError('Oturumunuzun süresi doldu. Lütfen yeniden giriş yapın.', 'session_expired');
  // Depolama
  if (/exceeded the maximum allowed size|Payload too large/i.test(msg) || err.statusCode === '413' || err.status === 413) {
    return new AppError('Dosya, izin verilen en büyük boyutu aşıyor.', 'file_too_large');
  }
  if (/mime type .* is not supported|invalid_mime_type/i.test(msg)) return new AppError('Bu dosya türünün bu depoya yüklenmesine izin verilmiyor.', 'file_type');
  if (/The resource already exists|Duplicate/i.test(msg) && /storage|resource/i.test(msg)) return new AppError('Aynı adla bir dosya zaten var.', 'file_exists');
  if (/Object not found|not_found/i.test(msg)) return new AppError('Dosya bulunamadı.', 'not_found');
  // Veritabanı
  if (code === '42501' || /row-level security|permission denied|Unauthorized/i.test(msg)) {
    return new AppError(/Rol değiştirme|yönetici yetkisi|düzenleme yetkisi/.test(msg) ? msg : 'Bu işlem için yetkiniz yok.', 'forbidden');
  }
  if (code === 'PGRST116') return new AppError('Kayıt bulunamadı veya bu işlem için yetkiniz yok.', 'not_found');
  if (code === '23505') return new AppError('Bu değerle bir kayıt zaten var (ör. aynı kod veya kısa ad).', 'duplicate');
  if (code === '23503') {
    return new AppError(/delete|update/i.test(msg)
      ? 'Bu kayıt başka kayıtlarda kullanıldığı için silinemez. Önce bağlı kayıtları kaldırın.'
      : 'Seçilen ilişkili kayıt bulunamadı.', 'in_use');
  }
  if (code === '23514' || code === '23502' || code === '22023' || code === 'P0001' || code === 'P0002') {
    const c = Object.keys(constraintMessages).find((k) => msg.includes(k));
    if (c) return new AppError(constraintMessages[c], 'validation');
    if (/[çğıöşüÇĞİÖŞÜ]/.test(msg)) return new AppError(msg, 'validation'); // sunucudaki Türkçe iletiler
    return new AppError('Girilen değerler geçerlilik kurallarına uymuyor.', 'validation');
  }
  if (code === '22P02' || code === '22007' || code === '22008') return new AppError('Geçersiz değer biçimi (sayı veya tarih).', 'validation');
  if (code === 'not_configured') return new AppError(msg, 'not_configured');
  if (/[çğıöşüÇĞİÖŞÜ]/.test(msg)) return new AppError(msg, code || 'unknown');
  return new AppError('Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.' + (msg ? ` (${msg.slice(0, 140)})` : ''), code || 'unknown');
}

export function errorMessage(e: unknown) {
  return toAppError(e).message;
}
