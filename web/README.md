# Ubuzima web

React + Vite + TypeScript frontend for the Ubuzima health buddy: onboarding, chat (streaming), voice, settings, and an admin panel. English and Kinyarwanda, light and dark themes.

## Install and run

```bash
cd web
npm install
cp .env.example .env     # optional; see below
npm run dev              # http://localhost:5173
```

Other scripts: `npm test` (vitest), `npm run typecheck`, `npm run build`.

## Pointing at a backend

The API base URL comes from `VITE_API_BASE` (default `http://127.0.0.1:8099`). Set it in `web/.env`:

```
VITE_API_BASE=http://127.0.0.1:8099
```

Restart `npm run dev` after changing it. The backend must allow your dev origin via CORS.

### Real backend / real answers

The backend defaults to **fake-provider mode**: replies are placeholders and no external model is called. To use real models, run the backend with an OpenRouter key and a non-fake provider (set `OPENROUTER_API_KEY` and the provider setting in the backend's `.env`; see the backend README for exact variable names), then point `VITE_API_BASE` at it. The frontend never holds that key.

## Fake-provider mode: what to expect

Answers are grounded only in approved documents. Until an admin uploads **and approves** a PDF, most questions return the calm "I don't have verified information, please see a doctor or health worker" referral message. That is expected, not a bug. Upload and approve a document in the admin panel, wait for its ingest status to show Indexed, then ask a related question.

## Admin panel

Open `/admin` (or the "Admin" nav link) and sign in with an admin or reviewer account created in the backend (use the backend's bootstrap/seed command or `.env` admin settings to create one). Roles gate the UI: reviewers can approve/reject, admins can also manage users and delete. The server remains the authority.

## Settings

`/settings`: theme and language, edit profile (only changed fields are sent), re-run onboarding, and "Wipe my data" (deletes your profile server-side after a confirmation).

## Notes

- Anonymous identity: a session is created automatically; tokens live in browser storage. Nothing is logged.
- No gradients, `prefers-reduced-motion` respected, layouts tested down to 360px wide.
