"""Browser fingerprint anti-detection init scripts.

Fixes the original code's issues:
- `ANTI_DETECT_JS` was trivial (only 4 properties) — modern WhatsApp Web
  anti-bot checks much more (WebGL, Canvas, AudioContext, fonts, etc.)
- `navigator.plugins` returned `[1, 2, 3, 4, 5]` (numbers!) — easily detected
  as fake because real plugins have a specific shape
- No timezone/locale spoofing
"""
from __future__ import annotations

import random

from media.whatsapp.config import settings


# Realistic Chrome plugins list (must look like PluginArray objects)
_PLUGINS_JS = """
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const make = (name, filename, desc) => {
            const p = { name, filename, description: desc, length: 1 };
            p[0] = { type: 'application/pdf', suffixes: 'pdf', description: desc };
            return p;
        };
        const arr = [
            make('PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
            make('Chrome PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
            make('Chromium PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
            make('Microsoft Edge PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
            make('WebKit built-in PDF', 'internal-pdf-viewer', 'Portable Document Format'),
        ];
        arr.namedItem = (name) => arr.find(p => p.name === name) || null;
        arr.refresh = () => {};
        arr.item = (i) => arr[i] || null;
        return arr;
    }
});
"""


# Languages: pretend to be en-US primary
_LANGUAGES_JS = """
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en']
});
"""


# Hide webdriver flag
_WEBDRIVER_JS = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
Object.defineProperty(navigator, 'driverEval', {
    get: () => undefined
});
"""


# Chrome runtime object (proves we're "real" Chrome)
_CHROME_JS = """
window.chrome = window.chrome || {};
window.chrome.runtime = window.chrome.runtime || {};
window.chrome.app = window.chrome.app || { isInstalled: false };
window.chrome.csi = window.chrome.csi || function() { return {}; };
window.chrome.loadTimes = window.chrome.loadTimes || function() { return {}; };
"""


# Permissions API: always return 'granted' to avoid detection via prompt
_PERMISSIONS_JS = """
const origQuery = navigator.permissions && navigator.permissions.query;
if (origQuery) {
    navigator.permissions.query = (p) => (
        p && p.name === 'notifications'
            ? Promise.resolve({ state: 'granted', onchange: null })
            : origQuery.call(navigator.permissions, p)
    );
}
"""


# WebGL vendor/renderer spoofing (common anti-bot check)
_WEBGL_JS = """
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';            // UNMASKED_VENDOR_WEBGL
    if (p === 37446) return 'Intel Iris OpenGL Engine'; // UNMASKED_RENDERER_WEBGL
    return getParameter.call(this, p);
};
"""


# Hardware concurrency & device memory (look like a real machine).
# Note: values are randomized per-session in build_init_script() below.
# Override `navigator.userAgent` to remove "HeadlessChrome"`
_USER_AGENT_JS = """
if (navigator.userAgent.includes('HeadlessChrome')) {
    Object.defineProperty(navigator, 'userAgent', {
        get: () => navigator.userAgent.replace('HeadlessChrome', 'Chrome')
    });
}
"""


_ANTI_DETECT_TEMPLATE = """
// ── Anti-detection init script ────────────────────────────────────────────
// __HARDWARE_PLACEHOLDER__
__WEBDRIVER__
__PLUGINS__
__LANGUAGES__
__CHROME__
__PERMISSIONS__
__WEBGL__
__USER_AGENT__
"""


# Backwards-compat: expose the original constant name (without hardware spoofing)
ANTI_DETECT_JS = _ANTI_DETECT_TEMPLATE.replace(
    "// __HARDWARE_PLACEHOLDER__\n", ""
).replace("__WEBDRIVER__", _WEBDRIVER_JS.strip()
).replace("__PLUGINS__", _PLUGINS_JS.strip()
).replace("__LANGUAGES__", _LANGUAGES_JS.strip()
).replace("__CHROME__", _CHROME_JS.strip()
).replace("__PERMISSIONS__", _PERMISSIONS_JS.strip()
).replace("__WEBGL__", _WEBGL_JS.strip()
).replace("__USER_AGENT__", _USER_AGENT_JS.strip())


def build_init_script() -> str:
    """Build a fresh init script with randomized hardware values per session."""
    cores = random.choice([4, 8, 12, 16])
    memory = random.choice([4, 8, 16])
    hardware_js = (
        "Object.defineProperty(navigator, 'hardwareConcurrency', "
        "{ get: () => " + str(cores) + " });\n"
        "Object.defineProperty(navigator, 'deviceMemory', "
        "{ get: () => " + str(memory) + " });"
    )
    return (
        _ANTI_DETECT_TEMPLATE
        .replace("// __HARDWARE_PLACEHOLDER__\n", hardware_js + "\n")
        .replace("__WEBDRIVER__", _WEBDRIVER_JS.strip())
        .replace("__PLUGINS__", _PLUGINS_JS.strip())
        .replace("__LANGUAGES__", _LANGUAGES_JS.strip())
        .replace("__CHROME__", _CHROME_JS.strip())
        .replace("__PERMISSIONS__", _PERMISSIONS_JS.strip())
        .replace("__WEBGL__", _WEBGL_JS.strip())
        .replace("__USER_AGENT__", _USER_AGENT_JS.strip())
    )
