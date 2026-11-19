import type { JSX } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { LoadingState } from '@/components/ui';
import { useAuthStore } from '@/features/auth/store';

export const ProtectedRoute = (): JSX.Element => {
  const status = useAuthStore((state) => state.status);
  const location = useLocation();

  if (status === 'booting') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <LoadingState label="Restoring your session…" />
      </div>
    );
  }
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
};
