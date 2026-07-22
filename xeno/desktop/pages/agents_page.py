"""Agents Manager — create, configure, enable/disable AI agents."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QTextEdit, QLineEdit, QComboBox, QCheckBox,
    QSpinBox, QFormLayout, QDialog, QDialogButtonBox,
    QFileDialog, QMessageBox
)
from PySide6.QtGui import QIcon

from xeno.desktop.theme_manager import theme_manager

logger = logging.getLogger(__name__)


def save_agent(data: dict):
    """Persist agent to agents/ directory as a Markdown file with YAML frontmatter."""
    agents_dir = Path("agents")
    agents_dir.mkdir(exist_ok=True)
    name = data.get("name", "untitled")
    filename = name.lower().replace(" ", "_") + ".md"
    filepath = agents_dir / filename
    
    yaml_lines = [
        "---",
        f"name: {name}",
        f"description: {data.get('description', '')}",
        f"model: {data.get('model', 'default')}",
        f"enabled: {str(data.get('enabled', True)).lower()}",
        f"always_on: {str(data.get('always_on', False)).lower()}",
        f"temperature: {data.get('temperature', 0.7)}"
    ]
    if "tools" in data and data["tools"]:
        yaml_lines.append("tools:")
        for t in data["tools"]:
            yaml_lines.append(f"  - {t}")
    else:
        yaml_lines.append("tools: []")
            
    yaml_lines.append("---")
    yaml_lines.append("")
    yaml_lines.append(data.get("prompt", ""))
    
    filepath.write_text("\n".join(yaml_lines), encoding="utf-8")


def load_agents_from_dir() -> list[dict]:
    """Load agents by scanning agents/ directory for description.md files with YAML frontmatter."""
    agents_dir = Path("agents")
    agents = []
    if not agents_dir.exists():
        return agents
        
    for filepath in agents_dir.glob("*.md"):
        try:
            content = filepath.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    yaml_str = parts[1]
                    prompt = parts[2].strip()
                    data = {"prompt": prompt}
                    current_list = None
                    for line in yaml_str.split("\n"):
                        line = line.rstrip()
                        if not line:
                            continue
                        if line.startswith("  - "):
                            if current_list is not None:
                                data[current_list].append(line[4:].strip())
                        elif ":" in line:
                            k, v = line.split(":", 1)
                            k = k.strip()
                            v = v.strip()
                            if not v or v == "[]":
                                current_list = k
                                data[k] = []
                            else:
                                current_list = None
                                if v.lower() == "true": v = True
                                elif v.lower() == "false": v = False
                                else:
                                    try: v = float(v)
                                    except ValueError: pass
                                data[k] = v
                    agents.append(data)
        except Exception as e:
            logger.warning(f"Failed to load agent {filepath}: {e}")
            
    return agents


class RunAgentDialog(QDialog):
    """Dialog to run a task on a specific agent."""
    def __init__(self, agent_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Run Task on {agent_name}")
        self.setMinimumSize(450, 300)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Send task to {agent_name}:</b>"))
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Enter your prompt or task description...")
        layout.addWidget(self.prompt_edit)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Run")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def get_prompt(self) -> str:
        return self.prompt_edit.toPlainText()


class AgentCard(QFrame):
    """Premium app-store like Agent display card."""
    
    edit_requested = Signal(dict)
    run_requested = Signal(dict, str)
    toggle_changed = Signal(dict, bool)

    def __init__(self, agent_data: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.agent_data = agent_data
        
        name = agent_data.get("name", "Unknown")
        description = agent_data.get("description", "")
        model = agent_data.get("model", "default")
        enabled = agent_data.get("enabled", True)
        tools = agent_data.get("tools", [])
        
        self.setMinimumHeight(170)
        
        # Color hash for accent bar
        colors = ["#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#EF4444", "#06B6D4", "#EC4899"]
        self.accent_color = colors[hash(name) % len(colors)]
        
        tokens = theme_manager.get_tokens()
        surface_alt = tokens.get("surface_alt", "#F4F4F7")
        accent = tokens.get("accent", "#3B82F6")
        
        self.setStyleSheet(f"""
            #card {{
                background-color: transparent;
                border: 1px solid palette(mid);
                border-radius: 12px;
                border-left: 3px solid {self.accent_color};
            }}
            #card:hover {{
                border-color: {accent};
                background-color: rgba(120, 120, 120, 0.05);
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Header: Status, Name, Toggle
        header = QHBoxLayout()
        
        status_color = "#22C55E" if enabled else "#A1A1AA"
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {status_color}; font-size: 16px;")
        header.addWidget(self.status_dot)
        
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 16px; font-weight: 600;")
        header.addWidget(name_lbl)
        
        header.addStretch()
        
        self.toggle = QCheckBox()
        self.toggle.setChecked(enabled)
        self.toggle.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 32px;
                height: 18px;
                border-radius: 9px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: #A1A1AA;
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.accent_color};
            }}
        """)
        self.toggle.toggled.connect(self._on_toggled)
        header.addWidget(self.toggle)
        
        layout.addLayout(header)

        # Description
        desc_lbl = QLabel(description[:100] + ("..." if len(description)>100 else ""))
        desc_lbl.setObjectName("secondary")
        desc_lbl.setWordWrap(True)
        desc_lbl.setMinimumHeight(40)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(desc_lbl)

        # Badges
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(6)
        
        badge_style = f"""
            background-color: {surface_alt};
            color: {tokens.get("text_secondary", "#52525B")};
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        """
        
        model_badge = QLabel(str(model))
        model_badge.setStyleSheet(badge_style)
        badges_layout.addWidget(model_badge)
        
        if tools:
            tools_badge = QLabel(f"{len(tools)} tools")
            tools_badge.setStyleSheet(badge_style)
            badges_layout.addWidget(tools_badge)
            
        badges_layout.addStretch()
        layout.addLayout(badges_layout)

        # Run Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.run_btn = QPushButton("Run")
        self.run_btn.setFixedHeight(28)
        self.run_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.accent_color};
                color: white;
                border-radius: 14px;
                padding: 0 16px;
                font-weight: 600;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {accent};
            }}
        """)
        self.run_btn.clicked.connect(self._on_run_clicked)
        btn_layout.addWidget(self.run_btn)
        
        layout.addLayout(btn_layout)
        
    def _on_toggled(self, checked: bool):
        status_color = "#22C55E" if checked else "#A1A1AA"
        self.status_dot.setStyleSheet(f"color: {status_color}; font-size: 16px;")
        self.toggle_changed.emit(self.agent_data, checked)

    def _on_run_clicked(self):
        dlg = RunAgentDialog(self.agent_data.get("name", "Agent"), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            prompt = dlg.get_prompt()
            if prompt.strip():
                self.run_requested.emit(self.agent_data, prompt)

    def mousePressEvent(self, event):
        # Only edit if clicking on the card itself, not the buttons
        if event.button() == Qt.MouseButton.LeftButton:
            self.edit_requested.emit(self.agent_data)
        super().mousePressEvent(event)


class AgentEditDialog(QDialog):
    """Dialog for editing an agent's configuration."""

    def __init__(self, agent_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Agent: {agent_data.get('name', 'New Agent')}")
        self.setMinimumSize(500, 600)
        self._result = None
        self._setup_ui(agent_data)

    def _setup_ui(self, data):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(12)

        self._name = QLineEdit(data.get("name", ""))
        form.addRow("Name", self._name)

        self._desc = QTextEdit()
        self._desc.setPlainText(data.get("description", ""))
        self._desc.setMaximumHeight(80)
        form.addRow("Description", self._desc)

        self._prompt = QTextEdit()
        self._prompt.setPlainText(data.get("prompt", ""))
        form.addRow("System Prompt", self._prompt)

        self._model = QLineEdit(str(data.get("model", "default")))
        form.addRow("Model", self._model)

        self._temperature = QSpinBox()
        self._temperature.setRange(0, 100)
        try:
            temp_val = float(data.get("temperature", 0.7))
        except (ValueError, TypeError):
            temp_val = 0.7
        self._temperature.setValue(int(temp_val * 10))
        form.addRow("Temperature (x0.1)", self._temperature)

        self._enabled = QCheckBox()
        self._enabled.setChecked(data.get("enabled", True))
        form.addRow("Enabled", self._enabled)
        
        self._always_on = QCheckBox()
        self._always_on.setChecked(data.get("always_on", False))
        form.addRow("Always-On", self._always_on)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        self._result = {
            "name": self._name.text(),
            "description": self._desc.toPlainText(),
            "prompt": self._prompt.toPlainText(),
            "model": self._model.text(),
            "temperature": self._temperature.value() / 10.0,
            "enabled": self._enabled.isChecked(),
            "always_on": self._always_on.isChecked(),
            "tools": [],
        }
        self.accept()

    def get_result(self) -> dict:
        return self._result or {}


class AgentsPage(QWidget):
    """Agent manager — view, edit, create, and configure AI agents."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("agentsPage")
        self._agents: list[dict] = []
        self._resize_timer = None
        self._setup_ui()
        self._load_agents()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("Agent Manager")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        desc = QLabel("Configure AI agents, assign tools, skills, and manage background agents")
        desc.setObjectName("secondary")
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._add_btn = QPushButton("+ New Agent")
        self._add_btn.setObjectName("primary")
        self._add_btn.setFixedHeight(36)
        self._add_btn.clicked.connect(self._create_agent)
        toolbar.addWidget(self._add_btn)

        self._export_btn = QPushButton("Export All")
        self._export_btn.setObjectName("subtle")
        self._export_btn.setFixedHeight(32)
        self._export_btn.clicked.connect(self._export_agents)
        toolbar.addWidget(self._export_btn)

        self._import_btn = QPushButton("Import")
        self._import_btn.setObjectName("subtle")
        self._import_btn.setFixedHeight(32)
        self._import_btn.clicked.connect(self._import_agents)
        toolbar.addWidget(self._import_btn)
        
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("subtle")
        self._refresh_btn.setFixedHeight(32)
        self._refresh_btn.clicked.connect(self._load_agents)
        toolbar.addWidget(self._refresh_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setSpacing(24)
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Standard Agents Grid
        self._grid = QGridLayout()
        self._grid.setSpacing(16)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._container_layout.addLayout(self._grid)
        
        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet(f"background-color: {theme_manager.get_tokens().get('border', '#E4E4E7')};")
        self._container_layout.addWidget(divider)
        
        # Always-On Section
        always_on_title = QLabel("Always-On Agents")
        always_on_title.setObjectName("sectionTitle")
        self._container_layout.addWidget(always_on_title)
        
        always_on_desc = QLabel("Background agents that run continuously.")
        always_on_desc.setObjectName("secondary")
        self._container_layout.addWidget(always_on_desc)
        
        self._always_on_grid = QGridLayout()
        self._always_on_grid.setSpacing(16)
        self._always_on_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._container_layout.addLayout(self._always_on_grid)

        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

    def _load_agents(self):
        self._agents = load_agents_from_dir()
        
        # Fallback to defaults if none loaded
        if not self._agents:
            self._agents = [
                {"name": "Research Agent", "description": "Web research and analysis", "model": "default", "enabled": True, "always_on": False, "tools": ["web_search"], "prompt": "", "temperature": 0.5},
                {"name": "Coding Agent", "description": "Code generation and debugging", "model": "default", "enabled": True, "always_on": False, "tools": ["code_execute", "file_ops"], "prompt": "", "temperature": 0.3},
                {"name": "Monitor Agent", "description": "Background system monitor", "model": "default", "enabled": True, "always_on": True, "tools": ["system_stats"], "prompt": "", "temperature": 0.1},
            ]
            for a in self._agents:
                save_agent(a)
                
        self._render_agents()

    def _render_agents(self):
        # Clear Standard Grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
                
        # Clear Always-On Grid
        while self._always_on_grid.count():
            item = self._always_on_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        cols = max(1, self.width() // 340)
        
        std_idx = 0
        ao_idx = 0
        
        for agent in self._agents:
            card = AgentCard(agent)
            card.edit_requested.connect(self._edit_agent)
            card.run_requested.connect(self._run_agent)
            card.toggle_changed.connect(self._on_agent_toggled)
            
            if agent.get("always_on", False):
                self._always_on_grid.addWidget(card, ao_idx // cols, ao_idx % cols)
                ao_idx += 1
            else:
                self._grid.addWidget(card, std_idx // cols, std_idx % cols)
                std_idx += 1

    def _edit_agent(self, agent_data: dict):
        dlg = AgentEditDialog(agent_data, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            # Preserve tools
            result["tools"] = agent_data.get("tools", [])
            for i, a in enumerate(self._agents):
                if a["name"] == agent_data["name"]:
                    self._agents[i].update(result)
                    save_agent(self._agents[i])
                    break
            self._render_agents()

    def _create_agent(self):
        dlg = AgentEditDialog({
            "name": "New Agent", "description": "", "model": "default",
            "enabled": True, "always_on": False, "tools": [], "prompt": "", "temperature": 0.7,
        }, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_result()
            self._agents.append(result)
            save_agent(result)
            self._render_agents()
            
    def _run_agent(self, agent_data: dict, prompt: str):
        logger.info(f"Running agent {agent_data.get('name')} with prompt: {prompt}")
        QMessageBox.information(self, "Agent Started", f"Task sent to {agent_data.get('name')}:\n\n{prompt}")

    def _on_agent_toggled(self, agent_data: dict, enabled: bool):
        for i, a in enumerate(self._agents):
            if a["name"] == agent_data["name"]:
                self._agents[i]["enabled"] = enabled
                save_agent(self._agents[i])
                break

    def _export_agents(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Agents", "", "JSON Files (*.json)")
        if path:
            try:
                Path(path).write_text(json.dumps(self._agents, indent=2), encoding="utf-8")
                QMessageBox.information(self, "Export Successful", f"Exported {len(self._agents)} agents.")
            except Exception as e:
                QMessageBox.warning(self, "Export Failed", str(e))

    def _import_agents(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Agents", "", "JSON Files (*.json)")
        if path:
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for a in data:
                        # Append and save
                        # Ensure no duplicate name blindly, or overwrite
                        existing = [x for x in self._agents if x["name"] == a.get("name")]
                        if existing:
                            existing[0].update(a)
                            save_agent(existing[0])
                        else:
                            self._agents.append(a)
                            save_agent(a)
                    self._render_agents()
                    QMessageBox.information(self, "Import Successful", "Agents imported successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Import Failed", str(e))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._resize_timer:
            self._resize_timer.stop()
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._render_agents)
        self._resize_timer.start(150)

