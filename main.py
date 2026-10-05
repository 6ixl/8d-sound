"""8D Sound — превращает любой звук Windows в 8D."""
import math
import os
import sys

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QSlider, QVBoxLayout, QWidget, QFileDialog)

from engine import PATTERNS, Engine, demo_track
import winaudio

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
"""


class SpacePad(QWidget):
    """Круг вокруг головы слушателя: показывает и задаёт положение звука."""

    moved = Signal(float, float)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setMinimumSize(380, 380)
        self.trail = []
        self.spectrum = np.zeros(72)
        self.t = 0.0
        self.setCursor(Qt.OpenHandCursor)

    def geometry_(self):
        side = min(self.width(), self.height()) - 30
        c = QPointF(self.width() / 2, self.height() / 2)
        return c, side / 2

    def tick(self):
        self.t += 1 / 60
        if not self.engine.running:  # без звука двигаем точку сами
            self.engine._advance(1, 60)
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

    def mousePressEvent(self, e):
        self.setCursor(Qt.ClosedHandCursor)
        self.moved.emit(*self._to_xy(e.position()))

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self.moved.emit(*self._to_xy(e.position()))

    def wheelEvent(self, e):
        x, y = self.engine.pos_xy
        r = max(0.15, math.hypot(x, y))
        a = math.atan2(x, y) + math.radians(e.angleDelta().y() / 120 * 10)
        self.moved.emit(math.sin(a) * r, math.cos(a) * r)

    def mouseReleaseEvent(self, e):
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
        for txt, dx, dy in (("ПЕРЕД", 0, -1), ("ЗАД", 0, 1), ("Л", -1, 0), ("П", 1, 0)):
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
        if self.trail:
            s = pt(self.trail[-1])
            lvl = min(1.0, self.engine.level * 6)
            glow = QRadialGradient(s, 34 + 20 * lvl)
            glow.setColorAt(0, QColor(240, 171, 252, 230))
            glow.setColorAt(0.35, QColor(192, 38, 211, 120))
            glow.setColorAt(1, QColor(124, 58, 237, 0))
            p.setBrush(glow)
            p.drawEllipse(s, 34 + 20 * lvl, 34 + 20 * lvl)
            p.setBrush(QColor("#fdf4ff"))
            p.setPen(QPen(PINK, 3))
            p.drawEllipse(s, 9, 9)


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


def make_icon():
    pm = QPixmap(128, 128)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 128, 128)
    g.setColorAt(0, QColor("#7c3aed"))
    g.setColorAt(1, QColor("#c026d3"))
    p.setBrush(g)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, 120, 120, 30, 30)
    p.setPen(QColor("white"))
    p.setFont(QFont("Segoe UI", 44, QFont.Black))
    p.drawText(QRectF(0, 0, 128, 128), Qt.AlignCenter, "8D")
    p.end()
    return QIcon(pm)


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = Engine()
        self.settings = QSettings("6ixl", "8D Sound")
        self.setWindowTitle("8D Sound")
        self.setWindowIcon(make_icon())
        self.resize(1060, 700)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(22, 20, 22, 20)
        main.setSpacing(20)

        # ---- левая колонка: площадка ----
        left = QVBoxLayout()
        title = QLabel("8D SOUND")
        title.setObjectName("title")
        self.status = QLabel()
        self.status.setObjectName("subtitle")
        left.addWidget(title)
        left.addWidget(self.status)
        self.pad = SpacePad(self.engine)
        self.pad.moved.connect(self.on_pad)
        left.addWidget(self.pad, 1)
        hint = QLabel("Тащи точку мышкой или крути колёсиком. Центр = в голове, край = далеко.")
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
        bopen.setCursor(Qt.PointingHandCursor)
        bopen.clicked.connect(self.open_file)
        btest = QPushButton("🎧  Тест 8D")
        btest.setCursor(Qt.PointingHandCursor)
        btest.clicked.connect(self.play_demo)
        top.addWidget(bopen)
        top.addWidget(btest)
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
        right.setSpacing(14)

        c1, l1 = card()
        sec = QLabel("РЕЖИМ")
        sec.setObjectName("section")
        l1.addWidget(sec)
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
        right.addWidget(c1)

        c2, l2 = card()
        sec = QLabel("ДВИЖЕНИЕ")
        sec.setObjectName("section")
        l2.addWidget(sec)
        mv = QHBoxLayout()
        self.bauto = QPushButton("⟳  Авто-вращение")
        self.bhand = QPushButton("✋  Вручную")
        for b in (self.bauto, self.bhand):
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            mv.addWidget(b)
        self.bauto.clicked.connect(lambda: self.set_auto(True))
        self.bhand.clicked.connect(lambda: self.set_auto(False))
        l2.addLayout(mv)
        self.pattern = QComboBox()
        self.pattern.addItems(PATTERNS)
        self.pattern.currentIndexChanged.connect(lambda i: setattr(self.engine, "pattern", i))
        l2.addWidget(self.pattern)
        box, self.s_speed = labeled_slider("Скорость", 2, 60, 12, lambda v: f"{100 / v:.1f} с/оборот")
        self.s_speed.valueChanged.connect(lambda v: setattr(self.engine, "speed", v / 100))
        l2.addLayout(box)
        box, self.s_dist = labeled_slider("Дистанция", 15, 100, 75, lambda v: f"{v}%")
        self.s_dist.valueChanged.connect(lambda v: setattr(self.engine, "distance", v / 100))
        l2.addLayout(box)
        box, self.s_room = labeled_slider("Пространство", 0, 100, 25, lambda v: f"{v}%")
        self.s_room.valueChanged.connect(lambda v: setattr(self.engine, "room", v / 100))
        l2.addLayout(box)
        box, self.s_vol = labeled_slider("Громкость", 0, 150, 90, lambda v: f"{v}%")
        self.s_vol.valueChanged.connect(lambda v: setattr(self.engine, "volume", v / 100))
        l2.addLayout(box)
        right.addWidget(c2)

        c3, l3 = card()
        sec = QLabel("ЗВУК")
        sec.setObjectName("section")
        l3.addWidget(sec)
        src = QHBoxLayout()
        self.bsys = QPushButton("🖥  Весь звук ПК")
        self.bfile = QPushButton("🎵  Файл")
        for b in (self.bsys, self.bfile):
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            src.addWidget(b)
        self.bsys.clicked.connect(lambda: self.set_source("system"))
        self.bfile.clicked.connect(lambda: self.set_source("file"))
        l3.addLayout(src)
        self.cin = QComboBox()
        self.cout = QComboBox()
        self.cin_lbl = QLabel("Откуда брать (VB-Cable Output)")
        self.cin_lbl.setObjectName("hint")
        l3.addWidget(self.cin_lbl)
        l3.addWidget(self.cin)
        lab = QLabel("Куда выводить (твои наушники)")
        lab.setObjectName("hint")
        l3.addWidget(lab)
        l3.addWidget(self.cout)
        row = QHBoxLayout()
        win = QPushButton("⚙  Звук Windows")
        win.setCursor(Qt.PointingHandCursor)
        win.clicked.connect(lambda: os.startfile("ms-settings:sound"))
        ref = QPushButton("↻")
        ref.setFixedWidth(44)
        ref.setCursor(Qt.PointingHandCursor)
        ref.clicked.connect(self.load_devices)
        row.addWidget(win, 1)
        row.addWidget(ref)
        l3.addLayout(row)
        for name, getter in (("Вход", lambda: self.engine.in_level), ("Выход 8D", lambda: self.engine.level)):
            r = QHBoxLayout()
            lb = QLabel(name)
            lb.setObjectName("hint")
            lb.setFixedWidth(62)
            m = Meter(getter)
            self.meters = getattr(self, "meters", []) + [m]
            r.addWidget(lb)
            r.addWidget(m, 1)
            l3.addLayout(r)
        right.addWidget(c3)

        self.power = QPushButton()
        self.power.setObjectName("power")
        self.power.setCursor(Qt.PointingHandCursor)
        self.power.clicked.connect(self.toggle)
        right.addWidget(self.power)
        reset = QPushButton("↺  Сбросить настройки")
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self.reset)
        right.addWidget(reset)
        right.addStretch()
        main.addLayout(right, 2)

        self.setStyleSheet(STYLE)
        self.load_devices()
        self.restore()
        self.cin.currentIndexChanged.connect(self.devices_changed)
        self.cout.currentIndexChanged.connect(self.devices_changed)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        self.refresh()

    # ---------- логика ----------
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

    def restore(self):
        s = self.settings
        for key, w in (("speed", self.s_speed), ("dist", self.s_dist), ("room", self.s_room), ("vol", self.s_vol)):
            if s.contains(key):
                w.setValue(int(s.value(key)))
        self.pattern.setCurrentIndex(int(s.value("pattern", 0)))
        for key, combo in (("in", self.cin), ("out", self.cout)):
            name = s.value(key, "")
            if name and combo.findText(name) >= 0:
                combo.setCurrentText(name)
        self.engine.source = s.value("source", "system")
        self.engine.mode_8d = s.value("mode8d", "true") == "true"
        self.engine.auto = s.value("auto", "true") == "true"

    def closeEvent(self, e):
        s = self.settings
        s.setValue("speed", self.s_speed.value())
        s.setValue("dist", self.s_dist.value())
        s.setValue("room", self.s_room.value())
        s.setValue("vol", self.s_vol.value())
        s.setValue("pattern", self.pattern.currentIndex())
        s.setValue("in", self.cin.currentText())
        s.setValue("out", self.cout.currentText())
        s.setValue("source", self.engine.source)
        s.setValue("mode8d", "true" if self.engine.mode_8d else "false")
        s.setValue("auto", "true" if self.engine.auto else "false")
        self.engine.stop()
        self.route_windows(False)
        super().closeEvent(e)

    def reset(self):
        self.s_speed.setValue(12)
        self.s_dist.setValue(75)
        self.s_room.setValue(25)
        self.s_vol.setValue(90)
        self.pattern.setCurrentIndex(0)
        self.engine.manual_xy = (0.0, 0.75)
        self.engine.phase = 0.0
        self.engine.mode_8d = True
        self.engine.auto = True
        self.engine.error = ""
        self.set_source("system")
        self.settings.clear()
        self.load_devices()
        self.refresh()

    def on_pad(self, x, y):
        self.engine.manual_xy = (x, y)
        if not self.engine.mode_8d:
            self.set_mode(True)
        self.set_auto(False)

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
        if self.cout.currentData() is None:
            e.error = "Не найдено устройство вывода."
        elif "CABLE" in self.cout.currentText():
            e.error = "Выход не должен быть CABLE — выбери наушники."
        elif e.source == "file":
            self.route_windows(False)
            e.start_file(self.cout.currentData())
        elif self.cin.currentData() is None:
            e.error = "Не найден VB-Cable. Установи его (vb-audio.com/Cable) или выбери «Файл»."
        elif e.start(self.cin.currentData(), self.cout.currentData()):
            self.route_windows(True)
        self.silent_ticks = 0
        self.refresh()

    def set_source(self, src):
        if self.engine.source == src:
            self.refresh()
            return
        was = self.engine.running
        self.engine.stop()
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
            e.track_pos = int(len(e.track) * self.seek.value() / 1000)

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
            self.silent_ticks = 0 if e.in_level > 0.0005 else getattr(self, "silent_ticks", 0) + 1
            if self.silent_ticks == 180:
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
        self.bfile.setChecked(e.source == "file")
        self.cin.setVisible(e.source == "system")
        self.cin_lbl.setVisible(e.source == "system")
        self.pattern.setEnabled(e.auto)
        self.s_speed.setEnabled(e.auto)
        if e.track_name:
            self.track_lbl.setText(e.track_name)
        self.power.setText("■  ВЫКЛЮЧИТЬ" if e.running else "▶  ВКЛЮЧИТЬ")
        self.power.setProperty("on", "true" if e.running else "false")
        self.power.style().unpolish(self.power)
        self.power.style().polish(self.power)
        if e.error:
            self.status.setText("⚠  " + e.error)
            self.status.setStyleSheet("color: #f472b6;")
        elif e.running:
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
    w = Main()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
