"""Plugins Manager — install, update, remove, enable/disable plugins."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QLineEdit, QProgressBar, QMessageBox, QCheckBox, QDialog, QTabWidget
)
from xeno.desktop.theme_manager import theme_manager

logger = logging.getLogger(__name__)


class PluginCard(QFrame):
    """Single plugin display card."""
    
    toggled_signal = Signal(str, bool)
    configure_signal = Signal(str)

    def __init__(self, plugin_data: dict, parent=None):
        super().__init__(parent)
        self.plugin_data = plugin_data
        self.name = plugin_data.get("name", "Unknown")
        self.enabled = plugin_data.get("enabled", False)
        
        self.setObjectName("card")
        self.setMinimumHeight(130)
        
        # Category color
        cat = plugin_data.get("category", "default").lower()
        colors = {
            "automation": "#10B981",
            "browser": "#F59E0B",
            "coding": "#3B82F6",
            "research": "#8B5CF6",
            "core": "#64748B",
            "resource": "#EC4899"
        }
        color = colors.get(cat, "#3B82F6")
        
        self.setStyleSheet(f"""
            #card {{
                background-color: transparent;
                border: 1px solid palette(mid);
                border-radius: 12px;
                border-left: 4px solid {color};
            }}
            #card:hover {{
                border-color: {color};
                background-color: {color}11;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        icon_map = {"automation": "⚡", "browser": "🌐", "coding": "💻", "research": "🔍",
                    "core": "🔧", "resource": "📦", "default": "🧩"}
        icon = icon_map.get(cat, icon_map["default"])
        nl = QLabel(f"{icon}  {self.name}")
        nl.setStyleSheet("font-size: 15px; font-weight: 600;")
        header.addWidget(nl)
        header.addStretch()

        self.toggle = QCheckBox("Enabled")
        self.toggle.setChecked(self.enabled)
        self.toggle.toggled.connect(self._on_toggle)
        header.addWidget(self.toggle)
        
        layout.addLayout(header)

        desc = plugin_data.get("description", "")
        dl = QLabel(desc[:120] + ("..." if len(desc) > 120 else ""))
        dl.setObjectName("secondary")
        dl.setWordWrap(True)
        layout.addWidget(dl)

        footer = QHBoxLayout()
        hooks = plugin_data.get("hooks", 0)
        tools = plugin_data.get("tools", 0)
        version = plugin_data.get("version", "0.1.0")
        
        stats = QLabel(f"v{version} • {hooks} hooks • {tools} tools")
        stats.setObjectName("tertiary")
        footer.addWidget(stats)
        
        footer.addStretch()
        
        self.conf_btn = QPushButton("Configure")
        self.conf_btn.setObjectName("subtle")
        self.conf_btn.clicked.connect(lambda: self.configure_signal.emit(self.name))
        footer.addWidget(self.conf_btn)
        
        layout.addLayout(footer)

    def _on_toggle(self, checked: bool):
        self.toggled_signal.emit(self.name, checked)


class PluginsPage(QWidget):
    """Plugin marketplace and management."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pluginsPage")
        self._plugins: list[dict] = []
        self._resize_timer = None
        self._setup_ui()
        self._scan_plugins()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Plugins")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        desc = QLabel("Extend Xeno with plugins — install, update, and manage")
        desc.setObjectName("secondary")
        layout.addWidget(desc)

        # Install section
        install_layout = QHBoxLayout()
        self._install_input = QLineEdit()
        self._install_input.setPlaceholderText("Enter plugin URL or path to install...")
        self._install_input.setFixedHeight(36)
        install_layout.addWidget(self._install_input)
        
        self._install_btn = QPushButton("Install Plugin")
        self._install_btn.setObjectName("primary")
        self._install_btn.setFixedHeight(36)
        install_layout.addWidget(self._install_btn)
        layout.addLayout(install_layout)

        # Tabs
        self._tabs = QTabWidget()
        
        self._installed_tab = QWidget()
        self._installed_layout = QVBoxLayout(self._installed_tab)
        
        self._marketplace_tab = QWidget()
        self._marketplace_layout = QVBoxLayout(self._marketplace_tab)
        
        self._tabs.addTab(self._installed_tab, "Installed")
        self._tabs.addTab(self._marketplace_tab, "Marketplace")
        layout.addWidget(self._tabs, 1)

        # Installed Tab Content
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search installed plugins...")
        self._search.setFixedHeight(36)
        self._search.setMaximumWidth(300)
        self._search.textChanged.connect(self._filter)
        toolbar.addWidget(self._search)

        toolbar.addStretch()

        self._refresh_btn = QPushButton("⟳ Refresh")
        self._refresh_btn.setObjectName("subtle")
        self._refresh_btn.setFixedHeight(32)
        self._refresh_btn.clicked.connect(self._scan_plugins)
        toolbar.addWidget(self._refresh_btn)

        self._installed_layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(12)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._container)
        self._installed_layout.addWidget(scroll, 1)
        
        # Marketplace Tab Content
        mpl = QLabel("Marketplace coming soon...")
        mpl.setObjectName("secondary")
        mpl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._marketplace_layout.addWidget(mpl)

    def _scan_plugins(self):
        self._plugins.clear()
        plugins_dir = Path("plugins")
        if plugins_dir.exists():
            for p in plugins_dir.iterdir():
                if p.is_dir():
                    manifest = p / "plugin.json"
                    info = {"name": p.name, "description": "", "version": "0.1.0", "enabled": True, "installed": True, "category": "default", "hooks": 0, "tools": 0}
                    if manifest.exists():
                        try:
                            data = json.loads(manifest.read_text())
                            info.update(data)
                            if "hooks" not in info:
                                info["hooks"] = len(info.get("hooks_list", []))
                            if "tools" not in info:
                                info["tools"] = len(info.get("tools_list", []))
                        except Exception as e:
                            logger.error(f"Error reading plugin manifest {manifest}: {e}")
                    self._plugins.append(info)

        if not self._plugins:
            self._plugins = [
                {"name": "Automation", "description": "System automation and task scheduling", "version": "1.0.0", "enabled": True, "installed": True, "category": "automation", "hooks": 2, "tools": 5},
                {"name": "Browser", "description": "Web browser control and data extraction", "version": "1.2.0", "enabled": True, "installed": True, "category": "browser", "hooks": 1, "tools": 3},
                {"name": "Coding", "description": "Code analysis, generation, and execution", "version": "2.0.0", "enabled": True, "installed": True, "category": "coding", "hooks": 3, "tools": 10},
                {"name": "Research", "description": "Web research with multiple search providers", "version": "1.1.0", "enabled": True, "installed": True, "category": "research", "hooks": 0, "tools": 2},
                {"name": "Computer Vision", "description": "Screen analysis, OCR, and image understanding", "version": "0.9.0", "enabled": False, "installed": True, "category": "core", "hooks": 1, "tools": 4},
            ]

        self._render()

    def _render(self, filter_text: str = ""):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        filtered = self._plugins
        if filter_text:
            filtered = [p for p in filtered if filter_text.lower() in p["name"].lower()]

        cols = max(1, self.width() // 320)
        display = filtered[:200]
        for idx, plugin in enumerate(display):
            card = PluginCard(plugin)
            card.toggled_signal.connect(self._on_plugin_toggled)
            card.configure_signal.connect(self._on_plugin_configure)
            self._grid.addWidget(card, idx // cols, idx % cols)

        if len(filtered) > 200:
            more = QLabel(f"… and {len(filtered) - 200} more plugins")
            more.setObjectName("tertiary")
            more.setAlignment(Qt.AlignmentFlag.AlignCenter)
            more.setStyleSheet("padding: 16px;")
            row = len(display) // cols + (1 if len(display) % cols else 0)
            self._grid.addWidget(more, row, 0, 1, cols)

    def _filter(self, text: str):
        self._render(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._resize_timer:
            self._resize_timer.stop()
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(lambda: self._render(self._search.text()))
        self._resize_timer.start(150)

    def _on_plugin_toggled(self, name: str, state: bool):
        manifest_path = Path("plugins") / name.lower() / "plugin.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text())
                data["enabled"] = state
                manifest_path.write_text(json.dumps(data, indent=2))
            except Exception as e:
                logger.error(f"Failed to update plugin state for {name}: {e}")
                
        for p in self._plugins:
            if p["name"] == name:
                p["enabled"] = state

    def _on_plugin_configure(self, name: str):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Configure {name}")
        dlg.resize(400, 300)
        ly = QVBoxLayout(dlg)
        ly.addWidget(QLabel(f"Settings for {name} will appear here."))
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        ly.addWidget(btn)
        dlg.exec()
