from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .converter import ConversionError, convert_to_fcs


def _find_logo() -> Path | None:
    explicit = "Gemini_Generated_Image_72a67r72a67r72a6.png"
    candidates = [
        Path(__file__).resolve().parents[2] / explicit,
        Path.cwd() / explicit,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


class DropZone(QFrame):
    file_dropped = Signal(str)
    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("dropZone")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(6)

        self.title = QLabel("Drop .xls / .csv / .tsv file here")
        self.title.setObjectName("dropTitle")
        self.title.setAlignment(Qt.AlignCenter)

        self.subtitle = QLabel("or click to browse")
        self.subtitle.setObjectName("dropSubtitle")
        self.subtitle.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)

    def set_selected(self, path: Path) -> None:
        self.title.setText(path.name)
        self.subtitle.setText(str(path))

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802
        urls = event.mimeData().urls()
        if not urls:
            return
        local_path = urls[0].toLocalFile()
        if local_path:
            self.file_dropped.emit(local_path)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ConvertWorker(QObject):
    status = Signal(str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, input_path: Path) -> None:
        super().__init__()
        self.input_path = input_path

    def run(self) -> None:
        try:
            output = convert_to_fcs(self.input_path, progress=self.status.emit)
            self.done.emit(str(output))
        except ConversionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unexpected error: {exc}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TFADS to FCS Converter")
        self.setMinimumSize(760, 460)

        self.input_path: Path | None = None
        self.worker_thread: QThread | None = None
        self.worker: ConvertWorker | None = None

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(12)

        logo_label = QLabel()
        logo_label.setFixedSize(84, 84)
        logo_label.setAlignment(Qt.AlignCenter)

        logo_path = _find_logo()
        if logo_path:
            pixmap = QPixmap(str(logo_path)).scaled(
                80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_label.setPixmap(pixmap)

        title_stack = QVBoxLayout()
        title = QLabel("TFADS to FCS 3.0")
        title.setObjectName("title")
        subtitle = QLabel("Drag, drop, convert.")
        subtitle.setObjectName("subtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        title_stack.addStretch(1)

        header.addWidget(logo_label)
        header.addLayout(title_stack, 1)
        root.addLayout(header)

        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._select_file_from_drop)
        self.drop_zone.clicked.connect(self._browse_file)
        root.addWidget(self.drop_zone)

        self.convert_button = QPushButton("Convert")
        self.convert_button.setObjectName("convertButton")
        self.convert_button.setEnabled(False)
        self.convert_button.clicked.connect(self._start_conversion)
        root.addWidget(self.convert_button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        root.addWidget(self.progress)

        self.status_label = QLabel("Choose a file to start.")
        self.status_label.setObjectName("status")
        root.addWidget(self.status_label)

        self.setCentralWidget(container)
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #f5f7fb;
                color: #182230;
                font-family: "Segoe UI", "Helvetica Neue", "Noto Sans", sans-serif;
                font-size: 14px;
            }
            QLabel#title {
                font-size: 26px;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#subtitle {
                color: #475569;
                font-size: 14px;
            }
            QFrame#dropZone {
                border: 2px dashed #94a3b8;
                border-radius: 14px;
                background: #ffffff;
            }
            QLabel#dropTitle {
                font-size: 17px;
                font-weight: 600;
                color: #0f172a;
            }
            QLabel#dropSubtitle {
                font-size: 12px;
                color: #64748b;
            }
            QPushButton#convertButton {
                background: #0f766e;
                color: #ffffff;
                border: none;
                border-radius: 10px;
                min-height: 44px;
                font-size: 15px;
                font-weight: 700;
            }
            QPushButton#convertButton:disabled {
                background: #9ca3af;
            }
            QPushButton#convertButton:hover:!disabled {
                background: #0d9488;
            }
            QProgressBar {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                background: #ffffff;
                min-height: 10px;
            }
            QProgressBar::chunk {
                background: #0f766e;
                border-radius: 8px;
            }
            QLabel#status {
                color: #334155;
            }
            """
        )

    def _browse_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select input file",
            str(Path.cwd()),
            "Data files (*.xls *.csv *.tsv *.txt);;All files (*.*)",
        )
        if file_path:
            self._set_input(Path(file_path))

    def _select_file_from_drop(self, file_path: str) -> None:
        self._set_input(Path(file_path))

    def _set_input(self, path: Path) -> None:
        if not path.exists() or path.is_dir():
            QMessageBox.warning(self, "Invalid file", "Please select a valid file.")
            return

        self.input_path = path.resolve()
        self.drop_zone.set_selected(self.input_path)
        self.convert_button.setEnabled(True)
        self.status_label.setText("Ready to convert.")

    def _start_conversion(self) -> None:
        if self.input_path is None:
            return

        self.convert_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.status_label.setText("Starting conversion...")

        self.worker_thread = QThread(self)
        self.worker = ConvertWorker(self.input_path)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.status.connect(self.status_label.setText)
        self.worker.done.connect(self._on_success)
        self.worker.failed.connect(self._on_failure)

        self.worker.done.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._on_thread_finished)

        self.worker_thread.start()

    def _on_success(self, output_path: str) -> None:
        self.status_label.setText(f"Conversion completed: {output_path}")
        QMessageBox.information(self, "Success", f"FCS file created:\n{output_path}")

    def _on_failure(self, message: str) -> None:
        self.status_label.setText("Conversion failed.")
        QMessageBox.critical(self, "Conversion failed", message)

    def _on_thread_finished(self) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.convert_button.setEnabled(self.input_path is not None)
        self.worker = None
        self.worker_thread = None


def run_gui() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
