"""8D Sound — превращает любой звук Windows в 8D."""
import json
import math
import os
import sys

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QInputDialog, QLabel, QMainWindow, QMenu, QPushButton, QSlider,
                               QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget, QListWidget, QListWidgetItem)

from engine import PATTERNS, SPLITS, Engine, demo_track
import appaudio
import winaudio
from icon import app_icon, render

VIOLET = QColor("#a855f7")
VIOLET_LIGHT = QColor("#d8b4fe")
PINK = QColor("#e879f9")
BG = QColor("#0b0614")

STYLE = """
QWidget { background: transparent; color: #e9dcff; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, #root { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #120822, stop:1 #07040d); }
#card { background: rgba(40, 18, 70, 0.55); border: 1px solid rgba(168, 85, 247, 0.25); border-radius: 18px; }
#title { font-size: 26px; font-weight: 800; color: #f3e8ff; letter-spacing: 4px; }
#subtitle { color: #9d7cc9; font-size: 12px; }
#section { color: #b794f6; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
#value { color: #d8b4fe; font-weight: 600; }
#hint { color: #8c6fb8; font-size: 11px; }
QPushButton { background: rgba(88, 28, 135, 0.45); border: 1px solid rgba(168, 85, 247, 0.4);
              border-radius: 12px; padding: 9px 14px; color: #f3e8ff; font-weight: 600; }
QPushButton:hover { background: rgba(126, 34, 206, 0.6); border-color: #c084fc; }
QPushButton:checked { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #c026d3);
                      border-color: #e879f9; }
#seg { font-size: 22px; font-weight: 800; padding: 14px; border-radius: 16px; }
#power { font-size: 16px; font-weight: 800; padding: 14px; border-radius: 16px;
         background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #c026d3); border: none; }
#power:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #d946ef); }
#power[on="true"] { background: rgba(88, 28, 135, 0.5); border: 1px solid #e879f9; }
QComboBox { background: rgba(30, 12, 55, 0.9); border: 1px solid rgba(168, 85, 247, 0.35);
            border-radius: 10px; padding: 7px 10px; }
QComboBox:hover { border-color: #c084fc; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #1a0b30; border: 1px solid #7c3aed; selection-background-color: #7c3aed;
                              color: #f3e8ff; outline: none; }
QSlider::groove:horizontal { height: 6px; background: rgba(168, 85, 247, 0.18); border-radius: 3px; }
QSlider::sub-page:horizontal { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #e879f9);
                               border-radius: 3px; }
QSlider::handle:horizontal { background: #f5d0fe; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px;
                             border: 2px solid #a855f7; }
QSlider::handle:horizontal:hover { background: #ffffff; }
QSlider::groove:vertical { width: 6px; background: rgba(168, 85, 247, 0.18); border-radius: 3px; }
QSlider::add-page:vertical { background: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #7c3aed, stop:1 #e879f9);
                             border-radius: 3px; }
QSlider::handle:vertical { background: #f5d0fe; width: 16px; height: 16px; margin: 0 -5px; border-radius: 8px;
                           border: 2px solid #a855f7; }
QSlider:disabled { opacity: 0.4; }
QSlider::sub-page:horizontal:disabled { background: rgba(168, 85, 247, 0.3); }
QTabWidget::pane { background: rgba(40, 18, 70, 0.55); border: 1px solid rgba(168, 85, 247, 0.25);
                   border-radius: 18px; top: -1px; }
QTabBar::tab { background: transparent; color: #9d7cc9; padding: 8px 16px; margin-right: 4px;
               border-top-left-radius: 10px; border-top-right-radius: 10px; font-weight: 700; }
QTabBar::tab:selected { background: rgba(124, 58, 237, 0.45); color: #f3e8ff; }
QTabBar::tab:hover { color: #f3e8ff; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 6px; border: 1px solid #a855f7;
                       background: rgba(30, 12, 55, 0.9); }
QCheckBox::indicator:checked { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #c026d3); }
QListWidget { background: rgba(30, 12, 55, 0.6); border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 10px;
              padding: 4px; outline: none; }
QListWidget::item { padding: 7px 6px; border-radius: 6px; }
QListWidget::item:hover { background: rgba(124, 58, 237, 0.3); }
QListWidget::indicator { width: 16px; height: 16px; border-radius: 5px; border: 1px solid #a855f7; }
QListWidget::indicator:checked { background: #a855f7; }
QToolTip { background: #1a0b30; color: #f3e8ff; border: 1px solid #7c3aed; }
QInputDialog, QMessageBox { background: #120822; }
QLineEdit { background: rgba(30, 12, 55, 0.9); border: 1px solid #7c3aed; border-radius: 8px; padding: 6px; }
"""
MENU_STYLE = """
QMenu { background: #1a0b30; color: #f3e8ff; border: 1px solid #7c3aed; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 6px 22px; border-radius: 6px; }
QMenu::item:selected { background: #7c3aed; }
QMenu::separator { height: 1px; background: rgba(168, 85, 247, 0.35); margin: 4px 8px; }
"""


class SpacePad(QWidget):
    """Круг вокруг головы слушателя: показывает и задаёт положение звука."""

    moved = Signal(float, float)
    vocal_moved = Signal(float, float)
    height = Signal(int)

    def __init__(self, engine, size=380, compact=False):
        super().__init__()
        self.engine = engine
        self.compact = compact
        self.setMinimumSize(size, size)
        self.trail = []
        self.spectrum = np.zeros(72)
        self.t = 0.0
        self.setCursor(Qt.OpenHandCursor)
        self.grab_vocal = False
        self.setMouseTracking(True)

    def geometry_(self):
        side = min(self.width(), self.height()) - 30
        c = QPointF(self.width() / 2, self.height() / 2)
        return c, side / 2

    def tick(self):
        self.t += 1 / 30
        if not self.engine.running:  # без звука двигаем точку сами
            self.engine._advance(1, 30)
        sc = self.engine.scope
        if self.engine.running:
            spec = np.abs(np.fft.rfft(sc * np.hanning(len(sc))))[1:400]
            edges = np.geomspace(1, len(spec), len(self.spectrum) + 1).astype(int)
            bands = np.array([spec[a:max(a + 1, b)].mean() for a, b in zip(edges[:-1], edges[1:])])
            bands = np.clip(np.log10(1 + bands * 4) / 1.6, 0, 1)
        else:
            bands = np.zeros_like(self.spectrum)
        self.spectrum = np.maximum(bands, self.spectrum * 0.86)
        x, y = self.engine.pos_xy if self.engine.mode_8d else (0.0, 0.0)
        self.trail.append((x, y))
        self.trail = self.trail[-40:]
        self.update()

    def _to_xy(self, pos):
        c, r = self.geometry_()
        x, y = (pos.x() - c.x()) / r, -(pos.y() - c.y()) / r
        k = math.hypot(x, y)
        if k > 1:
            x, y = x / k, y / k
        return x, y

    def _near_vocal(self, pos):
        if not (self.engine.mode_8d and self.engine.split == 2):
            return False
        c, r = self.geometry_()
        vx, vy = self.engine.vocal_xy
        return math.hypot(pos.x() - (c.x() + vx * r), pos.y() - (c.y() - vy * r)) < 24

    def mousePressEvent(self, e):
        self.setCursor(Qt.ClosedHandCursor)
        self.grab_vocal = self._near_vocal(e.position())
        (self.vocal_moved if self.grab_vocal else self.moved).emit(*self._to_xy(e.position()))

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            (self.vocal_moved if self.grab_vocal else self.moved).emit(*self._to_xy(e.position()))
        else:
            self.setCursor(Qt.PointingHandCursor if self._near_vocal(e.position()) else Qt.OpenHandCursor)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ShiftModifier:
            d = e.angleDelta().y() or e.angleDelta().x()
            self.height.emit(10 if d > 0 else -10)
            return
        x, y = self.engine.pos_xy
        r = max(0.15, math.hypot(x, y))
        a = math.atan2(x, y) + math.radians(e.angleDelta().y() / 120 * 10)
        self.moved.emit(math.sin(a) * r, math.cos(a) * r)

    def mouseReleaseEvent(self, e):
        self.grab_vocal = False
        self.setCursor(Qt.OpenHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c, r = self.geometry_()

        g = QRadialGradient(c, r)
        g.setColorAt(0, QColor(70, 25, 120, 160))
        g.setColorAt(0.7, QColor(30, 10, 60, 120))
        g.setColorAt(1, QColor(15, 5, 30, 40))
        p.setBrush(g)
        p.setPen(QPen(QColor(168, 85, 247, 120), 1.5))
        p.drawEllipse(c, r, r)

        p.setBrush(Qt.NoBrush)
        for k in (0.33, 0.66):
            p.setPen(QPen(QColor(168, 85, 247, 50), 1, Qt.DashLine))
            p.drawEllipse(c, r * k, r * k)
        p.setPen(QPen(QColor(168, 85, 247, 40), 1))
        p.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - r), QPointF(c.x(), c.y() + r))

        # волна-пульс
        pulse = (self.t * 0.6) % 1.0
        if self.engine.running and self.engine.mode_8d:
            p.setPen(QPen(QColor(232, 121, 249, int(90 * (1 - pulse))), 2))
            p.drawEllipse(c, r * pulse, r * pulse)

        # спектр вокруг головы
        inner = r * 0.2
        n = len(self.spectrum)
        for i, v in enumerate(self.spectrum):
            a = 2 * math.pi * i / n - math.pi / 2 + self.t * 0.15
            ln = inner + 6 + v * r * 0.3
            col = QColor(VIOLET).lighter(100 + int(v * 60))
            col.setAlpha(80 + int(v * 175))
            p.setPen(QPen(col, 3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(c.x() + math.cos(a) * (inner + 4), c.y() + math.sin(a) * (inner + 4)),
                       QPointF(c.x() + math.cos(a) * ln, c.y() + math.sin(a) * ln))

        # голова
        p.setPen(QPen(VIOLET_LIGHT, 2))
        hg = QRadialGradient(c, inner)
        hg.setColorAt(0, QColor(90, 40, 150))
        hg.setColorAt(1, QColor(40, 15, 70))
        p.setBrush(hg)
        head = r * 0.11
        p.drawEllipse(QPointF(c.x() - head, c.y()), head * 0.22, head * 0.42)
        p.drawEllipse(QPointF(c.x() + head, c.y()), head * 0.22, head * 0.42)
        p.drawEllipse(c, head, head)
        nose = QPainterPath()
        nose.moveTo(c.x() - head * 0.25, c.y() - head * 0.92)
        nose.lineTo(c.x(), c.y() - head * 1.35)
        nose.lineTo(c.x() + head * 0.25, c.y() - head * 0.92)
        p.drawPath(nose)

        # подписи
        p.setPen(QColor(183, 148, 246, 170))
        f = QFont("Segoe UI", 9, QFont.Bold)
        p.setFont(f)
        labels = (("ПЕРЕД", 0, -1), ("ЗАД", 0, 1), ("Л", -1, 0), ("П", 1, 0))
        for txt, dx, dy in labels if not self.compact else ():
            rect = QRectF(c.x() + dx * (r - 22) - 30, c.y() + dy * (r - 14) - 10, 60, 20)
            p.drawText(rect, Qt.AlignCenter, txt)

        # хвост и источник
        def pt(xy):
            return QPointF(c.x() + xy[0] * r, c.y() - xy[1] * r)

        for i, xy in enumerate(self.trail[:-1]):
            k = i / len(self.trail)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(232, 121, 249, int(120 * k)))
            p.drawEllipse(pt(xy), 3 + 6 * k, 3 + 6 * k)
        def extra_dot(xy, label):
            q = pt(xy)
            g2 = QRadialGradient(q, 26)
            g2.setColorAt(0, QColor(196, 181, 253, 200))
            g2.setColorAt(1, QColor(124, 58, 237, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g2)
            p.drawEllipse(q, 26, 26)
            p.setBrush(QColor("#ede9fe"))
            p.setPen(QPen(VIOLET, 2))
            p.drawEllipse(q, 6, 6)
            if not self.compact:
                p.setPen(QColor("#c4b5fd"))
                p.setFont(QFont("Segoe UI", 8, QFont.Bold))
                p.drawText(QPointF(q.x() + 10, q.y() + 16), label)

        if self.trail and self.engine.mode_8d:
            if self.engine.split == 1:
                x, y = self.trail[-1]
                extra_dot((-x, -y), "верха")
            elif self.engine.split == 2:
                extra_dot(self.engine.vocal_xy, "голос")

        if self.trail:
            s = pt(self.trail[-1])
            lvl = min(1.0, self.engine.level * 6)
            glow = QRadialGradient(s, 34 + 20 * lvl)
            glow.setColorAt(0, QColor(240, 171, 252, 230))
            glow.setColorAt(0.35, QColor(192, 38, 211, 120))
            glow.setColorAt(1, QColor(124, 58, 237, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(s, 34 + 20 * lvl, 34 + 20 * lvl)
            z = self.engine.pos_z if self.engine.mode_8d else 0.0
            rad = 9 * (1 + 0.45 * z)
            p.setBrush(QColor("#fdf4ff"))
            p.setPen(QPen(PINK, 3))
            p.drawEllipse(s, rad, rad)
            if abs(z) > 0.04 and not self.compact:
                p.setPen(QColor("#f5d0fe"))
                p.setFont(QFont("Segoe UI", 9, QFont.Bold))
                p.drawText(QPointF(s.x() + 16, s.y() - 12), f"{'↑' if z > 0 else '↓'} {abs(z) * 100:.0f}%")


class Meter(QWidget):
    def __init__(self, getter):
        super().__init__()
        self.getter = getter
        self.v = 0.0
        self.setFixedHeight(8)

    def tick(self):
        lvl = min(1.0, math.sqrt(max(self.getter(), 0.0)) * 2.2)
        self.v = max(lvl, self.v * 0.9)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(168, 85, 247, 40))
        p.drawRoundedRect(self.rect(), 4, 4)
        g = QLinearGradient(0, 0, self.width(), 0)
        g.setColorAt(0, QColor("#7c3aed"))
        g.setColorAt(1, QColor("#e879f9"))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(0, 0, self.width() * self.v, self.height()), 4, 4)


def fmt_time(sec):
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def labeled_slider(title, lo, hi, val, fmt):
    box = QVBoxLayout()
    box.setSpacing(4)
    head = QHBoxLayout()
    t = QLabel(title.upper())
    t.setObjectName("section")
    v = QLabel()
    v.setObjectName("value")
    head.addWidget(t)
    head.addStretch()
    head.addWidget(v)
    s = QSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.valueChanged.connect(lambda x: v.setText(fmt(x)))
    s.setValue(val)
    v.setText(fmt(val))
    box.addLayout(head)
    box.addWidget(s)
    return box, s


def card():
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(12)
    return f, lay


class MiniPlayer(QWidget):
    """Маленькое окно поверх всех окон: круг, вкл/выкл, 2D/8D, пауза."""

    def __init__(self, main):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.main = main
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("8D Sound — мини")
        self.drag = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 14)
        lay.setSpacing(8)

        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(render(22))
        self.title = QLabel("8D SOUND")
        self.title.setObjectName("section")
        bmax = QPushButton("⤢")
        bmax.setToolTip("Открыть полное окно")
        bmax.clicked.connect(self.expand)
        bclose = QPushButton("✕")
        bclose.setToolTip("Свернуть в трей")
        bclose.clicked.connect(self.hide)
        for b in (bmax, bclose):
            b.setObjectName("mini")
            b.setFixedSize(28, 28)
            b.setCursor(Qt.PointingHandCursor)
        top.addWidget(logo)
        top.addWidget(self.title)
        top.addStretch()
        top.addWidget(bmax)
        top.addWidget(bclose)
        lay.addLayout(top)

        self.pad = SpacePad(main.engine, 200, compact=True)
        self.pad.moved.connect(main.on_pad)
        self.pad.height.connect(main.on_pad_height)
        self.pad.vocal_moved.connect(main.on_vocal)
        lay.addWidget(self.pad, 1)

        row = QHBoxLayout()
        self.bpower = QPushButton("⏻")
        self.bpower.setToolTip("Включить / выключить")
        self.bpower.clicked.connect(main.toggle)
        self.bmode = QPushButton("8D")
        self.bmode.setToolTip("Переключить 2D / 8D")
        self.bmode.clicked.connect(lambda: main.set_mode(not main.engine.mode_8d))
        self.bplay = QPushButton("▶")
        self.bplay.setToolTip("Плеер: пауза / играть")
        self.bplay.clicked.connect(main.play_pause)
        for b in (self.bpower, self.bmode, self.bplay):
            b.setCheckable(b is not self.bplay)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(38)
            row.addWidget(b)
        lay.addLayout(row)
        self.setStyleSheet(STYLE + """
            #mini { padding: 0; border-radius: 8px; font-size: 13px; }
        """)
        self.resize(250, 320)
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.right() - 270, scr.bottom() - 340)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, QColor(30, 12, 55, 240))
        g.setColorAt(1, QColor(10, 5, 20, 245))
        p.setBrush(g)
        p.setPen(QPen(QColor(168, 85, 247, 140), 1.2))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 20, 20)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self.drag)

    def mouseReleaseEvent(self, e):
        self.drag = None

    def expand(self):
        self.hide()
        self.main.show_window()

    def tick(self):
        self.pad.tick()
        e = self.main.engine
        playing = e.running and e.source == "file" and e.playing
        self.bplay.setText("❚❚" if playing else "▶")

    def refresh(self):
        e = self.main.engine
        self.bpower.setChecked(e.running)
        self.bmode.setChecked(e.mode_8d)
        self.bmode.setText("8D" if e.mode_8d else "2D")
        self.title.setText("8D SOUND · " + ("в эфире" if e.running else "выкл"))


PRESETS = {
    "Классика 8D": dict(pattern=0, speed=12, dist=75, room=25, elev=0, wobble=0, eq=[0, 0, 0, 0, 0], bass=0, rate=100),
    "Концертный зал": dict(pattern=0, speed=6, dist=95, room=80, elev=10, wobble=10, eq=[1, 0, 0, 1, 2], bass=2, rate=100),
    "Шёпот у уха": dict(pattern=2, speed=20, dist=22, room=5, elev=0, wobble=0, eq=[0, 0, 2, 4, 3], bass=0, rate=100),
    "Под водой": dict(pattern=0, speed=5, dist=60, room=45, elev=-20, wobble=15, eq=[4, 2, -6, -14, -18], bass=4, rate=100),
    "Космос": dict(pattern=3, speed=8, dist=100, room=100, elev=20, wobble=60, eq=[0, 0, 0, 2, 4], bass=2, rate=100),
    "Slowed + reverb": dict(pattern=0, speed=8, dist=70, room=70, elev=0, wobble=0, eq=[2, 1, 0, -1, -2], bass=3, rate=82),
    "Nightcore": dict(pattern=0, speed=22, dist=70, room=30, elev=10, wobble=0, eq=[0, 0, 1, 3, 4], bass=2, rate=125),
    "Бас-качалка": dict(pattern=1, speed=15, dist=65, room=20, elev=0, wobble=20, eq=[6, 2, 0, 1, 2], bass=8, rate=100),
}

BUFFERS = [(20, "20 мс — минимум задержки"), (50, "50 мс — баланс"), (100, "100 мс — стабильно"),
           (200, "200 мс — очень стабильно"), (300, "300 мс"), (500, "500 мс — для слабых ПК"),
           (1000, "1000 мс — максимум стабильности")]

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pyw}" "{os.path.abspath(__file__)}" --tray'


def autostart_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, "8D Sound")
            return True
    except OSError:
        return False


def set_autostart(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "8D Sound", 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, "8D Sound")
            except OSError:
                pass


class Main(QMainWindow):
    def __init__(self, tray_start=False):
        super().__init__()
        self.engine = Engine()
        self.settings = QSettings("6ixl", "8D Sound")
        self.quitting = False
        self.silent_ticks = 0
        self.app_tick = 0
        self.mini = None
        self.routed_pids = set()
        self.selected_apps = set()
        self.setWindowTitle("8D Sound")
        self.setWindowIcon(app_icon())
        self.resize(1120, 780)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(22, 20, 22, 20)
        main.setSpacing(20)

        # ---- левая колонка: площадка и плеер ----
        left = QVBoxLayout()
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(render(44))
        title = QLabel("8D SOUND")
        title.setObjectName("title")
        head.addWidget(logo)
        head.addWidget(title)
        head.addStretch()
        bmini = QPushButton("▣  Мини-плеер")
        bmini.setCursor(Qt.PointingHandCursor)
        bmini.setToolTip("Маленькое окно поверх всех окон")
        bmini.clicked.connect(self.show_mini)
        head.addWidget(bmini)
        left.addLayout(head)
        self.status = QLabel()
        self.status.setObjectName("subtitle")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.pad = SpacePad(self.engine)
        self.pad.moved.connect(self.on_pad)
        self.pad.height.connect(self.on_pad_height)
        self.pad.vocal_moved.connect(self.on_vocal)
        left.addWidget(self.pad, 1)
        hint = QLabel("Тащи точку мышкой · колёсико — вращать · Shift + колёсико — высота")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignCenter)
        left.addWidget(hint)

        pc, pl = card()
        top = QHBoxLayout()
        self.bplay = QPushButton("▶")
        self.bplay.setObjectName("seg")
        self.bplay.setFixedSize(58, 58)
        self.bplay.setCursor(Qt.PointingHandCursor)
        self.bplay.clicked.connect(self.play_pause)
        top.addWidget(self.bplay)
        info = QVBoxLayout()
        self.track_lbl = QLabel("Файл не выбран — открой музыку или перетащи её в окно")
        self.track_lbl.setObjectName("value")
        self.time_lbl = QLabel("0:00 / 0:00")
        self.time_lbl.setObjectName("hint")
        info.addWidget(self.track_lbl)
        info.addWidget(self.time_lbl)
        top.addLayout(info, 1)
        bopen = QPushButton("📂  Открыть")
        bopen.clicked.connect(self.open_file)
        btest = QPushButton("🎧  Тест 8D")
        btest.clicked.connect(self.play_demo)
        for b in (bopen, btest):
            b.setCursor(Qt.PointingHandCursor)
            top.addWidget(b)
        pl.addLayout(top)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.sliderReleased.connect(self.do_seek)
        pl.addWidget(self.seek)
        left.addWidget(pc)
        main.addLayout(left, 3)
        self.setAcceptDrops(True)

        # ---- правая колонка ----
        right = QVBoxLayout()
        right.setSpacing(12)

        c1, l1 = card()
        seg = QHBoxLayout()
        self.b2d = QPushButton("2D")
        self.b8d = QPushButton("8D")
        for b in (self.b2d, self.b8d):
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            seg.addWidget(b)
        self.b2d.clicked.connect(lambda: self.set_mode(False))
        self.b8d.clicked.connect(lambda: self.set_mode(True))
        l1.addLayout(seg)
        prow = QHBoxLayout()
        self.preset = QComboBox()
        self.preset.activated.connect(lambda _: self.apply_preset(self.preset.currentText()))
        bsave = QPushButton("💾")
        bsave.setToolTip("Сохранить текущие настройки как свой пресет")
        bsave.clicked.connect(self.save_preset)
        bdel = QPushButton("🗑")
        bdel.setToolTip("Удалить свой пресет")
        bdel.clicked.connect(self.delete_preset)
        for b in (bsave, bdel):
            b.setFixedWidth(46)
            b.setCursor(Qt.PointingHandCursor)
        prow.addWidget(self.preset, 1)
        prow.addWidget(bsave)
        prow.addWidget(bdel)
        l1.addLayout(prow)
        right.addWidget(c1)

        self.tabs = QTabWidget()
        right.addWidget(self.tabs, 1)

        # вкладка «Движение»
        t1, m1 = self.tab("Движение")
        mv = QHBoxLayout()
        self.bauto = QPushButton("⟳  Авто")
        self.bhand = QPushButton("✋  Вручную")
        for b in (self.bauto, self.bhand):
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            mv.addWidget(b)
        self.bauto.clicked.connect(lambda: self.set_auto(True))
        self.bhand.clicked.connect(lambda: self.set_auto(False))
        m1.addLayout(mv)
        self.pattern = QComboBox()
        self.pattern.addItems(PATTERNS)
        self.pattern.currentIndexChanged.connect(lambda i: setattr(self.engine, "pattern", i))
        m1.addWidget(self.pattern)
        self.split = QComboBox()
        self.split.addItems(SPLITS)
        self.split.setToolTip("Разделить музыку на несколько источников в пространстве")
        self.split.currentIndexChanged.connect(self.split_changed)
        m1.addWidget(self.split)
        self.vocal_box = QWidget()
        vb = QVBoxLayout(self.vocal_box)
        vb.setContentsMargins(0, 0, 0, 0)
        vb.setSpacing(8)
        self.cb_vocal = QCheckBox("Вокал тоже вращается")
        self.cb_vocal.toggled.connect(lambda on: (setattr(self.engine, "vocal_auto", on), self.refresh()))
        vb.addWidget(self.cb_vocal)
        self.s_vspeed = self.slider(vb, "Вращение вокала", -50, 50, -10,
                                    lambda v: "стоит" if v == 0 else
                                    f"{100 / abs(v):.1f} с/оборот {'↻' if v > 0 else '↺'}",
                                    lambda v: setattr(self.engine, "vocal_speed", v / 100))
        m1.addWidget(self.vocal_box)
        self.s_speed = self.slider(m1, "Скорость", 2, 60, 12, lambda v: f"{100 / v:.1f} с/оборот",
                                   lambda v: setattr(self.engine, "speed", v / 100))
        self.s_dist = self.slider(m1, "Дистанция", 15, 100, 75, lambda v: f"{v}%",
                                  lambda v: setattr(self.engine, "distance", v / 100))
        self.s_elev = self.slider(m1, "Высота", -100, 100, 0,
                                  lambda v: "по уровню ушей" if v == 0 else (f"↑ {v}%" if v > 0 else f"↓ {-v}%"),
                                  lambda v: setattr(self.engine, "elevation", v / 100))
        self.s_wob = self.slider(m1, "Качание вверх-вниз", 0, 100, 0, lambda v: "выкл" if v == 0 else f"{v}%",
                                 lambda v: setattr(self.engine, "elev_wobble", v / 100))
        m1.addStretch()

        # вкладка «Звук»
        t2, m2 = self.tab("Звук")
        self.s_room = self.slider(m2, "Пространство (реверб)", 0, 100, 25, lambda v: f"{v}%",
                                  lambda v: setattr(self.engine, "room", v / 100))
        self.s_vol = self.slider(m2, "Громкость", 0, 150, 90, lambda v: f"{v}%",
                                 lambda v: setattr(self.engine, "volume", v / 100))
        self.s_rate = self.slider(m2, "Slowed ↔ Nightcore (только файл)", 60, 150, 100,
                                  lambda v: "обычная скорость" if v == 100 else
                                  (f"slowed {v}%" if v < 100 else f"nightcore {v}%"),
                                  lambda v: setattr(self.engine, "rate", v / 100))
        sec = QLabel("ЭКВАЛАЙЗЕР")
        sec.setObjectName("section")
        m2.addWidget(sec)
        eqrow = QHBoxLayout()
        self.eq_sliders = []
        names = ["Бас+", "60", "250", "1k", "4k", "12k"]
        for i, name in enumerate(names):
            col = QVBoxLayout()
            val = QLabel("0")
            val.setObjectName("value")
            val.setAlignment(Qt.AlignCenter)
            s = QSlider(Qt.Vertical)
            s.setRange(-12 if i else 0, 12)
            s.setFixedHeight(110)
            s.valueChanged.connect(lambda v, lb=val: lb.setText(f"{v:+d}" if v else "0"))
            s.valueChanged.connect(self.eq_changed)
            lb = QLabel(name)
            lb.setObjectName("hint")
            lb.setAlignment(Qt.AlignCenter)
            col.addWidget(val)
            col.addWidget(s, 0, Qt.AlignHCenter)
            col.addWidget(lb)
            eqrow.addLayout(col)
            self.eq_sliders.append(s)
        m2.addLayout(eqrow)
        beq = QPushButton("Сбросить эквалайзер")
        beq.setCursor(Qt.PointingHandCursor)
        beq.clicked.connect(lambda: [s.setValue(0) for s in self.eq_sliders])
        m2.addWidget(beq)
        m2.addStretch()

        # вкладка «Источник»
        t0, m0 = self.tab("Источник", 0)
        src = QHBoxLayout()
        self.bsys = QPushButton("🖥  Весь ПК")
        self.bapps = QPushButton("🎯  Программы")
        self.bfile = QPushButton("🎵  Файл")
        for b in (self.bsys, self.bapps, self.bfile):
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            src.addWidget(b)
        self.bsys.clicked.connect(lambda: self.set_source("system"))
        self.bapps.clicked.connect(lambda: self.set_source("apps"))
        self.bfile.clicked.connect(lambda: self.set_source("file"))
        m0.addLayout(src)
        self.src_hint = QLabel()
        self.src_hint.setObjectName("hint")
        self.src_hint.setWordWrap(True)
        m0.addWidget(self.src_hint)
        self.apps_list = QListWidget()
        self.apps_list.itemChanged.connect(self.apps_changed)
        m0.addWidget(self.apps_list, 1)
        self.bref_apps = QPushButton("↻  Обновить список программ")
        self.bref_apps.setCursor(Qt.PointingHandCursor)
        self.bref_apps.clicked.connect(self.load_apps)
        m0.addWidget(self.bref_apps)
        m0.addStretch()

        # вкладка «Настройки»
        t3, m3 = self.tab("Настройки")
        self.cin = QComboBox()
        self.cout = QComboBox()
        self.cin_lbl = QLabel("Откуда брать (VB-Cable Output)")
        self.cin_lbl.setObjectName("hint")
        m3.addWidget(self.cin_lbl)
        m3.addWidget(self.cin)
        lab = QLabel("Куда выводить (твои наушники)")
        lab.setObjectName("hint")
        m3.addWidget(lab)
        m3.addWidget(self.cout)
        lab = QLabel("Буфер (больше — стабильнее, меньше — без задержки)")
        lab.setObjectName("hint")
        m3.addWidget(lab)
        self.buffer = QComboBox()
        for ms, text in BUFFERS:
            self.buffer.addItem(text, ms)
        self.buffer.setCurrentIndex(1)
        m3.addWidget(self.buffer)
        row = QHBoxLayout()
        win = QPushButton("⚙  Звук Windows")
        win.clicked.connect(lambda: os.startfile("ms-settings:sound"))
        ref = QPushButton("↻")
        ref.setFixedWidth(46)
        ref.setToolTip("Обновить список устройств")
        ref.clicked.connect(self.load_devices)
        for b in (win, ref):
            b.setCursor(Qt.PointingHandCursor)
        row.addWidget(win, 1)
        row.addWidget(ref)
        m3.addLayout(row)
        self.cb_auto = QCheckBox("Запускать вместе с Windows (в трее)")
        self.cb_auto.setChecked(autostart_enabled())
        self.cb_auto.toggled.connect(self.toggle_autostart)
        self.cb_tray = QCheckBox("Крестик сворачивает в трей")
        self.cb_tray.setChecked(True)
        m3.addWidget(self.cb_auto)
        m3.addWidget(self.cb_tray)
        m3.addStretch()

        # индикаторы
        self.meters = []
        mbox = QHBoxLayout()
        for name, getter in (("Вход", lambda: self.engine.in_level), ("Выход", lambda: self.engine.level)):
            lb = QLabel(name)
            lb.setObjectName("hint")
            m = Meter(getter)
            self.meters.append(m)
            mbox.addWidget(lb)
            mbox.addWidget(m, 1)
        right.addLayout(mbox)

        self.power = QPushButton()
        self.power.setObjectName("power")
        self.power.setCursor(Qt.PointingHandCursor)
        self.power.clicked.connect(self.toggle)
        right.addWidget(self.power)
        reset = QPushButton("↺  Сбросить настройки")
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self.reset)
        right.addWidget(reset)
        main.addLayout(right, 2)

        self.setStyleSheet(STYLE)
        self.load_devices()
        self.restore()
        try:
            self.selected_apps = set(json.loads(self.settings.value("apps", "[]")))
        except (TypeError, ValueError):
            self.selected_apps = set()
        self.load_apps()
        self.tabs.setCurrentIndex(0)
        self.reload_presets()
        self.cin.currentIndexChanged.connect(self.devices_changed)
        self.cout.currentIndexChanged.connect(self.devices_changed)
        self.buffer.currentIndexChanged.connect(self.buffer_changed)
        self.buffer_changed()

        self.make_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
        self.refresh()
        if tray_start and self.settings.value("was_running", "false") == "true":
            self.start()

    # ---------- построение ----------
    def tab(self, name, index=-1):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 12)
        lay.setSpacing(12)
        self.tabs.insertTab(index, w, name)
        return w, lay

    def slider(self, layout, title, lo, hi, val, fmt, on_change):
        box, s = labeled_slider(title, lo, hi, val, fmt)
        s.valueChanged.connect(on_change)
        on_change(val)
        layout.addLayout(box)
        return s

    def make_tray(self):
        self.tray = QSystemTrayIcon(app_icon(False), self)
        menu = QMenu()
        menu.setStyleSheet(MENU_STYLE)
        self.m_show = menu.addAction("Открыть 8D Sound", self.show_window)
        menu.addAction("Мини-плеер", self.show_mini)
        menu.addSeparator()
        self.m_power = menu.addAction("Включить", self.toggle)
        self.m_mode = menu.addAction("Режим 8D", lambda: self.set_mode(not self.engine.mode_8d))
        self.m_mode.setCheckable(True)
        self.m_presets = menu.addMenu("Пресеты")
        menu.addSeparator()
        menu.addAction("Выход", self.quit_app)
        self.tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.show_window() if r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
        self.tray.show()

    # ---------- трей / окно ----------
    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self.quitting = True
        self.close()

    def closeEvent(self, e):
        if self.cb_tray.isChecked() and not self.quitting:
            e.ignore()
            self.hide()
            if not self.settings.value("tray_hint_shown"):
                self.tray.showMessage("8D Sound", "Я свернулся в трей и продолжаю работать.", app_icon(), 3000)
                self.settings.setValue("tray_hint_shown", True)
            return
        self.save_settings()
        self.engine.stop()
        self.route_windows(False)
        self.unroute_apps()
        if self.mini:
            self.mini.close()
        self.tray.hide()
        e.accept()
        QApplication.quit()

    def toggle_autostart(self, on):
        try:
            set_autostart(on)
        except OSError as ex:
            self.engine.error = f"Автозапуск: {ex}"
            self.refresh()

    # ---------- программы ----------
    def load_apps(self):
        try:
            playing = appaudio.sessions()
        except Exception:  # noqa: BLE001
            playing = {}
        names = sorted(set(playing) | self.selected_apps, key=str.lower)
        self.apps_list.blockSignals(True)
        self.apps_list.clear()
        for exe in names:
            item = QListWidgetItem(("🔊  " if exe in playing else "      ") + appaudio.pretty(exe))
            item.setData(Qt.UserRole, exe)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if exe in self.selected_apps else Qt.Unchecked)
            self.apps_list.addItem(item)
        if not names:
            item = QListWidgetItem("Сейчас ни одна программа не играет звук")
            item.setFlags(Qt.NoItemFlags)
            self.apps_list.addItem(item)
        self.apps_list.blockSignals(False)

    def apps_changed(self, item):
        exe = item.data(Qt.UserRole)
        if not exe:
            return
        if item.checkState() == Qt.Checked:
            self.selected_apps.add(exe)
        else:
            self.selected_apps.discard(exe)
            if self.engine.running and self.engine.source == "apps":
                appaudio.route_apps([exe], None)
                self.routed_pids = {p for p in self.routed_pids if p[0] != exe}
        if self.engine.running and self.engine.source == "apps":
            self.route_selected_apps()
        self.refresh()

    def route_selected_apps(self):
        cable = winaudio.find_output("CABLE Input")
        if not cable:
            return
        for exe in self.selected_apps:
            for pid in appaudio._pids_of(exe):
                if (exe, pid) in self.routed_pids:
                    continue
                try:
                    appaudio._set_persisted(pid, cable)
                    self.routed_pids.add((exe, pid))
                except OSError:
                    pass  # у процесса пока нет звука — попробуем позже

    def unroute_apps(self):
        for _, pid in self.routed_pids:
            try:
                appaudio._set_persisted(pid, None)
            except OSError:
                pass
        self.routed_pids = set()

    # ---------- мини-плеер ----------
    def show_mini(self):
        if self.mini is None:
            self.mini = MiniPlayer(self)
        self.hide()
        self.mini.show()
        self.mini.raise_()
        self.mini.refresh()

    # ---------- пресеты ----------
    def custom_presets(self):
        try:
            return json.loads(self.settings.value("custom_presets", "{}"))
        except (TypeError, ValueError):
            return {}

    def reload_presets(self):
        cur = self.preset.currentText()
        self.preset.clear()
        self.preset.addItem("— Пресет —")
        for name in PRESETS:
            self.preset.addItem(name)
        for name in self.custom_presets():
            self.preset.addItem("★ " + name)
        if cur and self.preset.findText(cur) >= 0:
            self.preset.setCurrentText(cur)
        self.m_presets_fill()

    def m_presets_fill(self):
        if not hasattr(self, "m_presets"):
            return
        self.m_presets.clear()
        for i in range(1, self.preset.count()):
            name = self.preset.itemText(i)
            self.m_presets.addAction(name, lambda n=name: self.apply_preset(n))

    def current_values(self):
        return dict(pattern=self.pattern.currentIndex(), speed=self.s_speed.value(), dist=self.s_dist.value(),
                    room=self.s_room.value(), elev=self.s_elev.value(), wobble=self.s_wob.value(),
                    eq=[s.value() for s in self.eq_sliders[1:]], bass=self.eq_sliders[0].value(),
                    rate=self.s_rate.value())

    def apply_preset(self, name):
        p = PRESETS.get(name) or self.custom_presets().get(name.removeprefix("★ "))
        if not p:
            return
        self.pattern.setCurrentIndex(p["pattern"])
        self.s_speed.setValue(p["speed"])
        self.s_dist.setValue(p["dist"])
        self.s_room.setValue(p["room"])
        self.s_elev.setValue(p["elev"])
        self.s_wob.setValue(p["wobble"])
        self.eq_sliders[0].setValue(p["bass"])
        for s, v in zip(self.eq_sliders[1:], p["eq"]):
            s.setValue(v)
        self.s_rate.setValue(p["rate"])
        self.engine.mode_8d = True
        self.set_auto(True)
        self.preset.setCurrentText(name)

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Свой пресет", "Название:")
        name = name.strip()
        if ok and name:
            data = self.custom_presets()
            data[name] = self.current_values()
            self.settings.setValue("custom_presets", json.dumps(data, ensure_ascii=False))
            self.reload_presets()
            self.preset.setCurrentText("★ " + name)

    def delete_preset(self):
        name = self.preset.currentText()
        if not name.startswith("★ "):
            self.status.setText("Удалять можно только свои пресеты (со ★).")
            return
        data = self.custom_presets()
        data.pop(name[2:], None)
        self.settings.setValue("custom_presets", json.dumps(data, ensure_ascii=False))
        self.reload_presets()
        self.preset.setCurrentIndex(0)

    # ---------- логика ----------
    def eq_changed(self):
        self.engine.bass = float(self.eq_sliders[0].value())
        self.engine.eq = [float(s.value()) for s in self.eq_sliders[1:]]

    def buffer_changed(self):
        self.engine.buffer_ms = self.buffer.currentData()
        if self.engine.running:
            self.start()

    def load_devices(self):
        ins, outs, default_out = Engine.wasapi_devices()
        cur_in, cur_out = self.cin.currentText(), self.cout.currentText()
        for combo, items in ((self.cin, ins), (self.cout, outs)):
            combo.blockSignals(True)
            combo.clear()
            for i, name in items:
                combo.addItem(name, i)
            combo.blockSignals(False)
        pick_in = cur_in or next((n for _, n in ins if "CABLE Output" in n), "")
        default_name = next((n for i, n in outs if i == default_out and "CABLE" not in n), "")
        vxe = next((n for _, n in outs if "VXE V1" in n), "")
        pick_out = cur_out or vxe or default_name or next((n for _, n in outs if "CABLE" not in n), "")
        if pick_in:
            self.cin.setCurrentText(pick_in)
        if pick_out:
            self.cout.setCurrentText(pick_out)

    SLIDERS = ("speed", "dist", "room", "vol", "elev", "wob", "rate")

    def slider_map(self):
        return dict(zip(self.SLIDERS, (self.s_speed, self.s_dist, self.s_room, self.s_vol, self.s_elev,
                                       self.s_wob, self.s_rate)))

    def restore(self):
        s = self.settings
        for key, w in self.slider_map().items():
            if s.contains(key):
                w.setValue(int(s.value(key)))
        for i, sl in enumerate(self.eq_sliders):
            if s.contains(f"eq{i}"):
                sl.setValue(int(s.value(f"eq{i}")))
        self.pattern.setCurrentIndex(int(s.value("pattern", 0)))
        self.split.setCurrentIndex(int(s.value("split", 0)))
        self.cb_vocal.setChecked(s.value("vocal_auto", "false") == "true")
        self.s_vspeed.setValue(int(s.value("vspeed", -10)))
        try:
            self.engine.vocal_xy = tuple(json.loads(s.value("vocal", "[0.0, 0.25]")))
        except (TypeError, ValueError):
            pass
        self.buffer.setCurrentIndex(int(s.value("buffer", 1)))
        for key, combo in (("in", self.cin), ("out", self.cout)):
            name = s.value(key, "")
            if name and combo.findText(name) >= 0:
                combo.setCurrentText(name)
        self.engine.source = s.value("source", "system")
        self.engine.mode_8d = s.value("mode8d", "true") == "true"
        self.engine.auto = s.value("auto", "true") == "true"
        self.cb_tray.setChecked(s.value("close_to_tray", "true") == "true")

    def save_settings(self):
        s = self.settings
        for key, w in self.slider_map().items():
            s.setValue(key, w.value())
        for i, sl in enumerate(self.eq_sliders):
            s.setValue(f"eq{i}", sl.value())
        s.setValue("pattern", self.pattern.currentIndex())
        s.setValue("split", self.split.currentIndex())
        s.setValue("vocal_auto", "true" if self.engine.vocal_auto else "false")
        s.setValue("vspeed", self.s_vspeed.value())
        s.setValue("vocal", json.dumps(list(self.engine.vocal_xy)))
        s.setValue("apps", json.dumps(sorted(self.selected_apps), ensure_ascii=False))
        s.setValue("buffer", self.buffer.currentIndex())
        s.setValue("in", self.cin.currentText())
        s.setValue("out", self.cout.currentText())
        s.setValue("source", self.engine.source)
        s.setValue("mode8d", "true" if self.engine.mode_8d else "false")
        s.setValue("auto", "true" if self.engine.auto else "false")
        s.setValue("close_to_tray", "true" if self.cb_tray.isChecked() else "false")
        s.setValue("was_running", "true" if self.engine.running and self.engine.source != "file" else "false")

    def reset(self):
        self.apply_preset("Классика 8D")
        self.s_vol.setValue(90)
        self.buffer.setCurrentIndex(1)
        self.preset.setCurrentIndex(0)
        self.engine.manual_xy = (0.0, 0.75)
        self.engine.vocal_xy = (0.0, 0.25)
        self.split.setCurrentIndex(0)
        self.cb_vocal.setChecked(False)
        self.s_vspeed.setValue(-10)
        self.engine.phase = 0.0
        self.engine.error = ""
        self.set_source("system")
        custom = self.settings.value("custom_presets", "{}")
        self.settings.clear()
        self.settings.setValue("custom_presets", custom)  # свои пресеты не трогаем
        self.load_devices()
        self.refresh()

    def on_pad(self, x, y):
        self.engine.manual_xy = (x, y)
        if not self.engine.mode_8d:
            self.set_mode(True)
        self.set_auto(False)

    def split_changed(self, i):
        self.engine.split = i
        self.refresh()

    def on_vocal(self, x, y):
        self.engine.vocal_xy = (x, y)

    def on_pad_height(self, delta):
        self.s_elev.setValue(self.s_elev.value() + delta)

    def set_mode(self, on):
        self.engine.mode_8d = on
        self.refresh()

    def set_auto(self, on):
        if on and not self.engine.auto:
            x, y = self.engine.pos_xy  # продолжить вращение с текущей точки
            self.engine.phase = (math.atan2(x, y) / (2 * math.pi)) % 1.0
        self.engine.auto = on
        self.refresh()

    def devices_changed(self):
        if self.engine.running:
            self.start()

    def start(self):
        e = self.engine
        e.error = ""
        if self.cout.currentData() is None:
            e.error = "Не найдено устройство вывода."
        elif "CABLE" in self.cout.currentText():
            e.error = "Выход не должен быть CABLE — выбери наушники."
        elif e.source == "file":
            self.route_windows(False)
            e.start_file(self.cout.currentData())
        elif self.cin.currentData() is None:
            e.error = "Не найден VB-Cable. Установи его (vb-audio.com/Cable) или выбери «Файл»."
        elif e.source == "apps":
            self.route_windows(False)
            if e.start(self.cin.currentData(), self.cout.currentData()):
                self.routed_pids = set()
                self.route_selected_apps()
        elif e.start(self.cin.currentData(), self.cout.currentData()):
            self.unroute_apps()
            self.route_windows(True)
        self.silent_ticks = 0
        self.refresh()

    def set_source(self, src):
        if self.engine.source == src:
            self.refresh()
            return
        was = self.engine.running
        self.engine.stop()
        self.unroute_apps()
        self.engine.source = src
        if src == "system":
            self.engine.playing = False
        if was:
            self.start()
        else:
            self.route_windows(False)
        self.refresh()

    # ---------- плеер ----------
    def load_path(self, path):
        import soundfile as sf
        try:
            data, sr = sf.read(path, dtype="float32", always_2d=True)
        except Exception as ex:  # noqa: BLE001
            self.engine.error = f"Не удалось открыть файл: {ex}"
            self.refresh()
            return
        self.engine.load_track(data, sr, os.path.splitext(os.path.basename(path))[0])
        self.begin_playback()

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть музыку", self.settings.value("lastdir", ""),
                                              "Аудио (*.mp3 *.wav *.flac *.ogg *.opus *.aiff)")
        if path:
            self.settings.setValue("lastdir", os.path.dirname(path))
            self.load_path(path)

    def play_demo(self):
        self.engine.load_track(demo_track(), 48000, "Тестовый луп 8D")
        self.engine.mode_8d = True  # тест всегда в 8D, с вращением
        self.set_auto(True)
        self.begin_playback()

    def begin_playback(self):
        self.engine.playing = True
        if self.engine.source != "file" or not self.engine.running:
            self.engine.source = "file"
            self.start()
        self.refresh()

    def play_pause(self):
        e = self.engine
        if e.track is None:
            self.open_file()
            return
        if e.source != "file" or not e.running:
            self.begin_playback()
        else:
            e.playing = not e.playing
        self.refresh()

    def do_seek(self):
        e = self.engine
        if e.track is not None:
            e.track_pos = float(int(len(e.track) * self.seek.value() / 1000))

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Space:
            self.play_pause()
        else:
            super().keyPressEvent(ev)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        urls = ev.mimeData().urls()
        if urls:
            self.load_path(urls[0].toLocalFile())

    def tick(self):
        self.app_tick += 1
        if self.engine.running and self.engine.source == "apps" and self.app_tick % 60 == 0:
            self.route_selected_apps()  # раз в ~2 с подхватываем новые процессы
        if self.mini and self.mini.isVisible():
            self.mini.tick()
        if not self.isVisible():
            return  # в трее не тратим процессор на отрисовку
        self.pad.tick()
        for m in self.meters:
            m.tick()
        e = self.engine
        if e.track is not None:
            total = len(e.track) / e.track_sr
            self.time_lbl.setText(f"{fmt_time(e.track_pos / e.track_sr)} / {fmt_time(total)}")
            if not self.seek.isSliderDown():
                self.seek.setValue(int(1000 * e.track_pos / max(1, len(e.track))))
        playing = e.running and e.source == "file" and e.playing
        if self.bplay.text() != ("❚❚" if playing else "▶"):
            self.bplay.setText("❚❚" if playing else "▶")
        # диагностика: режим «весь ПК», а сигнала с кабеля нет
        if e.running and e.source == "system" and not e.error:
            self.silent_ticks = 0 if e.in_level > 0.0005 else self.silent_ticks + 1
            if self.silent_ticks == 90:
                self.status.setText("⚠  Сигнала нет. Включи музыку; если играет — перезапусти плеер "
                                    "(он остался на старом устройстве) или жми «🎵 Файл».")
                self.status.setStyleSheet("color: #f472b6;")
            elif self.silent_ticks == 0 and "Сигнала нет" in self.status.text():
                self.refresh()

    def route_windows(self, on):
        """Весь звук Windows -> CABLE Input, при выключении — обратно."""
        try:
            if on:
                cur = winaudio.get_default_output()
                cable = winaudio.find_output("CABLE Input")
                if cable and cur != cable:
                    self.saved_default = cur
                    winaudio.set_default_output(cable)
            elif getattr(self, "saved_default", None):
                winaudio.set_default_output(self.saved_default)
                self.saved_default = None
            elif winaudio.get_default_output() == winaudio.find_output("CABLE Input"):
                back = winaudio.find_output("VXE V1")
                if back:
                    winaudio.set_default_output(back)
        except Exception as ex:  # noqa: BLE001
            self.engine.error = f"Не удалось переключить звук Windows: {ex}"

    def toggle(self):
        if self.engine.running:
            self.engine.stop()
            self.route_windows(False)
            self.unroute_apps()
            self.refresh()
        else:
            self.start()

    def refresh(self):
        e = self.engine
        self.b2d.setChecked(not e.mode_8d)
        self.b8d.setChecked(e.mode_8d)
        self.bauto.setChecked(e.auto)
        self.bhand.setChecked(not e.auto)
        self.bsys.setChecked(e.source == "system")
        self.bapps.setChecked(e.source == "apps")
        self.bfile.setChecked(e.source == "file")
        self.cin.setVisible(e.source != "file")
        self.cin_lbl.setVisible(e.source != "file")
        self.apps_list.setVisible(e.source == "apps")
        self.bref_apps.setVisible(e.source == "apps")
        self.src_hint.setText({
            "system": "Весь звук компьютера (музыка, игры, Discord) идёт через 8D. Нужен VB-Cable.",
            "apps": "В 8D только отмеченные программы, остальное звучит как обычно. В списке — программы, "
                    "которые сейчас издают звук: включи в них музыку и нажми «Обновить».",
            "file": "Встроенный плеер: открой трек или перетащи его в окно. Кабель не нужен.",
        }[e.source])
        if self.mini:
            self.mini.refresh()
        self.pattern.setEnabled(e.auto)
        self.s_speed.setEnabled(e.auto)
        self.s_wob.setEnabled(e.auto)
        self.vocal_box.setVisible(e.split == 2)
        self.s_vspeed.setEnabled(e.vocal_auto)
        if e.track_name:
            self.track_lbl.setText(e.track_name)
        self.power.setText("■  ВЫКЛЮЧИТЬ" if e.running else "▶  ВКЛЮЧИТЬ")
        self.power.setProperty("on", "true" if e.running else "false")
        self.power.style().unpolish(self.power)
        self.power.style().polish(self.power)
        if hasattr(self, "tray"):
            self.tray.setIcon(app_icon(e.running))
            state = ("8D" if e.mode_8d else "2D") if e.running else "выключено"
            self.tray.setToolTip(f"8D Sound — {state}")
            self.m_power.setText("Выключить" if e.running else "Включить")
            self.m_mode.setChecked(e.mode_8d)
        if e.error:
            self.status.setText("⚠  " + e.error)
            self.status.setStyleSheet("color: #f472b6;")
        elif e.running:
            if e.source == "apps":
                names = ", ".join(appaudio.pretty(a) for a in sorted(self.selected_apps)) or "программы не выбраны"
                src = names
            else:
                src = "весь звук ПК" if e.source == "system" else "файл"
            self.status.setText(f"● В эфире — {'8D' if e.mode_8d else '2D'} · {src}")
            self.status.setStyleSheet("color: #c084fc;")
        else:
            self.status.setText("Выключено. «Включить» — весь звук ПК в 8D, или открой файл / «Тест 8D».")
            self.status.setStyleSheet("")


def main():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("6ixl.8dsound")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    tray_start = "--tray" in sys.argv
    w = Main(tray_start)
    if not tray_start:
        w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
