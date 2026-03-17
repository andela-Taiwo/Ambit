/**
 * Runtime configuration, validated at startup.
 *
 * Mirrors the backend's fail-fast rule (plan Section 6): a missing or
 * malformed required value stops the app immediately rather than surfacing as
 * a confusing network error later.
 */

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigError';
  }
}

export interface AppConfig {
  readonly apiBaseUrl: string;
  readonly sentryDsn?: string;
}

type RawEnv = Record<string, string | undefined>;

const requireUrl = (env: RawEnv, key: string): string => {
  const value = env[key];
  if (value === undefined || value.trim() === '') {
    throw new ConfigError(`Missing required environment variable: ${key}`);
  }

  const trimmed = value.trim().replace(/\/+$/, '');
  if (!URL.canParse(trimmed)) {
    throw new ConfigError(`Environment variable ${key} is not a valid URL: ${value}`);
  }
  return trimmed;
};

export const readConfig = (env: RawEnv): AppConfig => {
  const apiBaseUrl = requireUrl(env, 'VITE_API_BASE_URL');
  const sentryDsn = env['VITE_SENTRY_DSN']?.trim();

  return sentryDsn !== undefined && sentryDsn !== '' ? { apiBaseUrl, sentryDsn } : { apiBaseUrl };
};

export const config: AppConfig = readConfig(import.meta.env);
