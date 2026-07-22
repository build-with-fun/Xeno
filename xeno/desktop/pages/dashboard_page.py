"""Dashboard — premium system overview with animated stats, agent grid, and activity feed."""

from __future__ import annotations

import math
import time
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property, QRectF, QPointF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QScrollArea, QSizePolicy, QGraphicsOpacityEffect, QPushButton
)
from PySide6.QtGui import QFont, QPainter, QColor, QLinearGradient, QBrush, QPen, QPainterPath

from xeno.desktop.theme_manager import theme_manager

logger = logging.getLogger(__name__)


class AnimatedStatCard(QFrame):
    """Premium metric card with animated counter, gradient accent bar, and glow effect."""

    def __init__(self, title: str, value: str, subtitle: str = "", color: str = "#3B82F6", icon: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(130)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._color = color
        self._icon = icon
        self._target_value = value
        self._animated_value = 0.0
        self._glow_opacity = 0.0

        # Try to detect numeric value for animation
        self._is_numeric = False
        try:
            self._numeric_target = int(value.replace(',', ''))
            self._is_numeric = True
        except (ValueError, AttributeError):
            self._numeric_target = 0

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        # Header row: icon + title
        header = QHBoxLayout()
        header.setSpacing(8)
        if icon:
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"font-size: 18px;")
            header.addWidget(icon_lbl)
        title_lbl = QLabel(title.upper())
        title_lbl.setObjectName("tertiary")
        title_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; letter-spacing: 1px; color: {color};")
        header.addWidget(title_lbl)
        header.addStretch()
        layout.addLayout(header)

        # Value
        self._value_label = QLabel(value)
        self._value_label.setStyleSheet(f"font-size: 36px; font-weight: 800; color: {color};")
        layout.addWidget(self._value_label)

        # Subtitle
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("tertiary")
            sub.setWordWrap(True)
            sub.setStyleSheet("font-size: 12px;")
            layout.addWidget(sub)

        layout.addStretch()

    def paintEvent(self, event):
        """Custom paint with gradient accent line at top."""
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Gradient accent bar at top
        color = QColor(self._color)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0.0, color)
        color2 = QColor(color)
        color2.setAlpha(60)
        grad.setColorAt(1.0, color2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(QRectF(12, 0, self.width() - 24, 3), 1.5, 1.5)
        p.end()

    def animate_value(self):
        """Animate the value counter from 0 to target."""
        if not self._is_numeric or self._numeric_target == 0:
            return
        self._animated_value = 0
        self._anim_timer = QTimer(self)
        self._anim_step = 0
        self._anim_steps = 30  # frames
        self._anim_timer.timeout.connect(self._step_animation)
        self._anim_timer.start(25)  # ~40fps

    def _step_animation(self):
        self._anim_step += 1
        t = self._anim_step / self._anim_steps
        # Ease out cubic
        t = 1 - (1 - t) ** 3
        current = int(self._numeric_target * t)
        self._value_label.setText(f"{current:,}")
        if self._anim_step >= self._anim_steps:
            self._value_label.setText(f"{self._numeric_target:,}" if self._is_numeric else self._target_value)
            self._anim_timer.stop()

    def update_value(self, value: str):
        """Update the displayed value."""
        self._target_value = value
        try:
            self._numeric_target = int(value.replace(',', ''))
            self._is_numeric = True
        except (ValueError, AttributeError):
            self._is_numeric = False
        self._value_label.setText(value)


class AgentStatusDot(QWidget):
    """Tiny animated status indicator dot."""

    def __init__(self, name: str, status: str = "active", parent=None):
        super().__init__(parent)
        self._name = name
        self._status = status
        self.setFixedSize(120, 36)
        self.setToolTip(f"{name}: {status}")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        colors = {
            "active": QColor("#22C55E"),
            "idle": QColor("#3B82F6"),
            "running": QColor("#F59E0B"),
            "error": QColor("#EF4444"),
            "disabled": QColor("#6B6B72"),
        }
        color = colors.get(self._status, QColor("#A1A1AA"))

        # Dot with glow
        dot_x, dot_y = 8, self.height() // 2
        glow = QColor(color)
        glow.setAlpha(40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(dot_x, dot_y), 6, 6)
        p.setBrush(color)
        p.drawEllipse(QPointF(dot_x, dot_y), 4, 4)

        # Name text
        tokens = theme_manager.get_tokens()
        p.setPen(QColor(tokens["text_secondary"]))
        p.setFont(QFont("Segoe UI Variable Text", 10))
        p.drawText(20, 0, self.width() - 24, self.height(), Qt.AlignmentFlag.AlignVCenter, self._name)
        p.end()


class ActivityEntry(QFrame):
    """Activity log entry with colored accent, icon, and timestamp."""

    def __init__(self, text: str, time_str: str, type_: str = "info", parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        tokens = theme_manager.get_tokens()

        colors = {
            "info": tokens.get("accent", "#3B82F6"),
            "task": "#F59E0B",
            "done": tokens.get("success", "#22C55E"),
            "error": tokens.get("danger", "#EF4444"),
            "memory": "#06B6D4",
            "agent": "#EC4899",
        }
        color = colors.get(type_, tokens.get("text_tertiary", "#A1A1AA"))
        icons = {"info": "→", "task": "▸", "done": "✓", "error": "✗", "memory": "◈", "agent": "◉"}
        icon = icons.get(type_, "·")

        self.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border-left: 2px solid {color};
                padding-left: 8px;
                margin: 0;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 8, 2)
        layout.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(16)
        icon_lbl.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold; border: none;")
        layout.addWidget(icon_lbl)

        text_lbl = QLabel(text)
        text_lbl.setObjectName("secondary")
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet("font-size: 13px; border: none;")
        layout.addWidget(text_lbl, 1)

        ts = QLabel(time_str)
        ts.setObjectName("tertiary")
        ts.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ts.setStyleSheet("font-size: 11px; border: none;")
        layout.addWidget(ts)


class MemoryBar(QWidget):
    """Horizontal bar showing memory tier usage."""

    def __init__(self, label: str, value: int, max_val: int, color: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._value = value
        self._max_val = max(max_val, 1)
        self._color = color
        self.setFixedHeight(28)
        self.setMinimumWidth(200)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tokens = theme_manager.get_tokens()
        w = self.width()
        h = self.height()

        # Label
        p.setPen(QColor(tokens["text_secondary"]))
        p.setFont(QFont("Segoe UI Variable Text", 10))
        p.drawText(0, 0, 100, h, Qt.AlignmentFlag.AlignVCenter, self._label)

        # Bar background
        bar_x = 110
        bar_w = w - 160
        bar_h = 6
        bar_y = (h - bar_h) // 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(tokens["border"]))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

        # Bar fill
        fill_w = max(2, bar_w * min(self._value / self._max_val, 1.0))
        grad = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
        color = QColor(self._color)
        grad.setColorAt(0.0, color)
        color_end = QColor(color)
        color_end.setAlpha(180)
        grad.setColorAt(1.0, color_end)
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 3, 3)

        # Count
        p.setPen(QColor(tokens["text_tertiary"]))
        p.setFont(QFont("Segoe UI Variable Text", 10, QFont.Weight.DemiBold))
        p.drawText(w - 44, 0, 44, h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, str(self._value))
        p.end()


class DashboardPage(QWidget):
    """Main dashboard with system overview and activity feed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dashboardPage")
        self._start_time = time.time()
        self._setup_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_stats)
        self._refresh_timer.start(5000)
        # Trigger initial counter animations
        QTimer.singleShot(300, self._animate_cards)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        # Header
        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()

        # Quick action buttons
        consolidate_btn = QPushButton("🧠 Consolidate Memory")
        consolidate_btn.setObjectName("subtle")
        consolidate_btn.setFixedHeight(32)
        consolidate_btn.setToolTip("Trigger memory consolidation")
        consolidate_btn.clicked.connect(self._consolidate_memory)
        header.addWidget(consolidate_btn)

        layout.addLayout(header)

        desc = QLabel("System overview and real-time status")
        desc.setObjectName("secondary")
        layout.addWidget(desc)

        # ── Stat Cards Row ──
        self._stats_grid = QGridLayout()
        self._stats_grid.setSpacing(12)
        layout.addLayout(self._stats_grid)
        self._populate_stats()

        # ── Two-column content area ──
        content = QHBoxLayout()
        content.setSpacing(16)

        # Left: Activity Feed
        left = QVBoxLayout()
        left.setSpacing(8)

        activity_header = QHBoxLayout()
        al = QLabel("Recent Activity")
        al.setObjectName("sectionTitle")
        activity_header.addWidget(al)
        activity_header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("subtle")
        clear_btn.setFixedHeight(24)
        clear_btn.clicked.connect(self._clear_activity)
        activity_header.addWidget(clear_btn)
        left.addLayout(activity_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._activity_container = QWidget()
        self._activity_container.setStyleSheet("background: transparent;")
        self._activity_layout = QVBoxLayout(self._activity_container)
        self._activity_layout.setContentsMargins(0, 0, 0, 0)
        self._activity_layout.setSpacing(4)
        self._activity_layout.addStretch()

        scroll.setWidget(self._activity_container)
        left.addWidget(scroll, 1)
        content.addLayout(left, 3)

        # Right column: Agent status + Memory health
        right = QVBoxLayout()
        right.setSpacing(16)

        # Agent Status Grid
        agents_label = QLabel("Agent Status")
        agents_label.setObjectName("sectionTitle")
        right.addWidget(agents_label)

        self._agent_grid = QVBoxLayout()
        self._agent_grid.setSpacing(2)
        self._populate_agents()
        right.addLayout(self._agent_grid)

        right.addSpacing(8)

        # Memory Health
        mem_label = QLabel("Memory Health")
        mem_label.setObjectName("sectionTitle")
        right.addWidget(mem_label)

        self._memory_bars = QVBoxLayout()
        self._memory_bars.setSpacing(4)
        self._populate_memory_bars()
        right.addLayout(self._memory_bars)

        right.addStretch()
        content.addLayout(right, 2)

        layout.addLayout(content, 1)

    def _populate_stats(self):
        self._stat_cards = {}
        model = self._get_model_name()
        mem_count = self._get_memory_count()
        agent_count = self._get_agent_count()
        sched_count = self._get_schedule_count()
        tool_count = self._get_tool_count()

        stats_data = [
            ("Model", model, "Primary LLM", "#3B82F6", "🤖"),
            ("Memories", mem_count, "Stored items", "#8B5CF6", "🧠"),
            ("Tools", tool_count, "Available tools", "#22C55E", "🔧"),
            ("Schedules", sched_count, "Active tasks", "#F59E0B", "📅"),
            ("Agents", agent_count, "Registered", "#06B6D4", "🤝"),
            ("Uptime", self._get_uptime(), "Since start", "#EC4899", "⏱"),
        ]

        for i, (title, value, subtitle, color, icon) in enumerate(stats_data):
            row, col = divmod(i, 3)
            card = AnimatedStatCard(title, value, subtitle, color, icon)
            self._stats_grid.addWidget(card, row, col)
            self._stat_cards[title] = card

    def _populate_agents(self):
        agents_info = self._get_agents_info()
        for name, status in agents_info:
            dot = AgentStatusDot(name, status)
            self._agent_grid.addWidget(dot)

    def _populate_memory_bars(self):
        mem_data = self._get_memory_tier_data()
        colors = ["#3B82F6", "#8B5CF6", "#22C55E", "#F59E0B", "#06B6D4", "#EC4899"]
        for i, (label, count, max_val) in enumerate(mem_data):
            bar = MemoryBar(label, count, max_val, colors[i % len(colors)])
            self._memory_bars.addWidget(bar)

    def _animate_cards(self):
        for card in self._stat_cards.values():
            card.animate_value()

    # ── Data Fetchers ──

    def _get_model_name(self) -> str:
        try:
            from xeno.config import XenoConfig
            m = XenoConfig.from_env().model
            return m.split(":")[-1] if ":" in m else m
        except Exception:
            return "N/A"

    def _get_memory_count(self) -> str:
        try:
            from xeno.memory.unified import get_memory_manager
            mm = get_memory_manager()
            if mm:
                stats = mm.stats() if hasattr(mm, 'stats') else {}
                total = stats.get('total_items', 0)
                if total:
                    return str(total)
        except Exception:
            pass
        # Fallback: count context facts
        try:
            ctx_path = Path("data/memory/context_facts.json")
            if ctx_path.exists():
                import json
                data = json.loads(ctx_path.read_text(encoding='utf-8'))
                return str(len(data)) if isinstance(data, (dict, list)) else "0"
        except Exception:
            pass
        return "0"

    def _get_agent_count(self) -> str:
        count = 0
        try:
            agents_dir = Path("agents")
            if agents_dir.exists():
                count = sum(1 for d in agents_dir.iterdir() if d.is_dir() and (d / "description.md").exists())
        except Exception:
            pass
        return str(count) if count else "0"

    def _get_tool_count(self) -> str:
        try:
            from xeno.tools.registry import ALL_TOOLS
            return str(len(ALL_TOOLS))
        except Exception:
            return "0"

    def _get_schedule_count(self) -> str:
        try:
            from xeno.scheduler import get_scheduler
            s = get_scheduler()
            if s and hasattr(s, 'tasks'):
                return str(len(s.tasks))
        except Exception:
            pass
        try:
            import json
            p = Path("data/schedules.json")
            if p.exists():
                data = json.loads(p.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    return str(len(data))
        except Exception:
            pass
        return "0"

    def _get_uptime(self) -> str:
        elapsed = int(time.time() - self._start_time)
        if elapsed < 60:
            return f"{elapsed}s"
        elif elapsed < 3600:
            return f"{elapsed // 60}m {elapsed % 60}s"
        else:
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            return f"{h}h {m}m"

    def _get_agents_info(self) -> list[tuple[str, str]]:
        result = []
        try:
            agents_dir = Path("agents")
            if agents_dir.exists():
                for d in sorted(agents_dir.iterdir()):
                    if d.is_dir() and (d / "description.md").exists():
                        result.append((d.name.replace('_', ' ').title(), "active"))
        except Exception:
            pass
        if not result:
            result = [
                ("Research", "active"), ("Coding", "active"), ("Browser", "idle"),
                ("Planner", "active"), ("Automation", "idle"),
            ]
        return result

    def _get_memory_tier_data(self) -> list[tuple[str, int, int]]:
        """Returns [(tier_name, item_count, max_capacity)]."""
        tiers = []
        try:
            # Try real data
            import json
            ctx_path = Path("data/memory/context_facts.json")
            ctx_count = 0
            if ctx_path.exists():
                data = json.loads(ctx_path.read_text(encoding='utf-8'))
                ctx_count = len(data) if isinstance(data, (dict, list)) else 0
            tiers.append(("Context", ctx_count, max(ctx_count + 20, 50)))

            # Vector DB
            vec_path = Path("data/vector_db")
            vec_count = 0
            if vec_path.exists():
                vec_count = sum(1 for _ in vec_path.rglob("*.bin")) + sum(1 for _ in vec_path.rglob("*.pkl"))
            tiers.append(("Vector", vec_count, max(vec_count + 50, 200)))

            # Episodic
            tiers.append(("Episodic", 0, 100))
            tiers.append(("Semantic", 0, 100))
            tiers.append(("Procedural", 0, 50))

        except Exception:
            tiers = [
                ("Context", 0, 50), ("Vector", 0, 200),
                ("Episodic", 0, 100), ("Semantic", 0, 100),
            ]
        return tiers

    def _refresh_stats(self):
        if not self.isVisible():
            return
        # Update uptime
        uptime_card = self._stat_cards.get("Uptime")
        if uptime_card:
            uptime_card.update_value(self._get_uptime())
        # Update schedule count
        sched_card = self._stat_cards.get("Schedules")
        if sched_card:
            sched_card.update_value(self._get_schedule_count())

    def _consolidate_memory(self):
        try:
            from xeno.memory.unified import get_memory_manager
            mm = get_memory_manager()
            if mm and hasattr(mm, 'consolidate'):
                mm.consolidate()
                self.add_activity("Memory consolidation triggered", "memory")
        except Exception as e:
            self.add_activity(f"Consolidation failed: {e}", "error")

    def _clear_activity(self):
        while self._activity_layout.count() > 1:
            item = self._activity_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def add_activity(self, text: str, type_: str = "info"):
        now = datetime.now().strftime("%H:%M")
        item = ActivityEntry(text, now, type_)
        self._activity_layout.insertWidget(self._activity_layout.count() - 1, item)
        while self._activity_layout.count() > 100:
            item = self._activity_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
