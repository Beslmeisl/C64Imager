"""Main application window."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator, QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PIL import Image

from app.core.c64_palette import C64_PALETTE, color_name
from app.core.convert_hires import HiresResult, convert_to_hires
from app.core.convert_mono import (
    MonoResult,
    compute_mono_luminances,
    convert_to_mono,
    foreground_percent_for_threshold,
    threshold_for_foreground_percent,
)
from app.core.convert_grayscale import GrayscaleResult, convert_to_grayscale
from app.core.convert_multicolor import MulticolorResult, convert_to_multicolor
from app.core.export_prg import (
    HiresFrame,
    export_hires_prg_program,
    export_multicolor_prg_program,
)
from app.core.image_adjust import (
    DEFAULT_NORMALIZE_SLIDER_MAX,
    MAX_ADJUSTMENT_SLIDER_MAX,
    MIN_ADJUSTMENT_SLIDER_MAX,
    apply_rgb_express,
    apply_rgb_depress,
    apply_rgb_adjustment,
    average_raster_preview,
    rgb_average_slider_values,
    rgb_normalize_slider_values,
    rescale_adjustment_percent,
)
from app.ui.widgets import CommitLineEdit, pil_to_qpixmap

_ADJUSTMENT_PERCENT_EDIT_WIDTH = 50


def _default_export_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "Export"
    return Path(__file__).resolve().parent.parent.parent / "Export"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("C64 Imager")
        self.resize(1400, 950)

        self.original_image: Optional[Image.Image] = None
        self.adjusted_image: Optional[Image.Image] = None
        self.original_pixmap: Optional[QPixmap] = None
        self.hires_result: Optional[HiresResult] = None
        self.multicolor_result: Optional[MulticolorResult] = None
        self.mono_result: Optional[MonoResult] = None
        self.grayscale_result: Optional[GrayscaleResult] = None
        self.mono_luminances: Optional[List[float]] = None
        self.source_brightness = 100
        self.source_red = 100
        self.source_green = 100
        self.source_blue = 100
        self.source_slider_max = DEFAULT_NORMALIZE_SLIDER_MAX
        self.c64_border_color = 0
        self._border_color_combos: List[QComboBox] = []
        self._adjustment_dialog: Optional[QDialog] = None

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.original_label = self._create_image_label()
        self.average_320_label = self._create_image_label()
        self.average_160_label = self._create_image_label()
        self.hires_label = self._create_image_label()
        self.multicolor_label = self._create_image_label()
        self.mono_label = self._create_image_label()
        self.grayscale_label = self._create_image_label()

        self.tabs.addTab(self._build_original_tab(), "Original")
        self.tabs.addTab(self._build_average_tab(self.average_320_label, "Mittelwerte 320x200"), "Mittelwerte 320x200")
        self.tabs.addTab(self._build_average_tab(self.average_160_label, "Mittelwerte 160x200"), "Mittelwerte 160x200")
        self.tabs.addTab(self._build_hires_tab(), "C64 HIRES")
        self.tabs.addTab(self._build_multicolor_tab(), "C64 Multicolor")
        self.tabs.addTab(self._build_mono_tab(), "Monochrom 320x200")
        self.tabs.addTab(self._build_grayscale_tab(), "Graustufen")

    def _build_original_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        actions = QHBoxLayout()
        open_btn = QPushButton("JPG laden")
        open_btn.clicked.connect(self.open_image)
        rotate_btn = QPushButton("90° im Uhrzeigersinn")
        rotate_btn.clicked.connect(self.rotate_original_clockwise)
        export_btn = self._create_export_button()
        actions.addWidget(open_btn)
        actions.addWidget(rotate_btn)
        actions.addWidget(export_btn)
        actions.addWidget(self._create_adjustment_button())
        actions.addStretch(1)

        layout.addLayout(actions)
        layout.addWidget(self.original_label, stretch=1)
        return tab

    def _build_average_tab(self, image_label: QLabel, title: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()
        controls.addWidget(QLabel(f"{title}, 4x skaliert"))
        controls.addWidget(self._create_export_button())
        controls.addWidget(self._create_adjustment_button())
        controls.addStretch(1)
        layout.addLayout(controls)
        layout.addWidget(image_label, stretch=1)
        return tab

    def _build_hires_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()

        self.hires_bg_combo = QComboBox()
        for idx in range(16):
            self.hires_bg_combo.addItem(f"{idx}: {color_name(idx)}", idx)
        self.hires_bg_combo.currentIndexChanged.connect(self.recompute_all)

        controls.addWidget(QLabel("Hintergrundfarbe"))
        controls.addWidget(self.hires_bg_combo)
        controls.addWidget(QLabel("Rahmenfarbe"))
        controls.addWidget(self._create_border_color_combo())
        controls.addWidget(self._create_export_button())
        controls.addWidget(self._create_adjustment_button())
        controls.addStretch(1)

        layout.addLayout(controls)
        layout.addWidget(self.hires_label, stretch=1)
        return tab

    def _build_multicolor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()
        info = QLabel("Multicolor Vorschau (160x200, 4x skaliert)")
        controls.addWidget(info)
        controls.addWidget(QLabel("Rahmenfarbe"))
        controls.addWidget(self._create_border_color_combo())
        controls.addWidget(self._create_export_button())
        controls.addWidget(self._create_adjustment_button())
        controls.addStretch(1)
        layout.addLayout(controls)
        layout.addWidget(self.multicolor_label, stretch=1)
        return tab

    def _build_mono_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Rahmenfarbe"))
        controls.addWidget(self._create_border_color_combo())
        controls.addWidget(self._create_export_button())
        controls.addWidget(self._create_adjustment_button())
        controls.addStretch(1)
        layout.addLayout(controls)

        form = QFormLayout()
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(0, 442)
        self.threshold_slider.setValue(220)
        self.threshold_slider.valueChanged.connect(self.recompute_mono)

        self.mono_percent_edit = QLineEdit()
        self.mono_percent_edit.setPlaceholderText("0–100 %")
        pct_validator = QDoubleValidator(0.0, 100.0, 2, self)
        pct_validator.setNotation(QDoubleValidator.StandardNotation)
        self.mono_percent_edit.setValidator(pct_validator)
        self.mono_percent_edit.editingFinished.connect(self._on_mono_percent_editing_finished)

        self.mono_fg_combo = QComboBox()
        self.mono_bg_combo = QComboBox()
        for idx in range(16):
            label = f"{idx}: {color_name(idx)}"
            self.mono_fg_combo.addItem(label, idx)
            self.mono_bg_combo.addItem(label, idx)
        self.mono_fg_combo.setCurrentIndex(1)
        self.mono_bg_combo.setCurrentIndex(0)
        self.mono_fg_combo.currentIndexChanged.connect(self.recompute_mono)
        self.mono_bg_combo.currentIndexChanged.connect(self.recompute_mono)

        form.addRow("Helligkeitsgrenze", self.threshold_slider)
        form.addRow("Vordergrundanteil", self.mono_percent_edit)
        form.addRow("Vordergrundfarbe", self.mono_fg_combo)
        form.addRow("Hintergrundfarbe", self.mono_bg_combo)
        layout.addLayout(form)
        layout.addWidget(self.mono_label, stretch=1)
        return tab

    def _build_grayscale_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        controls = QHBoxLayout()
        info = QLabel("Graustufen Vorschau (160x200, 4x skaliert)")
        controls.addWidget(info)
        controls.addWidget(QLabel("Rahmenfarbe"))
        controls.addWidget(self._create_border_color_combo())
        controls.addWidget(self._create_export_button())
        controls.addWidget(self._create_adjustment_button())
        controls.addStretch(1)
        layout.addLayout(controls)
        layout.addWidget(self.grayscale_label, stretch=1)
        return tab

    def _create_image_label(self) -> QLabel:
        label = QLabel("Kein Bild geladen.")
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumSize(500, 300)
        label.setStyleSheet("QLabel { background: #202020; color: #efefef; }")
        return label

    def _create_adjustment_button(self) -> QPushButton:
        button = QPushButton("Vorlage-Korrektur...")
        button.clicked.connect(self._show_adjustment_popup)
        return button

    def _create_export_button(self) -> QPushButton:
        button = QPushButton("Export PRG")
        button.clicked.connect(self.export_all)
        return button

    def _create_border_color_combo(self) -> QComboBox:
        combo = QComboBox()
        for idx in range(16):
            combo.addItem(f"{idx}: {color_name(idx)}", idx)
        combo.setCurrentIndex(self.c64_border_color)
        combo.currentIndexChanged.connect(
            lambda: self._set_c64_border_color(int(combo.currentData()))
        )
        self._border_color_combos.append(combo)
        return combo

    def _set_c64_border_color(self, color: int) -> None:
        self.c64_border_color = color & 0x0F
        for combo in self._border_color_combos:
            combo.blockSignals(True)
            combo.setCurrentIndex(self.c64_border_color)
            combo.blockSignals(False)
        self._update_c64_previews()

    def _show_adjustment_popup(self) -> None:
        if self._adjustment_dialog is not None and self._adjustment_dialog.isVisible():
            self._adjustment_dialog.raise_()
            self._adjustment_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Vorlage-Korrektur")
        dialog.setMinimumWidth(420)
        dialog.setWindowModality(Qt.NonModal)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        layout = QFormLayout(dialog)
        sliders = {}
        value_edits = {}

        for key, caption, value in (
            ("brightness", "Helligkeit", self.source_brightness),
            ("red", "Rot", self.source_red),
            ("green", "Grün", self.source_green),
            ("blue", "Blau", self.source_blue),
        ):
            row = QHBoxLayout()
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, self.source_slider_max)
            slider.setValue(value)
            value_edit = CommitLineEdit(str(value))
            value_edit.setFixedWidth(_ADJUSTMENT_PERCENT_EDIT_WIDTH)
            slider.valueChanged.connect(self._make_adjustment_slider_handler(key, value_edit))
            self._wire_adjustment_percent_edit(key, value_edit, slider)
            row.addWidget(slider)
            row.addWidget(QLabel("%"))
            row.addWidget(value_edit)
            layout.addRow(caption, row)
            sliders[key] = slider
            value_edits[key] = value_edit

        reset_btn = QPushButton("Vorlage-Regler zurücksetzen")
        reset_btn.clicked.connect(
            lambda: self._reset_source_adjustments(sliders, value_edits)
        )
        normalize_btn = QPushButton("RGB Max")
        normalize_btn.clicked.connect(self._normalize_source_rgb)
        avg_btn = QPushButton("RGB AVG")
        avg_btn.clicked.connect(self._average_source_rgb)
        express_btn = QPushButton("Express")
        express_btn.clicked.connect(self._express_source_rgb)
        depress_btn = QPushButton("Depress")
        depress_btn.clicked.connect(self._depress_source_rgb)
        slider_max_edit = CommitLineEdit(str(self.source_slider_max))
        slider_max_edit.setFixedWidth(_ADJUSTMENT_PERCENT_EDIT_WIDTH)
        self._wire_adjustment_max_edit(slider_max_edit, sliders, value_edits)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(dialog.close)
        buttons = QHBoxLayout()
        buttons.addWidget(QLabel("Max %"))
        buttons.addWidget(slider_max_edit)
        buttons.addWidget(normalize_btn)
        buttons.addWidget(avg_btn)
        buttons.addWidget(express_btn)
        buttons.addWidget(depress_btn)
        buttons.addWidget(reset_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)
        layout.addRow(buttons)
        for button in dialog.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
        self._adjustment_dialog = dialog
        self._adjustment_dialog_refs = (sliders, value_edits)
        dialog.finished.connect(self._on_adjustment_dialog_closed)
        dialog.show()

    def _on_adjustment_dialog_closed(self) -> None:
        self._adjustment_dialog = None
        self._adjustment_dialog_refs = None

    def _wire_adjustment_percent_edit(
        self,
        key: str,
        value_edit: CommitLineEdit,
        slider: QSlider,
    ) -> None:
        def apply() -> None:
            self._on_adjustment_percent_editing_finished(key, value_edit, slider)

        value_edit.returnPressed.connect(apply)
        value_edit.editingFinished.connect(apply)

    def _wire_adjustment_max_edit(
        self,
        slider_max_edit: CommitLineEdit,
        sliders: dict,
        value_edits: dict,
    ) -> None:
        def apply() -> None:
            self._update_adjustment_slider_max(slider_max_edit, sliders, value_edits)

        slider_max_edit.returnPressed.connect(apply)
        slider_max_edit.editingFinished.connect(apply)

    def _make_adjustment_slider_handler(self, key: str, value_edit: QLineEdit):
        def handler(value: int) -> None:
            value_edit.blockSignals(True)
            value_edit.setText(str(value))
            value_edit.blockSignals(False)
            self._on_adjustment_slider_changed(key, value)

        return handler

    def _on_adjustment_percent_editing_finished(
        self,
        key: str,
        value_edit: QLineEdit,
        slider: QSlider,
    ) -> None:
        text = value_edit.text().strip()
        if not text:
            value_edit.setText(str(slider.value()))
            return
        try:
            value = int(text)
        except ValueError:
            value_edit.setText(str(slider.value()))
            return
        value = max(0, min(self.source_slider_max, value))
        slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(False)
        value_edit.setText(str(value))
        self._on_adjustment_slider_changed(key, value)

    def _source_adjustment_values(self) -> dict[str, int]:
        return {
            "brightness": self.source_brightness,
            "red": self.source_red,
            "green": self.source_green,
            "blue": self.source_blue,
        }

    def _sync_adjustment_sliders(self, sliders: dict, value_edits: dict) -> None:
        for key, value in self._source_adjustment_values().items():
            slider = sliders[key]
            slider.blockSignals(True)
            slider.setRange(0, self.source_slider_max)
            slider.setValue(value)
            slider.blockSignals(False)
            value_edit = value_edits[key]
            value_edit.blockSignals(True)
            value_edit.setText(str(value))
            value_edit.blockSignals(False)

    def _update_adjustment_slider_max(
        self,
        slider_max_edit: QLineEdit,
        sliders: dict,
        value_edits: dict,
    ) -> None:
        old_max = self.source_slider_max
        try:
            slider_max = int(float(slider_max_edit.text().strip().replace(",", ".")))
        except ValueError:
            slider_max = DEFAULT_NORMALIZE_SLIDER_MAX
        new_max = max(MIN_ADJUSTMENT_SLIDER_MAX, min(MAX_ADJUSTMENT_SLIDER_MAX, slider_max))
        self.source_slider_max = new_max
        slider_max_edit.setText(str(self.source_slider_max))
        if new_max != old_max:
            self.source_brightness = rescale_adjustment_percent(
                self.source_brightness, old_max, new_max
            )
            self.source_red = rescale_adjustment_percent(self.source_red, old_max, new_max)
            self.source_green = rescale_adjustment_percent(self.source_green, old_max, new_max)
            self.source_blue = rescale_adjustment_percent(self.source_blue, old_max, new_max)
        for slider in sliders.values():
            slider.setRange(0, self.source_slider_max)
        self._sync_adjustment_sliders(sliders, value_edits)
        self._apply_source_adjustments()

    def open_image(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "JPG auswählen",
            "",
            "Bilder (*.jpg *.jpeg *.png *.bmp)",
        )
        if not file_name:
            return
        self.original_image = Image.open(file_name).convert("RGB")
        self._apply_source_adjustments()

    def rotate_original_clockwise(self) -> None:
        if self.original_image is None:
            return
        self.original_image = self.original_image.rotate(-90, expand=True)
        self._apply_source_adjustments()

    def _apply_source_adjustments(self) -> None:
        if self.original_image is None:
            return
        self.adjusted_image = apply_rgb_adjustment(
            self.original_image,
            brightness_percent=self.source_brightness,
            red_percent=self.source_red,
            green_percent=self.source_green,
            blue_percent=self.source_blue,
        )
        self.mono_luminances = None
        self.original_pixmap = pil_to_qpixmap(self.adjusted_image)
        self._update_original_preview()
        self.recompute_all()

    def _on_adjustment_slider_changed(self, key: str, value: int) -> None:
        if key == "brightness":
            self.source_brightness = value
        elif key == "red":
            self.source_red = value
        elif key == "green":
            self.source_green = value
        elif key == "blue":
            self.source_blue = value
        self._apply_source_adjustments()

    def _reset_source_adjustments(self, sliders: dict, value_edits: dict) -> None:
        self.source_brightness = 100
        self.source_red = 100
        self.source_green = 100
        self.source_blue = 100
        self._sync_adjustment_sliders(sliders, value_edits)
        self._apply_source_adjustments()

    def _normalize_source_rgb(self) -> None:
        if self.original_image is None:
            return
        self.source_brightness = 100
        self.source_red, self.source_green, self.source_blue = rgb_normalize_slider_values(
            self.original_image,
            slider_max=self.source_slider_max,
        )
        refs = getattr(self, "_adjustment_dialog_refs", None)
        if refs is not None:
            sliders, value_edits = refs
            self._sync_adjustment_sliders(sliders, value_edits)
        self._apply_source_adjustments()

    def _average_source_rgb(self) -> None:
        if self.original_image is None:
            return
        self.source_brightness = 100
        self.source_red, self.source_green, self.source_blue = rgb_average_slider_values(
            self.original_image,
            slider_max=self.source_slider_max,
        )
        refs = getattr(self, "_adjustment_dialog_refs", None)
        if refs is not None:
            sliders, value_edits = refs
            self._sync_adjustment_sliders(sliders, value_edits)
        self._apply_source_adjustments()

    def _express_source_rgb(self) -> None:
        if self.original_image is None:
            return
        self.original_image = apply_rgb_express(self.adjusted_image or self.original_image)
        self.source_brightness = 100
        self.source_red = 100
        self.source_green = 100
        self.source_blue = 100
        refs = getattr(self, "_adjustment_dialog_refs", None)
        if refs is not None:
            sliders, value_edits = refs
            self._sync_adjustment_sliders(sliders, value_edits)
        self._apply_source_adjustments()

    def _depress_source_rgb(self) -> None:
        if self.original_image is None:
            return
        self.original_image = apply_rgb_depress(self.adjusted_image or self.original_image)
        self.source_brightness = 100
        self.source_red = 100
        self.source_green = 100
        self.source_blue = 100
        refs = getattr(self, "_adjustment_dialog_refs", None)
        if refs is not None:
            sliders, value_edits = refs
            self._sync_adjustment_sliders(sliders, value_edits)
        self._apply_source_adjustments()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_original_preview()

    def _update_original_preview(self) -> None:
        if self.original_pixmap is None:
            return
        scaled = self.original_pixmap.scaled(
            self.original_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.original_label.setPixmap(scaled)

    def _update_average_previews(self) -> None:
        if self.adjusted_image is None:
            return
        average_320 = average_raster_preview(self.adjusted_image, (320, 200), upscale_factor=4)
        average_160 = average_raster_preview(
            self.adjusted_image,
            (160, 200),
            upscale_factor=4,
            stretch_horizontal=True,
        )
        self.average_320_label.setPixmap(pil_to_qpixmap(average_320))
        self.average_160_label.setPixmap(pil_to_qpixmap(average_160))

    def recompute_all(self) -> None:
        if self.adjusted_image is None:
            return
        self.hires_result = convert_to_hires(
            self.adjusted_image,
            background_color=int(self.hires_bg_combo.currentData()),
            upscale_factor=4,
        )
        self.multicolor_result = convert_to_multicolor(self.adjusted_image, upscale_factor=4)
        self.grayscale_result = convert_to_grayscale(self.adjusted_image, upscale_factor=4)
        self.recompute_mono()
        self._update_average_previews()
        self._update_c64_previews()

    def recompute_mono(self) -> None:
        if self.adjusted_image is None:
            return
        if self.mono_luminances is None:
            self.mono_luminances = compute_mono_luminances(self.adjusted_image)
        threshold = float(self.threshold_slider.value())
        self.mono_result = convert_to_mono(
            self.adjusted_image,
            threshold=threshold,
            fg_color=int(self.mono_fg_combo.currentData()),
            bg_color=int(self.mono_bg_combo.currentData()),
            upscale_factor=4,
        )
        self._update_c64_previews()
        pct = foreground_percent_for_threshold(self.mono_luminances, threshold)
        self.mono_percent_edit.blockSignals(True)
        self.mono_percent_edit.setText(f"{pct:.2f}")
        self.mono_percent_edit.blockSignals(False)

    def _update_c64_previews(self) -> None:
        if self.hires_result is not None:
            self.hires_label.setPixmap(
                pil_to_qpixmap(self._with_c64_border(self.hires_result.preview_upscaled))
            )
        if self.multicolor_result is not None:
            self.multicolor_label.setPixmap(
                pil_to_qpixmap(self._with_c64_border(self.multicolor_result.preview_upscaled))
            )
        if self.mono_result is not None:
            self.mono_label.setPixmap(
                pil_to_qpixmap(self._with_c64_border(self.mono_result.preview_upscaled))
            )
        if self.grayscale_result is not None:
            self.grayscale_label.setPixmap(
                pil_to_qpixmap(self._with_c64_border(self.grayscale_result.preview_upscaled))
            )

    def _with_c64_border(self, image: Image.Image) -> Image.Image:
        scale = max(1, image.height // 200)
        border = 12 * scale
        bordered = Image.new(
            "RGB",
            (image.width + border * 2, image.height + border * 2),
            C64_PALETTE[self.c64_border_color],
        )
        bordered.paste(image, (border, border))
        return bordered

    def _on_mono_percent_editing_finished(self) -> None:
        if self.original_image is None or self.mono_luminances is None:
            return
        text = self.mono_percent_edit.text().strip().replace(",", ".")
        if not text:
            return
        try:
            percent = float(text)
        except ValueError:
            return
        percent = max(0.0, min(100.0, percent))
        t = threshold_for_foreground_percent(self.mono_luminances, percent)
        self.threshold_slider.blockSignals(True)
        self.threshold_slider.setValue(t)
        self.threshold_slider.blockSignals(False)
        self.recompute_mono()

    def export_all(self) -> None:
        if self.original_image is None:
            QMessageBox.warning(self, "Kein Bild", "Bitte zuerst ein Bild laden.")
            return
        if (
            self.hires_result is None
            or self.multicolor_result is None
            or self.mono_result is None
            or self.grayscale_result is None
        ):
            self.recompute_all()
        default_export_dir = _default_export_dir()
        default_export_dir.mkdir(parents=True, exist_ok=True)
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Export-Ordner wählen",
            str(default_export_dir),
        )
        if not output_dir:
            return
        out = Path(output_dir)
        base = self._next_export_base_name(out)

        export_hires_prg_program(
            out / f"{base}_hires",
            HiresFrame(
                bitmap=self.hires_result.bitmap,
                screen_ram=self.hires_result.screen_ram,
                background_color=self.hires_result.background_color,
                border_color=self.c64_border_color,
            ),
        )
        self._save_bordered_bmp(out / f"{base}_hires.bmp", self.hires_result.preview_upscaled)
        mono_fg = int(self.mono_fg_combo.currentData())
        mono_bg = int(self.mono_bg_combo.currentData())
        mono_screen = bytes([((mono_fg & 0x0F) << 4) | (mono_bg & 0x0F)] * 1000)
        export_hires_prg_program(
            out / f"{base}_mono",
            HiresFrame(
                bitmap=self.mono_result.bitmap,
                screen_ram=mono_screen,
                background_color=mono_bg,
                border_color=self.c64_border_color,
            ),
        )
        self._save_bordered_bmp(out / f"{base}_mono.bmp", self.mono_result.preview_upscaled)
        export_multicolor_prg_program(
            out / f"{base}_multicolor",
            self.multicolor_result.frame.with_border_color(self.c64_border_color),
        )
        self._save_bordered_bmp(
            out / f"{base}_multicolor.bmp",
            self.multicolor_result.preview_upscaled,
        )
        export_multicolor_prg_program(
            out / f"{base}_grayscale",
            self.grayscale_result.frame.with_border_color(self.c64_border_color),
        )
        self._save_bordered_bmp(
            out / f"{base}_grayscale.bmp",
            self.grayscale_result.preview_upscaled,
        )
        QMessageBox.information(self, "Export", f"Export abgeschlossen:\n{out}")

    def _save_bordered_bmp(self, output_path: Path, image: Image.Image) -> None:
        self._with_c64_border(image).save(output_path, format="BMP")

    def _next_export_base_name(self, output_dir: Path) -> str:
        variants = ("hires", "mono", "multicolor", "grayscale")
        extensions = (".prg", ".asm", ".bas", ".bmp")
        index = 1
        while True:
            candidate = f"image_{index:03d}"
            existing = [
                output_dir / f"{candidate}_{variant}{extension}"
                for variant in variants
                for extension in extensions
            ]
            if not any(path.exists() for path in existing):
                return candidate
            index += 1
