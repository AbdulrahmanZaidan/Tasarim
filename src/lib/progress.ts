/**
 * İLERLEME HESABI (tek ve belgelenmiş yöntem)
 * ------------------------------------------------------------
 * 1) Aşama ilerlemesi  = tamamlanan görevlerin ağırlıkları toplamı / tüm görevlerin ağırlıkları toplamı × 100
 *    (Görevi olmayan aşamanın ilerlemesi "tanımsız" kabul edilir ve 0 olarak sayılır.)
 * 2) Genel ilerleme    = Σ (aşama ağırlığı × aşama ilerlemesi) / Σ aşama ağırlıkları
 *    Aşama ağırlıklarının toplamı 100 olmalıdır; yönetici panelindeki “Ağırlıkları kaydet” işlemi bunu denetler.
 *    Tüm ağırlıklar 0 ise aşamalar eşit ağırlıklı sayılır.
 * 3) Dönem ilerlemesi  = (2) yalnızca ilgili dönemin aşamalarıyla hesaplanır.
 * Elle girilen yüzde KULLANILMAZ; `progress_updates.progress_value` yalnızca tarihsel bilgi notudur.
 */

export interface ProgressTask { status: string; weight?: number | null; phase_id?: string | null; component_id?: string | null }
export interface ProgressPhase { id: string; weight?: number | null; semester?: string }

export function taskProgress(tasks: ProgressTask[]): number | null {
  const total = tasks.reduce((a, t) => a + (Number(t.weight) || 1), 0);
  if (total === 0) return null;
  const done = tasks.filter((t) => t.status === 'completed').reduce((a, t) => a + (Number(t.weight) || 1), 0);
  return round1((done / total) * 100);
}

export function phaseProgress(phaseId: string, tasks: ProgressTask[]) {
  return taskProgress(tasks.filter((t) => t.phase_id === phaseId));
}

export function componentProgress(componentId: string, tasks: ProgressTask[]) {
  return taskProgress(tasks.filter((t) => t.component_id === componentId));
}

export interface WeightedResult {
  value: number;
  /** Ağırlık toplamı (100 olmalıdır) */
  weightSum: number;
  weightsValid: boolean;
  /** Görev tanımlanmamış aşama sayısı */
  phasesWithoutTasks: number;
}

export function weightedProgress(phases: ProgressPhase[], tasks: ProgressTask[]): WeightedResult {
  const weightSum = round2(phases.reduce((a, p) => a + (Number(p.weight) || 0), 0));
  const equal = weightSum === 0;
  let acc = 0;
  let wsum = 0;
  let without = 0;
  for (const p of phases) {
    const w = equal ? 1 : Number(p.weight) || 0;
    const pr = phaseProgress(p.id, tasks);
    if (pr === null) without++;
    acc += w * (pr ?? 0);
    wsum += w;
  }
  return { value: wsum ? round1(acc / wsum) : 0, weightSum, weightsValid: equal || Math.abs(weightSum - 100) < 0.005, phasesWithoutTasks: without };
}

export function semesterProgress(semester: string, phases: ProgressPhase[], tasks: ProgressTask[]) {
  return weightedProgress(phases.filter((p) => p.semester === semester), tasks);
}

/** Yeni aşama ağırlıklarını doğrular; hata iletisi veya null döner. */
export function validateWeights(values: Record<string, number>): string | null {
  const nums = Object.values(values);
  if (nums.some((n) => !Number.isFinite(n) || n < 0 || n > 100)) return 'Her ağırlık 0 ile 100 arasında olmalıdır.';
  const sum = round2(nums.reduce((a, b) => a + b, 0));
  if (Math.abs(sum - 100) > 0.005) return `Ağırlıkların toplamı 100 olmalıdır (şu an ${sum.toLocaleString('tr-TR')}).`;
  return null;
}

const round1 = (n: number) => Math.round(n * 10) / 10;
const round2 = (n: number) => Math.round(n * 100) / 100;
