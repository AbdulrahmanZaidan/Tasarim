import type { Enums } from './database.types';

export type AppRole = Enums<'app_role'>;
export type PhaseStatus = Enums<'phase_status'>;
export type WorkStatus = Enums<'work_status'>;
export type Priority = Enums<'task_priority'>;
export type ExperimentResult = Enums<'experiment_result'>;
export type PurchaseStatus = Enums<'purchase_status'>;
export type MediaCategory = Enums<'media_category'>;
export type DocumentType = Enums<'document_type'>;
export type Semester = Enums<'semester'>;

export const roleLabels: Record<AppRole, string> = { admin: 'Yönetici', editor: 'Düzenleyici', viewer: 'İzleyici' };
export const roleHints: Record<AppRole, string> = {
  admin: 'Tüm yönetim yetkileri, kullanıcı rolleri ve proje ayarları',
  editor: 'İçerik ekleme, düzenleme ve silme (ayarlar ve roller hariç)',
  viewer: 'Yalnızca okuma; yayımlanmamış kayıtları görebilir',
};

/** Aşama durumları — mevcut genel sitedeki etiketlerle uyumlu */
export const phaseStatusLabels: Record<PhaseStatus, string> = {
  planned: 'Planlandı', not_started: 'Henüz Başlamadı', in_progress: 'Devam Ediyor', completed: 'Tamamlandı', blocked: 'Engellendi',
};
export const workStatusLabels: Record<WorkStatus, string> = {
  not_started: 'Başlanmadı', in_progress: 'Devam Ediyor', completed: 'Tamamlandı', blocked: 'Engellendi',
};
export const priorityLabels: Record<Priority, string> = { low: 'Düşük', medium: 'Orta', high: 'Yüksek' };
export const resultLabels: Record<ExperimentResult, string> = {
  not_started: 'Başlanmadı', in_progress: 'Sürüyor', passed: 'Başarılı', failed: 'Başarısız', needs_review: 'İnceleme Gerekli',
};
export const purchaseLabels: Record<PurchaseStatus, string> = {
  not_purchased: 'Alınmadı', ordered: 'Sipariş Verildi', received: 'Teslim Alındı', tested: 'Test Edildi',
};
export const mediaCategoryLabels: Record<MediaCategory, string> = {
  simulation_screenshot: 'Simülasyon ekran görüntüsü',
  architecture_diagram: 'Mimari diyagram',
  circuit_schematic: 'Devre şeması',
  breadboard_photo: 'Breadboard fotoğrafı',
  component_photo: 'Bileşen fotoğrafı',
  testing_evidence: 'Test kanıtı',
  report: 'Rapor',
  technical_file: 'Teknik dosya',
  receipt: 'Makbuz / fatura',
};
export const documentTypeLabels: Record<DocumentType, string> = {
  project_report: 'Proje raporu',
  circuit_schematic: 'Devre şeması',
  architecture_document: 'Mimari belge',
  simulation_report: 'Simülasyon raporu',
  datasheet: 'Veri sayfası (datasheet)',
  test_report: 'Test raporu',
  meeting_notes: 'Toplantı notları',
  graduation_deliverable: 'Bitirme projesi teslimi',
};
export const semesterLabels: Record<Semester, string> = { tasarim_1: 'Tasarım I', tasarim_2: 'Tasarım II' };

export const softwareOptions = ['Digital', 'Logisim Evolution', 'Proteus', 'Diğer'] as const;

/** Durum rozetleri için renk sınıfları (erişilebilir kontrast) */
export const toneClass = {
  success: 'border-emerald-700/30 bg-emerald-50 text-emerald-800',
  warning: 'border-amber-600/30 bg-amber-50 text-amber-800',
  danger: 'border-red-700/30 bg-red-50 text-red-800',
  brand: 'border-brand-line bg-brand-soft text-brand',
  info: 'border-sky-600/30 bg-sky-50 text-sky-800',
  muted: 'border-ink-3/25 bg-neutral-100 text-ink-3',
} as const;
export type Tone = keyof typeof toneClass;

export const workTone: Record<WorkStatus, Tone> = { not_started: 'muted', in_progress: 'warning', completed: 'success', blocked: 'danger' };
export const phaseTone: Record<PhaseStatus, Tone> = { planned: 'brand', not_started: 'muted', in_progress: 'warning', completed: 'success', blocked: 'danger' };
export const resultTone: Record<ExperimentResult, Tone> = { not_started: 'muted', in_progress: 'warning', passed: 'success', failed: 'danger', needs_review: 'info' };
export const purchaseTone: Record<PurchaseStatus, Tone> = { not_purchased: 'muted', ordered: 'warning', received: 'info', tested: 'success' };
export const priorityTone: Record<Priority, Tone> = { low: 'muted', medium: 'brand', high: 'danger' };

export function options<K extends string>(labels: Record<K, string>) {
  return (Object.keys(labels) as K[]).map((value) => ({ value, label: labels[value] }));
}
