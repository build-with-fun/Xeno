---
name: coding-react-js
description: >
  Comprehensive reference for React.js (web) development through React 19.2 (mid-2026).
  Covers React 19 features (Actions, use(), refs), the stable React Compiler,
  Server Components, Next.js App Router, state management (TanStack Query, Zustand),
  testing, performance profiling, and critical security advisories.
  Use for any React web task including refactoring, debugging, and project setup.
---

# React.js — Comprehensive Reference (current through React 19.2, mid-2026)

This is a working reference for present-day React, not the React of training-data vintage. React
moves in small, frequent releases (three minors in the last twelve months alone), and a handful of
things that were true in 2024 are no longer true: Create React App is dead, manual memoization is
now optional rather than expected, Server Components shipped a maximum-severity CVE that every RSC
codebase needs to be checked against, and the state-management "default" quietly flipped from
Redux to a server-state/client-state split. Read the orientation table and the security advisory
below before writing any React code, then use the rest of this document as needed.

## 0. Orientation: what's actually current right now

| Area | Current state (mid-2026) |
|---|---|
| Stable React | 19.2.x (latest patch as of this writing is 19.2.7, June 1 2026). React 19 itself shipped Dec 5, 2024; 19.1 in June 2025; 19.2 in October 2025. Always assume 19.2 semantics unless the user's `package.json` says otherwise. |
| React 18 | Out of active support (ended Dec 2024); still gets critical security backports. Don't scaffold new 18.x projects without a reason. |
| Scaffolding tool | **Create React App is deprecated** (React team announcement, Feb 2025) and should not be recommended for new projects. Use a framework or Vite/Parcel/Rsbuild instead (see §2). |
| React Compiler | **Stable v1.0** as of React Conf, Oct 7 2025. Safe and recommended for production. Works with React 17+ via a runtime polyfill package, not just React 19. |
| React Server Components | Stable since React 19, but see the security advisory immediately below before touching RSC/Server Actions code. |
| Governance | React's project governance moved under the newly formed **React Foundation**, announced October 2025. |
| Dominant state-management split | Server state → TanStack Query. Client/global state → Zustand (now out-downloading Redux) or Jotai for atomic/derived state. Redux Toolkit persists mainly in large existing enterprise codebases. See §9. |
| Testing default for new/Vite projects | Vitest + React Testing Library, with Playwright for E2E. Jest remains common in legacy/enterprise repos. See §14. |

---

## 1. CRITICAL — security advisory: "React2Shell" (CVE-2025-55182 / CVE-2025-66478)

**Check this before generating or reviewing any code that touches React Server Components, Server
Actions, or Next.js App Router.** This is not a routine lint nit — it's a maximum-severity,
unauthenticated remote-code-execution vulnerability that was mass-exploited in the wild by
state-linked threat actors within hours of disclosure, with reported near-100% exploit success
against unpatched defaults.

**What it is.** Disclosed by the React team on December 3, 2025 (researcher: Lachlan Davidson,
responsibly disclosed Nov 29, 2025), CVE-2025-55182 — dubbed "React2Shell" — is an unsafe
deserialization flaw in the RSC "Flight" protocol, the wire format React Server Components use to
send Server Function calls between client and server. A single crafted HTTP request to a Server
Function endpoint can trigger prototype pollution and achieve unauthenticated remote code
execution. Critically, **an application can be vulnerable even if it never defines an explicit
Server Function** — merely supporting RSC is enough, because a standard `create-next-app`
production build is exploitable out of the box with no code changes. Next.js tracks its downstream
exposure as CVE-2025-66478 (now merged into the same advisory).

**Affected versions / packages:**

| Package or framework | Vulnerable versions |
|---|---|
| `react-server-dom-webpack`, `react-server-dom-turbopack`, `react-server-dom-parcel` | 19.0.0, 19.1.0, 19.1.1, 19.2.0 |
| Next.js (App Router) | 15.0.4 – 16.0.6, plus canaries from 14.3.0-canary.77 |
| React Router (RSC mode), Waku, `@parcel/rsc`, `@vitejs/plugin-rsc`, RedwoodSDK (`rwsdk`) | Versions built on the same vulnerable Flight deserialization logic |

**Patched versions — verify the user is on at least one of these:**

| Package | Fixed at |
|---|---|
| React Server Components packages | 19.0.1, 19.1.2, 19.2.1 (or later) |
| Next.js | 15.0.5, 15.1.9, 15.2.6, 15.3.6, 15.4.8, 15.5.7, 16.0.7 (or later) |

**What to do with this information:**
- If a user mentions a React/Next.js version, or you see a `package.json`/lockfile, that falls in
  the vulnerable ranges above and the app uses (or could use) Server Components or Server Actions,
  proactively flag it — don't wait to be asked. Recommend upgrading to the patched line for their
  minor version immediately; there is no safe configuration workaround, only patching (WAF rules
  from Cloudflare/Vercel/Google Cloud Armor are defense-in-depth at best, not a fix).
  Next.js canaries pinned before 14.3.0-canary.77+ should be moved to a stable patched release
  rather than bumped to a newer canary.
- This is a good moment to generally remind users to keep React/Next.js current — patch releases
  for security issues have shipped multiple times in the 19.x line, and "pin and forget" is risky
  specifically for anything that runs Server Functions.
- This does **not** mean RSC/Server Actions are unsafe to use going forward — patched versions
  close the hole — but it's a reason to treat dependency freshness as a real security control for
  full-stack React, not just a hygiene nicety.

**General RSC/Server Action security hygiene** (independent of this CVE): always treat Server
Action arguments as untrusted input from the network — validate and authorize inside the action
itself, never assume a Server Action is only reachable from the UI that calls it (it's a public
HTTP endpoint); never pass secrets or unvalidated objects through `'use server'` boundaries; keep
`react`, `react-dom`, and the framework's RSC runtime on the same, current minor version, since the
RSC wire protocol is not guaranteed stable across minors.

---

## 2. Starting or scaffolding a project

**Do not suggest `create-react-app`.** It's been deprecated by the React team since February 2025;
it still technically runs in maintenance mode, but is not where new projects should start. The
official guidance now branches on whether the app needs server features at all.

| Need | Recommended tool | Scaffold command |
|---|---|---|
| Full-stack app, most opinionated, biggest ecosystem | Next.js (App Router) | `npx create-next-app@latest` |
| Full-stack, standards-first, you already like React Router | React Router v7 (framework mode) | `npx create-react-router@latest` |
| Full-stack, type-safety-first, you're invested in TanStack | TanStack Start (beta, stable enough for production but still moving) | clone a TanStack Router example; no dedicated CLI yet |
| Native iOS/Android/web from one React codebase | Expo | `npx create-expo-app@latest` |
| Pure client-side SPA, no server needed at all | Vite | `npm create vite@latest my-app -- --template react-ts` |

Decision notes:
- **Next.js** is the default safe choice for most teams: most mature, largest hiring pool, Vercel
  backing, supports CSR/SSR/SSG/static export, deployable to any Node/Docker host.
- **React Router v7** unified with what used to be Remix; framework mode is the closest analog to
  "old Remix" and is the recommended starting point if the user wants a full-stack app without
  Next.js's opinions. It has three modes — declarative (just `<Routes>`, no data APIs), data mode
  (`createBrowserRouter`, loaders/actions, but you bring your own server), and framework mode
  (full SSR, file-based conventions, a real backend). Don't assume "React Router" automatically
  means client-only routing anymore — ask or infer which mode is in play before writing loader
  code.
- **TanStack Start** trades Next.js's "follow our conventions" philosophy for "here are powerful,
  composable primitives" — fully type-safe end-to-end, built on TanStack Router + Vite, thinner
  runtime than Next.js, but younger and still stabilizing. Good fit for client-heavy apps already
  using TanStack Query/Router.
- **Plain Vite** is correct when there's genuinely no server-rendering need (an internal tool, a
  widget, an app behind auth that doesn't care about SEO/first-paint). It is not a framework —
  there's no built-in routing, data loading, or SSR; add React Router or TanStack Router yourself
  if you need routing.
- If the user is already on CRA, don't suggest a risky big-bang rewrite by default — point them at
  the official "migrate to a client-only SPA" path (swap to Vite, keep the app's actual code
  mostly intact) unless they explicitly want to adopt SSR/RSC, which is a bigger jump best framed
  as a deliberate decision, not a drive-by migration.

---

## 3. React 19 core features

These shipped in the stable Dec 2024 release. If a codebase is still writing `forwardRef`
everywhere or hand-rolling pending/error state for forms, it likely predates this and is a good
candidate for incremental modernization — but don't force a rewrite uninvited.

### Actions, useActionState, useOptimistic, useFormStatus

"Actions" is the umbrella term for **async functions passed to `startTransition`**. They
automatically track a pending state, surface errors to the nearest Error Boundary, and integrate
with optimistic updates — replacing the old hand-rolled `isPending`/`error` `useState` triad.

```jsx
// The old way: three pieces of state you manage by hand
function UpdateName() {
  const [name, setName] = useState('');
  const [error, setError] = useState(null);
  const [isPending, setIsPending] = useState(false);

  async function handleSubmit() {
    setIsPending(true);
    const err = await updateName(name);
    setIsPending(false);
    if (err) { setError(err); return; }
    redirect('/profile');
  }
  // ...
}

// The React 19 way: useActionState + <form action>
function UpdateName() {
  const [error, submitAction, isPending] = useActionState(
    async (previousState, formData) => {
      const err = await updateName(formData.get('name'));
      if (err) return err;
      redirect('/profile');
      return null;
    },
    null, // initial state
  );

  return (
    <form action={submitAction}>
      <input type="text" name="name" />
      <button type="submit" disabled={isPending}>Update</button>
      {error && <p>{error}</p>}
    </form>
  );
}
```

- `useActionState(actionFn, initialState)` returns `[state, wrappedAction, isPending]`. Pass
  `wrappedAction` straight to a `<form action={...}>` or call it yourself.
- `<form>`, `<input>`, and `<button>` now accept **functions** for `action`/`formAction`. On
  success, React resets uncontrolled forms automatically; call the new `requestFormReset()`
  (from `react-dom`) if you need to reset manually.
- `useOptimistic(currentValue, updateFn)` lets you render the *expected* result immediately while
  a mutation is in flight, then reverts automatically on error:

```jsx
function ChangeName({ currentName, onUpdateName }) {
  const [optimisticName, setOptimisticName] = useOptimistic(currentName);

  async function submitAction(formData) {
    const newName = formData.get('name');
    setOptimisticName(newName);              // shows instantly
    const updated = await updateName(newName); // real request
    onUpdateName(updated);
  }

  return (
    <form action={submitAction}>
      <p>Your name is: {optimisticName}</p>
      <input name="name" disabled={currentName !== optimisticName} />
    </form>
  );
}
```

- `useFormStatus()` (from `react-dom`) lets a deeply nested child read its parent `<form>`'s
  pending state without prop drilling or Context — it behaves as if the form were a Context
  provider:

```jsx
import { useFormStatus } from 'react-dom';

function SubmitButton() {
  const { pending } = useFormStatus();
  return <button type="submit" disabled={pending} />;
}
```
  Pitfall: `useFormStatus` only sees the *nearest enclosing* `<form>`. Call it from outside a
  form's subtree and `pending` is always `false`.

### `use()` — reading promises and context during render

`use` is not a Hook in the strict sense (it can be called conditionally, after early returns), but
it follows similar rules about where it can appear. It suspends a component until a promise
resolves:

```jsx
import { use, Suspense } from 'react';

function Comments({ commentsPromise }) {
  const comments = use(commentsPromise); // suspends until resolved
  return comments.map((c) => <p key={c.id}>{c.text}</p>);
}

function Page({ commentsPromise }) {
  return (
    <Suspense fallback={<div>Loading…</div>}>
      <Comments commentsPromise={commentsPromise} />
    </Suspense>
  );
}
```

It can also read Context conditionally (something `useContext` cannot do):

```jsx
function Heading({ children }) {
  if (children == null) return null;
  const theme = use(ThemeContext); // fine even after the early return above
  return <h1 style={{ color: theme.color }}>{children}</h1>;
}
```

Important constraint: **`use` cannot consume a promise created during that same render** — you'll
get an "uncached promise" warning. The promise has to come from somewhere Suspense-aware (a
framework's data layer, `cache()`, or TanStack Query's `useSuspenseQuery`), not a bare
`fetch(...)` called inline in the component body.

### `ref` as a normal prop — no more `forwardRef`

```jsx
// React 19: ref is just a prop name function components can declare
function MyInput({ placeholder, ref }) {
  return <input placeholder={placeholder} ref={ref} />;
}

<MyInput ref={someRef} />
```

`forwardRef` still works for backward compatibility but is on a deprecation path — write new
components without it. Refs to **class** components are not passed as a prop (they reference the
instance, as before).

**Ref callbacks can now return a cleanup function**, which React calls on unmount instead of
calling the ref with `null`:

```jsx
<div ref={(node) => {
  if (!node) return;
  const observer = new ResizeObserver(/* ... */);
  observer.observe(node);
  return () => observer.disconnect(); // cleanup, like an Effect
}} />
```
This is a breaking change for TypeScript: an arrow ref callback with an implicit return value
(`ref={current => (instance = current)}`) is now rejected, because TypeScript can't tell whether
you meant to return a cleanup function. Use a block body (`ref={current => { instance = current }}`).

### `<Context>` as its own provider

```jsx
const ThemeContext = createContext('light');

function App({ children }) {
  return <ThemeContext value="dark">{children}</ThemeContext>; // no .Provider
}
```
`<Context.Provider>` still works but is the old spelling now.

### Document metadata, stylesheets, scripts, and preloading — natively, in any component

You can render `<title>`, `<meta>`, and `<link>` from *any* component, and React hoists them to
`<head>` automatically — this works in client-only apps, streaming SSR, and Server Components
alike, without `react-helmet` or a manual Effect:

```jsx
function BlogPost({ post }) {
  return (
    <article>
      <title>{post.title}</title>
      <meta name="author" content={post.author} />
      <link rel="canonical" href={post.url} />
      <h1>{post.title}</h1>
      {/* ... */}
    </article>
  );
}
```
A dedicated metadata library (e.g. a framework's built-in `<Metadata>` API, or `react-helmet`) is
still worth it when you need route-based overriding of generic metadata — native support handles
the simple case, not the templating layer.

Stylesheets rendered with a `precedence` prop get DOM insertion order managed for you, and React
will block paint on external stylesheets that gate a Suspense boundary's content; identical
stylesheet renders from multiple components are deduplicated:

```jsx
<link rel="stylesheet" href="/theme.css" precedence="default" />
```

Async scripts (`<script async src="...">`) can be rendered anywhere in the tree, are deduplicated
across components, and in SSR are prioritized behind paint-blocking resources.

Resource-preloading APIs (`react-dom`) let you hint the browser early:

```jsx
import { prefetchDNS, preconnect, preload, preinit } from 'react-dom';

preinit('/critical.js', { as: 'script' });   // loads + executes eagerly
preload('/font.woff2', { as: 'font' });
prefetchDNS('https://api.example.com');
preconnect('https://api.example.com');
```

### Other React 19 improvements worth knowing about

- **Custom Elements**: full support, passing all of Custom Elements Everywhere's tests. Primitive
  props (`string`/`number`/`true`) render as attributes during SSR; on the client, props matching
  an instance property are assigned as properties, otherwise as attributes.
- **Hydration error messages** are now a single diff-style message instead of three separate,
  duplicated console errors.
- **Error reporting**: `createRoot`/`hydrateRoot` now accept `onCaughtError`, `onUncaughtError`,
  and `onRecoverableError` so you can route different error categories to your monitoring tool
  without console-log scraping.
- **`useDeferredValue(value, initialValue)`** now accepts an initial value for the first render,
  scheduling the real deferred value in the background afterward.
- Hydration is more tolerant of **third-party scripts and browser extensions** injecting DOM —
  unexpected tags in `<head>`/`<body>` are skipped rather than treated as a mismatch.

---

## 4. React 19.1 and 19.2 — what's new since the initial release

The React team has shipped roughly one minor every few months since 19.0. Treat these as current,
not bleeding-edge:

- **`<Activity>`** (19.2) — a structured alternative to `{isVisible && <Page />}` for keeping a
  subtree mounted-but-hidden:
  ```jsx
  import { Activity } from 'react';

  <Activity mode={isVisible ? 'visible' : 'hidden'}>
    <Page />
  </Activity>
  ```
  `hidden` unmounts effects and defers updates; `visible` mounts effects and updates normally. Use
  it to pre-render a screen the user is likely to navigate to next, or to preserve scroll/input
  state for a screen they navigated away from, without paying the render cost while it's hidden.

- **`useEffectEvent`** (19.2) — solves the long-standing "non-reactive value inside an Effect"
  problem. Previously, if an Effect needed to read a value (like a `theme` prop) without that
  value being a *reason to re-run* the Effect, you either disabled the exhaustive-deps lint rule
  (losing its protection) or fought the dependency array. `useEffectEvent` extracts the
  "event"-like part so it always sees the latest props/state without being a dependency:
  ```jsx
  function ChatRoom({ roomId, theme }) {
    const onConnected = useEffectEvent(() => {
      showNotification('Connected!', theme); // always sees latest theme
    });

    useEffect(() => {
      const connection = createConnection(serverUrl, roomId);
      connection.on('connected', () => onConnected());
      connection.connect();
      return () => connection.disconnect();
    }, [roomId]); // theme is correctly NOT a dependency — no lint suppression needed
  }
  ```
  Effect Events must be declared in the same component/Hook as the Effect that uses them, and must
  *not* appear in that Effect's dependency array — `eslint-plugin-react-hooks@latest` enforces
  both. Don't reach for this just to silence a lint warning; use it specifically for
  event-shaped logic fired from inside an Effect.

- **`cacheSignal`** (19.2, Server Components only) — tells you when a `cache()`-wrapped function's
  lifetime is over (render completed, aborted, or failed), so you can cancel in-flight work:
  ```jsx
  import { cache, cacheSignal } from 'react';
  const dedupedFetch = cache(fetch);
  async function Component() {
    await dedupedFetch(url, { signal: cacheSignal() });
  }
  ```

- **Partial pre-rendering** (19.2, `react-dom/static` + `react-dom/server`) — `prerender` an app
  with an `AbortController`, save the returned `postponed` state, ship the static `prelude` to a
  CDN immediately, then later call `resume`/`resumeAndPrerender` to fill in the dynamic parts.
  Lets you serve a fully static shell instantly while dynamic content streams in afterward.

- **Performance Tracks** (19.2) — custom Chrome DevTools performance-profile tracks ("Scheduler"
  and "Components") that show what priority React is working at and which components are
  rendering/running effects and for how long. Reach for this before reaching for `useMemo`-by-guesswork
  when chasing a real performance problem.

- **`eslint-plugin-react-hooks` v6** (19.2) — flat config (`eslint.config.js`) is now the default
  for the `recommended` preset, with opt-in Compiler-powered rules (e.g. flagging `setState`
  calls synchronously inside an Effect). If a project needs the old `.eslintrc`-style config,
  switch to the `recommended-legacy` preset rather than fighting the new default.

- The default `useId()` prefix changed twice (`:r:` → `«r»` → `_r_` in 19.2) to stay valid for
  `view-transition-name` and XML 1.0 names — irrelevant to app code unless something was
  snapshot-testing the literal id string.

---

## 5. React Server Components and Server Actions — the mental model

Two genuinely different concepts get conflated constantly; keep them separate:

- **Server Components** render ahead of time, in an environment separate from the
  browser/bundler, and **have no directive of their own**. In an RSC-enabled framework (Next.js
  App Router, React Router framework mode, Waku, TanStack Start, etc.), components are Server
  Components *by default*. You opt a subtree **into the client** with `'use client'` at the top of
  a file — everything that file exports becomes a Client Component (and so does everything it
  imports, transitively, unless that import has its own `'use client'` boundary).
- **Server Actions** are async functions marked `'use server'` that a Client Component can call as
  if they were local — the framework generates a reference, sends it to the client, and a call to
  that reference becomes a network request executing the real function on the server. **`'use
  server'` is for Server Actions, not Server Components** — there is no such thing as a `'use
  server'`-decorated Server Component; that's a common and understandable misreading.

Practical implications:
- Server Components can be `async` and read data directly (DB calls, server-only SDKs) without an
  API layer — that data fetching never round-trips to the client as JS.
- Server Components cannot use `useState`, `useEffect`, browser APIs, or event handlers — anything
  interactive needs to live in (or below) a `'use client'` boundary.
- Treat every Server Action as a public HTTP endpoint for security purposes (see §1) — the fact
  that it's "just a function call" in your source code is a development-time illusion.
- The underlying bundler-integration APIs for RSC are explicitly **not** covered by semver
  stability guarantees within the 19.x line (only the React Server Components *feature* itself is
  stable) — if you're building a bundler/framework integration rather than consuming one, pin
  exact versions.
- If the user isn't using an RSC-capable framework (e.g. they're on plain Vite), don't suggest
  `'use server'`/`'use client'` directives — they only mean something to a bundler that
  understands them.

---

## 6. The React Compiler

**Status: stable (v1.0, October 2025)**, not experimental — safe to recommend for production. It's
a build-time tool that automatically inserts the memoization a careful developer used to write by
hand with `useMemo`/`useCallback`/`React.memo`, by statically analyzing data flow across an entire
component (something a human adding `useMemo` one call at a time structurally can't do as
thoroughly).

**Setup:**
```bash
npm install --save-dev --save-exact babel-plugin-react-compiler@latest
```
Wire it into Babel/Vite/Rsbuild config, or for Next.js set `experimental.reactCompiler: true` (or
the stable equivalent in newer Next.js versions — check current docs, this flag has moved in and
out of `experimental`). It also works via an SWC plugin path for Turbopack/Parcel-based toolchains.
It is **not** tied to React 19 — for React 17/18 codebases, install `react-compiler-runtime` as a
polyfill and the compiler still works.

**Does this mean delete every `useMemo`/`useCallback`?** No — and don't go on a deletion spree
just because the compiler exists.
- Existing manual memoization is safe to leave; the compiler checks it for correctness rather than
  conflicting with it.
- The compiler's own internal mechanism (an internal hook, formerly called `useMemoCache`) is
  different from `useMemo`/`useCallback` under the hood, but produces the same practical effect.
- You can still opt a specific file out with the `"use no memo"` directive if you have a reason to
  hand-tune it.
- **Manual memoization is still genuinely useful for**: values handed across a boundary the
  compiler can't see into (a third-party library that does its own reference-equality checks);
  exceptionally expensive computations you want guaranteed-cached rather than best-effort;
  cases where you need a *stable* function identity as a dependency of another Hook for reasons
  beyond render-skipping.
- If a component violates the Rules of React (mutating props/state directly, calling Hooks
  conditionally, etc.), the compiler detects this and **bails out safely** for that component —
  it skips memoizing it rather than guessing and introducing a bug. This is itself a reason to fix
  Rules-of-React violations: not just correctness, but to actually get the compiler's benefit.
- Practical advice for new code: write plain, readable React first. Reach for manual memoization
  only after profiling shows a real, specific problem the compiler isn't solving — not
  speculatively.

---

## 7. Hooks reference and the Rules of Hooks

| Hook | Package | What it's for |
|---|---|---|
| `useState` | react | Local component state |
| `useReducer` | react | Local state with complex transition logic |
| `useEffect` | react | Synchronizing with an external system (see §8 before reaching for this) |
| `useLayoutEffect` | react | Like useEffect, but fires before the browser paints — for DOM measurements that must happen before the user sees a frame |
| `useInsertionEffect` | react | Rare; for CSS-in-JS libraries injecting styles before layout effects run. App code almost never needs this directly. |
| `useEffectEvent` | react | Non-reactive "event" logic referenced from inside an Effect (19.2+, see §4) |
| `useContext` | react | Read a Context value (unconditionally — use `use()` if you need conditional reads) |
| `useRef` | react | Mutable value that doesn't trigger re-renders; DOM node handles |
| `useImperativeHandle` | react | Customize what a `ref` exposes from a component |
| `useMemo` | react | Cache an expensive computed value between renders |
| `useCallback` | react | Cache a function identity between renders |
| `useTransition` | react | Mark a state update as non-urgent (and, since React 19, wrap async Actions) |
| `useDeferredValue` | react | Show stale content while a new value is computed in the background |
| `useId` | react | Stable unique IDs for accessibility attributes (not for list keys) |
| `useSyncExternalStore` | react | Subscribe to external (non-React) state safely under concurrent rendering |
| `useDebugValue` | react | Label a custom hook's value in React DevTools |
| `useOptimistic` | react | Optimistic UI while a mutation is pending (§3) |
| `useActionState` | react | Manage an Action's pending/result state (§3) |
| `useFormStatus` | react-dom | Read the nearest parent `<form>`'s pending state (§3) |
| `use` | react | Read a promise or Context value during render, including conditionally (§3) |
| `cacheSignal` | react | RSC-only: know when a `cache()` lifetime ends (§4) |

**Rules of Hooks** (the linter enforces these, and the Compiler depends on them holding):
1. Only call Hooks at the top level of a function component or another custom Hook — never inside
   loops, conditions, or nested functions. (`use()` is the deliberate exception to the
   "no conditionals" part of this rule.)
2. Only call Hooks from React function components or custom Hooks, never from plain JS functions.
3. Custom Hook names must start with `use` — this isn't cosmetic, it's how the linter and the
   Compiler recognize a function as participating in the Hooks contract at all.

---

## 8. "You Might Not Need an Effect" — decision framework

This is one of the highest-leverage things to get right in a React codebase, and overuse of
`useEffect` remains one of the most common sources of bugs and confusion, even among experienced
developers. The governing question:

> **Are you synchronizing with something outside React** (the network, the DOM, a third-party
> widget, a subscription, browser APIs)? If yes, an Effect is probably right. If no — if you're
> just reacting to a prop or state change within your own component tree — **you almost certainly
> don't need an Effect.**

Common situations that look like they need an Effect but don't:

- **Deriving a value from props/state.** Don't store it in state and sync it with an Effect — just
  compute it during render.
  ```jsx
  // ❌ Unnecessary Effect + extra state + extra render pass
  const [fullName, setFullName] = useState('');
  useEffect(() => { setFullName(`${firstName} ${lastName}`); }, [firstName, lastName]);

  // ✅ Just compute it
  const fullName = `${firstName} ${lastName}`;
  ```

- **Resetting all state when a prop changes** (e.g. a `userId` prop switches and the whole form
  should reset). Don't write an Effect that detects the change and resets fields one by one — pass
  a `key` so React treats it as a fresh component instance:
  ```jsx
  <ProfilePage userId={userId} key={userId} />
  ```

- **Adjusting *some* state when a prop changes**, without a `key`-driven full reset. Compute the
  derived part during render instead of mirroring it into state via an Effect — this is exactly
  the pattern the official `set-state-in-effect` lint rule and the community
  `eslint-plugin-react-you-might-not-need-an-effect` plugin's `no-derived-state` rule both exist
  to catch.

- **Handling a user event.** Logic that's a direct result of a click/submit/etc. belongs in the
  event handler, not in an Effect watching for the state that the event handler set. Putting it in
  an Effect delays it by an extra render and obscures cause and effect.

- **Chains of Effects, each setting state that triggers the next Effect.** This is a common
  "waterfall" bug. Refactor to compute everything possible up front in the event handler, and
  derive the rest during render — chained Effects usually mean state should be consolidated or a
  `useReducer` should own the whole transition.

- **Fetching data**, when a framework or library with built-in caching/race-condition handling is
  available. React's own docs note that fetching in an Effect is *fine* in the sense that it's
  genuinely synchronizing with the network, but call out real problems (race conditions, no
  caching, no dedup, no automatic retry) that a `useEffect` + `fetch` does not solve and a tool
  like TanStack Query or a framework's data layer does. Default to those over hand-rolled
  `useEffect` fetching for anything beyond a throwaway prototype.

Effects genuinely earn their keep for: subscribing to an external store (`useSyncExternalStore` is
often even better-suited), manually manipulating a non-React-owned DOM node, connecting to a
WebSocket/chat-room-style external system, logging/analytics side effects tied to a render, and
synchronizing with browser APIs that have no React-idiomatic equivalent.

Tooling: install `eslint-plugin-react-you-might-not-need-an-effect` to catch several of the above
patterns automatically (derived state, chained state updates, event-handler logic misplaced in an
Effect, state resets on prop change) — genuinely useful for both new learners and to catch
regressions in experienced teams' codebases.

---

## 9. State management — pick by state *type*, not by personal favorite

The 2026 consensus that's emerged is that state management isn't one decision anymore — it's
several smaller decisions per kind of state. Don't reach for one global library to solve all of
them.

| Kind of state | Default choice | Why |
|---|---|---|
| Local, single-component | `useState` / `useReducer` | No reason to externalize state only one component tree needs |
| Server data (anything fetched from an API/DB) | **TanStack Query** | Caching, dedup, background refetch, request cancellation — a hand-rolled store reinvents this badly |
| Form state | **React Hook Form** (+ Zod for schema validation), or React 19's `useActionState`/Actions for simpler forms | Avoids re-rendering the whole form on every keystroke; schema validation gives you parsing and types together |
| URL-shareable state (filters, pagination, selected tab) | Router state (`useSearchParams`, loader params) | If it should survive a refresh or be linkable, it belongs in the URL, not a JS store |
| Cross-cutting client UI state (theme, auth flag, locale) that changes rarely | `Context` | React 19 optimizes Context consumers reasonably well; rarely-changing values are exactly Context's sweet spot |
| Global client state that changes often (cart contents, multi-step wizard, app-wide UI flags) | **Zustand** | ~1KB, no Provider required, store is just a hook, built-in devtools/persist/immer middleware; now out-downloads Redux Toolkit |
| State with lots of interdependent derived/computed values | **Jotai** | Atomic model composes derived atoms more naturally than selector functions over one big store |
| Large enterprise codebase, already on Redux, need enforced patterns / time-travel debugging across a big team | **Redux Toolkit** | Legitimate to keep; rarely the right *first* choice for a new app in 2026 |

A few hard-won rules that cut across all of the above:
- **Don't put server data in Context or Zustand.** It needs cache invalidation semantics those
  tools don't give you for free; that's exactly TanStack Query's job.
- **Don't reach for global state as a first resort.** If only one component (or one component
  subtree) ever reads a value, it's local state or a prop, full stop — "might need it elsewhere
  later" is not a reason to globalize it now.
- **Context is not a performance optimization.** A Context value that changes frequently
  re-renders every consumer; it solves prop-drilling, not render-count. Frequently-changing,
  widely-consumed state wants Zustand/Jotai, not Context.
- Recoil is effectively abandoned/archived at this point — don't recommend it for new projects.
- It's normal and good for one app to use three of these at once: TanStack Query for server data,
  Zustand for global client UI state, React Hook Form for forms. That's not "too many state
  libraries," that's matching tools to problems.

```jsx
// Zustand: a store is just a hook, no Provider
import { create } from 'zustand';

const useCartStore = create((set) => ({
  items: [],
  addItem: (item) => set((state) => ({ items: [...state.items, item] })),
}));

function CartButton() {
  const items = useCartStore((state) => state.items); // select just what you need
  return <button>Cart ({items.length})</button>;
}
```

```jsx
// Jotai: atoms compose
import { atom, useAtom } from 'jotai';

const userAtom = atom(null);
const isLoggedInAtom = atom((get) => get(userAtom) !== null); // derived, recomputes automatically
```

---

## 10. Data fetching and Suspense

- **`use()` + Suspense** is the React-native primitive for "render this once a promise resolves,"
  but it needs a Suspense-aware source of the promise (see §3's caveat about uncached promises).
- **TanStack Query's `useSuspenseQuery`** is the practical way to get Suspense-driven data fetching
  with caching, in a framework-agnostic way, without building your own cache:
  ```jsx
  function Profile({ userId }) {
    const { data: user } = useSuspenseQuery({
      queryKey: ['user', userId],
      queryFn: () => fetchUser(userId),
    });
    return <h1>{user.name}</h1>;
  }
  // wrap with <Suspense fallback={...}> and an Error Boundary at an appropriate level
  ```
- **Always pair Suspense boundaries with an Error Boundary** above or alongside them — a rejected
  promise/thrown error needs somewhere to be caught, Suspense alone only handles the pending case.
- In RSC frameworks, **`async` Server Components** that `await` data directly are often simpler
  than threading a promise down to `use()` in a child — reach for `use()` mainly when the
  component receiving the promise is a Client Component, or when you deliberately want to start
  a fetch high in the tree and let a deeply nested component suspend on it.
- For SSR streaming specifically: as of 19.2, server-rendered Suspense boundaries are **batched**
  for a short window so reveals don't visually trickle in piecemeal the way they could before —
  this happens automatically; nothing to configure, but useful to know when explaining why
  streaming output "feels" different from raw `renderToReadableStream` semantics pre-19.2.

---

## 11. Performance

1. **Profile before optimizing.** Use React DevTools' Profiler tab, or — for React 19.2+ — the new
   Scheduler/Components custom tracks in Chrome DevTools' Performance panel, which show what
   priority work is happening and which components are responsible. Guessing which component is
   slow and wrapping it in `useMemo` is no longer even the *fast* way to optimize, now that
   profiling tools are this good.
2. **Let the Compiler handle render-skipping memoization** (§6) rather than hand-placing
   `useMemo`/`useCallback`/`React.memo` speculatively. Where the Compiler isn't enabled, the
   classic guidance still applies: `React.memo` a component, `useCallback` the function props you
   pass to it, `useMemo` the non-primitive props you pass to it — all three together, or the memo
   does nothing.
3. **Code-split with `lazy` + `Suspense`** for routes/heavy components not needed on first paint:
   ```jsx
   const Editor = lazy(() => import('./Editor'));
   // <Suspense fallback={<Spinner />}><Editor /></Suspense>
   ```
4. **Virtualize long lists.** Rendering thousands of DOM nodes is a DOM problem no amount of React
   memoization fixes — use `@tanstack/react-virtual` (or a framework's equivalent) once a list
   regularly exceeds a couple hundred items.
5. **State colocation beats memoization.** A piece of state that only affects a small subtree
   should live in that subtree, not lifted to a common ancestor "just in case" — lifting
   unnecessarily widens the blast radius of every update.
6. **`useTransition`/`startTransition`** for marking expensive UI updates (large list re-filters,
   tab switches with heavy content) as interruptible/non-urgent so typing and clicking stay
   responsive while the expensive update happens in the background.
7. Resource hints (`preload`/`preinit`/`preconnect`/`prefetchDNS`, §3) and native stylesheet
   `precedence` handling are part of the performance story too, not just a DX nicety — use them
   for fonts, critical scripts, and known-upcoming-navigation API hosts.

---

## 12. TypeScript with React 19

```tsx
// Children: prefer the React-provided helper types over hand-rolling them
import { PropsWithChildren, ReactNode } from 'react';

interface CardProps { title: string; }
function Card({ title, children }: PropsWithChildren<CardProps>) { /* ... */ }

// ReactNode is the maximally-permissive "anything React can render" type.
// ReactElement / JSX.Element are narrower — usually only needed for a function's *return* type,
// not for a children prop.
```

```tsx
// ref as a prop (post-forwardRef, React 19+)
import type { Ref } from 'react';

interface MyInputProps {
  ref?: Ref<HTMLInputElement>;
  placeholder: string;
}
function MyInput({ placeholder, ref }: MyInputProps) {
  return <input placeholder={placeholder} ref={ref} />;
}

// Don't hand-write children/ref over and over — compose the official helpers instead:
type ButtonProps = React.ComponentProps<'button'>;              // every native <button> prop, typed
type CardProps = PropsWithChildren<{ title: string }> & React.RefAttributes<HTMLDivElement>;
type InputProps = Omit<React.ComponentProps<'input'>, 'onChange'> & {
  onChange: (value: string) => void; // override one prop's signature deliberately
};
```

```tsx
// Event handlers
interface ButtonProps {
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
}
```

Notes:
- `React.FC` no longer implicitly includes `children` in its prop type (changed with the React 18
  types) — don't assume `FC<Props>` gives you `children` for free; add it explicitly via
  `PropsWithChildren` if needed, or just skip `FC` and type props directly (increasingly the
  preferred style — `FC` adds little besides an implicit return type and historically-incorrect
  `children` assumptions).
- For wrapper/HOC-style components, `React.ComponentProps<typeof SomeComponent>` keeps your
  wrapper's prop type in sync with whatever it wraps, instead of manually duplicating fields that
  will drift.
- Type hook return values explicitly for custom hooks consumed across module boundaries — inferred
  tuple types from `useState`-returning custom hooks can otherwise widen unhelpfully at the call
  site.

---

## 13. Testing

**Default for new projects (especially Vite-based): Vitest + React Testing Library.** Jest remains
a perfectly reasonable choice for existing/enterprise codebases already standardized on it — this
isn't a "rip out Jest" situation, just the default for green-field work, since Vitest shares Vite's
config/transform pipeline and is meaningfully faster on most real codebases.

Core principle, regardless of runner: **test behavior, not implementation.** Query by what a user
would see/do (role, label, text), not by CSS class or component internals — implementation-detail
tests break on harmless refactors and don't catch real regressions.

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

describe('LoginForm', () => {
  it('submits the entered email', async () => {
    const onSubmit = vi.fn();
    render(<LoginForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByRole('textbox', { name: /email/i }), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: /log in/i }));

    expect(onSubmit).toHaveBeenCalledWith('a@b.com');
  });
});
```

- Prefer `getByRole` > `getByLabelText` > `getByText` > `getByTestId`, in roughly that order —
  `getByTestId` is a last resort, not a default; reaching for it constantly is usually a sign the
  markup itself isn't accessible enough to query naturally.
- **MSW (Mock Service Worker)** for mocking network requests at the network layer rather than
  mocking `fetch`/your API client directly — tests then exercise the real request code path.
- **Playwright** (or Cypress) for end-to-end coverage of a handful of genuinely critical user
  flows — not a substitute for component tests, and not something to write dozens of for every
  minor UI permutation; E2E suites get slow and flaky fast if over-applied.
- For custom hooks in isolation, `renderHook` from Testing Library lets you test hook logic without
  needing a full component around it.

---

## 14. Accessibility

The single highest-leverage rule: **use semantic HTML before reaching for ARIA.** A `<button>` has
correct keyboard handling, focus behavior, and screen-reader semantics for free; a
`<div onClick>` has none of that until you manually rebuild it with `tabIndex`, `role`,
`onKeyDown`, and focus styles — and it's easy to miss a case. "No ARIA is better than bad ARIA" is
the field's own guiding maxim for a reason.

```jsx
// ❌ "Div soup" — every interaction has to be rebuilt by hand, and easy to get wrong
<div className="nav">
  <div onClick={goHome}>Home</div>
</div>

// ✅ Semantic elements get the behavior for free
<nav aria-label="Main navigation">
  <ul><li><a href="/">Home</a></li></ul>
</nav>
```

Practical checklist:
- Landmark elements (`<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`) give assistive tech
  users a way to jump between page regions — use them even when you're not asked to.
- Reach for ARIA only for genuinely custom widgets without a native HTML equivalent (custom
  dropdowns, tab panels, modal dialogs) — and when you do, keep ARIA state synced with actual
  component state (`aria-expanded` must flip when the dropdown actually opens, not lag behind).
- Manage focus deliberately for modals/dialogs: trap focus inside while open, return it to the
  triggering element on close, and ensure there's no way to keyboard-tab to something hidden
  behind an open modal.
- Label every form input programmatically (`<label htmlFor>` or `aria-label`), not just by visual
  proximity — visual proximity alone tells a screen reader nothing.
- Test with the actual tools, not just by eye: axe DevTools or Lighthouse for automated checks,
  and at least spot-check with a real screen reader (VoiceOver on macOS, NVDA on Windows) for
  anything genuinely custom/interactive.

---

## 15. Project structure and architecture

**Feature-based ("screaming architecture") organization is the dominant pattern for medium-to-large
apps in 2026** — group files by what they *do* (a business domain/feature), not by what *kind* of
file they are. The old `components/`, `hooks/`, `utils/` top-level split scales poorly once an app
has more than a handful of screens, because finding everything related to one feature means
hopping between four unrelated folders.

```
src/
├── app/                    # entry point, providers, root routing
├── features/
│   ├── auth/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── api/            # TanStack Query hooks for this feature's endpoints
│   │   └── index.ts         # public API barrel — only export what other features should use
│   ├── billing/
│   └── dashboard/
├── components/              # genuinely reusable, feature-agnostic UI (Button, Modal, Input)
├── hooks/                   # genuinely reusable, feature-agnostic hooks
└── lib/                     # API client setup, third-party config, generic utilities
```

Guidance that holds regardless of the exact folder names chosen:
- Keep `components/`/`hooks/` at the root reserved for things with **no feature-specific
  knowledge** at all — the moment a component knows about "users" or "invoices," it belongs in
  that feature folder, not the shared one.
- Use an `index.ts` barrel per feature to define its public surface; other features should import
  from the barrel, not reach into a sibling feature's internal files directly — this is what keeps
  features actually decoupled instead of just colocated.
- Two of the most common real architecture problems in inherited codebases are **defaulting to
  global state** (everything dumped into Redux/Zustand regardless of whether more than one
  component tree needs it) and **over-extracting components** (wrapping every five lines of JSX in
  its own component "for cleanliness," producing files with a dozen tiny components and tangled
  prop-chains that make a single feature's logic harder, not easier, to follow). Extract a
  component when there's a concrete reason — reuse, independent testability, or a file that's
  truly hard to navigate — not as a default reflex.
- This isn't one-size-fits-all: a small app is fine with a flat structure; don't impose
  feature-folder ceremony on a project with five components total.

---

## 16. Routing in more detail

**Next.js App Router** — file-based: a route is a folder under `app/` with a `page.tsx`;
`layout.tsx` wraps nested routes; Server Components by default, opt into `'use client'` per file;
data fetching is usually `async`/`await` directly in Server Components rather than a separate
loader concept.

**React Router v7** — three distinct modes, and "I'm using React Router" no longer implies just one
of them:
- *Declarative mode*: `<Routes>`/`<Route>`, no built-in data loading — closest to "classic" React
  Router; you fetch data yourself, typically in an Effect or a query hook.
- *Data mode*: `createBrowserRouter` + `RouterProvider`, unlocking `loader`/`action` per route and
  automatic revalidation after a `<Form>` submission — runs in the browser, you still bring your
  own server/API.
  ```jsx
  const router = createBrowserRouter([
    { path: '/dashboard', element: <Dashboard />, loader: () => fetch('/api/stats').then(r => r.json()) },
  ]);
  // in Dashboard: const stats = useLoaderData();
  ```
- *Framework mode*: `npx create-react-router@latest`, file-based conventions, loaders/actions run
  **on the server**, full SSR. This is the recommended starting point for a new full-stack app
  built around React Router rather than Next.js.

Before writing loader/action code, confirm which mode the project is actually in — the same
function names (`loader`, `action`) mean "runs in the browser, you supply the backend" in data
mode versus "runs on a real server, has access to request/cookies" in framework mode, and that
distinction matters enormously for anything involving auth or secrets.

---

## 17. Common anti-patterns and gotchas

| Anti-pattern | Why it bites | Fix |
|---|---|---|
| Array index as the `key` in a dynamic/reorderable list | Breaks React's identity tracking on insert/remove/reorder — wrong state can attach to the wrong row | Use a stable, unique id from the data itself |
| Mutating state directly (`state.items.push(x)`, `count++`) | React compares by reference; a mutated-in-place object looks unchanged, so the re-render that should happen doesn't | Always create a new object/array: `setState([...items, x])` |
| `useEffect` for anything not synchronizing with an external system | Extra render passes, hidden bugs, and is the single most common source of "why does this re-render twice" confusion | See §8 |
| Prop drilling through 4+ layers just to reach one deeply-nested consumer | Every intermediate component re-renders on the value's change and has to forward a prop it doesn't use | Context (rare changes) or a store (frequent changes) — see §9 |
| One giant component mixing data fetching, business logic, and markup | Hard to read, hard to test, hard to reuse any part of it | Extract a custom hook for the logic/data, keep the component focused on rendering |
| Calling a Hook inside a condition/loop/nested function | Breaks React's per-render Hook-call-order bookkeeping — can silently corrupt unrelated state | Always call Hooks unconditionally at the top level (§7) |
| Controlled input that's sometimes `undefined` | React warns about switching between controlled/uncontrolled, and the input can lose its "controlled" status mid-life | Always supply at least `''`/`0`/`false` as the initial value, never `undefined` |
| Defaulting every piece of UI state to global (Redux/Zustand/Context) "just in case" | State explosion, unnecessary coupling, harder reasoning about what affects what | Local `useState` until something genuinely needs to be shared (§9, §15) |
| Skipping tests on anything with real branching logic (form validation, async mutations) | The bugs that get through are exactly the ones manual testing reliably misses (edge cases, race conditions) | At minimum, cover the non-happy paths with RTL/Vitest (§14) |

---

## 18. ESLint / tooling baseline

```js
// eslint.config.js — flat config is now the default shape
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  // ...other config...
  reactHooks.configs.recommended, // v6+: flat config by default; use recommended-legacy for .eslintrc
];
```

- `eslint-plugin-react-hooks@latest` (v6+) ships Compiler-aware rules in addition to the
  long-standing `rules-of-hooks` and `exhaustive-deps` — keep it current rather than pinned to an
  old major, since some of the newer guidance (e.g. around `useEffectEvent`) depends on linter
  awareness of the newer APIs.
- Pair with `eslint-plugin-react-you-might-not-need-an-effect` (§8) for an extra layer of
  Effect-overuse detection beyond what the core hooks plugin catches.
- If using the Compiler (§6), its ESLint integration surfaces components where the compiler had
  to bail out — treat those as a to-do list of Rules-of-React fixes, not noise to suppress.

---

## 19. Library reference (2026 snapshot)

| Category | Library | Notes |
|---|---|---|
| Server state | TanStack Query (React Query) v5 | The default; pair with `useSuspenseQuery` for Suspense-driven fetching |
| Client/global state | Zustand | ~1KB, hook-based store, no Provider; now out-downloads Redux Toolkit |
| Atomic/derived state | Jotai | Bottom-up atom model, good for heavily-interdependent computed values |
| Enterprise/legacy state | Redux Toolkit | Still right for big existing codebases needing enforced patterns + time-travel debugging |
| Forms | React Hook Form + Zod | Uncontrolled-by-default for performance; Zod gives you parsing and types from one schema |
| Routing (SPA only) | React Router v7, declarative or data mode | Pick data mode once you want loaders/actions without a full framework |
| Routing (full-stack) | Next.js App Router / React Router v7 framework mode / TanStack Start | See §2 for how to choose |
| Unit/component testing | Vitest + React Testing Library | Default for new/Vite projects; Jest still fine for existing repos |
| E2E testing | Playwright | Cypress remains a reasonable alternative |
| Network mocking in tests | MSW (Mock Service Worker) | Mocks at the network layer, not the call site |
| List virtualization | `@tanstack/react-virtual` | Needed once lists regularly exceed a few hundred rows |
| Styling | Tailwind CSS (utility-first), CSS Modules, or vanilla-extract | Pick one consistently per project; don't mix paradigms within the same codebase |
| Headless UI primitives | Radix UI (and increasingly Base UI as an alternative) | Accessible, unstyled building blocks — handles keyboard/ARIA so you don't have to |
| Styled component system on top of Radix | shadcn/ui | Copy-in component source (not an npm runtime dependency) over Radix + Tailwind |
| Animation | Motion (the library formerly named Framer Motion) | Declarative, physics-based; framework-agnostic despite the React-centric history |
| Icons | lucide-react | Common default; tree-shakeable |
| Build tool (SPA, no framework) | Vite | Replaces Create React App's old role for client-only apps |

---

## 20. Quick decision checklist

Apply these defaults when writing or reviewing React code, in roughly this order:

1. **Check for the React2Shell CVE exposure first** if RSC/Server Actions/Next.js are anywhere in
   scope (§1) — this takes priority over style/architecture concerns.
2. **Never suggest Create React App** for a new project; route to a framework or Vite (§2).
3. **Default to React 19.2 semantics** — `ref` as a prop, `<Context>` as its own provider,
   Actions/`useActionState` for async form/mutation flows — unless the codebase is visibly older.
4. **Before writing a `useEffect`, ask the synchronization question** (§8). If the answer is "I'm
   just deriving/reacting to local state," don't write the Effect.
5. **Don't hand-place `useMemo`/`useCallback` reflexively** if the React Compiler is enabled (or
   could reasonably be enabled) — let it do that job; reserve manual memoization for profiled,
   specific cases (§6, §11).
6. **Route state to the right tool by kind**, not by habit: server data → TanStack Query, forms →
   React Hook Form, shareable filters → the URL, frequently-changing global UI state → Zustand,
   rarely-changing global state → Context (§9).
7. **Reach for semantic HTML before ARIA**, every time a custom interactive widget is being built
   (§14).
8. **Prefer feature-based folder structure** once a project has more than a handful of screens
   (§15), and don't default new state to global scope (§9, §17).
9. **Test behavior via React Testing Library queries**, not implementation details or test IDs as
   a first resort (§14).
10. **When in doubt about exact current API names/flags** (e.g. a Next.js config flag's exact
    location, a library's current major version), say so and suggest verifying against current
    docs rather than asserting a specific detail with false confidence — this ecosystem moves fast
    enough that precise flag names and package versions are exactly the kind of thing that drifts.