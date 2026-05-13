"""Shared Qt widgets and image conversion helpers."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLineEdit
from PIL import Image


class CommitLineEdit(QLineEdit):
    """Line edit that commits on Enter without activating dialog default buttons."""

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.returnPressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


def pil_to_qpixmap(image: Image.Image) -> QPixmap:
    rgb = image.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())
