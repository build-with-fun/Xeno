"""Setup Wizard — 6-step first-run onboarding flow.

Steps:
  1. Welcome — animated intro with feature highlights
  2. User Setup — name, info, documents
  3. Profile Setup — browser profiles, WhatsApp profile
  4. AI Configuration — providers, models per agent type
  5. Speech — TTS/STT configuration
  6. Computer Context — auto-gather system information
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QCheckBox, QFrame,
    QProgressBar, QScrollArea, QFileDialog, QListWidget,
    QListWidgetItem, QFormLayout, QGroupBox, QStackedWidget,
    QWizard, QWizardPage, QMessageBox, QSizePolicy
)
from PySide6.QtGui import QFont, QPixmap, QIcon

from xeno.desktop.theme_manager import theme_manager

logger = logging.getLogger(__name__)


class XenoSetupWizard(QWidget):
    """6-step onboarding wizard with animated transitions."""

    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("setupWizard")
        self.setStyleSheet("""
            #setupWizard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0B0B0D, stop:1 #161618);
            }
        """)
        self._steps = []
        self._current_step = 0
        self._setup_data = {
            "user": {},
            "documents": [],
            "profiles": {},
            "ai": {},
            "speech": {},
            "computer": {},
        }
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255,255,255,0.1);
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3B82F6, stop:1 #8B5CF6);
            }
        """)
        layout.addWidget(self._progress_bar)

        self._step_label = QLabel("Step 1 of 6")
        self._step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._step_label.setStyleSheet("color: #6B6B72; font-size: 13px; padding: 8px;")
        layout.addWidget(self._step_label)

        self._content_stack = QStackedWidget()
        self._content_stack.setStyleSheet("background: transparent;")
        layout.addWidget(self._content_stack, 1)

        self._build_pages()

    def _build_pages(self):
        pages = [
            self._build_welcome_page(),
            self._build_user_page(),
            self._build_profiles_page(),
            self._build_ai_page(),
            self._build_speech_page(),
            self._build_computer_page(),
        ]
        for page in pages:
            self._content_stack.addWidget(page)
        self._steps = pages
        self._update_progress()

    def _build_welcome_page(self):
        from .welcome_page import WelcomePage
        page = WelcomePage(self)
        return page

    def _build_user_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(60, 24, 60, 24)
        layout.setSpacing(12)

        title = QLabel("Tell us about yourself")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #F5F5F6;")
        layout.addWidget(title)

        subtitle = QLabel("This helps the AI personalize your experience")
        subtitle.setStyleSheet("font-size: 15px; color: #A6A6AC; padding-bottom: 16px;")
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._user_name = QLineEdit()
        self._user_name.setPlaceholderText("Your name")
        self._user_name.setStyleSheet("min-height: 36px;")
        form.addRow("Name", self._user_name)

        self._user_nickname = QLineEdit()
        self._user_nickname.setPlaceholderText("Optional")
        form.addRow("Nickname", self._user_nickname)

        self._user_email = QLineEdit()
        self._user_email.setPlaceholderText("you@example.com")
        form.addRow("Email", self._user_email)

        self._user_phone = QLineEdit()
        self._user_phone.setPlaceholderText("+1 234 567 890")
        form.addRow("Phone", self._user_phone)

        self._user_occupation = QLineEdit()
        self._user_occupation.setPlaceholderText("Software Engineer")
        form.addRow("Occupation", self._user_occupation)

        self._user_company = QLineEdit()
        self._user_company.setPlaceholderText("Optional")
        form.addRow("Company", self._user_company)

        self._user_country = QComboBox()
        self._user_country.setEditable(True)
        self._user_country.addItems(["", "United States", "United Kingdom", "Canada", "Australia", "Germany", "France", "India", "Pakistan", "UAE", "Saudi Arabia", "Other"])
        self._user_country.setStyleSheet("min-height: 36px;")
        form.addRow("Country", self._user_country)

        self._user_timezone = QComboBox()
        self._user_timezone.setEditable(True)
        self._user_timezone.addItems(["UTC-8", "UTC-5", "UTC", "UTC+1", "UTC+3", "UTC+5", "UTC+5:30", "UTC+8", "UTC+10"])
        form.addRow("Timezone", self._user_timezone)

        self._user_languages = QLineEdit()
        self._user_languages.setPlaceholderText("English, Urdu, Arabic")
        form.addRow("Languages", self._user_languages)

        self._user_birthday = QLineEdit()
        self._user_birthday.setPlaceholderText("April 21")
        form.addRow("Birthday", self._user_birthday)

        self._user_interests = QTextEdit()
        self._user_interests.setPlaceholderText("AI, programming, design, photography, gaming...")
        self._user_interests.setMaximumHeight(80)
        form.addRow("Interests", self._user_interests)

        layout.addLayout(form)

        layout.addSpacing(16)

        doc_label = QLabel("Add important documents (optional)")
        doc_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #F5F5F6;")
        layout.addWidget(doc_label)

        doc_desc = QLabel("Resume, PDFs, identity documents, personal files — AI will search them")
        doc_desc.setStyleSheet("font-size: 14px; color: #A6A6AC;")
        doc_desc.setWordWrap(True)
        layout.addWidget(doc_desc)

        doc_btn_layout = QHBoxLayout()
        add_doc = QPushButton("+ Add Files")
        add_doc.setObjectName("subtle")
        add_doc.setFixedHeight(36)
        add_doc.clicked.connect(self._add_documents)
        doc_btn_layout.addWidget(add_doc)

        self._doc_count = QLabel("0 files")
        self._doc_count.setStyleSheet("color: #A6A6AC; padding-left: 8px;")
        doc_btn_layout.addWidget(self._doc_count)
        doc_btn_layout.addStretch()
        layout.addLayout(doc_btn_layout)

        self._doc_list = QListWidget()
        self._doc_list.setMaximumHeight(120)
        self._doc_list.setStyleSheet("""
            QListWidget { border: 1px solid #2B2B2F; border-radius: 8px; padding: 4px; }
            QListWidget::item { padding: 4px 8px; color: #A6A6AC; }
        """)
        layout.addWidget(self._doc_list)

        layout.addStretch()

        nav = QHBoxLayout()
        nav.addStretch()
        next_btn = QPushButton("Continue →")
        next_btn.setObjectName("primary")
        next_btn.setFixedHeight(40)
        next_btn.setFixedWidth(160)
        next_btn.clicked.connect(self.next_step)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _add_documents(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Documents", "",
            "All Files (*);;PDFs (*.pdf);;Documents (*.doc *.docx *.txt *.md);;Images (*.png *.jpg)"
        )
        for f in files:
            path = Path(f)
            if path.exists():
                self._setup_data["documents"].append(str(path))
                self._doc_list.addItem(path.name)
        self._doc_count.setText(f"{len(self._setup_data['documents'])} files")

    def _build_profiles_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(60, 24, 60, 24)
        layout.setSpacing(16)

        title = QLabel("Set up your profiles")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #F5F5F6;")
        layout.addWidget(title)

        subtitle = QLabel("Configure browser and communication profiles for AI integration")
        subtitle.setStyleSheet("font-size: 15px; color: #A6A6AC;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        profiles = [
            ("chrome", "Chrome Profile", True),
            ("edge", "Edge Profile", False),
            ("brave", "Brave Profile", False),
            ("firefox", "Firefox Profile", False),
            ("whatsapp", "WhatsApp Profile", True),
        ]

        for key, name, recommended in profiles:
            group = QGroupBox(f"{'★ ' if recommended else ''}{name}")
            group.setStyleSheet("""
                QGroupBox {
                    background-color: rgba(255,255,255,0.03);
                    border: 1px solid #2B2B2F;
                    border-radius: 12px;
                    margin-top: 20px;
                    padding: 20px;
                    font-weight: 600;
                    color: #F5F5F6;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 4px 12px;
                    color: #F5F5F6;
                }
            """)
            gl = QVBoxLayout(group)
            gl.setSpacing(8)

            path_input = QLineEdit()
            path_input.setPlaceholderText(f"Path to {name} profile data...")
            path_input.setStyleSheet("min-height: 36px;")
            browse_btn = QPushButton("Browse...")
            browse_btn.setObjectName("subtle")
            browse_btn.setFixedHeight(32)

            path_layout = QHBoxLayout()
            path_layout.addWidget(path_input, 1)
            path_layout.addWidget(browse_btn)
            gl.addLayout(path_layout)

            self._setup_data["profiles"][key] = {"path": "", "enabled": True}
            browse_btn.clicked.connect(lambda checked, k=key, pi=path_input: self._browse_profile_path(k, pi))

            layout.addWidget(group)

        layout.addStretch()

        nav = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("subtle")
        back_btn.setFixedHeight(40)
        back_btn.clicked.connect(self.prev_step)
        nav.addWidget(back_btn)
        nav.addStretch()
        next_btn = QPushButton("Continue →")
        next_btn.setObjectName("primary")
        next_btn.setFixedHeight(40)
        next_btn.setFixedWidth(160)
        next_btn.clicked.connect(self.next_step)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _browse_profile_path(self, key: str, input_field: QLineEdit):
        dir_path = QFileDialog.getExistingDirectory(self, f"Select {key} profile directory")
        if dir_path:
            input_field.setText(dir_path)
            self._setup_data["profiles"][key]["path"] = dir_path

    def _build_ai_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(60, 24, 60, 24)
        layout.setSpacing(12)

        title = QLabel("Configure AI")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #F5F5F6;")
        layout.addWidget(title)

        subtitle = QLabel("Select AI providers and models for different capabilities")
        subtitle.setStyleSheet("font-size: 15px; color: #A6A6AC;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        provider_models = {
            "Google Gemini": "gemini-2.0-flash",
            "DeepSeek": "deepseek-chat",
            "Groq": "llama-3.3-70b-versatile",
            "OpenAI": "gpt-4o",
            "Anthropic": "claude-sonnet-4-20250514",
            "Ollama (Local)": "llama3.2",
        }

        self._main_provider = QComboBox()
        self._main_provider.addItems(provider_models.keys())
        self._main_provider.setStyleSheet("min-height: 36px;")
        self._main_provider.currentTextChanged.connect(lambda t: self._update_model_combo(t))

        self._main_model = QComboBox()
        self._main_model.setEditable(True)
        self._main_model.setStyleSheet("min-height: 36px;")

        global_toggle = QCheckBox("Use the same provider and model for ALL agents")
        global_toggle.setChecked(True)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Provider", self._main_provider)
        form.addRow("Model", self._main_model)

        layout.addLayout(form)

        layout.addWidget(global_toggle)

        self._agent_models_group = QGroupBox("Per-Agent Model Overrides")
        self._agent_models_group.setStyleSheet("""
            QGroupBox {
                background-color: rgba(255,255,255,0.03);
                border: 1px solid #2B2B2F;
                border-radius: 12px;
                margin-top: 20px;
                padding: 20px;
                color: #F5F5F6;
            }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 4px 12px; }
        """)
        agent_form = QFormLayout(self._agent_models_group)
        self._agent_combos = {}
        for agent in ["Main", "Coder", "Research", "Vision", "Reasoning", "Planning"]:
            c = QComboBox()
            c.setEditable(True)
            c.addItems(list(provider_models.keys()))
            c.setStyleSheet("min-height: 32px;")
            agent_form.addRow(f"{agent}:", c)
            self._agent_combos[agent] = c

        global_toggle.toggled.connect(self._agent_models_group.setHidden)
        self._agent_models_group.setVisible(False)

        layout.addWidget(self._agent_models_group)

        layout.addStretch()

        nav = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("subtle")
        back_btn.setFixedHeight(40)
        back_btn.clicked.connect(self.prev_step)
        nav.addWidget(back_btn)
        nav.addStretch()
        next_btn = QPushButton("Continue →")
        next_btn.setObjectName("primary")
        next_btn.setFixedHeight(40)
        next_btn.setFixedWidth(160)
        next_btn.clicked.connect(self.next_step)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _update_model_combo(self, provider: str):
        models = {
            "Google Gemini": ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-lite"],
            "DeepSeek": ["deepseek-chat", "deepseek-reasoner", "deepseek-v3", "deepseek-r1"],
            "Groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
            "OpenAI": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3-mini", "o4-mini"],
            "Anthropic": ["claude-sonnet-4-20250514", "claude-3.5-haiku", "claude-opus-4"],
            "Ollama (Local)": ["llama3.2", "llama3.1", "mistral", "qwen2.5", "deepseek-r1", "phi4", "gemma3"],
        }
        self._main_model.clear()
        self._main_model.addItems(models.get(provider, [provider]))

    def _build_speech_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(60, 24, 60, 24)
        layout.setSpacing(12)

        title = QLabel("Voice Configuration")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #F5F5F6;")
        layout.addWidget(title)

        subtitle = QLabel("Configure speech-to-text and text-to-speech settings")
        subtitle.setStyleSheet("font-size: 15px; color: #A6A6AC;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setSpacing(10)

        self._tts_provider = QComboBox()
        self._tts_provider.addItems(["Gemini TTS (Default)", "Edge TTS", "System TTS", "Eleven Labs", "OpenAI TTS"])
        self._tts_provider.setStyleSheet("min-height: 36px;")
        form.addRow("TTS Provider", self._tts_provider)

        self._tts_voice = QComboBox()
        self._tts_voice.addItems(["Gemini Default", "Charon", "Puck", "Eireann", "Kore", "Aoede", "Fenrir", "Zephyr", "Orus", "Sterope"])
        self._tts_voice.setStyleSheet("min-height: 36px;")
        form.addRow("Voice", self._tts_voice)

        self._stt_provider = QComboBox()
        self._stt_provider.addItems(["Whisper (Local)", "Gemini STT", "Deepgram", "Azure STT", "Google STT"])
        self._stt_provider.setStyleSheet("min-height: 36px;")
        form.addRow("STT Provider", self._stt_provider)

        self._wake_word = QLineEdit("Hey Xeno")
        self._wake_word.setStyleSheet("min-height: 36px;")
        form.addRow("Wake Word", self._wake_word)

        self._streaming_tts = QCheckBox("Enable streaming TTS")
        self._streaming_tts.setChecked(True)
        form.addRow("", self._streaming_tts)

        self._interrupt = QCheckBox("Enable interruptible speech (barge-in)")
        self._interrupt.setChecked(True)
        form.addRow("", self._interrupt)

        layout.addLayout(form)

        layout.addStretch()

        nav = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("subtle")
        back_btn.setFixedHeight(40)
        back_btn.clicked.connect(self.prev_step)
        nav.addWidget(back_btn)
        nav.addStretch()
        next_btn = QPushButton("Continue →")
        next_btn.setObjectName("primary")
        next_btn.setFixedHeight(40)
        next_btn.setFixedWidth(160)
        next_btn.clicked.connect(self.next_step)
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _build_computer_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(60, 24, 60, 24)
        layout.setSpacing(12)

        title = QLabel("System Analysis")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #F5F5F6;")
        layout.addWidget(title)

        subtitle = QLabel("Xeno will gather information about your computer for persistent context")
        subtitle.setStyleSheet("font-size: 15px; color: #A6A6AC;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._scan_btn = QPushButton("🔍 Scan My Computer")
        self._scan_btn.setObjectName("primary")
        self._scan_btn.setFixedHeight(44)
        self._scan_btn.setFixedWidth(240)
        self._scan_btn.clicked.connect(self._run_system_scan)
        layout.addWidget(self._scan_btn)

        self._scan_results = QLabel("Click the button above to scan your system")
        self._scan_results.setStyleSheet("color: #A6A6AC; padding: 8px 0;")
        self._scan_results.setWordWrap(True)
        layout.addWidget(self._scan_results)

        self._system_info = QTextEdit()
        self._system_info.setReadOnly(True)
        self._system_info.setMaximumHeight(300)
        self._system_info.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255,255,255,0.03);
                border: 1px solid #2B2B2F;
                border-radius: 8px;
                color: #A6A6AC;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
                padding: 12px;
            }
        """)
        layout.addWidget(self._system_info)

        layout.addStretch()

        nav = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("subtle")
        back_btn.setFixedHeight(40)
        back_btn.clicked.connect(self.prev_step)
        nav.addWidget(back_btn)
        nav.addStretch()
        finish_btn = QPushButton("✨ Complete Setup")
        finish_btn.setObjectName("primary")
        finish_btn.setFixedHeight(44)
        finish_btn.setFixedWidth(200)
        finish_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #22C55E, stop:1 #3B82F6);
                color: white;
                border: none;
                border-radius: 22px;
                font-size: 15px;
                font-weight: 600;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #16A34A, stop:1 #2563EB);
            }
        """)
        finish_btn.clicked.connect(self.finish_setup)
        nav.addWidget(finish_btn)
        layout.addLayout(nav)

        scroll.setWidget(content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _run_system_scan(self):
        self._scan_results.setText("🔍 Scanning your system...")
        info = []
        try:
            import platform
            info.append(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
            info.append(f"Machine: {platform.machine()}")
            info.append(f"Processor: {platform.processor()}")
        except Exception:
            pass

        try:
            import psutil
            info.append(f"CPU Cores: {psutil.cpu_count(logical=True)} ({psutil.cpu_count(logical=False)} physical)")
            mem = psutil.virtual_memory()
            info.append(f"RAM: {mem.total / 1024**3:.1f} GB ({mem.used / 1024**3:.1f} GB used)")
            info.append(f"Disk: {psutil.disk_usage('/').total / 1024**3:.0f} GB total")
            info.append(f"Disk Free: {psutil.disk_usage('/').free / 1024**3:.0f} GB")
        except Exception:
            pass

        try:
            import shutil
            python_path = shutil.which("python") or shutil.which("python3") or "N/A"
            info.append(f"Python: {platform.python_version()} at {python_path}")
            git_path = shutil.which("git")
            info.append(f"Git: {'Available' if git_path else 'Not found'}")
        except Exception:
            pass

        info.append(f"Hostname: {platform.node()}")

        self._system_info.setText("\n".join(info))
        self._setup_data["computer"] = {"info": info}
        self._scan_results.setText(f"✅ Scan complete — {len(info)} data points collected")
        self._scan_btn.setText("⟳ Rescan")

    def next_step(self):
        if self._current_step < len(self._steps) - 1:
            self._current_step += 1
            self._content_stack.setCurrentIndex(self._current_step)
            self._update_progress()

    def prev_step(self):
        if self._current_step > 0:
            self._current_step -= 1
            self._content_stack.setCurrentIndex(self._current_step)
            self._update_progress()

    def _update_progress(self):
        total = len(self._steps)
        current = self._current_step + 1
        self._step_label.setText(f"Step {current} of {total}")
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)

    def finish_setup(self):
        self._save_setup_data()
        theme_manager.set_setup_complete(True)
        self.finished.emit()

    def _save_setup_data(self):
        data = {
            "user": {
                "name": self._user_name.text() if hasattr(self, '_user_name') else "",
                "email": self._user_email.text() if hasattr(self, '_user_email') else "",
                "occupation": self._user_occupation.text() if hasattr(self, '_user_occupation') else "",
            },
            "documents": getattr(self, '_setup_data', {}).get("documents", []),
            "computer": getattr(self, '_setup_data', {}).get("computer", {}),
        }
        path = Path("data") / "setup_complete.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))
        logger.info("Setup data saved")
