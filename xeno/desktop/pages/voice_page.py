"""Voice / Main Page — central AI conversation interface with animated orb.

Left: Live activity log
Center: AI Orb + mic button
Right: Chat-style conversation with bubbles
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QLineEdit, QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtGui import QFont, QColor, QKeySequence, QShortcut

from xeno.desktop.widgets.orb_widget import AIOrbWidget, OrbContainerWidget
from xeno.desktop.widgets.log_panel import LogPanel
from xeno.desktop.runtime_bridge import get_bridge
from xeno.desktop.theme_manager import theme_manager

logger = logging.getLogger(__name__)


class ChatBubble(QFrame):
    """Individual chat message bubble."""

    def __init__(self, text: str, is_user: bool = False, bubble_type: str = "normal", parent=None):
        super().__init__(parent)
        tokens = theme_manager.get_tokens()

        if is_user:
            bg = tokens["accent"]
            text_color = "#FFFFFF"
            align = Qt.AlignmentFlag.AlignRight
            margin = "margin-left: 60px;"
            border_radius = "border-radius: 16px 16px 4px 16px;"
        else:
            if bubble_type == "before_work":
                bg = tokens.get("accent_subtle", "rgba(59,130,246,0.14)")
                text_color = tokens["text_primary"]
            elif bubble_type == "after_work":
                bg = f"rgba({int(tokens['success'][1:3], 16)}, {int(tokens['success'][3:5], 16)}, {int(tokens['success'][5:7], 16)}, 0.12)"
                text_color = tokens["text_primary"]
            elif bubble_type == "error":
                bg = f"rgba({int(tokens['danger'][1:3], 16)}, {int(tokens['danger'][3:5], 16)}, {int(tokens['danger'][5:7], 16)}, 0.12)"
                text_color = tokens["danger"]
            elif bubble_type == "reminder":
                bg = f"rgba({int(tokens['warning'][1:3], 16)}, {int(tokens['warning'][3:5], 16)}, {int(tokens['warning'][5:7], 16)}, 0.12)"
                text_color = tokens["text_primary"]
            else:
                bg = tokens["surface"]
                text_color = tokens["text_primary"]
            align = Qt.AlignmentFlag.AlignLeft
            margin = "margin-right: 60px;"
            border_radius = "border-radius: 16px 16px 16px 4px;"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                {border_radius}
                {margin}
                padding: 12px 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Prefix for AI messages
        if not is_user and bubble_type != "normal":
            prefixes = {
                "before_work": "🤖 Working on it...",
                "after_work": "✓ Task Complete",
                "error": "✗ Error",
                "reminder": "⏰ Reminder",
            }
            prefix = prefixes.get(bubble_type, "")
            if prefix:
                prefix_lbl = QLabel(prefix)
                prefix_lbl.setStyleSheet(f"color: {text_color}; font-size: 11px; font-weight: 700; background: transparent;")
                layout.addWidget(prefix_lbl)

        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg.setStyleSheet(f"color: {text_color}; font-size: 14px; background: transparent; line-height: 1.5;")
        layout.addWidget(msg)

        # Timestamp
        ts = QLabel(datetime.now().strftime("%H:%M"))
        ts.setStyleSheet(f"color: {text_color}; opacity: 0.5; font-size: 10px; background: transparent;")
        ts.setAlignment(align)
        layout.addWidget(ts)


class ChatPanel(QWidget):
    """Right panel showing chat-style conversation with bubbles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("Conversation")
        title.setObjectName("subsection")
        header.addWidget(title)
        header.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("subtle")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.clicked.connect(self._clear)
        header.addWidget(self._clear_btn)
        layout.addLayout(header)

        # Scrollable chat area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._chat_container = QWidget()
        self._chat_container.setStyleSheet("background: transparent;")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(4, 4, 4, 4)
        self._chat_layout.setSpacing(8)
        self._chat_layout.addStretch()

        self._scroll.setWidget(self._chat_container)
        layout.addWidget(self._scroll, 1)

    def add_user_message(self, text: str):
        bubble = ChatBubble(text, is_user=True)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def add_ai_message(self, text: str, bubble_type: str = "normal"):
        bubble = ChatBubble(text, is_user=False, bubble_type=bubble_type)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _clear(self):
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()


class VoicePage(QWidget):
    """Main conversation page with AI orb, logs, and chat."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("voicePage")
        self._bridge = get_bridge()
        self._is_processing = False
        self._response_timer = None
        self._setup_ui()
        self._connect_bridge()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        left_panel = self._build_left_panel()
        center_panel = self._build_center_panel()
        right_panel = self._build_right_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([260, 500, 380])

        layout.addWidget(splitter)
        self._build_input_bar(layout)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("leftPanel")
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(400)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)

        self.log_panel = LogPanel(panel)
        layout.addWidget(self.log_panel)

        panel.setStyleSheet("""
            #leftPanel {
                background-color: transparent;
                border-right: 1px solid palette(mid);
            }
        """)
        return panel

    def _build_center_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("centerPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        scroll = QScrollArea(panel)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.orb_container = OrbContainerWidget(content)
        cl.addWidget(self.orb_container, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("Type a message or click the orb to begin")
        self.status_label.setObjectName("secondary")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tokens = theme_manager.get_tokens()
        self.status_label.setStyleSheet(f"color: {tokens['text_tertiary']}; padding: 8px; font-size: 13px;")
        cl.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("rightPanel")
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(500)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 16, 12, 16)

        self.chat_panel = ChatPanel(panel)
        layout.addWidget(self.chat_panel)

        panel.setStyleSheet("""
            #rightPanel {
                background-color: transparent;
                border-left: 1px solid palette(mid);
            }
        """)
        return panel

    def _build_input_bar(self, parent_layout: QVBoxLayout):
        tokens = theme_manager.get_tokens()

        bar = QFrame()
        bar.setObjectName("inputBar")
        bar.setFixedHeight(64)
        bar.setStyleSheet(f"""
            #inputBar {{
                background-color: transparent;
                border-top: 1px solid {tokens['border']};
            }}
        """)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 8, 16, 8)
        bar_layout.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask Xeno anything...")
        self.input_field.setFixedHeight(40)
        self.input_field.returnPressed.connect(self._send_message)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {tokens['border']};
                border-radius: 20px;
                padding: 8px 16px;
                font-size: 14px;
                background-color: {tokens['surface']};
                color: {tokens['text_primary']};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {tokens['accent']};
            }}
        """)
        bar_layout.addWidget(self.input_field)

        # Cancel button (hidden by default)
        self.cancel_btn = QPushButton("■ Stop")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.request_interrupt)
        self.cancel_btn.hide()
        bar_layout.addWidget(self.cancel_btn)

        self.send_btn = QPushButton("Send  ➤")
        self.send_btn.setFixedHeight(36)
        self.send_btn.setFixedWidth(90)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._send_message)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {tokens['accent']}, stop:1 {tokens.get('orb_gradient_end', '#8B5CF6')});
                color: white;
                border: none;
                border-radius: 18px;
                font-weight: 600;
                font-size: 13px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {tokens.get('accent_hover', tokens['accent'])}, stop:1 {tokens['accent']});
            }}
            QPushButton:disabled {{
                background: {tokens['border']};
                color: {tokens['text_tertiary']};
            }}
        """)
        bar_layout.addWidget(self.send_btn)

        parent_layout.addWidget(bar)

    def _send_message(self):
        text = self.input_field.text().strip()
        if not text or self._is_processing:
            return
        self.input_field.clear()

        # Check bridge readiness
        if not self._bridge._ready:
            self.chat_panel.add_ai_message("Xeno is still starting up. Please wait a moment...", "error")
            self.log_panel.log("Bridge not ready yet", "ERROR")
            return

        self.chat_panel.add_user_message(text)
        self.log_panel.log(f"User: {text[:80]}", "INFO")
        self.orb_container.orb.set_state("thinking")
        self.status_label.setText("Thinking...")
        self._set_processing(True)

        # Safety timeout — reset if no response within 120s
        if self._response_timer:
            self._response_timer.stop()
        self._response_timer = QTimer(self)
        self._response_timer.setSingleShot(True)
        self._response_timer.timeout.connect(self._on_response_timeout)
        self._response_timer.start(120000)

        # NON-BLOCKING: send in background thread
        def _do_send():
            try:
                self._bridge.send_input_sync(text)
            except Exception as e:
                logger.error(f"Send error: {e}")

        thread = threading.Thread(target=_do_send, daemon=True)
        thread.start()

    def _on_response_timeout(self):
        if self._is_processing:
            self.chat_panel.add_ai_message("Response timed out. The AI might be unavailable.", "error")
            self.log_panel.log("Response timed out", "ERROR")
            self.orb_container.orb.set_state("error")
            self.status_label.setText("Timed out")
            self._set_processing(False)

    def _set_processing(self, processing: bool):
        self._is_processing = processing
        self.send_btn.setVisible(not processing)
        self.cancel_btn.setVisible(processing)
        self.send_btn.setEnabled(not processing)
        if not processing and self._response_timer:
            self._response_timer.stop()

    def _connect_bridge(self):
        self._bridge.subscribe("event", self._on_event)

    def _on_event(self, ev):
        try:
            msg = getattr(ev, "message", str(ev))

            from xeno.brain.orchestrator import BrainEventType

            if hasattr(ev, "type"):
                et = ev.type
                if et == BrainEventType.BEFORE_WORK:
                    self.chat_panel.add_ai_message(msg, "before_work")
                    self.log_panel.log(msg[:100], "WORK")
                    self.orb_container.orb.set_state("speaking")
                    self.status_label.setText("Working...")
                elif et == BrainEventType.AFTER_WORK:
                    self.chat_panel.add_ai_message(msg, "after_work")
                    self.log_panel.log(msg[:100], "DONE")
                    self.orb_container.orb.set_state("idle")
                    self.status_label.setText("Ready")
                    self._set_processing(False)
                elif et == BrainEventType.INSTANT_REPLY:
                    self.chat_panel.add_ai_message(msg)
                    self.orb_container.orb.set_state("idle")
                    self.status_label.setText("Ready")
                    self._set_processing(False)
                elif et == BrainEventType.PROGRESS:
                    self.log_panel.log(msg[:100], "STATUS")
                    self.orb_container.orb.set_state("thinking")
                elif et == BrainEventType.AFTER_FAILURE:
                    self.chat_panel.add_ai_message(f"{msg}", "error")
                    self.log_panel.log(msg[:100], "ERROR")
                    self.orb_container.orb.set_state("error")
                    self.status_label.setText("Error occurred")
                    self._set_processing(False)
                elif et == BrainEventType.QUEUED:
                    self.log_panel.log(msg[:100], "TASK")
                elif et == BrainEventType.QUEUE_STARTED:
                    self.log_panel.log(f"Started: {msg[:80]}", "TASK")
                elif et == BrainEventType.REMINDER:
                    self.chat_panel.add_ai_message(f"{msg}", "reminder")
                    self.log_panel.log(msg[:100], "INFO")
                elif et == BrainEventType.INFO:
                    self.log_panel.log(msg[:100], "STATUS")
        except Exception as e:
            logger.debug(f"Event display error: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        self.log_panel.log("Voice page ready", "STATUS")

    def request_interrupt(self):
        """Interrupt the current AI response (barge-in)."""
        self._bridge.cancel_task()
        self.orb_container.orb.set_state("idle")
        self.status_label.setText("Interrupted")
        self.log_panel.log("User interrupted", "STATUS")
        self._set_processing(False)
