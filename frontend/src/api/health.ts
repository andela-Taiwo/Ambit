/**
 * Hand-written client for the unversioned health endpoint.
 *
 * From Phase 1 onward, feature clients are generated from the backend's
 * OpenAPI schema into `src/api/generated/`; this module stays hand-written
 * because the probe contract is fixed and must work before any schema exists.
 */

export class ApiError extends Error {
  readonly status: number | undefined;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export interface HealthPayload {
  readonly status: 'ok';
}

const isHealthPayload = (value: unknown): value is HealthPayload =>
  typeof value === 'object' && value !== null && (value as { status?: unknown }).status === 'ok';

export const fetchHealth = async (
  baseUrl: string,
  signal?: AbortSignal,
): Promise<HealthPayload> => {
  const requestId = crypto.randomUUID();

  const response = await fetch(`${baseUrl}/health`, {
    headers: {
      Accept: 'application/json',
      'X-Request-ID': requestId,
    },
    ...(signal ? { signal } : {}),
  });

  if (!response.ok) {
    throw new ApiError(
      `Health check failed with status ${String(response.status)}`,
      response.status,
    );
  }

  const body: unknown = await response.json();
  if (!isHealthPayload(body)) {
    throw new ApiError('Health response did not match the expected contract');
  }
  return body;
};
