import { useCore, useMaterialsData } from '../data/public';
import { isSupabaseConfigured } from '../lib/supabase';
import DataNotice from '../components/DataNotice';
import MaterialsLive from './materials/MaterialsLive';
import MaterialsStatic from './materials/MaterialsStatic';

/**
 * Supabase yapılandırılmışsa ortak (veritabanı) listesi gösterilir; değilse veya bağlantı kurulamazsa
 * özgün, tarayıcı içi düzenlenebilir sürüm kullanılır.
 */
export default function MaterialsPage() {
  const core = useCore();
  const stage = core.data.phases.find((p) => p.slug === 'materials');
  const mats = useMaterialsData();
  if (!isSupabaseConfigured || (mats.error && mats.fallback)) {
    return <MaterialsStatic stage={stage} notice={mats.error ? <DataNotice state={mats} /> : undefined} />;
  }
  return <MaterialsLive data={mats.data} loading={mats.loading} stage={stage} settings={core.data.settings} notice={<DataNotice state={core} />} />;
}
