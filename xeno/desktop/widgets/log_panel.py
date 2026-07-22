"""Live Log Panel — real-time display of agent activity, tool calls, API calls, etc."""

from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPlainTextEdit,
    QHBoxLayout, QPushButton, QScrollArea, QLineEdit, QApplication
)

from xeno.desktop.theme_manager import theme_manager


class LogPlainTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def mousePressEvent(self, e):
        cursor = self.cursorForPosition(e.pos())
        block = cursor.block()
        text = block.text()
        if text:
            QApplication.clipboard().setText(text)
        super().mousePressEvent(e)


class LogPanel(QWidget):
    """Real-time scrolling log panel showing agent activity."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logPanel")
        self.tokens = theme_manager.get_tokens()
        self._all_logs = []
        self._auto_scroll = True
        self._current_filter_level = "ALL"
        self._search_text = ""
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("Activity Log")
        title.setObjectName("subsection")
        header.addWidget(title)
        
        # Log count
        self._count_label = QLabel("0 entries")
        self._count_label.setStyleSheet(f"color: {self.tokens.get('text_tertiary', '#A1A1AA')}; font-size: 11px;")
        header.addWidget(self._count_label)
        
        header.addStretch()

        # Search box
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search logs...")
        self._search_input.setFixedWidth(120)
        self._search_input.textChanged.connect(self._on_search_changed)
        header.addWidget(self._search_input)

        # Filters
        self._filter_layout = QHBoxLayout()
        self._filter_layout.setSpacing(4)
        
        levels = ["ALL", "INFO", "WORK", "TOOL", "API", "ERROR"]
        self._level_btns = {}
        for lvl in levels:
            btn = QPushButton(lvl)
            btn.setObjectName("subtle")
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            if lvl == "ALL":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, l=lvl: self._on_level_filter_clicked(l))
            self._level_btns[lvl] = btn
            self._filter_layout.addWidget(btn)
            
        header.addLayout(self._filter_layout)

        # Pin to bottom
        self._pin_btn = QPushButton("Pin")
        self._pin_btn.setObjectName("subtle")
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(True)
        self._pin_btn.setFixedHeight(24)
        self._pin_btn.toggled.connect(self.set_auto_scroll)
        header.addWidget(self._pin_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("subtle")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.clicked.connect(self.clear_log)
        header.addWidget(self._clear_btn)

        layout.addLayout(header)

        self._log = LogPlainTextEdit(self)
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(5000)
        self._log.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: transparent;
                border: none;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 11px;
                color: {self.tokens.get('text_secondary', '#A6A6AC')};
                padding: 4px;
            }}
        """)
        self._log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        layout.addWidget(self._log)
        
        if hasattr(theme_manager, 'theme_changed'):
            theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self):
        self.tokens = theme_manager.get_tokens()
        self._log.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: transparent;
                border: none;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 11px;
                color: {self.tokens.get('text_secondary', '#A6A6AC')};
                padding: 4px;
            }}
        """)
        self._count_label.setStyleSheet(f"color: {self.tokens.get('text_tertiary', '#A1A1AA')}; font-size: 11px;")
        self._refresh_log_display()

    def _on_level_filter_clicked(self, level: str):
        self._current_filter_level = level
        for lvl, btn in self._level_btns.items():
            btn.setChecked(lvl == level)
        self._refresh_log_display()

    def _on_search_changed(self, text: str):
        self._search_text = text.lower()
        self._refresh_log_display()

    def _get_level_color(self, level: str) -> str:
        colors = {
            "INFO": self.tokens.get("accent", "#3B82F6"),
            "WORK": self.tokens.get("orb_gradient_start", "#8B5CF6"),
            "TOOL": self.tokens.get("warning", "#F59E0B"),
            "API": self.tokens.get("success", "#22C55E"),
            "MEMORY": self.tokens.get("accent_subtle", "#06B6D4"),
            "STATUS": self.tokens.get("text_tertiary", "#A1A1AA"),
            "ERROR": self.tokens.get("danger", "#EF4444"),
            "DONE": self.tokens.get("success", "#22C55E"),
            "AGENT": self.tokens.get("orb_gradient_end", "#EC4899"),
            "SKILL": "#14B8A6",
            "TASK": "#F97316",
        }
        return colors.get(level, self.tokens.get("text_primary", "#FFFFFF"))

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        record = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "raw_text": f"{timestamp} [{level}] {message}"
        }
        self._all_logs.append(record)
        if len(self._all_logs) > 5000:
            self._all_logs.pop(0)
            
        self._update_count()
        
        if self._matches_filter(record):
            self._append_record_to_display(record)

    def _matches_filter(self, record: dict) -> bool:
        if self._current_filter_level != "ALL" and record["level"] != self._current_filter_level:
            return False
        if self._search_text and self._search_text not in record["raw_text"].lower():
            return False
        return True

    def _append_record_to_display(self, record: dict):
        color_hex = self._get_level_color(record["level"])
        prefix = f"[{record['level']:6s}]"
        
        text_tertiary = self.tokens.get("text_tertiary", "#6B6B72")
        line = f'<span style="color:{text_tertiary};">{record["timestamp"]}</span> <span style="color:{color_hex};font-weight:600;">{prefix}</span> <span>{record["message"]}</span><br>'
        
        self._log.appendHtml(line)
        if self._auto_scroll:
            self._log.moveCursor(QTextCursor.MoveOperation.End)

    def _refresh_log_display(self):
        self._log.clear()
        for record in self._all_logs:
            if self._matches_filter(record):
                self._append_record_to_display(record)
        if self._auto_scroll:
            self._log.moveCursor(QTextCursor.MoveOperation.End)

    def _update_count(self):
        self._count_label.setText(f"{len(self._all_logs)} entries")

    def clear_log(self):
        self._all_logs.clear()
        self._log.clear()
        self._update_count()

    def set_auto_scroll(self, enabled: bool):
        self._auto_scroll = enabled
        self._pin_btn.setChecked(enabled)
        if enabled:
            self._log.moveCursor(QTextCursor.MoveOperation.End)


class TranscriptionPanel(QWidget):
    """Right panel showing real-time transcription and AI responses."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("transcriptionPanel")
        self.tokens = theme_manager.get_tokens()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Conversation")
        title.setObjectName("subsection")
        layout.addWidget(title)

        self._display = QPlainTextEdit(self)
        self._display.setReadOnly(True)
        self._display.setMaximumBlockCount(2000)
        self._display.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: transparent;
                border: none;
                font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
                font-size: 13px;
                color: {self.tokens.get('text_primary', '#F5F5F6')};
                padding: 4px;
            }}
        """)
        layout.addWidget(self._display)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("subtle")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.clicked.connect(self._display.clear)
        layout.addWidget(self._clear_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        if hasattr(theme_manager, 'theme_changed'):
            theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self):
        self.tokens = theme_manager.get_tokens()
        self._display.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: transparent;
                border: none;
                font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
                font-size: 13px;
                color: {self.tokens.get('text_primary', '#F5F5F6')};
                padding: 4px;
            }}
        """)

    def add_user_text(self, text: str):
        if not self._display.document().isEmpty():
            self.add_divider()
        color = self.tokens.get("accent", "#3B82F6")
        line = f'<p style="color:{color};margin:4px 0;"><b>You:</b> {text}</p>'
        self._display.appendHtml(line)
        self._display.moveCursor(QTextCursor.MoveOperation.End)

    def add_ai_text(self, text: str, is_before_work: bool = False, is_after_work: bool = False):
        if is_before_work:
            color = self.tokens.get("orb_gradient_start", "#8B5CF6")
            prefix = "🤖 "
        elif is_after_work:
            color = self.tokens.get("success", "#22C55E")
            prefix = "✓ "
        else:
            color = self.tokens.get("text_primary", "#F5F5F6")
            prefix = "AI: "
        line = f'<p style="color:{color};margin:4px 0;"><b>{prefix}</b>{text}</p>'
        self._display.appendHtml(line)
        self._display.moveCursor(QTextCursor.MoveOperation.End)

    def add_ai_thought(self, text: str):
        color = self.tokens.get("text_tertiary", "#A1A1AA")
        line = f'<p style="color:{color};font-style:italic;margin:2px 0 2px 16px;">💭 {text}</p>'
        self._display.appendHtml(line)
        self._display.moveCursor(QTextCursor.MoveOperation.End)

    def add_divider(self):
        border_color = self.tokens.get("border", "#2B2B2F")
        self._display.appendHtml(f'<hr style="border:0;border-top:1px solid {border_color};margin:8px 0;">')
        self._display.moveCursor(QTextCursor.MoveOperation.End)
