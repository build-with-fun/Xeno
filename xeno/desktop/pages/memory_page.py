"""Memory Center — unified memory management with CRUD for all memory tiers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QBrush, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QListWidget, QListWidgetItem, QSplitter,
    QTabWidget, QLineEdit, QTextEdit, QMessageBox,
    QMenu, QTreeWidget, QTreeWidgetItem, QInputDialog
)

from xeno.desktop.theme_manager import theme_manager
from xeno.desktop.runtime_bridge import get_bridge

logger = logging.getLogger(__name__)


class MemoryPage(QWidget):
    """Unified memory management — chat, vector, episodic, semantic, and more."""

    MEMORY_TIERS = ["Context", "Semantic", "Episodic", "Vector", "Procedural", "Temporal KG"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("memoryPage")
        self._trees: dict[str, QTreeWidget] = {}
        self._stat_labels: dict[str, QLabel] = {}
        self._setup_ui()
        self._load_real_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Header Row
        header_layout = QHBoxLayout()
        title_layout = QVBoxLayout()
        
        title = QLabel("Memory Center")
        title.setObjectName("pageTitle")
        title_layout.addWidget(title)

        desc = QLabel("Search, view, and manage all memory tiers")
        desc.setObjectName("secondary")
        title_layout.addWidget(desc)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Health Indicator
        self._status_label = QLabel("🟢 Status: Loading...")
        self._status_label.setObjectName("secondary")
        self._status_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self._status_label)
        
        layout.addLayout(header_layout)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search all columns...")
        self._search.setFixedHeight(36)
        self._search.setMaximumWidth(300)
        self._search.textChanged.connect(self._search_memory)
        toolbar.addWidget(self._search)

        self._search_btn = QPushButton("🔍 Search")
        self._search_btn.setObjectName("primary")
        self._search_btn.setFixedHeight(36)
        self._search_btn.clicked.connect(self._search_memory)
        toolbar.addWidget(self._search_btn)
        
        self._add_btn = QPushButton("➕ Add Memory")
        self._add_btn.setObjectName("primary")
        self._add_btn.setFixedHeight(36)
        self._add_btn.clicked.connect(self._add_memory)
        toolbar.addWidget(self._add_btn)
        
        self._consolidate_btn = QPushButton("🧠 Consolidate")
        self._consolidate_btn.setObjectName("subtle")
        self._consolidate_btn.setFixedHeight(36)
        self._consolidate_btn.clicked.connect(self._consolidate_memory)
        toolbar.addWidget(self._consolidate_btn)

        toolbar.addStretch()

        self._clear_btn = QPushButton("🗑 Clear All")
        self._clear_btn.setObjectName("danger")
        self._clear_btn.setFixedHeight(36)
        self._clear_btn.clicked.connect(self._confirm_clear)
        toolbar.addWidget(self._clear_btn)

        self._export_btn = QPushButton("📥 Export")
        self._export_btn.setObjectName("subtle")
        self._export_btn.setFixedHeight(36)
        self._export_btn.clicked.connect(self._export_data)
        toolbar.addWidget(self._export_btn)

        layout.addLayout(toolbar)
        
        # Stats Row
        stats_frame = QFrame()
        stats_frame.setObjectName("card")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(16, 8, 16, 8)
        
        for tier in self.MEMORY_TIERS:
            lbl = QLabel(f"{tier}: 0")
            lbl.setObjectName("secondary")
            self._stat_labels[tier] = lbl
            stats_layout.addWidget(lbl)
            if tier != self.MEMORY_TIERS[-1]:
                sep = QLabel("|")
                sep.setObjectName("tertiary")
                stats_layout.addWidget(sep)
                
        stats_layout.addStretch()
        layout.addWidget(stats_frame)

        # Tab Widget
        self._tab_widget = QTabWidget()
        self._apply_tab_theme()

        for tier in self.MEMORY_TIERS:
            page = QWidget()
            pl = QVBoxLayout(page)
            pl.setContentsMargins(0, 12, 0, 0)

            tree = QTreeWidget()
            tree.setHeaderLabels(["Content", "Source", "Importance", "Timestamp"])
            tree.setAlternatingRowColors(True)
            tree.setIndentation(16)
            tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            tree.customContextMenuRequested.connect(lambda pos, t=tree: self._show_context_menu(pos, t))
            
            tree.setStyleSheet("""
                QTreeWidget {
                    border: 1px solid palette(mid);
                    border-radius: 8px;
                    padding: 4px;
                }
                QTreeWidget::item {
                    padding: 6px 8px;
                }
            """)
            tree.setColumnWidth(0, 400)
            tree.setColumnWidth(1, 120)
            tree.setColumnWidth(2, 100)

            pl.addWidget(tree)
            self._tab_widget.addTab(page, tier)
            self._trees[tier] = tree

        layout.addWidget(self._tab_widget)

    def _apply_tab_theme(self):
        tokens = theme_manager.get_tokens()
        self._tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{ 
                border: 1px solid {tokens.get('border', '#E4E4E7')}; 
                border-radius: 8px;
                background: {tokens.get('surface', '#FFFFFF')}; 
            }}
            QTabBar::tab {{ 
                padding: 8px 16px; 
                font-weight: 500; 
                color: {tokens.get('text_secondary', '#52525B')};
                background: transparent;
            }}
            QTabBar::tab:selected {{ 
                color: {tokens.get('accent', '#2563EB')};
                border-bottom: 2px solid {tokens.get('accent', '#2563EB')};
            }}
            QTabBar::tab:hover {{
                color: {tokens.get('text_primary', '#18181B')};
            }}
        """)

    def _load_real_data(self):
        """Try loading real memory data from backend or local files."""
        bridge = get_bridge()
        data_loaded = False
        
        # Attempt to get real memory from the bridge
        if bridge and bridge.runtime and bridge.runtime.memory:
            try:
                self._status_label.setText("🟢 Status: Connected (Runtime Memory)")
                memory = bridge.runtime.memory
                
                # Fetch facts
                facts = memory.list_facts()
                if isinstance(facts, dict):
                    for k, v in facts.items():
                        self._add_tree_item("Context", f"{k}: {v}", "context", "high")
                
                # Try getting stats if available
                if hasattr(memory, "reconcile_stats"):
                    stats = memory.reconcile_stats()
                    # Could populate stats from this...
                
                data_loaded = True
            except Exception as e:
                logger.warning(f"Failed to read from bridge memory: {e}")
        
        # Fallback to local files if bridge read failed
        if not data_loaded:
            self._status_label.setText("🟡 Status: Offline (Local Files)")
            
            try:
                context_path = Path("data") / "memory" / "context.json"
                if context_path.exists():
                    with open(context_path, "r", encoding="utf-8") as f:
                        cdata = json.load(f)
                        for fact in cdata.get("facts", []):
                            content = f"{fact.get('key')}: {fact.get('value')}"
                            ts = fact.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M"))
                            self._add_tree_item("Context", content, "context_json", "medium", ts)
                        data_loaded = True
            except Exception as e:
                logger.warning(f"Error reading local context.json: {e}")
                
            # Attempt to read memory managers (get_memory_manager fallback)
            try:
                from xeno.memory.unified import get_memory_manager
                manager = get_memory_manager()
                if manager:
                    facts = manager.list_facts()
                    if isinstance(facts, dict):
                        for k, v in facts.items():
                            self._add_tree_item("Context", f"{k}: {v}", "manager", "high")
                    data_loaded = True
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"get_memory_manager failed: {e}")

        # If completely empty, show empty state or sample info
        if self._is_empty():
            self._status_label.setText("⚪ Status: No Data (Showing Samples)")
            self._load_sample_data()
            
        self._update_stats()

    def _is_empty(self) -> bool:
        for tree in self._trees.values():
            if tree.topLevelItemCount() > 0:
                return False
        return True

    def _add_tree_item(self, tier: str, content: str, source: str, importance: str, timestamp: str = None):
        tree = self._trees.get(tier)
        if not tree: return
        
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            
        item = QTreeWidgetItem([content, source, importance, timestamp])
        
        # Apply importance visual badge
        tokens = theme_manager.get_tokens()
        imp_lower = importance.lower()
        if imp_lower == "high":
            item.setForeground(2, QBrush(QColor(tokens.get("success", "#16A34A"))))
            item.setText(2, f"🟢 {importance.capitalize()}")
        elif imp_lower == "medium":
            item.setForeground(2, QBrush(QColor(tokens.get("warning", "#D97706"))))
            item.setText(2, f"🟡 {importance.capitalize()}")
        else:
            item.setForeground(2, QBrush(QColor(tokens.get("text_tertiary", "#A1A1AA"))))
            item.setText(2, f"⚪ {importance.capitalize()}")
            
        tree.addTopLevelItem(item)

    def _load_sample_data(self):
        data = {
            "Semantic": [
                ("Ammar likes clean code architecture", "conversation", "medium", "2026-07-22 12:00"),
                ("Prefers mobile-first design patterns", "conversation", "low", "2026-07-20 09:30"),
            ],
            "Episodic": [
                ("Fixed WhatsApp bot connection issue", "task_complete", "high", "2026-07-21 18:00"),
                ("Created email filter system", "task_complete", "high", "2026-07-20 15:30"),
            ],
            "Vector": [
                ("Semantic search embeddings ready (452 chunks)", "chromadb", "high", "2026-07-22 08:00"),
                ("Memory vectors dimension: 768", "system", "medium", "2026-07-19 12:00"),
            ],
            "Procedural": [
                ("Web search: duckduckgo → web_search", "skill", "medium", "2026-07-18 14:00"),
                ("Email: gmail_list → gmail_send flow", "skill", "medium", "2026-07-17 11:00"),
            ],
            "Temporal KG": [
                ("Ammar → created → WhatsApp bot (2026-07-15)", "temporal", "high", "2026-07-22"),
                ("Ammar → fixed → email filter (2026-07-20)", "temporal", "high", "2026-07-22"),
            ],
        }

        for tier, items in data.items():
            for content, source, importance, timestamp in items:
                self._add_tree_item(tier, content, source, importance, timestamp)

    def _update_stats(self):
        for tier, tree in self._trees.items():
            count = tree.topLevelItemCount()
            if tier in self._stat_labels:
                self._stat_labels[tier].setText(f"{tier}: {count}")

    def _search_memory(self):
        query = self._search.text().strip().lower()
        for tier, tree in self._trees.items():
            for i in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(i)
                if item:
                    match = False
                    if not query:
                        match = True
                    else:
                        # Search across all columns
                        for col in range(tree.columnCount()):
                            if query in item.text(col).lower():
                                match = True
                                break
                    item.setHidden(not match)

    def _show_context_menu(self, pos: QPoint, tree: QTreeWidget):
        item = tree.itemAt(pos)
        if not item: return
        
        menu = QMenu(self)
        tokens = theme_manager.get_tokens()
        menu.setStyleSheet(f"""
            QMenu {{ 
                background-color: {tokens.get('surface', '#FFFFFF')}; 
                border: 1px solid {tokens.get('border', '#E4E4E7')}; 
                border-radius: 6px;
            }}
            QMenu::item {{ 
                padding: 6px 24px 6px 16px; 
                color: {tokens.get('text_primary', '#18181B')}; 
            }}
            QMenu::item:selected {{ 
                background-color: {tokens.get('accent_subtle', '#DBEAFE')}; 
            }}
        """)
        
        edit_action = menu.addAction("✏️ Edit Memory")
        delete_action = menu.addAction("🗑 Delete Memory")
        
        action = menu.exec(tree.viewport().mapToGlobal(pos))
        if action == edit_action:
            self._edit_item(item, tree)
        elif action == delete_action:
            self._delete_item(item, tree)

    def _edit_item(self, item: QTreeWidgetItem, tree: QTreeWidget):
        current_text = item.text(0)
        new_text, ok = QInputDialog.getText(self, "Edit Memory", "Content:", QLineEdit.EchoMode.Normal, current_text)
        if ok and new_text.strip():
            item.setText(0, new_text.strip())
            # In a real app, you would save this back to the backend.

    def _delete_item(self, item: QTreeWidgetItem, tree: QTreeWidget):
        reply = QMessageBox.question(
            self, "Delete Memory",
            "Are you sure you want to delete this memory?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            index = tree.indexOfTopLevelItem(item)
            tree.takeTopLevelItem(index)
            self._update_stats()
            # In a real app, delete from backend as well.

    def _add_memory(self):
        tier = self._tab_widget.tabText(self._tab_widget.currentIndex())
        content, ok = QInputDialog.getText(self, f"Add {tier} Memory", "Content:")
        if ok and content.strip():
            self._add_tree_item(tier, content.strip(), "manual", "high")
            self._update_stats()

    def _consolidate_memory(self):
        bridge = get_bridge()
        if bridge and bridge.runtime and bridge.runtime.memory:
            QMessageBox.information(self, "Consolidation", "Triggering memory consolidation across tiers...")
            try:
                bridge.send_input_sync("Please consolidate memory now.")
            except Exception as e:
                logger.error(f"Consolidation request failed: {e}")
        else:
            QMessageBox.warning(self, "Offline", "Cannot consolidate: Xeno runtime is offline.")

    def _export_data(self):
        export_data = {}
        for tier, tree in self._trees.items():
            items = []
            for i in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(i)
                # Strip the emoji from importance string for export
                imp = item.text(2).split(" ")[-1].lower() if " " in item.text(2) else item.text(2)
                items.append({
                    "content": item.text(0),
                    "source": item.text(1),
                    "importance": imp,
                    "timestamp": item.text(3)
                })
            export_data[tier] = items
            
        export_path = Path("data") / "memory_export.json"
        export_path.parent.mkdir(exist_ok=True)
        try:
            export_path.write_text(json.dumps(export_data, indent=2))
            QMessageBox.information(self, "Export Successful", f"Exported {sum(len(v) for v in export_data.values())} memories to:\n{export_path.absolute()}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not write to file:\n{e}")

    def _confirm_clear(self):
        reply = QMessageBox.warning(
            self, "Clear All Memory",
            "This will clear all items from the view.\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            confirm = QMessageBox.question(
                self, "Final Confirmation",
                "Are you absolutely sure?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                for tree in self._trees.values():
                    tree.clear()
                self._update_stats()
                QMessageBox.information(self, "Done", "Memory view cleared.")
