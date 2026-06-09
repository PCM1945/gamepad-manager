from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen, QColor
import logging

logger = logging.getLogger("gamepad_manager")


class StickCartesianMap(QWidget):
    """Draw a circular Cartesian map for joystick position visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._x = 0.0
        self._y = 0.0
        self.setMinimumSize(140, 140)

    def set_stick_position(self, x, y):
        """Set normalized stick position in range -1.0..1.0 and repaint."""
        self._x = max(-1.0, min(1.0, float(x)))
        self._y = max(-1.0, min(1.0, float(y)))
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        margin = 10
        content = self.rect().adjusted(margin, margin, -margin, -margin)
        size = min(content.width(), content.height())
        radius = size / 2.0
        cx = content.x() + content.width() / 2.0
        cy = content.y() + content.height() / 2.0

        # Background and outer circle.
        painter.setBrush(QColor(245, 248, 252))
        painter.setPen(QPen(QColor(90, 100, 115), 2))
        painter.drawEllipse(int(cx - radius), int(cy - radius), int(size), int(size))

        # Cartesian axes.
        painter.setPen(QPen(QColor(165, 170, 180), 1))
        painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))
        painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))

        # Deadzone ring for reference.
        deadzone_radius = radius * 0.15
        painter.setPen(QPen(QColor(210, 215, 225), 1, Qt.DashLine))
        painter.drawEllipse(
            int(cx - deadzone_radius),
            int(cy - deadzone_radius),
            int(deadzone_radius * 2),
            int(deadzone_radius * 2),
        )

        # Current stick position and vector.
        px = cx + (self._x * radius)
        # Cartesian map: positive Y goes up on screen.
        py = cy - (self._y * radius)
        painter.setPen(QPen(QColor(40, 120, 220), 2))
        painter.drawLine(int(cx), int(cy), int(px), int(py))

        painter.setBrush(QColor(220, 60, 60))
        painter.setPen(QPen(QColor(150, 30, 30), 1))
        dot_size = 10
        painter.drawEllipse(int(px - dot_size / 2), int(py - dot_size / 2), dot_size, dot_size)