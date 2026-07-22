"""AI Orb Widget — animated, reactive particle sphere for voice conversation.

States: idle, listening, thinking, speaking, error
Each state changes: color gradient, rotation speed, particle intensity, pulse rhythm
"""

from __future__ import annotations

import math
import random
from PySide6.QtCore import (
    Qt, QTimer, QPointF, QRectF, Property, QEasingCurve,
    QPropertyAnimation, Signal, QParallelAnimationGroup
)
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QRadialGradient, QConicalGradient,
    QLinearGradient, QBrush, QPen, QFont, QFontMetrics, QPixmap
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton

from xeno.desktop.theme_manager import theme_manager


class OrbParticle:
    __slots__ = ("x", "y", "z", "vx", "vy", "vz", "size", "alpha", "speed", "phase")

    def __init__(self):
        self.x = random.uniform(-1, 1)
        self.y = random.uniform(-1, 1)
        self.z = random.uniform(-1, 1)
        self.vx = random.uniform(-0.003, 0.003)
        self.vy = random.uniform(-0.003, 0.003)
        self.vz = random.uniform(-0.003, 0.003)
        self.size = random.uniform(1.0, 3.5)
        self.alpha = random.uniform(0.3, 0.9)
        self.speed = random.uniform(0.5, 1.5)
        self.phase = random.uniform(0, math.pi * 2)


class AIOrbWidget(QWidget):
    """Animated AI orb with reactive states and particle effects."""

    stateChanged = Signal(str)

    STATES = ["idle", "listening", "thinking", "speaking", "error"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)

        self._state = "idle"
        self._rotation = 0.0
        self._pulse = 0.0
        self._glow_intensity = 0.0
        self._particle_intensity = 1.0
        self._breath_phase = 0.0
        self._ripple = 0.0

        self._particles = [OrbParticle() for _ in range(120)]

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(16)
        self._timer.start()
        
        # Initialize theme colors
        self._init_theme_colors()

        self._setup_animations()

    def _init_theme_colors(self):
        tokens = theme_manager.get_tokens()
        self._gradient_start = QColor(tokens.get("orb_gradient_start", "#3B82F6"))
        self._gradient_end = QColor(tokens.get("orb_gradient_end", "#8B5CF6"))
        self._accent_color = QColor(tokens.get("accent", "#3B82F6"))
        self._text_primary = QColor(tokens.get("text_primary", "#FFFFFF"))

    def _tick(self):
        self._breath_phase = (self._breath_phase + 0.02) % (math.pi * 2)
        self.update()

    def _setup_animations(self):
        self._pulse_anim = QPropertyAnimation(self, b"pulse")
        self._pulse_anim.setDuration(3000)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.SineCurve)
        self._pulse_anim.start()

        self._rotation_anim = QPropertyAnimation(self, b"rotation")
        self._rotation_anim.setDuration(8000)
        self._rotation_anim.setStartValue(0.0)
        self._rotation_anim.setEndValue(360.0)
        self._rotation_anim.setLoopCount(-1)
        self._rotation_anim.setEasingCurve(QEasingCurve.Type.Linear)
        self._rotation_anim.start()

    def get_rotation(self): return self._rotation
    def set_rotation(self, v):
        self._rotation = v
        if self._rotation >= 360.0:
            self._rotation = 0.0
        self.update()
    rotation = Property(float, get_rotation, set_rotation)

    def get_pulse(self): return self._pulse
    def set_pulse(self, v):
        self._pulse = v
        self._breath_phase = math.sin(v * math.pi * 2) * 0.5 + 0.5
        self.update()
    pulse = Property(float, get_pulse, set_pulse)

    def get_ripple(self): return self._ripple
    def set_ripple(self, v):
        self._ripple = v
        self.update()
    ripple = Property(float, get_ripple, set_ripple)

    def set_state(self, state: str):
        if state not in self.STATES:
            return
        if self._state != state:
            self._trigger_ripple()
            
        self._state = state
        self.stateChanged.emit(state)
        self._update_state_visuals()

    def _trigger_ripple(self):
        self._ripple = 0.0
        self._ripple_anim = QPropertyAnimation(self, b"ripple")
        self._ripple_anim.setDuration(800)
        self._ripple_anim.setStartValue(0.0)
        self._ripple_anim.setEndValue(1.0)
        self._ripple_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._ripple_anim.start()

    def _update_state_visuals(self):
        anim_duration = 600
        tokens = theme_manager.get_tokens()
        
        if self._state == "idle":
            self._target_gradient_start = QColor(tokens.get("orb_gradient_start", "#3B82F6"))
            self._target_gradient_end = QColor(tokens.get("orb_gradient_end", "#8B5CF6"))
            self._target_glow = 0.3
            self._target_particle = 1.0
            self._target_rotation_speed = 8000
        elif self._state == "listening":
            self._target_gradient_start = QColor(tokens.get("success", "#22C55E"))
            self._target_gradient_end = QColor(tokens.get("orb_gradient_start", "#3B82F6"))
            self._target_glow = 0.6
            self._target_particle = 1.5
            self._target_rotation_speed = 6000
        elif self._state == "thinking":
            self._target_gradient_start = QColor(tokens.get("warning", "#F59E0B"))
            self._target_gradient_end = QColor(tokens.get("danger", "#EF4444"))
            self._target_glow = 0.8
            self._target_particle = 2.0
            self._target_rotation_speed = 4000
        elif self._state == "speaking":
            self._target_gradient_start = QColor(tokens.get("orb_gradient_start", "#3B82F6"))
            self._target_gradient_end = QColor(tokens.get("orb_gradient_end", "#8B5CF6"))
            self._target_glow = 1.0
            self._target_particle = 2.5
            self._target_rotation_speed = 3000
        elif self._state == "error":
            self._target_gradient_start = QColor(tokens.get("danger", "#EF4444"))
            self._target_gradient_end = QColor(tokens.get("warning", "#F59E0B"))
            self._target_glow = 0.9
            self._target_particle = 1.5
            self._target_rotation_speed = 5000

        self._gradient_start = self._target_gradient_start
        self._gradient_end = self._target_gradient_end

        self._rotation_anim.setDuration(self._target_rotation_speed)

        glow_anim = QPropertyAnimation(self, b"glow_intensity")
        glow_anim.setDuration(anim_duration)
        glow_anim.setStartValue(self._glow_intensity)
        glow_anim.setEndValue(self._target_glow)
        glow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        glow_anim.start()

        particle_anim = QPropertyAnimation(self, b"particle_intensity")
        particle_anim.setDuration(anim_duration)
        particle_anim.setStartValue(self._particle_intensity)
        particle_anim.setEndValue(self._target_particle)
        particle_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        particle_anim.start()

    def get_glow_intensity(self): return self._glow_intensity
    def set_glow_intensity(self, v):
        self._glow_intensity = v
        self.update()
    glow_intensity = Property(float, get_glow_intensity, set_glow_intensity)

    def get_particle_intensity(self): return self._particle_intensity
    def set_particle_intensity(self, v):
        self._particle_intensity = v
        self.update()
    particle_intensity = Property(float, get_particle_intensity, set_particle_intensity)

    def set_theme_colors(self, start: QColor, end: QColor):
        """Called to explicitly set the base theme colors."""
        self._gradient_start = start
        self._gradient_end = end
        self.update()

    def set_colors(self, start: QColor, end: QColor):
        """Legacy support for set_colors."""
        self.set_theme_colors(start, end)

    def paintEvent(self, event):
        if self.width() < 10 or self.height() < 10:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx = self.width() / 2
        cy = self.height() / 2
        radius = min(cx, cy) * 0.78

        self._draw_outer_glow(p, cx, cy, radius)
        self._draw_ripple(p, cx, cy, radius)
        self._draw_ring(p, cx, cy, radius)
        self._draw_particles(p, cx, cy, radius)
        self._draw_orbs(p, cx, cy, radius)
        self._draw_core(p, cx, cy, radius)
        self._draw_state_label(p, cx, cy, radius)

    def _draw_outer_glow(self, painter, cx, cy, radius):
        glow_radius = radius * (1.8 + self._glow_intensity * 0.6 + self._breath_phase * 0.15)
        grad = QRadialGradient(cx, cy, glow_radius)
        start_c = QColor(self._gradient_start)
        end_c = QColor(self._gradient_end)
        
        # Idle state gets an extra ambient pulse
        ambient_alpha_boost = 10 if self._state == "idle" else 0
        
        start_c.setAlpha(int(self._glow_intensity * 30) + ambient_alpha_boost)
        end_c.setAlpha(0)
        grad.setColorAt(0.0, start_c)
        grad.setColorAt(0.3, QColor(self._gradient_start.red(), self._gradient_start.green(),
                                     self._gradient_start.blue(), int(self._glow_intensity * 15)))
        grad.setColorAt(1.0, end_c)
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_radius, glow_radius)

    def _draw_ripple(self, painter, cx, cy, radius):
        if self._ripple > 0.0 and self._ripple < 1.0:
            r = radius * (1.0 + self._ripple * 0.8)
            alpha = int(255 * (1.0 - self._ripple) * 0.6)
            c = QColor(self._gradient_start)
            c.setAlpha(alpha)
            painter.setPen(QPen(c, max(1, 4 * (1.0 - self._ripple))))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_ring(self, painter, cx, cy, radius):
        ring_radius = radius * 1.15
        base_color = QColor(self._gradient_start)
        base_color.setAlpha(40)
        painter.setPen(QPen(base_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), ring_radius, ring_radius)
        
        # Rotating segments
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._rotation * 0.5)
        
        grad = QConicalGradient(0, 0, 0)
        grad.setColorAt(0, QColor(255, 255, 255, 0))
        c_end = QColor(self._gradient_end)
        c_end.setAlpha(120)
        grad.setColorAt(0.5, c_end)
        grad.setColorAt(1, QColor(255, 255, 255, 0))
        
        painter.setPen(QPen(QBrush(grad), 2))
        painter.drawArc(QRectF(-ring_radius, -ring_radius, ring_radius*2, ring_radius*2), 0, 16 * 90)
        painter.drawArc(QRectF(-ring_radius, -ring_radius, ring_radius*2, ring_radius*2), 16 * 180, 16 * 90)
        painter.restore()

    def _draw_particles(self, painter, cx, cy, radius):
        if self._state == "idle":
            num_particles = 15
        elif self._state == "thinking":
            num_particles = 40
        elif self._state == "speaking":
            num_particles = 30
        elif self._state == "error":
            num_particles = 10
        else:
            num_particles = 25 # listening

        for i in range(num_particles):
            if i >= len(self._particles):
                break
            particle = self._particles[i]
            
            intensity = self._particle_intensity
            alpha = int(particle.alpha * intensity * 180)
            if alpha < 5:
                continue

            expansion_multiplier = 1.0
            if self._state == "speaking":
                expansion_multiplier = (1 + self._breath_phase * 0.6)
            elif self._state == "idle":
                expansion_multiplier = (1 + self._breath_phase * 0.3)

            particle.x += particle.vx * particle.speed * expansion_multiplier
            particle.y += particle.vy * particle.speed * expansion_multiplier
            particle.z += particle.vz * particle.speed

            if self._state == "error":
                # Jitter effect
                particle.x += random.uniform(-0.03, 0.03)
                particle.y += random.uniform(-0.03, 0.03)

            dist = math.sqrt(particle.x**2 + particle.y**2 + particle.z**2)
            if dist > 1.0:
                inv = 1.0 / dist
                particle.x *= inv * 0.99
                particle.y *= inv * 0.99
                particle.z *= inv * 0.99

            rot_speed_mult = 2.0 if self._state == "thinking" else 1.0
            rot_angle = math.radians(self._rotation * rot_speed_mult)
            xr = particle.x * math.cos(rot_angle) - particle.z * math.sin(rot_angle)
            zr = particle.x * math.sin(rot_angle) + particle.z * math.cos(rot_angle)
            scale = 1.0 / (1.0 + zr * 0.5)
            px = cx + xr * radius * 0.85 * scale
            py = cy + particle.y * radius * 0.85 * scale
            ps = max(1.0, particle.size * scale * intensity)

            color = QColor(self._gradient_start)
            color.setAlpha(alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(px, py), ps, ps)

    def _draw_orbs(self, painter, cx, cy, radius):
        orb_count = 3
        for i in range(orb_count):
            angle = math.radians(self._rotation + i * 120.0)
            orbit_radius = radius * (0.55 + self._breath_phase * 0.08)
            ox = cx + math.cos(angle) * orbit_radius
            oy = cy + math.sin(angle * 0.7) * orbit_radius * 0.5
            orb_size = radius * 0.08 * (1 + self._glow_intensity * 0.2)

            grad = QRadialGradient(ox, oy, orb_size * 1.5)
            c = QColor(self._gradient_end)
            c2 = QColor(self._gradient_start)
            grad.setColorAt(0.0, QColor(self._gradient_end.red(), self._gradient_end.green(),
                                         self._gradient_end.blue(), 200))
            grad.setColorAt(0.5, QColor(c.red(), c.green(), c.blue(), 100))
            grad.setColorAt(1.0, QColor(c2.red(), c2.green(), c2.blue(), 0))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(ox, oy), orb_size * 1.5, orb_size * 1.5)

            painter.setBrush(QColor(255, 255, 255, 60 + int(self._glow_intensity * 40)))
            painter.drawEllipse(QPointF(ox, oy), orb_size, orb_size)

    def _draw_core(self, painter, cx, cy, radius):
        core_radius = radius * (0.32 + self._breath_phase * 0.04)
        
        # Smoother inner glow
        grad = QRadialGradient(cx, cy, core_radius * 1.8)
        grad.setColorAt(0.0, QColor(255, 255, 255, 240))
        grad.setColorAt(0.15, QColor(255, 255, 255, 180))
        grad.setColorAt(0.4, QColor(self._gradient_start.red(), self._gradient_start.green(),
                                     self._gradient_start.blue(), 150))
        grad.setColorAt(0.7, QColor(self._gradient_end.red(), self._gradient_end.green(),
                                     self._gradient_end.blue(), 80))
        grad.setColorAt(1.0, QColor(self._gradient_end.red(), self._gradient_end.green(),
                                     self._gradient_end.blue(), 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), core_radius * 1.8, core_radius * 1.8)

        inner_grad = QRadialGradient(cx - core_radius * 0.2, cy - core_radius * 0.2, core_radius)
        inner_grad.setColorAt(0.0, QColor(255, 255, 255, 180))
        inner_grad.setColorAt(0.5, QColor(255, 255, 255, 80))
        inner_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(inner_grad))
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)

    def _draw_state_label(self, painter, cx, cy, radius):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setFont(QFont("Segoe UI Variable Display", 10))
        labels = {
            "idle": "Ready",
            "listening": "Listening...",
            "thinking": "Thinking...",
            "speaking": "Speaking...",
            "error": "Error",
        }
        label = labels.get(self._state, "")
        
        # Use theme text color for label
        text_color = self._text_primary
        text_color.setAlpha(120)
        painter.setPen(text_color)
        
        fm = QFontMetrics(painter.font())
        tw = fm.horizontalAdvance(label)
        painter.drawText(int(cx - tw / 2), int(cy + radius * 0.65), label)


class OrbContainerWidget(QWidget):
    """Container for the AI orb with state labels and control buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.orb = AIOrbWidget(self)
        self.orb.setMinimumSize(320, 320)
        self.orb.setMaximumSize(500, 500)
        layout.addWidget(self.orb, alignment=Qt.AlignmentFlag.AlignCenter)

        self._setup_mic_button()

    def _setup_mic_button(self):
        self.mic_button = QPushButton("🎤 Click to Speak", self)
        self.mic_button.setObjectName("primary")
        self.mic_button.setFixedHeight(40)
        self.mic_button.setFixedWidth(200)
        self.mic_button.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Use theme dynamic colors for mic button
        tokens = theme_manager.get_tokens()
        grad_start = tokens.get("orb_gradient_start", "#3B82F6")
        grad_end = tokens.get("orb_gradient_end", "#8B5CF6")
        
        self.mic_button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {grad_start}, stop:1 {grad_end});
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
                padding: 8px 24px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {grad_end}, stop:1 {grad_start});
            }}
        """)
        parent_layout = self.layout()
        if parent_layout:
            parent_layout.addWidget(self.mic_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_state(self, state: str):
        self.orb.set_state(state)
