# Ubuzima — Web Frontend (Sub-project 3-web) — Design Spec

- **Date:** 2026-10-11
- **Project:** Ubuzima SRHR Digital Navigator — browser-testable end-user web app + admin panel.
- **Builds on:** the running backend (sub-projects 1 & 2) at `VITE_API_BASE` (default `http://127.0.0.1:8099`). Frontend-only, plus one small additive backend change (CORS).
- **Goal:** a real, clickable end-user experience a person can use in a browser (and on a phone browser) today — onboarding, chat (text + voice), EN/RW, light/dark — plus an admin panel to manage the knowledge base. Native Flutter is a later packaging step on the same API.

## 1. Intent & confirmed decisions
- **Scope:** ONE Vite + React + TypeScript app. End-user experience at `/`; admin panel at `/admin` (credential-gated). Mobile-responsive (this is the "mobile" experience in a browser).
- **Design:** "Warm & friendly buddy" — soft rounded cards, a warm accent (coral + teal), large friendly type, playful but calm micro-animations; chat feels like texting a trusted friend. **No gradients.** Light + dark (persisted). WCAG-AA contrast; calm, non-alarming treatment for sensitive/crisis content.
- **Languages:** Kinyarwanda + English, user-togglable; a frontend UI string dictionary (separate from the backend's AI-copy i18n).
- **Providers:** backend runs in fake-provider mode for testing, so AI answers are placeholder text — the UX, safety rendering, citations, admin flows are all real.

## 2. Architecture
Vite + React 18 + TypeScript. React Router. Data via lightweight fetch hooks (or TanStack Query). Framer Motion (or CSS) for animation. Styling via CSS custom properties (design tokens) — no CSS-in-JS required; no gradient tokens.

```
web/
  index.html
  src/
    main.tsx, App.tsx, router.tsx
    api/            # typed client: client.ts (fetch wrapper, base URL, auth header, token refresh), endpoints (identity, profile, chat, voice, admin), types.ts
    auth/           # token store (localStorage, try/catch), anon bootstrap, admin session
    theme/          # tokens.css (:root + dark), ThemeProvider, toggle
    i18n/           # en/rw string dicts + useT()
    components/     # Button, Card, Bubble, Chip, Avatar, Spinner, Toast, Modal, LangToggle, ThemeToggle
    features/
      onboarding/   # nickname, language, age-band, pronouns, interests/tone, optional sensitive-context (clearly labeled)
      chat/         # message list, composer, SSE streaming, citation + safety/referral + crisis rendering
      voice/        # record (MediaRecorder) -> /v1/voice/chat -> play reply + show transcript/answer
      settings/     # theme, language, profile edit, data wipe
      admin/        # login, documents (list/upload/review/reindex/delete + status), users (list/disable), audit log
    styles/
  .env.example      # VITE_API_BASE
  package.json, tsconfig.json, vite.config.ts, vitest.config.ts
```
**Backend change (additive):** add CORS middleware to FastAPI, allow-list from a setting (`CORS_ORIGINS`, default includes `http://localhost:5173` and `http://127.0.0.1:5173`). No other backend change.

## 3. End-user flows (against real endpoints)
- **Onboarding:** on first visit, `POST /v1/identity/anon` → store tokens. Collect profile (all optional except a nickname prompt): nickname, preferred language, age band, gender/pronouns, interests/tone, and an explicitly-labeled, skippable "sensitive health context" with a short privacy note (stored encrypted server-side). `PUT /v1/profile`. Re-entrant/skippable.
- **Chat:** `POST /v1/chat/stream` (SSE) for streamed answers; render user/assistant bubbles; show **citations** (source chips) when present; render **referral / "see a doctor"** callouts and **crisis** responses with distinct, calm, supportive styling (not alarming red); show a typing indicator while streaming. Conversation continuity via `conversation_id`. Graceful handling of the out-of-knowledge answer (the common case until PDFs are approved).
- **Voice (turn-based):** record mic audio (MediaRecorder), `POST /v1/voice/chat` (multipart) → show transcript + answer, play returned `audio_base64` (if `tts_available`), else show text. A clear "Live mode (full-duplex) coming soon" placeholder for `/v1/live` (needs WebRTC; out of scope here).
- **Settings:** theme toggle, language toggle, edit profile (`PUT /v1/profile`), **wipe my data** (`DELETE /v1/profile`) with confirm.

## 4. Admin panel (`/admin`)
- **Login:** `POST /v1/admin/login` (email/password) → store admin tokens separately from the end-user anon token.
- **Documents:** list (`GET /v1/admin/documents`) with status/review badges; **upload** a PDF (multipart, with title/language/topic tags); **review** approve/reject (`POST …/review`); **reindex** (`POST …/reindex`); **delete** (admin). Show ingest status (uploaded/processing/indexed/failed).
- **Users:** list (`GET /v1/admin/users`), disable (`POST …/{id}/disable`).
- **Audit log:** `GET /v1/admin/audit`.
- RBAC respected (reviewer vs admin): hide/disable admin-only actions for reviewer tokens; handle 401/403/503 with clear messages.

## 5. Cross-cutting
- **Theming:** tokens on `:root`, dark under a `[data-theme="dark"]` + `prefers-color-scheme`; warm palette, no gradients; focus-visible rings; AA contrast. Persist theme + language in localStorage (try/catch).
- **Errors:** map the backend error envelope `{error:{code,message}}` to friendly toasts; 503 (provider unavailable / realtime extra) → a clear, non-scary message; network errors handled.
- **Accessibility:** keyboard-navigable, labelled controls, reduced-motion respected, screen-reader-friendly chat log.
- **Responsive:** phone-first; works at 360px width through desktop; no horizontal scroll; touch targets ≥44px.
- **Privacy:** reflect the backend's data-minimization — sensitive context clearly optional + wipe available; no secrets/tokens logged to console.

## 6. Testing
- **Vitest + React Testing Library** for: the API client (auth header, token refresh, error-envelope parsing — msw-mocked), the auth/token store, the i18n `useT`, the chat SSE parser, and key components (bubble renders citations/crisis styling; onboarding submits the right profile payload; admin upload posts multipart). 
- **Build gate:** `tsc --noEmit` + `vite build` must pass (no type errors). 
- Real end-to-end against the live backend is manual (the controller runs the dev server and smoke-tests the main flows).

## 7. Out of scope
Native Flutter app; live full-duplex WebRTC client (turn-based voice only here); offline/PWA sync; push notifications; SMS/USSD. (Interfaces/placeholders left so these slot in later.)

## 8. Run / deliverable
`npm install && npm run dev` serves on 5173; `VITE_API_BASE` points at the running backend (8099). The controller will run it and give the URL so you can test end-to-end as a user, plus the admin panel with the seeded admin account.
