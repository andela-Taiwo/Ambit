import { QueryClientProvider } from '@tanstack/react-query';
import { type JSX, type ReactNode, useState } from 'react';

import { createQueryClient } from '@/app/queryClient';

export const AppProviders = ({ children }: { children: ReactNode }): JSX.Element => {
  const [queryClient] = useState(createQueryClient);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};
