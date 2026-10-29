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
        self._image_paths: dict[str, Path] = {}
        self._image_urls: dict[str, str] = {}
        self._rendered_signatures: dict[str, tuple[Any, ...]] = {}
        self._cards: list[dict[str, Any]] = []
        self._image_url = ""
        self._backend.changed.connect(self._refresh_image)
        self._refresh_image()

    @Property(str, notify=imageChanged)
    def imageUrl(self) -> str:
        return self._image_url

    @Property("QVariantList", notify=imageChanged)
    def tableCards(self) -> list[dict[str, Any]]:
        return self._cards

    def _refresh_image(self) -> None:
        panels: list[dict[str, Any]] = self._backend.tablePanels
        current_keys = set()
        cards = []
        for panel in panels:
            key = f"{panel['outputId']}-{panel['sliceIndex']}"
            current_keys.add(key)
            path = self._image_paths.get(key)
            if path is None:
                path = (
                    Path(tempfile.gettempdir())
                    / f"logicbool-table-{os.getpid()}-{key}.png"
                )
                self._image_paths[key] = path
            signature = (
                panel["outputName"],
                panel["assignment"],
                tuple(
                    (row["label"], tuple(
                        (cell["index"], cell["value"]) for cell in row["cells"]
                    ))
                    for row in panel["rows"]
                ),
            )
            if self._rendered_signatures.get(key) != signature:
                image = self._render_image(panel)
                if not image.save(str(path), "PNG"):
                    raise OSError(f"Could not write truth-table image to {path}.")
                self._rendered_signatures[key] = signature
                self._revision += 1
                self._image_urls[key] = (
                    f"{QUrl.fromLocalFile(str(path)).toString()}"
                    f"?revision={self._revision}"
                )
            cards.append({
                **panel,
                "imageUrl": self._image_urls[key],
            })

        for key in set(self._image_paths) - current_keys:
            self._image_paths.pop(key).unlink(missing_ok=True)
            self._rendered_signatures.pop(key, None)
            self._image_urls.pop(key, None)

        self._cards = cards
        self._image_url = cards[0]["imageUrl"] if cards else ""
        self.imageChanged.emit()

    def _render_image(self, panel: dict[str, Any]) -> QImage:
        image = QImage(900, 310, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("#ffffff"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = float(image.width())
        label_width = 120.0
        gap = 5.0
        header_height = 44.0
        cell_height = 56.0
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

        header_font = QFont("Arial", 13, QFont.Weight.Bold)
        cell_font = QFont("Arial", 13, QFont.Weight.Bold)
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

        rows: list[dict[str, Any]] = panel["rows"]
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

    @Slot(str, int, float, float, float, float)
    def toggleCellAt(
        self, output_id: str, slice_index: int,
        x: float, y: float, width: float, height: float,
    ) -> None:
        if width <= 0 or height <= 0:
            return
        x *= 900 / width
        y *= 310 / height
        label_width = 120.0
        gap = 5.0
        header_height = 44.0
        cell_height = 56.0
        cell_width = (900 - label_width - gap * 4) / 4
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
        panel = next((
            item for item in self._cards
            if item["outputId"] == output_id
            and item["sliceIndex"] == slice_index
        ), None)
        if panel is None:
            return
        cell = panel["rows"][row]["cells"][column]
        self._backend.setOutputTableCell(
            output_id, int(cell["index"]), 1 - int(cell["value"])
        )

    @Slot()
    def cleanup(self) -> None:
        for path in self._image_paths.values():
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        self._image_paths.clear()
        self._image_urls.clear()
        self._rendered_signatures.clear()
