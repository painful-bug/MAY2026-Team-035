# HomeBandhu API reference

All endpoints are under `/api/v1`. Browser requests use credentialed,
same-origin cookies; provider credentials are never JSON responses.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/auth/google/start` | Start signed PKCE Google OAuth. |
| GET | `/auth/methods` | Browser-safe enabled identity methods and primary order. |
| GET | `/auth/google/callback` | Exchange code and establish cookies. |
| GET | `/auth/session` | Identity, active membership, portal, and capabilities. |
| POST | `/auth/refresh` | Rotate the HTTP-only refresh session. |
| POST | `/auth/logout` | Revoke the provider session and clear cookies. |
| POST | `/invitations/prepare` | Store a short-lived opaque invitation context. |
| POST | `/invitations/redeem` | Redeem the pending invite for the verified Google email. |
| POST | `/admin/invitations` | Create an email-bound resident invitation. |
| GET | `/communities/search` | Minimal authenticated community typeahead projection. |
| GET | `/communities/admin/units` | Units in the active administrator community. |
| POST | `/access-requests` | Submit a self-service resident join request. |
| GET | `/access-requests/mine` | Current identity's persisted join requests. |
| POST | `/access-requests/{id}/withdraw` | Withdraw the caller's pending request. |
| GET | `/admin/access-requests` | Active administrator's tenant-scoped request queue. |
| POST | `/admin/access-requests/{id}/approve` | Atomically activate resident membership. |
| POST | `/admin/access-requests/{id}/reject` | Reject a pending request with an audit reason. |
| POST | `/onboarding/community` | Atomically create the founder's community. |

Unsafe methods require an exact same-origin Origin/Referer and the readable
CSRF cookie echoed as `X-CSRF-Token`: `hb_preauth_csrf` before authentication,
`__Host-hb_csrf` in production sessions (`hb_csrf` over local HTTP), or
`hb_recovery_csrf` during password recovery. The browser client obtains the
pre-authentication cookie from `GET /auth/csrf` automatically before its first
unsafe request. Establishing a session clears the pre-authentication cookie so
subsequent writes use only the session- or recovery-bound token.
