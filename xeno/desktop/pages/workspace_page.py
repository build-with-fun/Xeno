"""Workspace — view generated content, code, images, documents, notes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QFrame,
    QScrollArea, QListWidget, QListWidgetItem, QSplitter,
    QTabWidget, QFileDialog, QMessageBox
)
from PySide6.QtGui import QIcon

from xeno.desktop.theme_manager import theme_manager


class WorkspaceItem(QFrame):
    """A single workspace item (file, code, image, note)."""

    def __init__(self, name: str, type_: str, path: str, size: str = "", modified: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._path = path
        self.setMinimumHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            #card {
                background-color: transparent;
                border: 1px solid palette(mid);
                border-radius: 12px;
                padding: 12px;
            }
            #card:hover {
                background-color: rgba(59,130,246,0.05);
                border-color: #3B82F6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        icons = {"code": "📄", "image": "🖼", "doc": "📝", "note": "📌", "audio": "🎵", "video": "🎬", "data": "📊", "other": "📁"}
        icon = icons.get(type_, "📁")
        
        top_layout = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        top_layout.addWidget(icon_label)
        top_layout.addWidget(name_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        tl = QLabel(f"Type: {type_.title()}  |  {size}")
        tl.setObjectName("tertiary")
        layout.addWidget(tl)

        if modified:
            ml = QLabel(f"Modified: {modified}")
            ml.setObjectName("tertiary")
            layout.addWidget(ml)

    def mousePressEvent(self, event):
        if self._path:
            path = Path(self._path)
            if path.suffix.lower() in [".txt", ".py", ".md", ".json", ".js", ".html", ".css", ".csv", ".xml", ".yaml", ".log"]:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read(1000)
                    msg = QMessageBox(self)
                    msg.setWindowTitle(f"Preview: {path.name}")
                    msg.setText(content + ("\n..." if len(content) == 1000 else ""))
                    msg.exec()
                except Exception:
                    pass
            else:
                try:
                    import subprocess
                    subprocess.Popen(["explorer", "/select,", self._path])
                except Exception:
                    pass


class WorkspacePage(QWidget):
    """Central workspace for all AI-generated content."""

    CATEGORIES = ["All", "Code", "Images", "Documents", "Notes", "Audio", "Data"]
    MAX_VISIBLE_ITEMS = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workspacePage")
        self._is_grid_view = True
        self.setAcceptDrops(True)
        self._resize_timer = None
        self._setup_ui()
        self._scan_workspace()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Workspace")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        desc = QLabel("Files, code, images, and documents created by AI")
        desc.setObjectName("secondary")
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search workspace...")
        self._search.setFixedHeight(36)
        self._search.setMaximumWidth(300)
        self._search.textChanged.connect(self._filter_items)
        toolbar.addWidget(self._search)

        toolbar.addStretch()

        self._view_btn = QPushButton("List View")
        self._view_btn.setObjectName("subtle")
        self._view_btn.setFixedHeight(32)
        self._view_btn.clicked.connect(self._toggle_view)
        toolbar.addWidget(self._view_btn)
        
        self._explorer_btn = QPushButton("📂 Open Folder")
        self._explorer_btn.setObjectName("subtle")
        self._explorer_btn.setFixedHeight(32)
        self._explorer_btn.clicked.connect(self._open_explorer)
        toolbar.addWidget(self._explorer_btn)

        self._refresh_btn = QPushButton("⟳ Refresh")
        self._refresh_btn.setObjectName("subtle")
        self._refresh_btn.setFixedHeight(32)
        self._refresh_btn.clicked.connect(self._scan_workspace)
        toolbar.addWidget(self._refresh_btn)

        layout.addLayout(toolbar)

        self._all_items: list[dict] = []
        self._grid_layouts: dict[str, QGridLayout] = {}

        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane { border: none; background: transparent; }
            QTabBar::tab { padding: 8px 16px; font-weight: 500; }
        """)

        for cat in self.CATEGORIES:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 12, 0, 0)
            page_layout.setSpacing(0)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

            container = QWidget()
            container.setStyleSheet("background: transparent;")
            grid = QGridLayout(container)
            grid.setSpacing(12)
            grid.setAlignment(Qt.AlignmentFlag.AlignTop)
            self._grid_layouts[cat] = grid

            scroll.setWidget(container)
            page_layout.addWidget(scroll)
            self._tab_widget.addTab(page, cat)

        layout.addWidget(self._tab_widget)

    def _toggle_view(self):
        self._is_grid_view = not self._is_grid_view
        self._view_btn.setText("List View" if self._is_grid_view else "Grid View")
        self._render_items(self._search.text())
        
    def _open_explorer(self):
        try:
            import subprocess
            workspace_dir = Path("workspace").absolute()
            workspace_dir.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["explorer", str(workspace_dir)])
        except Exception:
            pass

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        workspace_dir = Path("workspace")
        workspace_dir.mkdir(parents=True, exist_ok=True)
        for url in urls:
            path = url.toLocalFile()
            if path and Path(path).is_file():
                shutil.copy2(path, workspace_dir / Path(path).name)
        self._scan_workspace()

    def _scan_workspace(self):
        self._all_items.clear()
        workspace_dir = Path("workspace")
        if not workspace_dir.exists():
            workspace_dir.mkdir(parents=True, exist_ok=True)
            return

        type_map = {
            ".py": "code", ".js": "code", ".ts": "code", ".html": "code", ".css": "code",
            ".json": "data", ".xml": "data", ".yaml": "data", ".csv": "data",
            ".md": "doc", ".txt": "note", ".pdf": "doc", ".docx": "doc",
            ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".svg": "image",
            ".mp3": "audio", ".wav": "audio", ".flac": "audio",
            ".mp4": "video", ".webm": "video",
            ".zip": "other", ".rar": "other",
        }

        for f in workspace_dir.rglob("*"):
            if len(self._all_items) >= 10000:
                break
            if f.is_file() and not f.name.startswith("."):
                type_ = type_map.get(f.suffix.lower(), "other")
                size = f.stat().st_size
                size_str = f"{size / 1024:.0f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB"
                modified = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                self._all_items.append({
                    "name": f.name, "type": type_, "path": str(f),
                    "size": size_str, "modified": modified,
                })

        self._render_items()

    def _render_items(self, filter_text: str = ""):
        for layout in self._grid_layouts.values():
            while layout.count():
                item = layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()

        filtered = self._all_items
        if filter_text:
            filtered = [i for i in filtered if filter_text.lower() in i["name"].lower()]

        cat_map = {"Code": "code", "Images": "image", "Documents": "doc", "Notes": "note", "Audio": "audio", "Data": "data"}

        for i, cat in enumerate(self.CATEGORIES):
            grid = self._grid_layouts.get(cat, QGridLayout())
            cat_type = cat_map.get(cat, cat.lower())
            
            cat_items = filtered
            if cat != "All":
                cat_items = [item for item in filtered if item["type"] == cat_type]

            total = len(cat_items)
            self._tab_widget.setTabText(i, f"{cat} ({total})")

            display = cat_items[:self.MAX_VISIBLE_ITEMS]
            cols = max(1, self.width() // 250) if self._is_grid_view else 1
            for idx, item in enumerate(display):
                wi = WorkspaceItem(
                    item["name"], item["type"], item["path"],
                    item["size"], item["modified"]
                )
                grid.addWidget(wi, idx // cols, idx % cols)

            if total > self.MAX_VISIBLE_ITEMS:
                remaining = total - self.MAX_VISIBLE_ITEMS
                more = QLabel(f"… and {remaining} more files")
                more.setObjectName("tertiary")
                more.setAlignment(Qt.AlignmentFlag.AlignCenter)
                more.setStyleSheet("padding: 16px;")
                row = len(display) // cols + (1 if len(display) % cols else 0)
                grid.addWidget(more, row, 0, 1, cols)

    def _filter_items(self, text: str):
        if self._resize_timer:
            self._resize_timer.stop()
        self._render_items(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._resize_timer:
            self._resize_timer.stop()
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(lambda: self._render_items(self._search.text()))
        self._resize_timer.start(150)
