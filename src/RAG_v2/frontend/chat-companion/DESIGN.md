# Trợ Lý Học Vụ Bách Khoa — Design System

> **Scope**: Web chatbot frontend (`chat-companion`).
> **Stack**: Vite + React 18 + TypeScript + Tailwind CSS 3 + shadcn/ui + Radix UI.
> **Font**: [Inter](https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap) via Google Fonts.

---

## 1. Visual Theme & Atmosphere

| Attribute | Description |
|-----------|-------------|
| **Mood** | Professional, authoritative, academic, warm. |
| **Density** | Medium density; generous whitespace in chat, compact sidebar |
| **Philosophy** | *Brand-aligned*. UI reflects the prestige of HUST with modern Web3/AI aesthetics. |
| **Mode** | Dual-mode: Light (default) + Dark (`.dark` class toggle) |
| **Brand Focus** | Official HUST identity: Crimson Red (`#C22727`) and Gold (`#F5A623`) |
| **Iconography** | Lucide React (`lucide-react`) — thin stroke, rounded caps |

**Design pillars**:
1. **Brand Identity** — Strong HUST red/gold integration via semantic CSS variables.
2. **Warmth & Clarity** — High contrast text, warm background tints, clear hierarchy.
3. **Responsiveness** — Sidebar collapses to sheet on mobile; fluid chat bubbles.
4. **Future-ready** — Token-based design system maps 1:1 to React Native for mobile expansion.

---

## 2. Color Palette & Roles

All colors are defined as HSL CSS custom properties in `index.css` and consumed via `tailwind.config.ts`.

### 2.1 HUST Brand Tokens (Base Colors)

| Token | HSL | Role |
|-------|-----|------|
| `--hust-red` | `0 72% 46%` | Primary brand color, actions |
| `--hust-red-dark` | `0 70% 32%` | Deep red for sidebar/footer |
| `--hust-gold` | `38 91% 55%` | Secondary brand color, accents |
| `--hust-brown` | `25 45% 16%` | Deep brown/red for contrast |

### 2.2 Light Mode (`:root`)

| Semantic Name | HSL Value | Role |
|---------------|-----------|------|
| `--background` | `30 20% 98%` | Warm white page background |
| `--foreground` | `20 15% 12%` | Dark brown/gray text |
| `--card` | `0 0% 100%` | Pure white card surface |
| `--primary` | `0 72% 46%` | **HUST Red** — buttons, active states |
| `--accent` | `38 91% 55%` | **HUST Gold** — accent lines, highlights |
| `--secondary` | `30 15% 95%` | Light warm gray fills |
| `--muted` | `30 12% 95%` | Muted backgrounds |
| `--ring` | `0 72% 46%` | Focus ring (HUST Red) |

#### Chat-specific tokens (Light)
| Token | HSL | Role |
|-------|-----|------|
| `--chat-user-bg` | `0 50% 96%` | Warm red-tinted user bubble |
| `--chat-assistant-bg` | `0 0% 100%` | White assistant bubble |
| `--chat-container-bg` | `30 15% 96%` | Chat area canvas |

#### Sidebar tokens (Light/Dark Shared)
*The sidebar uses a dark-theme by default even in light mode to anchor the brand.*

| Token | HSL | Role |
|-------|-----|------|
| `--sidebar-background` | `0 45% 16%` | Dark crimson background |
| `--sidebar-foreground` | `30 20% 92%` | Light text |
| `--sidebar-primary` | `38 91% 55%` | Gold active item |
| `--sidebar-accent` | `0 40% 22%` | Darker red hover state |
| `--sidebar-border` | `0 30% 24%` | Subtle dark red dividers |

### 2.3 Dark Mode (`.dark`)

| Semantic Name | HSL Value | Δ from Light |
|---------------|-----------|--------------|
| `--background` | `0 12% 8%` | Very dark warm gray |
| `--foreground` | `30 15% 96%` | Light text |
| `--card` | `0 12% 11%` | Elevated dark surface |
| `--primary` | `0 68% 52%` | Brighter HUST Red |
| `--accent` | `38 85% 50%` | Deep Gold |
| `--chat-user-bg` | `0 45% 18%` | Dark red user bubble |
| `--chat-assistant-bg` | `0 12% 13%` | Dark card bubble |

---

## 3. Typography Rules

### 3.1 Font Stack
```css
font-family: 'Inter', system-ui, sans-serif;
```
Loaded via Google Fonts: weights **400**, **500**, **600**, **700**.

### 3.2 Type Scale

| Element | Class / Size | Usage |
|---------|-------------|-------|
| Hero Title | `text-4xl sm:text-5xl md:text-6xl` | Landing page heading |
| Heading | `text-2xl font-bold` | Auth page titles |
| Header Brand | `text-lg font-semibold text-white` | "ĐHBK Hà Nội" top bar |
| Body | `text-sm font-normal` | Chat messages, labels |
| Meta/Small | `text-xs text-muted-foreground` | Timestamps, debug info |
| Brand Label | `text-xs uppercase tracking-widest`| "ĐẠI HỌC BÁCH KHOA HÀ NỘI" |

---

## 4. UI Patterns & Components

### 4.1 Gradients
- `.hust-gradient`: Diagonal red-to-gold gradient.
- `.hust-gradient-header`: Horizontal gradient used on Landing Page navbar (`vàng` → `cam` → `đỏ`).

### 4.2 Brand Accents
- **Auth Cards**: `w-full max-w-sm overflow-hidden rounded-2xl` with a gold top stripe: `<div className="h-1 w-full bg-accent"></div>`.
- **Primary Actions**: Red background (`bg-primary`).
- **Sidebar CTA**: Gold background (`bg-accent text-accent-foreground`).

### 4.3 Chat Bubbles
- **User**: Right-aligned, `bg-chat-user`, warm red tint.
- **Assistant**: Left-aligned, `bg-chat-assistant border border-border`, white/dark surface.
- Avatars: `h-8 w-8 rounded-full`.

### 4.4 Logo Component
- `HustLogo.tsx` wraps `/hust-logo.png` with size presets: `sm` (24px), `md` (32px), `lg` (40px), `xl` (64px). Used globally replacing old inline SVGs.

### 4.5 Animations
- `typing-dot`: 3 bouncing dots (1.4s infinite, staggered 0.2s).
- `thinking-pulse`: Avatar pulse for thinking state.
- `skeleton-thinking`: Shimmer animation on assistant bubble.

---

## 5. Layout & Scrolling

- **Full-screen Apps (Chat, Admin)**: Wrapper uses `h-dvh overflow-hidden`. Internal containers use `overflow-y-auto`.
- **Public Pages (Landing, Auth)**: Use `min-h-screen` relying on normal native browser scrolling. Do **NOT** put `overflow: hidden` on `body` or `html`.
- **Mobile Responsive**: Breakpoint is `md` (768px). Chat sidebar becomes a `Sheet`. Layout changes from grid (desktop) to stack (mobile).

---

## 6. Do's and Don'ts

### ✅ Do's
| Rule | Reason |
|------|--------|
| Use semantic color tokens (`bg-primary`, `bg-accent`) | Dark mode works automatically. |
| Use `HustLogo` component | Keeps branding consistent across the app. |
| Use Vietnamese text | Target audience is HUST students. |
| Allow native scrolling on public pages | Better UX for content-heavy pages. |

### ❌ Don'ts
| Anti-pattern | Why |
|-------------|-----|
| Don't use raw hex colors or blue tokens | Breaks the HUST brand identity. |
| Don't add `overflow: hidden` to `body` | Breaks scrolling on Landing/Auth pages. |
| Don't use heavy drop shadows on chat bubbles | Clutters the conversation view. |
