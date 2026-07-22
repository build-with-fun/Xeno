---
name: coding-frontend-ui-ux
description: Master skill for building award-winning websites with premium motion design, micro-interactions, and cutting-edge animations. Comprehensive reference covering design systems, CSS, animation libraries (Motion, GSAP, Lenis, Three.js), 50+ patterns, component library, Next.js 16 architecture, performance, and accessibility. Triggers on motion design, animations, premium UI/UX, or animation library mentions.
---

# Awwwards-Tier UI/UX Master Skill

> One file. Everything. The most comprehensive reference for building
> award-winning websites with Next.js 16, React 19, Motion, GSAP, Lenis, and
> Three.js. Every pattern, every line of code, every gotcha.
>
> **How to use this file:**
> 1. Read Part I (philosophy) — sets the mindset.
> 2. Skim Part II (stack) — pin these versions.
> 3. Jump to the section you need using the table of contents.
> 4. The pattern catalog (Part VII) and component library (Part VIII) are
>    copy-paste ready. The reference sections (Parts IV-VI) explain the "why".
> 5. Before shipping, run the Part XII checklist. Non-negotiable.

## Table of Contents

- Part I — Philosophy: What separates Awwwards-tier from "good"
- Part II — The 2026 verified stack
- Part III — Design system foundations (color, type, spacing, motion)
- Part IV — Complete CSS reference (every modern feature)
- Part V — Animation libraries deep dive (Motion, GSAP, Lenis, R3F, Lottie)
- Part VI — Next.js 16 App Router architecture
- Part VII — Pattern catalog (50+ patterns with full code)
- Part VIII — Full component library (copy-paste ready)
- Part IX — Performance engineering
- Part X — Accessibility deep dive
- Part XI — Page-type recipes
- Part XII — Build, deploy, verify (mandatory pre-ship checklist)
- Part XIII — Anti-patterns catalog
- Part XIV — Easing & timing reference

---

# Part I — Philosophy: What separates Awwwards-tier from "good"

Awwwards Site of the Day is not about adding more animations. It's about
**restraint, intentionality, and execution**. A site with three perfectly-tuned
animations beats a site with thirty sloppy ones every time.

## The 7 principles of premium motion

### 1. Motion must mean something
Every animation answers a question: *what is this teaching the user?* If the
answer is "nothing, it just looks cool," cut it. Motion guides attention
(scroll reveals pace the narrative), confirms actions (button press = scale
down), establishes hierarchy (the magnetic CTA pulls the eye), and signals
state (loading → ready). Decorative motion that doesn't serve one of these
purposes is noise.

### 2. Three signature moments, not thirty
Every Awwwards site has 2-3 interactions that define its character. The rest is
quiet. Pick three moments — e.g., a pinned horizontal gallery, a WebGL shader
hero, a fullscreen menu with staggered text — and nail them. More than five
signature moments kills performance and cohesion. The eye doesn't know where
to land.

### 3. Easing is personality
A site's easing curves ARE its voice. Linear feels robotic. `ease-in-out` feels
corporate. `cubic-bezier(0.16, 1, 0.3, 1)` (expo out) feels confident and
editorial. `cubic-bezier(0.68, -0.55, 0.27, 1.55)` (with anticipation) feels
playful. Pick three site-wide curves, encode them as CSS variables, and use
ONLY those. Mismatched easings across co-occurring animations is the #1 cause
of "feels off but I can't pinpoint why".

### 4. Typography is identity
90% of an Awwwards site's perceived quality is typography. Variable fonts that
animate weight. Editorial serifs paired with technical sans. `text-wrap:
balance` on every heading. Tabular numerals on stats. Proper `font-feature-
settings` (kerning, ligatures, stylistic sets). Type scale built on a modular
ratio (1.25, 1.333, 1.5, 1.618). If your type system is wrong, no amount of
animation saves it.

### 5. Restraint is the signature of confidence
The best sites feel alive because every transition guides attention. They don't
shout. A magnetic button that leans 4px toward the cursor is premium. A button
that leans 20px is gimmicky. A 600ms reveal with expo-out is editorial. A 200ms
reveal with linear is amateur. Slow down. Trust the user to follow.

### 6. Performance is a feature
A janky site cannot feel premium. Frame drops read as "cheap" before the
conscious mind even notices. Hard budgets: First Load JS ≤180KB gzip on the
homepage, frame time ≤8ms during scroll, LCP ≤2s on 4G. Animate `transform`
and `opacity` only. Never `width`, `height`, `top`, `left`, `box-shadow` on hot
paths. Code-split Three.js to routes that need it. These aren't optimizations —
they're the baseline.

### 7. Inclusive motion is premium motion
`prefers-reduced-motion: reduce` users get a fully usable site. Custom cursors
disappear on touch devices. `:focus-visible` outlines stay visible. Sound is
off by default. Skipping accessibility loses you Awwwards nomination points AND
real users. A site that's buttery for 95% of users and broken for 5% is not
premium — it's unfinished.

## The "wow factor" hierarchy

When a user lands on an Awwwards site, here's what registers as "wow", in
descending order of impact:

1. **Smooth scroll** (Lenis) — instant sub-conscious "this is premium"
2. **Custom cursor with hover states** — signature feel
3. **Editorial typography** — type that breathes, balanced line lengths, weight contrast
4. **Scroll-linked reveals** — content paces itself to the user
5. **One pinned/scrubbed showcase** — the "stop scrolling and watch" moment
6. **Page transitions** — no hard cuts between routes
7. **Magnetic interactions** — buttons that lean toward you
8. **WebGL moment** — one shader hero, max
9. **Sound design** (opt-in only) — the controversial cherry on top

Spend 80% of your effort on the top 4. They define the character. The rest is
accent.

## What this skill produces

When you follow this skill end-to-end, you ship a Next.js 16 site with:
- Lenis smooth scroll synced with GSAP ScrollTrigger
- Custom multi-state cursor (auto-disabled on touch / reduced-motion)
- Magnetic primary buttons
- Drop-in scroll reveal component (4 variants)
- Page transitions via `template.tsx` + Motion + View Transitions API
- Editorial typography with `next/font` + `text-wrap: balance` + tabular nums
- Preloader with real LCP tracking (not a fake counter)
- Marquee component (pause on hover)
- GSAP SplitText reveal for headings
- One optional WebGL hero (code-split, with CSS fallback)
- Full accessibility (reduced-motion, focus management, touch)
- First Load JS ≤180KB gzip (homepage)

Total build time for the skeleton: ~4 hours. Add the 3 signature moments:
~3-5 days.

---

# Part II — The 2026 verified stack

All versions verified against the npm registry on 2026-07-07. Pin to these.

## Core stack (every project)

| Concern | Package | Version | License | Notes |
|---|---|---|---|---|
| Framework | `next` | `^16.2.10` | MIT | App Router default, Turbopack stable, View Transitions experimental |
| React | `react` + `react-dom` | `^19.2.0` | MIT | Server Components, `<Activity>`, React Compiler |
| Declarative animation | `motion` | `^12.42.2` | MIT | Import from `motion/react`. (Framer Motion renamed to Motion in 2025.) |
| Timeline / pinning / text | `gsap` | `^3.15.0` | Free (no-charge) | All former Club plugins FREE since Webflow acquired GreenSock April 2025 |
| React GSAP hook | `@gsap/react` | `^2.1.2` | Free | `useGSAP()` — handles cleanup, scope, revert |
| Smooth scroll | `lenis` | `^1.3.25` | MIT | Use `lenis/react` subpath. Old `@studio-freight/lenis` deprecated. |
| Styling | `tailwindcss` + `@tailwindcss/postcss` | `^4.3.2` | MIT | v4 Oxide engine, CSS-first config via `@theme`, no `tailwind.config.js` |

## Optional libraries (install only when needed)

| Concern | Package | Version | When to install |
|---|---|---|---|
| 3D / WebGL | `three` + `@react-three/fiber` + `@react-three/drei` + `@react-three/postprocessing` | `^0.185.1` / `^9.6.1` / `^10.7.7` / `^3.0.4` | Only for the WebGL hero moment. R3F v9 is React-19-only — don't mix with v8. |
| Lottie | `@lottiefiles/dotlottie-react` | `^0.19.7` | Designer-authored micro-animations. `.lottie` format is ~10× smaller than `.json`. |
| Carousel | `embla-carousel-react` + `embla-carousel-autoplay` | `^8.6.0` | Headless ~7KB. Prefer over Swiper for premium bespoke carousels. |
| Drawer | `vaul` | `^1.1.2` | Mobile-first bottom sheet with drag-to-dismiss. ~18 months stale but React-19-compatible. |
| Icons | `lucide-react` | `^0.5xx` | Tree-shakable. Pair with `optimizePackageImports`. |
| Product tour | `driver.js` | `^1.6.0` | MIT. **Never `intro.js` (AGPL-3.0, paid commercial).** |

## Native browser APIs (no library needed)

| API | Use for | Browser support (mid-2026) |
|---|---|---|
| View Transitions API | Cross-route crossfades, directional slides | Same-doc: Chrome 111+, Safari 18+, Firefox 144+. Cross-doc: Chrome 125+, Safari 26+. FF in progress. |
| CSS scroll-driven animations | Scroll progress bars, simple parallax, view-enter reveals — ZERO JS | Chrome 115+, Safari 26, Firefox 141 — Baseline 2026 |
| Intersection Observer | Trigger-on-enter, lazy-load | Universal |
| Web Animations API | JS-controlled keyframes, off main thread | Universal (Baseline) |
| `prefers-reduced-motion` | Accessibility | Universal |
| `@property` | Animatable CSS custom properties | Chrome 85+, Safari 16.4+, Firefox 128+ |
| `:has()` | Parent selector | Chrome 105+, Safari 15.4+, Firefox 121+ |
| `oklch()` + `color-mix()` + `light-dark()` | Perceptual color, theme variations, built-in dark mode | ~93% support |

## Compatibility matrix — critical

- **R3F v8** = React 18 only. **R3F v9** = React 19 only. Don't mix.
- **Motion v12** peer-deps `react ^18 || ^19` — works on both.
- **GSAP 3.15** is framework-agnostic. `@gsap/react` peer-deps `react >=17`.
- **Tailwind v4** drops `tailwind.config.js` — uses CSS-first `@theme` instead.
- **Next.js 16** requires React 19. If you're on React 18, use Next.js 15.5.x.

## Quick install commands

```bash
# Bootstrap
npx create-next-app@latest my-site --typescript --tailwind --app --turbopack --no-src-dir --import-alias "@/*"

# Core animation stack
npm i motion gsap @gsap/react lenis

# Optional: 3D
npm i three @react-three/fiber @react-three/drei @react-three/postprocessing
npm i -D @types/three

# Optional: Lottie
npm i @lottiefiles/dotlottie-react

# Optional: carousel
npm i embla-carousel-react embla-carousel-autoplay

# Optional: drawer
npm i vaul

# Dev tooling
npm i -D @next/bundle-analyzer
```

## License cheat sheet

| Library | License | Commercial use |
|---|---|---|
| next, react, motion, gsap, @gsap/react, lenis, three, @react-three/*, lottie-*, embla-carousel-*, swiper, vaul, driver.js, lucide-react | MIT or "free no-charge" | ✅ Free |
| intro.js | AGPL-3.0 | ❌ Paid license required |
| atropos | MIT | ✅ (but unmaintained since 2023) |

---

# Part III — Design system foundations

A great Awwwards site starts with a great design system. Skip this and no
amount of animation saves you.

## Color system

### Use `oklch()` — not hex, not hsl, not rgb

`oklch()` is perceptually uniform: 50% lightness looks the same across hues.
This means your design system's "muted" color is actually muted regardless of
hue. HSL lies — `hsl(240 50% 50%)` looks lighter than `hsl(0 50% 50%)` despite
same "lightness".

```css
@theme {
  /* Cool dark base */
  --color-bg:           oklch(15% 0.02 250);
  --color-bg-elevated:  oklch(20% 0.02 250);
  --color-fg:           oklch(95% 0.02 250);
  --color-fg-muted:     oklch(60% 0.02 250);
  --color-accent:       oklch(72% 0.18 250);   /* electric blue */
  --color-accent-warm:  oklch(72% 0.18 30);    /* warm contrast */
  --color-border:       oklch(95% 0.02 250 / 8%);
}

@media (prefers-color-scheme: light) {
  @theme {
    --color-bg:           oklch(99% 0.001 250);
    --color-bg-elevated:  oklch(96% 0.005 250);
    --color-fg:           oklch(15% 0.02 250);
    --color-fg-muted:     oklch(45% 0.02 250);
    --color-border:       oklch(15% 0.02 250 / 10%);
  }
}
```

### `color-mix()` for theme variations

```css
.button-hover {
  background: color-mix(in oklab, var(--color-accent) 80%, white);
}
```
Always use `in oklab` (perceptually uniform). `in srgb` produces muddy results.

### `light-dark()` for built-in dark mode

No media-query duplication:

```css
:root { color-scheme: light dark; }
body {
  background: light-dark(white, oklch(15% 0.02 250));
  color: light-dark(black, oklch(95% 0.02 250));
}
```

### Contrast verification

- Body text: 4.5:1 minimum (WCAG AA)
- Large text (≥24px or ≥18.66px bold): 3:1
- UI components (borders, focus indicators): 3:1

With `oklch()`, two colors with the same `L` value have the same perceived
lightness. For AA body contrast: aim for ~50-60 `L` difference between text and
background.

## Typography system

### Variable fonts via `next/font`

```tsx
import { Inter, Instrument_Serif } from "next/font/google";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-serif",
  display: "swap",
});

// In layout.tsx:
<html className={`${inter.variable} ${serif.variable}`}>
```

- Self-hosted (no Google Fonts CDN request → faster, privacy-friendly)
- Automatic subset optimization
- `display: "swap"` prevents FOIT
- Variable fonts: one file, infinite weights — animate `font-variation-settings`

### Modular type scale

Pick a ratio and use it for every heading size:

| Ratio | Name | Use for |
|---|---|---|
| 1.200 | Minor Third | Dense data UIs |
| 1.250 | Major Third | Marketing sites (default) |
| 1.333 | Perfect Fourth | Editorial / portfolio |
| 1.414 | Augmented Fourth | Loud, confident |
| 1.500 | Perfect Fifth | Hero-only sites |
| 1.618 | Golden Ratio | Maximum drama, sparse use |

```css
@theme {
  --text-xs:   0.75rem;     /* 12px */
  --text-sm:   0.875rem;    /* 14px */
  --text-base: 1rem;        /* 16px */
  --text-lg:   1.25rem;     /* 20px — ratio 1.25 */
  --text-xl:   1.563rem;    /* 25px */
  --text-2xl:  1.953rem;    /* 31px */
  --text-3xl:  2.441rem;    /* 39px */
  --text-4xl:  3.052rem;    /* 49px */
  --text-5xl:  3.815rem;    /* 61px */
  --text-6xl:  4.768rem;    /* 76px */
  --text-7xl:  5.960rem;    /* 95px */
}
```

### Fluid type with `clamp()`

```css
.hero-title {
  font-size: clamp(3rem, 10vw, 8rem);
  line-height: 1.05;
  letter-spacing: -0.03em;
}
```

The clamp syntax: `clamp(min, preferred, max)`. `10vw` scales with viewport.

### Premium typography CSS

```css
@layer base {
  h1, h2, h3, h4 {
    text-wrap: balance;        /* balance line lengths in headings */
    line-height: 1.05;
    letter-spacing: -0.02em;   /* tight tracking for big text */
  }

  p {
    text-wrap: pretty;         /* avoid orphan words in body */
    line-height: 1.6;
  }

  .numeric {
    font-variant-numeric: tabular-nums lining-nums;
    font-feature-settings: "tnum" 1, "lnum" 1;
  }

  /* Premium kerning + ligatures */
  body {
    font-feature-settings: "kern" 1, "liga" 1, "calt" 1;
  }

  /* Stylistic set example (Inter ss01 = alternate single-story g) */
  .display {
    font-feature-settings: "kern" 1, "liga" 1, "ss01" 1;
  }
}
```

### Fallback font metrics — eliminate FOUT layout shift

When the web font loads, the fallback font's metrics differ → text reflows. Fix
with `size-adjust` on a fallback `@font-face`:

```css
@font-face {
  font-family: "Inter Fallback";
  src: local("Arial");
  size-adjust: 100.5%;        /* tune to match Inter's metrics */
  ascent-override: 90%;
  descent-override: 22%;
}
body { font-family: "Inter", "Inter Fallback", sans-serif; }
```

Or use `fontpie` / `fontaine` packages to auto-generate these metrics.

## Spacing system

### 8px base grid

Every padding, margin, gap is a multiple of 4 or 8:

```css
@theme {
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-6: 1.5rem;    /* 24px */
  --space-8: 2rem;      /* 32px */
  --space-12: 3rem;     /* 48px */
  --space-16: 4rem;     /* 64px */
  --space-24: 6rem;     /* 96px */
  --space-32: 8rem;     /* 128px */
}
```

### Container with editorial gutters

```css
@layer utilities {
  .container-editorial {
    max-width: 80rem;
    margin-inline: auto;
    padding-inline: clamp(1.5rem, 5vw, 4rem);
  }
}
```

### Logical properties everywhere (RTL-ready)

```css
.card {
  padding-inline: 2rem;      /* NOT padding-left */
  margin-block: 1rem;        /* NOT margin-top */
  inset-block-start: 0;      /* NOT top */
}
```

## Motion system

### Three site-wide easing tokens

Encode as CSS variables. Use ONLY these across the entire site.

```css
@theme {
  /* Default — soft, confident entrances and reveals */
  --ease-out-expo:     cubic-bezier(0.16, 1, 0.3, 1);

  /* Symmetric — for entrance + exit pairs (page transitions) */
  --ease-in-out-quint: cubic-bezier(0.83, 0, 0.17, 1);

  /* With personality — playful overshoot, use SPARINGLY */
  --ease-anticipate:   cubic-bezier(0.68, -0.55, 0.27, 1.55);

  /* Card hover, button press */
  --ease-out-back:     cubic-bezier(0.34, 1.56, 0.64, 1);

  /* Subtle — long fades */
  --ease-out-quart:    cubic-bezier(0.25, 1, 0.5, 1);

  /* Dramatic — fullscreen overlays */
  --ease-in-out-circ:  cubic-bezier(0.85, 0, 0.15, 1);
}
```

In JS (Motion / GSAP), use the same numeric values:

```ts
// Motion
transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}

// GSAP
gsap.to(el, { duration: 0.7, ease: "expo.out" });
gsap.to(el, { duration: 0.7, ease: "power4.inOut" });
gsap.to(el, { duration: 0.7, ease: "back.out(1.7)" });
```

### Duration scale

| Token | Duration | Use for |
|---|---|---|
| `--duration-instant` | 100ms | Color changes, instant feedback |
| `--duration-fast` | 200ms | Hover states, small UI |
| `--duration-normal` | 400ms | Default transitions |
| `--duration-md` | 600ms | Standard reveals |
| `--duration-slow` | 900ms | Hero entrances, page transitions |
| `--duration-slower` | 1200ms | Preloader curtain, big moments |

### Stagger pattern

```css
.item {
  --i: 0;
  transition: opacity 0.5s var(--ease-out-expo);
  transition-delay: calc(var(--i) * 80ms);
}
.item:nth-child(1) { --i: 0; }
.item:nth-child(2) { --i: 1; }
.item:nth-child(3) { --i: 2; }
/* Or in React: style={{ '--i': index } as CSSProperties} */
```

In Motion:
```tsx
const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 30 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};
```

---

# Part IV — Complete CSS reference

Modern CSS eliminates ~70% of the JS animation code you'd have written 3 years
ago. Reach for CSS first; Motion/GSAP only when CSS can't express it.

## Browser support cheat-sheet (mid-2026, verified)

| Feature | Chrome | Safari | Firefox | Baseline |
|---|---|---|---|---|
| Subgrid | 117+ | 16+ | 71+ | ✅ |
| Container queries | 106+ | 16+ | 110+ | ✅ |
| `:has()` | 105+ | 15.4+ | 121+ | ✅ |
| Native nesting | 112+ | 16.5+ | 117+ | ✅ |
| Cascade layers `@layer` | 99+ | 15.4+ | 97+ | ✅ |
| `clip-path` (path/polygon) | 24+ | 7+ | 54+ | ✅ |
| `mask-image` | 120+ | 16+ | 53+ | ✅ |
| `backdrop-filter` | 76+ | 18+ | 103+ | ✅ |
| `mix-blend-mode` | 41+ | 8+ | 32+ | ✅ |
| `background-clip: text` | 4+ (-webkit-) | 4+ (-webkit-) | 49+ (-webkit-) | ✅ |
| `@property` | 85+ | 16.4+ | 128+ | ✅ |
| `color-mix()` | 111+ | 16.2+ | 113+ | ✅ |
| `oklch()` | 111+ | 15.4+ | 113+ | ✅ |
| `light-dark()` | 123+ | 17.5+ | 120+ | ✅ |
| **CSS scroll-driven animations** | 115+ | 26+ | 141+ | ✅ Baseline 2026 |
| `interpolate-size: allow-keywords` | 129+ | 26.4+ | flag only | ⚠️ Use grid fallback |
| `transition-behavior: allow-discrete` | 129+ | 17.4+ | 129+ (partial) | ⚠️ |
| `@starting-style` | 117+ | 17.4+ | 129+ | ⚠️ |
| View Transitions (same-doc) | 111+ | 18+ | 144+ | ✅ |
| View Transitions (cross-doc) | 125+ | 26+ | in progress | ⚠️ |
| Variable fonts | 62+ | 11+ | 62+ | ✅ |
| `text-wrap: balance` | 114+ | 17.5+ | 121+ | ✅ |
| `text-wrap: pretty` | 117+ | 17.5+ | ❌ | ⚠️ FF missing |
| Dynamic viewport `dvh/dvw` | 108+ | 15.4+ | 101+ | ✅ |
| `scroll-snap` | 69+ | 11+ | 68+ | ✅ |
| `scrollbar-gutter` | 94+ | 16.4+ | 97+ | ✅ |
| `overscroll-behavior` | 63+ | 16+ | 59+ | ✅ |
| `content-visibility: auto` | 85+ | 18+ | 125+ | ⚠️ Safari late |
| `prefers-reduced-motion` | 74+ | 10.1+ | 63+ | ✅ |

## Layout primitives

### Subgrid
```css
.card { display: grid; grid-template-columns: 1fr 2fr; }
.card-body { display: grid; grid-template-columns: subgrid; grid-column: span 2; }
```

### Container queries
```css
.sidebar { container-type: inline-size; }
@container (min-width: 400px) {
  .sidebar .widget { display: grid; grid-template-columns: 1fr 1fr; }
}
```

### `:has()` — the parent selector
```css
form:has(input:invalid) .submit { opacity: 0.5; pointer-events: none; }
.card:has(img:hover) { transform: scale(1.02); }
.nav:has(.submenu:hover) .backdrop { opacity: 1; }
```

### Native CSS nesting
```css
.card {
  padding: 2rem;
  & .title { font-size: 1.5rem; }
  &:hover { background: var(--color-bg-hover); }
  & > p { color: var(--color-fg-muted); }
}
```

### Cascade layers (manage Tailwind + custom + Motion CSS)
```css
@layer base, components, motion, utilities;
@layer motion { /* Motion overrides always win */ }
@layer utilities { /* Tailwind utilities */ }
```

## Visual effects

### `clip-path` — reveals and wipes
```css
.reveal {
  clip-path: inset(0 0 100% 0);     /* hidden from bottom up */
  transition: clip-path 0.8s var(--ease-out-expo);
}
.reveal.visible { clip-path: inset(0 0 0 0); }

.wipe-circle {
  clip-path: circle(0% at 50% 50%);
  transition: clip-path 1s var(--ease-out-expo);
}
.wipe-circle.visible { clip-path: circle(150% at 50% 50%); }
```
**Performance:** mid-cost — better than `width` but worse than `transform`. Use sparingly on large elements.

### `mask-image`
```css
.fade-bottom {
  mask-image: linear-gradient(to bottom, black 70%, transparent 100%);
}
.marquee {
  mask-image: linear-gradient(to right, transparent, black 8%, black 92%, transparent);
}
```

### `backdrop-filter` — glassmorphism
**CRITICAL RULE:** Only on `position: fixed` / `sticky` surfaces (nav, modals). Never on scrolling content — re-rasters every frame on Safari.
```css
.nav {
  position: sticky; top: 0;
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  background: color-mix(in oklab, var(--color-bg) 70%, transparent);
  border-bottom: 1px solid var(--color-border);
}
```

### `mix-blend-mode` — difference, exclusion, multiply
```css
.cursor { mix-blend-mode: difference; background: white; }
.overlay { mix-blend-mode: multiply; background: var(--color-accent); }
```
**Warning:** `mix-blend-mode` + `position: sticky` + `backdrop-filter` together renders as black on Safari. Don't combine.

### `background-clip: text` — gradient/image-filled text
```css
.gradient-text {
  background: linear-gradient(90deg, oklch(70% 0.2 250), oklch(70% 0.2 30));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
```

### `-webkit-text-stroke` — outlined text
```css
.outline-text {
  -webkit-text-stroke: 1px var(--color-fg);
  color: transparent;
}
```

### `@property` — animatable CSS custom properties
Without `@property`, custom properties are strings and can't be animated.
```css
@property --hue {
  syntax: "<number>";
  initial-value: 0;
  inherits: false;
}
.gradient {
  background: linear-gradient(90deg, hsl(var(--hue) 80% 50%), hsl(calc(var(--hue) + 60) 80% 50%));
  transition: --hue 1s ease;
}
.gradient:hover { --hue: 180; }
```

### `filter` — blur, hue-rotate, contrast
```css
.img:hover { filter: brightness(1.1) contrast(1.05) saturate(1.2); }
```

## Animation & motion

### CSS scroll-driven animations (Baseline 2026, ZERO JS)

**Scroll progress bar:**
```css
.progress {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--color-accent);
  transform-origin: left;
  animation: grow linear forwards;
  animation-timeline: scroll(root);
}
@keyframes grow {
  from { transform: scaleX(0); }
  to   { transform: scaleX(1); }
}
```

**View-enter reveal:**
```css
.reveal {
  animation: reveal-up linear forwards;
  animation-timeline: view();
  animation-range: entry 0% entry 80%;
}
@keyframes reveal-up {
  from { opacity: 0; transform: translateY(40px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

**Parallax:**
```css
.parallax {
  animation: parallax linear;
  animation-timeline: scroll(root);
}
@keyframes parallax {
  from { transform: translateY(0); }
  to   { transform: translateY(-30%); }
}
```

> Pair with `@supports (animation-timeline: scroll())` and a Motion fallback.

### Named scroll timelines
```css
@scroll-timeline page-scroll {
  source: root;
  orientation: block;
}
.progress { animation-timeline: page-scroll; }
```

### `interpolate-size: allow-keywords` — animate `height: auto`!
```css
.acc { interpolate-size: allow-keywords; }
.acc-body { height: 0; transition: height 0.4s var(--ease-out-expo); }
.acc[data-open] .acc-body { height: auto; }
```
**Universal fallback** (works everywhere):
```css
.acc-body {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.4s var(--ease-out-expo);
}
.acc[data-open] .acc-body { grid-template-rows: 1fr; }
.acc-body > div { overflow: hidden; }
```

### `transition-behavior: allow-discrete` — animate `display`
```css
.modal {
  display: none;
  opacity: 0;
  transition: opacity 0.3s, display 0.3s allow-discrete;
}
.modal.open { display: block; opacity: 1; }
```

### `@starting-style` — animate first render
Like Motion's `initial` → `animate`, in pure CSS:
```css
.modal { opacity: 0; transition: opacity 0.3s; }
.modal.open { opacity: 1; }
@starting-style { .modal.open { opacity: 0; } }
```

### View Transitions CSS
```css
::view-transition-old(root),
::view-transition-new(root) {
  animation-duration: 0.4s;
  animation-timing-function: var(--ease-out-expo);
}

/* Directional slides via transitionTypes */
::view-transition-old(root) { animation: 0.3s ease both slide-out-left; }
::view-transition-new(root) { animation: 0.3s ease both slide-in-right; }

@keyframes slide-out-left { to { transform: translateX(-100%); } }
@keyframes slide-in-right { from { transform: translateX(100%); } }
```

### `linear()` easing — spring physics in pure CSS
```css
.button {
  transition: transform 0.5s linear(0, 0.01, 0.04 1%, 0.1, 0.18, 0.3, 0.45, 0.62, 0.78, 0.92, 1);
}
```
Generate via [linear-easing-generator.netlify.app](https://linear-easing-generator.netlify.app/).

### `prefers-reduced-motion` — global guard
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```
Or scope motion to ONLY users who haven't opted out:
```css
@media (prefers-reduced-motion: no-preference) {
  .reveal { animation: reveal-up 0.8s ease forwards; }
}
```

## Layout & spacing polish

### Dynamic viewport units (mobile URL bar fix)
```css
.hero { height: 100dvh; }      /* dynamic — accounts for URL bar */
.hero-min { height: 100svh; }  /* small viewport — URL bar shown */
.hero-max { height: 100lvh; }  /* large viewport — URL bar hidden */
```
**Use `dvh` everywhere you previously used `vh`.** Never `100vh` on mobile.

### `scroll-snap`
```css
.scroll-container { scroll-snap-type: y proximity; }
section { scroll-snap-align: start; scroll-snap-stop: always; }
```
Use `proximity` (not `mandatory`) for content sections. Don't combine with Lenis — they fight.

### `scrollbar-gutter` — prevent layout shift
```css
html { scrollbar-gutter: stable; }
```

### `overscroll-behavior` — modal scroll lock
```css
.modal-content {
  overscroll-behavior: contain;
  overflow-y: auto;
}
```

## Premium UI patterns (CSS-only)

### Glassmorphism done right
```css
.glass {
  background: color-mix(in oklab, var(--color-bg) 60%, transparent);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--color-border);
  box-shadow: 0 8px 32px color-mix(in oklab, var(--color-bg) 40%, transparent);
}
```

### Gradient mesh backgrounds
```css
.mesh {
  background:
    radial-gradient(at 20% 20%, oklch(70% 0.2 250 / 0.6), transparent 50%),
    radial-gradient(at 80% 30%, oklch(70% 0.2 30 / 0.5), transparent 50%),
    radial-gradient(at 40% 80%, oklch(70% 0.2 180 / 0.4), transparent 50%),
    oklch(15% 0.02 250);
}
```

### Animated gradient borders via mask compositing
```css
.gradient-border { position: relative; background: var(--color-bg); }
.gradient-border::before {
  content: "";
  position: absolute; inset: 0;
  padding: 1px;
  background: linear-gradient(90deg, oklch(70% 0.2 250), oklch(70% 0.2 30));
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
          mask-composite: exclude;
}
```

### Conic gradient spinner
```css
.spinner {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: conic-gradient(from 0deg, transparent, var(--color-accent));
  -webkit-mask: radial-gradient(circle at center, transparent 60%, #000 61%);
          mask: radial-gradient(circle at center, transparent 60%, #000 61%);
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
```

### Stagger via `:nth-child` delay
```css
.item {
  --i: 0;
  transition: opacity 0.5s var(--ease-out-expo);
  transition-delay: calc(var(--i) * 80ms);
}
.item:nth-child(1) { --i: 0; }
.item:nth-child(2) { --i: 1; }
/* Or set --i inline via React: style={{ '--i': index }} */
```

### Marquee (pure CSS, pause on hover)
```css
.marquee {
  display: flex;
  overflow: hidden;
  mask-image: linear-gradient(to right, transparent, black 8%, black 92%, transparent);
}
.marquee-track {
  display: flex;
  flex-shrink: 0;
  gap: 2rem;
  animation: marquee 30s linear infinite;
  min-width: 100%;
}
.marquee:hover .marquee-track { animation-play-state: paused; }
@keyframes marquee {
  from { transform: translateX(0); }
  to   { transform: translateX(-100%); }
}
/* HTML: <div class="marquee"><div class="marquee-track">…items…</div><div class="marquee-track" aria-hidden>…duplicate…</div></div> */
```

### Spotlight cursor effect
```css
.spotlight {
  --x: 50%;
  --y: 50%;
  background:
    radial-gradient(300px at var(--x) var(--y), oklch(70% 0.2 250 / 0.2), transparent 80%),
    var(--color-bg);
}
```
```tsx
<div
  className="spotlight"
  onMouseMove={(e) => {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--x", `${e.clientX - r.left}px`);
    e.currentTarget.style.setProperty("--y", `${e.clientY - r.top}px`);
  }}
/>
```

### 3D card flip
```css
.flip-card { perspective: 1000px; width: 300px; height: 400px; }
.flip-card-inner {
  position: relative;
  width: 100%; height: 100%;
  transform-style: preserve-3d;
  transition: transform 0.6s var(--ease-out-expo);
}
.flip-card:hover .flip-card-inner { transform: rotateY(180deg); }
.flip-card-face {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
}
.flip-card-back { transform: rotateY(180deg); }
```

### Animated `box-shadow` without layout cost
Don't animate `box-shadow` directly — animate a pseudo-element's `opacity`:
```css
.card { position: relative; }
.card::after {
  content: ""; position: absolute; inset: 0;
  box-shadow: 0 10px 30px rgba(0,0,0,0.2);
  opacity: 0;
  transition: opacity 0.4s var(--ease-out-expo);
}
.card:hover::after { opacity: 1; }
```

## Performance — cheap vs expensive properties

| Cost | Properties |
|---|---|
| **Cheap (compositor)** | `transform` (translate, scale, rotate, skew), `opacity` |
| **Mid (paint only)** | `clip-path`, `background-color`, `color`, `filter: blur()`, `mask-image` |
| **Expensive (layout)** | `width`, `height`, `top`, `left`, `margin`, `padding`, `border-width`, `box-shadow`, `font-size`, `gap` |

**Animate only `transform` and `opacity` on hot paths.**

### `will-change` — use correctly
```css
.card:hover { will-change: transform; }
.card { transition: transform 0.4s; }
/* JS: card.addEventListener('transitionend', () => card.style.willChange = 'auto') */
```
✅ Set on hover/focus, remove on `transitionend`. ❌ Never permanent — burns GPU memory.

### `contain` — CSS containment
```css
.card { contain: layout paint style; }
/* Or shorthand */ .card { contain: strict; }
```

### `content-visibility: auto` — virtualize off-screen DOM
```css
section {
  content-visibility: auto;
  contain-intrinsic-size: auto 800px;
}
```
Browser skips rendering off-screen sections. Pair with `contain-intrinsic-size` to avoid scrollbar jump.

---

# Part V — Animation libraries deep dive

## 1. Motion (formerly Framer Motion)

### Identity & versions
- Renamed "Framer Motion" → "Motion" in early 2025
- Two equivalent npm packages, lockstep releases:
  - `motion` — canonical, import from `motion/react`
  - `framer-motion` — backwards-compat alias
- Use `motion` for new projects: `import { motion } from "motion/react"`
- v12.42.2 (2026-06-30), MIT, peer-deps `react ^18 || ^19`

### Full API reference

| API | Purpose |
|-----|---------|
| `motion.div`, `motion.span`, `motion(Component)` | DOM primitive + custom HOC. Accept `initial`, `animate`, `whileHover`, `whileTap`, `whileInView`, `exit`, `transition`, `variants`, `layout`, `layoutId`. |
| `AnimatePresence` | Wraps conditionally-rendered children to animate `exit` before unmount. `mode="wait"` / `mode="popLayout"`. |
| `useScroll({ target, offset, container })` | Returns `scrollY`, `scrollX`, `scrollYProgress`, `scrollXProgress`. `offset` accepts viewport-relative tuples like `["start end", "end start"]`. |
| `useTransform(value, inputRange, outputRange)` | Map a MotionValue through interpolation. |
| `useSpring(value, config)` | Smooth a MotionValue with critically-damped spring. |
| `useInView(ref, { once, margin, amount })` | Boolean hook around IntersectionObserver. |
| `useMotionValue`, `useMotionTemplate`, `useVelocity`, `useTime`, `useAnimationFrame` | Lower-level primitives. |
| `layout` / `layoutId` | Shared-layout / FLIP animations. |
| `LayoutGroup` / `MotionConfig` | Coordinate `layoutId` scopes; set global config (`transition`, `reducedMotion="always|never|user"`). |
| Stagger | Parent `variants={{ show: { transition: { staggerChildren: 0.05 } } }}`. |
| `useAnimate()` | Imperative API — `[scope, animate]` for hover-driven sequences. |
| `drag`, `dragControls`, `Reorder.Group` / `Reorder.Item` | Drag-and-drop and reorderable lists. |

### React 19 / Next.js 16 compatibility
- ✅ Fully supported. v12 peer-depends `react ^18 || ^19`.
- ✅ Works in App Router — every component importing `motion/react` must carry `"use client"`.
- ✅ SSR-safe: `motion.*` components render their `initial` state on the server, so streamed markup matches the first painted frame (no hydration mismatch if `initial` is deterministic).
- ⚠️ Cannot call `useScroll`/`useTransform`/`useSpring`/`useAnimate` in a Server Component.

### Gotchas
- Avoid `useTransform` chains on every scroll tick when CSS `animation-timeline: scroll()` could do it. Motion's scroll-linked runs in JS, not on the compositor.
- `AnimatePresence` requires the same component type in the same position to track exit. Use `key` when siblings swap.
- `layout` animations are FLIP-based — snapshot on every layout-changing render. Don't `layout` a giant list; use `layout="position"` to opt out of size animation.
- `whileInView` does NOT unobserve by default. Pass `once: true` for fire-once.
- Bundle: ~50 KB min+gzip for the full React API; tree-shakes well.
- Reduced motion: `<MotionConfig reducedMotion="user">` (or `"always"`).

### Code: scroll-linked progress bar
```tsx
"use client";
import { motion, useScroll, useSpring } from "motion/react";

export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 30,
    restDelta: 0.001,
  });
  return (
    <motion.div
      style={{ scaleX }}
      className="fixed top-0 left-0 right-0 h-[2px] bg-accent origin-left z-50"
    />
  );
}
```

### Code: shared layout tab indicator
```tsx
"use client";
import { motion } from "motion/react";
import { useState } from "react";

const tabs = ["Overview", "Details", "Reviews"];

export function Tabs() {
  const [active, setActive] = useState(0);
  return (
    <div className="flex gap-1 border-b border-border">
      {tabs.map((tab, i) => (
        <button
          key={tab}
          onClick={() => setActive(i)}
          className="relative px-4 py-3"
        >
          {tab}
          {active === i && (
            <motion.div
              layoutId="tab-underline"
              className="absolute bottom-0 left-0 right-0 h-[2px] bg-accent"
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            />
          )}
        </button>
      ))}
    </div>
  );
}
```

### Code: magnetic button
```tsx
"use client";
import { motion, useMotionValue, useSpring } from "motion/react";
import { useRef } from "react";

export function MagneticButton({ children, href, strength = 0.4 }) {
  const ref = useRef<HTMLAnchorElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 200, damping: 15, mass: 0.3 });
  const sy = useSpring(y, { stiffness: 200, damping: 15, mass: 0.3 });

  const handleMove = (e: React.MouseEvent) => {
    if (window.matchMedia("(pointer: coarse)").matches) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const rect = ref.current!.getBoundingClientRect();
    x.set((e.clientX - rect.left - rect.width / 2) * strength);
    y.set((e.clientY - rect.top - rect.height / 2) * strength);
  };
  const reset = () => { x.set(0); y.set(0); };

  return (
    <motion.a
      ref={ref}
      href={href}
      onMouseMove={handleMove}
      onMouseLeave={reset}
      style={{ x: sx, y: sy }}
      whileTap={{ scale: 0.95 }}
      className="magnetic-button"
    >
      <span className="magnetic-button-content">{children}</span>
    </motion.a>
  );
}
```

### Code: staggered list reveal
```tsx
"use client";
import { motion } from "motion/react";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 30 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

export function StaggerList({ items }: { items: { id: string; title: string }[] }) {
  return (
    <motion.ul
      variants={container}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-80px" }}
    >
      {items.map((i) => (
        <motion.li key={i.id} variants={item}>
          {i.title}
        </motion.li>
      ))}
    </motion.ul>
  );
}
```

### Code: AnimatePresence for exit animations
```tsx
"use client";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

export function Modal({ isOpen, onClose, children }) {
  return (
    <AnimatePresence mode="wait">
      {isOpen && (
        <motion.div
          className="modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
        >
          <motion.div
            className="modal-content"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            onClick={(e) => e.stopPropagation()}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

### Code: useAnimate imperative sequence (hover-driven)
```tsx
"use client";
import { useAnimate } from "motion/react";

export function HoverSequence({ children }) {
  const [scope, animate] = useAnimate();
  const handleEnter = async () => {
    await animate(scope.current, { opacity: 0.5 }, { duration: 0.2 });
    await animate(scope.current, { opacity: 1 }, { duration: 0.3 });
  };
  return (
    <div ref={scope} onMouseEnter={handleEnter}>
      {children}
    </div>
  );
}
```

---

## 2. GSAP (GreenSock Animation Platform)

### Identity & versions
- `gsap` → 3.15.0 (2026-04-13)
- `@gsap/react` → 2.1.2 — provides `useGSAP()` hook
- License: "Standard 'no charge' license — free for all use including commercial."
- **All former Club GSAP premium plugins are FREE** since Webflow acquired GreenSock in April 2025. No paid tier.

### What ships in the npm package
The `gsap/dist/` directory contains every plugin, minified and unminified:

**Core (always free):**
- `gsap.js` (TweenMax+TweenLite+TimelineMax merged), `CSSPlugin`, `EasePack`

**Formerly Club / premium (now free):**
- `ScrollTrigger.js` — pin, scrub, container animation, batch, matchMedia
- `ScrollSmoother.js` — premium scroll smoothing tied to ScrollTrigger
- `Observer.js` — pointer/touch/wheel observer
- `Flip.js` — FLIP layout/state animations
- `SplitText.js` — char/word/line splitting (PREFER over `split-type`)
- `ScrambleTextPlugin.js` — randomized text scrambling
- `DrawSVGPlugin.js` — animate `stroke-dashoffset` of SVG paths
- `MorphSVGPlugin.js` — morph between SVG paths
- `MotionPathPlugin.js` — animate along an SVG path / arbitrary bezier
- `CustomEase.js`, `CustomBounce.js`, `CustomWiggle.js` — bespoke easing
- `Draggable.js` — drag/rotate/throw with momentum
- `InertiaPlugin.js`, `Physics2DPlugin.js`, `PhysicsPropsPlugin.js`
- `PixiPlugin.js`, `EaselPlugin.js`, `TextPlugin.js`, `CSSRulePlugin.js`, `GSDevTools.js`

### When to choose GSAP over Motion
- **Complex timelines** with overlapping tweens, labels, and precise sync.
- **ScrollTrigger pinning** and scrub-tied sequences (Motion has no equivalent).
- **SplitText** char/word/line reveals (Motion's `staggerChildren` is per-item, not per-character).
- **SVG path drawing** (`DrawSVGPlugin`) and **path morphing** (`MorphSVGPlugin`).
- **Custom easing** (`CustomEase`) — Motion springs are great but sometimes you need a precise curve.

When Motion is better: layout animations, hover/tap gestures, exit animations, declarative React-idiomatic API, smaller bundle for simple use cases.

### Import patterns
```ts
// Core only
import { gsap } from "gsap";

// Register plugins (client-side only)
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { DrawSVGPlugin } from "gsap/DrawSVGPlugin";
import { ScrambleTextPlugin } from "gsap/ScrambleTextPlugin";
gsap.registerPlugin(ScrollTrigger, SplitText, DrawSVGPlugin, ScrambleTextPlugin);
```

### React integration — `useGSAP`
```tsx
"use client";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useRef } from "react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

function MyComponent() {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      // All selectors are scoped to `container` — no global .class queries
      gsap.from(".reveal", {
        scrollTrigger: { trigger: container.current, start: "top 80%" },
        y: 40,
        opacity: 0,
        stagger: 0.1,
        duration: 0.8,
        ease: "expo.out",
      });
    },
    { scope: container, revertOnUpdate: true }
  );

  return <div ref={container}>…</div>;
}
```

`useGSAP` handles:
- Cleanup on unmount (calls `gsap.context.revert()`)
- Re-running when deps change (with `revertOnUpdate: true`) — CRITICAL for React 19 Strict Mode
- Scoping selectors to a ref

### Gotchas
- **Pinning inside a `transform`ed ancestor breaks.** The ancestor's transform corrupts `position: sticky` math. This is the #1 ScrollTrigger bug. Use `invalidateOnRefresh: true` and check ancestry.
- **SplitText must be `.revert()`ed on cleanup** or you get duplicated text on re-render in Strict Mode.
- **ScrollTrigger needs `invalidateOnRefresh: true`** if any element's height changes after load (font swap, image load, accordion expand).
- **Don't run two RAF loops.** Sync Lenis's RAF with `gsap.ticker`.
- Use `ScrollTrigger.matchMedia()` for responsive + reduced-motion — it auto-creates and tears down scenes per breakpoint.
- GSAP mutates DOM directly; React doesn't know. Always animate inside `useGSAP` scope, never inside `useEffect` without context.

### Code: ScrollTrigger pinned horizontal scroll
```tsx
"use client";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useRef } from "react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

export function HorizontalScroll({ panels }: { panels: string[] }) {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (window.matchMedia("(max-width: 768px)").matches) return; // disable on mobile

    const sections = gsap.utils.toArray<HTMLElement>(".panel");
    gsap.to(sections, {
      xPercent: -100 * (sections.length - 1),
      ease: "none",
      scrollTrigger: {
        trigger: container.current,
        pin: true,
        scrub: 1,
        end: () => `+=${container.current!.scrollWidth}`,
        invalidateOnRefresh: true,
      },
    });
  }, { scope: container, revertOnUpdate: true });

  return (
    <div ref={container} className="flex overflow-hidden">
      {panels.map((p, i) => (
        <div key={i} className="panel w-screen h-screen flex-shrink-0 flex items-center justify-center">
          {p}
        </div>
      ))}
    </div>
  );
}
```

### Code: SplitText char reveal
```tsx
"use client";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger, SplitText } from "@/lib/gsap";
import { useRef } from "react";

export function HeadingReveal({ children }: { children: string }) {
  const ref = useRef<HTMLHeadingElement>(null);

  useGSAP(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      gsap.set(ref.current, { opacity: 1 });
      return;
    }

    const split = SplitText.create(ref.current!, { type: "chars, words" });
    gsap.from(split.chars, {
      yPercent: 120,
      opacity: 0,
      stagger: 0.025,
      duration: 0.8,
      ease: "expo.out",
      scrollTrigger: { trigger: ref.current, start: "top 80%" },
    });
  }, { scope: ref, revertOnUpdate: true });

  return (
    <h2 ref={ref} className="heading-reveal overflow-hidden">
      {children}
    </h2>
  );
}
```

### Code: SVG path draw on scroll
```tsx
"use client";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger, DrawSVGPlugin } from "@/lib/gsap";
import { useRef } from "react";

gsap.registerPlugin(DrawSVGPlugin);

export function SvgDraw({ paths }: { paths: string[] }) {
  const ref = useRef<SVGSVGElement>(null);

  useGSAP(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    gsap.from("path", {
      drawSVG: "0%",
      ease: "none",
      stagger: 0.2,
      duration: 2,
      scrollTrigger: {
        trigger: ref.current,
        start: "top 70%",
        end: "bottom 30%",
        scrub: true,
      },
    });
  }, { scope: ref });

  return (
    <svg ref={ref} viewBox="0 0 800 400">
      {paths.map((d, i) => (
        <path key={i} d={d} fill="none" stroke="currentColor" strokeWidth="2" />
      ))}
    </svg>
  );
}
```

### Code: ScrollTrigger.matchMedia for responsive + reduced motion
```tsx
useGSAP(() => {
  ScrollTrigger.matchMedia({
    "(prefers-reduced-motion: reduce)": () => {
      gsap.set(".reveal", { opacity: 1, y: 0 });
    },
    "(prefers-reduced-motion: no-preference) and (min-width: 769px)": () => {
      gsap.from(".reveal", {
        opacity: 0, y: 40, stagger: 0.1, duration: 0.8, ease: "expo.out",
        scrollTrigger: { trigger: ".section", start: "top 80%" },
      });
    },
    "(prefers-reduced-motion: no-preference) and (max-width: 768px)": () => {
      // Simplified animation on mobile
      gsap.from(".reveal", {
        opacity: 0, y: 20, stagger: 0.05, duration: 0.5, ease: "expo.out",
        scrollTrigger: { trigger: ".section", start: "top 90%" },
      });
    },
  });
}, { scope: container });
```

### Code: GSAP timeline with labels
```tsx
useGSAP(() => {
  const tl = gsap.timeline({
    scrollTrigger: {
      trigger: ".hero",
      start: "top top",
      end: "+=200%",
      pin: true,
      scrub: 1,
      invalidateOnRefresh: true,
    },
  });

  tl.from(".hero-title", { yPercent: 100, opacity: 0, duration: 1 })
    // "<" means "same start time as previous" — overlapping
    .from(".hero-sub", { yPercent: 100, opacity: 0, duration: 1 }, "<")
    // "+=1" means "1 second after previous ends"
    .to(".hero-title", { opacity: 0, duration: 0.5 }, "+=1")
    .from(".next-section", { yPercent: 50, opacity: 0, duration: 1 });
}, { scope: container });
```

---

## 3. Lenis — smooth scroll

### Identity
- `lenis` → 1.3.25 (2026-06-26)
- React wrapper: `lenis/react` subpath export
- Old `@studio-freight/lenis` is deprecated
- License: MIT

### Recommended options for premium feel
```ts
const lenis = new Lenis({
  duration: 1.2,                                  // wheel smoothing duration (s)
  easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),  // expo out
  smoothWheel: true,
  wheelMultiplier: 1,
  touchMultiplier: 1.5,
  // lerp: 0.1,       // alternative to duration
  // syncTouch: true, // smooth touch on mobile (can feel laggy — test)
});
```

### Integration with GSAP ScrollTrigger
```ts
lenis.on("scroll", ScrollTrigger.update);
const tickerCb = (time: number) => lenis.raf(time * 1000);
gsap.ticker.add(tickerCb);
gsap.ticker.lagSmoothing(0);

// Cleanup:
gsap.ticker.remove(tickerCb);
lenis.destroy();
```

### Full SmoothScroll provider
```tsx
"use client";
import { useEffect } from "react";
import Lenis from "lenis";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { usePathname } from "next/navigation";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

export function SmoothScroll({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      wheelMultiplier: 1,
      touchMultiplier: 1.5,
    });

    lenis.on("scroll", ScrollTrigger.update);
    const tickerCb = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(tickerCb);
    gsap.ticker.lagSmoothing(0);

    return () => {
      gsap.ticker.remove(tickerCb);
      lenis.destroy();
    };
  }, []);

  // Scroll to top on route change — Next.js doesn't do this automatically
  // for Lenis-wrapped sites.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return <>{children}</>;
}
```

### Lenis scrollTo for anchor links
```tsx
// If using Lenis, anchor links need manual handling:
const handleClick = (e: React.MouseEvent, id: string) => {
  e.preventDefault();
  const lenis = window.__lenis; // store reference globally or via context
  lenis?.scrollTo(id, { offset: -80, duration: 1.5 });
};
```

### Gotchas
- Don't initialize Lenis if `prefers-reduced-motion: reduce`.
- On route change in Next.js App Router, manually `lenis.scrollTo(0, { immediate: true })`.
- Don't combine Lenis with CSS `scroll-snap` — they fight.
- Don't combine Lenis with `scroll-behavior: smooth` in CSS — duplicate smoothing feels laggy.

---

## 4. Three.js + React Three Fiber + Drei + postprocessing

### Versions
- `three` → 0.185.1 (2026-07-01)
- `@react-three/fiber` → 9.6.1 (2026-04-28) — **R3F v9 is React-19-only**
- `@react-three/drei` → 10.7.7 (2025-11-13) — requires R3F v9
- `@react-three/postprocessing` → 3.0.4 (2025-02-20)
- License: MIT (all)

### When to use 3D on the web
✅ Use for: hero showpieces, shader gradient backgrounds, product configurators, data viz that genuinely needs 3D space.
❌ Don't use for: marketing fluff ("we need 3D because it looks cool"), entire sites that could be 2D, mobile-first sites with tight performance budgets.

### Performance budgets
- ≤ 60 draw calls in a hero scene (hard limit 120)
- ≤ 30 KB gzip shaders (custom GLSL) per scene
- ≤ 100K triangles on desktop, ≤ 30K on mobile
- Always provide a CSS gradient fallback for software-WebGL devices
- `frameloop="demand"` for static scenes — re-render only on interaction

### React 19 + Next.js 16 pattern (dynamic import with ssr:false shim)
```tsx
// components/HeroCanvasClient.tsx — "use client" shim
"use client";
import dynamic from "next/dynamic";
const HeroCanvas = dynamic(() => import("./HeroCanvas"), {
  ssr: false,
  loading: () => <div className="hero-fallback" />,
});
export default HeroCanvas;
```

```tsx
// app/page.tsx — Server Component
import HeroCanvas from "@/components/HeroCanvasClient";
export default function Page() {
  return (
    <main>
      <HeroCanvas />
    </main>
  );
}
```

### Full WebGL hero with shader + postprocessing
```tsx
// components/HeroCanvas.tsx
"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Environment } from "@react-three/drei";
import { EffectComposer, Bloom, Noise } from "@react-three/postprocessing";
import { useRef, useMemo, useEffect, useState } from "react";
import * as THREE from "three";

// Detect software WebGL (SwiftShader) and bail out
function isWebGLUsable() {
  if (typeof window === "undefined") return false;
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
  if (!gl) return false;
  const renderer = gl.getParameter(gl.RENDERER) ?? "";
  return !/SwiftShader|llvmpipe|Microsoft Basic Render/.test(renderer);
}

function ShaderMesh() {
  const matRef = useRef<THREE.ShaderMaterial>(null);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uColorA: { value: new THREE.Color("#4a90e2") },
      uColorB: { value: new THREE.Color("#e24a90") },
    }),
    []
  );

  useFrame((state) => {
    if (matRef.current) {
      matRef.current.uniforms.uTime.value = state.clock.elapsedTime;
    }
  });

  return (
    <mesh>
      <icosahedronGeometry args={[1.5, 64]} />
      <shaderMaterial
        ref={matRef}
        uniforms={uniforms}
        vertexShader={`
          varying vec3 vPos;
          uniform float uTime;
          // Simplex noise function (GLSL)
          vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
          vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
          vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
          vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
          float snoise(vec3 v) {
            const vec2 C = vec2(1.0/6.0, 1.0/3.0);
            const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
            vec3 i = floor(v + dot(v, C.yyy));
            vec3 x0 = v - i + dot(i, C.xxx);
            vec3 g = step(x0.yzx, x0.xyz);
            vec3 l = 1.0 - g;
            vec3 i1 = min(g.xyz, l.zxy);
            vec3 i2 = max(g.xyz, l.zxy);
            vec3 x1 = x0 - i1 + C.xxx;
            vec3 x2 = x0 - i2 + C.yyy;
            vec3 x3 = x0 - D.yyy;
            i = mod289(i);
            vec4 p = permute(permute(permute(
              i.z + vec4(0.0, i1.z, i2.z, 1.0))
              + i.y + vec4(0.0, i1.y, i2.y, 1.0))
              + i.x + vec4(0.0, i1.x, i2.x, 1.0));
            float n_ = 0.142857142857;
            vec3 ns = n_ * D.wyz - D.xzx;
            vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
            vec4 x_ = floor(j * ns.z);
            vec4 y_ = floor(j - 7.0 * x_);
            vec4 x = x_ * ns.x + ns.yyyy;
            vec4 y = y_ * ns.x + ns.yyyy;
            vec4 h = 1.0 - abs(x) - abs(y);
            vec4 b0 = vec4(x.xy, y.xy);
            vec4 b1 = vec4(x.zw, y.zw);
            vec4 s0 = floor(b0)*2.0 + 1.0;
            vec4 s1 = floor(b1)*2.0 + 1.0;
            vec4 sh = -step(h, vec4(0.0));
            vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
            vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
            vec3 p0 = vec3(a0.xy, h.x);
            vec3 p1 = vec3(a0.zw, h.y);
            vec3 p2 = vec3(a1.xy, h.z);
            vec3 p3 = vec3(a1.zw, h.w);
            vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
            p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
            vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
            m = m * m;
            return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
          }
          void main() {
            float n = snoise(position * 2.0 + uTime * 0.3);
            vPos = position + normal * n * 0.3;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(vPos, 1.0);
          }
        `}
        fragmentShader={`
          varying vec3 vPos;
          uniform vec3 uColorA;
          uniform vec3 uColorB;
          uniform float uTime;
          void main() {
            float t = sin(vPos.y * 3.0 + uTime) * 0.5 + 0.5;
            vec3 col = mix(uColorA, uColorB, t);
            gl_FragColor = vec4(col, 1.0);
          }
        `}
      />
    </mesh>
  );
}

export default function HeroCanvas() {
  const [usable, setUsable] = useState(true);

  useEffect(() => {
    setUsable(isWebGLUsable());
  }, []);

  if (!usable) return <div className="hero-fallback" />;

  return (
    <Canvas
      camera={{ position: [0, 0, 5], fov: 50 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true }}
    >
      <ambientLight intensity={0.4} />
      <directionalLight position={[5, 5, 5]} intensity={0.8} />
      <Float speed={2} rotationIntensity={0.5} floatIntensity={0.5}>
        <ShaderMesh />
      </Float>
      <Environment preset="city" />
      <EffectComposer>
        <Bloom intensity={0.5} luminanceThreshold={0.6} luminanceSmoothing={0.4} />
        <Noise opacity={0.04} />
      </EffectComposer>
    </Canvas>
  );
}
```

### Gotchas
- R3F v9 + React 19 Strict Mode mounts → unmounts → re-mounts in dev. Use `useGSAP({ revertOnUpdate: true })` and symmetric Effect cleanup.
- Always `dispose()` geometries and materials on unmount (R3F does this automatically in v9, but verify).
- Use `suspend: false` on `useTexture` if you don't want React Suspense to wrap the canvas.
- `dpr={[1, 2]}` caps device pixel ratio at 2 — never use unbounded `dpr` on retina.
- Avoid `@react-three/drei`'s heavier helpers (Text3D, useGLTF without suspense) — they balloon bundle size.
- Mobile: disable or simplify. Use `matchMedia("(max-width: 768px)")` to swap to a static gradient.

### Code-split to routes that need it
```tsx
// Only routes with a 3D hero import HeroCanvasClient.
// next/dynamic with ssr:false ensures ~600KB of three/R3F/drei never ships
// to routes without the canvas.
```

---

## 5. Lottie

### Packages
- `lottie-web` → 5.13.0 (low-level)
- `lottie-react` → 2.4.1 (React wrapper for `lottie-web`)
- `@lottiefiles/dotlottie-react` → 0.19.7 — **preferred** (`.lottie` is ~10× smaller than `.json`)
- License: MIT

### When to use
✅ Designer-authored micro-animations (icon hovers, success checkmarks, loaders)
❌ Long-form animations, anything that needs to be interactive or scrubbed by user input

### Basic usage (dotLottie)
```tsx
"use client";
import { DotLottieReact } from "@lottiefiles/dotlottie-react";

export function SuccessCheck() {
  return (
    <DotLottieReact
      src="/animations/success.lottie"
      loop
      autoplay
      style={{ width: 64, height: 64 }}
    />
  );
}
```

### Scroll-scrubbed Lottie (use lottie-web directly)
```tsx
"use client";
import { useEffect, useRef } from "react";
import lottie from "lottie-web";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { gsap } from "gsap";

gsap.registerPlugin(ScrollTrigger);

export function ScrollLottie({ path }: { path: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const anim = lottie.loadAnimation({
      container: containerRef.current!,
      path,
      loop: false,
      autoplay: false,
      renderer: "svg",
    });

    const st = ScrollTrigger.create({
      trigger: containerRef.current,
      start: "top 80%",
      end: "bottom 20%",
      scrub: true,
      onUpdate: (self) => {
        anim.goToAndStop(self.progress * anim.totalFrames, true);
      },
    });

    return () => {
      anim.destroy();
      st.kill();
    };
  }, [path]);

  return <div ref={containerRef} />;
}
```

### Performance
- `.lottie` (zipped) is ~10× smaller than `.json`
- Use `loop` and `autoplay` sparingly — autoplaying loops consume CPU even off-screen. Gate with IntersectionObserver.
- For scroll-scrubbed Lottie, use `lottie-web` directly with `goToAndStop(frame, true)` driven by `useScroll`.

---

## 6. Native browser APIs

### View Transitions API in Next.js 16
```ts
// next.config.ts
experimental: { viewTransition: true }
```

```tsx
// app/template.tsx
"use client";
import { unstable_ViewTransition } from "next";
import { motion } from "motion/react";

export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <unstable_ViewTransition>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -16 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        {children}
      </motion.div>
    </unstable_ViewTransition>
  );
}
```

Directional transitions via `transitionTypes`:
```tsx
import Link from "next/link";
<Link href="/work" transitionTypes={["forward"]}>Work</Link>
<Link href="/" transitionTypes={["back"]}>Home</Link>
```

```css
@media (prefers-reduced-motion: no-preference) {
  ::view-transition-old(root) { animation: 0.3s ease both slide-out-left; }
  ::view-transition-new(root) { animation: 0.3s ease both slide-in-right; }
  :active-view-transition-type(back) ::view-transition-old(root) {
    animation: 0.3s ease both slide-out-right;
  }
  :active-view-transition-type(back) ::view-transition-new(root) {
    animation: 0.3s ease both slide-in-from-left;
  }
}
```

### Intersection Observer (vanilla, universal)
```tsx
"use client";
import { useEffect, useRef, useState } from "react";

export function useInView<T extends HTMLElement>(options?: IntersectionObserverInit) {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([entry]) => {
      setInView(entry.isIntersecting);
    }, { threshold: 0.2, ...options });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return { ref, inView };
}
```

### Web Animations API (`Element.animate()`)
```ts
element.animate(
  [
    { transform: "translateY(40px)", opacity: 0 },
    { transform: "translateY(0)", opacity: 1 },
  ],
  { duration: 600, easing: "cubic-bezier(0.16, 1, 0.3, 1)", fill: "forwards" }
);
```
Runs off main thread where supported. Zero-dependency.

---

# Part VI — Next.js 16 App Router architecture

## Next.js version landscape (mid-2026, verified 2026-07-07)

- **Stable:** `next@16.2.10` (published 2026-07-01)
- **Backport:** `next@15.5.20` (for React 18 projects)
- React peer dep: `^19.2.0` (16.x) or `^18.2.0 || ^19.0.0` (15.x)
- **App Router is the default.** Pages Router still works but is no longer recommended.
- **Turbopack is stable** for dev and build in 16.x.
- **React Compiler 1.0 stable, opt-in** via `reactCompiler: true`. 16.3 adds experimental Rust port (`turbopackRustReactCompiler: true`) — 20-50% faster than Babel.
- **Server Components are the default** in `app/`. Client Components are opt-in via `'use client'`.

## Animation constraints in Server Components

Every animation library (Motion, GSAP, Lenis, R3F, Lottie) touches the DOM,
`window`, or `requestAnimationFrame`. These are not available in Server Components.

### Pattern: server-rendered page + client animation islands
```tsx
// app/page.tsx — Server Component
import { getProjects } from "@/lib/data";
import { ProjectShowcase } from "@/components/ProjectShowcase"; // "use client"

export default async function Page() {
  const projects = await getProjects();      // server-side data fetch
  return (
    <main>
      <h1>Work</h1>
      <ProjectShowcase projects={projects} />  {/* client island */}
    </main>
  );
}
```

```tsx
// components/ProjectShowcase.tsx — Client Component island
"use client";
import { motion } from "motion/react";
import { useEffect } from "react";

export function ProjectShowcase({ projects }: { projects: Project[] }) {
  // …animation logic…
  return <div>…</div>;
}
```

### `'use client'` boundary placement best practices
- **Push the boundary as far down the tree as possible.** A `'use client'` on a parent makes the entire subtree client-rendered.
- **One client boundary at the root for global providers** (Lenis, cursor, MotionConfig) — see provider stack below.
- **Don't wrap every page in `'use client'`** — you lose RSC streaming, data fetching, and bundle splitting.

### `next/dynamic` with `ssr: false` — heavy client-only mounts
`ssr: false` is **NOT allowed in Server Components** — wrap in a one-line client shim:
```tsx
// components/HeroCanvasClient.tsx
"use client";
import dynamic from "next/dynamic";
const HeroCanvas = dynamic(() => import("./HeroCanvas"), {
  ssr: false,
  loading: () => <div className="hero-fallback" />,
});
export default HeroCanvas;
```

```tsx
// app/page.tsx — Server Component
import HeroCanvas from "@/components/HeroCanvasClient";
export default function Page() {
  return <main><HeroCanvas /></main>;
}
```

### Suspense boundaries
```tsx
import { Suspense } from "react";
import { DesignedLoading } from "@/components/DesignedLoading";

export default function Page() {
  return (
    <main>
      <Suspense fallback={<DesignedLoading />}>
        <AsyncProjectList />
      </Suspense>
    </main>
  );
}
```
The `DesignedLoading` should look intentional — not a bare spinner.

## App Router file structure for an Awwwards-style site

```
app/
├── layout.tsx              # Server Component — <html>, <body>, fonts, metadata
├── providers.tsx           # "use client" — MotionConfig, SmoothScroll, CustomCursor, Preloader
├── template.tsx            # "use client" — page transition wrapper (re-mounts on nav)
├── globals.css             # Tailwind v4 @import, design tokens, easing variables
├── page.tsx                # Home (Server Component composing client islands)
├── work/
│   ├── page.tsx            # Work index
│   └── [slug]/page.tsx     # Case study detail
├── about/page.tsx
├── contact/page.tsx
├── loading.tsx             # Default route loading fallback
├── error.tsx               # Route error boundary (must be "use client")
├── not-found.tsx           # 404
└── opengraph-image.tsx     # Dynamic OG image via next/og
components/
├── SmoothScroll.tsx        # Lenis provider
├── CustomCursor.tsx        # Global cursor
├── MagneticButton.tsx      # Reusable magnetic button
├── Reveal.tsx              # Drop-in scroll reveal
├── Marquee.tsx             # Infinite marquee
├── Preloader.tsx           # Counter + curtain lift
├── ScrollProgress.tsx      # Top progress bar
├── nav/
│   ├── Navbar.tsx
│   └── MobileMenu.tsx
└── showcase/
    ├── PinnedGallery.tsx   # GSAP ScrollTrigger pinned horizontal gallery
    └── HeroCanvas.tsx      # R3F canvas (dynamically imported, ssr: false)
lib/
├── gsap.ts                 # Plugin registration + useGSAP setup
├── motion-variants.ts      # Shared Motion variants
└── utils.ts
public/
├── fonts/                  # Self-hosted fonts (if not using next/font)
├── models/                 # GLTF models for R3F
└── videos/                 # Hero video assets
```

## `app/layout.tsx` — root server layout

```tsx
import type { Metadata, Viewport } from "next";
import { Inter, Instrument_Serif } from "next/font/google";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-serif",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://example.com"),
  title: {
    default: "Studio — Award-winning design & development",
    template: "%s — Studio",
  },
  description: "We design and build award-winning websites, brands, and digital products.",
  openGraph: {
    title: "Studio",
    description: "Award-winning design & development.",
    type: "website",
    url: "https://example.com",
    siteName: "Studio",
  },
  twitter: { card: "summary_large_image", title: "Studio", description: "…" },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${serif.variable}`}
      suppressHydrationWarning
    >
      <body className="bg-bg text-fg antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

## `app/providers.tsx` — single client boundary

```tsx
"use client";
import { MotionConfig } from "motion/react";
import { SmoothScroll } from "@/components/SmoothScroll";
import { CustomCursor } from "@/components/CustomCursor";
import { Preloader } from "@/components/Preloader";
import { ScrollProgress } from "@/components/ScrollProgress";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig
      reducedMotion="user"
      transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.6 }}
    >
      <SmoothScroll>
        <ScrollProgress />
        <CustomCursor />
        <Preloader />
        {children}
      </SmoothScroll>
    </MotionConfig>
  );
}
```

## `app/template.tsx` — page transition wrapper

`template.tsx` re-mounts on every navigation (unlike `layout.tsx` which persists). This is the correct place for route transitions.

```tsx
"use client";
import { motion } from "motion/react";
import { unstable_ViewTransition } from "next";
import { useEffect, useRef } from "react";

const variants = {
  initial: { opacity: 0, y: 16 },
  enter: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
  exit: { opacity: 0, y: -16, transition: { duration: 0.4, ease: [0.83, 0, 0.17, 1] } },
};

export default function Template({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);

  // Move focus to the new page on route change so screen reader users know
  // where they are.
  useEffect(() => {
    ref.current?.focus();
  }, []);

  return (
    <unstable_ViewTransition>
      <motion.div
        ref={ref}
        tabIndex={-1}
        initial="initial"
        animate="enter"
        exit="exit"
        variants={variants}
        style={{ outline: "none" }}
      >
        {children}
      </motion.div>
    </unstable_ViewTransition>
  );
}
```

## `next.config.ts` — production config for animation sites

```ts
import type { NextConfig } from "next";
import withBundleAnalyzer from "@next/bundle-analyzer";

const nextConfig: NextConfig = {
  // React 19 stable, opt-in. Auto-memoizes.
  reactCompiler: true,

  // Mounts → unmounts → re-mounts every component in dev. Catches effect
  // cleanup bugs. Animation setup/teardown MUST be symmetric.
  reactStrictMode: true,

  images: {
    formats: ["image/avif", "image/webp"],
    qualities: [50, 75, 90],
    // remotePatterns: [{ protocol: "https", hostname: "cdn.example.com" }],
  },

  experimental: {
    // Enables <unstable_ViewTransition> and <Link transitionTypes>
    viewTransition: true,

    // Barrel-file optimization. Critical for animation libraries.
    optimizePackageImports: [
      "motion",
      "motion/react",
      "@react-three/drei",
      "@react-three/fiber",
      "lucide-react",
      "gsap",
    ],
  },

  // ─── Static export (uncomment for fully static marketing sites) ────────
  // output: "export",
  // trailingSlash: true,
  // images: { unoptimized: true },

  // ─── Self-host via Docker ──────────────────────────────────────────────
  // output: "standalone",
};

// Bundle analyzer — runs when ANALYZE=true npm run build
const analyzer = withBundleAnalyzer({ enabled: process.env.ANALYZE === "true" });

export default analyzer(nextConfig);
```

### Notes on each flag
- **`reactCompiler: true`** — automatic memoization. No more `useMemo`/`useCallback` boilerplate. Stable in React 19.
- **`reactStrictMode: true`** — mounts → unmounts → re-mounts in dev. Catches Effect cleanup bugs.
- **`images.formats: ["image/avif", "image/webp"]`** — AVIF where supported (40-50% smaller than WebP), WebP fallback.
- **`experimental.viewTransition: true`** — enables `<unstable_ViewTransition>` and `<Link transitionTypes>`. Safe to enable even if unused.
- **`experimental.optimizePackageImports`** — barrel-file optimization. Critical for `motion/react` and `@react-three/drei`.
- **`experimental.scrollRestoration` does NOT exist in Next 16 App Router** — it was Pages Router only. For Lenis-wrapped sites, manually `lenis.scrollTo(0, { immediate: true })` on route change.

## Hydration & layout shift prevention

### Avoiding layout shift during font load
1. Use `next/font` with `display: "swap"`.
2. Define a `@font-face` fallback with `size-adjust`:
```css
@font-face {
  font-family: "Inter Fallback";
  src: local("Arial");
  size-adjust: 100.5%;
  ascent-override: 90%;
  descent-override: 22%;
}
body { font-family: "Inter", "Inter Fallback", sans-serif; }
```

### Avoiding layout shift during image load
- Always pass `width` and `height` to `next/image` (or set `aspect-ratio` in CSS).
- Use `placeholder="blur"` with a `blurDataURL`.
- For dynamic images: use `plaiceholder` or `sharp` to generate blur placeholders server-side.

### `useLayoutEffect` vs `useEffect` warnings
Use `useGSAP` from `@gsap/react` (SSR-safe). For other libraries, use `useIsomorphicLayoutEffect`:
```ts
const useIsomorphicLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;
```

### `suppressHydrationWarning`
Use on `<html>` when toggling theme class via inline script. Don't use to silence legitimate hydration mismatches — those are bugs.

## Image optimization with `next/image`

```tsx
import Image from "next/image";

// LCP image — preload (NOT priority, which is deprecated in Next 16)
<Image
  src="/hero.jpg"
  alt="Hero"
  width={1920}
  height={1080}
  preload
  sizes="100vw"
  placeholder="blur"
  blurDataURL="data:image/jpeg;base64,…"  // or auto-generated
/>

// Below-the-fold image — no preload, responsive sizes
<Image
  src="/project-1.jpg"
  alt="Project"
  width={800}
  height={600}
  sizes="(max-width: 768px) 100vw, 50vw"
  placeholder="blur"
/>
```

> **`priority` is deprecated in Next 16 — use `preload` instead.** Same behavior.

## Font optimization with `next/font`

```tsx
import { Inter, Instrument_Serif } from "next/font/google";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});
```
- Self-hosted (no Google Fonts CDN → faster, privacy-friendly)
- Automatic subset optimization
- `display: "swap"` prevents FOIT
- Pair with `size-adjust` on `@font-face` fallbacks to eliminate FOUT layout shift

## Code splitting strategy

```
motion (~50KB)        → ship everywhere; it's the workhorse
gsap (~70KB core)     → ship everywhere; plugins are tree-shaken
@react-three/* (~600KB) → ONLY on routes with 3D, via next/dynamic ssr:false
@lottiefiles/* (~20KB) → ONLY on routes with Lottie, via dynamic import
```

## Deployment targets

### Vercel (default, best DX)
- Zero-config, Edge functions, Image optimization, ISR

### Self-host (Docker)
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```
Configure `output: "standalone"` in `next.config.ts`.

### Static export (`output: 'export'`)
For fully static marketing sites — no ISR, no server actions, no `next/image` optimization (`images: { unoptimized: true }`). Caveats:
- No dynamic OG images via `next/og`
- No middleware (no A/B tests)
- All routes must be statically discoverable

## Tailwind CSS v4 — CSS-first config

No `tailwind.config.js` needed. Use `@theme` in `globals.css`:

```css
@import "tailwindcss";

@theme {
  --color-bg: oklch(15% 0.02 250);
  --color-fg: oklch(95% 0.02 250);
  --color-accent: oklch(72% 0.18 250);
  --font-sans: var(--font-inter), system-ui, sans-serif;
  --font-serif: var(--font-instrument), Georgia, serif;
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out-quint: cubic-bezier(0.83, 0, 0.17, 1);
}
```

Setup: `@tailwindcss/postcss` in PostCSS config + `@import "tailwindcss"` in CSS.

## React 19-specific features

- **`use()` hook** — unwrap promises in components
- **`useOptimistic`** — instant UI feedback before server confirms
- **`useActionState`** — track pending state of server actions
- **React Compiler** — auto-memoization with `reactCompiler: true`
- **`<Activity>`** (stable in 19.2) — hide/show subtrees without unmounting. Effects fire `mode="hidden"` → `mode="visible"`. Animation setup/cleanup must be symmetric.
- **`<ViewTransition>`** — canary, but available in Next 16 via `experimental.viewTransition`

## `lib/gsap.ts` — shared GSAP setup

```ts
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";
import { useGSAP } from "@gsap/react";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger, SplitText, useGSAP);
}

export { gsap, ScrollTrigger, SplitText, useGSAP };

export function reducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export const eases = {
  outExpo: "expo.out",
  inOutQuint: "power4.inOut",
  anticipate: "back.out(1.7)",
} as const;
```

## `lib/motion-variants.ts` — shared Motion variants

```ts
import type { Variants } from "motion/react";

export const templateVariants: Variants = {
  initial: { opacity: 0, y: 16 },
  enter: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
  exit: { opacity: 0, y: -16, transition: { duration: 0.4, ease: [0.83, 0, 0.17, 1] } },
};

export const staggerContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 30 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.6 } },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.92 },
  show: { opacity: 1, scale: 1, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

export const clipReveal: Variants = {
  hidden: { opacity: 0, clipPath: "inset(0 0 100% 0)" },
  show: { opacity: 1, clipPath: "inset(0 0 0% 0)", transition: { duration: 0.8, ease: [0.83, 0, 0.17, 1] } },
};
```

---

# Part VII — Pattern catalog (50+ patterns with full code)

Every pattern includes: what it is, library, full implementation code, common mistakes, and performance budget.

## Category A — Scroll-driven animations

### Pattern 1: Smooth scroll with momentum (Lenis)

**What:** Wheel/touch smoothing that makes scroll feel like butter.
**Library:** Lenis (synced with GSAP ticker).
**Budget:** <0.5ms/frame.

See Part V §3 for the full `<SmoothScroll>` provider code.

**Mistakes:**
- Combining with `scroll-behavior: smooth` in CSS (double smoothing → laggy)
- Combining with CSS `scroll-snap` (they fight)
- Not scrolling to 0 on route change → Next.js scroll restoration breaks

### Pattern 2: Scroll-linked progress indicator

**What:** Top-of-page progress bar fills as user scrolls.
**Library:** CSS scroll-driven animations (preferred, zero JS) or Motion `useScroll`.

**CSS approach (zero JS):**
```css
.scroll-progress {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--color-accent);
  transform-origin: left;
  animation: grow-progress linear forwards;
  animation-timeline: scroll(root);
}
@keyframes grow-progress {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}
```

**Motion approach (universal fallback):**
```tsx
"use client";
import { motion, useScroll, useSpring } from "motion/react";

export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 30, restDelta: 0.001 });
  return (
    <motion.div
      style={{ scaleX }}
      className="fixed top-0 left-0 right-0 h-[2px] bg-accent origin-left z-50"
    />
  );
}
```

**Mistakes:** Running the Motion version on every scroll tick when CSS could do it for free.
**Budget:** CSS = 0ms (compositor). Motion = 0.5-1ms/frame.

### Pattern 3: Parallax scrolling (multi-layer depth)

**What:** Background layers move slower than foreground, creating depth.
**Library:** GSAP ScrollTrigger or Motion `useScroll` + `useTransform`.

**GSAP:**
```ts
gsap.to(".bg-layer", {
  yPercent: 30,
  ease: "none",
  scrollTrigger: {
    trigger: ".hero",
    start: "top top",
    end: "bottom top",
    scrub: true,
  },
});
```

**Motion:**
```tsx
"use client";
import { motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";

export function Parallax({ children, speed = 0.3 }) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], ["0%", `${-speed * 100}%`]);
  return (
    <div ref={ref} className="overflow-hidden">
      <motion.div style={{ y }}>{children}</motion.div>
    </div>
  );
}
```

**Mistakes:**
- Animating `background-position` instead of `transform: translateY` (forces paint)
- Going beyond ±50% parallax (looks fake)
- Not testing on 120Hz displays (scrub feels too fast)

**Budget:** 0.5ms/frame per layer (5 layers max).

### Pattern 4: Scroll-triggered reveals (fade / slide / scale / clip-path)

**What:** Content animates in as it enters viewport.

**Motion `whileInView`:**
```tsx
"use client";
import { motion } from "motion/react";

export function Reveal({ children, variant = "up", delay = 0, duration = 0.7, className }) {
  const variants = {
    up:    { initial: { opacity: 0, y: 40 }, animate: { opacity: 1, y: 0 } },
    fade:  { initial: { opacity: 0 }, animate: { opacity: 1 } },
    scale: { initial: { opacity: 0, scale: 0.92 }, animate: { opacity: 1, scale: 1 } },
    clip:  { initial: { opacity: 0, clipPath: "inset(0 0 100% 0)" }, animate: { opacity: 1, clipPath: "inset(0 0 0% 0)" } },
  };
  const v = variants[variant];
  return (
    <motion.div
      className={className}
      initial="initial"
      whileInView="animate"
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration, delay, ease: [0.16, 1, 0.3, 1] }}
      variants={v}
    >
      {children}
    </motion.div>
  );
}
```

**CSS-only (modern browsers, zero JS):**
```css
.reveal {
  animation: reveal-up linear forwards;
  animation-timeline: view();
  animation-range: entry 0% entry 80%;
}
@keyframes reveal-up {
  from { opacity: 0; transform: translateY(40px); }
  to { opacity: 1; transform: translateY(0); }
}
```

**Mistakes:**
- Using `once: false` (default) — re-animates every scroll, feels broken
- Adding reveal to too many elements — visual chaos
- Revealing above-the-fold content (it should be visible on load)

**Budget:** ~0.2ms/element on enter.

### Pattern 5: Pin & scrub (GSAP ScrollTrigger pinning)

**What:** A section pins in place while the user scrolls, scrubbing through a sequence.
**Library:** GSAP ScrollTrigger — Motion has no equivalent.

```tsx
"use client";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "@/lib/gsap";
import { useRef } from "react";

export function PinnedSequence() {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    if (reducedMotion()) return;
    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: container.current,
        start: "top top",
        end: "+=200%",         // pin for 2 viewport heights of scroll
        pin: true,
        scrub: 1,              // 1s smoothing
        invalidateOnRefresh: true,
      },
    });
    tl.to(".panel-1", { opacity: 0, duration: 1 })
      .to(".panel-2", { opacity: 1, duration: 1 }, "<")
      .to(".panel-2", { opacity: 0, duration: 1 })
      .to(".panel-3", { opacity: 1, duration: 1 }, "<");
  }, { scope: container, revertOnUpdate: true });

  return (
    <section ref={container} className="h-screen relative">
      <div className="panel-1 absolute inset-0">Panel 1</div>
      <div className="panel-2 absolute inset-0 opacity-0">Panel 2</div>
      <div className="panel-3 absolute inset-0 opacity-0">Panel 3</div>
    </section>
  );
}
```

**Mistakes:**
- **Pinning inside a `transform`ed ancestor** — the #1 ScrollTrigger bug. Audit ancestors for `transform`, `filter`, `perspective`, `will-change`.
- Missing `invalidateOnRefresh: true` — breaks on resize / font load / image load
- `scrub: true` (instant) feels janky; use `scrub: 1` for 1s smoothing
- Not setting `end` correctly — too short feels rushed, too long feels padded

**Budget:** 1-2ms/frame during the pinned section.

### Pattern 6: Horizontal scroll sections

**What:** Vertical scroll translates to horizontal panel movement.

```tsx
"use client";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "@/lib/gsap";
import { useRef } from "react";

export function HorizontalScroll({ panels }: { panels: string[] }) {
  const container = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    if (reducedMotion()) return;
    if (window.matchMedia("(max-width: 768px)").matches) return;

    const sections = gsap.utils.toArray<HTMLElement>(".panel");
    gsap.to(sections, {
      xPercent: -100 * (sections.length - 1),
      ease: "none",
      scrollTrigger: {
        trigger: container.current,
        pin: true,
        scrub: 1,
        end: () => `+=${container.current!.scrollWidth}`,
        invalidateOnRefresh: true,
      },
    });
  }, { scope: container, revertOnUpdate: true });

  return (
    <div ref={container} className="flex overflow-hidden">
      {panels.map((p, i) => (
        <div key={i} className="panel w-screen h-screen flex-shrink-0 flex items-center justify-center">
          {p}
        </div>
      ))}
    </div>
  );
}
```

**Mistakes:**
- Not accounting for scrollbar width on the pin spacer
- Mobile: horizontal scroll sections are nauseating — disable on touch

**Budget:** 1-2ms/frame.

### Pattern 7: Scroll-snap sections

**What:** Page snaps to section boundaries on scroll.
**Library:** Pure CSS.

```css
html { scroll-snap-type: y proximity; }
section { scroll-snap-align: start; scroll-snap-stop: always; }
```

**Mistakes:**
- `mandatory` is too aggressive for tall sections — use `proximity`
- Don't combine with Lenis — they fight

**Budget:** 0ms (browser native).

### Pattern 8: Scroll-triggered SVG path drawing

**What:** SVG path "draws itself" as it enters view.
**Library:** GSAP DrawSVGPlugin (free).

```tsx
"use client";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger, DrawSVGPlugin } from "@/lib/gsap";
import { useRef } from "react";

gsap.registerPlugin(DrawSVGPlugin);

export function SvgDraw({ paths }: { paths: string[] }) {
  const ref = useRef<SVGSVGElement>(null);
  useGSAP(() => {
    if (reducedMotion()) return;
    gsap.from("path", {
      drawSVG: "0%",
      ease: "none",
      stagger: 0.2,
      duration: 2,
      scrollTrigger: { trigger: ref.current, start: "top 70%", end: "bottom 30%", scrub: true },
    });
  }, { scope: ref });
  return (
    <svg ref={ref} viewBox="0 0 800 400">
      {paths.map((d, i) => <path key={i} d={d} fill="none" stroke="currentColor" strokeWidth="2" />)}
    </svg>
  );
}
```

**Mistakes:**
- Forgetting `drawSVG: "0%"` (start) vs `drawSVG: 0` (length in px)
- Not using `ease: "none"` for draw — eased draw looks weird

**Budget:** 0.5ms/frame.

### Pattern 9: Sticky/pinned hero that dissolves into next section

**What:** Hero stays put while next section slides up over it (Apple product pages).

```css
.hero { position: sticky; top: 0; height: 100vh; z-index: 1; }
.next-section { position: relative; z-index: 2; background: var(--color-bg); }
```

```tsx
"use client";
import { motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";

export function StickyHero({ children }) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const opacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.8], [1, 0.95]);
  return (
    <motion.div ref={ref} style={{ opacity, scale }} className="hero sticky top-0 h-screen z-1">
      {children}
    </motion.div>
  );
}
```

**Budget:** ~1ms/frame (single transform).

### Pattern 10: Image sequence scroll scrub (Apple AirPods-style)

**What:** User scrolls through a sequence of frames.
**Library:** GSAP ScrollTrigger + `<canvas>` + preloaded images.

```tsx
"use client";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "@/lib/gsap";
import { useEffect, useRef } from "react";

export function ImageSequence({ frameCount, folder }: { frameCount: number; folder: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imagesRef = useRef<HTMLImageElement[]>([]);

  useEffect(() => {
    // Preload all frames
    const imgs: HTMLImageElement[] = [];
    for (let i = 0; i < frameCount; i++) {
      const img = new Image();
      img.src = `${folder}/frame-${String(i + 1).padStart(4, "0")}.jpg`;
      imgs.push(img);
    }
    imagesRef.current = imgs;
  }, [frameCount, folder]);

  useGSAP(() => {
    if (reducedMotion()) return;
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;

    const render = (frame: number) => {
      const img = imagesRef.current[Math.floor(frame)];
      if (img?.complete) ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    };

    const obj = { frame: 0 };
    gsap.to(obj, {
      frame: frameCount - 1,
      snap: "frame",
      ease: "none",
      scrollTrigger: {
        trigger: canvas,
        start: "top top",
        end: "+=300%",
        scrub: 0.5,
        pin: true,
        onUpdate: () => render(obj.frame),
      },
    });
  }, { scope: canvasRef });

  return <canvas ref={canvasRef} width={1920} height={1080} className="w-full h-screen object-cover" />;
}
```

**Mistakes:**
- Using `<video>` — Apple uses image sequences because videos can't scrub in sync with scroll
- Not preloading → first scroll shows blank canvas
- Too many frames (>150) → memory blowup. Aim for 60-100

**Budget:** 1-2ms/frame (canvas draw).

### Pattern 11: Lottie on scroll

**What:** Lottie plays frame-by-frame tied to scroll.
**Library:** `lottie-web` directly (not `dotlottie-react` for this).

```tsx
"use client";
import { useEffect, useRef } from "react";
import lottie from "lottie-web";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

export function ScrollLottie({ path }: { path: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (reducedMotion()) return;
    const anim = lottie.loadAnimation({
      container: ref.current!, path, loop: false, autoplay: false, renderer: "svg",
    });
    const st = ScrollTrigger.create({
      trigger: ref.current, start: "top 80%", end: "bottom 20%", scrub: true,
      onUpdate: (self) => anim.goToAndStop(self.progress * anim.totalFrames, true),
    });
    return () => { anim.destroy(); st.kill(); };
  }, [path]);
  return <div ref={ref} />;
}
```

## Category B — Hover & interaction

### Pattern 12: Magnetic buttons

**What:** Button leans toward cursor when cursor is within ~100px.
**Library:** Motion `useMotionValue` + `useSpring`.

See Part V §1 for full `<MagneticButton>` code.

**Mistakes:**
- Not disabling on touch (`@media (pointer: coarse)`)
- Strength >0.5 feels broken — the button never returns

**Budget:** 0.5ms/hover event.

### Pattern 13: Custom cursor with hover state changes

**What:** OS cursor hidden; custom cursor follows pointer with spring smoothing, swaps label/scale on hover over interactive elements.
**Library:** Motion + `mix-blend-mode: difference`.

```tsx
"use client";
import { useEffect, useState } from "react";
import { motion, useMotionValue, useSpring } from "motion/react";

type CursorVariant = "default" | "hover" | "view" | "drag";

export function CustomCursor() {
  const [variant, setVariant] = useState<CursorVariant>("default");
  const [hidden, setHidden] = useState(true);
  const cursorX = useMotionValue(-100);
  const cursorY = useMotionValue(-100);
  const springConfig = { damping: 25, stiffness: 350, mass: 0.5 };
  const x = useSpring(cursorX, springConfig);
  const y = useSpring(cursorY, springConfig);

  useEffect(() => {
    const finePointer = window.matchMedia("(pointer: fine)");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!finePointer.matches || reducedMotion.matches) return;

    setHidden(false);

    const move = (e: MouseEvent) => {
      cursorX.set(e.clientX);
      cursorY.set(e.clientY);
    };
    const over = (e: MouseEvent) => {
      const target = (e.target as HTMLElement)?.closest(
        "a, button, [data-cursor], input, textarea, select, [role='button']"
      );
      if (target) {
        const cursorAttr = target.getAttribute("data-cursor");
        setVariant((cursorAttr as CursorVariant) ?? "hover");
      } else {
        setVariant("default");
      }
    };
    const leave = () => setHidden(true);
    const enter = () => setHidden(false);

    window.addEventListener("mousemove", move, { passive: true });
    document.addEventListener("mouseover", over, { passive: true });
    document.addEventListener("mouseleave", leave);
    document.addEventListener("mouseenter", enter);

    return () => {
      window.removeEventListener("mousemove", move);
      document.removeEventListener("mouseover", over);
      document.removeEventListener("mouseleave", leave);
      document.removeEventListener("mouseenter", enter);
    };
  }, [cursorX, cursorY]);

  if (hidden) return null;

  return (
    <motion.div
      aria-hidden="true"
      className="custom-cursor"
      style={{ x, y }}
      animate={{
        scale: variant === "default" ? 1 : variant === "hover" ? 1.5 : 2.5,
        opacity: 1,
      }}
      transition={{ type: "spring", damping: 20, stiffness: 300 }}
    >
      <span className="custom-cursor-label">
        {variant === "view" && "View"}
        {variant === "drag" && "Drag"}
      </span>
    </motion.div>
  );
}
```

CSS:
```css
@media (pointer: fine) {
  body.custom-cursor-active { cursor: none; }
  body.custom-cursor-active a,
  body.custom-cursor-active button { cursor: none; }
}
.custom-cursor {
  position: fixed;
  top: 0; left: 0;
  width: 24px; height: 24px;
  border-radius: 50%;
  background: white;
  mix-blend-mode: difference;
  pointer-events: none;
  z-index: 9999;
  translate: -50% -50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
```

**Mistakes:**
- Cursor on touch devices — broken UX
- `pointer-events: auto` on the cursor — blocks clicks
- Forgetting `mix-blend-mode: difference` makes it invisible on white backgrounds

**Budget:** 0.3ms/frame.

### Pattern 14: Image hover reveals (clip-path / scale / overlay)

**What:** Image reacts on hover — clip-path wipes, scale, color overlay.
**Library:** Pure CSS.

```css
.card { overflow: hidden; }
.card img {
  transition: transform 0.7s var(--ease-out-expo), clip-path 0.7s var(--ease-out-expo);
  clip-path: inset(0 0 100% 0);
}
.card:hover img {
  transform: scale(1.05);
  clip-path: inset(0 0 0 0);
}
```

**Budget:** 0ms (compositor).

### Pattern 15: Link hover with animated underline

```css
.link { position: relative; display: inline-block; }
.link::after {
  content: "";
  position: absolute;
  left: 0; right: 0; bottom: -2px;
  height: 1px;
  background: currentColor;
  transform: scaleX(0);
  transform-origin: right;
  transition: transform 0.4s var(--ease-out-expo);
}
.link:hover::after { transform: scaleX(1); transform-origin: left; }
```

### Pattern 16: Link hover with text swap

```css
.link {
  position: relative;
  overflow: hidden;
  display: inline-block;
  height: 1em;
}
.link .text {
  display: block;
  transition: transform 0.4s var(--ease-out-expo);
}
.link .text-alt {
  position: absolute;
  inset: 0;
  transform: translateY(100%);
}
.link:hover .text { transform: translateY(-100%); }
.link:hover .text-alt { transform: translateY(0); }
```

### Pattern 17: Card 3D tilt

**What:** Card tilts in 3D toward cursor.
**Library:** Vanilla JS (5 lines). Don't pull in Atropos for a card grid.

```tsx
"use client";
export function TiltCard({ children }: { children: React.ReactNode }) {
  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (window.matchMedia("(pointer: coarse)").matches) return;
    const r = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    e.currentTarget.style.transform =
      `perspective(800px) rotateY(${px * 12}deg) rotateX(${-py * 12}deg)`;
  };
  const onLeave = (e: React.MouseEvent<HTMLDivElement>) => {
    e.currentTarget.style.transform = "";
  };
  return (
    <div
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ transition: "transform 0.4s var(--ease-out-expo)", transformStyle: "preserve-3d" }}
      className="card"
    >
      {children}
    </div>
  );
}
```

**Mistakes:**
- Tilt >15° looks gimmicky
- No transition → jittery

**Budget:** 0.2ms/frame.

### Pattern 18: Tooltip follow-cursor

```tsx
"use client";
import { motion, useMotionValue } from "motion/react";

export function FollowTooltip({ children, label }: { children: React.ReactNode; label: string }) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  return (
    <div
      className="relative inline-block"
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        x.set(e.clientX - r.left);
        y.set(e.clientY - r.top);
      }}
    >
      {children}
      <motion.div
        style={{ x, y }}
        className="pointer-events-none absolute z-50 hidden group-hover:block"
      >
        {label}
      </motion.div>
    </div>
  );
}
```

### Pattern 19: Hover-activated video preview (Awwwards site list)

**What:** List items show a small video preview on hover.
**Library:** One shared `<video>` element swapped on hover — NOT one per item.

```tsx
"use client";
import { useRef, useState } from "react";

export function HoverVideoList({ items }: { items: { title: string; video: string }[] }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [visible, setVisible] = useState(false);
  const [current, setCurrent] = useState("");

  const handleEnter = (item: { title: string; video: string }, e: React.MouseEvent) => {
    if (videoRef.current) {
      videoRef.current.src = item.video;
      videoRef.current.play();
    }
    setCurrent(item.title);
    setVisible(true);
  };

  const handleMove = (e: React.MouseEvent) => {
    setPos({ x: e.clientX, y: e.clientY });
  };

  const handleLeave = () => {
    setVisible(false);
    if (videoRef.current) videoRef.current.pause();
  };

  return (
    <div onMouseMove={handleMove} onMouseLeave={handleLeave}>
      {items.map((item) => (
        <div
          key={item.title}
          onMouseEnter={(e) => handleEnter(item, e)}
          className="py-8 border-b border-border hover:px-8 transition-all"
        >
          {item.title}
        </div>
      ))}
      <video
        ref={videoRef}
        muted
        loop
        playsInline
        className="fixed pointer-events-none z-50 w-64 h-40 object-cover rounded-lg"
        style={{
          left: pos.x + 20,
          top: pos.y - 80,
          opacity: visible ? 1 : 0,
          transition: "opacity 0.3s ease",
        }}
      />
    </div>
  );
}
```

**Mistakes:**
- One `<video>` per item → 30+ decoders, ~95 MB GPU memory gone
- Not pausing on hover-leave → audio bleeds between items

**Budget:** 1ms/hover (decoder swap).

### Pattern 20: Marquee on hover (pause/play)

See Part VIII component library for full `<Marquee>` code.

### Pattern 21: Cursor blend mode

**What:** Cursor uses `mix-blend-mode: difference` so it inverts whatever's underneath.
**Library:** Pure CSS, paired with Pattern 13.

## Category C — Page transitions

### Pattern 22: Route transitions in Next.js App Router

**What:** Smooth transition between routes — not just a hard cut.
**Library:** Motion `AnimatePresence` + `app/template.tsx`, OR native View Transitions API.

See Part VI for full `template.tsx` code.

**Mistakes:**
- Using `app/layout.tsx` for transitions — layouts DON'T re-mount on navigation. Use `template.tsx`.
- AnimatePresence wrapping the wrong scope
- Not handling scroll-to-top on route change

**Budget:** ~0.5ms for the duration of the transition.

### Pattern 23: Overlay curtain transitions

**What:** Full-screen panel slides in, covers the page, then slides out revealing the new page.

```tsx
"use client";
import { AnimatePresence, motion } from "motion/react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

export function CurtainTransition() {
  const pathname = usePathname();
  const [transitioning, setTransitioning] = useState(false);

  // Detect route change → show curtain → hide after 500ms
  useEffect(() => {
    setTransitioning(true);
    const t = setTimeout(() => setTransitioning(false), 800);
    return () => clearTimeout(t);
  }, [pathname]);

  return (
    <AnimatePresence>
      {transitioning && (
        <motion.div
          className="fixed inset-0 z-[9999] bg-fg"
          initial={{ clipPath: "inset(0 0 100% 0)" }}
          animate={{ clipPath: "inset(0 0 0% 0)" }}
          exit={{ clipPath: "inset(100% 0 0 0)" }}
          transition={{ duration: 0.4, ease: [0.83, 0, 0.17, 1] }}
        />
      )}
    </AnimatePresence>
  );
}
```

### Pattern 24: Clip-path page wipes

**What:** New page reveals via `clip-path` wipe (circle, polygon, or directional).

```tsx
"use client";
import { motion } from "motion/react";

export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ clipPath: "circle(0% at 50% 50%)" }}
      animate={{ clipPath: "circle(150% at 50% 50%)" }}
      transition={{ duration: 1, ease: [0.83, 0, 0.17, 1] }}
    >
      {children}
    </motion.div>
  );
}
```

**Budget:** ~1ms/frame during the wipe.

### Pattern 25: Stagger content reveal on route change

**What:** After page transition, child elements stagger in.

```tsx
"use client";
import { motion } from "motion/react";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.2 } },
};
const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <motion.div variants={container} initial="hidden" animate="show">
      {children}
    </motion.div>
  );
}
```

### Pattern 26: Preloader with progress

**What:** Page shows a counter 0→100% then lifts a curtain, revealing the page.
**Library:** Custom (don't fake the counter).

```tsx
"use client";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

export function Preloader() {
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setEnabled(false);
      setDone(true);
      return;
    }
    document.body.style.overflow = "hidden";

    // Track LCP via PerformanceObserver
    const obs = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const last = entries[entries.length - 1];
      if (last.startTime + last.renderTime < performance.now()) setProgress(100);
    });
    try {
      obs.observe({ type: "largest-contentful-paint", buffered: true });
    } catch {
      setTimeout(() => setProgress(100), 1500);
    }

    const safety = setTimeout(() => setProgress(100), 4000);
    const interval = setInterval(() => {
      setProgress((p) => (p >= 90 ? p : Math.min(90, p + Math.random() * 8 + 2)));
    }, 100);

    return () => { obs.disconnect(); clearTimeout(safety); clearInterval(interval); };
  }, []);

  useEffect(() => {
    if (progress < 100) return;
    const t = setTimeout(() => {
      setDone(true);
      document.body.style.overflow = "";
    }, 400);
    return () => clearTimeout(t);
  }, [progress]);

  if (!enabled) return null;

  return (
    <AnimatePresence>
      {!done && (
        <motion.div
          className="preloader"
          initial={{ clipPath: "inset(0 0 0 0)" }}
          exit={{ clipPath: "inset(0 0 100% 0)", transition: { duration: 0.9, ease: [0.83, 0, 0.17, 1] } }}
        >
          <div className="preloader-content">
            <motion.span className="preloader-count" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {Math.round(progress)}
            </motion.span>
            <span className="preloader-percent">%</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

**Mistakes:**
- **Faking the counter** — users notice when it sits at 87% then jumps to 100% while assets still load
- Counter too fast (finishes before LCP) or too slow (artificial delay)

## Category D — Text animations

### Pattern 27: Character/word stagger reveal

**What:** Heading reveals character-by-character or word-by-word.
**Library:** GSAP SplitText (free, preferred).

See Part V §2 for full `<HeadingReveal>` code.

**Mistakes:**
- **Not reverting SplitText** — duplicated text on re-render in Strict Mode. Use `useGSAP({ revertOnUpdate: true })`.
- Splitting on every render
- `type: "chars"` only (without `words`) — breaks for languages without spaces

**Budget:** 0.5ms for the entrance.

### Pattern 28: Text mask with image background

**What:** Text is filled with an image via `background-clip: text`.
**Library:** Pure CSS.

```css
.masked-text {
  background: url("/hero.jpg") center/cover;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
```

### Pattern 29: Marquee text scrollers (infinite, smooth)

See Pattern 20 / Part VIII.

### Pattern 30: Typewriter effect

**What:** Text types itself out character-by-character.

```tsx
"use client";
import { useEffect, useState } from "react";

export function Typewriter({ text, speed = 60 }: { text: string; speed?: number }) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    let i = 0;
    const tick = () => {
      setDisplayed(text.slice(0, ++i));
      if (i < text.length) {
        setTimeout(tick, speed + Math.random() * 40);
      } else {
        setDone(true);
      }
    };
    tick();
  }, [text, speed]);

  return (
    <span>
      {displayed}
      {!done && <span className="animate-pulse">|</span>}
    </span>
  );
}
```

**Mistakes:** Fixed timing — randomize for realism.

### Pattern 31: Text scramble effect

**What:** Text scrambles through random characters before settling on final text.
**Library:** GSAP ScrambleTextPlugin (free).

```tsx
"use client";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrambleTextPlugin } from "gsap/ScrambleTextPlugin";
import { useRef } from "react";

gsap.registerPlugin(ScrambleTextPlugin);

export function ScrambleText({ text }: { text: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  useGSAP(() => {
    gsap.to(ref.current, {
      duration: 1.5,
      scrambleText: text,
      chars: "01",
      ease: "none",
    });
  }, { dependencies: [text] });
  return <span ref={ref}>{text}</span>;
}
```

### Pattern 32: Split text on scroll with rotation/skew per character

**What:** Heading's characters rotate/skew into place on scroll.

```tsx
useGSAP(() => {
  if (reducedMotion()) return;
  const split = SplitText.create(ref.current!, { type: "chars" });
  gsap.from(split.chars, {
    rotation: 90,
    y: 80,
    opacity: 0,
    stagger: 0.03,
    scrollTrigger: { trigger: ref.current, start: "top 80%", scrub: 1 },
  });
}, { scope: ref, revertOnUpdate: true });
```

## Category E — Image/media

### Pattern 33: Image reveal on scroll (clip-path wipe + scale-from-1.15)

**What:** Image starts at scale 1.15 inside a clip-path mask, then clip-path reveals it as scale settles to 1.

```tsx
"use client";
import { motion } from "motion/react";

export function ImageReveal({ src, alt }: { src: string; alt: string }) {
  return (
    <motion.div
      className="img-wrapper overflow-hidden"
      initial={{ clipPath: "inset(100% 0 0 0)" }}
      whileInView={{ clipPath: "inset(0% 0 0 0)" }}
      viewport={{ once: true }}
      transition={{ duration: 1, ease: [0.83, 0, 0.17, 1] }}
    >
      <motion.img
        src={src}
        alt={alt}
        initial={{ scale: 1.15 }}
        whileInView={{ scale: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
      />
    </motion.div>
  );
}
```

### Pattern 34: Ken Burns effect (slow zoom on still images)

**What:** Image slowly zooms over many seconds for a documentary feel.
**Library:** Pure CSS.

```css
@keyframes ken-burns {
  0%   { transform: scale(1) translate(0, 0); }
  100% { transform: scale(1.1) translate(-2%, 1%); }
}
.ken { animation: ken-burns 20s ease-out forwards; }
```

### Pattern 35: WebGL shader backgrounds

**What:** Animated shader (gradient mesh, noise, fluid) as a hero background.
**Library:** Three.js + custom GLSL.

See Part V §4 for full `<HeroCanvas>` code with simplex noise shader.

**Mistakes:**
- Heavy shader on mobile — kill on `(max-width: 768px)`
- No fallback → broken on older devices

**Budget:** 4-8ms/frame on desktop, kill on mobile.

### Pattern 36: Distortion hover on images

**What:** Image distorts (RGB shift, displacement map) on hover.
**Library:** WebGL for serious distortion; CSS `filter: hue-rotate()` for cheap.

```css
.img:hover { filter: hue-rotate(20deg) saturate(1.5); }
```

### Pattern 37: Picture-perfect lazy loading with blur-up

**What:** Image starts as a blurred low-res placeholder, sharpens when loaded.
**Library:** `next/image` with `placeholder="blur"`.

```tsx
import Image from "next/image";
<Image src="/hero.jpg" alt="…" width={1920} height={1080} placeholder="blur" blurDataURL="data:image/jpeg;base64,…" />
```

For dynamic images, generate the blur placeholder server-side with `plaiceholder` or `sharp`.

## Category F — Layout & micro-interactions

### Pattern 38: Magnetic menu items

Same as Pattern 12, applied to nav links.

### Pattern 39: Burger menu → fullscreen overlay with stagger

**What:** Click hamburger → fullscreen overlay slides in, nav links stagger in.

```tsx
"use client";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

const links = ["Home", "Work", "About", "Contact"];
const container = { hidden: {}, show: { transition: { staggerChildren: 0.08, delayChildren: 0.3 } } };
const item = { hidden: { opacity: 0, y: 40 }, show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } } };

export function FullscreenMenu() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)} className="fixed top-8 right-8 z-50">
        Menu
      </button>
      <AnimatePresence>
        {open && (
          <motion.nav
            className="fixed inset-0 z-[100] bg-bg flex items-center"
            initial={{ clipPath: "circle(0% at 100% 0%)" }}
            animate={{ clipPath: "circle(150% at 100% 0%)" }}
            exit={{ clipPath: "circle(0% at 100% 0%)" }}
            transition={{ duration: 0.6, ease: [0.83, 0, 0.17, 1] }}
          >
            <button onClick={() => setOpen(false)} className="absolute top-8 right-8">Close</button>
            <motion.ul variants={container} initial="hidden" animate="show" className="container-editorial">
              {links.map((l) => (
                <motion.li key={l} variants={item} className="font-serif text-6xl py-4">
                  <a href={`/${l.toLowerCase()}`}>{l}</a>
                </motion.li>
              ))}
            </motion.ul>
          </motion.nav>
        )}
      </AnimatePresence>
    </>
  );
}
```

### Pattern 40: Modal/drawer with spring physics

**What:** Bottom drawer with realistic drag-to-dismiss.
**Library:** Vaul.

```tsx
"use client";
import { Drawer } from "vaul";

export function BottomDrawer({ trigger, children }: { trigger: React.ReactNode; children: React.ReactNode }) {
  return (
    <Drawer.Root>
      <Drawer.Trigger asChild>{trigger}</Drawer.Trigger>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 bg-black/40 z-40" />
        <Drawer.Content className="fixed bottom-0 left-0 right-0 z-50 bg-bg rounded-t-3xl p-6 max-h-[80vh] overflow-y-auto">
          <div className="w-12 h-1 bg-fg-muted rounded-full mx-auto mb-6" />
          {children}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
```

### Pattern 41: Form input micro-animations

**What:** Floating labels, glow on focus, success checkmark.
**Library:** Pure CSS for the float.

```css
.field { position: relative; }
.field input {
  padding: 1.5rem 1rem 0.5rem;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  width: 100%;
  transition: border-color 0.3s ease;
}
.field input:focus {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px color-mix(in oklab, var(--color-accent) 20%, transparent);
}
.field label {
  position: absolute;
  left: 1rem; top: 1rem;
  pointer-events: none;
  transition: all 0.2s var(--ease-out-expo);
  color: var(--color-fg-muted);
}
.field input:focus + label,
.field input:not(:placeholder-shown) + label {
  top: 0.4rem;
  font-size: 0.75rem;
  color: var(--color-accent);
}
```

### Pattern 42: Tab transitions with layout animations

**What:** Active tab indicator slides between tabs (Magic Motion).
**Library:** Motion `layoutId`.

See Part V §1 for full `<Tabs>` code.

### Pattern 43: Accordion with smooth height animation

**What:** Accordion smoothly expands/collapses.
**Library:** CSS `interpolate-size: allow-keywords` (modern) or `grid-template-rows: 0fr → 1fr` (universal fallback).

**Modern:**
```css
.acc { interpolate-size: allow-keywords; }
.acc-body { height: 0; transition: height 0.4s var(--ease-out-expo); }
.acc[data-open] .acc-body { height: auto; }
```

**Universal fallback:**
```css
.acc-body {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.4s var(--ease-out-expo);
}
.acc[data-open] .acc-body { grid-template-rows: 1fr; }
.acc-body > div { overflow: hidden; }
```

### Pattern 44: Number counter / odometer on scroll into view

**What:** Number animates from 0 to target when scrolled into view.

```tsx
"use client";
import { animate, useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";

export function Counter({ to, duration = 2 }: { to: number; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const [val, setVal] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const controls = animate(0, to, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setVal(v),
    });
    return () => controls.stop();
  }, [inView, to, duration]);

  return (
    <span ref={ref} aria-label={`${to}`}>
      <span aria-hidden="true">{Math.round(val).toLocaleString()}</span>
    </span>
  );
}
```

**Accessibility:** Add `aria-label={`${to}`}` so screen readers announce the final value, not the animation.

### Pattern 45: Theme switcher with View Transitions API

**What:** Theme toggle crossfades the whole page.

```tsx
"use client";
import { useState } from "react";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("dark");

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    if (!document.startViewTransition) {
      setTheme(next);
      return;
    }
    document.startViewTransition(() => {
      setTheme(next);
    });
  };

  return <button onClick={toggle}>Toggle theme</button>;
}
```

### Pattern 46: Sound design on hover/scroll

**What:** Subtle hover/click sounds via Web Audio API.
**Library:** Web Audio API directly.
**Default:** OFF. Gate behind explicit opt-in toggle.

```tsx
"use client";
import { useEffect, useRef, useState } from "react";

export function useSound() {
  const [enabled, setEnabled] = useState(false);
  const ctxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (!enabled) return;
    ctxRef.current = new AudioContext();
    return () => ctxRef.current?.close();
  }, [enabled]);

  const play = (freq = 800, duration = 0.1) => {
    if (!enabled || !ctxRef.current) return;
    const ctx = ctxRef.current;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.05, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  };

  return { enabled, setEnabled, play };
}
```

## Category G — Loading

### Pattern 47: Skeleton shimmer with premium feel

```css
.skeleton {
  background: linear-gradient(90deg, var(--color-bg-elevated) 25%, var(--color-bg) 50%, var(--color-bg-elevated) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite linear;
  border-radius: 4px;
}
@keyframes shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}
```

### Pattern 48: Preloader sequences

See Pattern 26.

### Pattern 49: Suspense fallbacks that feel intentional

```tsx
import { Suspense } from "react";
import { DesignedLoading } from "@/components/DesignedLoading";

export default function Page() {
  return (
    <main>
      <Suspense fallback={<DesignedLoading />}>
        <AsyncProjectList />
      </Suspense>
    </main>
  );
}
```

## Category H — Mobile-specific

### Pattern 50: Touch-friendly magnetic disabled

```css
@media (pointer: coarse) {
  .magnetic { transform: none !important; }
}
```
Or in JS: `if (window.matchMedia("(pointer: coarse)").matches) return;`

### Pattern 51: Haptic feedback via Vibration API

```ts
function onClick() {
  navigator.vibrate?.(10);
  // do the thing
}
```
Works on Android Chrome. No-op on iOS Safari — don't make it required.

### Pattern 52: Mobile menu slide-in with gesture close

**Library:** Vaul for the drawer, or Motion `drag="y"` with `dragConstraints`.

```tsx
"use client";
import { motion } from "motion/react";
import { useState } from "react";

export function SlideInMenu({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <motion.nav
      className="fixed top-0 right-0 h-full w-80 bg-bg z-50"
      initial={{ x: "100%" }}
      animate={{ x: open ? 0 : "100%" }}
      transition={{ type: "spring", damping: 25, stiffness: 200 }}
      drag="x"
      dragConstraints={{ left: 0, right: 300 }}
      dragElastic={0.4}
      onDragEnd={(_, info) => { if (info.offset.x > 100) setOpen(false); }}
    >
      <button onClick={() => setOpen(!open)}>Toggle</button>
      {children}
    </motion.nav>
  );
}
```

### Pattern 53: Responsive reduced-motion fallback

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```
Plus in JS: don't init Lenis, don't init ScrollTrigger pinning, etc.

---

# Part VIII — Full component library (copy-paste ready)

Every component below is production-ready. Copy into `components/`, import, use.

## globals.css — complete design system

```css
@import "tailwindcss";

@theme {
  /* Colors — oklch */
  --color-bg:           oklch(15% 0.02 250);
  --color-bg-elevated:  oklch(20% 0.02 250);
  --color-fg:           oklch(95% 0.02 250);
  --color-fg-muted:     oklch(60% 0.02 250);
  --color-accent:       oklch(72% 0.18 250);
  --color-accent-warm:  oklch(72% 0.18 30);
  --color-border:       oklch(95% 0.02 250 / 8%);

  /* Fonts */
  --font-sans:  var(--font-inter), system-ui, -apple-system, sans-serif;
  --font-serif: var(--font-instrument), Georgia, serif;

  /* Easings — three site-wide tokens */
  --ease-out-expo:      cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out-quint:  cubic-bezier(0.83, 0, 0.17, 1);
  --ease-anticipate:    cubic-bezier(0.68, -0.55, 0.27, 1.55);
  --ease-out-back:      cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-out-quart:     cubic-bezier(0.25, 1, 0.5, 1);
  --ease-in-out-circ:   cubic-bezier(0.85, 0, 0.15, 1);

  /* Durations */
  --duration-instant: 100ms;
  --duration-fast:    200ms;
  --duration-normal:  400ms;
  --duration-md:      600ms;
  --duration-slow:    900ms;
  --duration-slower:  1200ms;
}

@media (prefers-color-scheme: light) {
  @theme {
    --color-bg:           oklch(99% 0.001 250);
    --color-bg-elevated:  oklch(96% 0.005 250);
    --color-fg:           oklch(15% 0.02 250);
    --color-fg-muted:     oklch(45% 0.02 250);
    --color-border:       oklch(15% 0.02 250 / 10%);
  }
}

@layer base {
  html {
    scrollbar-gutter: stable;
    -webkit-text-size-adjust: 100%;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  body {
    background: var(--color-bg);
    color: var(--color-fg);
    font-family: var(--font-sans);
    font-feature-settings: "kern" 1, "liga" 1, "calt" 1;
    overflow-x: clip;
  }

  h1, h2, h3, h4 {
    text-wrap: balance;
    line-height: 1.05;
    letter-spacing: -0.02em;
  }

  p {
    text-wrap: pretty;
    line-height: 1.6;
  }

  :focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 4px;
    border-radius: 2px;
  }

  body.custom-cursor-active,
  body.custom-cursor-active a,
  body.custom-cursor-active button,
  body.custom-cursor-active [data-cursor] {
    cursor: none;
  }

  ::selection {
    background: var(--color-accent);
    color: var(--color-bg);
  }
}

@layer utilities {
  .text-balance { text-wrap: balance; }
  .text-pretty { text-wrap: pretty; }
  .h-dvh { height: 100dvh; }
  .min-h-dvh { min-height: 100dvh; }

  .container-editorial {
    max-width: 80rem;
    margin-inline: auto;
    padding-inline: clamp(1.5rem, 5vw, 4rem);
  }

  .glass {
    background: color-mix(in oklab, var(--color-bg) 70%, transparent);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border: 1px solid var(--color-border);
  }

  .numeric {
    font-variant-numeric: tabular-nums lining-nums;
    font-feature-settings: "tnum" 1, "lnum" 1;
  }
}

/* Custom cursor */
.custom-cursor {
  position: fixed;
  top: 0; left: 0;
  width: 24px; height: 24px;
  border-radius: 50%;
  background: white;
  mix-blend-mode: difference;
  pointer-events: none;
  z-index: 9999;
  translate: -50% -50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Magnetic button */
.magnetic-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 1rem 2rem;
  background: var(--color-fg);
  color: var(--color-bg);
  border-radius: 9999px;
  font-weight: 500;
  font-size: 1rem;
  text-decoration: none;
  will-change: transform;
  transition: background 0.3s var(--ease-out-expo);
}
.magnetic-button:hover { background: var(--color-accent); }
.magnetic-button-content { display: inline-block; position: relative; z-index: 1; }

/* Marquee */
.marquee { display: flex; overflow: hidden; width: 100%; }
.marquee-track {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 2rem;
  padding-right: 2rem;
  min-width: 100%;
  white-space: nowrap;
  animation: marquee linear infinite;
}
.marquee-track--pause:hover { animation-play-state: paused; }
@keyframes marquee {
  from { transform: translateX(0); }
  to { transform: translateX(-100%); }
}

/* Preloader */
.preloader {
  position: fixed;
  inset: 0;
  z-index: 10000;
  background: var(--color-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.preloader-content {
  display: flex;
  align-items: baseline;
  font-family: var(--font-serif);
  font-size: clamp(4rem, 15vw, 12rem);
  line-height: 1;
}
.preloader-count { font-variant-numeric: tabular-nums; }
.preloader-percent { font-size: 0.4em; margin-left: 0.1em; opacity: 0.6; }

/* Reduced motion — global guard */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

## SmoothScroll.tsx

(See Part V §3 — full code provided there.)

## CustomCursor.tsx

(See Pattern 13 — full code provided there.)

## MagneticButton.tsx

(See Part V §1 — full code provided there.)

## Reveal.tsx

```tsx
"use client";
import { motion, type HTMLMotionProps } from "motion/react";
import { type ElementType, type ReactNode } from "react";

type Variant = "up" | "fade" | "scale" | "clip";

const variants: Record<Variant, { initial: object; animate: object }> = {
  up:    { initial: { opacity: 0, y: 40 }, animate: { opacity: 1, y: 0 } },
  fade:  { initial: { opacity: 0 }, animate: { opacity: 1 } },
  scale: { initial: { opacity: 0, scale: 0.92 }, animate: { opacity: 1, scale: 1 } },
  clip:  { initial: { opacity: 0, clipPath: "inset(0 0 100% 0)" }, animate: { opacity: 1, clipPath: "inset(0 0 0% 0)" } },
};

type RevealProps = {
  children: ReactNode;
  variant?: Variant;
  delay?: number;
  duration?: number;
  once?: boolean;
  as?: ElementType;
  className?: string;
} & Omit<HTMLMotionProps<"div">, "children">;

export function Reveal({
  children, variant = "up", delay = 0, duration = 0.7, once = true, as = "div", className, ...rest
}: RevealProps) {
  const M = motion(as as ElementType);
  const v = variants[variant];
  return (
    <M
      className={className}
      initial="initial"
      whileInView="animate"
      viewport={{ once, margin: "-80px" }}
      transition={{ duration, delay, ease: [0.16, 1, 0.3, 1] }}
      variants={v}
      {...rest}
    >
      {children}
    </M>
  );
}

// Stagger variants
const staggerContainer = {
  initial: {},
  animate: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};
const staggerItem = {
  initial: { opacity: 0, y: 30 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

export function RevealStagger({ children, className, once = true }: { children: ReactNode; className?: string; once?: boolean }) {
  return (
    <motion.div
      className={className}
      initial="initial"
      whileInView="animate"
      viewport={{ once, margin: "-80px" }}
      variants={staggerContainer}
    >
      {children}
    </motion.div>
  );
}

RevealStagger.Item = function RevealStaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div className={className} variants={staggerItem}>{children}</motion.div>;
};
```

## Marquee.tsx

```tsx
"use client";
import { type ReactNode } from "react";

type Props = {
  children: ReactNode;
  speed?: number;       // seconds for one full loop. Default 30s.
  reverse?: boolean;
  pauseOnHover?: boolean;  // Default true
  fade?: boolean;          // Default true
  className?: string;
};

export function Marquee({
  children, speed = 30, reverse = false, pauseOnHover = true, fade = true, className = "",
}: Props) {
  const maskStyle = fade ? {
    WebkitMaskImage: "linear-gradient(to right, transparent, black 8%, black 92%, transparent)",
    maskImage: "linear-gradient(to right, transparent, black 8%, black 92%, transparent)",
  } : undefined;
  return (
    <div className={`marquee ${className}`} style={maskStyle}>
      <div
        className={`marquee-track ${pauseOnHover ? "marquee-track--pause" : ""}`}
        style={{ animationDuration: `${speed}s`, animationDirection: reverse ? "reverse" : "normal" }}
      >
        {children}
      </div>
      <div
        className={`marquee-track ${pauseOnHover ? "marquee-track--pause" : ""}`}
        aria-hidden="true"
        style={{ animationDuration: `${speed}s`, animationDirection: reverse ? "reverse" : "normal" }}
      >
        {children}
      </div>
    </div>
  );
}
```

## Preloader.tsx

(See Pattern 26 — full code provided there.)

## ScrollProgress.tsx

(See Pattern 2 — full code provided there.)

## HeadingReveal.tsx

(See Pattern 27 — full code provided there.)

## Parallax.tsx

(See Pattern 3 — full code provided there.)

## ImageReveal.tsx

(See Pattern 33 — full code provided there.)

## FullscreenMenu.tsx

(See Pattern 39 — full code provided there.)

## Counter.tsx

(See Pattern 44 — full code provided there.)

## HeroCanvasClient.tsx + HeroCanvas.tsx

(See Part V §4 — full code provided there.)

---

# Part IX — Performance engineering

## Hard budgets

| Metric | Target | Hard limit | How to measure |
|---|---|---|---|
| First Load JS (homepage) | 180 KB gzip | 250 KB gzip | `next build` + `@next/bundle-analyzer` |
| First Load JS (other routes) | 130 KB gzip | 200 KB gzip | `next build` + `@next/bundle-analyzer` |
| Per-route delta | ≤30 KB gzip | 50 KB gzip | `next build` |
| LCP | < 2.0s on 4G | < 2.5s | Lighthouse mobile, field CrUX |
| CLS | 0.00 | 0.05 | Lighthouse, web-vitals |
| INP | < 100ms | 200ms | field CrUX |
| TBT | < 200ms | 500ms | Lighthouse |
| Frame time during scroll | < 8ms (120Hz) / < 12ms (60Hz) | 12ms / 16ms | DevTools Performance |
| WebGL draw calls (hero) | < 60 | 120 | R3F `<Stats />` |
| WebGL triangles (desktop) | < 100K | 200K | `<Stats />` |
| WebGL triangles (mobile) | < 30K | 60K | `<Stats />` |
| Image size (hero) | < 200 KB (AVIF) | 400 KB | `next/image` |
| Total page weight | < 2 MB | 4 MB | DevTools Network |

## Bundle budget tiers (gzipped)

| Tier | First Load JS | Includes |
|---|---|---|
| Minimal premium | 90-130 KB | Next 16 + React 19 + Tailwind + small Motion |
| Standard Awwwards | 140-180 KB | Above + GSAP core + Lenis + full Motion |
| Heavy premium | 180-250 KB | Above + drei + postprocessing on homepage |
| With 3D hero | 220-280 KB | Above + three.js (~150 KB extra, code-split to homepage only) |
| Above 280 KB | ❌ Reject | Refactor |

## How to verify bundle size

```bash
# Install analyzer
npm i -D @next/bundle-analyzer

# next.config.ts
import withBundleAnalyzer from "@next/bundle-analyzer";
const analyzer = withBundleAnalyzer({ enabled: process.env.ANALYZE === "true" });
export default analyzer(nextConfig);

# Run
ANALYZE=true npm run build
# Open .next/analyze/node.html
```

## Frame budget breakdown (60Hz = 16.67ms per frame)

```
Frame budget: 16.67ms
├── Input handling:        ~0.5ms
├── JS execution:          target < 6ms
│   ├── RAF callbacks
│   ├── React re-renders
│   ├── Motion value updates
│   └── GSAP ticker
├── Style recalc:          ~1ms
├── Layout:                ~1ms (more if you animate layout props!)
├── Paint:                 ~2ms (more with backdrop-filter)
├── Composite:             ~1ms
└── Idle / GPU:            ~5ms
```

At 120Hz the budget is **8.33ms per frame** — JS work must be < 4ms. Test on 120Hz displays (modern MacBooks, iPad Pro).

## Bundle optimization checklist

- [ ] `experimental.optimizePackageImports` includes `motion`, `motion/react`, `@react-three/drei`, `lucide-react`
- [ ] Three.js code-split via `next/dynamic` with `ssr: false` (wrapped in a client shim)
- [ ] Lottie code-split to routes that use it
- [ ] No `lodash` (use `lodash-es` if needed, or vanilla)
- [ ] No `moment` (use `date-fns` or `Intl.DateTimeFormat`)
- [ ] Icons: `lucide-react` with `optimizePackageImports` (no full import)
- [ ] Fonts via `next/font` (no Google Fonts CDN)
- [ ] Images via `next/image` (no raw `<img>`)
- [ ] `reactCompiler: true` for auto-memoization

## Image optimization checklist

- [ ] All images use `next/image`
- [ ] `formats: ["image/avif", "image/webp"]` in `next.config.ts`
- [ ] LCP image has `preload` (NOT the deprecated `priority`)
- [ ] LCP image has `placeholder="blur"` with a real `blurDataURL`
- [ ] All images have explicit `width` and `height` (or `aspect-ratio` in CSS)
- [ ] Hero image ≤ 200 KB (AVIF)
- [ ] Card images ≤ 80 KB (AVIF)
- [ ] `sizes` attribute is set correctly (not just `100vw` everywhere)
- [ ] For dynamic images: use `plaiceholder` or `sharp` to generate blur placeholders

## Font optimization checklist

- [ ] All fonts via `next/font/google` or `next/font/local`
- [ ] `display: "swap"` set on all fonts
- [ ] Subsets match the actual content
- [ ] Variable fonts preferred (one font file, infinite weights)
- [ ] Fallback `@font-face` with `size-adjust` to eliminate FOUT layout shift
- [ ] ≤ 4 font families total
- [ ] ≤ 2 MB total font weight (much less for variable fonts)

## Runtime performance checklist

- [ ] No `addEventListener("scroll")` — use Intersection Observer or `useScroll`
- [ ] No `setInterval` for animations — use RAF
- [ ] Only one RAF source (Lenis → GSAP ticker, or Motion's `useAnimationFrame`)
- [ ] `contain: layout paint style` on cards and list items
- [ ] `content-visibility: auto` on long-scroll sections below the fold
- [ ] `will-change` only during active animations, removed on `transitionend`
- [ ] No `backdrop-filter` on scrolling content
- [ ] No animating layout properties (`width`, `height`, `top`, `left`, `box-shadow`)
- [ ] ScrollTrigger with `invalidateOnRefresh: true`
- [ ] SplitText `.revert()` in cleanup
- [ ] WebGL canvas has CSS fallback for software WebGL
- [ ] Mobile: 3D scene disabled or simplified
- [ ] Mobile: custom cursor + magnetic buttons disabled (`@media (pointer: coarse)`)

## Field measurement (real users)

```bash
npm i web-vitals
```
```ts
// app/layout.tsx
import { onCLS, onLCP, onINP } from "web-vitals";
if (typeof window !== "undefined") {
  onCLS(console.log);
  onLCP(console.log);
  onINP(console.log);
}
```

Targets: LCP P75 < 2.5s, CLS P75 < 0.1, INP P75 < 200ms.

## Lab measurement (DevTools)

1. **Lighthouse mobile** — Performance, Accessibility, Best Practices, SEO. All ≥ 90, target ≥ 95.
2. **DevTools Performance tab** — Record a scroll. Frame time chart mostly green. No purple Layout blocks > 5ms. No yellow Scripting blocks > 8ms.
3. **DevTools Rendering tab** — enable "Paint flashing", "Layer borders", "Frame rendering stats" — scroll and watch for hot spots.
4. **React DevTools Profiler** — record an interaction, check for unnecessary re-renders.
5. **Bundle analyzer** — `ANALYZE=true npm run build`, inspect treemap.

---

# Part X — Accessibility deep dive

## The three rules of premium accessible motion

1. **Motion must be optional.** `prefers-reduced-motion` must visibly slow or disable motion. Users who opt out still get a fully usable site.
2. **Custom pointers must not be the only pointer indicator.** Always keep visible `:focus-visible` outlines. Hide the OS cursor only on fine-pointer devices.
3. **Sound must be opt-in.** Default OFF. Always. No exceptions.

## `prefers-reduced-motion: reduce`

### CSS guard (scope motion to no-preference only)
```css
@media (prefers-reduced-motion: no-preference) {
  .reveal { animation: reveal-up 0.8s var(--ease-out-expo) forwards; }
}
```

### Global reduce override
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### Motion
```tsx
<MotionConfig reducedMotion="user">
  {children}
</MotionConfig>
```

### GSAP
```ts
ScrollTrigger.matchMedia({
  "(prefers-reduced-motion: reduce)": () => {
    gsap.set(".reveal", { opacity: 1, y: 0 });
  },
  "(prefers-reduced-motion: no-preference)": () => {
    gsap.from(".reveal", { opacity: 0, y: 40, stagger: 0.1,
      scrollTrigger: { trigger: ".reveal", start: "top 80%" } });
  },
});
```

### Lenis — don't initialize
```ts
if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
const lenis = new Lenis({ /* … */ });
```

## Custom cursor rules

- Don't break touch devices: `@media (pointer: fine) { * { cursor: none !important; } }`
- Keep `:focus-visible` outlines — never `outline: none` without replacement
- Don't block clicks: `pointer-events: none` on cursor element
- Provide hover affordance: change underlying element's appearance so keyboard/touch users see hover state too

## Focus management

### Page transitions — move focus to new page
```tsx
// app/template.tsx
useEffect(() => {
  ref.current?.focus();
}, []);
// <motion.div ref={ref} tabIndex={-1} style={{ outline: "none" }}>
```

### Modal focus trap
Use `@radix-ui/react-dialog` or `focus-trap-react` — don't roll your own.

### Skip-to-content link
```tsx
<a href="#main" className="skip-link">Skip to content</a>
<main id="main">…</main>
```
```css
.skip-link { position: absolute; top: -100px; left: 0; background: var(--color-bg); color: var(--color-fg); padding: 1rem; z-index: 10000; }
.skip-link:focus { top: 0; }
```

## Color contrast

- Body text: 4.5:1 minimum (WCAG AA)
- Large text (≥24px or ≥18.66px bold): 3:1
- UI components: 3:1
- Don't rely on color alone — use color + icon + text for status

## Screen reader considerations

- `aria-live` for dynamic content (number counters, async-loaded lists, toasts)
- `aria-hidden` for decorative animations (cursor, decorative SVGs, marquee text)
- Descriptive `alt` for images (empty `alt=""` for decorative)
- Heading hierarchy: one `<h1>` per page, no skipped levels
- Semantic landmarks: `<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`

## Touch device rules

- Disable cursor and magnetic: `@media (pointer: coarse) { .magnetic { transform: none !important; } .cursor { display: none !important; } }`
- Mobile menu closeable by: tap close button (always), tap overlay (always), drag-down gesture (bonus), Escape key
- Haptic feedback: `navigator.vibrate?.(10)` — Android only, never required

## Keyboard navigation

- Tab order matches visual reading order
- `:focus-visible` only (not `:focus`) — shows focus for keyboard, not mouse
- Escape closes modals and menus
- Don't trap focus in animations — interactive elements stay keyboard-focusable

## Sound design

- Default OFF — Web Audio hover/click sounds are controversial
- Explicit opt-in toggle: `<button aria-pressed={soundOn}>`
- Auto-pause AudioContext on tab blur
- See Pattern 46 for full `useSound` hook

## Cognitive load

- No flashing animations faster than 3 Hz (WCAG 2.3.1) — seizure risk
- No auto-playing video with sound
- No infinite scroll without a "load more" button
- Pause autoplaying marquees and carousels on hover and focus
- Don't auto-advance carousels faster than 5 seconds per slide

## Pre-ship accessibility checklist

- [ ] `prefers-reduced-motion: reduce` visibly slows/disables all decorative motion
- [ ] Site fully usable with motion disabled
- [ ] All interactive elements have visible `:focus-visible` outlines
- [ ] Tab order matches visual reading order
- [ ] One `<h1>` per page, no skipped heading levels
- [ ] Modal/dialog focus trap works correctly
- [ ] Escape key closes modals and mobile menus
- [ ] All images have appropriate `alt` text
- [ ] Color contrast meets AA minimums
- [ ] Status indicators don't rely on color alone
- [ ] `aria-live` on dynamic content
- [ ] `aria-hidden` on decorative animations
- [ ] Custom cursor disabled on touch devices
- [ ] Magnetic buttons disabled on touch devices
- [ ] Sound is OFF by default
- [ ] No flashing animations faster than 3 Hz
- [ ] Carousels pause on hover and focus
- [ ] Skip-to-content link present
- [ ] Lighthouse Accessibility ≥ 95

---

# Part XI — Page-type recipes

## Recipe 1: Landing page / homepage

**First Load JS target:** 180 KB

**Structure:**
```
app/page.tsx (Server Component)
├── Hero section (motion reveal + optional WebGL canvas via dynamic import)
├── Marquee strip (CSS marquee, pause on hover)
├── Featured work (3-4 cards with image reveal)
├── Pinned showcase (GSAP ScrollTrigger pin + horizontal scroll, desktop only)
├── Stats counter section (number counters on scroll)
├── Testimonial carousel (Embla)
├── CTA section (magnetic button)
└── Footer
```

**Key patterns:** SmoothScroll, CustomCursor, ScrollProgress, Preloader, Reveal, MagneticButton, Marquee, HeadingReveal, ImageReveal, PinnedGallery, Counter

## Recipe 2: Case study detail page

**First Load JS target:** 140 KB

**Structure:**
```
app/work/[slug]/page.tsx (Server Component)
├── Hero (full-bleed image, text reveal on mount)
├── Meta info (client, year, role — staggered)
├── Body content (rich text, image galleries)
├── Quote pull (large serif, clip reveal)
├── Image grid (staggered reveal)
├── Video embed (lazy-loaded)
├── Next/prev navigation (layout animation)
└── Footer
```

**Key patterns:** HeadingReveal, ImageReveal, RevealStagger, ScrollProgress. No 3D. No pinning.

## Recipe 3: Portfolio index

**First Load JS target:** 130 KB

**Structure:**
```
app/work/page.tsx (Server Component)
├── Page header (heading reveal)
├── Filter bar (tabs with layout animation)
├── Project list (hover-activated video preview — single shared <video>)
├── Load more (button, not infinite scroll)
└── Footer
```

**Key patterns:** HoverVideoList, Tabs (layoutId), HeadingReveal. No Lottie. CSS reveals only.

## Recipe 4: Product launch page

**First Load JS target:** 220 KB (3D hero allowed)

**Structure:**
```
app/page.tsx
├── Hero with 3D product model (R3F, code-split, CSS fallback)
├── Feature highlights (pinned scroll sequence)
├── Image sequence scroll scrub (Apple-style)
├── Spec table (animated number counters)
├── Comparison table
├── FAQ accordion (interpolate-size)
├── Buy CTA (magnetic)
└── Footer
```

**Key patterns:** HeroCanvas, PinnedSequence, ImageSequence, Counter, Accordion, MagneticButton

## Recipe 5: Editorial / blog article

**First Load JS target:** 100 KB

**Structure:**
```
app/blog/[slug]/page.tsx (Server Component)
├── Article header (title, author, date, reading time)
├── Hero image (image reveal)
├── Article body (prose, balanced text, drop cap)
├── Pull quotes (clip reveal)
├── Code blocks (syntax highlighting)
├── Image figures with captions
├── Author bio
├── Related articles
└── Footer
```

**Key patterns:** Maybe Motion for reveal; no GSAP. No 3D. Focus on typography.

---

# Part XII — Build, deploy, verify (mandatory pre-ship checklist)

Before you tell the user the site is done, run EVERY item on this list. If any fails, fix it — don't ship around it.

## Build
- [ ] `next build` succeeds with no warnings about missing `'use client'`
- [ ] `@next/bundle-analyzer` shows First Load JS within budget on every route
- [ ] No TypeScript errors
- [ ] No ESLint errors

## Performance
- [ ] Lighthouse mobile: Performance ≥ 90, target ≥ 95
- [ ] LCP element has `preload` and a `blur` placeholder
- [ ] No layout shift during font load (verify in DevTools Performance → CLS)
- [ ] First Load JS homepage ≤ 180 KB gzip
- [ ] No image > 200 KB on hero page

## Accessibility
- [ ] Lighthouse Accessibility ≥ 95
- [ ] Tab through the entire page with the keyboard — every interactive element reachable, focus visible, order logical
- [ ] Toggle `prefers-reduced-motion: reduce` in DevTools — site fully usable, motion disabled or significantly reduced
- [ ] Screen reader test (VoiceOver / NVDA) — page makes sense without visuals
- [ ] Color contrast AA on all text

## Cross-browser / device
- [ ] Chrome desktop
- [ ] Safari desktop
- [ ] Firefox desktop
- [ ] iOS Safari (real device)
- [ ] Android Chrome (real device)
- [ ] Page transitions degrade gracefully where View Transitions API is unsupported
- [ ] No console errors during scroll, including during fast scroll and rapid route changes

## WebGL
- [ ] WebGL hero has a CSS fallback (gradient or static image) for software WebGL
- [ ] Test on a device with software WebGL (older Intel Mac, low-end Android)

## Responsive
- [ ] `prefers-color-scheme: dark` works via `light-dark()`
- [ ] Test at 320px, 768px, 1024px, 1440px, 1920px widths
- [ ] No horizontal scroll on mobile

## Images
- [ ] All images are AVIF with WebP fallback
- [ ] No PNG/JPG > 200KB
- [ ] `sizes` attribute correct on every `next/image`

## SEO / Meta
- [ ] `<title>` and `<meta name="description">` per route via the Metadata API
- [ ] OG image via `next/og` (`ImageResponse`) — not a static PNG
- [ ] `robots.txt` and `sitemap.xml`
- [ ] Canonical URLs

## Motion quality
- [ ] No custom cursor on touch devices
- [ ] No magnetic buttons on touch devices
- [ ] Preloader doesn't fake the counter — reflects real resource load
- [ ] No layout shift during preloader curtain lift
- [ ] Page transition focus management works (focus moves to new page)
- [ ] All animations respect `prefers-reduced-motion`

## Final
- [ ] `<title>` and `<meta name="description">` per route
- [ ] OG image via `next/og`
- [ ] All images AVIF with WebP fallback
- [ ] All interactive elements keyboard-accessible
- [ ] Lighthouse all categories ≥ 90

---

# Part XIII — Anti-patterns catalog (things that LOOK premium but actually feel janky)

## A. Animating layout properties instead of transform/opacity

**Symptom:** Frame time spikes during the animation; long yellow layout blocks in DevTools.
**Cause:** Animating `width`, `height`, `top`, `left`, `margin`, `padding`, `border-width`, `box-shadow`, or `font-size` forces layout recalc on every frame.
**Fix:** Restructure to animate `transform` and `opacity` only. Need to grow? `transform: scale()`. Need box-shadow? Animate a `::after` pseudo-element's `opacity`.

## B. Overusing `backdrop-filter: blur()` on scrolling content

**Symptom:** 5-15fps scroll on Safari; fans spin up.
**Cause:** `backdrop-filter` re-rasters the backdrop every frame. Safari's implementation is slowest.
**Fix:** Only on `position: fixed`/`sticky` surfaces. For glass on scrolling content, use semi-transparent solid background.

## C. Mismatched easing curves across co-occurring animations

**Symptom:** Animations feel "off" but you can't pinpoint why.
**Cause:** Three animations start together with different easings — finish at different times.
**Fix:** Define 3 site-wide easing tokens. Use only those. Same token for animations that start together.

## D. Two RAF loops running simultaneously

**Symptom:** Jank on otherwise-simple pages.
**Cause:** Lenis has its own RAF. GSAP has its own ticker. Motion has `useAnimationFrame`. Three independent loops.
**Fix:** Sync them. Lenis RAF → GSAP ticker. Prefer Motion's `useAnimationFrame` over raw RAF. Never more than one RAF source.

## E. Pinning inside a `transform`ed ancestor

**Symptom:** ScrollTrigger pinned section "jumps" or doesn't stick.
**Cause:** `position: sticky` breaks when any ancestor has `transform`, `filter`, `perspective`, `will-change: transform`, `backdrop-filter`, or `mask`.
**Fix:** Audit ancestors. Remove offending property, or move pinned section outside.

## F. Preloaders that fake the counter

**Symptom:** Counter sits at 87%, jumps to 100%, page still loading.
**Cause:** Developer wrote `setInterval(() => setCount(c => c + 1), 30)` without binding to load.
**Fix:** Track real progress via `PerformanceObserver` on LCP resource. Or just use a spinner. Honest > fake.

## G. Custom cursor on touch devices

**Symptom:** User on phone has no visible cursor state.
**Cause:** `* { cursor: none !important; }` applied unconditionally.
**Fix:** Gate on `(pointer: fine)`.

## H. `mix-blend-mode` on `position: sticky` + `backdrop-filter`

**Symptom:** Element renders as solid black on Safari.
**Cause:** Three-way interaction bug in Safari's compositing.
**Fix:** Pick two of the three.

## I. Hover-activated video preview with one `<video>` per item

**Symptom:** ~95 MB GPU memory; fans spin up; battery drains.
**Cause:** Each `<video>` spins up its own decoder. 30 items × 3 MB = 90 MB.
**Fix:** One shared `<video>`, swap `src` on hover. ~3 MB total.

## J. Splitting text on every render without reverting

**Symptom:** Duplicated text nodes. Heading reads "HelloHelloHello".
**Cause:** SplitText rewrites DOM. No `.revert()` in cleanup → re-split on next render.
**Fix:** `useGSAP({ revertOnUpdate: true })`.

## K. WebGL with no CSS fallback

**Symptom:** Site renders at 2fps on older Intel Macs and low-end Android.
**Cause:** Software WebGL (SwiftShader, llvmpipe) is very slow.
**Fix:** Detect and bail out:
```ts
function isWebGLUsable() {
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
  if (!gl) return false;
  const renderer = gl.getParameter(gl.RENDERER) ?? "";
  return !/SwiftShader|llvmpipe|Microsoft Basic Render/.test(renderer);
}
```

## L. ScrollTrigger without `invalidateOnRefresh: true`

**Symptom:** ScrollTrigger positions drift after window resize, font swap, or image load.
**Cause:** ScrollTrigger caches start/end positions. Without invalidateOnRefresh, never re-measures.
**Fix:** Always pass `invalidateOnRefresh: true` on triggers depending on element positions.

---

# Part XIV — Easing & timing reference

## Standard cubic-bezier curves

| Name | `cubic-bezier(...)` | Use for |
|---|---|---|
| Out Expo | `0.16, 1, 0.3, 1` | Default — entrances, reveals |
| In Out Quint | `0.83, 0, 0.17, 1` | Symmetric — entrance + exit pairs |
| Anticipate | `0.68, -0.55, 0.27, 1.55` | Playful overshoot — sparingly |
| Out Back | `0.34, 1.56, 0.64, 1` | Card hover, button press |
| Out Quart | `0.25, 1, 0.5, 1` | Subtle — long fades |
| In Out Circ | `0.85, 0, 0.15, 1` | Dramatic — fullscreen overlays |
| Linear | `0, 0, 1, 1` | Marquees, scroll-scrubbed timelines only |

## CSS variables (put in `:root` or `@theme`)
```css
--ease-out-expo:      cubic-bezier(0.16, 1, 0.3, 1);
--ease-in-out-quint:  cubic-bezier(0.83, 0, 0.17, 1);
--ease-anticipate:    cubic-bezier(0.68, -0.55, 0.27, 1.55);
--ease-out-back:      cubic-bezier(0.34, 1.56, 0.64, 1);
--ease-out-quart:     cubic-bezier(0.25, 1, 0.5, 1);
--ease-in-out-circ:   cubic-bezier(0.85, 0, 0.15, 1);
```

## GSAP equivalents
```ts
export const eases = {
  outExpo: "expo.out",
  inOutQuint: "power4.inOut",
  anticipate: "back.out(1.7)",
  outBack: "back.out(1.7)",
  outQuart: "power3.out",
  inOutCirc: "circ.inOut",
};
```

## Duration guidelines

| Duration | Use for |
|---|---|
| 100ms | Color changes, instant feedback |
| 200ms | Hover states, small UI |
| 400ms | Default transitions |
| 600ms | Standard reveals |
| 900ms | Hero entrances, page transitions |
| 1200ms | Preloader curtain, big moments |

## Spring configs (Motion)

| Config | Use for |
|---|---|
| `{ stiffness: 200, damping: 15, mass: 0.3 }` | Magnetic buttons — snappy return |
| `{ stiffness: 120, damping: 30, restDelta: 0.001 }` | Scroll progress — smooth but responsive |
| `{ damping: 25, stiffness: 350, mass: 0.5 }` | Custom cursor — tight follow |
| `{ stiffness: 300, damping: 20 }` | Layout animations — quick settle |

---

# Final philosophy

Awwwards sites win because every motion decision answers a question: *what is this animation teaching the user?* If the answer is "nothing, it just looks cool," cut it. The best sites feel alive because every transition guides attention, every hover confirms interactivity, every scroll reveal paces the narrative. Restraint is the signature of confidence.

Pick three signature moments. Nail them. Make the rest quiet. Ship.

---

*End of skill. This is one file. Everything is here. Use it well.*
