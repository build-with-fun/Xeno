---
description: COMPLETE Next.js skill covering v15 and v16 (App Router), React 19.2,
  Server Components & Actions, Cache Components (use cache), PPR, Turbopack, routing,
  rendering strategies (SSR/SSG/ISR/PPR), middleware/proxy, data fetching & mutations,
  authentication patterns, caching APIs (revalidateTag, updateTag, refresh), SEO &
  Metadata API, image/font optimization, Tailwind CSS v4 + shadcn/ui, i18n (next-intl),
  testing (Vitest/Playwright), deployment (self-host, Docker, Vercel), security (React2Shell
  CVE), React Compiler, performance, streaming. Use for ANY Next.js task.
name: coding-next-js
---

---
name: coding-next-js
description: >
  ULTIMATE Next.js skill covering v15 and v16 (App Router), React 19.2,
  Server Components & Actions, Cache Components (use cache), PPR, Turbopack,
  routing, rendering (SSR/SSG/ISR/PPR), middleware/proxy, data fetching &
  mutations, auth patterns, caching APIs (revalidateTag, updateTag, refresh),
  SEO & Metadata API, image/font optimization, Tailwind v4 + shadcn/ui, i18n
  (next-intl), testing (Vitest/Playwright), deployment (self-host, Docker,
  Vercel), security (React2Shell CVE), React Compiler, performance, streaming.
  Use for ANY Next.js task including scaffolding, refactoring, debugging,
  optimization, and production deployment.
version: 2026.2.0
last_updated: 2026-06-30
versions_covered: "15.x - 16.x (current stable: 16.2.x)"
---

# NEXT.JS — COMPLETE PRODUCTION REFERENCE

> **⚠️ CRITICAL**: Before generating ANY Next.js code, check §1 for React2Shell CVE. Affects every App Router deployment.

## 0. ORIENTATION

| Area | Current State (mid-2026) |
|------|--------------------------|
| **Stable Next.js** | **16.2.x** (v16 shipped Oct 2025) |
| **Minimum Node.js** | 20.9+ (v16) |
| **React version** | 19.2.x |
| **Default bundler** | **Turbopack** (stable, dev + prod) |
| **Router** | App Router only; Pages Router is legacy |
| **Rendering** | Cache Components (`"use cache"`) replace old PPR flags |
| **Middleware** | Renamed to `proxy.ts` in v16 |

**Upgrade:** `npx @next/codemod@canary upgrade latest`
**Scaffold:** `npx create-next-app@latest`

## 1. SECURITY — CRITICAL

### 1.1 React2Shell CVE (CVE-2025-55182)
Max-severity RCE in RSC Flight protocol. **Vulnerable:** Next.js 15.0.4–16.0.6. **Patched:** 15.0.5+, 15.1.9+, 15.2.6+, 15.3.6+, 15.4.8+, 15.5.7+, 16.0.7+.

### 1.2 Server Action Security Rules
1. **Server Actions are public HTTP endpoints** — always validate/authorize inside the action.
2. Never pass unvalidated objects through `'use server'` boundaries.
3. Use unguessable action IDs (v15+ does this automatically).

```typescript
'use server'
export async function deletePost(formData: FormData) {
  const session = await auth()
  if (!session?.user) throw new Error('Unauthorized')
  const id = formData.get('id')
  const post = await db.post.findUnique({ where: { id } })
  if (!post || post.authorId !== session.user.id) throw new Error('Forbidden')
  await db.post.delete({ where: { id } })
  revalidatePath('/posts')
}
```

## 2. PROJECT STRUCTURE

```
src/
├── app/                    # App Router pages & layouts
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Home
│   ├── (auth)/             # Route group
│   ├── (dashboard)/
│   └── api/                # Route handlers (when needed)
├── components/
│   ├── ui/                 # shadcn/ui components
│   └── shared/             # App-specific components
├── features/               # Feature-sliced modules
│   ├── auth/ → actions.ts, components/, hooks/
│   └── blog/ → actions.ts, components/, hooks/
├── lib/                    # Utilities, API clients, config
├── hooks/                  # Shared hooks
├── styles/globals.css
└── types/                  # TypeScript types
```

## 3. APP ROUTER FILE CONVENTIONS

| File | Purpose |
|------|---------|
| `layout.tsx` | Shared layout (persists across navs) |
| `page.tsx` | Unique page |
| `loading.tsx` | Suspense fallback |
| `error.tsx` | Error boundary (`'use client'`) |
| `global-error.tsx` | Root-level error UI |
| `not-found.tsx` | 404 |
| `route.ts` | API route (no `page.tsx` at same segment) |
| `template.tsx` | Layout that remounts on nav |
| `default.tsx` | Required for parallel route slots (v16) |
| `proxy.ts`/`middleware.ts` | Request interception |

**Dynamic routes:** `[slug]`, `[...slug]` (catch-all), `[[...slug]]` (optional catch-all)
**Route groups:** `(shop)/products` (no path segment)
**Parallel routes:** `@modal`, `@sidebar` rendered alongside `children` in layout
**Intercepting routes:** `(.)photo/[id]` (same level), `(..)` (parent), `(..)(..)` (grandparent)

## 4. RENDERING STRATEGIES

| Strategy | When | How |
|----------|------|-----|
| **SSR (Dynamic)** | Auth pages, real-time data | Dynamic functions (`cookies()`, `headers()`) or `force-dynamic` |
| **SSG (Static)** | Marketing, blog | Default (no dynamic functions) |
| **ISR** | Blog with updates, catalog | `revalidate: 60` or `fetch(..., { next: { revalidate: 60 } })` |
| **PPR/Cache Components** | Mixed static + dynamic | `cacheComponents: true` in config + `"use cache"` directive |
| **CSR** | Internal dashboards | Fetch in Client Components |

### 4.1 Cache Components (v16 — opt-in caching)
```typescript
// next.config.ts
const nextConfig = { cacheComponents: true }  // Replaces experimental.ppr / dynamicIO
export default nextConfig
```

```tsx
// Cache a page or component
export default async function Page() {
  'use cache'
  const data = await fetch('https://api.example.com/data')
  return <div>{/* ... */}</div>
}
```

### 4.2 Data Fetching
```tsx
export default async function Page() {
  const data = await fetch('https://api.example.com/posts')
  // cache: 'no-store' = SSR, next: { revalidate: 60 } = ISR
  // next: { tags: ['posts'] } = tag-based invalidation
  return <div>{/* render */}</div>
}
```

## 5. SERVER ACTIONS & DATA MUTATIONS

### 5.1 Creating Server Actions
```typescript
// Module-level (recommended) — app/actions.ts
'use server'
import { revalidatePath, revalidateTag, redirect } from 'next/cache'

export async function createPost(formData: FormData) {
  const title = formData.get('title') as string
  const content = formData.get('content') as string
  const post = await db.post.create({ data: { title, content } })
  revalidatePath('/posts')
  revalidateTag('blog-posts')
  redirect(`/posts/${post.id}`)
}
```

### 5.2 Client Component Invocation
```tsx
'use client'
import { useActionState, useOptimistic } from 'react'
import { createPost } from '@/app/actions'

export function Form() {
  const [state, formAction, isPending] = useActionState(createPost, null)
  return (
    <form action={formAction}>
      <input name="title" required />
      <button type="submit" disabled={isPending}>
        {isPending ? 'Creating...' : 'Create'}
      </button>
      {state?.error && <p>{state.error}</p>}
    </form>
  )
}

// Optimistic UI
export function LikeButton({ initialLikes }: { initialLikes: number }) {
  const [optimisticLikes, addOptimisticLike] = useOptimistic(initialLikes, (s, n) => s + n)
  return <button onClick={async () => { addOptimisticLike(1); await incrementLike() }}>♥ {optimisticLikes}</button>
}
```

### 5.3 Caching APIs (v16)
```typescript
import { revalidateTag, updateTag, refresh } from 'next/cache'

// revalidateTag — stale-while-revalidate (v16: requires cacheLife profile)
revalidateTag('blog-posts', 'max')              // Built-in profile
revalidateTag('products', { expire: 3600 })     // Custom inline

// updateTag — READ-YOUR-WRITES (immediate refresh, Server Actions only)
export async function updateProfile(profile: Profile) {
  'use server'
  await db.users.update(profile)
  updateTag(`user-${profile.id}`)  // Immediate — user sees changes
}

// refresh — for UNCACHED data (notification counts, live metrics)
export async function markAsRead(id: string) {
  'use server'
  await db.notifications.markAsRead(id)
  refresh()
}
```

### 5.4 Revalidation Patterns
```typescript
revalidatePath('/posts')                    // Specific path
revalidatePath('/blog/[slug]', 'page')      // Dynamic path pattern
revalidatePath('/blog', 'layout')           // All pages under layout
revalidateTag('posts')                      // By cache tag
redirect('/posts')                          // Call AFTER revalidation
```

## 6. PROXY (formerly MIDDLEWARE) — v16

```typescript
// proxy.ts at app root
import { NextRequest, NextResponse } from 'next/server'

export default function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  if (pathname === '/') return NextResponse.redirect(new URL('/home', request.url))
  return NextResponse.next()
}

export const config = { matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'] }
```

### Auth in Proxy
```typescript
export default async function proxy(req: NextRequest) {
  const path = req.nextUrl.pathname
  const isProtected = protectedRoutes.some(r => path.startsWith(r))
  const cookie = req.cookies.get('session')?.value
  const session = await decrypt(cookie)
  if (isProtected && !session?.userId) return NextResponse.redirect(new URL('/login', req.url))
  const headers = new Headers(req.headers)
  headers.set('x-user-id', session?.userId)
  return NextResponse.next({ request: { headers } })
}
```

## 7. AUTHENTICATION

### 7.1 Auth.js (NextAuth v5)
```typescript
// lib/auth.ts
import NextAuth from 'next-auth'
import GitHub from 'next-auth/providers/github'
import { PrismaAdapter } from '@auth/prisma-adapter'

export const { handlers, signIn, signOut, auth } = NextAuth({
  adapter: PrismaAdapter(db),
  providers: [GitHub],
  callbacks: { session({ session, user }) { session.user.id = user.id; return session } },
})
```

### 7.2 DAL Pattern (Recommended)
```typescript
import { cache } from 'react'
import { auth } from './auth'

export const getCurrentUser = cache(async () => {
  const session = await auth()
  return session?.user ?? null
})

export const authorizeAdmin = cache(async () => {
  const user = await getCurrentUser()
  if (user?.role !== 'admin') throw new Error('Unauthorized')
  return user
})
```

## 8. SEO & METADATA API

### 8.1 Static Metadata
```typescript
export const metadata: Metadata = {
  title: { default: 'My App', template: '%s | My App' },
  description: 'Description',
  openGraph: { title: 'My App', description: 'OG desc', images: ['/og.png'], type: 'website' },
  twitter: { card: 'summary_large_image', title: 'My App', images: ['/twitter.png'] },
  robots: { index: true, follow: true },
  alternates: { canonical: 'https://example.com' },
}
```

### 8.2 Dynamic Metadata
```typescript
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params
  const post = await db.post.findUnique({ where: { slug } })
  if (!post) return { title: 'Not Found' }
  return { title: post.title, description: post.excerpt, openGraph: { images: [post.coverImage] } }
}
```

### 8.3 Sitemap & Robots
```typescript
// app/sitemap.ts
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await db.post.findMany()
  return [{ url: 'https://example.com', lastModified: new Date(), changeFrequency: 'yearly', priority: 1 },
    ...posts.map(p => ({ url: `https://example.com/blog/${p.slug}`, lastModified: p.updatedAt }))]
}

// app/robots.ts
export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: '*', allow: '/', disallow: '/admin/' }, sitemap: 'https://example.com/sitemap.xml' }
}
```

## 9. UI/UX — STYLING & COMPONENTS

| Need | Recommended |
|------|-------------|
| **Styling** | Tailwind CSS v4 (utility-first, OKLCH) |
| **Components** | shadcn/ui (copy-paste, own your code) |
| **Headless** | Radix UI |
| **Animations** | Motion (formerly Framer Motion) |
| **Icons** | lucide-react |
| **Fonts** | `next/font` (self-hosted, zero CLS) |

### 9.1 shadcn/ui
```bash
npx shadcn@latest init
npx shadcn@latest add button card dialog form input select table toast
```

### 9.2 next/font
```typescript
import { Inter } from 'next/font/google'
const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className={inter.variable}><body>{children}</body></html>
}
```

### 9.3 next/image
```typescript
// next.config.ts
const nextConfig = { images: { remotePatterns: [{ protocol: 'https', hostname: 'images.example.com' }] } }

// Usage
<Image src="https://images.example.com/photo.jpg" alt="Alt text" width={400} height={300} priority sizes="(max-width: 768px) 100vw, 33vw" />
```

## 10. ROUTE HANDLERS

```typescript
// app/api/posts/route.ts
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const posts = await db.post.findMany({ skip: Number(searchParams.get('page') ?? '1'), take: 10 })
  return Response.json(posts)
}

// Dynamic — app/api/posts/[slug]/route.ts
export async function GET(request: NextRequest, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params  // Async params in v16!
  const post = await db.post.findUnique({ where: { slug } })
  if (!post) return Response.json({ error: 'Not found' }, { status: 404 })
  return Response.json(post)
}
```

**Server Actions vs Route Handlers:** Actions for form submissions/mutations tightly coupled to UI. Route Handlers for public APIs, webhooks, CORS-required endpoints, mobile app backends.

## 11. INTERNATIONALIZATION — next-intl

```bash
npm install next-intl
```

```typescript
// src/i18n/request.ts
export default getRequestConfig(async () => {
  const locale = 'en'  // From cookie/header/path
  return { locale, messages: (await import(`./messages/${locale}.json`)).default }
})

// Usage
import { useTranslations } from 'next-intl'
function HomePage() { const t = useTranslations('HomePage'); return <h1>{t('title')}</h1> }
```

## 12. TESTING

### 12.1 Unit — Vitest + Testing Library
```bash
npm install -D vitest @vitejs/plugin-react @testing-library/react @testing-library/jest-dom jsdom
```

```typescript
// vitest.config.ts
export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', setupFiles: './tests/setup.ts', globals: true },
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
})

// Test
it('renders button', async () => {
  const onClick = vi.fn()
  render(<button onClick={onClick}>Click</button>)
  await userEvent.click(screen.getByRole('button'))
  expect(onClick).toHaveBeenCalledOnce()
})
```

### 12.2 E2E — Playwright
```bash
npm install -D @playwright/test && npx playwright install
```

```typescript
test('homepage loads', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1')).toContainText('Welcome')
  await page.click('text=Get Started')
  await expect(page).toHaveURL(/\/dashboard/)
})
```

## 13. DEPLOYMENT

### 13.1 Vercel (Managed)
Zero-config. `git push` deploys. Env vars via Vercel dashboard. Edge Functions automatically distributed.

### 13.2 Self-Host — Node.js
```bash
npm run build && npm run start
```

### 13.3 Self-Host — Docker (Multi-stage)
```dockerfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY src/ ./src/ public/ ./public/ next.config.ts ./
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=deps /app/node_modules ./node_modules
EXPOSE 3000
CMD ["node", "node_modules/.bin/next", "start"]
```

### 13.4 Multi-Server Deployments
```bash
# Set consistent encryption key for Server Actions across instances
NEXT_SERVER_ACTIONS_ENCRYPTION_KEY=your-base64-key npm run build
# Set deployment ID for version skew protection
NEXT_DEPLOYMENT_ID=your-deploy-id npm run build
```

## 14. PERFORMANCE OPTIMIZATION

### 14.1 React Compiler (Stable v1.0)
```bash
npm install --save-dev babel-plugin-react-compiler@latest
```

```typescript
// next.config.ts
const nextConfig = { reactCompiler: true }  // Auto-memoizes components
```

### 14.2 Streaming & Suspense
```tsx
import { Suspense } from 'react'

export default function Page() {
  return (
    <div>
      <h1>Dashboard</h1>
      <Suspense fallback={<Skeleton />}>
        <SlowComponent />
      </Suspense>
    </div>
  )
}

async function SlowComponent() {
  const data = await fetch('https://slow-api.com/data')
  return <DataView data={data} />
}
```

### 14.3 after() — Deferred Execution (v15+)
```typescript
import { unstable_after as after } from 'next/server'

export default function Layout({ children }: { children: React.ReactNode }) {
  after(async () => {
    await logAnalytics()  // Runs after response sent to client
  })
  return <>{children}</>
}
```

### 14.4 Turbopack (Default in v16)
- 2-5× faster production builds
- Up to 10× faster Fast Refresh
- File system caching for dev: `experimental: { turbopackFileSystemCacheForDev: true }`
- Opt out with `next build --webpack` if custom webpack config needed

## 15. ERROR HANDLING

### 15.1 error.tsx
```tsx
'use client'
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={() => reset()}>Try again</button>
    </div>
  )
}
```

### 15.2 instrumentation.ts — Global Error Tracking
```typescript
export async function onRequestError(err: Error, request: Request, context: { router: string; renderSource: string }) {
  await fetch('https://observability.example.com/report', {
    method: 'POST',
    body: JSON.stringify({ message: err.message, request, context }),
  })
}

export async function register() {
  // Init Sentry/OpenTelemetry SDK
}
```

## 16. COMMON GOTCHAS & ANTI-PATTERNS

| Problem | Fix |
|---------|-----|
| Using `useEffect` for data fetching in Server Components | Fetch directly in Server Component with `async/await` |
| Forgetting `'use client'` for interactive components | Add `'use client'` at the top of files with hooks/events |
| Mixing route handlers and page at same segment | Cannot have `route.ts` and `page.tsx` at same segment |
| Stale UI after Server Action mutation | Call `revalidatePath()` or `revalidateTag()` in the action |
| Assuming `params` is sync | `const { slug } = await params` (async in v16) |
| Using `middleware.ts` in v16 | Rename to `proxy.ts` (middleware.ts deprecated) |
| Caching sensitive data | Dynamic data should use `cache: 'no-store'` or `force-dynamic` |
| Server Actions not refreshing UI | Use `updateTag()` for read-your-writes, or `refresh()` for uncached |
| Blocking the main thread in Server Components | Use `Suspense` boundaries + streaming |
| Not handling loading/error states | Add `loading.tsx` and `error.tsx` at every route level |
| Over-using global state (Zustand/Context) | Prefer Server Component data fetching + URL state for shareable state |

## 17. QUICK DECISION CHECKLIST

1. **Check React2Shell CVE** if touching any RSC/Server Action code (§1)
2. **Scaffold with App Router**, TypeScript, Tailwind (§2)
3. **Classify each route by rendering strategy** (§4): SSG for static, ISR for semi-dynamic, SSR for personalized, Cache Components for mixed
4. **Prefer Server Components by default** — only use `'use client'` when interactivity is needed
5. **Route data mutations through Server Actions** (§5) — simpler than API routes for UI-tied operations
6. **Use Route Handlers** (§10) for external-facing APIs, webhooks, CORS scenarios
7. **Authorize at every entry point** — proxy, Server Component, Server Action, Route Handler (§6, §7)
8. **Cache explicitly with `"use cache"`** (v16) or tag-based invalidation (§4.1, §5.3)
9. **Implement metadata, sitemap, robots** for every public route (§8)
10. **Add `loading.tsx` and `error.tsx`** at every route level (§15)
11. **Test with Vitest + Playwright** (§12) — component tests for logic, E2E for critical flows
12. **Deploy with proper Dockerfile and env config** for self-hosting (§13)