/** TanStack Query hooks. Server state lives here, never in Zustand. */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';

import { fetchHealth, type HealthPayload } from '@/api/health';
import { config } from '@/app/config';

export const healthQueryKey = ['health'] as const;

export const useHealth = (): UseQueryResult<HealthPayload> =>
  useQuery({
    queryKey: healthQueryKey,
    queryFn: ({ signal }) => fetchHealth(config.apiBaseUrl, signal),
    retry: false,
    staleTime: 30_000,
  });
