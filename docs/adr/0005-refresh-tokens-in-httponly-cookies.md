# 5. Refresh tokens travel in httpOnly cookies

- **Status**: Accepted
- **Date**: 2026-09-02

## Context

The access/refresh split needs a delivery mechanism. Returning both tokens in
the JSON body is simpler to test and trivially cross-origin, but any XSS
vulnerability can then read the long-lived refresh token from JavaScript and
maintain persistent access to a user's financial data.

## Decision

- The **refresh token** is set as a `Secure`, `HttpOnly`, `SameSite=Lax`
  cookie scoped to `/api/v1/auth`, so it is unreadable by JavaScript and is not
  attached to ordinary API calls. `Secure` is disabled only in `local`/`test`,
  where there is no TLS.
- The **access token** is returned in the response body for the client to hold
  in memory. It is short-lived (15 minutes by default).
- Refresh tokens are stored **hashed** (SHA-256, since the token is already
  high-entropy) and **rotate** on every use: the presented token is revoked and
  linked to its replacement via `replaced_by_id`.
- Token type is asserted on decode, so a refresh token can never authenticate
  an ordinary request and vice versa.

## Consequences

- A stolen refresh token is usable at most once, and only before the
  legitimate client next refreshes.
- The frontend must send credentialed requests to the refresh endpoint, and
  CORS must be configured with explicit origins (never `*`) — already enforced
  by config validation.
- The `replaced_by_id` chain gives Phase 7 the data to detect replay attempts
  and revoke a whole token family.
