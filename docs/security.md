# Security

## Implemented Controls

- Password hashing with bcrypt.
- JWT access tokens with issuer, audience, expiry, and token type.
- Hashed refresh tokens with server-side session revocation.
- RBAC permission mapping by organization membership.
- Rate limiting on login, signup, refresh, and password reset.
- CORS allowlist.
- Secure response headers.
- SQL injection resistance through SQLAlchemy parameterization.
- Audit-log schema for sensitive actions.
- WebSocket token validation.
- File-size and extension filtering during code indexing.

## Production Hardening

- Encrypt GitHub OAuth tokens before database storage with KMS.
- Add CSRF tokens if cookie auth is introduced.
- Add risk-based auth checks for suspicious login patterns.
- Enforce TLS everywhere.
- Add SAST, dependency scanning, image scanning, and secret scanning gates.
- Add GitHub webhook signature verification.
- Run containers as non-root and apply network policies.
- Add prompt-injection filters and repository-content trust boundaries.
- Add per-tenant rate limits and LLM budget controls.
