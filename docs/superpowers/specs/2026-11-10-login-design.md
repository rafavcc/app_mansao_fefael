# Login page — design

## Why
The app will be reachable from the public internet through Tailscale Funnel. That lets Rafa open it from
the work PC (no Tailscale there) and gives Fefe a plain link. Today there is no authentication at all: every
page and every `/api` endpoint is open to anyone who can reach the server.

## Goals
- Two accounts: `rafavcc` (Fafa, user `FAFA`) and `fefe` (Fefe, user `FEFE`).
- Each person sets their own password on their first login.
- Every page and every `/api` endpoint requires a logged-in session. Only `/login`, `/api/health` and the
  static/NiceGUI assets stay public.
- Sessions survive server restarts and last 30 days per device.

## Non-goals
- Turning on Funnel or changing how the server is started (a separate step, documented, done with Rafa).
- Database encryption, "who entered this expense", and the other proposed improvements.
- A password-reset email flow or more than two users.

## Anti-goals
- A stranger who reaches the public URL must never be able to set a password, including for an account
  that has not been set up yet.

## Approaches considered
- **Login inside the app** (chosen): username and hashed password in the database, NiceGUI session. Works
  identically on the tailnet, over Funnel and from the work PC.
- Tailscale identity headers only: no passwords, but Funnel requests carry no identity, so the work PC and
  Fefe's link would not work. Rejected.
- A separate auth proxy (e.g. "Sign in with Google"): an extra service to run and maintain for two people.
  Rejected.

## Decisions
- **First-time setup only from Rafa's own devices** (Rafa's choice). If an account has no password yet,
  the login page offers "create password" only when the request is not public: a direct local request, or
  a tailnet request through `tailscale serve`. A request marked by Funnel (`Tailscale-Funnel-Request`
  header) gets "Account not set up. Ask Rafa." The check fails closed: when unsure, refuse setup.
  Fefe sets her password the first time on one of Rafa's devices; after that she can log in from anywhere.
- Accounts live on the existing `users` table: new nullable columns `login` (unique) and `password_hash`,
  added by the existing `_add_missing_columns` migration. The seed sets `FAFA → rafavcc`, `FEFE → fefe`.
- Passwords: at least 8 characters, hashed with `hashlib.scrypt` (standard library, random salt per
  password), compared in constant time. No new dependency.
- Session: NiceGUI `app.storage.user` keeps the logged-in user and login time; it expires after 30 days.
  One middleware (the NiceGUI authentication pattern) guards both pages and `/api`: pages redirect to
  `/login?next=…`, the API answers 401.
- Brute force: after 5 wrong passwords for one account, that account refuses logins for 15 minutes
  (kept in memory).
- Header shows who is logged in and a logout button.
- Forgotten password: `python -m app.auth reset fefe` clears the password, so it can be set again from
  one of Rafa's devices.
- `CASA_STORAGE_SECRET` must be fixed: the systemd service (`/etc/systemd/system/app-mansao-fefael.service`)
  does not set it today, so every restart would log everyone out. Rafa sets it in the service (documented in
  the README); the app keeps its current warning when it is missing.

## Left to the builder
- Exact wording and layout of the login page, consistent with the existing theme (light and dark, phone width).
- How the tests fake local, tailnet and Funnel requests.
- Verifying, against a real `tailscale serve`/Funnel, which headers each kind of request carries, before
  relying on them.
