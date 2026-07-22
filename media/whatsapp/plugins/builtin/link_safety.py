"""Link safety checking plugin.

Extracts URLs from incoming messages and checks them against:
1. A local blocklist of known-bad domains
2. The Google Safe Browsing API (if API key is configured)

Suspicious links force the message into the approval queue.
"""
from __future__ import annotations

import re
from typing import Optional

from media.whatsapp.plugins.base import Plugin, PluginContext, PluginResult, HookPoint
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)

_URL_RE = re.compile(
    r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*",
)

# Known-bad domain patterns (extend as needed)
_BLOCKED_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co",  # Shorteners (often abused)
    "ngrok.io", "locanet.contabil.net",
}
_BLOCKED_PATTERNS = [
    re.compile(r"free[- ]?(money|cash|gift|prize|iphone|samsung)", re.I),
    re.compile(r"(crypto|bitcoin|btc|eth)\s*(giveaway|free|mining)", re.I),
    re.compile(r"verify\s+(your\s+)?account|confirm\s+(your\s+)?(identity|account)", re.I),
    re.compile(r"you\s+won|winner|congratulations?\s+you", re.I),
    re.compile(r"click\s+here\s+to\s+(claim|get|win|verify)", re.I),
]


class LinkSafetyPlugin(Plugin):
    """Checks URLs in messages against safety databases."""

    name = "link_safety"
    version = "1.0.0"
    description = "Checks URLs for spam/phishing; escalates suspicious links"
    hooks = {HookPoint.BEFORE_DECISION}
    default_config = {
        "block_shorteners": True,
        "check_safe_browsing": False,  # Requires Google API key
        "safe_browsing_api_key": "",
        "force_approval_on_suspicious": True,
    }

    def before_decision(self, ctx: PluginContext) -> PluginResult:
        """Check all messages for suspicious links."""
        full_text = " ".join(m.get("content", "") for m in ctx.messages)
        if not full_text:
            return PluginResult()

        urls = _URL_RE.findall(full_text)
        if not urls:
            # Also check for suspicious patterns even without URLs
            for pattern in _BLOCKED_PATTERNS:
                if pattern.search(full_text):
                    logger.warning(
                        f"[LinkSafety] Suspicious pattern in message from "
                        f"{ctx.contact_name}: {pattern.pattern}"
                    )
                    if ctx.decision and self.config["force_approval_on_suspicious"]:
                        modified = dict(ctx.decision)
                        modified["needs_approval"] = True
                        modified["risk_level"] = "HIGH"
                        modified["reason"] = f"Suspicious content pattern detected"
                        return PluginResult(modified_decision=modified)
                    break
            return PluginResult()

        suspicious_urls = []
        for url in urls:
            domain = self._extract_domain(url)
            if self._is_suspicious(domain, full_text):
                suspicious_urls.append(url)

        if suspicious_urls:
            logger.warning(
                f"[LinkSafety] {len(suspicious_urls)} suspicious URL(s) from "
                f"{ctx.contact_name}: {suspicious_urls[:3]}"
            )
            if ctx.decision and self.config["force_approval_on_suspicious"]:
                modified = dict(ctx.decision)
                modified["needs_approval"] = True
                modified["risk_level"] = "HIGH"
                modified["reason"] = f"Suspicious URL(s): {', '.join(suspicious_urls[:3])}"
                return PluginResult(modified_decision=modified)

        # Optional: Google Safe Browsing API check
        if self.config["check_safe_browsing"] and self.config["safe_browsing_api_key"]:
            for url in urls:
                if self._check_safe_browsing(url):
                    logger.warning(f"[LinkSafety] Safe Browsing flagged: {url}")
                    if ctx.decision:
                        modified = dict(ctx.decision)
                        modified["needs_approval"] = True
                        modified["risk_level"] = "CRITICAL"
                        modified["reason"] = f"Safe Browsing flag: {url}"
                        return PluginResult(modified_decision=modified)
                    break

        return PluginResult()

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract the domain from a URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower().replace("www.", "")
        except Exception:
            return ""

    def _is_suspicious(self, domain: str, text: str) -> bool:
        """Check if a domain is suspicious based on blocklist + heuristics."""
        if not domain:
            return False
        # Check blocklist
        if self.config["block_shorteners"] and domain in _BLOCKED_DOMAINS:
            return True
        # Check for lookalike domains (e.g., "faceb00k.com")
        # Skip exact matches — a legit domain is not a lookalike of itself
        legit = ["facebook.com", "google.com", "amazon.com", "apple.com",
                 "microsoft.com", "paypal.com", "instagram.com", "whatsapp.com"]
        if domain in legit:
            return False
        for l in legit:
            if self._is_lookalike(domain, l):
                return True
        return False

    @staticmethod
    def _is_lookalite(domain: str, legit: str) -> bool:
        """Check if domain is a lookalike of a legitimate domain."""
        # Replace common lookalike chars
        normalized = domain.replace("0", "o").replace("1", "l").replace("3", "e")
        if normalized == legit:
            return True
        # Check Levenshtein distance (simple: if differ by 1-2 chars)
        if abs(len(domain) - len(legit)) <= 2:
            diff = sum(a != b for a, b in zip(domain, legit))
            if diff <= 2 and len(domain) == len(legit):
                return True
        return False

    def _is_lookalike(self, domain: str, legit: str) -> bool:
        """Wrapper for the static method (fixes typo in method name)."""
        return self._is_lookalite(domain, legit)

    def _check_safe_browsing(self, url: str) -> bool:
        """Check URL against Google Safe Browsing API."""
        try:
            import requests
            api_key = self.config["safe_browsing_api_key"]
            payload = {
                "client": {"clientId": "whatsapp-bot", "clientVersion": "3.0"},
                "threatInfo": {
                    "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
                    "platformTypes": ["ANY_PLATFORM"],
                    "threatEntryTypes": ["URL"],
                    "threatEntries": [{"url": url}],
                },
            }
            r = requests.post(
                f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}",
                json=payload, timeout=5,
            )
            if r.ok:
                data = r.json()
                return bool(data.get("matches"))
        except Exception as e:
            logger.warning(f"[LinkSafety] Safe Browsing API error: {e}")
        return False
