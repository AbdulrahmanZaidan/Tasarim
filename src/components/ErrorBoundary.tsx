import { Component, type ReactNode } from 'react';
import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom';

/** Bileşen düzeyi hata sınırı: bir bölüm çökerse sayfanın kalanı çalışmaya devam eder. */
export class ErrorBoundary extends Component<{ children: ReactNode; fallback?: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error) { console.error('[ErrorBoundary]', error); }
  render() {
    if (this.state.error) {
      return this.props.fallback ?? (
        <div role="alert" className="card m-4 p-5 text-[14px] text-ink-2">
          <b className="text-ink">Bu bölüm görüntülenirken bir hata oluştu.</b>
          <div className="mt-1 text-ink-3">{this.state.error.message}</div>
          <button className="btn-outline mt-3 py-1.5" onClick={() => this.setState({ error: null })}>Tekrar dene</button>
        </div>
      );
    }
    return this.props.children;
  }
}

/** Yönlendirici düzeyi hata sayfası (ör. sayfa kodu yüklenemediğinde) */
export function RouteError() {
  const err = useRouteError();
  const chunk = err instanceof Error && /dynamically imported module|Loading chunk|Failed to fetch/i.test(err.message);
  return (
    <div className="container-x py-24 text-center">
      <div className="eyebrow">{isRouteErrorResponse(err) ? err.status : 'Hata'}</div>
      <h1 className="mt-2 text-[28px] font-bold">{chunk ? 'Sayfa güncellenmiş olabilir' : 'Bir şeyler ters gitti'}</h1>
      <p className="lead mx-auto mt-3 max-w-lg">
        {chunk ? 'Sitenin yeni bir sürümü yayımlandı. Sayfayı yenileyerek devam edebilirsiniz.' : 'Sayfa görüntülenirken beklenmeyen bir hata oluştu.'}
      </p>
      <div className="mt-6 flex justify-center gap-3">
        <button className="btn-primary" onClick={() => window.location.reload()}>Sayfayı yenile</button>
        <Link to="/" className="btn-outline">Ana Sayfa</Link>
      </div>
    </div>
  );
}
