# DESIGN.md

Design language for HomeBandhu, reverse-engineered from the current UI (`frontend/src/`). No design tool/Figma source of truth exists — this file *is* the source of truth. Follow it when adding new pages or components so the app doesn't drift into a second visual language.

## Principles

- **Soft, quiet SaaS look.** White cards floating on a pale slate canvas, thin 1px borders instead of heavy dividers, shadows used sparingly for elevation, not decoration.
- **Indigo does the talking.** One brand color (`indigo-600`) for every primary action, active nav state, and focus ring. Everything else is neutral or semantic.
- **Small, loud labels; big, quiet values.** Overline-style uppercase micro-labels (10–11px, bold, tracked-out, muted) sit above large bold numbers/headings. This pairing is the most repeated motif in the app.
- **Rounded everywhere, consistently graduated.** Corner radius scales with element size (see Radius table) — never mix an `xl` button inside an `lg` card.
- **No unstyled native controls.** Every input/select/textarea is re-skinned the same way; nothing uses browser-default chrome.

## Typography

- **Font:** Plus Jakarta Sans (Google Fonts import in `index.css`), fallback to system sans. Set once via `@theme { --font-sans }`, applied on `body`.
- **Weights:** `font-bold` and `font-semibold` dominate; `font-extrabold` for headings and big stat numbers. Body copy is almost never `font-normal` — this UI has no light/regular text, everything is at least medium-weight.
- **Scale in practice:**
  - Page titles: `text-2xl` / `text-3xl font-extrabold tracking-tight`
  - Card/section headings: `text-base font-extrabold`
  - Body/labels: `text-sm` / `text-xs`
  - Micro-labels (badges, overlines, timestamps): `text-[10px]`–`text-[11px]`, always paired with `font-bold`/`font-extrabold uppercase tracking-wider`
- **Muted text color:** `text-slate-400` for secondary copy, timestamps, placeholders — used constantly instead of a lighter font-weight.

## Color

Tailwind v4 defaults, no custom palette — the language comes from *which* shades are reused, not new tokens.

| Role | Shades | Where |
|---|---|---|
| Brand / primary action | `indigo-500/600/700` | primary buttons, active nav, links, focus ring, logo mark |
| Neutral surface | `white`, `slate-50` | cards on `white`, page canvas on `slate-50` |
| Neutral text/border | `slate-400` (muted), `slate-600/700/800/900` (body→heading), `slate-100/200` (borders) | everywhere |
| Success | `emerald-50/600/700` | resolved status, checked-in, confirmed |
| Danger | `rose-50/600/700/800` | errors, complaints, reject/logout hover |
| Warning | `amber-50/600/700` | medium urgency, dues, "switch to admin" button |
| Info | `blue-50/700` | low-urgency notices, "in progress" status |

Pattern for status/semantic color: **pastel tint background + saturated-600/700 text**, e.g. `bg-emerald-50 text-emerald-700`, `bg-rose-50 text-rose-800`. Never solid saturated background with dark text except the indigo primary button and the indigo "maintenance due" hero banner.

Colored shadows follow the surface color: `shadow-md shadow-indigo-100` on indigo elements, `shadow-emerald-100` on emerald banners, etc. — shadow tint always matches the element's own hue family, at a pale (`50`/`100`) shade.

> Note: a handful of odd intermediate shades appear (`indigo-650`, `slate-450`, `rose-750`, etc.). Treat these as ad-hoc fine-tuning by whoever wrote that component, not intentional tokens — round to the nearest standard Tailwind step (`50/100/200/300/400/500/600/700/800/900`) for new work.

## Spacing & Layout

- Page content wrapped in `max-w-7xl mx-auto`, padded `p-6`.
- Card interiors: `p-5` (compact stat cards) or `p-6` (content cards).
- Vertical rhythm inside a card: `space-y-4` (forms), `space-y-6` (page sections), `space-y-1` (label+value pairs).
- Grids: 4-up stat/quick-action rows (`grid-cols-2 md:grid-cols-4 gap-4`), 12-col main content split (`lg:col-span-8` + `lg:col-span-4`).
- List rows inside a card use `divide-y divide-slate-50` rather than individual borders.

## Radius

Strict size→radius correlation — reuse this table rather than picking arbitrarily:

| Element | Radius |
|---|---|
| Modal, big hero card | `rounded-3xl` |
| Standard card, stat tile, banner | `rounded-2xl` |
| Button, input, select, textarea, nav item, small card | `rounded-xl` |
| Small icon chip, list-row icon box | `rounded-lg` |
| Avatar, icon badge, pill/status badge, progress bar | `rounded-full` |

## Elevation

- `shadow-sm` — resting state for minor chrome (date pill, footer button).
- `shadow-md shadow-{color}-100` — default for primary buttons and active/brand elements. Always pair a colored shadow with its matching background color.
- `shadow-lg` / `hover:shadow-lg` — hover lift on interactive cards (quick-action tiles).
- `shadow-xl shadow-slate-100` — big modal/auth-card elevation.
- Plain cards at rest use **border only** (`border border-slate-100`), no shadow — shadow is reserved for emphasis or hover, not baseline state.

## Components

**Primary button**
```
bg-indigo-600 hover:bg-indigo-700 text-white font-bold
py-3 px-4 rounded-xl transition-all shadow-md shadow-indigo-100
```
Disabled state: swap to `bg-slate-300 cursor-not-allowed shadow-none` (never a lighter indigo).

**Secondary / outline button**
```
border border-slate-100 hover:bg-slate-50 text-slate-600
font-bold rounded-xl transition-all
```
Destructive-hover variant swaps hover to `hover:bg-rose-50 hover:text-rose-600 hover:border-rose-100` (used for logout).

**Text input / select / textarea**
```
bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5(–3) text-sm
text-slate-700 placeholder:text-slate-400 font-medium
focus:outline-none focus:border-indigo-500 focus:bg-white transition-all
```
Leading icon: `absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4`, input gets `pl-10`. Label above every field: `text-[10–11px] font-bold text-slate-500 uppercase tracking-wider`.

**Card**
```
bg-white border border-slate-100 rounded-2xl p-6
```
(`rounded-3xl` + `p-8`/no border-only-shadow variant for modals/auth cards.)

**Stat tile**
Overline label (colored, uppercase, extrabold, 10px) → big `text-2xl font-extrabold text-slate-800` value → muted one-line caption, with a `rounded-full` icon chip (`bg-{color}-50 text-{color}-600`) pinned to the side.

**Status / urgency badge**
```
text-[10px] font-extrabold px-2.5 py-1 rounded-full
bg-{semantic}-50 text-{semantic}-700 [border border-{semantic}-100]
```

**Modal**
```
fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[999]
  flex items-center justify-center p-4
```
Panel: `bg-white rounded-3xl border border-slate-100 max-w-md w-full p-6 space-y-6 animate-slide-up`. Header row is title (`text-lg font-extrabold`) + a plain-text "Cancel" button, not an X icon.

**Sidebar nav item**
```
flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all
# active:
bg-indigo-600 text-white shadow-md shadow-indigo-100
# inactive:
text-slate-600 hover:bg-slate-50 hover:text-slate-800
```

**Progress bar**
`bg-slate-200 h-1.5 rounded-full overflow-hidden` track, `bg-indigo-600 h-full rounded-full transition-all duration-500` fill.

## Motion

- Two custom keyframe utilities in `index.css`: `.animate-slide-up` (12px translateY + fade, 0.3s, `cubic-bezier(0.16,1,0.3,1)`) for modals and the login card; `.animate-fade-in` (0.2s ease-out) for route/page transitions and overlay scrims.
- Interactive elements use `transition-all` by default; use the narrower `transition-colors` / `transition-transform` only when just one property changes (e.g. icon `group-hover:scale-105`).
- Sidebar slide uses plain Tailwind `transition-transform duration-300 ease-in-out` with a `-translate-x-full` ↔ `translate-x-0` toggle — no custom keyframe needed for that one.

## Icons

`lucide-react` exclusively. Sizing convention: `w-4 h-4` inline/small, `w-5 h-5` nav and section headers, `w-8`–`w-10` square icon chips. Icon chips are `rounded-lg` (small, sidebar) or `rounded-xl`/`rounded-full` (dashboard tiles/badges) with `bg-{color}-50 text-{color}-600`.

## Layout shells

Three portal shells — `ResidentLayout`, `SecurityLayout`, and `AdminLayout` —
share the same visual contract: fixed `w-64` white sidebar (`border-r
border-slate-100`) with a top brand block, middle navigation, bottom logout or
role-switch controls; a `Header` bar; and `<Outlet>` content padded and
centered at `max-w-7xl`. The sidebar collapses to an overlay drawer below `lg`,
toggled by a hamburger in `Header`. Portal-specific data is hydrated by the
non-visual `DashboardDataBootstrap` component; see `ARCHITECTURE.md` for its
data-flow boundary rather than duplicating it in the visual design system.

## When extending this system

1. Reuse the tables above instead of eyeballing a new radius/shadow/shade.
2. New semantic states get a pastel-bg + 700-text pair from the existing five families (indigo/slate/emerald/rose/amber[/blue]) — don't introduce a new hue without a reason.
3. Successful mutating actions should use the existing toast + activity-feed
   conventions rather than new ad-hoc notification patterns. A mutation must
   be backend-backed before it is presented as durable state.
4. If a component needs to be reused 3+ times, promote it into `components/common/` (currently sparse: only `ToastContainer`) instead of re-copying the class strings.
