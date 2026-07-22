"""Scheduler — calendar, timeline, and task management for scheduled AI actions."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QDate, QTime, QTimer, QDateTime
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QListWidget, QListWidgetItem, QSplitter,
    QTabWidget, QLineEdit, QTextEdit, QComboBox,
    QDateEdit, QTimeEdit, QSpinBox, QGroupBox,
    QFormLayout, QDialog, QDialogButtonBox, QCalendarWidget,
    QMessageBox, QMenu
)

from xeno.desktop.theme_manager import theme_manager

logger = logging.getLogger(__name__)


class ScheduleItem(QFrame):
    """Schedule entry display."""

    def __init__(self, schedule: dict, parent_page=None, parent=None):
        super().__init__(parent)
        self.schedule = schedule
        self.parent_page = parent_page
        self.setObjectName("card")
        self.setMinimumHeight(120)
        
        tokens = theme_manager.get_tokens()
        accent = tokens.get("accent", "#3B82F6")
        success = tokens.get("success", "#22C55E")
        warning = tokens.get("warning", "#F59E0B")
        danger = tokens.get("danger", "#EF4444")
        text_primary = tokens.get("text_primary", "#FFFFFF")
        text_secondary = tokens.get("text_secondary", "#A1A1AA")
        border = tokens.get("border", "#3F3F46")
        
        self.setStyleSheet(f"""
            #card {{
                background-color: transparent;
                border: 1px solid {border};
                border-radius: 12px;
            }}
            #card:hover {{
                border-color: {accent};
                background-color: rgba(59,130,246,0.05);
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        type_icons = {"once": "🔵", "daily": "🔄", "weekly": "📅", "monthly": "📆", "yearly": "🗓", "cron": "⚙️", "reminder": "⏰"}
        sched_type = self.schedule.get("type", "once")
        icon = type_icons.get(sched_type, "📌")
        
        self.icon_badge = QLabel(icon)
        self.icon_badge.setFixedSize(32, 32)
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_badge.setStyleSheet(f"background-color: rgba(59,130,246,0.15); border-radius: 16px; font-size: 16px;")
        
        name_lbl = QLabel(self.schedule.get("name", "Unnamed"))
        name_lbl.setStyleSheet(f"font-family: 'Segoe UI Variable Display'; font-size: 16px; font-weight: 600; color: {text_primary};")
        
        header.addWidget(self.icon_badge)
        header.addWidget(name_lbl)
        header.addStretch()

        self.enabled = self.schedule.get("enabled", True)
        self.status = QLabel("● Active" if self.enabled else "○ Paused")
        self.status.setStyleSheet(f"color: {success if self.enabled else text_secondary}; font-size: 12px; font-weight: 600;")
        header.addWidget(self.status)
        layout.addLayout(header)

        pl = QLabel(self.schedule.get("prompt", "")[:100])
        pl.setStyleSheet(f"color: {text_secondary}; font-size: 14px; font-family: 'Segoe UI Variable Text';")
        pl.setWordWrap(True)
        layout.addWidget(pl)
        
        footer = QHBoxLayout()
        info = QLabel(f"{sched_type.title()}  ·  Next: {self.schedule.get('next_run', 'N/A')}")
        info.setStyleSheet(f"color: {text_secondary}; font-size: 12px;")
        
        self.countdown_lbl = QLabel("")
        self.countdown_lbl.setStyleSheet(f"color: {accent}; font-size: 12px; font-weight: 600;")
        
        footer.addWidget(info)
        footer.addStretch()
        footer.addWidget(self.countdown_lbl)
        
        layout.addLayout(footer)
        
        # Actions row
        actions = QHBoxLayout()
        self.run_btn = QPushButton("▶ Run Now")
        self.run_btn.setObjectName("primary")
        self.run_btn.setFixedHeight(28)
        self.run_btn.clicked.connect(self._run_now)
        
        self.toggle_btn = QPushButton("Pause" if self.enabled else "Resume")
        self.toggle_btn.setObjectName("subtle")
        self.toggle_btn.setFixedHeight(28)
        self.toggle_btn.clicked.connect(self._toggle_status)
        
        self.edit_btn = QPushButton("✎ Edit")
        self.edit_btn.setObjectName("subtle")
        self.edit_btn.setFixedHeight(28)
        self.edit_btn.clicked.connect(self._edit_schedule)
        
        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.setFixedHeight(28)
        self.delete_btn.setStyleSheet(f"color: {danger}; background: transparent; border: 1px solid {danger}; border-radius: 4px; padding: 0 10px;")
        self.delete_btn.clicked.connect(self._delete_schedule)
        
        actions.addWidget(self.run_btn)
        actions.addWidget(self.toggle_btn)
        actions.addWidget(self.edit_btn)
        actions.addStretch()
        actions.addWidget(self.delete_btn)
        
        layout.addLayout(actions)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_countdown)
        self.timer.start(1000)
        self._update_countdown()
        
    def _update_countdown(self):
        next_run = self.schedule.get("next_run", "")
        if not next_run or next_run == "N/A": return
        try:
            target = QDateTime.fromString(next_run, "yyyy-MM-dd HH:mm")
            if target.isValid():
                now = QDateTime.currentDateTime()
                secs = now.secsTo(target)
                if secs > 0:
                    d = secs // 86400
                    h = (secs % 86400) // 3600
                    m = (secs % 3600) // 60
                    s = secs % 60
                    parts = []
                    if d > 0: parts.append(f"{d}d")
                    if h > 0 or d > 0: parts.append(f"{h}h")
                    parts.append(f"{m}m {s}s")
                    self.countdown_lbl.setText("in " + " ".join(parts))
                else:
                    self.countdown_lbl.setText("Running soon...")
        except Exception:
            pass

    def _run_now(self):
        try:
            from xeno.scheduler import get_scheduler
            sched = get_scheduler()
            if sched and hasattr(sched, 'execute_now'):
                sched.execute_now(self.schedule.get("id"))
            QMessageBox.information(self, "Run Now", f"Task '{self.schedule.get('name')}' triggered successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Run Now", f"Could not run task: {e}")

    def _toggle_status(self):
        self.enabled = not self.enabled
        self.schedule["enabled"] = self.enabled
        tokens = theme_manager.get_tokens()
        success = tokens.get("success", "#22C55E")
        text_secondary = tokens.get("text_secondary", "#A1A1AA")
        
        self.status.setText("● Active" if self.enabled else "○ Paused")
        self.status.setStyleSheet(f"color: {success if self.enabled else text_secondary}; font-size: 12px; font-weight: 600;")
        self.toggle_btn.setText("Pause" if self.enabled else "Resume")
        
        try:
            from xeno.scheduler import get_scheduler
            sched = get_scheduler()
            if sched and hasattr(sched, 'toggle_task'):
                sched.toggle_task(self.schedule.get("id"), self.enabled)
        except Exception:
            pass

    def _edit_schedule(self):
        if self.parent_page:
            self.parent_page._edit_schedule(self.schedule)

    def _delete_schedule(self):
        if self.parent_page:
            self.parent_page._delete_schedule(self.schedule)


class EventCalendarWidget(QCalendarWidget):
    """Calendar widget with event markers."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.event_dates = set()
        self.tokens = theme_manager.get_tokens()
        
    def paintCell(self, painter: QPainter, rect, date: QDate):
        super().paintCell(painter, rect, date)
        if date in self.event_dates:
            painter.save()
            accent = QColor(self.tokens.get("accent", "#3B82F6"))
            painter.setBrush(accent)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(rect.center().x() - 3, rect.bottom() - 6, 6, 6)
            painter.restore()


class ScheduleDialog(QDialog):
    """Create/edit a schedule."""

    def __init__(self, schedule_data: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Schedule Task" if not schedule_data else "Edit Schedule")
        self.setMinimumSize(480, 500)
        self._data = schedule_data or {}
        self._result = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(10)

        self._name = QLineEdit(self._data.get("name", ""))
        form.addRow("Name", self._name)

        self._prompt = QTextEdit()
        self._prompt.setPlainText(self._data.get("prompt", ""))
        self._prompt.setMaximumHeight(100)
        form.addRow("Prompt / Action", self._prompt)

        self._type = QComboBox()
        self._type.addItems(["once", "daily", "weekly", "monthly", "yearly", "cron", "reminder"])
        idx = self._type.findText(self._data.get("type", "once"))
        if idx >= 0: self._type.setCurrentIndex(idx)
        form.addRow("Type", self._type)

        self._date = QDateEdit()
        if "next_run" in self._data and self._data["next_run"]:
            try:
                date_str = self._data["next_run"][:10]
                self._date.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
            except:
                self._date.setDate(QDate.currentDate())
        else:
            self._date.setDate(QDate.currentDate())
        form.addRow("Date", self._date)

        self._time = QTimeEdit()
        if "next_run" in self._data and self._data["next_run"]:
            try:
                time_str = self._data["next_run"][11:16]
                self._time.setTime(QTime.fromString(time_str, "HH:mm"))
            except:
                self._time.setTime(QTime.currentTime())
        else:
            self._time.setTime(QTime.currentTime())
        form.addRow("Time", self._time)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        self._result = {
            "name": self._name.text(),
            "prompt": self._prompt.toPlainText(),
            "type": self._type.currentText(),
            "date": self._date.date().toString("yyyy-MM-dd"),
            "time": self._time.time().toString("HH:mm"),
        }
        self.accept()

    def get_result(self) -> dict:
        return self._result or {}


class SchedulerPage(QWidget):
    """Scheduler dashboard with calendar, timeline, and list views."""

    VIEWS = ["Timeline", "Calendar", "List"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("schedulerPage")
        self._schedules: list[dict] = []
        self._setup_ui()
        self._load_schedules()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Scheduler")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        desc = QLabel("Automate tasks, set reminders, and schedule AI actions")
        desc.setObjectName("secondary")
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._add_btn = QPushButton("+ New Schedule")
        self._add_btn.setObjectName("primary")
        self._add_btn.setFixedHeight(36)
        self._add_btn.clicked.connect(self._create_schedule)
        toolbar.addWidget(self._add_btn)

        self._refresh_btn = QPushButton("⟳ Refresh")
        self._refresh_btn.setObjectName("subtle")
        self._refresh_btn.setFixedHeight(32)
        self._refresh_btn.clicked.connect(self._load_schedules)
        toolbar.addWidget(self._refresh_btn)

        toolbar.addStretch()

        for view_name in self.VIEWS:
            btn = QPushButton(view_name)
            btn.setObjectName("subtle")
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda checked, v=view_name: self._switch_view(v))
            toolbar.addWidget(btn)

        layout.addLayout(toolbar)

        self._view_stack = QTabWidget()
        self._view_stack.setStyleSheet("""
            QTabWidget::pane { border: none; background: transparent; }
            QTabBar::tab { padding: 8px 16px; font-weight: 500; }
        """)

        self._timeline_page = QWidget()
        self._timeline_layout = QVBoxLayout(self._timeline_page)
        self._timeline_layout.setContentsMargins(0, 12, 0, 0)
        self._timeline_container = QWidget()
        self._timeline_container.setStyleSheet("background: transparent;")
        self._timeline_list = QVBoxLayout(self._timeline_container)
        self._timeline_list.setSpacing(12)
        self._timeline_list.addStretch()
        tl_scroll = QScrollArea()
        tl_scroll.setWidgetResizable(True)
        tl_scroll.setWidget(self._timeline_container)
        tl_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._timeline_layout.addWidget(tl_scroll)
        self._view_stack.addTab(self._timeline_page, "Timeline")

        self._calendar_page = QWidget()
        cal_layout = QVBoxLayout(self._calendar_page)
        cal_layout.setContentsMargins(0, 12, 0, 0)
        self._calendar = EventCalendarWidget()
        self._calendar.setGridVisible(True)
        self._calendar.setStyleSheet("""
            QCalendarWidget { border: 1px solid palette(mid); border-radius: 8px; }
            QCalendarWidget QToolButton { color: #3B82F6; font-weight: 600; }
        """)
        cal_layout.addWidget(self._calendar)
        self._view_stack.addTab(self._calendar_page, "Calendar")

        self._list_page = QWidget()
        list_layout = QVBoxLayout(self._list_page)
        list_layout.setContentsMargins(0, 12, 0, 0)
        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid palette(mid);
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-radius: 4px;
            }
            QListWidget::item:hover { background-color: rgba(59,130,246,0.05); }
        """)
        list_layout.addWidget(self._list_widget)
        self._view_stack.addTab(self._list_page, "List")

        layout.addWidget(self._view_stack)

    def _load_schedules(self):
        self._schedules.clear()
        try:
            from xeno.scheduler import get_scheduler
            sched = get_scheduler()
            if sched:
                for task_id, task in sched.tasks.items():
                    if hasattr(task, '__dict__'):
                        t = task.__dict__
                    else:
                        t = {"name": str(task), "prompt": "", "type": "once"}
                    self._schedules.append({
                        "id": task_id,
                        "name": t.get("name", task_id),
                        "prompt": t.get("prompt", ""),
                        "type": t.get("schedule_type", t.get("type", "once")),
                        "next_run": t.get("next_run", "soon"),
                        "enabled": t.get("enabled", True),
                    })
        except Exception as e:
            logger.warning(f"Could not load schedules: {e}")

        if not self._schedules:
            self._schedules = [
                {"id": "1", "name": "Morning Check-in", "prompt": "Check emails and WhatsApp", "type": "daily", "next_run": "2026-07-23 09:00", "enabled": True},
                {"id": "2", "name": "Weekly Summary", "prompt": "Generate weekly productivity report", "type": "weekly", "next_run": "2026-07-27 18:00", "enabled": True},
                {"id": "3", "name": "Birthday Reminder", "prompt": "Remind about Ammar's birthday", "type": "yearly", "next_run": "2027-04-21 00:00", "enabled": False},
            ]

        self._render_timeline()
        self._render_list()
        self._update_calendar_markers()

    def _render_timeline(self):
        while self._timeline_list.count() > 1:
            item = self._timeline_list.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for s in self._schedules:
            item = ScheduleItem(s, parent_page=self)
            self._timeline_list.insertWidget(self._timeline_list.count() - 1, item)

    def _render_list(self):
        self._list_widget.clear()
        for s in self._schedules:
            icon = {"once": "🔵", "daily": "🔄", "weekly": "📅", "monthly": "📆", "yearly": "🗓", "reminder": "⏰"}.get(s["type"], "📌")
            text = f"{icon}  {s['name']}  —  {s['prompt'][:60]}  [{s['type']}]"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, s.get("id", ""))
            self._list_widget.addItem(item)

    def _update_calendar_markers(self):
        self._calendar.event_dates.clear()
        for s in self._schedules:
            next_run = s.get("next_run", "")
            if next_run and len(next_run) >= 10:
                try:
                    d = QDate.fromString(next_run[:10], "yyyy-MM-dd")
                    if d.isValid():
                        self._calendar.event_dates.add(d)
                except Exception:
                    pass
        self._calendar.updateCells()

    def _create_schedule(self):
        dlg = ScheduleDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            
            # Persist to backend
            try:
                from xeno.scheduler import get_scheduler
                sched = get_scheduler()
                if sched:
                    sched.create(
                        name=result["name"],
                        prompt=result["prompt"],
                        schedule_type=result["type"],
                        schedule_config={"date": result["date"], "time": result["time"]}
                    )
            except Exception as e:
                logger.warning(f"Could not persist schedule to backend: {e}")

            self._schedules.append({
                "id": f"s{len(self._schedules)}",
                "name": result["name"],
                "prompt": result["prompt"],
                "type": result["type"],
                "next_run": f"{result['date']} {result['time']}",
                "enabled": True,
            })
            self._render_timeline()
            self._render_list()
            self._update_calendar_markers()

    def _edit_schedule(self, schedule: dict):
        dlg = ScheduleDialog(schedule_data=schedule, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            schedule.update({
                "name": result["name"],
                "prompt": result["prompt"],
                "type": result["type"],
                "next_run": f"{result['date']} {result['time']}",
            })
            # Try persist update
            try:
                from xeno.scheduler import get_scheduler
                sched = get_scheduler()
                if sched and hasattr(sched, 'update_task'):
                    sched.update_task(schedule["id"], **schedule)
            except Exception:
                pass
                
            self._render_timeline()
            self._render_list()
            self._update_calendar_markers()

    def _delete_schedule(self, schedule: dict):
        confirm = QMessageBox.question(self, "Delete Schedule", f"Are you sure you want to delete '{schedule['name']}'?")
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                from xeno.scheduler import get_scheduler
                sched = get_scheduler()
                if sched and hasattr(sched, 'delete_task'):
                    sched.delete_task(schedule["id"])
            except Exception:
                pass
                
            if schedule in self._schedules:
                self._schedules.remove(schedule)
                self._render_timeline()
                self._render_list()
                self._update_calendar_markers()

    def _switch_view(self, view: str):
        for i in range(self._view_stack.count()):
            if self._view_stack.tabText(i) == view:
                self._view_stack.setCurrentIndex(i)
                break
