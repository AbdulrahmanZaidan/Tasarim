const entity: Record<string, string> = {
  settings: 'Proje ayarları', phase: 'Aşama', component: 'Bileşen', task: 'Görev', simulation: 'Simülasyon', progress: 'İlerleme kaydı',
  media: 'Dosya', document: 'Belge', material: 'Malzeme', purchase: 'Satın alma', profile: 'Kullanıcı',
};
const special: Record<string, string> = {
  'task.completed': 'Görev tamamlandı', 'phase.status_changed': 'Aşama durumu değişti', 'simulation.result_changed': 'Deney sonucu güncellendi',
  'media.uploaded': 'Dosya yüklendi', 'purchase.recorded': 'Satın alma kaydedildi', 'profile.role_changed': 'Kullanıcı rolü değişti',
  'settings.updated': 'Proje ayarları değiştirildi',
};
const verb: Record<string, string> = { created: 'eklendi', updated: 'güncellendi', deleted: 'silindi' };

export const entityLabels = entity;
export function actionLabel(action: string) {
  if (special[action]) return special[action];
  const [e, v] = action.split('.');
  return `${entity[e] ?? e} ${verb[v] ?? v}`;
}
