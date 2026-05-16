# HUST Assistant — Design System

> **Scope**: Web chatbot frontend (`chat-companion`).
> **Stack**: Vite + React 18 + TypeScript + Tailwind CSS 3 + shadcn/ui + Radix UI.
> **Font**: [Inter](https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap) via Google Fonts.

---

## 1. Visual Theme & Atmosphere

| Attribute | Description |
|-----------|-------------|
| **Mood** | Professional, clean, trustworthy — an academic assistant |
| **Density** | Medium density; generous whitespace in chat, compact sidebar |
| **Philosophy** | *Content-first*. The UI disappears so the conversation shines |
| **Mode** | Dual-mode: Light (default) + Dark (`.dark` class toggle) |
| **Motion** | Subtle & purposeful — fade-in messages, shimmer skeleton, typing dots |
| **Iconography** | Lucide React (`lucide-react`) — thin stroke, rounded caps |

**Design pillars**:
1. **Clarity** — High contrast text, clear hierarchy, no visual noise.
2. **Trust** — Academic blue primary, clean card surfaces, source citations.
3. **Responsiveness** — Sidebar collapses to sheet on mobile; fluid chat bubbles.
4. **Future-ready** — Token-based design system maps 1:1 to React Native (NativeWind) for mobile expansion.

---

## 2. Color Palette & Roles

All colors are defined as HSL CSS custom properties in `index.css` and consumed via `tailwind.config.ts`.

### 2.1 Light Mode (`:root`)

| Semantic Name | HSL Value | Hex (approx) | Role |
|---------------|-----------|---------------|------|
| `--background` | `0 0% 98%` | `#FAFAFA` | Page background |
| `--foreground` | `220 14% 10%` | `#161A1F` | Primary text |
| `--card` | `0 0% 100%` | `#FFFFFF` | Card / panel surface |
| `--card-foreground` | `220 14% 10%` | `#161A1F` | Text on cards |
| `--primary` | `217 91% 60%` | `#3B82F6` | Brand blue — buttons, links, accents |
| `--primary-foreground` | `0 0% 100%` | `#FFFFFF` | Text on primary surfaces |
| `--secondary` | `220 14% 96%` | `#F3F4F6` | Secondary fills, hover states |
| `--secondary-foreground` | `220 14% 10%` | `#161A1F` | Text on secondary |
| `--muted` | `220 14% 96%` | `#F3F4F6` | Disabled / muted backgrounds |
| `--muted-foreground` | `220 9% 46%` | `#6B7280` | Secondary text, timestamps |
| `--accent` | `217 91% 60%` | `#3B82F6` | Same as primary (accent = primary) |
| `--destructive` | `0 84% 60%` | `#EF4444` | Errors, delete actions |
| `--border` | `220 13% 91%` | `#E5E7EB` | Dividers, card borders |
| `--input` | `220 13% 91%` | `#E5E7EB` | Input field borders |
| `--ring` | `217 91% 60%` | `#3B82F6` | Focus ring |
| `--radius` | `0.75rem` | — | Base border-radius (12px) |

#### Chat-specific tokens (Light)

| Token | HSL | Hex | Role |
|-------|-----|-----|------|
| `--chat-user-bg` | `217 91% 97%` | `#EFF6FF` | User message bubble |
| `--chat-assistant-bg` | `0 0% 100%` | `#FFFFFF` | Assistant message bubble |
| `--chat-input-bg` | `0 0% 100%` | `#FFFFFF` | Input area background |
| `--chat-container-bg` | `220 14% 96%` | `#F3F4F6` | Chat area canvas |

#### Sidebar tokens (Light)

| Token | HSL | Role |
|-------|-----|------|
| `--sidebar-background` | `0 0% 98%` | Sidebar bg |
| `--sidebar-foreground` | `240 5.3% 26.1%` | Sidebar text |
| `--sidebar-primary` | `240 5.9% 10%` | Sidebar active item |
| `--sidebar-accent` | `240 4.8% 95.9%` | Sidebar hover |
| `--sidebar-border` | `220 13% 91%` | Sidebar dividers |

### 2.2 Dark Mode (`.dark`)

| Semantic Name | HSL Value | Hex (approx) | Δ from Light |
|---------------|-----------|---------------|--------------|
| `--background` | `224 14% 10%` | `#171B22` | Deep navy |
| `--foreground` | `0 0% 98%` | `#FAFAFA` | Light text |
| `--card` | `224 14% 12%` | `#1C2028` | Elevated surface |
| `--primary` | `217 91% 60%` | `#3B82F6` | Unchanged |
| `--secondary` | `224 14% 16%` | `#252A33` | Dark fill |
| `--muted` | `224 14% 16%` | `#252A33` | Dark muted |
| `--muted-foreground` | `220 9% 60%` | `#9CA3AF` | Brighter than light |
| `--destructive` | `0 62% 30%` | `#7A1D1D` | Muted red |
| `--border` | `224 14% 20%` | `#2D333D` | Subtle border |
| `--chat-user-bg` | `217 50% 20%` | `#1E3A5F` | Dark blue bubble |
| `--chat-assistant-bg` | `224 14% 14%` | `#1F242B` | Dark card bubble |
| `--chat-container-bg` | `224 14% 10%` | `#171B22` | Same as bg |

### 2.3 Semantic Debug Colors (inline in ChatMessage)

| Color | Usage |
|-------|-------|
| `emerald-500/10` | Mode badge |
| `sky-500/10` | Iteration count |
| `amber-500/10` | Latency / timing |
| `indigo-500/10` | Tool badges |
| `cyan-500/10` | Routing probabilities |
| `fuchsia-500/10` | Collection hit counts |

---

## 3. Typography Rules

### 3.1 Font Stack

```
font-family: 'Inter', system-ui, sans-serif;
```

Loaded via Google Fonts: weights **400** (Regular), **500** (Medium), **600** (SemiBold). `antialiased` rendering enabled.

### 3.2 Type Scale

| Element | Class / Size | Weight | Usage |
|---------|-------------|--------|-------|
| Page title (hero) | `text-4xl` → `sm:text-5xl` → `md:text-6xl` | `font-bold` | Landing page heading |
| Page heading | `text-2xl` – `text-3xl` | `font-bold` | Section titles, auth page titles |
| App header | `text-base` → `sm:text-lg` | `font-semibold` | "HUST Assistant" top bar |
| Chat greeting | `text-lg` | `font-semibold` | Empty state heading |
| Card title | `text-base` | `font-semibold` | Feature cards, source titles |
| Body / message | `text-sm` (`14px`) | `font-normal` | Chat messages, form labels |
| Small / meta | `text-xs` (`12px`) | `font-medium` | Badges, timestamps, sidebar items |
| Tiny / debug | `text-[10px]` – `text-[11px]` | `font-normal` | Debug info, source rank |
| Brand label | `text-xs uppercase tracking-widest` | `font-medium` | "HUST ASSISTANT" above auth titles |
| Hint text | `text-xs` | `font-normal` | "Nhấn Enter để gửi..." |

### 3.3 Markdown Prose (Chat Messages)

Applied via `.prose .prose-sm` + custom `markdownComponents`:

| Element | Style |
|---------|-------|
| `<p>` | `mb-2 last:mb-0` |
| `<ul>` | `ml-4 list-disc space-y-1` |
| `<ol>` | `ml-4 list-decimal space-y-1` |
| `<strong>` | `font-semibold text-foreground` |
| `<code>` (inline) | `bg-muted px-1 py-0.5 rounded text-xs` |
| `<pre>` | `bg-muted p-2 rounded my-2 overflow-x-auto text-xs` |
| `<blockquote>` | `border-l-4 border-primary pl-3 italic` |
| `<a>` | `text-primary hover:underline` — opens `target="_blank"` |
| `<h1>` | `text-lg font-bold mb-2 mt-3` |
| `<h2>` | `text-base font-bold mb-2 mt-3` |
| `<h3>` | `text-sm font-bold mb-1 mt-2` |

---

## 4. Component Stylings

### 4.1 Buttons

**Component**: `components/ui/button.tsx` — CVA-based variants.

| Variant | Appearance | Usage |
|---------|-----------|-------|
| `default` | `bg-primary text-white hover:bg-primary/90` | Primary CTA — "Đăng nhập", "Get Started", Send |
| `destructive` | `bg-destructive text-white` | Delete actions |
| `outline` | `border border-input bg-background hover:bg-accent` | OAuth buttons, secondary actions |
| `secondary` | `bg-secondary text-secondary-foreground` | Low-emphasis actions |
| `ghost` | `hover:bg-accent` | Icon buttons, toolbar items |
| `link` | `text-primary underline-offset-4 hover:underline` | Inline links |

| Size | Dimensions |
|------|-----------|
| `default` | `h-10 px-4 py-2` |
| `sm` | `h-9 px-3` |
| `lg` | `h-11 px-8` |
| `icon` | `h-10 w-10` |

**Send button** (ChatInput): `h-10 w-10 rounded-xl hover:scale-105 disabled:opacity-40`.

**Sidebar "New Chat"**: Full-width `bg-primary text-primary-foreground rounded-lg px-3 py-2`.

### 4.2 Cards

**Component**: `components/ui/card.tsx`.

- Base: `rounded-lg border bg-card text-card-foreground shadow-sm`
- Header: `p-6`, Footer: `p-6 pt-0`, Content: `p-6 pt-0`
- **Feature cards** (Landing): `rounded-xl border bg-card p-6 shadow-sm hover:shadow-md transition-shadow`
- **Auth cards**: `rounded-2xl border bg-card p-8 shadow-sm max-w-sm`
- **Source cards** (Chat): `rounded-lg border bg-background/80 p-3`

### 4.3 Inputs

**Component**: `components/ui/input.tsx`.

- Base: `h-10 rounded-md border border-input bg-background px-3 py-2 text-base md:text-sm`
- Focus: `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`
- Error: `border-destructive focus-visible:ring-destructive`
- Disabled: `cursor-not-allowed opacity-50`

**Chat textarea** (ChatInput):
- Container: `rounded-2xl border bg-chat-input p-2 shadow-lg focus-within:shadow-xl focus-within:ring-2 focus-within:ring-ring/20`
- Textarea: `min-h-[44px] max-h-[120px] resize-none bg-transparent text-sm`

### 4.4 Badges

**Component**: `components/ui/badge.tsx`.

- Base: `rounded-full border px-2.5 py-0.5 text-xs font-semibold`
- `default`: `bg-primary text-primary-foreground`
- `secondary`: `bg-secondary text-secondary-foreground`
- `destructive`: `bg-destructive text-destructive-foreground`
- `outline`: `text-foreground` (border only)

### 4.5 Chat Bubbles

| Role | Style |
|------|-------|
| User | `rounded-2xl rounded-tr-sm bg-chat-user shadow-sm` — right-aligned |
| Assistant | `rounded-2xl rounded-tl-sm bg-chat-assistant border border-border shadow-sm` — left-aligned |
| Width | `max-w-[92%]` → `sm:max-w-[85%]` → `md:max-w-[75%]` |
| Padding | `px-3 py-3` → `sm:px-4` |

**Avatars**: `h-8 w-8 rounded-full` — User: `bg-secondary`, Assistant: `bg-primary`.

### 4.6 Navigation / Sidebar

- Sidebar width: Desktop `16rem`, Mobile `18rem`, Icon-collapsed `3rem`
- Collapsible mode: `offcanvas` — slides off-screen
- Mobile: renders as a `Sheet` (bottom-sheet overlay)
- Keyboard shortcut: `Ctrl+B` / `⌘B`
- Menu item active: `bg-sidebar-accent font-medium text-sidebar-accent-foreground`
- Hover: `hover:bg-sidebar-accent`

### 4.7 Typing Indicator

- **Thinking phase**: Skeleton shimmer bars (`w-48`), avatar pulses
- **Streaming phase**: 3 bouncing dots (`h-2 w-2 rounded-full bg-muted-foreground`)
- Animation: `typing-dot` keyframe — 1.4s infinite, staggered 0.2s

### 4.8 Animations

| Animation | Duration | Easing | Usage |
|-----------|----------|--------|-------|
| `fade-in` | `0.3s` | `ease-out` | Message entrance (`translateY(10px)→0`) |
| `accordion-down/up` | `0.2s` | `ease-out` | Collapsible sections |
| `shimmer` | `2s` | `linear infinite` | Skeleton loading |
| `thinking-pulse` | `2s` | `cubic-bezier(0.4,0,0.6,1)` | Avatar pulse while thinking |
| `typing-dot` | `1.4s` | `ease-in-out infinite` | Dot bounce |
| `hover:scale-105` | CSS transition | — | Send button hover |

---

## 5. Layout Principles

### 5.1 Spacing Scale (Tailwind default)

| Token | Value | Common Usage |
|-------|-------|-------------|
| `0.5` | `2px` | Tiny gaps |
| `1` | `4px` | Icon gaps |
| `1.5` | `6px` | Label-to-input gap |
| `2` | `8px` | Sidebar item padding, input inner padding |
| `3` | `12px` | Chat area padding (mobile), card padding (compact) |
| `4` | `16px` | Chat area padding (sm), section gaps |
| `6` | `24px` | Chat area padding (md), card padding (p-6) |
| `8` | `32px` | Auth card padding (p-8), hero section |
| `14` | `56px` | Header height (h-14) |

### 5.2 Layout Structure

```
┌─────────────────────────────────────────────┐
│ SidebarProvider  (flex h-screen w-full)      │
│ ┌──────────┐ ┌────────────────────────────┐ │
│ │ Sidebar  │ │ Main (flex-1 flex-col)     │ │
│ │ 16rem    │ │ ┌────────────────────────┐ │ │
│ │          │ │ │ Header (h-14, border-b)│ │ │
│ │ ┌──────┐ │ │ ├────────────────────────┤ │ │
│ │ │NewChat│ │ │ │ ChatContainer (flex-1)│ │ │
│ │ ├──────┤ │ │ │  ┌──────────────────┐ │ │ │
│ │ │List  │ │ │ │  │ Messages (max-w- │ │ │ │
│ │ │      │ │ │ │  │ 3xl, centered)   │ │ │ │
│ │ │      │ │ │ │  └──────────────────┘ │ │ │
│ │ ├──────┤ │ │ ├────────────────────────┤ │ │
│ │ │Logout│ │ │ │ Input (border-t,       │ │ │
│ │ └──────┘ │ │ │ max-w-3xl, centered)   │ │ │
│ └──────────┘ │ └────────────────────────┘ │ │
│              └────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 5.3 Content Width

| Context | Max Width | Centering |
|---------|-----------|-----------|
| Chat messages | `max-w-3xl` (`48rem`) | `mx-auto` |
| Chat input | `max-w-3xl` | `mx-auto` |
| Landing content | `max-w-6xl` (`72rem`) | `mx-auto` |
| Hero text | `max-w-3xl` | `mx-auto` |
| Auth forms | `max-w-sm` (`24rem`) | `mx-auto` centered page |
| Container (Tailwind) | `1400px` at `2xl` | `center`, `padding: 2rem` |

### 5.4 Whitespace Philosophy

- **Chat area**: Generous vertical spacing (`space-y-4`) between messages.
- **Sidebar**: Compact (`gap-0.5` – `gap-1`) — scannable list.
- **Auth pages**: Large margins (`mb-8` header, `gap-4` fields) — calm, focused forms.
- **Landing**: Spacious sections (`py-20` – `py-36`) — premium feel.

---

## 6. Depth & Elevation

### 6.1 Shadow System

| Level | Class | Usage |
|-------|-------|-------|
| 0 (flat) | None | Backgrounds, sidebar |
| 1 (subtle) | `shadow-sm` | Cards, chat bubbles, feature cards |
| 2 (medium) | `shadow-md` | Feature card hover |
| 3 (elevated) | `shadow-lg` | Chat input, dropdown menus, user menu |
| 4 (floating) | `shadow-xl` | Chat input focus state |

### 6.2 Surface Hierarchy

```
Layer 0  ─  Page background    (--background)
Layer 1  ─  Chat container     (--chat-container-bg)
Layer 2  ─  Cards / Bubbles    (--card / --chat-assistant-bg)
Layer 3  ─  Input area         (--chat-input-bg + shadow-lg)
Layer 4  ─  Overlays           (Sheet, Dropdown — bg-card + shadow-lg)
```

### 6.3 Backdrop Effects

- Header: `bg-background/80 backdrop-blur-sm` — frosted glass
- Input area: `bg-background/90 backdrop-blur-sm`
- Scroll-to-bottom button: `bg-background/80 backdrop-blur`
- Landing navbar: `bg-background/80 backdrop-blur-sm`

### 6.4 Borders

- Default: `border border-border` (`1px solid`)
- Separator: `border-t border-border`
- Sidebar: `border-r` (desktop left sidebar)
- Blockquote: `border-l-4 border-primary`

---

## 7. Do's and Don'ts

### ✅ Do's

| Rule | Reason |
|------|--------|
| Use semantic color tokens (`bg-primary`, `text-foreground`) | Dark mode works automatically |
| Keep chat bubbles ≤ 75% width on desktop | Prevents wall-of-text feel |
| Use `Inter` font exclusively | Brand consistency |
| Use `rounded-2xl` for chat elements, `rounded-lg`/`rounded-xl` for cards | Visual cohesion |
| Animate message entrance with `animate-fade-in` | Smooth conversation flow |
| Show source count badge on assistant messages | Builds user trust |
| Use `text-sm` (14px) for body content | Optimal readability |
| Use HSL CSS variables for all colors | Single source of truth |
| Use Lucide icons with consistent stroke width | Visual harmony |
| Test both light and dark modes | Users expect theme parity |

### ❌ Don'ts

| Anti-pattern | Why |
|-------------|-----|
| Don't use raw hex colors in components | Breaks dark mode, creates inconsistency |
| Don't make bubbles full-width | Destroys chat feel, hard to scan |
| Don't add heavy drop shadows to chat bubbles | Clutters the conversation |
| Don't use more than 2 font weights in one view | Over-complicated hierarchy |
| Don't auto-play sound or intrusive animations | Academic tool, not a game |
| Don't put critical info only in color | Use icons + text labels together (a11y) |
| Don't nest interactive elements (button in button) | Accessibility violation |
| Don't override shadcn/ui primitives with inline styles | Use CVA variants or className extension |
| Don't use `!important` | Tailwind utility order handles specificity |
| Don't add new colors without defining CSS variables | Keep the token system intact |

---

## 8. Responsive Behavior

### 8.1 Breakpoints

| Breakpoint | Width | Behavior |
|------------|-------|----------|
| Base (mobile) | `< 768px` | Sidebar hidden → Sheet overlay; single-column |
| `sm` | `≥ 640px` | Slightly larger padding, hero buttons row |
| `md` | `≥ 768px` | Sidebar visible (desktop); chat bubble max-width 75% |
| `lg` | `≥ 1024px` | Feature grid 3-column |
| `2xl` | `≥ 1400px` | Max container width cap |

**Mobile detection**: `useIsMobile()` hook — `window.matchMedia('(max-width: 767px)')`.

### 8.2 Touch Targets

| Element | Min Size | Notes |
|---------|----------|-------|
| Send button | `h-10 w-10` (40×40px) | Meets 44px with padding |
| Sidebar menu items | `h-auto, min py-2 px-3` | ~36px+ height |
| Mobile sidebar action | `after:absolute after:-inset-2` | Invisible 8px hit area expansion |
| Chat input textarea | `min-h-[44px]` | Apple HIG minimum |

### 8.3 Collapsing Strategy

| Component | Desktop (≥768px) | Mobile (<768px) |
|-----------|------------------|-----------------|
| Sidebar | Fixed left panel, `16rem` | Hidden; opens as `Sheet` overlay (`18rem`) |
| Header | Full bar with status text | Compact; "Đang hoạt động" text hidden |
| Chat bubbles | `max-w-[75%]` | `max-w-[92%]` |
| Chat padding | `p-6` | `p-3` |
| Landing features | 3-column grid | 1-column stack |
| Hero buttons | Side-by-side row | Full-width stack |

### 8.4 Mobile-First Future (from MOBILE_APP_DESIGN.md)

The design system maps to React Native via NativeWind:
- Bottom tab navigation: 🏠 Chat, 📚 Lookup, 🔖 Bookmarks, 🔔 Notifications, 👤 Profile
- New screens to plan for: Bookmark folders, Notification list, Quick Lookup, Regulation browser
- SSE streaming → typing indicator reuse
- Same color tokens via NativeWind `tailwind.config.ts`

---

## 9. Agent Prompt Guide

### 9.1 Quick Color Reference

```css
/* Primary actions */
--primary:     hsl(217 91% 60%)    /* #3B82F6 — Blue */
--destructive: hsl(0 84% 60%)      /* #EF4444 — Red  */

/* Surfaces (Light) */
--background:  hsl(0 0% 98%)       /* #FAFAFA */
--card:        hsl(0 0% 100%)      /* #FFFFFF */
--secondary:   hsl(220 14% 96%)    /* #F3F4F6 */

/* Surfaces (Dark) */
--background:  hsl(224 14% 10%)    /* #171B22 */
--card:        hsl(224 14% 12%)    /* #1C2028 */

/* Text */
--foreground:       light=#161A1F  dark=#FAFAFA
--muted-foreground: light=#6B7280  dark=#9CA3AF

/* Chat */
--chat-user-bg:      light=#EFF6FF  dark=#1E3A5F
--chat-assistant-bg: light=#FFFFFF  dark=#1F242B
```

### 9.2 Ready-to-Use Prompts

**When adding a new page:**
> Use `bg-background` for the page. Wrap content in `mx-auto max-w-3xl` (or `max-w-6xl` for wide layouts). Use `font-sans` (Inter). All text uses `text-foreground` / `text-muted-foreground`. Cards use `rounded-xl border border-border bg-card p-6 shadow-sm`.

**When adding a new chat feature (e.g., Bookmarks, Feedback):**
> Follow the existing chat bubble pattern: assistant messages use `bg-chat-assistant rounded-2xl rounded-tl-sm border border-border`. Actions appear below the message content. Use `text-xs text-primary font-medium` for clickable action links. Icons from `lucide-react`, size `h-3.5 w-3.5`.

**When adding a new form:**
> Use the auth page pattern: `max-w-sm rounded-2xl border bg-card p-8`. Labels are `text-sm font-medium text-foreground`. Inputs use the shadcn `<Input>` component. Errors: `text-xs text-destructive`. Submit button: `<Button className="mt-1 w-full font-semibold">`.

**When adding a sidebar section:**
> Use `<SidebarMenu>` + `<SidebarMenuItem>` + `<SidebarMenuButton>`. Active state via `isActive` prop. Text `text-sm`, subtitle `text-[10px] text-muted-foreground`.

**When styling for mobile:**
> Breakpoint is `768px`. Use `p-3` base → `sm:p-4` → `md:p-6`. Hide non-essential text at mobile with `hidden sm:inline`. Chat bubble width: `max-w-[92%]` → `sm:max-w-[85%]` → `md:max-w-[75%]`.

**When adding a notification/badge feature (future mobile parity):**
> Badge: `<Badge variant="secondary">` for neutral, `<Badge variant="default">` for counts. Notification dot: `h-2 w-2 rounded-full bg-primary` (or `bg-destructive` for unread). Follow the bottom-tab pattern from MOBILE_APP_DESIGN.md for navigation.
