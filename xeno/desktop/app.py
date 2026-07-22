"""Xeno Desktop — main application entry point.

PySide6 + qfluentwidgets application with Fluent Design, Mica, system tray, 
theme sync, and the full 7-page interface.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QUrl
from PySide6.QtGui import QIcon, QAction, QFont, QColor, QDesktopServices
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon as FIF,
    setTheme, Theme, setThemeColor, InfoBar, InfoBarPosition,
    SplashScreen, MessageBox
)
from xeno.desktop.theme_manager import theme_manager, THEME_NAMES

logger = logging.getLogger(__name__)


class XenoMainWindow(FluentWindow):
    """Main application window with Fluent navigation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xeno — AI Desktop Assistant")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)
        self._center_on_screen()

        self._init_splash()
        try:
            self._setup_pages()
            self._setup_navigation()
            self._setup_tray()
            self._apply_mica()
            self._setup_shortcuts()
            theme_manager.set_on_theme_changed(self._on_theme_changed)
        except Exception as e:
            logger.error(f"Init failed: {e}", exc_info=True)

        QTimer.singleShot(500, self._finish_splash)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                (geo.width() - 1280) // 2,
                (geo.height() - 800) // 2,
            )

    def _init_splash(self):
        splash = SplashScreen(self.windowIcon(), self)
        splash.show()
        self._splash = splash

    def _finish_splash(self):
        if hasattr(self, '_splash') and self._splash:
            self._splash.close()
            self._splash = None

    def _setup_pages(self):
        from xeno.desktop.pages.voice_page import VoicePage
        from xeno.desktop.pages.dashboard_page import DashboardPage
        from xeno.desktop.pages.workspace_page import WorkspacePage
        from xeno.desktop.pages.agents_page import AgentsPage
        from xeno.desktop.pages.plugins_page import PluginsPage
        from xeno.desktop.pages.memory_page import MemoryPage
        from xeno.desktop.pages.settings_page import SettingsPage
        from xeno.desktop.pages.scheduler_page import SchedulerPage

        self.homeInterface = VoicePage(self)
        self.dashboardInterface = DashboardPage(self)
        self.workspaceInterface = WorkspacePage(self)
        self.agentsInterface = AgentsPage(self)
        self.pluginsInterface = PluginsPage(self)
        self.memoryInterface = MemoryPage(self)
        self.schedulerInterface = SchedulerPage(self)
        self.settingsInterface = SettingsPage(self)

    def _setup_navigation(self):
        nav = self.navigationInterface
        nav.setExpandWidth(260)
        nav.setCollapsible(True)

        self.addSubInterface(self.homeInterface, FIF.MICROPHONE, "Voice")
        self.addSubInterface(self.dashboardInterface, FIF.HOME, "Dashboard")
        self.addSubInterface(self.workspaceInterface, FIF.DOCUMENT, "Workspace")
        self.addSubInterface(self.agentsInterface, FIF.ROBOT, "Agents")
        self.addSubInterface(self.pluginsInterface, FIF.CONNECT, "Plugins")
        self.addSubInterface(self.memoryInterface, FIF.BOOK_SHELF, "Memory")
        self.addSubInterface(self.schedulerInterface, FIF.DATE_TIME, "Scheduler")
        self.addSubInterface(
            self.settingsInterface, FIF.SETTING, "Settings",
            position=NavigationItemPosition.BOTTOM,
        )

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = str(Path(__file__).parent / "assets" / "xeno_icon.png")
        tray_icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        if tray_icon.isNull():
            from PySide6.QtGui import QPixmap, QPainter, QColor
            pix = QPixmap(64, 64)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            grad = QColor("#3B82F6")
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(0, 0, 64, 64, 16, 16)
            p.setBrush(QColor("#FFFFFF"))
            p.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
            p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "X")
            p.end()
            tray_icon = QIcon(pix)

        self.tray_icon.setIcon(tray_icon)
        self.tray_icon.setToolTip("Xeno — AI Desktop Assistant")

        tray_menu = QMenu()
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show_and_activate)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        voice_action = QAction("Voice Mode", self)
        voice_action.triggered.connect(lambda: self._navigate_to("Voice"))
        tray_menu.addAction(voice_action)

        quit_action = QAction("Quit Xeno", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_and_activate()

    def show_and_activate(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def _apply_mica(self):
        try:
            import pywinstyles
            pywinstyles.apply_style(self, "mica")
            if theme_manager.is_dark():
                pywinstyles.change_header_color(self, "#0B0B0D")
        except Exception:
            pass

    def _setup_shortcuts(self):
        from PySide6.QtGui import QShortcut, QKeySequence

        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self._navigate_to("Settings"))
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Escape"), self, activated=self._handle_escape)
        QShortcut(QKeySequence("F11"), self, activated=self._toggle_fullscreen)

    def _navigate_to(self, name: str):
        for i, (interface, icon, text) in enumerate(self._stacked_items()):
            if text == name:
                self.switchTo(interface)
                return

    def _stacked_items(self):
        items = []
        for i in range(self.stackedWidget.count()):
            w = self.stackedWidget.widget(i)
            name = w.objectName()
            display = name.replace("Interface", "").replace("Page", "")
            if display:
                items.append((w, None, name))
        return items

    def _focus_search(self):
        current = self.stackedWidget.currentWidget()
        if current:
            search = current.findChild(type('QLineEdit', (object,), {}))
            if search:
                search.setFocus()

    def _handle_escape(self):
        current = self.stackedWidget.currentWidget()
        if hasattr(current, 'request_interrupt'):
            current.request_interrupt()

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_theme_changed(self, theme_name: str):
        self._apply_mica()

    def _quit_app(self):
        self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Xeno is still running",
            "The application is minimized to the system tray.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )


def setup_application() -> QApplication:
    """Configure and return the QApplication instance."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Xeno")
    app.setOrganizationName("Xeno")
    app.setApplicationVersion("2.0.0")

    app.setStyle("Fluent")

    font = QFont("Segoe UI Variable Text", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    return app


def main():
    """Main entry point for the desktop application."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = setup_application()

    try:
        import darkdetect
        theme = darkdetect.theme()
        if theme == "Dark":
            theme_manager.switch_theme(theme_manager.get_light_pair() + " Dark")
    except Exception:
        pass

    theme_manager.apply(app)

    window = XenoMainWindow()

    if not theme_manager.is_setup_complete():
        window.hide()
        from xeno.desktop.setup.setup_wizard import XenoSetupWizard
        wizard = XenoSetupWizard()
        wizard.finished.connect(lambda: _finish_wizard(wizard, window))
        wizard.show()
    else:
        _start_bridge(window)
        window.show()

    sys.exit(app.exec())


def _start_bridge(window):
    """Start the Xeno backend bridge in the background."""
    from xeno.desktop.runtime_bridge import get_bridge
    bridge = get_bridge()

    def on_ready():
        logger.info("Bridge ready — UI is connected")
        InfoBar.success(
            title="Connected", content="Xeno AI is ready.",
            position=InfoBarPosition.TOP_RIGHT, duration=3000, parent=window,
        )

    QTimer.singleShot(2000, on_ready)

    import threading
    t = threading.Thread(target=_run_bridge_background, daemon=True)
    t.start()


def _run_bridge_background():
    from xeno.desktop.runtime_bridge import get_bridge
    bridge = get_bridge()
    bridge.start()


def _finish_wizard(wizard, window):
    wizard.close()
    wizard.deleteLater()
    _start_bridge(window)
    window.show()


if __name__ == "__main__":
    main()
