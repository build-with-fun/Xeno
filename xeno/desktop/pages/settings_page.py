"""Settings — centralized configuration with 6 themes, AI providers, TTS/STT, and more."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QListWidget, QListWidgetItem, QSplitter,
    QTabWidget, QLineEdit, QTextEdit, QComboBox,
    QCheckBox, QSpinBox, QGroupBox, QFormLayout,
    QSlider, QColorDialog, QMessageBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy,
)
from PySide6.QtGui import QFont, QColor

from xeno.desktop.theme_manager import theme_manager, THEME_PAIRS

logger = logging.getLogger(__name__)

import httpx

PROVIDER_META: dict[str, dict] = {
    "gemini":      {"label": "Google Gemini",     "color": "#4285F4",  "icon": "G"},
    "deepseek":    {"label": "DeepSeek",           "color": "#4F46E5",  "icon": "D"},
    "groq":        {"label": "Groq (GroqCloud)",   "color": "#F59E0B",  "icon": "Q"},
    "openai":      {"label": "OpenAI",             "color": "#10A37F",  "icon": "O"},
    "anthropic":   {"label": "Anthropic (Claude)", "color": "#D97706",  "icon": "A"},
    "qwen":        {"label": "Qwen (Alibaba)",     "color": "#8B5CF6",  "icon": "W"},
    "ollama":      {"label": "Ollama (Local)",     "color": "#22C55E",  "icon": "Ol"},
}

def _scan_env_keys() -> dict[str, list[str]]:
    """Mirror of setup.py _scan_env_keys — no dotenv dependency needed."""
    import re
    result: dict[str, list[str]] = {}
    patterns = {
        "gemini": [r"^GEMINI_API_KEY(?:_(\d+))?$", r"^GOOGLE_API_KEY(?:_(\d+))?$"],
        "deepseek": [r"^DEEPSEEK_API_KEY(?:_(\d+))?$"],
        "groq": [r"^GROQ_API_KEY(?:_(\d+))?$"],
        "openai": [r"^OPENAI_API_KEY(?:_(\d+))?$"],
        "anthropic": [r"^ANTHROPIC_API_KEY(?:_(\d+))?$"],
        "qwen": [r"^QWEN_API_KEY(?:_(\d+))?$"],
        "ollama": [r"^OLLAMA_BASE_URL$"],
    }
    for env_key, value in os.environ.items():
        for provider, regexes in patterns.items():
            for regex in regexes:
                if re.match(regex, env_key, re.IGNORECASE) and value.strip():
                    result.setdefault(provider, []).append(value.strip())
    for p in result:
        seen = set()
        result[p] = [k for k in result[p] if not (k in seen or seen.add(k))]
    # Also try loading .env
    try:
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                for provider, regexes in patterns.items():
                    for regex in regexes:
                        if re.match(regex, k, re.IGNORECASE) and v.strip():
                            result.setdefault(provider, []).append(v.strip())
    except Exception:
        pass
    return result


async def _fetch_ollama_models() -> list[dict[str, Any]]:
    """Fetch locally installed Ollama models."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                return [{
                    "id": m.get("name", "").replace(":latest", ""),
                    "name": m.get("name", "").replace(":latest", ""),
                    "provider": "ollama",
                    "context_window": m.get("details", {}).get("context_length", 0),
                } for m in data.get("models", []) if m.get("name")]
    except Exception:
        pass
    return []


async def _fetch_provider_models(provider_name: str, keys: list[str]) -> list[dict[str, Any]]:
    """Fetch models from a remote provider API."""
    models_urls = {
        "gemini":    "https://generativelanguage.googleapis.com/v1beta/models",
        "deepseek":  "https://api.deepseek.com/models",
        "groq":      "https://api.groq.com/openai/v1/models",
        "openai":    "https://api.openai.com/v1/models",
        "anthropic": "https://api.anthropic.com/v1/models",
        "qwen":      "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
    }
    base_url = models_urls.get(provider_name)
    if not base_url or not keys:
        return []
    for key in keys:
        for _ in range(2):
            try:
                if provider_name == "gemini":
                    url = f"{base_url}?key={key}"
                    headers = {}
                else:
                    url = base_url
                    headers = {"Authorization": f"Bearer {key}"}
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models = []
                    items = data.get("models", data.get("data", []))
                    for m in items:
                        mid = m.get("name", "").replace("models/", "")
                        if not mid:
                            continue
                        models.append({
                            "id": mid,
                            "name": m.get("displayName", m.get("id", mid)),
                            "provider": provider_name,
                            "context_window": m.get("inputTokenLimit", m.get("context_window", 0)),
                        })
                    if models:
                        return models
            except Exception:
                await asyncio.sleep(0.5)
    return []


def _load_current_config() -> dict:
    """Load the current setup.json config."""
    p = Path(__file__).parent.parent.parent.parent / "data" / "setup.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_config(data: dict):
    """Save to setup.json."""
    p = Path(__file__).parent.parent.parent.parent / "data" / "setup.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    current = _load_current_config()
    current.update(data)
    p.write_text(json.dumps(current, indent=2, default=str), encoding="utf-8")


class ThemeCard(QFrame):
    """Theme selection card with color preview."""

    clicked = Signal(str)

    def __init__(self, name: str, accent: str, is_dark: bool, active: bool = False, parent=None):
        super().__init__(parent)
        self._name = name
        self._active = active
        self.setObjectName("themeCard")
        self.setMinimumSize(160, 120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        border = f"2px solid {accent}" if active else "1px solid palette(mid)"
        self.setStyleSheet(f"""
            #themeCard {{
                background-color: transparent;
                border: {border};
                border-radius: 12px;
                padding: 12px;
            }}
            #themeCard:hover {{
                border: 2px solid {accent};
                background-color: rgba({int(accent[1:3],16)},{int(accent[3:5],16)},{int(accent[5:7],16)},0.08);
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        colors = QHBoxLayout()
        bg_color = "#0B0B0D" if is_dark else "#FAFAFA"
        for c in [accent, bg_color]:
            dot = QLabel()
            dot.setFixedSize(24, 24)
            dot.setStyleSheet(f"""
                background-color: {c};
                border-radius: 12px;
                border: 1px solid palette(mid);
            """)
            colors.addWidget(dot)
        colors.addStretch()
        layout.addLayout(colors)

        nl = QLabel(name)
        nl.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(nl)

        mode = "Dark" if is_dark else "Light"
        ml = QLabel(mode)
        ml.setObjectName("tertiary")
        layout.addWidget(ml)

    def mousePressEvent(self, event):
        self.clicked.emit(self._name)


class SettingsPage(QWidget):
    """Centralized settings for all Xeno configuration."""

    CATEGORIES = [
        "AI Providers", "Models", "API Keys", "TTS / STT",
        "Themes", "Memory", "Security", "Privacy",
        "Integrations", "Notifications", "Shortcuts",
        "Startup", "Updates", "Backup & Restore",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._setup_ui()
        self._build_content()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        nav = QWidget()
        nav.setMinimumWidth(200)
        nav.setMaximumWidth(260)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(12, 24, 12, 24)
        nav_layout.setSpacing(2)

        settings_title = QLabel("Settings")
        settings_title.setObjectName("subsection")
        nav_layout.addWidget(settings_title)
        nav_layout.addSpacing(12)

        self._nav_list = QListWidget()
        self._nav_list.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
                padding: 0;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 8px;
                font-weight: 500;
            }
            QListWidget::item:selected {
                background-color: rgba(59,130,246,0.12);
                color: #3B82F6;
            }
            QListWidget::item:hover {
                background-color: rgba(59,130,246,0.05);
            }
        """)
        for cat in self.CATEGORIES:
            self._nav_list.addItem(cat)
        self._nav_list.setFixedWidth(220)
        self._nav_list.currentRowChanged.connect(self._switch_category)
        nav_layout.addWidget(self._nav_list)
        nav_layout.addStretch()

        splitter.addWidget(nav)

        self._content_area = QScrollArea()
        self._content_area.setWidgetResizable(True)
        self._content_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(16)

        self._content_area.setWidget(self._content_widget)
        splitter.addWidget(self._content_area)

        layout.addWidget(splitter)

    def _switch_category(self, row: int):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._build_content(row)

    def _build_content(self, category_idx: int = 0):
        cat = self.CATEGORIES[category_idx]
        title = QLabel(cat)
        title.setObjectName("pageTitle")
        self._content_layout.addWidget(title)

        builders = {
            "AI Providers": self._build_ai_providers,
            "Models": self._build_models,
            "API Keys": self._build_api_keys,
            "TTS / STT": self._build_tts_stt,
            "Themes": self._build_themes,
            "Memory": self._build_memory_settings,
            "Security": self._build_security,
            "Privacy": self._build_privacy,
            "Integrations": self._build_integrations,
            "Notifications": self._build_notifications,
            "Shortcuts": self._build_shortcuts,
            "Startup": self._build_startup,
            "Updates": self._build_updates,
            "Backup & Restore": self._build_backup,
        }

        builder = builders.get(cat)
        if builder:
            builder()

        self._content_layout.addStretch()

    def _build_ai_providers(self):
        info = QLabel("Auto-detected providers from .env + your local Ollama installation.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        self._provider_status = QLabel("Scanning environment...")
        self._provider_status.setObjectName("tertiary")
        self._content_layout.addWidget(self._provider_status)

        self._provider_cards: dict[str, QFrame] = {}

        env_keys = _scan_env_keys()
        config = _load_current_config()

        for pname, meta in PROVIDER_META.items():
            keys = env_keys.get(pname, [])
            is_ollama = pname == "ollama"
            has_keys = bool(keys) or is_ollama

            card = QFrame()
            card.setObjectName("providerCard")
            card.setStyleSheet(f"""
                #providerCard {{
                    background-color: transparent;
                    border: 1px solid palette(mid);
                    border-radius: 12px;
                    padding: 16px;
                }}
                #providerCard:hover {{
                    border-color: {meta['color']};
                }}
            """)
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            cl.setSpacing(12)

            icon_lbl = QLabel(meta["icon"])
            icon_lbl.setStyleSheet(f"""
                background-color: {meta['color']}; color: white;
                font-weight: bold; font-size: 13px;
                border-radius: 14px; padding: 4px 8px;
                min-width: 28px; min-height: 28px;
            """)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(icon_lbl)

            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)
            nl = QLabel(meta["label"])
            nl.setStyleSheet("font-weight: 600; font-size: 14px;")
            info_layout.addWidget(nl)

            if is_ollama:
                dl = QLabel("Checking for local Ollama installation...")
            elif has_keys:
                dl = QLabel(f"{len(keys)} API key{'s' if len(keys) != 1 else ''} detected")
            else:
                dl = QLabel("No API key found in .env")
            dl.setObjectName("tertiary")
            info_layout.addWidget(dl)
            cl.addLayout(info_layout, 1)

            toggle = QCheckBox()
            toggle.setChecked(has_keys)
            toggle.setEnabled(has_keys)
            cl.addWidget(toggle)

            self._content_layout.addWidget(card)
            self._provider_cards[pname] = card

            # Async check for Ollama
            if is_ollama:
                self._check_ollama_status(card, dl)

        scan_btn = QPushButton("Rescan .env Keys")
        scan_btn.setObjectName("primary")
        scan_btn.setFixedWidth(180)
        scan_btn.setFixedHeight(36)
        scan_btn.clicked.connect(lambda: self._rescan_providers())
        self._content_layout.addWidget(scan_btn)

        self._provider_status.setText(
            f"Detected {sum(1 for p in PROVIDER_META if env_keys.get(p) or p == 'ollama')}/{len(PROVIDER_META)} providers with keys"
        )

    def _check_ollama_status(self, card: QFrame, label: QLabel):
        def check():
            import httpx
            try:
                r = httpx.get("http://localhost:11434/api/tags", timeout=3)
                if r.status_code == 200:
                    models = r.json().get("models", [])
                    QTimer.singleShot(0, lambda: label.setText(f"Running — {len(models)} model{'s' if len(models) != 1 else ''} installed"))
                    QTimer.singleShot(0, lambda: card.setStyleSheet(card.styleSheet().replace("palette(mid)", "#22C55E")))
                else:
                    QTimer.singleShot(0, lambda: label.setText("Not reachable"))
            except Exception:
                QTimer.singleShot(0, lambda: label.setText("Ollama not running (start with 'ollama serve')"))

        threading.Thread(target=check, daemon=True).start()

    def _rescan_providers(self):
        self._provider_status.setText("Rescanning...")
        env_keys = _scan_env_keys()
        for pname, meta in PROVIDER_META.items():
            card = self._provider_cards.get(pname)
            if not card:
                continue
            cl = card.layout()
            if cl:
                info_layout = cl.itemAt(1)
                if info_layout and info_layout.layout():
                    dl = info_layout.layout().itemAt(1)
                    if dl and dl.widget():
                        is_ollama = pname == "ollama"
                        keys = env_keys.get(pname, [])
                        if is_ollama:
                            dl.widget().setText("Checking...")
                            self._check_ollama_status(card, dl.widget())
                        elif keys:
                            dl.widget().setText(f"{len(keys)} API key{'s' if len(keys) != 1 else ''} detected")
                        else:
                            dl.widget().setText("No API key found in .env")
        count = sum(1 for p in PROVIDER_META if env_keys.get(p) or p == "ollama")
        self._provider_status.setText(f"Detected {count}/{len(PROVIDER_META)} providers with keys")

    def _build_models(self):
        info = QLabel("Fetching available models from all detected providers...")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        self._models_loading = QProgressBar()
        self._models_loading.setRange(0, 0)
        self._models_loading.setFixedHeight(6)
        self._models_loading.setTextVisible(False)
        self._content_layout.addWidget(self._models_loading)
        self._models_loading.hide()

        self._models_table = QTableWidget()
        self._models_table.setColumnCount(4)
        self._models_table.setHorizontalHeaderLabels(["Provider", "Model ID", "Name", "Context"])
        self._models_table.horizontalHeader().setStretchLastSection(True)
        self._models_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._models_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._models_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._models_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._models_table.setAlternatingRowColors(True)
        self._models_table.setMinimumHeight(200)
        self._models_table.setStyleSheet("""
            QTableWidget { border: 1px solid palette(mid); border-radius: 8px; background: transparent; }
            QHeaderView::section { background: transparent; padding: 8px; font-weight: 600; border: none; }
        """)
        self._content_layout.addWidget(self._models_table)

        model_roles = [
            ("Main Model", "model"),
            ("Small / Fast Model", "small_model"),
            ("Vision Model", "vision_model"),
            ("Reasoning Model", "reasoning_model"),
            ("Coding Model", "coding_model"),
        ]
        self._model_combos: dict[str, QComboBox] = {}
        roles_container = QFrame()
        roles_container.setObjectName("card")
        roles_container.setStyleSheet("""
            #card { background-color: transparent; border: 1px solid palette(mid); border-radius: 12px; padding: 16px; margin-top: 8px; }
        """)
        roles_layout = QHBoxLayout(roles_container)
        roles_layout.setSpacing(16)
        config = _load_current_config()
        for label, key in model_roles:
            col = QVBoxLayout()
            col.setSpacing(4)
            lbl = QLabel(label)
            lbl.setStyleSheet("font-weight: 600; font-size: 12px;")
            col.addWidget(lbl)
            combo = QComboBox()
            combo.setMinimumWidth(220)
            combo.setEditable(True)
            current_val = config.get(key, config.get("model", ""))
            if current_val:
                combo.setCurrentText(current_val)
            col.addWidget(combo)
            roles_layout.addLayout(col)
            self._model_combos[key] = combo

        self._content_layout.addWidget(roles_container)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        refresh_btn = QPushButton("⟳ Refresh Models")
        refresh_btn.setObjectName("primary")
        refresh_btn.setFixedHeight(36)
        refresh_btn.clicked.connect(self._fetch_models_background)
        btn_row.addWidget(refresh_btn)

        save_btn = QPushButton("Save Model Config")
        save_btn.setObjectName("primary")
        save_btn.setFixedHeight(36)
        save_btn.clicked.connect(self._save_model_config)
        btn_row.addWidget(save_btn)

        btn_row.addStretch()
        self._content_layout.addLayout(btn_row)

        self._model_list: list[dict[str, Any]] = []
        QTimer.singleShot(100, self._fetch_models_background)

    def _fetch_models_background(self):
        self._models_loading.show()
        self._models_table.setRowCount(0)
        self._model_list.clear()
        t = threading.Thread(target=self._fetch_models_sync, daemon=True)
        t.start()

    def _fetch_models_sync(self):
        env_keys = _scan_env_keys()
        all_models: list[dict[str, Any]] = []

        async def gather():
            tasks = []
            for pname in PROVIDER_META:
                if pname == "ollama":
                    tasks.append(_fetch_ollama_models())
                elif pname in env_keys and env_keys[pname]:
                    tasks.append(_fetch_provider_models(pname, env_keys[pname]))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    all_models.extend(r)

        try:
            asyncio.run(gather())
        except Exception as e:
            logger.warning(f"Model fetch error: {e}")

        if not all_models:
            all_models = [
                {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "provider": "gemini", "context_window": 1048576},
                {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "provider": "gemini", "context_window": 1048576},
                {"id": "deepseek-chat", "name": "DeepSeek Chat", "provider": "deepseek", "context_window": 65536},
                {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner", "provider": "deepseek", "context_window": 65536},
                {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai", "context_window": 128000},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai", "context_window": 128000},
                {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "anthropic", "context_window": 200000},
                {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "provider": "groq", "context_window": 128000},
                {"id": "qwen-plus", "name": "Qwen Plus", "provider": "qwen", "context_window": 131072},
                {"id": "llama3.2", "name": "Llama 3.2", "provider": "ollama", "context_window": 128000},
                {"id": "mistral", "name": "Mistral", "provider": "ollama", "context_window": 32768},
                {"id": "qwen2.5", "name": "Qwen 2.5", "provider": "ollama", "context_window": 32768},
                {"id": "deepseek-r1", "name": "DeepSeek R1", "provider": "ollama", "context_window": 65536},
                {"id": "phi4", "name": "Phi-4", "provider": "ollama", "context_window": 128000},
            ]

        self._model_list = all_models
        QTimer.singleShot(0, self._populate_models_table)

    def _populate_models_table(self):
        self._models_table.setRowCount(len(self._model_list))
        self._models_loading.hide()
        for i, m in enumerate(self._model_list):
            prov = m.get("provider", "?")
            meta = PROVIDER_META.get(prov, {})
            prov_item = QTableWidgetItem(f" {meta.get('icon', prov)}  {meta.get('label', prov)}")
            prov_item.setForeground(QColor(meta.get("color", "#888")))
            self._models_table.setItem(i, 0, prov_item)
            self._models_table.setItem(i, 1, QTableWidgetItem(m["id"]))
            self._models_table.setItem(i, 2, QTableWidgetItem(m.get("name", m["id"])))
            ctx = m.get("context_window", 0)
            self._models_table.setItem(i, 3, QTableWidgetItem(f"{ctx:,}" if ctx else "-"))
        self._models_table.resizeColumnsToContents()

        # Populate combos with all models
        for combo in self._model_combos.values():
            current = combo.currentText()
            block = combo.blockSignals(True)
            combo.clear()
            for m in self._model_list:
                model_str = f"{m['provider']}:{m['id']}"
                combo.addItem(f"{model_str}  ({m.get('name', '')})", model_str)
            combo.setEditable(True)
            combo.setCurrentText(current)
            combo.blockSignals(block)

    def _save_model_config(self):
        data = {}
        for key, combo in self._model_combos.items():
            text = combo.currentText().strip()
            if ":" in text and not text.startswith(":"):
                data[key] = text
        _save_config(data)
        QMessageBox.information(self, "Saved", "Model configuration saved to data/setup.json")

    def _build_api_keys(self):
        info = QLabel("API keys detected from your .env file. Manage them per provider.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        env_keys = _scan_env_keys()
        for pname, meta in PROVIDER_META.items():
            keys = env_keys.get(pname, [])
            card = QFrame()
            card.setObjectName("keyCard")
            card.setStyleSheet(f"""
                #keyCard {{ background-color: transparent; border: 1px solid palette(mid); border-radius: 12px; padding: 12px; }}
                #keyCard:hover {{ border-color: {meta['color']}; }}
            """)
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 10, 16, 10)

            icon_lbl = QLabel(meta["icon"])
            icon_lbl.setStyleSheet(f"""
                background-color: {meta['color']}; color: white;
                font-weight: bold; font-size: 11px;
                border-radius: 12px; padding: 2px 6px;
                min-width: 24px; min-height: 24px;
            """)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(icon_lbl)

            nl = QLabel(meta["label"])
            nl.setStyleSheet("font-weight: 600; min-width: 130px;")
            cl.addWidget(nl)

            if keys:
                for key in keys:
                    masked = key[:8] + "..." + key[-4:] if len(key) > 16 else key[:6] + "..."
                    key_input = QLineEdit(masked)
                    key_input.setReadOnly(True)
                    key_input.setStyleSheet("color: palette(text); background: transparent; border: none; font-family: monospace;")
                    cl.addWidget(key_input, 1)
            else:
                placeholder = QLabel("No key detected in .env" if pname != "ollama" else "Local — no key needed")
                placeholder.setObjectName("tertiary")
                cl.addWidget(placeholder, 1)

            self._content_layout.addWidget(card)

        help_text = QLabel("Add keys to your .env file: DEEPSEEK_API_KEY=sk-... or GEMINI_API_KEY=AIza...")
        help_text.setObjectName("tertiary")
        help_text.setWordWrap(True)
        self._content_layout.addWidget(help_text)

    def _toggle_key_visibility(self, field: QLineEdit):
        if field.echoMode() == QLineEdit.EchoMode.Password:
            field.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            field.setEchoMode(QLineEdit.EchoMode.Password)

    def _build_tts_stt(self):
        info = QLabel("Configure Text-to-Speech and Speech-to-Text settings.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        config = _load_current_config()
        form = QFormLayout()
        form.setSpacing(12)

        # ── TTS Provider ──
        tts_provider = QComboBox()
        tts_provider.addItems(["Gemini TTS", "Edge TTS", "System TTS", "Eleven Labs", "OpenAI TTS"])
        tts_provider.setCurrentText(config.get("tts_provider", "Gemini TTS"))
        form.addRow("TTS Provider:", tts_provider)

        # ── Gemini TTS Model (actual API model IDs) ──
        tts_model = QComboBox()
        tts_model.setEditable(True)
        gemini_tts_models = [
            "gemini-3.1-flash-tts-preview",
            "gemini-2.5-flash-tts",
            "gemini-2.5-pro-tts",
            "gemini-2.5-flash-lite-preview-tts",
            "gemini-2.0-flash-tts",
        ]
        tts_model.addItems(gemini_tts_models)
        tts_model.setCurrentText(config.get("tts_model", "gemini-3.1-flash-tts-preview"))
        form.addRow("Gemini TTS Model:", tts_model)

        # ── Prebuilt Voice (official Gemini TTS voices) ──
        tts_voice = QComboBox()
        tts_voice.addItems(["Aoede", "Charon", "Fenrir", "Kore", "Puck", "Eireann"])
        tts_voice.setCurrentText(config.get("tts_voice", "Aoede"))
        form.addRow("Voice:", tts_voice)

        speed = QSlider(Qt.Orientation.Horizontal)
        speed.setRange(50, 200)
        speed.setValue(config.get("tts_speed", 100))
        form.addRow("Speed:", speed)

        pitch = QSlider(Qt.Orientation.Horizontal)
        pitch.setRange(50, 200)
        pitch.setValue(config.get("tts_pitch", 100))
        form.addRow("Pitch:", pitch)

        # ── STT ──
        stt_provider = QComboBox()
        stt_provider.addItems(["Whisper (Local)", "Gemini STT", "Deepgram", "Azure STT"])
        stt_provider.setCurrentText(config.get("stt_provider", "Whisper (Local)"))
        form.addRow("STT Provider:", stt_provider)

        wake_word = QLineEdit(config.get("wake_word", "Hey Xeno"))
        form.addRow("Wake Word:", wake_word)

        streaming = QCheckBox("Enable streaming TTS")
        streaming.setChecked(config.get("streaming_tts", True))
        form.addRow("", streaming)

        interrupt = QCheckBox("Enable interruptible speech (barge-in)")
        interrupt.setChecked(config.get("interrupt_speech", True))
        form.addRow("", interrupt)

        self._content_layout.addLayout(form)

        # ── Save button ──
        save = QPushButton("Save Speech Config")
        save.setObjectName("primary")
        save.setFixedWidth(200)

        def _do_save():
            data = {
                "tts_provider": tts_provider.currentText(),
                "tts_model": tts_model.currentText(),
                "tts_voice": tts_voice.currentText(),
                "tts_speed": speed.value(),
                "tts_pitch": pitch.value(),
                "stt_provider": stt_provider.currentText(),
                "wake_word": wake_word.text(),
                "streaming_tts": streaming.isChecked(),
                "interrupt_speech": interrupt.isChecked(),
            }
            _save_config(data)
            QMessageBox.information(self, "Saved", "Speech configuration saved to setup.json")

        save.clicked.connect(_do_save)
        self._content_layout.addWidget(save)

    def _build_themes(self):
        info = QLabel("Choose from 6 professionally designed themes with light/dark variants.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        themes_grid = QGridLayout()
        themes_grid.setSpacing(12)

        current = theme_manager.current_theme
        col = 0
        for light_name, dark_name in THEME_PAIRS:
            light_tokens = theme_manager.themes.get(light_name, {})
            dark_tokens = theme_manager.themes.get(dark_name, {})

            light_card = ThemeCard(
                light_name, light_tokens.get("accent", "#3B82F6"),
                False, active=(current == light_name)
            )
            light_card.clicked.connect(lambda n: self._apply_theme(n))
            themes_grid.addWidget(light_card, 0, col)

            dark_card = ThemeCard(
                dark_name, dark_tokens.get("accent", "#3B82F6"),
                True, active=(current == dark_name)
            )
            dark_card.clicked.connect(lambda n: self._apply_theme(n))
            themes_grid.addWidget(dark_card, 1, col)
            col += 1

        self._content_layout.addLayout(themes_grid)

        current_label = QLabel(f"Current theme: {current}")
        current_label.setObjectName("secondary")
        self._content_layout.addWidget(current_label)

    def _apply_theme(self, name: str):
        theme_manager.switch_theme(name)
        for btn in self.findChildren(ThemeCard):
            btn._active = (btn._name == name)
        QMessageBox.information(self, "Theme Applied", f"Theme changed to: {name}")

    def _build_memory_settings(self):
        info = QLabel("Configure memory tiers, retention, and storage.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(10)

        max_context = QSpinBox()
        max_context.setRange(10, 500)
        max_context.setValue(50)
        form.addRow("Max Context Messages:", max_context)

        retention = QSpinBox()
        retention.setRange(1, 365)
        retention.setValue(30)
        form.addRow("Retention (days):", retention)

        vector_enabled = QCheckBox("Enable vector memory (ChromaDB)")
        vector_enabled.setChecked(True)
        form.addRow("", vector_enabled)

        episodic_enabled = QCheckBox("Enable episodic memory")
        episodic_enabled.setChecked(True)
        form.addRow("", episodic_enabled)

        temporal_enabled = QCheckBox("Enable temporal knowledge graph")
        temporal_enabled.setChecked(True)
        form.addRow("", temporal_enabled)

        self._content_layout.addLayout(form)

        clear_btn = QPushButton("Clear All Memory Data")
        clear_btn.setObjectName("danger")
        clear_btn.setFixedWidth(200)
        clear_btn.clicked.connect(lambda: QMessageBox.warning(self, "Clear Memory", "This will delete all memory data!"))
        self._content_layout.addWidget(clear_btn)

    def _build_security(self):
        info = QLabel("Security settings and access control.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        form = QFormLayout()
        enable_gateway = QCheckBox("Enable security gateway")
        enable_gateway.setChecked(True)
        form.addRow("", enable_gateway)

        audit = QCheckBox("Enable audit logging")
        audit.setChecked(True)
        form.addRow("", audit)

        sandbox = QCheckBox("Enable sandbox execution")
        sandbox.setChecked(True)
        form.addRow("", sandbox)

        max_retries = QSpinBox()
        max_retries.setRange(1, 10)
        max_retries.setValue(3)
        form.addRow("Max retries:", max_retries)

        self._content_layout.addLayout(form)

    def _build_privacy(self):
        info = QLabel("Privacy controls and data management.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        form = QFormLayout()
        analytics = QCheckBox("Share anonymous usage data")
        analytics.setChecked(False)
        form.addRow("", analytics)

        logs = QCheckBox("Keep local logs")
        logs.setChecked(True)
        form.addRow("", logs)

        self._content_layout.addLayout(form)

        export = QPushButton("Export All Data")
        export.setObjectName("subtle")
        export.setFixedWidth(200)
        self._content_layout.addWidget(export)

    def _build_integrations(self):
        info = QLabel("Connect Xeno with external services.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        integrations = [
            ("WhatsApp", True, "WhatsApp automation bot"),
            ("Gmail", True, "Email management"),
            ("Google Calendar", False, "Calendar integration"),
            ("Slack", False, "Slack messaging"),
            ("Discord", False, "Discord bot"),
            ("GitHub", True, "Repository management"),
            ("Notion", False, "Notion workspace"),
            ("Jira", False, "Project tracking"),
        ]

        for name, enabled, desc in integrations:
            card = QFrame()
            card.setObjectName("card")
            card.setStyleSheet("""
                #card { background-color: transparent; border: 1px solid palette(mid); border-radius: 12px; padding: 12px; }
                #card:hover { border-color: #3B82F6; }
            """)
            cl = QHBoxLayout(card)
            cl.setContentsMargins(16, 10, 16, 10)
            nl = QLabel(f"{'●' if enabled else '○'}  {name}")
            nl.setStyleSheet(f"font-weight: 600; color: {'#22C55E' if enabled else '#A1A1AA'};")
            cl.addWidget(nl)
            dl = QLabel(desc)
            dl.setObjectName("secondary")
            cl.addWidget(dl, 1)
            toggle = QCheckBox()
            toggle.setChecked(enabled)
            cl.addWidget(toggle)
            self._content_layout.addWidget(card)

    def _build_notifications(self):
        info = QLabel("Configure notification preferences.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        form = QFormLayout()
        os_notify = QCheckBox("OS toast notifications")
        os_notify.setChecked(True)
        form.addRow("", os_notify)

        sound = QCheckBox("Notification sounds")
        sound.setChecked(True)
        form.addRow("", sound)

        tray = QCheckBox("Minimize to system tray")
        tray.setChecked(True)
        form.addRow("", tray)

        self._content_layout.addLayout(form)

    def _build_shortcuts(self):
        info = QLabel("Keyboard shortcuts for power users.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        shortcuts = [
            ("Command Palette", "Ctrl+Shift+P"),
            ("Toggle Voice Mode", "Ctrl+M"),
            ("New Chat", "Ctrl+N"),
            ("Search", "Ctrl+F"),
            ("Settings", "Ctrl+,"),
            ("Interrupt AI", "Escape"),
            ("Full Screen", "F11"),
            ("Quick Search", "Ctrl+K"),
        ]

        for action, shortcut in shortcuts:
            card = QFrame()
            card.setObjectName("card")
            card.setStyleSheet("""
                #card { background-color: transparent; border: 1px solid palette(mid); border-radius: 8px; padding: 8px; }
            """)
            cl = QHBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)
            al = QLabel(action)
            al.setStyleSheet("font-weight: 500;")
            cl.addWidget(al, 1)
            sl = QLabel(shortcut)
            sl.setStyleSheet("""
                background-color: palette(window); border: 1px solid palette(mid);
                border-radius: 4px; padding: 2px 8px;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
            """)
            cl.addWidget(sl)
            self._content_layout.addWidget(card)

    def _build_startup(self):
        info = QLabel("Configure application startup behavior.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        form = QFormLayout()
        auto_start = QCheckBox("Launch on system startup")
        auto_start.setChecked(False)
        form.addRow("", auto_start)

        minimize = QCheckBox("Start minimized to tray")
        minimize.setChecked(True)
        form.addRow("", minimize)

        auto_connect = QCheckBox("Auto-connect AI on startup")
        auto_connect.setChecked(True)
        form.addRow("", auto_connect)

        self._content_layout.addLayout(form)

    def _build_updates(self):
        info = QLabel("Software update preferences.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        form = QFormLayout()
        auto_update = QCheckBox("Automatically check for updates")
        auto_update.setChecked(True)
        form.addRow("", auto_update)

        channel = QComboBox()
        channel.addItems(["Stable", "Beta", "Nightly"])
        form.addRow("Update channel:", channel)

        self._content_layout.addLayout(form)

        check_btn = QPushButton("Check for Updates Now")
        check_btn.setObjectName("primary")
        check_btn.setFixedWidth(200)
        self._content_layout.addWidget(check_btn)

    def _build_backup(self):
        info = QLabel("Backup and restore your configuration and data.")
        info.setObjectName("secondary")
        self._content_layout.addWidget(info)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        backup = QPushButton("📤 Create Backup")
        backup.setObjectName("primary")
        backup.setFixedHeight(40)
        backup.setFixedWidth(200)
        btn_layout.addWidget(backup)

        restore = QPushButton("📥 Restore from Backup")
        restore.setObjectName("subtle")
        restore.setFixedHeight(40)
        restore.setFixedWidth(200)
        btn_layout.addWidget(restore)

        btn_layout.addStretch()
        self._content_layout.addLayout(btn_layout)
