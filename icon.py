"""Фирменная иконка 8D Sound: голова-сфера с орбитой звука."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient


def render(size=256, active=True):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 256
    c = QPointF(128 * s, 128 * s)

    bg = QLinearGradient(0, 0, size, size)
    bg.setColorAt(0, QColor("#3b0d74") if active else QColor("#3a3344"))
    bg.setColorAt(1, QColor("#12051f") if active else QColor("#18151d"))
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 58 * s, 58 * s)

    glow = QRadialGradient(c, 110 * s)
    glow.setColorAt(0, QColor(192, 38, 211, 110 if active else 30))
    glow.setColorAt(1, QColor(124, 58, 237, 0))
    p.setBrush(glow)
    p.drawEllipse(c, 110 * s, 110 * s)

    # орбита (наклонный эллипс)
    p.save()
    p.translate(c)
    p.rotate(-22)
    ring = QLinearGradient(-100 * s, 0, 100 * s, 0)
    ring.setColorAt(0, QColor("#7c3aed"))
    ring.setColorAt(1, QColor("#f0abfc"))
    p.setPen(QPen(ring, max(1.5, 11 * s), Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(0, 0), 100 * s, 42 * s)
    # звук на орбите
    a = math.radians(-35)
    dot = QPointF(math.cos(a) * 100 * s, math.sin(a) * 42 * s)
    dg = QRadialGradient(dot, 30 * s)
    dg.setColorAt(0, QColor(255, 240, 255, 255))
    dg.setColorAt(0.35, QColor(232, 121, 249, 200))
    dg.setColorAt(1, QColor(232, 121, 249, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(dg)
    p.drawEllipse(dot, 30 * s, 30 * s)
    p.restore()

    # «8D»
    p.setPen(QColor("white"))
    f = QFont("Segoe UI", 1, QFont.Black)
    f.setPixelSize(int(92 * s))
    p.setFont(f)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "8D")
    p.end()
    return pm


def app_icon(active=True):
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(render(sz, active))
    return icon
