import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="container-x py-24 text-center">
      <div className="eyebrow">404</div>
      <h1 className="mt-2 text-[30px] font-bold">Sayfa bulunamadı</h1>
      <p className="lead mx-auto mt-3 max-w-lg">Aradığınız sayfa taşınmış veya hiç oluşturulmamış olabilir.</p>
      <div className="mt-6 flex justify-center gap-3">
        <Link to="/" className="btn-primary">Ana Sayfaya Dön</Link>
        <Link to="/proje" className="btn-outline">Proje Planı</Link>
      </div>
    </div>
  );
}
