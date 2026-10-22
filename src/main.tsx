import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, createHashRouter, RouterProvider } from 'react-router-dom';
import { routes } from './App';
import { AuthProvider } from './auth/AuthProvider';
import { ConfirmProvider, ToastProvider } from './components/feedback';
import { ErrorBoundary } from './components/ErrorBoundary';
import './index.css';

// Tek dosyalık önizleme derlemesinde (mode=single) karma (#) adresler kullanılır;
// Vercel ve GitHub Pages derlemelerinde gerçek URL yolları.
const useHash = import.meta.env.MODE === 'single';
const basename = import.meta.env.BASE_URL.replace(/\/$/, '') || undefined;
const router = useHash ? createHashRouter(routes) : createBrowserRouter(routes, { basename });

function Boot() {
  return (
    <div className="flex min-h-screen items-center justify-center" aria-busy="true">
      <span className="h-8 w-8 animate-spin rounded-full border-[3px] border-brand-line border-t-brand" aria-label="Yükleniyor" />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <ToastProvider>
          <ConfirmProvider>
            <RouterProvider router={router} fallbackElement={<Boot />} future={{ v7_startTransition: true }} />
          </ConfirmProvider>
        </ToastProvider>
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
