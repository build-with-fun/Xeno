---
name: mobile-app-development
description: Comprehensive expertise in building production-ready mobile apps with React Native and Expo, covering React Native CLI, Expo SDK, Expo Router, EAS Build/Submit/Update, and the New Architecture (Fabric, TurboModules, JSI, Bridgeless). Includes navigation, styling, UI component libraries, animations, gestures, icons, fonts, state management, forms, storage, performance optimization, accessibility, testing, scalable project architecture, and modern mobile UI/UX principles (Material Design 3, Apple HIG, dark mode, motion, onboarding, micro-interactions). Apply this knowledge whenever designing, developing, structuring, styling, animating, optimizing, or troubleshooting React Native/Expo applications or mobile screens/components.
---

# Mobile App Development — React Native & Expo Mastery Reference

A single, dense reference for building real mobile products with React Native. It covers both major workflows (Expo and the bare React Native Community CLI), the full modern UI/UX toolchain, and the design principles that separate an app that merely runs from one that feels native. Written for an ecosystem that moves fast — treat every specific version number below as "true as of when this was written" and spot-check anything version-sensitive with `npm view <package> version` or the project's official changelog before locking in a dependency.

## Table of Contents

1. [The 2026 Landscape at a Glance]
2. [Core Vocabulary]
3. [Expo vs React Native CLI — The Decision]
4. [The New Architecture: Fabric, TurboModules, JSI, Bridgeless]
5. [Project Setup]
6. [Expo Deep Dive]
7. [React Native CLI Deep Dive]
8. [Navigation]
9. [Styling Systems]
10. [UI Component Libraries]
11. [Animation & Gesture Systems]
12. [Icons]
13. [Fonts & Typography]
14. [Mobile UI/UX Design Principles]
15. [Design Systems & Design Tokens]
16. [State Management & Data Fetching]
17. [Forms & Validation]
18. [Lists, Images & Performance]
19. [Local Storage]
20. [Accessibility]
21. [Testing]
22. [Project Structure & Architecture]
23. [Quick-Reference Cheat Sheets]
24. [Common Pitfalls]
25. [Further Reading]

---

## 1. The 2026 Landscape at a Glance

React Native is no longer "a bridge to native views" — the legacy bridge is gone by default. Here's the state of the world this document assumes:

| Layer | Current default | Notes |
|---|---|---|
| React Native core | 0.86.x | New Architecture mandatory since 0.82; bridgeless by default since 0.78 |
| React | 19.2.x | Concurrent features (`useTransition`, `Suspense`, `React.Activity`) now work in RN via Fabric |
| Expo SDK | 57 (SDK 56 shipped React Native 0.85 / React 19.2) | Three SDK releases a year, each pinned to one RN version |
| Navigation | React Navigation 7.x stable, 8.0 in alpha | Expo Router (file-based, built on React Navigation primitives, partially forked from it as of SDK 56) is the default for new Expo apps |
| Animation | Reanimated 4.x (worklets split into `react-native-worklets`) | New Architecture only; 3.x still works on old architecture but is legacy |
| Gestures | Gesture Handler 3.x | Hook-based API, New Architecture only (min RN 0.82) |
| Styling | NativeWind 4.x stable (Tailwind v3 semantics), Tamagui, StyleSheet | NativeWind v5 (Tailwind v4, CSS-first config) is in preview |
| Component libraries | React Native Paper 5.x (Material 3), gluestack-ui v3 (NativeBase's successor), Tamagui, UI Kitten | NativeBase itself is sunset in favor of gluestack-ui |
| Icons | `@react-native-vector-icons/*` (scoped packages, direct `expo-font` integration) | `@expo/vector-icons` is being deprecated/phased out — see Part 12 |
| State | Zustand + TanStack Query is the modern default pairing | Redux Toolkit still fits large teams/compliance; Jotai for atomic/fine-grained UI |
| Lists | FlashList v2 (JS-only, no size estimates, New Architecture only) | LegendList is a newer, New-Architecture-native contender |
| Storage | `react-native-mmkv` v4 (Nitro Module) for fast state; `expo-secure-store` for secrets; AsyncStorage only for compatibility | |
| Design language | Material 3 "Expressive" (Android), Liquid Glass / iOS 26 HIG (Apple) | Both pushed major expressive/motion updates in 2025–2026 |

The throughline for 2026: **the New Architecture is not optional anymore**, file-based routing (Expo Router) has become the default navigation mental model for new apps, and the ecosystem has converged on a "boring is good" state-management stack (Zustand + TanStack Query) after years of Redux dominance.

---

## 2. Core Vocabulary

Skim this once if any term below is unfamiliar — it's assumed knowledge for the rest of the document.

- **Bridge (legacy)** — the old asynchronous, JSON-serializing communication channel between the JavaScript thread and native code. Removed by default in modern RN.
- **JSI (JavaScript Interface)** — the C++ layer that lets JavaScript hold direct references to native objects and call native functions synchronously, without serialization. The foundation the New Architecture is built on.
- **Fabric** — the New Architecture's renderer. Replaces the old UIManager; supports concurrent, interruptible rendering compatible with React 18+ features.
- **TurboModules** — the New Architecture's native module system. Modules are lazily loaded (only initialized the moment JS first touches them) and typed via Codegen, replacing the old `NativeModules` API that eagerly loaded everything at startup.
- **Codegen** — a build-time tool that generates C++/Objective-C/Kotlin glue code from TypeScript/Flow type specs, so the JS↔native boundary is type-checked instead of discovered at runtime.
- **Bridgeless mode** — the end state where the message-loop bridge is removed entirely, including for internal RN plumbing (timers, error boundaries). Default since RN 0.78.
- **Hermes** — Meta's JavaScript engine purpose-built for React Native (ahead-of-time bytecode compilation, small binary size, low memory). Default engine since RN 0.70.
- **Worklet** — a short JavaScript function tagged with the `'worklet'` directive that can be serialized and run on a different JS runtime (typically the UI thread), used heavily by Reanimated and Gesture Handler to keep animations off the main JS thread.
- **Managed vs bare (Expo)** — "managed" means Expo owns your native `ios`/`android` folders (regenerated on demand via `prebuild`); "bare"/"CLI" means you own and commit those folders yourself. This distinction has blurred: modern Expo apps almost always use **Continuous Native Generation (CNG)**, treating native folders as build artifacts even while using custom native code via config plugins.
- **Config plugin** — a Node.js function that mutates native project files (`Info.plist`, `AndroidManifest.xml`, Gradle files, etc.) during `expo prebuild`, letting a managed/CNG project use native customizations without hand-editing native code.
- **EAS (Expo Application Services)** — Expo's hosted cloud platform: EAS Build (compiles native binaries in the cloud), EAS Submit (uploads to App Store Connect / Google Play), EAS Update (ships JS/asset-only OTA updates), and EAS Workflows (CI/CD orchestration).

---

## 3. Expo vs React Native CLI — The Decision

This is the first fork in the road for any new project, and in 2026 it's a much easier call than it used to be: **default to Expo.** The old "Expo is a toy, CLI is for real apps" split has not been true for years — Expo apps ship to production at massive scale, and Expo fully supports custom native code. The question is no longer "can I use Expo," it's "do I have a specific reason not to."

### Default to Expo when:
- You're starting a new project (this covers the overwhelming majority of cases in 2026).
- You want OTA JavaScript updates (EAS Update) without waiting on App Store/Play Store review for bug fixes.
- You want cloud builds so contributors don't need Xcode/Android Studio installed locally, and so Windows/Linux devs can build iOS binaries.
- You want file-based routing, universal (web + native) code sharing, or the growing catalog of first-party modules (camera, notifications, background tasks, secure storage, in-app purchases, etc.) maintained as a coherent, versioned SDK instead of a pile of independently-versioned community packages.
- You need custom native code occasionally, but not so much that you'd rather hand-manage Podfiles and Gradle files yourself — config plugins cover the large majority of native customization needs (permissions, entitlements, native SDK linking) without touching native code directly.

### Reach for bare React Native CLI when:
- Your app is primarily a thin React Native layer over a large amount of pre-existing native code (e.g., adding RN screens to a native iOS/Android app — a "brownfield" integration).
- You need exotic, low-level native control that fights the config-plugin model — deep custom build pipeline changes, unusual native SDKs with no config plugin and no Expo Module wrapper, or highly bespoke CI that a managed native-generation flow would fight against.
- Organizational policy requires full, permanent ownership of the native project files with no cloud build dependency at all, including offline/air-gapped builds.
- You're maintaining a large legacy app that predates Expo's modern CNG model and a migration isn't currently worth the cost.

### What actually changed to make this an easy call
Historically the friction was "Expo apps can't use custom native modules." That's no longer true:
- **Expo Modules API** lets you write native modules in a small, modern Swift/Kotlin DSL — no Objective-C, Java, JNI, or hand-written C++ bridging code required — and it autolinks automatically.
- **Config plugins** cover the vast majority of "I just need to add this native SDK / permission / entitlement" needs without ejecting.
- **`npx expo prebuild`** generates the native `ios`/`android` folders on demand from your config, so you can drop into native code whenever you truly need to, then regenerate cleanly later — you are never locked out of "real" native development by choosing Expo.
- **EAS Build supports arbitrary bare React Native projects**, not just Expo-flavored ones — so "I want EAS's cloud builds" is not, by itself, a reason to pick Expo over CLI either. The dividing line is really about SDK convenience and Continuous Native Generation vs. hand-owned native folders.

### Quick comparison table

| | Expo (recommended default) | React Native CLI (bare) |
|---|---|---|
| Native folders | Generated via `prebuild` (CNG); typically gitignored | Committed to the repo, hand-maintained |
| Native module system | Expo Modules API (Swift/Kotlin DSL) + any RN TurboModule | Any RN TurboModule / legacy native module |
| Custom native code | Via config plugins + Expo Modules, or drop into generated folders | Directly, always |
| Cloud builds | EAS Build (first-class) | EAS Build (also supported) or local Xcode/Android Studio |
| OTA JS updates | EAS Update (first-class, built in) | Possible via `expo-updates` installed standalone, or third-party OTA tooling |
| Routing | Expo Router (file-based) or React Navigation | React Navigation (or Expo Router, added manually) |
| Preview on device | Expo Go (subset of SDK, no custom native code) or Dev Client (full custom build) | Dev builds only (no Expo Go equivalent) |
| First-party SDK breadth | Very wide (camera, av, notifications, sensors, secure storage, in-app purchases, background tasks, blur, haptics, sharing, etc.) as one versioned unit | Whatever the community ecosystem provides, versioned independently per package |
| Best for | New apps, teams that want velocity, OTA updates, cross-platform (+web) code sharing | Brownfield/native-heavy integration, unusual native requirements, orgs requiring full native ownership |

One nuance worth internalizing: **"Expo Go" and "Expo" are not the same thing.** Expo Go is a pre-built sandbox app on the App/Play Store used for the fastest possible iteration during early development — it only supports the Expo SDK modules already baked into it (and only the single latest SDK version, since Apple review lag means Expo Go on the App Store can trail the newest SDK by a version or so). The moment you add any custom native code or a library that isn't in Expo Go's baked-in module set, you move to a **development build** (`npx expo run:ios` / `run:android`, or an EAS-built dev client) — still fully "Expo," just no longer constrained to Expo Go's pre-bundled native binary. Production apps should always be built and tested through development builds / EAS Build, not shipped through Expo Go.

---

## 4. The New Architecture: Fabric, TurboModules, JSI, Bridgeless

Understanding this once pays off constantly — it explains why certain libraries require a minimum RN version, why "remote JS debugging" was replaced, and why performance profiles changed so much since 2022–2024.

### The problem it solved
The legacy architecture split work across three threads (JS thread, native/UI thread, and a Shadow thread for Yoga layout) that could only talk to each other through **the bridge**: every call was serialized to JSON, sent asynchronously, and deserialized on the other side. This was fine for occasional calls, but it fell apart under load — fast list scrolling, gesture-driven UI, or chatty native modules created "bridge congestion," visible as dropped frames and jank. It also made concurrent React features (introduced in React 18) impossible to support properly, since UI updates couldn't be reliably synchronized with JS-side rendering priorities.

### The four pieces of the New Architecture

1. **JSI (JavaScript Interface)** — a C++ layer that gives the JS engine direct references to native objects/functions. JS can call native code **synchronously**, with no JSON serialization step. This is the foundational layer everything else is built on.
2. **Fabric** — the new renderer, replacing the old UIManager. Supports concurrent, interruptible rendering, so React 18+ features (`useTransition`, `Suspense`, automatic batching, `React.Activity`) work correctly, and UI updates can be prioritized instead of blocking on whatever JS is doing.
3. **TurboModules** — the new native module system. Unlike the old `NativeModules` API (which eagerly initialized every registered native module at app startup, however unused), TurboModules are **lazily loaded** — a Bluetooth module you never touch is simply never initialized, which measurably improves cold-start Time-to-Interactive.
4. **Codegen** — generates the C++/ObjC/Kotlin glue code from a typed spec file (TypeScript or Flow), so the JS↔native contract is checked at build time instead of failing at runtime with an opaque native crash.

**Bridgeless mode** is the end state of this transition: the legacy message-loop bridge is removed completely, including for internal RN plumbing like timers and error boundaries — not just for TurboModules. It's been the default since RN 0.78; new projects don't even carry the option to re-enable the old bridge.

### What a TurboModule spec looks like

```ts
// NativeDeviceInfo.ts — the typed spec Codegen reads
import type { TurboModule } from 'react-native';
import { TurboModuleRegistry } from 'react-native';

export interface Spec extends TurboModule {
  getDeviceModel(): string;                 // synchronous — impossible on the old bridge
  getBatteryLevel(): Promise<number>;
  getStorageInfo(): Promise<{ total: number; available: number }>;
}

export default TurboModuleRegistry.getEnforcing<Spec>('DeviceInfo');
```

The synchronous `getDeviceModel()` return is the tell: on the legacy bridge, every native call had to be async because of the serialization round-trip. JSI removes that constraint entirely.

### Practical implications for day-to-day work
- **You almost never touch this layer directly** unless you're writing custom native modules. Application code (components, hooks, styling, navigation) looks the same either way.
- **Library compatibility matters.** Most actively maintained libraries (React Navigation, Reanimated 4+, Gesture Handler 3+, FlashList v2, react-native-screens 4+) require the New Architecture and a recent minimum RN version. A library "hasn't been updated since 2023-2024" is the reddest of red flags — check its repo before adopting it.
- **Remote JS debugging via Chrome is gone**; use the New Architecture-native debugging path (React Native DevTools / the Hermes JS Inspector) instead, since Reanimated and other JSI-based libraries are fundamentally incompatible with the old remote-debugging model (it ran your JS in a different engine than the one on-device).
- **Migrating an old app:** never jump multiple versions at once. Go one minor version at a time, run `npx react-native-new-arch-check`-style dependency audits before flipping `newArchEnabled`, and budget real QA time — some libraries claim New Architecture support but have subtle Fabric-specific bugs that only show up under real interaction.

---

## 5. Project Setup

### Starting an Expo project

```bash
# Interactive; scaffolds Expo Router + TypeScript + a tabs layout by default
npx create-expo-app@latest my-app
cd my-app
npx expo start
```

Key files you'll immediately care about:
- **`app.json` / `app.config.ts`** — the single source of truth for app name, bundle identifier/package name, icon, splash screen, permissions, and the list of config plugins. Prefer `app.config.ts` once you need any conditional logic (different bundle IDs per environment, reading env vars, etc.) — it's just executable TypeScript.
- **`app/`** (or `src/app/`) — route files if using Expo Router (see Part 6).
- **`eas.json`** — build/submit/update profiles once you set up EAS (see Part 6).

Adding EAS to an existing project:

```bash
npm install -g eas-cli
eas login
eas init          # links the project to an Expo account, generates a project ID
eas build:configure
```

### Starting a bare React Native CLI project

```bash
npx @react-native-community/cli@latest init MyApp
cd MyApp
npx react-native run-ios      # or run-android
```

This generates and commits real `ios/` and `android/` native project folders immediately — you own them from line one. Native module linking is handled by **autolinking** (reads `package.json` dependencies and wires up native code automatically for most well-behaved packages), but anything unusual may require manual Podfile/Gradle edits.

### Moving between the two later
Because both workflows are just "a React Native app with different tooling around it," you can usually adopt Expo's SDK/EAS tooling into a bare CLI project (`npx install-expo-modules`) without a full rewrite, and you can `npx expo prebuild` an Expo project at any time to inspect or hand-edit the generated native folders. Treat the Expo/bare split as a spectrum of "how much do I want the tooling to manage for me," not a one-way, irreversible fork.

---

## 6. Expo Deep Dive

### 6.1 The SDK

The Expo SDK is a curated, single-versioned collection of native modules (`expo-camera`, `expo-notifications`, `expo-location`, `expo-haptics`, `expo-image`, `expo-sqlite`, `expo-secure-store`, `expo-av`/`expo-audio`/`expo-video`, `expo-file-system`, `expo-sharing`, `expo-in-app-purchases`, and dozens more) that all ship together and are guaranteed compatible with each other and with a specific React Native version. Install with the Expo-aware installer, not raw npm, so versions stay pinned correctly:

```bash
npx expo install expo-camera expo-haptics expo-image
```

Two other pieces of the SDK worth knowing by name:
- **Expo Modules API** — the modern way to write native modules, using a small declarative Swift/Kotlin DSL instead of hand-written Objective-C/Java/JNI bridging. Scaffold one with `npx create-expo-module@latest`; it autolinks automatically and can be published as an ordinary npm package.
- **Expo UI** — a set of genuinely native UI primitives backed by SwiftUI on iOS and Jetpack Compose on Android (pickers, switches, sliders, menus, bottom sheets) for teams that want pixel-perfect platform-native controls instead of a JS-rendered approximation. It's reached stability with drop-in-replacement components (e.g., a `BottomSheet` that mirrors the popular `@gorhom/bottom-sheet` API) for cases where you want the visuals fully native.
- **`"use dom"`** — a directive that lets a React component render as web content (a real DOM) inside your native app via a WebView, useful for incrementally migrating existing web code or reusing complex web-only libraries without a full native rewrite.

### 6.2 Expo Router (file-based routing)

Expo Router turns your file tree into your navigation graph. It's the default for new Expo projects and is generally the right choice unless you have a specific reason to hand-roll React Navigation (see Part 8 for that comparison).

**Core conventions:**

```
app/
  _layout.tsx          # Root layout — providers, font loading, global UI
  index.tsx            # matches "/"
  (auth)/              # a route group — organizes files without affecting the URL
    login.tsx           # matches "/login", not "/auth/login"
    register.tsx
  (tabs)/              # another route group, this one wraps its children in a tab bar
    _layout.tsx          # defines the Tabs navigator for this group
    index.tsx             # matches "/" inside the tab group
    profile.tsx            # matches "/profile"
  post/
    [id].tsx            # dynamic route — matches "/post/123"
    [...slug].tsx        # catch-all — matches "/post/a/b/c"
  settings.web.tsx     # web-only override; settings.native.tsx covers iOS+Android together
  +not-found.tsx        # 404 screen
```

Root layout example (also where you'd load fonts and wrap the Gesture Handler root — see Parts 11 and 13):

```tsx
// app/_layout.tsx
import { Stack } from 'expo-router';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { useFonts, Inter_400Regular, Inter_700Bold } from '@expo-google-fonts/inter';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [fontsLoaded] = useFonts({ Inter_400Regular, Inter_700Bold });

  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync();
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <Stack screenOptions={{ headerShown: false }} />
    </GestureHandlerRootView>
  );
}
```

Navigating and reading params:

```tsx
import { router, useLocalSearchParams, Link } from 'expo-router';

// Imperative navigation
router.push('/post/123');
router.back();

// Declarative navigation
<Link href="/settings">Settings</Link>

// Reading a dynamic segment
function PostScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <Text>Post {id}</Text>;
}
```

**Things worth knowing:**
- Every route is automatically a deep link — no manual linking config needed.
- Typed routes (enable in `app.json` via the `experiments.typedRoutes` flag on older SDKs, stable by default on newer ones) catch broken `router.push('/typoo')` calls at compile time.
- Native platforms get real platform tab bars/gesture-driven transitions; the web build can render an entirely different, unstyled tab UI via `expo-router/ui` for the same route group — this is why you'll sometimes see a `.native.tsx`/`.tsx` split for the same layout file.
- Route protection is declarative: wrap protected group layouts in `<Stack.Protected guard={isLoggedIn}>` rather than imperative redirect logic scattered across screens.
- Since SDK 56, Expo Router no longer re-exports `@react-navigation/*` for use in application code directly — import navigation primitives from `expo-router` itself. If you're jumping more than one SDK version (e.g., skipping from 54 straight to 56), upgrade one version at a time; the router's internals changed enough that version-skipping upgrades are unreliable.
- Basic static site generation (SSG) works out of the box for the web target; full server-side rendering needs custom infrastructure.

### 6.3 EAS: Build, Submit, Update

EAS is the piece that makes "build in the cloud, ship instantly, patch without app-store review" real.

**`eas.json` — build & submit profiles:**

```json
{
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "channel": "preview"
    },
    "production": {
      "autoIncrement": true,
      "channel": "production"
    }
  },
  "submit": {
    "production": {}
  }
}
```

**Everyday commands:**

```bash
eas build --platform all --profile preview      # cloud build, share via a link
eas submit --platform ios --latest              # upload the latest build to App Store Connect / TestFlight
eas update --branch production --message "Fix login button alignment"   # OTA JS/asset update, no store review
```

Mental model for EAS Update: a **channel** (defined per build profile, e.g. `production`) points at a **branch** (a list of updates, like a git branch), and every published update carries a target **runtime version**. An update only reaches devices whose build shares that exact platform + runtime version — this is the safety rail that stops you from OTA-shipping a JS update that assumes native code your already-installed binaries don't have. Any change to native code requires a new binary build (and store re-submission); anything JS/asset-only can go out instantly via EAS Update. App Store and Play Store content policies still apply to OTA updates — they're a deployment mechanism, not a way to bypass platform review of what your app actually does.

**Common pitfalls specific to EAS/Expo Go:**
- Expo Go on the app stores only ever supports the single latest SDK version, and can lag behind due to Apple's review turnaround — if you need to test against an older SDK on a physical iOS device or need any custom native module, use a **development build** instead of Expo Go.
- First-time Play Store / App Store Connect submissions still require one manual upload through the console before API-based `eas submit` calls will work for that app.
- EAS Build precompiles common native dependencies to speed up iOS build times — most projects don't need to think about this, but it's why clean builds have gotten noticeably faster over the last few SDK cycles.

### 6.4 Config plugins & prebuild

```bash
npx expo prebuild        # (re)generates ios/ and android/ from app.config.ts + installed plugins
npx expo prebuild --clean   # wipe and regenerate from scratch — the fix for "native folder got weird"
```

A config plugin is just a function that mutates the generated native project during prebuild — adding a permission string, an entitlement, a Gradle dependency, or an `Info.plist` key:

```ts
// app.config.ts
export default {
  expo: {
    name: 'MyApp',
    plugins: [
      'expo-router',
      ['expo-camera', { cameraPermission: 'Allow $(PRODUCT_NAME) to access your camera.' }],
      ['expo-build-properties', { ios: { deploymentTarget: '15.1' } }],
    ],
  },
};
```

Treat the generated `ios/`/`android/` folders as build output (gitignore them) whenever you can express your native customizations entirely through plugins — that keeps `prebuild --clean` a safe, reliable operation instead of something that destroys hand-edits.

---

## 7. React Native CLI Deep Dive

### 7.1 What you own in bare workflow

```
MyApp/
  ios/            # Xcode project, Podfile, entitlements — yours to edit directly
  android/        # Gradle project, AndroidManifest.xml — yours to edit directly
  index.js         # native entry point (registerComponent)
  App.tsx
```

There's no `prebuild` step because there's nothing to generate — the native folders are the source of truth, committed to version control, and every native change (a new permission, a new SDK, a Podfile tweak) is a direct edit to those files.

### 7.2 Autolinking

When you `npm install` a well-behaved React Native library, **autolinking** (built into the React Native CLI) reads your `package.json`, finds native modules declaring themselves linkable, and wires up the native project (CocoaPods entries, Gradle `settings.gradle`/`build.gradle` entries) automatically — you almost never manually edit `MainApplication`/`AppDelegate` package lists anymore for standard libraries. For iOS you still need to run pod install after adding a dependency with native code:

```bash
npx pod-install   # or: cd ios && pod install && cd ..
```

### 7.3 Writing a native module

Two paths, both leading to a TurboModule under the New Architecture:
- **TurboModules directly** (Objective-C++/C++ for iOS, Java/Kotlin for Android) — full control, more boilerplate, appropriate when you're maintaining a bare CLI app and want zero Expo dependency.
- **Expo Modules API** (Swift/Kotlin DSL) — works in bare CLI projects too (`npx install-expo-modules`), not just managed Expo apps, and is dramatically less boilerplate for the same result. There's rarely a good reason to hand-write a raw TurboModule spec today when the Expo Modules API produces the same TurboModule under the hood with a far friendlier authoring experience.

### 7.4 When bare is genuinely the right call
Revisit Part 3's decision table, but the sharpest signal is: **if you're integrating React Native into an existing large native codebase** (a "brownfield" app where RN is one screen or one feature inside an app that's 90% native Swift/Kotlin), bare CLI's direct native ownership is the natural fit — there's no "managed" project to speak of, because the native project already exists and predates the RN integration.

---

## 8. Navigation

### 8.1 Expo Router vs React Navigation — pick one mental model

Expo Router is **built on top of** React Navigation's primitives (stack/tab/drawer navigators, native-screens optimizations, gesture handling) — it isn't a competing engine, it's a file-based configuration layer over the same battle-tested navigation runtime. The practical decision:

| | Expo Router (file-based) | React Navigation (code-configured) |
|---|---|---|
| Mental model | Files ARE routes; folder structure = navigation tree | You explicitly call `createStackNavigator()` etc. and declare screens in code |
| Deep linking | Automatic, zero config | Manual linking config required |
| Type safety | Generated from the file tree | Hand-maintained generic types per navigator, or the newer static-config API |
| Web support | First-class, with SSG | Requires additional setup |
| Best for | New apps, especially anything Expo, anything wanting web+native from one codebase | Non-Expo/bare projects, highly dynamic or programmatically-generated navigation graphs, teams with a large existing RN-Navigation codebase |
| Downsides | Tighter coupling to the Expo toolchain and Metro; very dynamic route generation feels awkward when everything wants to be a file | More boilerplate; deep linking and TypeScript config must be hand-maintained (though React Navigation 7's static API narrows this gap) |

Rule of thumb for 2026: **default to Expo Router for new Expo projects.** Use React Navigation directly for bare CLI projects, or for Expo projects with unusually dynamic/data-driven navigation graphs that fight the file-based model.

### 8.2 React Navigation basics (v7)

```tsx
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

function HomeStack() {
  return (
    <Stack.Navigator>
      <Stack.Screen name="Feed" component={FeedScreen} />
      <Stack.Screen name="Details" component={DetailsScreen} />
    </Stack.Navigator>
  );
}

export default function App() {
  return (
    <NavigationContainer>
      <Tab.Navigator screenOptions={{ headerShown: false }}>
        <Tab.Screen name="Home" component={HomeStack} />
        <Tab.Screen name="Profile" component={ProfileScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
```

`@react-navigation/native-stack` uses real native navigation primitives (`react-native-screens`) for platform-correct transitions and gestures — prefer it over the older JS-only `@react-navigation/stack` unless you need a transition the native stack can't express.

### 8.3 What's coming: React Navigation 8

Currently in alpha, requiring React 19 (so RN 0.83+ / Expo SDK 55+). Headline changes: **native bottom tabs by default** (via `react-native-bottom-tabs`, including iOS 26's "liquid glass" tab bar look), deep linking enabled by default with automatic path generation, Standard Schema validation support (Zod/Valibot) for linking configs, and an `inactiveBehavior` option that uses React 19's `React.Activity` to pause off-screen screens' effects without fully unmounting them (cutting unnecessary re-renders while preserving state). Not something to adopt in production yet, but worth knowing the direction of travel if you're making long-lived architecture decisions today.

### 8.4 Common navigation patterns

- **Auth flow gating:** conditionally render an `(auth)` group vs an `(app)` group at the root layout based on auth state, rather than manually redirecting from every protected screen. Expo Router's `<Stack.Protected guard={...}>` formalizes this.
- **Modals:** in Expo Router, a file inside a group with `presentation: 'modal'` set in the layout's `screenOptions`; in React Navigation, a nested stack navigator with `screenOptions={{ presentation: 'modal' }}`.
- **Tab bar badges / scroll-to-top on re-tap:** native tab bars (both React Navigation's native-stack-backed tabs and Expo Router's platform tabs) provide this for free — it's one of the reasons to prefer native tab implementations over hand-rolled JS tab bars.
- **Nested navigators & params:** avoid the old `navigation.navigate(Screen)` shortcut into a nested navigator when you can — it's implicit, isn't type-safe, and only works if the target navigator happens to already be mounted. Be explicit about which navigator you're targeting.

---

## 9. Styling Systems

React Native has no CSS engine — every style is ultimately a JavaScript object handed to a `style` prop. Everything below is a different strategy for authoring those objects ergonomically.

### 9.1 `StyleSheet` (the foundation, always available)

```tsx
import { StyleSheet, View, Text } from 'react-native';

const styles = StyleSheet.create({
  card: { padding: 16, borderRadius: 12, backgroundColor: '#fff' },
  title: { fontSize: 18, fontWeight: '600' },
});

function Card() {
  return (
    <View style={styles.card}>
      <Text style={styles.title}>Hello</Text>
    </View>
  );
}
```

`StyleSheet.create` isn't just a naming convention — it lets the runtime hand style objects to native by reference/ID instead of serializing them on every render, which matters for list-heavy screens. It's the right default for small apps or design-system-internal component code, but it doesn't give you tokens, theming, dark mode switching, or responsive variants for free — you build those yourself or reach for one of the systems below.

### 9.2 NativeWind (Tailwind CSS for React Native)

The utility-class workflow, compiled to native `StyleSheet` objects at build time (not parsed at runtime), so there's effectively no runtime styling cost beyond ordinary RN styles.

```bash
npx expo install nativewind react-native-reanimated react-native-safe-area-context
npm install -D tailwindcss@^3.4.17 prettier-plugin-tailwindcss babel-preset-expo
npx tailwindcss init
```

```js
// tailwind.config.js
module.exports = {
  content: ['./app/**/*.{js,jsx,ts,tsx}', './components/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: { extend: { colors: { primary: '#2563eb' } } },
};
```

```tsx
import { View, Text } from 'react-native';

function Card() {
  return (
    <View className="rounded-xl bg-white p-4 shadow-sm dark:bg-neutral-900">
      <Text className="text-lg font-semibold text-neutral-900 dark:text-white">Hello</Text>
    </View>
  );
}
```

Notes:
- Current stable NativeWind (4.x) targets **Tailwind CSS v3** semantics — don't install `tailwindcss@latest` blindly, pin to the 3.4 line or you'll get a "NativeWind only supports Tailwind CSS v3" error. NativeWind v5 (targeting Tailwind v4's CSS-first config) is in preview and not yet the default recommendation.
- Supports dark mode (`dark:` variant via a `useColorScheme` hook), group/parent-state variants, CSS variables for theme tokens, and — via the Reanimated integration under the hood — basic Tailwind animation/transition utility classes.
- Not every web CSS concept has a native equivalent (no CSS Grid on native, shadows render differently than on web) — NativeWind applies whichever subset of a class actually maps to something RN's style engine supports and silently no-ops the rest, so test on-device rather than assuming visual parity with a web Tailwind reference.

### 9.3 Tamagui (compiler-based universal styling + UI kit)

Tamagui is a styling system **and** an optional component kit, built around a compile-time optimizer: it flattens styled-component trees, extracts static styles, and evaluates `useMedia`/`useTheme` hooks into plain CSS variables/media queries on web — while emitting plain `View`s with hoisted style objects on native. The pitch is genuine universal (web + native) performance parity, at the cost of a real setup/config learning curve.

```tsx
import { styled, Stack, Text } from '@tamagui/core';

const Card = styled(Stack, {
  backgroundColor: '$background',
  borderRadius: '$4',
  padding: '$4',
  variants: {
    elevated: { true: { shadowRadius: 8, shadowOpacity: 0.1 } },
  } as const,
});

function ProfileCard() {
  return (
    <Card elevated>
      <Text fontSize="$6" fontWeight="600">Hello</Text>
    </Card>
  );
}
```

Choose Tamagui when the app genuinely targets web + native from one codebase and long-term performance/bundle size matters enough to justify the compiler setup investment. Skip it for a native-only app where the setup cost isn't buying you the thing it's best at (universal, compiler-flattened cross-platform output).

### 9.4 Styling decision table

| Approach | Best for | Trade-off |
|---|---|---|
| `StyleSheet` | Small apps, design-system-internal code, anywhere you want zero dependencies | You build theming/tokens/dark-mode yourself |
| NativeWind | Teams already fluent in Tailwind, fastest ramp-up, native-only or native-first apps | Pinned to Tailwind v3 semantics on the stable line; some web CSS concepts don't map 1:1 |
| Tamagui | Universal (web + native) apps, teams that want compiler-level performance and a built-in token/theme system | Real setup and config learning curve; smaller community than NativeWind |
| `twrnc` (Tailwind React Native Classnames) | Want Tailwind syntax with zero build-step ceremony | Runtime class parsing (not compiled) — fine at small-to-medium scale, can add up with 100+ dynamically-styled components per screen |
| Styled-components / Emotion for RN | Teams migrating from a web codebase already using CSS-in-JS | Runtime style computation; less RN-specific tooling investment than the above in 2026 |

---

## 10. UI Component Libraries

A UI/component library saves you from re-implementing buttons, inputs, modals, and lists from scratch — and, done well, gives you accessibility and platform-appropriate behavior for free. None of these are mutually exclusive with the styling systems above (Tamagui is both a styling system and a component kit; the others are typically paired with `StyleSheet` or NativeWind underneath).

### 10.1 The landscape

| Library | Design language | Styling model | Best for |
|---|---|---|---|
| **React Native Paper** | Material Design 3 ("Material You") | Theme object + `StyleSheet` | Android-first or cross-platform apps that want to closely follow Material 3 out of the box; strong accessibility defaults (48×48dp touch targets, screen-reader labels) |
| **gluestack-ui v3** | Unstyled/headless, your design | Copy-paste components + NativeWind/Tailwind | Teams that want full ownership of component source (shadcn-style copy-paste model), New-Architecture-first, modular so unused components add zero bundle weight |
| **Tamagui** | Your design, via tokens | Compiler-optimized styled components | Universal web+native apps prioritizing performance and a single design-token source of truth |
| **UI Kitten** | Eva Design System | Theme object (`ApplicationProvider`) | Apps wanting strong, consistent runtime-switchable theming (light/dark, custom brand themes) with zero JS re-styling cost per theme swap; good multi-language/RTL support |
| **React Native Elements (RNEUI)** | Loosely Material/iOS-ish, easily overridden | Theme object | Long-established, straightforward API; slower-moving project, so audit New Architecture compatibility for any component you lean on heavily |
| **Shopify Restyle** | Fully custom (you define everything) | Type-safe theme + style props | Teams that want a lightweight, fully bespoke design-system foundation rather than pre-designed components |

### 10.2 React Native Paper (Material Design 3)

```tsx
import { PaperProvider, MD3LightTheme, Button, Card, Text } from 'react-native-paper';

const theme = { ...MD3LightTheme, colors: { ...MD3LightTheme.colors, primary: '#2563eb' } };

export default function App() {
  return (
    <PaperProvider theme={theme}>
      <Card style={{ margin: 16 }}>
        <Card.Content>
          <Text variant="titleLarge">Welcome</Text>
        </Card.Content>
        <Card.Actions>
          <Button mode="contained" onPress={() => {}}>Continue</Button>
        </Card.Actions>
      </Card>
    </PaperProvider>
  );
}
```

Paper's `Text` component takes a `variant` prop (`displayLarge`, `headlineMedium`, `titleLarge`, `bodyMedium`, `labelSmall`, and so on) mapping directly onto Material 3's fifteen-variant type scale — lean on it instead of hand-tuning `fontSize`/`fontWeight` per screen, since it's how you inherit Material 3's typographic rhythm for free. `adaptNavigationTheme()` bridges a Paper theme into React Navigation so navigator chrome (headers, tab bars) matches your Paper color scheme automatically.

### 10.3 gluestack-ui (the NativeBase successor)

```bash
npx gluestack-ui@latest init
npx gluestack-ui@latest add button card
```

```tsx
import { Button, ButtonText, Card, Heading } from '@/components/ui';

function Welcome() {
  return (
    <Card className="p-4 rounded-xl">
      <Heading size="lg">Welcome</Heading>
      <Button className="mt-4" onPress={() => {}}>
        <ButtonText>Continue</ButtonText>
      </Button>
    </Card>
  );
}
```

NativeBase (gluestack's predecessor) is effectively sunset — new projects should start on gluestack-ui v3 directly rather than NativeBase, even though a `@gluestack-ui/themed-native-base` compatibility shim exists for migrating legacy codebases. gluestack-ui's defining trait is the **copy-paste + CLI ownership model** (similar to shadcn/ui on the web): components land in your own source tree via the CLI rather than living as an opaque `node_modules` dependency, so you always have full read/write access to the actual component code, and unused components cost zero bundle size.

### 10.4 UI Kitten (Eva Design System)

```tsx
import * as eva from '@eva-design/eva';
import { ApplicationProvider, Layout, Text, Button } from '@ui-kitten/components';

export default function App() {
  return (
    <ApplicationProvider {...eva} theme={eva.light}>
      <Layout style={{ flex: 1, padding: 16 }}>
        <Text category="h1">Welcome</Text>
        <Button onPress={() => {}}>CONTINUE</Button>
      </Layout>
    </ApplicationProvider>
  );
}
```

Swap `theme={eva.light}` for `theme={eva.dark}` (typically driven by a `useColorScheme` hook) and the entire component tree re-themes at runtime with no reload — that instant, whole-app theme switch, plus first-class RTL support across all components, is UI Kitten's strongest differentiator. It ships 480+ matching Eva Icons as a companion package.

### 10.5 Choosing between them

- **Want the fastest path to a polished, Android-idiomatic Material 3 app?** React Native Paper.
- **Want full source ownership and a Tailwind-native workflow, à la shadcn?** gluestack-ui.
- **Targeting web + native from one codebase and performance is a first-class requirement?** Tamagui.
- **Need strong runtime theme-switching and RTL out of the box for an enterprise/multi-brand app?** UI Kitten.
- **Want to build a fully bespoke design system with type-safe style props and no prescriptive visual opinion at all?** Shopify Restyle, or hand-rolled `StyleSheet` + a token file.

Whichever you pick, verify New Architecture / Fabric compatibility before committing — a library that "hasn't shipped a release since before RN 0.76" is a real risk in 2026, since Fabric-specific rendering bugs in unmaintained libraries are one of the most common sources of hard-to-diagnose visual glitches.

---

## 11. Animation & Gesture Systems

Motion is one of the highest-leverage places to invest polish — it's also one of the easiest places to tank performance if you animate on the JS thread instead of the UI thread. Every library below exists to keep animation work off the (often busy) JS thread.

### 11.1 The mental model: threads, not libraries

Before picking a tool, understand *why* they exist. React Native's JS thread runs your application logic — state updates, network calls, rendering decisions — and on a loaded device it's frequently busy. Any animation driven by that thread will drop frames the moment it's busy with something else. **Reanimated** and **Gesture Handler** solve this by moving both gesture recognition and animation computation onto the UI thread (the native thread the OS itself uses for rendering) via **worklets** — small JS functions that get serialized and executed on a different JavaScript runtime. This is why a Reanimated-driven animation stays buttery even while a screen is mid-network-request or processing a heavy background computation, and why the old `PanResponder` API (JS-thread only) increasingly shows its age for anything gesture-heavy.

### 11.2 Reanimated (the foundation)

```bash
npx expo install react-native-reanimated react-native-worklets
```

```tsx
import Animated, { useSharedValue, useAnimatedStyle, withTiming, withSpring, Easing } from 'react-native-reanimated';
import { Pressable } from 'react-native';

function LikeButton() {
  const scale = useSharedValue(1);

  const style = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  return (
    <Pressable
      onPressIn={() => { scale.value = withTiming(0.9, { duration: 100 }); }}
      onPressOut={() => { scale.value = withSpring(1); }}
    >
      <Animated.View style={style}>
        <HeartIcon />
      </Animated.View>
    </Pressable>
  );
}
```

Reanimated 4 split its worklet runtime out into a separate `react-native-worklets` package — always install both. It's **New Architecture only**; apps still on the legacy architecture must stay on Reanimated 3.x. The historical `runOnJS`/`runOnUI`/`runOnRuntime` APIs were renamed in v4 to `scheduleOnRN`/`scheduleOnUI`/`scheduleOnRuntime` (now imported from `react-native-worklets` rather than `react-native-reanimated`) with a slightly different calling convention — check the official migration guide before upgrading an app that leans on the old names. Reanimated 4 also added CSS-style animations/transitions (running on Core Animation on iOS) as an alternative to the imperative shared-value API for simple cases.

### 11.3 Gesture Handler

```bash
npx expo install react-native-gesture-handler
```

```tsx
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { useSharedValue, useAnimatedStyle } from 'react-native-reanimated';

function DraggableCard() {
  const translateX = useSharedValue(0);
  const translateY = useSharedValue(0);

  const pan = Gesture.Pan()
    .onUpdate((e) => {
      translateX.value = e.translationX;
      translateY.value = e.translationY;
    })
    .onEnd(() => {
      translateX.value = withSpring(0);
      translateY.value = withSpring(0);
    });

  const style = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }, { translateY: translateY.value }],
  }));

  return (
    <GestureDetector gesture={pan}>
      <Animated.View style={[styles.card, style]} />
    </GestureDetector>
  );
}
```

Wrap your app root once in `<GestureHandlerRootView style={{ flex: 1 }}>` (in Expo Router, that's `app/_layout.tsx`) — forgetting this is the single most common "my gestures silently do nothing" bug report, especially inside Modals, which need their own nested `GestureHandlerRootView`. Gesture Handler 3.x requires a hook-based API and RN 0.82+; it's New Architecture only.

**When a parent `ScrollView` is "stealing" your pan gesture:** add `.activeOffsetX([-10, 10])` (or the Y-axis equivalent) to your `Gesture.Pan()` so it waits for a minimum amount of directional movement before activating, letting orthogonal scroll gestures pass through untouched.

### 11.4 Choosing an animation tool for the job

| Need | Reach for |
|---|---|
| Simple screen-transition/UI-state animations (fade in, toggle expand, skeleton loaders) | **Moti** — a Framer-Motion-style declarative wrapper over Reanimated (`from`/`animate`/`exit` props), roughly 10x less code than raw shared values for common cases |
| Gesture-driven interactions (swipe-to-delete, drag-to-reorder, pinch-to-zoom, draggable cards) | **Reanimated + Gesture Handler** directly, for full control over the interaction |
| Designer-authored motion from After Effects | **Lottie** (`lottie-react-native`) for the standard renderer, or **Skottie** (`react-native-skottie`, Lottie-on-Skia) when you need the ~60% frame-rate improvement Skia's native player gives over the JS-based Lottie renderer on low-end Android |
| Custom 2D graphics, charts, shaders, blur/glass effects | **React Native Skia** (`@shopify/react-native-skia`) — a GPU-accelerated `<Canvas>` API, conceptually similar to `<canvas>` on the web but backed by Google's Skia renderer via JSI |
| Simple, pre-built micro-animations with near-zero setup | **React Native Animatable** — 60+ ready-made animations (`fadeIn`, `bounce`, `shake`, `pulse`) for small, purely decorative touches |
| A production-grade draggable sheet (filters, "now playing," share sheets) | **`@gorhom/bottom-sheet`** — built on Reanimated + Gesture Handler, supports snap points, dynamic sizing, and scroll-aware content (`BottomSheetFlatList`/`BottomSheetScrollView`); or Expo's own `BottomSheet` (from `@expo/ui`) when you want a fully native SwiftUI/Jetpack Compose sheet instead of a JS-rendered one |
| Interactive data visualization with gesture-driven scrubbing | Reanimated + Gesture Handler + Skia together — shared values flow into a Skia canvas via `useDerivedValue()`, so a single gesture can drive both a native view transform and canvas-rendered paths at 60fps on the UI thread (this is how libraries like Victory Native XL work) |

A production pattern worth internalizing: **use Moti for standard UI transitions, Reanimated directly for gesture-driven interactions, and Skia for custom graphics that live alongside those interactions** — you don't have to pick just one.

### 11.5 Respect motion sensitivity
Both iOS and Android expose a system-level "Reduce Motion" accessibility setting. Well-built apps check it (`AccessibilityInfo.isReduceMotionEnabled()` in RN) and swap parallax/bounce/shake-heavy animations for simple cross-fades when it's on — this isn't optional polish, it's an accessibility requirement for users with vestibular disorders or motion sensitivity.

---

## 12. Icons

### 12.1 The 2026 shift: `@expo/vector-icons` is being phased out

This is a real, current change worth getting right, because a lot of existing tutorials will point you at the old pattern. **`@expo/vector-icons`** was historically the default icon story in Expo apps — a compatibility wrapper that made `react-native-vector-icons` work smoothly with Expo's asset system. It's now deprecated in favor of using the underlying icon packages directly:

```bash
npx expo install @react-native-vector-icons/ionicons @react-native-vector-icons/material-design-icons
```

```tsx
import Ionicons from '@react-native-vector-icons/ionicons';

<Ionicons name="heart" size={28} color="#e11d48" />
```

Why the change: the newer, scoped `@react-native-vector-icons/*` packages integrate directly with `expo-font` and work identically across Expo Go, development builds, and production — the old `@expo/vector-icons` wrapper existed to paper over a compatibility gap that no longer exists, and maintaining it duplicated effort Expo would rather spend elsewhere. If you're migrating an existing app, Expo ships a codemod (`npx @react-native-vector-icons/codemod`) that handles most of the mechanical import rewriting, followed by `npx expo doctor` to confirm no old packages are lingering. For **new projects, start directly with the scoped `@react-native-vector-icons/*` packages** rather than `@expo/vector-icons`.

Either way, the underlying icon sets are the same well-known families: Ionicons, Material Design Icons, Font Awesome (5/6), Octicons, Feather, Fontisto — plus **Lucide**, which has become the most popular modern choice for a clean, consistent, MIT-licensed line-icon set (also available standalone as `lucide-react-native`). **Phosphor Icons** (`phosphor-react-native`) is a similarly popular alternative with more weight variants (thin/light/regular/bold/fill/duotone).

### 12.2 Custom/brand icons

For a bespoke icon set (brand-specific glyphs, not a stock icon family), render SVGs directly with `react-native-svg` rather than converting everything to an icon font — it's more maintainable, composes naturally with Skia/Reanimated for animated icons, and avoids the font-glyph-mapping indirection entirely:

```tsx
import Svg, { Path } from 'react-native-svg';

function CustomIcon({ size = 24, color = '#000' }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 2L2 7l10 5 10-5-10-5z" stroke={color} strokeWidth={2} />
    </Svg>
  );
}
```

### 12.3 Practical guidance
- Pick **one** icon family per app for visual consistency — mixing Ionicons with Feather with Material icons in the same screen is one of the fastest ways to make an app look unpolished, even when every individual icon is well-drawn.
- Size icons to match your type scale (icons next to `bodyMedium` text should generally be close to that text's line-height, not an arbitrary fixed size), and always give icon-only buttons an `accessibilityLabel` (see Part 20) since a screen reader has no visual glyph to describe.

---

## 13. Fonts & Typography

### 13.1 Loading fonts

Two mechanisms, and they're not interchangeable:

**The `expo-font` config plugin (recommended)** — embeds the font file at build time as a native resource. Fonts are available the instant the app starts, with zero loading-state code, but it requires a development build (doesn't work in Expo Go) since it changes native project files:

```json
// app.json
{
  "expo": {
    "plugins": [
      ["expo-font", { "fonts": ["./assets/fonts/Inter-Bold.ttf"] }]
    ]
  }
}
```

**The `useFonts` runtime hook** — loads fonts asynchronously after the JS bundle starts running; works everywhere including Expo Go and the web, at the cost of a brief loading state you must handle explicitly (typically by holding the splash screen open):

```tsx
import { useFonts, Inter_400Regular, Inter_700Bold } from '@expo-google-fonts/inter';
import * as SplashScreen from 'expo-splash-screen';

SplashScreen.preventAutoHideAsync();

function App() {
  const [fontsLoaded] = useFonts({ Inter_400Regular, Inter_700Bold });
  if (!fontsLoaded) return null;   // keep splash screen visible until this resolves
  return <MainApp />;
}
```

`@expo-google-fonts/*` packages wrap the entire Google Fonts catalog (1000+ families) as ready-to-import font weights — `npx expo install @expo-google-fonts/<family>` gets you every named weight/style export for that family. Reference fonts by exact family name, and remember iOS and Android resolve font-family strings differently — Android typically wants the font *file name* (e.g. `Inter_900Black`), iOS wants the font's internal PostScript name (e.g. `Inter-Black`), so cross-platform font styles are frequently written with `Platform.select`.

### 13.2 Variable fonts — know the caveat
Variable fonts (a single file encoding a continuous range of weights/widths/optical sizes) are appealing for expressive, animatable typography, but **platform support is inconsistent across iOS/Android/web** in React Native specifically. For anything that needs to render identically everywhere, prefer static font files per weight over relying on a variable font's axes at runtime; if you do need variable-font effects, extract the specific axis configuration you actually use into a dedicated static file with a tool like `fontTools`, rather than shipping the full variable font and hoping every platform interprets the axis the same way.

### 13.3 Building an actual type scale

Don't reach for ad-hoc `fontSize: 16` scattered through the codebase — define a scale once and reuse it, the same way Material 3 defines Display/Headline/Title/Body/Label roles at small/medium/large sizes. A minimal, practical scale for a mobile app:

```ts
export const typography = {
  displayLarge: { fontSize: 36, lineHeight: 44, fontWeight: '700' },
  headline:     { fontSize: 24, lineHeight: 32, fontWeight: '700' },
  title:        { fontSize: 18, lineHeight: 24, fontWeight: '600' },
  body:         { fontSize: 16, lineHeight: 24, fontWeight: '400' },
  bodySmall:    { fontSize: 14, lineHeight: 20, fontWeight: '400' },
  caption:      { fontSize: 12, lineHeight: 16, fontWeight: '500' },
} as const;
```

A few non-negotiables regardless of which scale you land on:
- **Support Dynamic Type / font scaling.** Don't disable `allowFontScaling` reflexively to "protect" your layout — that actively harms users who've increased their system text size for accessibility reasons. Design layouts that can reflow (wrap, scroll, or truncate gracefully) rather than fighting the OS's text-scaling preference. If a specific label truly cannot scale (e.g. a fixed-size icon badge), disable scaling narrowly on that element and document why, rather than globally.
- **Pair a display face with a body face deliberately** if you're going beyond system fonts — the same two families you'd reach for on any other project reads as generic; a considered pairing (a characterful display face used sparingly for headlines, a highly legible body face for everything else) is part of what makes an app's visual identity distinctive rather than templated.
- **Line height matters more than font size** for perceived polish — tight, uneven line-heights are one of the fastest tells that a UI wasn't designed carefully.

---

## 14. Mobile UI/UX Design Principles

This is the part that separates "an app that technically works" from "an app that feels like it belongs on the device it's running on." Treat platform conventions as defaults to follow deliberately, not defaults to blindly inherit — but know them well enough that any deviation is a considered choice, not an accident.

### 14.1 Material Design 3 ("Material You" / "M3 Expressive") — Android's language

Material 3 is Google's current design system, and its 2025–2026 evolution ("M3 Expressive") pushed hard toward emotionally engaging, motion-rich interfaces backed by real usability research (not just a visual refresh). Core pieces to design with intentionally:

- **Dynamic color** — the entire app color scheme can algorithmically derive from the user's wallpaper or in-app content, giving personalization without losing brand identity (your brand's key colors still anchor the derived palette).
- **Color roles, not raw hex values** — M3 defines semantic roles (`primary`, `onPrimary`, `primaryContainer`, `onPrimaryContainer`, `secondary`, `tertiary`, `surface`, `surfaceVariant`, and their dark-mode-adapted counterparts) rather than fixed colors. Design and code against the *role*, and light/dark theming and accessibility contrast come along for free.
- **Type scale** — five roles (Display, Headline, Title, Body, Label) each in small/medium/large, i.e. fifteen named styles total. Use the role names, not raw point sizes, when communicating a design.
- **Shape system** — a scale from extra-small to extra-large corner roundedness, plus (in M3 Expressive) an expanded library of ~35 decorative shapes with morph animations between them, used for buttons, containers, and loading indicators.
- **Motion** — M3 Expressive introduced a physics-based motion system (spring-driven rather than fixed-duration easing curves) so interactions feel "alive" — e.g., dismissing one item in a list causes neighboring items to subtly, physically respond, rather than snapping instantly into their new position.
- **Accessibility is load-bearing, not bolted on** — M3 is designed to support text scaling up to 200%, algorithmically-guaranteed contrast ratios between text and background, and full compatibility with screen readers/keyboard/switch-access navigation as a baseline requirement of the system, not an afterthought layer.

Practical usability guidance straight from Material's own research: **don't stack multiple "expressive" tactics (bold color + heavy motion + decorative shape + loud typography) simultaneously** — pick the ones that serve the specific screen's goal, keep the rest quiet, and always validate any bold direction against real accessibility contrast requirements before shipping it.

### 14.2 Apple Human Interface Guidelines / "Liquid Glass" — iOS's language

Apple's HIG is built on three enduring principles — **Clarity, Deference, and Depth** — and iOS 26 (2025's WWDC redesign, the biggest visual overhaul since iOS 7's flat-design shift in 2013) expressed those principles through a new material called **Liquid Glass**: a translucent, light-refracting surface that floats above content rather than sitting flush with it.

Concrete implications for a mobile UI built to feel native on iOS:
- **Liquid Glass is reserved for the navigation/control layer** — nav bars, tab bars, toolbars, floating buttons — not for content itself. Lists and body content still render as plain, opaque surfaces; the glass material communicates "this is a control that floats above your content," not "this is decorative."
- **Controls float and give way to content.** The interface increasingly hides, simplifies, or merges related actions dynamically based on context, rather than always showing every control at fixed screen positions — hierarchy is now dynamic, not static.
- **The tab bar is inset**, appearing as a horizontal glass capsule rather than a bar flush with the screen edges, with content fading progressively as it scrolls beneath it. Prefer 2–5 tabs; when a tab's content stack is revisited, it should resume where the user left it, not reset to that tab's root.
- **SF Symbols + SF Pro are one system** — icon weight and type weight are designed to match at every scale, which is why a bespoke icon set dropped into an otherwise-native iOS UI often looks subtly "off" even when individually well-drawn; if pixel-perfect native alignment matters, consider SF Symbols for iOS-specific chrome.
- **Dynamic Type is a first-class citizen** — named text styles (`Body` at 17pt, `Large Title` at 34pt, etc.) rescale together as the user adjusts their system text size; design and build against the named styles, not fixed point values, the same way you'd use Material's type roles on Android.
- **44×44pt is the enduring minimum tap target** — this predates Liquid Glass by over a decade and remains the floor for any interactive element, glass-styled or not.
- **Accessibility risk of transparency:** translucent surfaces over busy or high-contrast backgrounds can genuinely hurt legibility and visual hierarchy for some users — maintain at least a 4.5:1 text contrast ratio regardless of what's visible through the glass behind it, and don't rely on transparency alone to signal a control's boundaries.

### 14.3 Platform-adaptive design — the practical synthesis

You don't have to build two completely different apps, but a UI that feels genuinely "at home" on both platforms usually differentiates a handful of things rather than reskinning everything:
- **Navigation chrome** — native tab bars/headers per platform (both React Navigation's native-stack and Expo Router's platform tabs give you this without extra work) rather than a single custom-drawn bar forced onto both.
- **Back navigation** — Android's hardware/gesture back button vs. iOS's edge-swipe-to-go-back and in-header back button; don't assume one input method covers both.
- **Modal presentation** — iOS's native card-style modal sheet vs. Android's fullscreen-dialog conventions.
- **Elevation vs. blur** — Android traditionally communicates layering through shadow/elevation; iOS increasingly communicates it through blur/translucency (Liquid Glass being the latest expression of that). Leaning on your component library's platform-adaptive elevation/shadow handling (Paper, Tamagui, and gluestack-ui all do this) is usually better than hand-rolling one shadow style for both platforms.

### 14.4 Touch targets, spacing, and thumb zones

- **Minimum tap target: 44×44pt on iOS, 48×48dp on Android** — treat these as hard floors, not suggestions, even when the visual icon inside is smaller; pad the touchable area, don't shrink the target to match a small glyph.
- **Design for the thumb, not the eye.** On modern large-screen phones, the top of the screen is the hardest area to reach one-handed, while the bottom third is the easiest. Primary actions (the thing you most want a user to do on this screen) belong within comfortable one-handed thumb reach; destructive or rarely-used actions can live further away, which also reduces accidental taps.
- **8pt/8dp spacing grid** — not an official mandate on either platform, but a near-universal convention (spacing values as multiples of 4 or 8) that keeps layouts visually rhythmic and makes cross-platform spacing translation trivial.
- **Don't gate an entire flow behind a gesture with no visible alternative.** Swipe-to-delete, swipe-to-archive, and similar patterns are excellent accelerators for users who've learned them, but they must have a discoverable, tappable fallback (a visible button, a long-press menu) for users who haven't, use assistive technology, or have a motor impairment that makes precise swipes difficult.

### 14.5 Motion design principles

- **Motion should communicate, not decorate.** Every animation should answer one of: *where did this come from, where is it going, what changed, or did my action register?* An animation that doesn't answer one of those questions is probably just noise — and excess uncommunicative motion is one of the more reliable tells that a UI is AI-generated or template-driven rather than deliberately designed.
- **Prefer spring-based, physical motion over fixed-duration easing curves** for anything gesture-adjacent (a card returning to rest after a drag, a sheet settling at a snap point) — it reads as responsive to the user's actual input rather than playing a canned animation regardless of gesture velocity. `withSpring` in Reanimated is built for exactly this.
- **Keep transitions fast.** 150–300ms is the practical range for most UI transitions; anything longer starts to feel like the app is making the user wait rather than helping them. Reserve longer, more elaborate motion for rare, high-value moments (a first-run welcome sequence, a milestone celebration) rather than routine navigation.
- **Always respect "Reduce Motion."** See Part 11.5 — this is a repeated point because it's frequently skipped and it's a genuine accessibility requirement, not a nice-to-have.

### 14.6 Dark mode is a first-class design surface, not an inverted afterthought

By 2026, dark mode is a baseline expectation, not a differentiator — and the apps that do it well design dark mode as its own considered palette rather than mechanically inverting the light theme. Practical guidance:
- Design semantic color roles (`background`, `surface`, `onSurface`, `primary`, and so on — the same role-based thinking Material 3 formalizes) so light/dark theming is a matter of swapping role values, not hunting down every hardcoded hex string in the codebase.
- True black (`#000000`) backgrounds save meaningfully more battery on OLED screens than dark grey, but pure black can also crush contrast and make elevation/layering harder to perceive — a very dark grey (not pure black) is usually the better default for content-dense screens, reserving true black for battery-sensitive, low-detail surfaces (media players, AMOLED-optimized always-on views).
- Don't just darken — recheck contrast ratios independently in dark mode; colors that pass contrast checks on a light background frequently fail on a dark one.

### 14.7 Onboarding, micro-interactions, empty states, and haptics

These four patterns show up in essentially every research-backed "what actually moves retention" list for 2026, and they're worth treating as required scope on any real product, not polish to bolt on later if time allows:

- **Progressive, adaptive onboarding** beats a static multi-screen tutorial: show the app's core value with minimal setup friction, then teach secondary features contextually, in the moment they become relevant, rather than front-loading everything before the user has done anything. Always provide a visible skip option.
- **Micro-interactions** — small, purposeful animated feedback (a button's subtle press state, a heart icon that fills with a satisfying bounce, a pull-to-refresh spinner) — measurably improve perceived performance and engagement precisely because they confirm to the user that their input registered. The failure mode is micro-interactions that are purely decorative and provide no actual feedback signal; every one should answer "did my tap work."
- **Design your empty states on purpose.** A screen with no data yet (no messages, no saved items, no search results) is an opportunity to direct the user toward their next action, not a dead end — pair a brief explanation with a clear, single call to action rather than leaving a blank void or a generic "No results" string.
- **Haptics confirm gestures.** Pair meaningful gesture-driven interactions with haptic feedback — iOS exposes light/medium/heavy impact intensities plus semantic success/warning/error notification types (`expo-haptics` wraps both platforms' native APIs); Android exposes comparable haptic feedback constants. A gesture with no haptic response reads as "did that work?"; the same gesture with haptic confirmation reads as solid and intentional. Don't overuse it — haptics on every single tap becomes noise instead of signal.
- **Frictionless, passwordless authentication** (biometrics/passkeys as the primary path, with a clearly available fallback like a magic link or SMS code for users without biometrics configured) measurably improves signup/login completion and is fast becoming a baseline expectation rather than a premium touch. Design the biometric-fallback path with just as much care as the primary path — it shouldn't feel like a penalty for having an older device.

### 14.8 A working checklist
When reviewing any screen you've just built, run it against this list:
1. Does every interactive element meet the 44pt/48dp minimum touch target?
2. Does the primary action sit in a comfortable one-handed thumb zone?
3. Is there a visible fallback for every gesture-only interaction?
4. Does the layout survive 200% system text scaling without clipping or overlapping?
5. Have you checked contrast ratios in **both** light and dark mode, not just one?
6. Does every animation answer "where from / where to / what changed / did it register" — or is it decorative noise?
7. Is "Reduce Motion" respected?
8. Does the empty state direct the user toward a next action instead of just saying "nothing here"?
9. Would a screen-reader user understand every icon-only control (see Part 20)?

---

## 15. Design Systems & Design Tokens

### 15.1 What a design token is, and why it's worth the setup

A **design token** is a named, platform-agnostic value for a design decision — a color, a spacing unit, a font size, a corner radius — stored once and referenced everywhere, instead of the same hex code or pixel value being hand-copied into a dozen different components. The **W3C Design Tokens Community Group (DTCG) format** is the emerging standard shape for these:

```json
{
  "color": {
    "brand": { "500": { "$value": "#2563eb", "$type": "color" } },
    "text": { "primary": { "$value": "{color.brand.500}", "$type": "color" } }
  },
  "spacing": {
    "small": { "$value": "8", "$type": "dimension" }
  }
}
```

Note the `{color.brand.500}` reference in `text.primary` — this is **semantic token aliasing**: a semantic token (what it's *for*) points at a primitive token (the raw value), so changing the brand color in one place cascades everywhere `text.primary` is used, and swapping an entire theme (light → dark, default → a white-label brand variant) is just swapping which primitive values the semantic layer points at.

### 15.2 The Figma → code pipeline

**Style Dictionary** (an open-source build tool) is the standard transform layer: it ingests token JSON and outputs whatever format each platform needs — CSS custom properties for web, a TypeScript theme object for React Native, XML for Android, Swift for iOS — from the same source of truth.

```js
// style-dictionary.config.js
module.exports = {
  source: ['tokens/**/*.json'],
  platforms: {
    reactNative: {
      transformGroup: 'react-native',
      buildPath: 'src/theme/',
      files: [{ destination: 'tokens.ts', format: 'javascript/es6' }],
    },
  },
};
```

A typical end-to-end flow: a designer edits color/spacing/type values as **Figma Variables**; a plugin (Tokens Studio is the most widely used) exports them as DTCG-format JSON into a git repo; a CI job runs Style Dictionary on merge to regenerate the platform-specific theme files automatically. Figma's **Dev Mode** and **Code Connect** further shrink the handoff gap by showing developers real component code snippets (not just measurements) directly against the design file — useful for understanding structure, but treat Dev Mode's auto-generated code as a *reference*, not a production diff to paste in directly, since generated code typically lacks the accessibility attributes and project-specific patterns your actual component library expects.

### 15.3 Turning tokens into a working RN theme

```ts
// theme.ts
export const colors = {
  primary: '#2563eb',
  background: { light: '#ffffff', dark: '#0a0a0a' },
  surface: { light: '#f4f4f5', dark: '#18181b' },
  text: { light: '#0a0a0a', dark: '#f4f4f5' },
};

export const spacing = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 };
export const radii = { sm: 8, md: 12, lg: 16, full: 9999 };
```

Whichever styling system you chose in Part 9, wire this theme object into it once (a Tamagui token config, a NativeWind `tailwind.config.js` `theme.extend`, a Paper/UI Kitten theme object, or a plain React Context if you're on bare `StyleSheet`) rather than letting raw values leak into individual component files — this single decision is what makes a rebrand, a new dark-mode pass, or a design-token update from Figma a mechanical, low-risk change instead of a multi-day hunt through the codebase.

---

## 16. State Management & Data Fetching

### 16.1 The single most important idea: separate server state from client state

**Server state** (data that lives on a backend and is fetched over the network — user profiles, feed content, order history) and **client state** (data that only exists in the app itself — is this modal open, which tab is active, form draft values) are fundamentally different problems with different correct tools. Trying to manage both with the same general-purpose store (the classic all-Redux approach) is why Redux got a reputation for boilerplate — most of that boilerplate was really hand-built data-fetching/caching logic that a purpose-built tool now handles for you.

**The 2026 default pairing:** **Zustand** for client state + **TanStack Query** for server state. Together they cover the large majority of what teams used to reach for Redux to solve, with a fraction of the code and no `Provider` wrapping required for Zustand.

```bash
npx expo install zustand @tanstack/react-query
```

```ts
// store/useUIStore.ts — client state
import { create } from 'zustand';

interface UIState {
  isFilterSheetOpen: boolean;
  toggleFilterSheet: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  isFilterSheetOpen: false,
  toggleFilterSheet: () => set((s) => ({ isFilterSheetOpen: !s.isFilterSheetOpen })),
}));

// usage — no Provider needed
const isOpen = useUIStore((s) => s.isFilterSheetOpen);
```

```tsx
// server state
import { useQuery } from '@tanstack/react-query';

function ProfileScreen({ userId }: { userId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['profile', userId],
    queryFn: () => fetch(`/api/users/${userId}`).then((r) => r.json()),
  });

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState />;
  return <Profile data={data} />;
}
```

TanStack Query handles caching, request de-duplication, background refetching, retries, and optimistic updates for you — the "loading/error/data" dance that used to be hand-written Redux thunk boilerplate largely disappears.

### 16.2 When to reach for something else

| Situation | Reach for |
|---|---|
| Most new apps, small-to-mid team | Zustand (client) + TanStack Query (server) |
| Large team (10+ engineers), compliance/audit needs, or you need Redux DevTools' time-travel debugging for a genuinely complex state machine | **Redux Toolkit** (+ **RTK Query** if you want the data-fetching layer built into the same store rather than a separate library) |
| Many independent, fine-grained UI pieces with complex derived/computed state (form builders, canvases, spreadsheet-like UIs) | **Jotai** — atomic model, each atom is an independent subscription, so a change to one atom doesn't re-render components subscribed to unrelated atoms |
| You're already deep in the TanStack ecosystem (Query + Router + Table) and want one consistent primitive | **TanStack Store** |
| Maintaining a large existing Redux codebase | Redux Toolkit is fine to keep — migrate incrementally (new features on Zustand/TanStack Query first, then peel server-state logic out of Redux into TanStack Query, then migrate remaining client state last) rather than a risky big-bang rewrite |

**Redux Toolkit (RTK)** is the modern, official way to write Redux — `createSlice`/`configureStore` eliminate almost all of the historical action-type/reducer-switch-statement boilerplate, and it remains the right call when a large team genuinely needs Redux's explicit, centralized, time-travel-debuggable architecture. **RTK Query** (included in the same package, `@reduxjs/toolkit/query/react`) is Redux's answer to TanStack Query — a `createApi` call defines a full set of endpoints and auto-generates data-fetching hooks with caching, invalidation, and de-duplication built in, so you get the "boring Redux" benefits without hand-writing thunks for every request:

```ts
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({ baseUrl: 'https://api.example.com/' }),
  endpoints: (builder) => ({
    getProfile: builder.query<Profile, string>({ query: (id) => `users/${id}` }),
  }),
});

export const { useGetProfileQuery } = api;
```

### 16.3 The state-classification exercise

Before reaching for any library, classify what you're actually storing — teams frequently discover that most of their perceived "state management problem" is really a data-fetching problem:

- **Server state** (API data) → TanStack Query or RTK Query. Never.
- **Form state** → React Hook Form (Part 17), not a global store.
- **URL/route state** → the router's own params (`useLocalSearchParams` in Expo Router), not duplicated into a separate store.
- **Local, single-component UI state** → plain `useState`/`useReducer`. Most component state genuinely doesn't need to leave the component.
- **Global client state actually shared across many screens** (auth session, theme preference, feature flags) → Zustand/Jotai, persisted to MMKV where it needs to survive an app restart (Part 19).

---

## 17. Forms & Validation

### 17.1 React Hook Form + Zod

The standard pairing: **React Hook Form** for performant, minimal-re-render form state, **Zod** for schema validation and TypeScript type inference from a single source of truth, connected via `@hookform/resolvers`.

```bash
npm install react-hook-form zod @hookform/resolvers
```

Because React Native has no native `<form>`/`<input>` DOM elements, you drive every field through React Hook Form's `<Controller>` component (RN's `TextInput` can't be `register()`-ed the way an HTML `<input>` can):

```tsx
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { TextInput, Text, View, Pressable } from 'react-native';

const schema = z.object({
  email: z.string().email({ message: 'Enter a valid email address' }),
  password: z.string().min(8, { message: 'At least 8 characters' }),
});
type FormValues = z.infer<typeof schema>;

function LoginForm() {
  const { control, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });

  const onSubmit = (data: FormValues) => { /* call your API */ };

  return (
    <View>
      <Controller
        control={control}
        name="email"
        render={({ field: { onChange, onBlur, value } }) => (
          <TextInput
            value={value}
            onChangeText={onChange}
            onBlur={onBlur}
            autoCapitalize="none"
            keyboardType="email-address"
            accessibilityLabel="Email address"
          />
        )}
      />
      {errors.email && <Text style={{ color: 'crimson' }}>{errors.email.message}</Text>}

      <Pressable onPress={handleSubmit(onSubmit)} accessibilityRole="button" accessibilityLabel="Log in">
        <Text>Log In</Text>
      </Pressable>
    </View>
  );
}
```

**Gotcha:** if you're on Zod v4 with an older `@hookform/resolvers`, you may hit a "expected a Zod schema" runtime error inside React Native specifically — either upgrade `@hookform/resolvers` to a version with confirmed Zod v4 support, or import `zod/v3` compatibility mode as a stopgap. Always check both packages' current peer-dependency ranges together before upgrading either one independently.

### 17.2 Practical form guidance
- Validate on blur or on submit for most fields, not on every keystroke — validating too eagerly (marking an email field invalid after the very first character) reads as hostile, not helpful.
- Reuse one schema-plus-defaults hook for both "create" and "edit" flows of the same entity, rather than maintaining two nearly-identical form components.
- Surface server-side validation errors (a "this email is already taken" response from your API) through the same `errors` object React Hook Form already renders, via `setError`, so the user sees one consistent error-display pattern regardless of whether the failure was caught client-side or server-side.
- Respect keyboard behavior deliberately: correct `keyboardType` per field (`email-address`, `numeric`, `phone-pad`), correct `returnKeyType`/`onSubmitEditing` chaining so the keyboard's return key advances focus to the next field, and test that your layout doesn't let the keyboard cover the active input (`KeyboardAvoidingView` or a library like `react-native-keyboard-controller` for anything beyond the simplest form).

---

## 18. Lists, Images & Performance

### 18.1 FlashList over FlatList for any real dataset

RN's built-in `FlatList` is a windowed/virtualized list — it only renders items near the visible viewport — but under load it still **destroys and recreates** component instances as they scroll on and off screen, which is expensive (JS creates a new component, native lays it out, all for something the user glanced at for a fraction of a second) and is the direct cause of the "blank flash while fast-scrolling" problem.

**FlashList** (Shopify) solves this with view **recycling**: instead of destroying an off-screen item, it keeps the underlying view and just updates its props/content when a new item scrolls into that recycled slot — closer to how native `RecyclerView`/`UITableView` actually work.

```tsx
import { FlashList } from '@shopify/flash-list';

<FlashList
  data={items}
  renderItem={({ item }) => <ProductCard item={item} />}
  keyExtractor={(item) => item.id}
/>
```

FlashList v2 (New Architecture only) removed the old requirement to hand-tune an `estimatedItemSize` prop, added Masonry (Pinterest-style) layout support, and is a near drop-in replacement for `FlatList` — most migrations are a component-name swap plus removing now-unnecessary size-estimate props. Practical rules that apply to any list library, including FlatList if you're stuck on it:
- Never put a `key` prop inside an item's own render tree (only on the top-level array-mapped element) — a stray internal `key` breaks recycling entirely and silently reverts you to FlatList-like behavior.
- Memoize `renderItem` and keep item components as cheap as possible; profile in release mode specifically, since dev-mode and release-mode performance differ substantially for virtualized lists.
- For heterogeneous item types in one list (a chat view mixing text/image/system messages), use `getItemType` so FlashList can maintain separate recycling pools per type instead of fighting to reuse a text-message view for an image message.

For lists under a few hundred items, plain `FlatList` is genuinely fine — don't add a dependency you don't need. Reach for FlashList once a list is large, has complex item layouts, or shows any visible jank on a mid-range Android device.

### 18.2 Images

`expo-image` (or `react-native-fast-image` in bare CLI projects) should replace RN's built-in `Image` component for anything beyond the most trivial static asset — it adds disk+memory caching, smooth cross-fade transitions on load, blurhash/thumbhash placeholder support, and meaningfully better memory behavior for image-heavy scroll views:

```tsx
import { Image } from 'expo-image';

<Image
  source={{ uri: product.imageUrl }}
  placeholder={{ blurhash: product.blurhash }}
  contentFit="cover"
  transition={200}
  style={{ width: '100%', aspectRatio: 1, borderRadius: 12 }}
/>
```

Serve appropriately-sized images from your backend/CDN (don't ship a 3000px-wide hero image to render at 150px), and prefer modern formats (WebP/AVIF) where your image pipeline supports them.

### 18.3 General performance checklist
- **Hermes is the default engine** and should stay that way — it's purpose-built for RN, with ahead-of-time bytecode compilation for faster startup and a smaller memory footprint than running raw JS through a general-purpose engine.
- **Memoize deliberately, not reflexively.** `useCallback`/`useMemo`/`React.memo` help, but wrapping everything in them "just in case" adds its own overhead and cognitive load — measure before and after a change, don't guess.
- **Move expensive computation off the render path** and, where it's animation-adjacent, off the JS thread entirely via Reanimated worklets (Part 11).
- **Avoid unnecessary re-renders from over-broad Context** — a single large Context value that changes frequently will re-render every consumer on every change; split contexts by how often each piece of data actually changes, or reach for a selector-based store (Zustand, Jotai) instead.
- **Watch bundle size** — Expo Atlas (`npx expo start` includes a bundle visualizer) and the standard Metro bundle-analysis tooling both help spot a dependency that's silently bloating your JS bundle.

---

## 19. Local Storage

Pick the right tool per data category — these are not interchangeable, and reaching for the wrong one is a common source of both bugs and security gaps.

| Data | Use | Why |
|---|---|---|
| Auth/refresh tokens, API keys, other secrets | **`expo-secure-store`** | Backed by iOS Keychain / Android Keystore; encrypted at rest by the OS. Note the practical payload-size ceiling (roughly ~2KB historically on some iOS versions) — store a small credential or an encryption key here, not a large object |
| Fast-changing UI/app state, theme, locale, onboarding flags, persisted Zustand/Jotai state, small caches | **`react-native-mmkv`** | Memory-mapped file storage, ~30x faster reads/writes than AsyncStorage, fully synchronous (no `await` needed), supports multiple named instances and built-in AES encryption |
| Legacy/compatibility baseline, or you need the broadest possible library compatibility during a migration | **`@react-native-async-storage/async-storage`** | Simple, promise-based, community-maintained (moved out of RN core years ago) — fine for small amounts of data, but don't reach for it in new code purely out of habit |
| Structured/relational data — many rows, queries, relationships, offline sync | **`expo-sqlite`, WatermelonDB, or Realm** | Key-value stores are the wrong tool once you need real queries, indexes, or conflict-resolution logic; don't hide a database inside a pile of serialized JSON strings in AsyncStorage/MMKV |

```ts
// react-native-mmkv v4
import { createMMKV } from 'react-native-mmkv';

export const storage = createMMKV(); // reuse this single instance across the app

storage.set('theme', 'dark');
storage.set('onboardingComplete', true);
const theme = storage.getString('theme');

// A separate, encrypted instance for anything more sensitive than UI prefs
export const secureCache = createMMKV({ id: 'secure-cache', encryptionKey: 'derive-this-from-secure-store' });
```

A clean pattern: store the actual MMKV **encryption key** in `expo-secure-store` (small payload, OS-encrypted) and use that key to encrypt a larger MMKV instance holding bigger cached payloads — you get SecureStore's hardware-backed key protection without hitting its payload-size ceiling.

**Migrating from AsyncStorage to MMKV in an existing app:** do a one-time copy of legacy keys into MMKV behind a completion flag, verify the copy, then stop reading from AsyncStorage — don't try to blindly swap every `await AsyncStorage.getItem(...)` call for a synchronous MMKV call and assume identical behavior, since the async/sync mismatch can hide subtle timing bugs during the transition.

---

## 20. Accessibility

### 20.1 Why React Native accessibility requires deliberate work

On the web, semantic HTML (`<button>`, `<nav>`, `<input>`) gives you a baseline accessibility tree for free — a browser already knows what a `<button>` is. React Native has no DOM; nearly everything ultimately renders as a platform `View`, which has **no inherent meaning** to VoiceOver or TalkBack. If you don't explicitly attach accessibility props, the assistive-technology user gets nothing — not "this is a broken button," just silence. Accessibility on mobile is opt-in and explicit by construction, not a matter of "remembering to add `alt` text."

### 20.2 The core props

```tsx
<Pressable
  onPress={addToCart}
  accessible={true}
  accessibilityRole="button"
  accessibilityLabel="Add to cart"
  accessibilityHint="Adds this item to your shopping cart"
  accessibilityState={{ disabled: !inStock }}
  disabled={!inStock}
>
  <CartIcon />
</Pressable>
```

- **`accessibilityRole`** — tells assistive tech what kind of element this is (`button`, `header`, `link`, `checkbox`, `switch`, `image`, `adjustable`, `menuitem`, and more). Without it, a perfectly button-shaped `View` is announced as an anonymous element with no indication it's tappable.
- **`accessibilityLabel`** — the element's *identity*, read first. Required whenever visible content alone isn't sufficient (icon-only buttons, images) — but don't duplicate visible text: if a button already displays "Save," adding `accessibilityLabel="Save"` causes VoiceOver to announce "Save Save."
- **`accessibilityHint`** — the *outcome* of interacting with the element, used sparingly for genuinely non-obvious results. Users can disable hints in their screen-reader settings, so the label alone must always be enough to understand the control — treat hints as bonus context, never the only source of meaning.
- **`accessibilityState`** — communicates dynamic state (`disabled`, `selected`, `checked`, `expanded`, `busy`) that a sighted user perceives visually but a screen-reader user otherwise wouldn't know changed.
- **`accessibilityValue`** — for range-based controls (sliders, progress bars): `{ min, max, now }`, so a screen reader can announce "Volume, 65%."

### 20.3 Known gotchas
- **ALL CAPS labels get spelled out letter by letter.** VoiceOver interprets an all-caps string as an abbreviation — a button labeled `"SAVE"` in your UI announces as "S. A. V. E.," not "Save." Keep the *label* in normal case even if the *visible* text style is uppercase.
- **Don't duplicate visible text in the label** (covered above) — it produces an awkward double-announcement.
- **Dynamic content changes need an explicit announcement.** If new content appears, an error shows up, or a view changes state, nothing tells a screen reader unless you say so — either via a live region (`accessibilityLiveRegion="polite"` on Android, or programmatically via `AccessibilityInfo.announceForAccessibility()`) or by explicitly moving accessibility focus (`AccessibilityInfo.setAccessibilityFocus`) to the new content.
- **Focus order isn't guaranteed to follow visual/DOM order** the way it reliably would on the web — test actual focus traversal with VoiceOver/TalkBack on real elements, especially in custom layouts, rather than assuming code order equals reading order.
- **Custom components need accessibility props threaded all the way through**, typically assigned to the top-most wrapping element of the composed component, with the option to override still exposed to the consumer.
- **Test on real devices with the actual screen reader on.** Simulator behavior and real-device VoiceOver/TalkBack behavior diverge often enough that "it worked in the simulator" isn't a reliable accessibility signal.

### 20.4 A minimal accessible-component checklist
1. Every interactive element has an explicit `accessibilityRole`.
2. Every icon-only control has a clear, action-oriented `accessibilityLabel` (not "gear icon" — "Settings").
3. Toggle/checkbox/switch-style controls expose `accessibilityState` so screen readers announce on/off, checked/unchecked.
4. Dynamic UI changes (errors, loading states, toasts) are announced, not just visually rendered.
5. Text respects system font scaling (see Part 13.3) instead of disabling `allowFontScaling`.
6. Color is never the *only* signal for meaning (error states also get an icon/text label, not just a red border).
7. Every meaningful animation/gesture-only interaction respects "Reduce Motion" and has a non-gesture fallback.

---

## 21. Testing

| Layer | Tool | Role |
|---|---|---|
| Unit / component logic | **Jest** + **React Native Testing Library** | Fast, isolated tests of hooks, utility functions, and component rendering/behavior without a real device or simulator |
| End-to-end (E2E), React-Native-specific | **Detox** | Gray-box: injects monitoring into the app process itself, synchronizing test execution with the JS thread, native UI queue, and network activity so tests only proceed when the app is truly idle — this is what gives it very low flakiness, at the cost of real native build/config setup |
| End-to-end (E2E), cross-platform-friendly | **Maestro** | Black-box: drives the app externally through the accessibility layer, using a declarative YAML flow syntax that reads like plain English. No native project changes, no code dependencies, works across React Native/Flutter/native apps alike. Much faster to set up than Detox, and increasingly the default recommendation for teams without a dedicated test-automation engineer |
| End-to-end, enterprise/multi-language | **Appium** | WebDriver-standard, broadest device/language support, common in orgs with existing WebDriver-based QA infrastructure across web + mobile; more setup overhead and generally slower than Maestro for RN-specific flows |

A representative Maestro flow (a login test), to show how low the authoring bar is:

```yaml
appId: com.myapp
---
- launchApp
- tapOn: "Email"
- inputText: "test@example.com"
- tapOn: "Password"
- inputText: "hunter2"
- tapOn: "Log In"
- assertVisible: "Welcome back"
```

**A sane default testing strategy for most teams:** Jest + React Native Testing Library for unit/component coverage as the bulk of your suite (fast feedback, runs on every commit), Maestro for a lean set of critical-path E2E flows (login, checkout, core happy paths) since it has the lowest setup cost, and Detox specifically when you need Detox's deeper JS-thread synchronization for a flakiness-sensitive suite and have the engineering bandwidth to maintain its native build configuration. Don't try to E2E-test everything — E2E suites are slow and comparatively brittle no matter which tool you pick; reserve them for flows where a regression would be genuinely costly.

Add `testID` props to key elements to make them reliably targetable regardless of visible text changes/localization, but note this isn't strictly required for Maestro (which can also match on visible text) — it's most valuable for Detox and for any element whose visible label might change or is localized.

---

## 22. Project Structure & Architecture

### 22.1 A feature-based structure that scales

For anything beyond a small demo, organize by **feature/domain**, not by file type — a folder full of forty unrelated files all named `*.tsx` inside one giant `components/` directory doesn't scale, while a structure that groups everything related to one feature together does:

```
src/
  app/                    # Expo Router routes (thin — import screens from features/)
  features/
    auth/
      components/
      hooks/
      api.ts               # TanStack Query hooks for this domain
      store.ts             # Zustand slice for this domain, if needed
      schema.ts            # Zod schemas for this domain
    profile/
    checkout/
  components/             # Truly shared, cross-feature UI primitives (Button, Card, ...)
  hooks/                  # Truly shared hooks (useDebounce, useColorScheme, ...)
  theme/                  # Design tokens, typography scale, color roles (Part 15)
  lib/                    # API client setup, MMKV instances, third-party SDK init
  types/
```

Keep route files in `app/` (or `src/app/` for Expo Router) intentionally thin — a route file should mostly import and render a screen component from `features/`, not contain the screen's actual implementation. This keeps the routing layer swappable (Expo Router today, something else later, if that ever became necessary) without a full rewrite of screen logic.

### 22.2 Environment configuration

Use `app.config.ts` (not static `app.json`) the moment you need per-environment values (dev/staging/production API URLs, different bundle identifiers per environment, feature flags):

```ts
// app.config.ts
import 'dotenv/config';

export default ({ config }) => ({
  ...config,
  name: process.env.APP_ENV === 'production' ? 'MyApp' : 'MyApp (Dev)',
  extra: { apiUrl: process.env.API_URL },
});
```

```ts
import Constants from 'expo-constants';
const apiUrl = Constants.expoConfig?.extra?.apiUrl;
```

For EAS builds, define environment-specific values as **EAS environment variables** per build profile rather than committing multiple `.env` files, so staging and production builds pull genuinely different, securely-managed values from the same source of truth.

### 22.3 A few architecture principles worth stating explicitly
- **Screens are composition, not implementation.** A screen component wires together feature hooks/components and handles layout; it shouldn't contain business logic that a hook or service module should own instead.
- **Co-locate a feature's Zod schema, API hook, and Zustand slice** — when they live next to each other, changing an API response shape is a one-folder change instead of a codebase-wide hunt.
- **Isolate third-party SDK initialization** (analytics, crash reporting, push notification setup) behind your own thin wrapper module rather than importing the vendor SDK directly all over the app — this is what makes swapping a vendor later (or mocking it in tests) tractable.
- **Don't let the New Architecture / Fabric distinction leak into application code.** If you find yourself writing conditional logic based on old vs. new architecture in a regular screen component, something's wrong — that concern belongs at the native-module boundary, not in UI code.

---

## 23. Quick-Reference Cheat Sheets

### 23.1 New project, zero to running

```bash
# Expo (default choice)
npx create-expo-app@latest my-app
cd my-app && npx expo start

# React Native CLI (bare)
npx @react-native-community/cli@latest init MyApp
cd MyApp && npx react-native run-ios
```

### 23.2 "Modern 2026 stack" starter install

A reasonable, opinionated default for a new Expo + TypeScript app — swap any row for the alternative that fits your team, per the decision tables above:

```bash
# Navigation — Expo Router ships by default with create-expo-app

# Styling
npx expo install nativewind react-native-reanimated react-native-safe-area-context
npm install -D tailwindcss@^3.4.17

# Animation & gestures
npx expo install react-native-reanimated react-native-worklets react-native-gesture-handler

# Icons
npx expo install @react-native-vector-icons/ionicons

# Fonts
npx expo install expo-font @expo-google-fonts/inter expo-splash-screen

# State
npm install zustand @tanstack/react-query

# Forms
npm install react-hook-form zod @hookform/resolvers

# Lists
npx expo install @shopify/flash-list

# Storage
npx expo install expo-secure-store
npm install react-native-mmkv react-native-nitro-modules

# Images & haptics
npx expo install expo-image expo-haptics

# Testing
npm install -D jest @testing-library/react-native
```

### 23.3 Package → purpose lookup

| Package | Purpose |
|---|---|
| `expo-router` | File-based navigation |
| `@react-navigation/native` + `native-stack`/`bottom-tabs` | Code-configured navigation |
| `react-native-reanimated` + `react-native-worklets` | UI-thread animation |
| `react-native-gesture-handler` | Native-thread gesture recognition |
| `moti` | Declarative animation wrapper over Reanimated |
| `@shopify/react-native-skia` | GPU 2D graphics/Canvas |
| `lottie-react-native` / `react-native-skottie` | After Effects (Bodymovin) animations |
| `@gorhom/bottom-sheet` | Draggable bottom sheets |
| `nativewind` | Tailwind utility classes for RN |
| `@tamagui/core` | Compiler-optimized universal styling + UI kit |
| `react-native-paper` | Material Design 3 components |
| `@gluestack-ui/*` | Copy-paste, Tailwind-native component library |
| `@ui-kitten/components` | Eva Design System components, runtime theming |
| `@react-native-vector-icons/*` | Icon fonts (current, replaces `@expo/vector-icons`) |
| `react-native-svg` | Custom/brand SVG icons and graphics |
| `expo-font`, `@expo-google-fonts/*` | Font loading |
| `zustand` | Client state |
| `@tanstack/react-query` | Server state / data fetching & caching |
| `@reduxjs/toolkit` | Redux, for large teams/compliance needs |
| `jotai` | Atomic, fine-grained client state |
| `react-hook-form`, `zod`, `@hookform/resolvers` | Forms and validation |
| `@shopify/flash-list` | High-performance recycled lists |
| `expo-image` | Cached, placeholder-aware images |
| `react-native-mmkv` | Fast synchronous key-value storage |
| `expo-secure-store` | OS-encrypted secret storage |
| `expo-sqlite` / WatermelonDB / Realm | Structured/relational local data |
| `@testing-library/react-native` + `jest` | Unit/component tests |
| `detox` / `maestro` | End-to-end tests |

---

## 24. Common Pitfalls

- **Reaching for a library that hasn't shipped a release since before the New Architecture became mandatory.** Check the repo's last release date and open issues for "Fabric"/"New Architecture" before adopting anything non-trivial.
- **Forgetting `GestureHandlerRootView`** at the app root (and again inside any `Modal`) — the most common cause of "gestures silently do nothing."
- **Disabling `allowFontScaling` reflexively** to protect a layout, rather than designing a layout that tolerates text scaling — this actively harms accessibility for users who rely on larger system text.
- **Skipping accessibility props on icon-only buttons** — a perfectly functional button that's completely invisible to a screen reader.
- **Treating Expo Go as the app you ship** — it's a development sandbox with a fixed, latest-SDK-only module set; production apps are built and tested through development builds / EAS Build.
- **Jumping multiple Expo SDK versions or RN minor versions at once** — upgrade incrementally; this is doubly true post-SDK-56 given the Expo Router internals fork (go through each intermediate SDK, don't skip from 54 straight to 56).
- **Installing `tailwindcss@latest` alongside stable NativeWind** — NativeWind's stable line targets Tailwind v3; pin the version explicitly.
- **Mixing multiple icon families in one screen** for no functional reason — pick one and stay consistent.
- **Storing secrets in AsyncStorage or plain MMKV** instead of `expo-secure-store` (or an MMKV instance encrypted with a SecureStore-protected key).
- **Hiding a relational data model inside serialized JSON strings in a key-value store** instead of reaching for SQLite/WatermelonDB/Realm once the data actually has structure, relationships, or needs queries.
- **Over-animating.** Motion with no communicative purpose (see Part 14.5) is one of the fastest ways to make an app feel unpolished or template-generated rather than deliberately designed — and it's a real accessibility problem for users with "Reduce Motion" enabled if you don't respect that setting.
- **Assuming visual parity between NativeWind/Tailwind classes on web vs. native** — always verify on-device; RN's style engine doesn't support every CSS concept a Tailwind class implies.
- **Blindly trusting AI-generated Figma-to-code exports as production-ready** — they typically lack accessibility attributes and don't follow your actual codebase's component/state patterns; use them as a structural reference, not a final diff.

---

## 25. Further Reading

- React Native core docs & architecture: `reactnative.dev/docs/accessibility`, `reactnative.dev/architecture/landing-page`
- Expo docs (the single best-maintained source for anything Expo-specific): `docs.expo.dev`
- Expo Router: `docs.expo.dev/router`
- EAS: `docs.expo.dev/eas-update`, `docs.expo.dev/build`, `docs.expo.dev/submit`
- React Navigation: `reactnavigation.org`
- Reanimated & Gesture Handler (Software Mansion): `docs.swmansion.com/react-native-reanimated`, `docs.swmansion.com/react-native-gesture-handler`
- React Native Skia: `shopify.github.io/react-native-skia`
- FlashList: `shopify.github.io/flash-list`
- NativeWind: `nativewind.dev`
- Tamagui: `tamagui.dev`
- React Native Paper: `oss.callstack.com/react-native-paper`
- gluestack-ui: `gluestack.io`
- UI Kitten / Eva Design System: `akveo.github.io/react-native-ui-kitten`
- Material Design 3: `m3.material.io`
- Apple Human Interface Guidelines: `developer.apple.com/design/human-interface-guidelines`
- TanStack Query: `tanstack.com/query`
- Redux Toolkit / RTK Query: `redux-toolkit.js.org`
- React Hook Form: `react-hook-form.com`
- Maestro: `maestro.dev`
- Detox: (Wix) `wix.github.io/Detox`

**A closing reminder:** this document is a map of a fast-moving territory. Treat every specific version number as a snapshot, not a permanent fact — before committing a real project to a specific package version, do a quick current-state check (`npm view <package> version`, the project's own changelog, or a fresh search) rather than assuming anything here is still exactly current.