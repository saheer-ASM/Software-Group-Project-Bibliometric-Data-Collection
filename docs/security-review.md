# Security Review: ScholarMetrics (backend, frontend, production)

- **Date:** 2026-10-24
- **Repository:** Software-Group-Project-Bibliometric-Data-Collection, branch `feature/author_extraction` (HEAD `a862653`)
- **Scope:** `backend/`, `frontend/`, `production/`, plus the files they depend on: `firestore.rules`, `.dockerignore` and `.gitignore`
- **Method:** Manual reading of all backend and production files and the security-relevant frontend files. Git history searched for leaked secrets. `npm audit --omit=dev` run in both packages. Nothing was executed against a running deployment.

## Summary

| # | Severity | Finding |
|---|----------|---------|
| 1 | ~~High~~ **Fixed** | Rate limiter keys every request on the nginx container IP, so all users share one 300 req/min bucket |
| 2 | ~~High~~ **Mitigated** | Expensive unauthenticated endpoints run on synchronous SQLite and block the whole Node process |

> **Remediation (2026-10-24, uncommitted, branch `feature/author_extraction`):**
> - **#1:** `TRUST_PROXY` is supported in `server.js` and set to `uniquelocal` in `compose.yaml`. nginx sets `X-Forwarded-For`/`X-Real-IP` to the visitor's `CF-Connecting-IP`, replacing any client-sent value. A per-IP `limit_req` (10 r/s, burst 50) is added at the edge.
> - **#2:** `/api/search`, `/api/search/publications`, `/api/compare` and `/api/authors` now require a session. A per-account `heavyQueryLimit` (60/min, configurable through `HEAVY_RATE_LIMIT_*`) covers them. `authorId` values are validated against `/^A\d{1,20}$/` before any query, and the frontend sends `authHeaders()` on these calls.
> - **Still open for #2:** the underlying full scans and the synchronous driver. The lasting fix is an indexed `author_id → pub_id` table in the pipeline and/or moving queries to a worker thread.
> - **Tests:** backend 56/56 and frontend 128/128 pass. `nginx -t` was not run because Docker was offline.
| 3 | **Medium** | Unverified Firebase tokens can rebind a legacy profile's `firebaseUid` and edit profile fields |
| 4 | **Medium** | Sessions can't be revoked: 7-day JWTs in `localStorage`, and password reset/logout don't invalidate them |
| 5 | **Medium** | The dev and production `JWT_SECRET` are identical, and the code falls back to `'dev-secret'` |
| 6 | **Medium** | Legacy `/api/auth/login` password endpoint is still live, with no per-account brute-force protection |
| 7 | **Medium** | No security headers anywhere (CSP, frame-ancestors, nosniff, HSTS, Referrer-Policy) |
| 8 | **Medium** | Vulnerable runtime dependencies in the backend (body-parser DoS, node-forge via firebase-admin) |
| 9 | Low | Internal error messages are returned to clients (`error: err.message`) |
| 10 | Low | Dead or legacy code with dangerous capabilities (`createUser`, `ensureFirebaseAuthUser`, `GET /api/authors/:id`) |
| 11 | Low | Secrets stored in a OneDrive-synced folder, with an unused `.env.bak` and stale Postgres credentials |
| 12 | Low | nginx trusts client-supplied forwarding headers (`X-Forwarded-Proto`, `set_real_ip_from 0.0.0.0/0`) |
| 13 | Low | Unescaped `LIKE` wildcards in the publication title filter |
| 14 | Info | Frontend build-chain vulnerabilities (react-scripts 5, 2 critical / 28 high, mostly build-time) |

**Secrets in git: none found.** `backend/.env`, `backend/serviceAccountKey.json`, `frontend/.env` and `production/.env` are all git-ignored and were never committed. The `JWT_SECRET=` values in history are placeholders only (`your_super_secret_jwt_key_here`, `…long_random_secret`). The `private_key` match in commit `323e5fc` is code (`process.env.FIREBASE_PRIVATE_KEY`), not a key.

---

## 1. High: the rate limiter treats every user as one client

**Where:** `backend/middleware/rateLimit.js:29-34` and `backend/server.js` (no `app.set('trust proxy', …)`)

The request path is Cloudflare → cloudflared → edge nginx → backend. Express doesn't have `trust proxy` set, so `req.ip` is the socket peer, which is the **nginx container's IP on `appnet`**. Every visitor therefore shares one counter: `RATE_LIMIT_MAX_REQUESTS=300` per 60 s.

**Impact:**
- One client sending about 5 requests a second gets HTTP 429 returned to **every** user of the site, including login.
- The limiter doesn't stop a single abuser any more than it stops everyone else, so it gives no real per-client protection.
- Normal traffic from a handful of users will hit the shared limit on its own (the Data Explorer issues several calls per page view).

**Fix:**
- In `server.js`, add `app.set('trust proxy', 'loopback, uniquelocal')`, or the exact `appnet` subnet.
- In `production/nginx/default.conf`, forward the real client address from Cloudflare: `proxy_set_header X-Forwarded-For $http_cf_connecting_ip;`. Better still, use `real_ip_header CF-Connecting-IP;` together with `set_real_ip_from` for the cloudflared source (127.0.0.1 / the Docker gateway).
- Add an nginx `limit_req_zone` keyed on the real client IP as a first layer, with a much stricter zone for `/api/auth/`.

## 2. High: unauthenticated heavy queries block the event loop

**Where:**
- `backend/config/database.js:41,71-74`: `DatabaseSync` (`node:sqlite`) is **synchronous**.
- `backend/routes/search.js:24-30`: `AUTHOR_MATCH_SQL` is a full scan of about 3M rows in `author_contribution_weight`, run for every `GET /api/search` and `/api/search/publications`.
- `backend/routes/compare.js:12-18`: same full scan, plus per-author correlated subqueries.
- `backend/repositories/authorRepository.js:4-18`: `INSTR(UNICODE_LOWER(author_name), …)` makes one JavaScript callback per author row.
- None of `/api/search`, `/api/search/publications`, `/api/compare`, `/api/authors?q=` or `/api/stats` requires authentication. Only `/api/authors/search` and `/api/authors/:id` do.

**Impact:** Each of these queries freezes the single Node process for the full duration of the query, which the code comments put at seconds to tens of seconds. While it runs:
- every other request (login, library, health) waits;
- the Docker healthcheck times out (5 s) and can mark the backend unhealthy.

A few concurrent anonymous requests with random `authorId` values, or with non-ASCII `q` values to force `UNICODE_LOWER`, make the site unavailable. Finding 1 means the rate limiter won't stop it.

**Fix (in order of effort):**
1. Require `authMiddleware` on `/api/search`, `/api/search/publications` and `/api/compare`, or add a strict per-IP limit to them once finding 1 is fixed.
2. Add indexes so the 10-slot scan goes away. For example, build a normalized `author_publication(author_id, pub_id)` table in the pipeline and index it. That changes a full scan into an index lookup.
3. Validate `authorId` against the OpenAlex pattern (`/^A\d{1,20}$/`) before querying. A random id currently costs a full scan.
4. Longer term, move queries to a `worker_threads` pool, or use an async driver, so one slow query can't stall the process.

## 3. Medium: unverified tokens can rebind a legacy profile's `firebaseUid`

**Where:** `backend/routes/auth.js:54-70` (`findProfile`), called from `/registration-status` (line 239) and `/registration/profile` (line 261), both with `requireVerifiedEmail: false`.

`findProfile` falls back to `findByEmail`. It then **writes** `firebaseUid = decoded.uid` and `emailVerified`, and its comment says this is safe because "the token proves ownership of this verified email". On these two routes the email is **not** verified. `/register-profile` guards against this (`existing.firebaseUid !== decoded.uid → 409`), but these two routes don't.

**Scenario:** A Firestore profile exists for `victim@x` and no Firebase Auth user currently holds that address. This happens to:
- legacy profiles where `ensureFirebaseAuthUser` returned `null`;
- legacy profiles whose Auth user was deleted from the console.

The attack then goes like this:
1. The attacker creates a Firebase email/password account for `victim@x`. It stays unverified.
2. The attacker calls `/api/auth/registration-status`.
3. The victim's profile is now bound to the attacker's uid, and `emailVerified` is set to false.
4. If the profile is incomplete, `/registration/profile` also lets the attacker overwrite username and designation.

No session token is issued, because verification is still required, so this is not account takeover. It is unauthorized modification of another user's profile, and it can lock out the real owner.

**Fix:** In `findProfile`, only rebind `firebaseUid` or update `email`/`emailVerified` when `decoded.email_verified === true`. When an email match carries a different, non-null `firebaseUid`, return 409 (as `/register-profile` does). Never fall back to email lookup for unverified tokens.

## 4. Medium: sessions can't be revoked

**Where:** `backend/routes/auth.js:10-14` (`expiresIn: '7d'`), `backend/middleware/auth.js`, and `frontend/src/AuthForm.jsx:94`, `CompleteProfile.jsx:72`, `ResetPassword.jsx:111` (`localStorage.setItem('token', …)`).

- The backend JWT is valid for 7 days and has no revocation check. Logout (`App.js:145`) only deletes the browser's copy.
- `/api/auth/reset-password` issues a new session but **doesn't invalidate existing ones**. A user who resets their password because a token was stolen stays compromised for up to 7 days.
- A token in `localStorage` can be read by any script on the origin. Finding 7 (no CSP) means nothing limits the damage of any future XSS. I found no `dangerouslySetInnerHTML` or `innerHTML` in `frontend/src`, which is good.

**Fix:**
- Add a `tokenVersion` (or `sessionsValidAfter`) field to the user document and include it in the JWT. Check it in `authMiddleware`, and bump it on password reset, logout-everywhere and admin disable.
- Shorten `JWT_EXPIRES_IN` (for example to 1h) and add a refresh flow. Alternatively, move to an `HttpOnly; Secure; SameSite=Strict` cookie.

## 5. Medium: shared `JWT_SECRET` and an insecure fallback

**Where:** `backend/middleware/auth.js:3` and `backend/routes/auth.js:6` (`process.env.JWT_SECRET || 'dev-secret'`), plus `backend/.env` and `production/.env`.

- I compared the two files without printing the values: `backend/.env` and `production/.env` contain the **same** 54-character `JWT_SECRET`. Any token minted by a dev or local backend is accepted in production. That includes any build where a teammate has the dev `.env`, and the in-memory user store where ids are `"1"`, `"2"`, … Anyone holding the dev `.env` can forge production sessions for any user id.
- `compose.yaml:88` correctly fails if the variable is unset. Running `npm start` outside compose without it, however, silently signs tokens with `'dev-secret'`.

**Fix:** Rotate the production secret now and keep it different from dev. In code, throw at startup when `JWT_SECRET` is missing or shorter than 32 bytes, and keep the fallback only when `NODE_ENV === 'test'`.

Also check `backend/server.js:2`. It loads dotenv from `path.resolve(__dirname, '..', 'env')`, which is a file literally named `env` in the repo root. That looks like a typo, and it means an unexpected file could inject configuration.

## 6. Medium: legacy password login is still live

**Where:** `backend/routes/auth.js:322-349`

`POST /api/auth/login` still checks bcrypt hashes stored in Firestore for legacy users. It has no per-account lockout or delay, and the only limit is the global shared one (finding 1). Each attempt also costs a bcrypt-12 compare, roughly 250 ms of CPU, which adds to finding 2. A 500 response leaks `err.message`.

**Fix:** Migrate the remaining legacy users to Firebase. `/reset-password` already clears `user.password`, so you could force a reset. Then return 410 from `/login`, as `/register` and `/change-password` already do. Until then, add a per-username and per-IP failure counter with exponential back-off.

## 7. Medium: no security headers

**Where:** `production/nginx/default.conf`, `production/nginx/frontend.conf`, `backend/server.js` (no `helmet`; `X-Powered-By: Express` is sent)

None of these are set: `Content-Security-Policy`, `X-Frame-Options`/`frame-ancestors` (clickjacking of the profile and settings pages), `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Strict-Transport-Security`, or `Permissions-Policy`.

**Fix:** In the edge nginx `server {}` block (use `always` so error responses are covered too):

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;  # or enable in Cloudflare
add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://apis.google.com; connect-src 'self' https://*.googleapis.com https://*.firebaseio.com https://identitytoolkit.googleapis.com https://securetoken.googleapis.com; frame-src https://*.firebaseapp.com https://accounts.google.com; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'" always;
```

Start with `Content-Security-Policy-Report-Only` and tune it against the Firebase sign-in pop-up. In Express, add `app.disable('x-powered-by')`.

## 8. Medium: vulnerable backend dependencies

`npm audit --omit=dev` in `backend/` reports **3 high, 7 moderate** issues:
- **body-parser** (high): DoS via trailing bytes after a compressed body. `express.json()` is reachable without authentication.
- **node-forge** (high, via firebase-admin): RSA PKCS#1 v1.5 signature verification accepts extra nested elements.
- **uuid / gaxios / google-gax / teeny-request** (moderate, via firebase-admin).

**Fix:** Update to `express@^4.21` (or 5.x) and the latest `firebase-admin@13`, run `npm audit fix`, and commit `backend/package-lock.json`. It is currently git-ignored, so `npm ci` in the Dockerfile depends on an untracked file and builds are not reproducible.

## 9. Low: internal error messages returned to clients

**Where:** `routes/auth.js:27` (`error: err.message` on every Firebase failure), `:347`, `:420`; `routes/authors.js:17,30,49`.

Firebase Admin and SQLite messages can reveal project ids, table names or internal state. `routes/search.js`, `compare.js` and `stats.js` already do this correctly: they log server-side and return a generic message.

**Fix:** Follow the `search.js` pattern everywhere.

## 10. Low: dead code with dangerous capabilities

- `services/firebaseUserStore.js:114-129` `ensureFirebaseAuthUser`: if the email already exists, it **overwrites that Firebase user's password** using Admin rights. It is reachable only through `createUser`, which no route calls today. If anyone re-wires it, it becomes a direct account takeover.
- `findOrCreateSocialUser` and `updatePassword(..., {syncFirebase})` are also unused.
- `GET /api/authors/:id` (`services/authorSearchService.js`, `repositories/authorRepository.js:20-112`) queries tables that don't exist in `openalex.db`, and calls `upsertMetrics` (an `INSERT`) on a read-only handle. Every call errors and leaks the SQLite message (finding 9).

**Fix:** Delete these functions and the `/:id` route, or put them behind a feature flag.

## 11. Low: local secret hygiene

None of these files are in git, but they are on disk:
- `backend/serviceAccountKey.json` is a Firebase **service-account private key**, with full Admin rights over Auth and Firestore. It sits in `OneDrive\Desktop\…`, so it is synced to Microsoft cloud storage and to every device on that OneDrive account.
- `backend/.env.bak` is a second copy of the backend secrets.
- `production/.env` and `backend/.env` still hold `DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DATABASE_URL` for the retired PostgreSQL database, which nothing uses any more. If that database still exists, its credentials sit in the clear here.

**Fix:**
- Move `serviceAccountKey.json` and `production/.env` out of the OneDrive tree, or exclude the folder from sync.
- Delete `.env.bak`.
- Remove the unused DB variables and rotate or decommission the old Postgres credentials.
- Consider rotating the service-account key, since it has been syncing.

## 12. Low: nginx trusts client-supplied headers

- `production/nginx/00-upgrade-map.conf:16-19`: `$forwarded_proto` passes the client's own `X-Forwarded-Proto` through unchanged. Nothing reads it today, but if the backend ever builds absolute URLs or secure-cookie logic from it, a client can spoof it. Overwrite it with the value Cloudflare guarantees: `proxy_set_header X-Forwarded-Proto https;`.
- `production/nginx/frontend.conf:13`: `set_real_ip_from 0.0.0.0/0` trusts `X-Forwarded-For` from anyone, which only affects log accuracy. Restrict it to the `appnet` subnet.
- `frontend/deploy/nginx.conf` is an older stand-alone config without `server_tokens off` and the hardening above. Delete it, or keep it in sync, so nobody deploys it by mistake.

## 13. Low: `LIKE` wildcard injection

**Where:** `backend/routes/search.js:216-217`. `` `%${title}%` `` is bound safely, so this is not SQL injection. However, `%` and `_` in user input act as wildcards, and patterns such as `%_%_%_%…` make the scan more expensive (see finding 2).

**Fix:** Escape them: `title.replace(/[\\%_]/g, '\\$&')` together with `LIKE ? ESCAPE '\'`, and cap `title` at around 200 characters.

## 14. Info: frontend dependency audit

`npm audit --omit=dev` in `frontend/` reports **2 critical, 28 high**. Almost all come from `react-scripts@5.0.1` (webpack-dev-server, svgo, serialize-javascript, shell-quote, launch-editor, …), which is **build or dev-server tooling** and doesn't ship in the production bundle. However, because `react-scripts` is listed under `dependencies`, the audit counts it as runtime. The runtime-relevant entries are:
- `firebase` → `@grpc/grpc-js`, which affects the Node transport, not browsers;
- `axios` → `follow-redirects`, which is Node only.

**Fix:**
- Move `react-scripts` and `@testing-library/*` to `devDependencies`.
- Plan a migration off CRA, which is unmaintained, to Vite.
- Upgrade `firebase` and `axios` to the latest versions.
- Never expose `npm start` (webpack-dev-server) on a network.

---

## What is already done well

- **Parameterized SQL everywhere.** Dynamic SQL fragments are built only from fixed whitelists (`CITATION_TYPES`, `IMPACT_LEVELS`, `CONTRIBUTIONS`, citation column whitelist), and every user value is bound. I found no SQL injection.
- **The database is opened read-only, twice over:** a `:ro` bind mount plus `readOnly: true`.
- **Library access is tied to the user.** Routes derive the document id from the verified JWT (`routes/library.js:55`), never from the request, so there is no IDOR. Inputs are length- and count-capped, and writes are transactional.
- **Firestore rules are tight.** Default deny, admin via a signed custom claim, owner identity and server timestamps enforced, a field whitelist on create and admin update, and length limits.
- **Email verification comes from the Firebase token or user record**, never from the request body. Retired endpoints (`/register`, `/change-password`) return 410.
- **Container posture is sound.** Only nginx publishes a port, bound to `127.0.0.1`. The backend runs as the `node` user. `.dockerignore` keeps `.env` files and `serviceAccountKey.json` out of images. Source maps are disabled in the production build. `server_tokens off` is set.
- **No `dangerouslySetInnerHTML`/`innerHTML`/`eval`** in the frontend. External links use `rel="noopener noreferrer"`. The post-login redirect (`afterLoginPath`) only uses in-app router state, so it is not an open redirect.
- **The public health endpoint** reports status without failure details.

## Suggested order of work

1. Findings 1 and 2: fix the client IP and rate limiting, and put auth and limits on `/api/search` and `/api/compare`. This closes the easy site-wide DoS.
2. Finding 5: rotate the production `JWT_SECRET` and remove the fallback.
3. Finding 3: stop `findProfile` from writing on unverified tokens.
4. Findings 4 and 6: add session revocation and retire `/api/auth/login`.
5. Findings 7 and 8: add security headers and upgrade the backend dependencies.
6. Findings 9–13: clean-up.
