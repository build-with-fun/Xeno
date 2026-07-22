"""Welcome Page — animated first-launch onboarding."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QFrame, QSizePolicy
)
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QRadialGradient, QBrush


class WelcomePage(QWidget):
    """Welcome screen for the setup wizard."""

    nextRequested = object()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.0
        self._setup_ui()
        self._start_animation()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 40, 60, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        self._title = QLabel("Welcome to Xeno")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet("""
            font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
            font-size: 48px;
            font-weight: 700;
            color: #F5F5F6;
            padding: 0;
        """)
        layout.addWidget(self._title)

        self._subtitle = QLabel("Your Next-Generation AI Desktop Assistant")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setStyleSheet("""
            font-size: 20px;
            color: #A6A6AC;
            padding: 0 40px;
        """)
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._subtitle)

        layout.addSpacing(24)

        features = QHBoxLayout()
        features.setSpacing(24)
        features.setAlignment(Qt.AlignmentFlag.AlignCenter)

        feature_data = [
            ("🤖", "Multi-Agent AI", "Multiple specialized AI agents working together"),
            ("🧠", "Advanced Memory", "8-tier memory with vector search"),
            ("🎙", "Voice & Vision", "Real-time voice and screen understanding"),
            ("🔌", "Extensible", "Plugins, MCP, skills, and custom tools"),
        ]

        for icon, title, desc in feature_data:
            card = QFrame()
            card.setObjectName("featureCard")
            card.setFixedSize(200, 180)
            card.setStyleSheet("""
                #featureCard {
                    background-color: rgba(255,255,255,0.05);
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 16px;
                    padding: 20px 16px;
                }
                #featureCard:hover {
                    background-color: rgba(59,130,246,0.1);
                    border-color: #3B82F6;
                }
            """)
            cl = QVBoxLayout(card)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.setSpacing(8)
            il = QLabel(icon)
            il.setAlignment(Qt.AlignmentFlag.AlignCenter)
            il.setStyleSheet("font-size: 40px;")
            cl.addWidget(il)
            tl = QLabel(title)
            tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tl.setStyleSheet("font-size: 14px; font-weight: 600; color: #F5F5F6;")
            cl.addWidget(tl)
            dl = QLabel(desc)
            dl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dl.setWordWrap(True)
            dl.setStyleSheet("font-size: 12px; color: #A6A6AC;")
            cl.addWidget(dl)
            features.addWidget(card)

        layout.addLayout(features)

        layout.addSpacing(32)

        self._start_btn = QPushButton("Get Started")
        self._start_btn.setObjectName("primary")
        self._start_btn.setFixedHeight(48)
        self._start_btn.setFixedWidth(240)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3B82F6, stop:1 #8B5CF6);
                color: white;
                border: none;
                border-radius: 24px;
                font-size: 16px;
                font-weight: 600;
                padding: 12px 32px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563EB, stop:1 #7C3AED);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1D4ED8, stop:1 #6D28D9);
            }
        """)
        self._start_btn.clicked.connect(self._on_next)
        layout.addWidget(self._start_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        skip = QPushButton("Skip setup →")
        skip.setObjectName("subtle")
        skip.setFixedHeight(32)
        skip.setStyleSheet("color: #6B6B72; font-size: 13px; border: none;")
        skip.clicked.connect(self._on_skip)
        layout.addWidget(skip, alignment=Qt.AlignmentFlag.AlignCenter)

    def _start_animation(self):
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(800)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

    def _on_next(self):
        self.parent().parent().next_step()

    def _on_skip(self):
        self.parent().parent().finish_setup()
