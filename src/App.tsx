/**
 * Rota tanımları (React Router veri yönlendiricisi).
 * Genel sayfaların adresleri önceki sürümle birebir aynıdır. Ağır sayfalar ve yönetim paneli
 * ayrı paketlere bölünür (route-level code splitting) ve ihtiyaç duyulduğunda yüklenir.
 */
import type { RouteObject } from 'react-router-dom';
import { Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import { RouteError } from './components/ErrorBoundary';

type Mod = { default: React.ComponentType };
const lazy = (load: () => Promise<Mod>) => async () => ({ Component: (await load()).default });

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'proje', lazy: lazy(() => import('./pages/PlanPage')) },
      { path: 'proje/mimari-sema', lazy: lazy(() => import('./pages/ArchitecturePage')) },
      { path: 'proje/simulasyon', lazy: lazy(() => import('./pages/SimulationPage')) },
      { path: 'proje/simulasyon/deney/:id', lazy: lazy(() => import('./pages/ExperimentPage')) },
      { path: 'proje/github', lazy: lazy(() => import('./pages/GithubPage')) },
      { path: 'proje/malzeme-maliyet', lazy: lazy(() => import('./pages/MaterialsPage')) },
      { path: 'proje/tasarim-ii', lazy: lazy(() => import('./pages/TasarimIIPage')) },
      { path: 'proje/ilerleme', lazy: lazy(() => import('./pages/ProgressPage')) },
      { path: 'proje/bilesen/:slug', lazy: lazy(() => import('./pages/ComponentPage')) },
      { path: 'proje/belgeler', lazy: lazy(() => import('./pages/DocumentsPage')) },
      { path: '*', lazy: lazy(() => import('./pages/NotFoundPage')) },
    ],
  },
  {
    path: 'admin',
    errorElement: <RouteError />,
    lazy: lazy(() => import('./admin/AdminRoot')),
    children: [
      { path: 'login', lazy: lazy(() => import('./admin/pages/LoginPage')) },
      { path: 'parola', lazy: lazy(() => import('./admin/pages/PasswordPage')) },
      {
        lazy: lazy(() => import('./admin/AdminLayout')),
        children: [
          { index: true, element: <Navigate to="dashboard" replace /> },
          { path: 'dashboard', lazy: lazy(() => import('./admin/pages/DashboardPage')) },
          { path: 'simulations', lazy: lazy(() => import('./admin/pages/SimulationsAdmin')) },
          { path: 'media', lazy: lazy(() => import('./admin/pages/MediaAdmin')) },
          { path: 'components', lazy: lazy(() => import('./admin/pages/ComponentsAdmin')) },
          { path: 'phases', lazy: lazy(() => import('./admin/pages/PhasesAdmin')) },
          { path: 'tasks', lazy: lazy(() => import('./admin/pages/TasksAdmin')) },
          { path: 'materials', lazy: lazy(() => import('./admin/pages/MaterialsAdmin')) },
          { path: 'purchases', lazy: lazy(() => import('./admin/pages/PurchasesAdmin')) },
          { path: 'documents', lazy: lazy(() => import('./admin/pages/DocumentsAdmin')) },
          { path: 'progress', lazy: lazy(() => import('./admin/pages/ProgressAdmin')) },
          { path: 'settings', lazy: lazy(() => import('./admin/pages/SettingsAdmin')) },
          { path: 'activity', lazy: lazy(() => import('./admin/pages/ActivityAdmin')) },
          { path: '*', element: <Navigate to="dashboard" replace /> },
        ],
      },
    ],
  },
];
