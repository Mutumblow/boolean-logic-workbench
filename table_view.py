import os
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QFont, QImage, QPainter, Qt


class TruthTableView(QObject):
    imageChanged = Signal()

    def __init__(self, backend: QObject) -> None:
        super().__init__()
        self._backend = backend
        self._revision = 0
        self._image_path = (
            Path(tempfile.gettempdir()) / f"logicbool-truth-table-{os.getpid()}.png"
        )
        self._image_url = ""
        self._backend.changed.connect(self._refresh_image)
        self._refresh_image()

    @Property(str, notify=imageChanged)
    def imageUrl(self) -> str:
        return self._image_url

    def _refresh_image(self) -> None:
        image = self._render_image()
        if not image.save(str(self._image_path), "PNG"):
            raise OSError(f"Could not write truth-table image to {self._image_path}.")
        self._revision += 1
        self._image_url = (
            f"{QUrl.fromLocalFile(str(self._image_path)).toString()}"
            f"?revision={self._revision}"
        )
        self.imageChanged.emit()

    def _render_image(self) -> QImage:
        image = QImage(1200, 430, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("#ffffff"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = float(image.width())
        label_width = 150.0
        gap = 6.0
        header_height = 54.0
        cell_height = 72.0
        cell_width = (width - label_width - gap * 4) / 4

        def draw_cell(
            x: float,
            y: float,
            cell_width: float,
            cell_height: float,
            background: str,
            text: str,
            foreground: str,
            font: QFont,
            border: str | None = None,
        ) -> None:
            painter.setPen(QColor(border or background))
            painter.setBrush(QColor(background))
            painter.drawRoundedRect(x, y, cell_width, cell_height, 6, 6)
            painter.setPen(QColor(foreground))
            painter.setFont(font)
            painter.drawText(
                int(x),
                int(y),
                int(cell_width),
                int(cell_height),
                int(Qt.AlignmentFlag.AlignCenter),
                text,
            )

        header_font = QFont("Arial", 14, QFont.Weight.Bold)
        cell_font = QFont("Arial", 16, QFont.Weight.Bold)
        draw_cell(
            0, 0, label_width, header_height, "#edf2fa",
            "C/D  |  A/B", "#26354f", header_font,
        )
        for column, label in enumerate(("A'B'", "A'B", "AB", "AB'")):
            x = label_width + gap + column * (cell_width + gap)
            draw_cell(
                x, 0, cell_width, header_height, "#edf2fa",
                label, "#26354f", header_font,
            )

        rows: list[dict[str, Any]] = self._backend.tableRows
        row_labels = ("C'D'", "C'D", "CD", "CD'")
        for row_index, row_label in enumerate(row_labels):
            y = header_height + gap + row_index * (cell_height + gap)
            draw_cell(
                0, y, label_width, cell_height, "#f5f7fb",
                row_label, "#26354f", cell_font,
            )
            for column in range(4):
                value = 0
                p_index = (row_index, column)
                if row_index < len(rows) and column < len(rows[row_index]["cells"]):
                    cell = rows[row_index]["cells"][column]
                    value = int(cell["value"])
                    p_index = int(cell["index"])
                background = "#e2f4e9" if value else "#fff0e9"
                foreground = "#176b39" if value else "#8b321f"
                x = label_width + gap + column * (cell_width + gap)
                draw_cell(
                    x,
                    y,
                    cell_width,
                    cell_height,
                    background,
                    f"{value}(P{p_index})",
                    foreground,
                    cell_font,
                    "#80bd91" if value else "#e1a58e",
                )

        painter.end()
        return image

    @Slot(float, float, float, float)
    def toggleCellAt(self, x: float, y: float, width: float, height: float) -> None:
        if width <= 0 or height <= 0:
            return
        x *= 1200 / width
        y *= 430 / height
        label_width = 150.0
        gap = 6.0
        header_height = 54.0
        cell_height = 72.0
        cell_width = (1200 - label_width - gap * 4) / 4
        first_cell_x = label_width + gap
        first_cell_y = header_height + gap
        if x < first_cell_x or y < first_cell_y:
            return
        column = int((x - first_cell_x) // (cell_width + gap))
        row = int((y - first_cell_y) // (cell_height + gap))
        if not (0 <= row < 4 and 0 <= column < 4):
            return
        within_cell_x = (x - first_cell_x) % (cell_width + gap)
        within_cell_y = (y - first_cell_y) % (cell_height + gap)
        if within_cell_x > cell_width or within_cell_y > cell_height:
            return
        cell = self._backend.tableRows[row]["cells"][column]
        self._backend.setTableCell(int(cell["index"]), 1 - int(cell["value"]))

    @Slot()
    def cleanup(self) -> None:
        try:
            self._image_path.unlink()
        except FileNotFoundError:
            pass
