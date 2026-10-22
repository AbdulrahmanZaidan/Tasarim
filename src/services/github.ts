/**
 * GitHub REST API (kimlik doğrulamasız, yalnızca herkese açık depo verisi).
 * İstemcide gizli belirteç (token) KULLANILMAZ. Kimliksiz istek sınırı saatte 60 olduğu için
 * yanıtlar oturum boyunca 10 dakika önbelleğe alınır ve sınır aşıldığında açıklayıcı ileti gösterilir.
 */
import { AppError } from '../lib/errors';

export interface RepoMeta {
  full_name: string; description: string | null; html_url: string; default_branch: string; visibility?: string;
  created_at: string; pushed_at: string; updated_at: string; stargazers_count: number; forks_count: number; open_issues_count: number; size: number; language: string | null;
}
export interface Commit { sha: string; html_url: string; commit: { message: string; author: { name: string; date: string } | null }; author: { login: string; avatar_url: string } | null }
export interface TreeItem { path: string; type: 'blob' | 'tree'; size?: number }
export interface RepoSnapshot {
  meta: RepoMeta;
  commits: Commit[];
  tree: TreeItem[];
  treeTruncated: boolean;
  empty: boolean;
  fetchedAt: number;
}

const API = 'https://api.github.com';
const TTL = 10 * 60 * 1000;

async function gh<T>(path: string): Promise<{ status: number; data: T | null }> {
  const res = await fetch(`${API}${path}`, { headers: { Accept: 'application/vnd.github+json' } });
  if (res.status === 403 || res.status === 429) {
    const remaining = res.headers.get('x-ratelimit-remaining');
    const reset = Number(res.headers.get('x-ratelimit-reset'));
    if (remaining === '0' || res.status === 429) {
      const at = reset ? new Date(reset * 1000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) : null;
      throw new AppError(`GitHub API istek sınırına ulaşıldı.${at ? ` Saat ${at} itibarıyla yeniden denenebilir.` : ''}`, 'rate_limited');
    }
  }
  if (res.status === 404) return { status: 404, data: null };
  if (res.status === 409) return { status: 409, data: null }; // boş depo
  if (!res.ok) throw new AppError(`GitHub API yanıtı: ${res.status}`, 'github');
  return { status: res.status, data: (await res.json()) as T };
}

export async function fetchRepo(owner: string, name: string, force = false): Promise<RepoSnapshot> {
  const key = `sdu8bit.github.${owner}/${name}`;
  if (!force) {
    try {
      const c = sessionStorage.getItem(key);
      if (c) {
        const snap = JSON.parse(c) as RepoSnapshot;
        if (Date.now() - snap.fetchedAt < TTL) return snap;
      }
    } catch { /* depolama kullanılamıyor */ }
  }
  const base = `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`;
  const meta = await gh<RepoMeta>(base);
  if (!meta.data) throw new AppError('Depo bulunamadı veya herkese açık değil.', 'not_found');
  const [commits, tree] = await Promise.all([
    gh<Commit[]>(`${base}/commits?per_page=10`),
    gh<{ tree: TreeItem[]; truncated: boolean }>(`${base}/git/trees/${encodeURIComponent(meta.data.default_branch)}?recursive=1`),
  ]);
  const snap: RepoSnapshot = {
    meta: meta.data,
    commits: commits.data ?? [],
    tree: tree.data?.tree ?? [],
    treeTruncated: tree.data?.truncated ?? false,
    empty: commits.status === 409 || (commits.data?.length ?? 0) === 0,
    fetchedAt: Date.now(),
  };
  try { sessionStorage.setItem(key, JSON.stringify(snap)); } catch { /* yok say */ }
  return snap;
}

/** Ana dizinler ve içerdikleri dosya sayısı */
export function topDirectories(tree: TreeItem[]) {
  const dirs = new Map<string, number>();
  for (const t of tree) {
    const [top, ...rest] = t.path.split('/');
    if (t.type === 'tree' && rest.length === 0) dirs.set(top, dirs.get(top) ?? 0);
    if (t.type === 'blob' && rest.length > 0) dirs.set(top, (dirs.get(top) ?? 0) + 1);
  }
  return [...dirs.entries()].map(([name, files]) => ({ name, files })).sort((a, b) => a.name.localeCompare(b.name));
}

const important = [
  /^readme(\.[a-z]+)?$/i, /^package\.json$/, /^(setup|database|admin_guide|deployment|changelog|audit)\.md$/i,
  /^(docs|architecture|schematics|simulations|microcode|reports|supabase\/migrations)\/.+/i,
  /\.(dig|circ|pdsprj|ino|asm|hex)$/i,
];
/** Önemli kaynak dosyalar (README, belgeler, şemalar, simülasyon ve mikrokod dosyaları) */
export function importantFiles(tree: TreeItem[], limit = 24) {
  return tree.filter((t) => t.type === 'blob' && important.some((r) => r.test(t.path))).slice(0, limit);
}
