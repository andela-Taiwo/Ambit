# 13. Access tokens live in memory, refresh tokens in httpOnly cookies

- **Status**: Accepted
- **Date**: 2026-10-27

## Context

A finance SPA needs a session that survives a page reload without making token
theft trivial. `localStorage` is readable by any XSS payload and persists across
tabs indefinitely.

## Decision

- The short-lived access token is held only in a module variable and attached by
  the API client. It is never written to `localStorage`/`sessionStorage`.
- The refresh token remains an httpOnly, Secure, SameSite cookie set by the
  backend. On boot the SPA calls `POST /auth/refresh` with credentials, then
  `GET /auth/me`.
- One 401 triggers a single refresh-and-retry. Concurrent refreshes share one
  in-flight promise. A failed refresh clears the token and moves the Zustand auth
  store to `anonymous`, which protected routing turns into a redirect to login.
- Login/register/refresh calls opt out of retry so a real 401 is surfaced.

## Consequences

- Reloading restores the session from the cookie without exposing a token to
  JavaScript.
- Multiple tabs each restore independently; the cookie is the shared secret.
- A hard XSS compromise can still act while the page is open, but cannot exfiltrate
  a long-lived token from storage.
