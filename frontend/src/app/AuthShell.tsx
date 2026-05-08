import { useEffect, type JSX, type ReactNode } from 'react';

import { LoadingState } from '@/components/ui';
import { bootstrapAuth, useAuthStore } from '@/features/auth/store';

export const AuthShell = ({ children }: { children: ReactNode }): JSX.Element => {
  const status = useAuthStore((state) => state.status);

  useEffect(() => {
    if (status === 'booting') {
      void bootstrapAuth();
    }
  }, [status]);

  if (status === 'booting') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <LoadingState label="Restoring your session…" />
      </div>
    );
  }
  return <>{children}</>;
};
