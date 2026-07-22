"""Theme system — 6 professionally designed themes with full light/dark mode support.

Each theme defines:
- accent:  primary brand color
- bg:      window/chrome background
- surface: card / panel background
- border:  divider / stroke color
- text:    primary / secondary / tertiary
- success / warning / danger: semantic states

Applies via QSS (Qt Style Sheets) generated from token dicts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Theme Definitions — 6 professional themes
# ============================================================================

THEME_DEFINITIONS: dict[str, dict[str, str]] = {
    "Ocean Blue": {
        "accent": "#2563EB",
        "accent_hover": "#1D4ED8",
        "accent_subtle": "#DBEAFE",
        "bg": "#FAFAFA",
        "surface": "#FFFFFF",
        "surface_alt": "#F4F4F7",
        "border": "#E4E4E7",
        "text_primary": "#18181B",
        "text_secondary": "#52525B",
        "text_tertiary": "#A1A1AA",
        "success": "#16A34A",
        "warning": "#D97706",
        "danger": "#DC2626",
        "orb_gradient_start": "#3B82F6",
        "orb_gradient_end": "#8B5CF6",
    },
    "Ocean Blue Dark": {
        "accent": "#3B82F6",
        "accent_hover": "#5B9DF7",
        "accent_subtle": "rgba(59,130,246,0.14)",
        "bg": "#0B0B0D",
        "surface": "#161618",
        "surface_alt": "#1E1E21",
        "border": "#2B2B2F",
        "text_primary": "#F5F5F6",
        "text_secondary": "#A6A6AC",
        "text_tertiary": "#6B6B72",
        "success": "#3DD16F",
        "warning": "#FBBF24",
        "danger": "#F87171",
        "orb_gradient_start": "#60A5FA",
        "orb_gradient_end": "#A78BFA",
    },
    "Emerald": {
        "accent": "#059669",
        "accent_hover": "#047857",
        "accent_subtle": "#D1FAE5",
        "bg": "#FAFAFA",
        "surface": "#FFFFFF",
        "surface_alt": "#F4F4F7",
        "border": "#E4E4E7",
        "text_primary": "#18181B",
        "text_secondary": "#52525B",
        "text_tertiary": "#A1A1AA",
        "success": "#16A34A",
        "warning": "#D97706",
        "danger": "#DC2626",
        "orb_gradient_start": "#10B981",
        "orb_gradient_end": "#3B82F6",
    },
    "Emerald Dark": {
        "accent": "#34D399",
        "accent_hover": "#6EE7B7",
        "accent_subtle": "rgba(52,211,153,0.14)",
        "bg": "#0A0F0A",
        "surface": "#141914",
        "surface_alt": "#1C221C",
        "border": "#2A322A",
        "text_primary": "#F0FDF4",
        "text_secondary": "#A3AFA3",
        "text_tertiary": "#6A7A6A",
        "success": "#3DD16F",
        "warning": "#FBBF24",
        "danger": "#F87171",
        "orb_gradient_start": "#34D399",
        "orb_gradient_end": "#60A5FA",
    },
    "Amethyst": {
        "accent": "#7C3AED",
        "accent_hover": "#6D28D9",
        "accent_subtle": "#EDE9FE",
        "bg": "#FAFAFA",
        "surface": "#FFFFFF",
        "surface_alt": "#F4F4F7",
        "border": "#E4E4E7",
        "text_primary": "#18181B",
        "text_secondary": "#52525B",
        "text_tertiary": "#A1A1AA",
        "success": "#16A34A",
        "warning": "#D97706",
        "danger": "#DC2626",
        "orb_gradient_start": "#8B5CF6",
        "orb_gradient_end": "#EC4899",
    },
    "Amethyst Dark": {
        "accent": "#A78BFA",
        "accent_hover": "#C4B5FD",
        "accent_subtle": "rgba(167,139,250,0.14)",
        "bg": "#0B0A0D",
        "surface": "#161418",
        "surface_alt": "#1E1C22",
        "border": "#2B2930",
        "text_primary": "#F5F3FF",
        "text_secondary": "#A6A0B5",
        "text_tertiary": "#6B6578",
        "success": "#34D399",
        "warning": "#FBBF24",
        "danger": "#F87171",
        "orb_gradient_start": "#A78BFA",
        "orb_gradient_end": "#F472B6",
    },
    "Ruby": {
        "accent": "#DC2626",
        "accent_hover": "#B91C1C",
        "accent_subtle": "#FEE2E2",
        "bg": "#FAFAFA",
        "surface": "#FFFFFF",
        "surface_alt": "#F4F4F7",
        "border": "#E4E4E7",
        "text_primary": "#18181B",
        "text_secondary": "#52525B",
        "text_tertiary": "#A1A1AA",
        "success": "#16A34A",
        "warning": "#D97706",
        "danger": "#DC2626",
        "orb_gradient_start": "#EF4444",
        "orb_gradient_end": "#F59E0B",
    },
    "Ruby Dark": {
        "accent": "#F87171",
        "accent_hover": "#FCA5A5",
        "accent_subtle": "rgba(248,113,113,0.14)",
        "bg": "#0D0A0A",
        "surface": "#181414",
        "surface_alt": "#201C1C",
        "border": "#302A2A",
        "text_primary": "#FEF2F2",
        "text_secondary": "#AFA3A3",
        "text_tertiary": "#786A6A",
        "success": "#34D399",
        "warning": "#FBBF24",
        "danger": "#F87171",
        "orb_gradient_start": "#F87171",
        "orb_gradient_end": "#FBBF24",
    },
    "Midnight": {
        "accent": "#0EA5E9",
        "accent_hover": "#0284C7",
        "accent_subtle": "#E0F2FE",
        "bg": "#FAFAFA",
        "surface": "#FFFFFF",
        "surface_alt": "#F4F4F7",
        "border": "#E4E4E7",
        "text_primary": "#18181B",
        "text_secondary": "#52525B",
        "text_tertiary": "#A1A1AA",
        "success": "#16A34A",
        "warning": "#D97706",
        "danger": "#DC2626",
        "orb_gradient_start": "#38BDF8",
        "orb_gradient_end": "#818CF8",
    },
    "Midnight Dark": {
        "accent": "#38BDF8",
        "accent_hover": "#7DD3FC",
        "accent_subtle": "rgba(56,189,248,0.14)",
        "bg": "#05070A",
        "surface": "#0E1115",
        "surface_alt": "#161A20",
        "border": "#252A32",
        "text_primary": "#F0F4F8",
        "text_secondary": "#9CA3B0",
        "text_tertiary": "#656A78",
        "success": "#34D399",
        "warning": "#FBBF24",
        "danger": "#F87171",
        "orb_gradient_start": "#38BDF8",
        "orb_gradient_end": "#A78BFA",
    },
    "Sunset": {
        "accent": "#F97316",
        "accent_hover": "#EA580C",
        "accent_subtle": "#FED7AA",
        "bg": "#FAFAFA",
        "surface": "#FFFFFF",
        "surface_alt": "#F4F4F7",
        "border": "#E4E4E7",
        "text_primary": "#18181B",
        "text_secondary": "#52525B",
        "text_tertiary": "#A1A1AA",
        "success": "#16A34A",
        "warning": "#D97706",
        "danger": "#DC2626",
        "orb_gradient_start": "#F97316",
        "orb_gradient_end": "#EF4444",
    },
    "Sunset Dark": {
        "accent": "#FB923C",
        "accent_hover": "#FDBA74",
        "accent_subtle": "rgba(251,146,60,0.14)",
        "bg": "#0D0B09",
        "surface": "#171410",
        "surface_alt": "#1F1C17",
        "border": "#2F2A24",
        "text_primary": "#FFF7ED",
        "text_secondary": "#ADA497",
        "text_tertiary": "#756F65",
        "success": "#34D399",
        "warning": "#FBBF24",
        "danger": "#F87171",
        "orb_gradient_start": "#FB923C",
        "orb_gradient_end": "#F87171",
    },
}

# Theme groups — dark/light pairs
THEME_PAIRS: list[tuple[str, str]] = [
    ("Ocean Blue", "Ocean Blue Dark"),
    ("Emerald", "Emerald Dark"),
    ("Amethyst", "Amethyst Dark"),
    ("Ruby", "Ruby Dark"),
    ("Midnight", "Midnight Dark"),
    ("Sunset", "Sunset Dark"),
]

THEME_NAMES = list(THEME_DEFINITIONS.keys())

# ============================================================================
# QSS Template — generated from token dict
# ============================================================================

QSS_TEMPLATE = """
* {{
    font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
    font-size: 14px;
}}
QMainWindow, #centralWidget {{
    background-color: {bg};
}}
QFrame#card {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 12px;
}}
QFrame#cardHover:hover {{
    background-color: {surface_alt};
    border: 1px solid {accent_hover};
}}
QLabel#pageTitle {{
    font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
    font-size: 28px;
    font-weight: 600;
    color: {text_primary};
}}
QLabel#sectionTitle {{
    font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
    font-size: 20px;
    font-weight: 600;
    color: {text_primary};
}}
QLabel#subsection {{
    font-size: 16px;
    font-weight: 600;
    color: {text_primary};
}}
QLabel#secondary {{
    font-size: 14px;
    color: {text_secondary};
}}
QLabel#tertiary {{
    font-size: 12px;
    color: {text_tertiary};
}}
QPushButton {{
    background-color: {surface_alt};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 16px;
    color: {text_primary};
    font-weight: 500;
    min-height: 24px;
}}
QPushButton:hover {{
    background-color: {surface};
    border-color: {accent};
}}
QPushButton:pressed {{
    background-color: {surface_alt};
}}
QPushButton:disabled {{
    background-color: {bg};
    color: {text_tertiary};
    border-color: {border};
}}
QPushButton#primary {{
    background-color: {accent};
    color: #FFFFFF;
    border: none;
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background-color: {accent_hover};
}}
QPushButton#primary:pressed {{
    background-color: {accent};
}}
QPushButton#primary:disabled {{
    background-color: {border};
    color: {text_tertiary};
}}
QPushButton#danger {{
    background-color: {danger};
    color: #FFFFFF;
    border: none;
    font-weight: 600;
}}
QPushButton#danger:hover {{
    background-color: #EF4444;
}}
QPushButton#subtle {{
    background: transparent;
    border: none;
    color: {text_secondary};
}}
QPushButton#subtle:hover {{
    color: {text_primary};
    background-color: {surface_alt};
}}
QLineEdit {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 12px;
    color: {text_primary};
    font-size: 14px;
    min-height: 24px;
}}
QLineEdit:focus {{
    border: 1.5px solid {accent};
}}
QLineEdit:disabled {{
    background-color: {bg};
    color: {text_tertiary};
}}
QTextEdit {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px;
    color: {text_primary};
    font-size: 14px;
}}
QTextEdit:focus {{
    border: 1.5px solid {accent};
}}
QComboBox {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 12px;
    color: {text_primary};
    font-size: 14px;
    min-height: 24px;
}}
QComboBox:focus {{
    border: 1.5px solid {accent};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accent_subtle};
    selection-color: {text_primary};
    color: {text_primary};
    padding: 4px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {border};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {text_tertiary};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {border};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QSplitter::handle {{
    background-color: {border};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}
QProgressBar {{
    background-color: {surface_alt};
    border: none;
    border-radius: 4px;
    text-align: center;
    color: {text_primary};
    font-size: 12px;
    height: 8px;
}}
QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 4px;
}}
QTableView {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    color: {text_primary};
    font-size: 14px;
    gridline-color: {border};
    selection-background-color: {accent_subtle};
    selection-color: {text_primary};
}}
QTableView::item {{
    padding: 8px 12px;
}}
QTableView::item:hover {{
    background-color: {surface_alt};
}}
QHeaderView::section {{
    background-color: {surface};
    border: none;
    border-bottom: 1px solid {border};
    padding: 8px 12px;
    font-weight: 600;
    color: {text_secondary};
}}
QToolTip {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 6px;
    color: {text_primary};
    font-size: 13px;
    padding: 6px 10px;
}}
QMenu {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 8px 32px 8px 16px;
    border-radius: 4px;
    color: {text_primary};
}}
QMenu::item:selected {{
    background-color: {accent_subtle};
    color: {text_primary};
}}
QMenu::separator {{
    height: 1px;
    background-color: {border};
    margin: 4px 8px;
}}
QTabWidget::pane {{
    border: none;
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    border: none;
    padding: 8px 16px;
    color: {text_secondary};
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {accent};
    border-bottom: 2px solid {accent};
}}
QTabBar::tab:hover {{
    color: {text_primary};
}}
QListWidget {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    color: {text_primary};
    padding: 4px;
}}
QListWidget::item {{
    padding: 8px 12px;
    border-radius: 4px;
}}
QListWidget::item:selected {{
    background-color: {accent_subtle};
    color: {text_primary};
}}
QListWidget::item:hover {{
    background-color: {surface_alt};
}}
QGroupBox {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 12px;
    margin-top: 16px;
    padding: 20px 16px 16px;
    font-weight: 600;
    color: {text_primary};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: {text_primary};
}}
"""


@dataclass
class ThemeManager:
    """Central theme management — 6 themes, light/dark, QSS generation."""

    current_theme: str = "Ocean Blue"
    themes: dict[str, dict[str, str]] = field(default_factory=lambda: dict(THEME_DEFINITIONS))
    _qapp: Any = None
    _on_theme_changed: Any = None
    _setup_complete_path: Path = Path("data") / "setup_complete.json"

    @classmethod
    def load(cls) -> ThemeManager:
        path = Path("data") / "theme_prefs.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return cls(current_theme=data.get("theme", "Ocean Blue"))
            except Exception:
                pass
        return cls()

    def save(self):
        path = Path("data")
        path.mkdir(parents=True, exist_ok=True)
        (path / "theme_prefs.json").write_text(json.dumps({"theme": self.current_theme}))

    def get_tokens(self) -> dict[str, str]:
        return dict(self.themes.get(self.current_theme, self.themes["Ocean Blue"]))

    def generate_qss(self) -> str:
        tokens = self.get_tokens()
        is_dark = "Dark" in self.current_theme
        if is_dark:
            tokens["surface_elevated_1"] = "#1A1A1D"
            tokens["surface_elevated_2"] = "#222226"
        else:
            tokens["surface_elevated_1"] = "#FFFFFF"
            tokens["surface_elevated_2"] = "#FFFFFF"
        return QSS_TEMPLATE.format(**tokens)

    def apply(self, qapp: Any):
        """Full theme setup — QSS + qfluentwidgets theme (call once at startup)."""
        self._qapp = qapp
        self._apply_qss(qapp)
        self._apply_fluent_theme()
        self.save()
        if self._on_theme_changed:
            self._on_theme_changed(self.current_theme)

    def apply_theme(self):
        """Lightweight theme switch — no QSS re-application."""
        if self._qapp:
            self._apply_fluent_theme()
            self.save()
            if self._on_theme_changed:
                self._on_theme_changed(self.current_theme)

    def _apply_qss(self, qapp):
        qss = self.generate_qss()
        qapp.setStyleSheet(qss)

    def _apply_fluent_theme(self):
        from qfluentwidgets import setTheme, setThemeColor, Theme
        tokens = self.get_tokens()
        setTheme(Theme.DARK if self.is_dark() else Theme.LIGHT)
        try:
            setThemeColor(tokens["accent"])
        except Exception:
            pass

    def switch_theme(self, theme_name: str):
        if theme_name in self.themes and theme_name != self.current_theme:
            self.current_theme = theme_name
            self.apply_theme()

    def toggle_dark_mode(self):
        """Switch between light/dark pair."""
        for light, dark in THEME_PAIRS:
            if self.current_theme == light:
                self.switch_theme(dark)
                return
            if self.current_theme == dark:
                self.switch_theme(light)
                return

    def is_dark(self) -> bool:
        return "Dark" in self.current_theme

    def get_light_pair(self) -> str:
        for light, dark in THEME_PAIRS:
            if self.current_theme == dark:
                return light
            if self.current_theme == light:
                return light
        return "Ocean Blue"

    def set_on_theme_changed(self, callback):
        self._on_theme_changed = callback

    def set_setup_complete(self, complete: bool = True):
        self._setup_complete_path.parent.mkdir(parents=True, exist_ok=True)
        self._setup_complete_path.write_text(json.dumps({"complete": complete}))

    def is_setup_complete(self) -> bool:
        if self._setup_complete_path.exists():
            try:
                data = json.loads(self._setup_complete_path.read_text())
                return data.get("complete", False)
            except Exception:
                pass
        return False


# Singleton
theme_manager = ThemeManager.load()
