import { describe, expect, it } from 'vitest';

import { ConfigError, readConfig } from '@/app/config';

describe('readConfig', () => {
  it('reads the API base URL from the environment', () => {
    const config = readConfig({ VITE_API_BASE_URL: 'https://api.example.com' });

    expect(config.apiBaseUrl).toBe('https://api.example.com');
  });

  it('strips a trailing slash so URL joins never double up', () => {
    const config = readConfig({ VITE_API_BASE_URL: 'https://api.example.com/' });

    expect(config.apiBaseUrl).toBe('https://api.example.com');
  });

  it('throws when the required API base URL is missing', () => {
    expect(() => readConfig({})).toThrow(ConfigError);
  });

  it('throws when the API base URL is not a valid URL', () => {
    expect(() => readConfig({ VITE_API_BASE_URL: 'not a url' })).toThrow(ConfigError);
  });

  it('treats the Sentry DSN as optional', () => {
    const config = readConfig({ VITE_API_BASE_URL: 'https://api.example.com' });

    expect(config.sentryDsn).toBeUndefined();
  });
});
