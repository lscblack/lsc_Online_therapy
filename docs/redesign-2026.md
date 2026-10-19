# Ubuzima redesign 2026 — shared design language (web + mobile)

One system across both apps. Inspired by four references: a modern green **chat** UI
(Chatzy), a calm **therapy landing** (Mindful), and an **admin dashboard** (EzMart).
Ubuzima stays a calm, private health companion — we borrow the *polish and layout*, not a
dating-app tone. Accessibility is non-negotiable: WCAG AA contrast, light + dark, large tap
targets (≥44px), `prefers-reduced-motion` honored, EN/RW throughout. No heavy gradients
(soft background "blobs" are OK).

## Palette (keep the emerald/forest-green brand; unify the two apps)

Primary brand — emerald green. Accent — teal-green. Single source of truth:
- Web tokens: `web/src/theme/tokens.css` (remember the dark block is duplicated in the
  `@media (prefers-color-scheme: dark)` query — update BOTH copies).
- Flutter: `mobile/lib/core/theme.dart` (`_lightScheme` / `_darkScheme`).

Unify light primary to the brighter green so both apps match:

| Token | Light | Dark |
|---|---|---|
| primary | `#15a06a` | `#45cf9f` |
| primary-strong (hover/text) | `#0c7a4e` | `#63dcb0` |
| accent (teal) | `#2bb6a3` | `#35c7bd` |
| bg | `#eef8f2` | `#0a1712` |
| surface | `#ffffff` | `#0f201a` |
| text | `#10271d` | `#e6f2ec` |
| danger | `#c0392b` | `#ff6b5e` |

**Admin surface accent (web only):** the admin console may use a warm **amber** accent
(`#f59e0b` light / `#fbbf24` dark) for KPI highlights/charts — EzMart energy — while keeping
the green brand for chrome. The user-facing app (chat/voice/onboarding/landing) stays green.

## Chat screen (from Chatzy, image 2) — the centerpiece

- Received (assistant) bubbles: left, surface-2 background, rounded 18px with a small
  "tail" corner (bottom-left radius tighter), assistant avatar (the "U" brand mark) to the left.
- Sent (user) bubbles: right, **primary** background, `primary-contrast` text, rounded 18px
  with tighter bottom-right corner.
- Day separators ("Today", date) centered, muted, small.
- Per-message meta under the bubble: time + a "Seen"/"Delivered" style status for sent.
- Typing indicator: three animated dots in a received bubble (respect reduced-motion → static).
- Composer: pill/rounded input, attach + emoji affordances optional, **circular primary
  send FAB** with a paper-plane icon; mic button to jump to voice.
- Safety/care callouts (crisis, referral) keep their distinct styling but adopt the new radii.
- Voice messages (where applicable): a waveform pill with a play button + duration.

## Landing (from Chatzy image 1 + Mindful image 4) — web only

- Hero: large headline (2 lines, strong weight), supportive subcopy, two pill CTAs
  (primary "Start chatting" + ghost "Talk by voice"), and a device/app mock or illustrated
  orb with floating "chips" (already present — refine). Soft background blobs.
- Trust row / feature grid: 3–4 cards with inline SVG icons (private, grounded, EN+RW, 24/7).
- A calm "how it works" 3-step strip, a stats/why panel, FAQ `<details>`, CTA band, footer.
- Mindful influence: generous whitespace, rounded everything, friendly but clinical-calm.

## Admin dashboard (from EzMart image 3) — web only

- Left sidebar: brand, nav items with icons (Overview, Documents, Users, Audit, AI Models),
  active item pill-highlighted. Collapses on narrow screens.
- Top bar: page title, search, theme/lang toggles, admin identity.
- Overview: a KPI row of stat cards (value, label, % delta chip green↑/red↓), then a chart
  row (the existing hand-rolled SVG charts in `features/admin/charts.tsx` — restyle: line/area
  for activity, donut for category split), then tables/panels.
- Use the **amber** accent for primary KPI emphasis and chart highlights; green for positive
  deltas, red for negative. Cards: surface, soft shadow, radius-lg.
- Surface the new **Jev** status (`GET /v1/admin/system` → `jev: {configured, model, triage,
  rerank}`) as a small status card/badge next to the STT/GPU card.

## Shared component rules

- Radii: sm 10 / md 14 / lg 20 / xl 28 / pill 999. Bubbles 18.
- Shadows: soft, low-opacity (already tokenized). Buttons: pill, 44px min height.
- Motion: 150/250/450ms; all entrance animation gated behind `prefers-reduced-motion`.
- Icons: inline SVG (web `features/landing/icons.tsx` pattern), Material icons (mobile).

## Mobile parity (Flutter)

Mobile has Chat, Voice, Nearby, Settings (bottom nav) + Onboarding; **no admin**. Match the
new chat bubble design (sent=primary right, received=surface-2 left with avatar, 18px radii,
time + status meta, animated typing dots), the composer (rounded field + circular send FAB),
the voice panel (waveform + big mic), onboarding (rounded cards, pill buttons), and settings
(grouped cards). Update `mobile/lib/core/theme.dart` to the unified palette above
(remember the one hardcoded `Colors.white` at `features/voice/live_voice_page.dart:171`).
