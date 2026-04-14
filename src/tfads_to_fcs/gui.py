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
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .converter import ConversionError, convert_to_fcs


def _find_logo() -> Path | None:
    explicit = "logo.png"
    candidates = [
        Path(__file__).resolve().parents[2] / explicit,
        Path.cwd() / explicit,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


class DropZone(QFrame):
    file_dropped = Signal(list)
    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("dropZone")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(6)

        self.title = QLabel("Drop .xls / .csv / .tsv files here")
        self.title.setObjectName("dropTitle")
        self.title.setAlignment(Qt.AlignCenter)

        self.subtitle = QLabel("or click to browse")
        self.subtitle.setObjectName("dropSubtitle")
        self.subtitle.setAlignment(Qt.AlignCenter)

        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setVisible(False)
        self.file_list.setAlternatingRowColors(True)

        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.file_list)

    def set_selected(self, paths: list[Path]) -> None:
        self.file_list.clear()
        if len(paths) == 1:
            self.title.setText(paths[0].name)
            self.subtitle.setText(str(paths[0]))
            self.file_list.setVisible(False)
        else:
            self.title.setText(f"{len(paths)} files selected")
            self.subtitle.setText("Click to add more files")
            for path in paths:
                self.file_list.addItem(f"{path.name}  —  {path}")
            self.file_list.setVisible(True)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):  # noqa: N802
        urls = event.mimeData().urls()
        if not urls:
            return
        paths = []
        for url in urls:
            local_path = url.toLocalFile()
            if local_path:
                paths.append(local_path)
        if paths:
            self.file_dropped.emit(paths)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ConvertWorker(QObject):
    status = Signal(str)
    progress_update = Signal(int, int)  # current, total
    done = Signal(list)  # list of output paths
    failed = Signal(str)

    def __init__(self, input_paths: list[Path]) -> None:
        super().__init__()
        self.input_paths = input_paths

    def run(self) -> None:
        output_paths = []
        total = len(self.input_paths)
        try:
            for idx, input_path in enumerate(self.input_paths, 1):
                self.progress_update.emit(idx, total)
                if total == 1:
                    self.status.emit(f"Converting: {input_path.name}")
                else:
                    self.status.emit(f"Converting {idx}/{total}: {input_path.name}")
                output = convert_to_fcs(input_path)
                output_paths.append(str(output))
            self.done.emit(output_paths)
        except ConversionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Unexpected error: {exc}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("TFADS to FCS Converter")
        self.setMinimumSize(760, 460)

        self.input_paths: list[Path] = []
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
            QListWidget#fileList {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                font-size: 12px;
                color: #334155;
            }
            QListWidget#fileList::item {
                padding: 6px 10px;
            }
            QListWidget#fileList::item:selected {
                background: #e0f2fe;
                color: #0c4a6e;
            }
            """
        )

    def _browse_file(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select input file(s)",
            str(Path.cwd()),
            "Data files (*.xls *.csv *.tsv *.txt);;All files (*.*)",
        )
        if file_paths:
            new_paths = [Path(p) for p in file_paths]
            if self.input_paths:
                self._set_input(self.input_paths + new_paths)
            else:
                self._set_input(new_paths)

    def _select_file_from_drop(self, file_paths: list[str]) -> None:
        paths = [Path(p) for p in file_paths if Path(p).exists() and not Path(p).is_dir()]
        if not paths:
            QMessageBox.warning(self, "Invalid file", "Please select a valid file.")
            return
        if self.input_paths:
            self._set_input(self.input_paths + paths)
        else:
            self._set_input(paths)

    def _set_input(self, paths: list[Path]) -> None:
        self.input_paths = [p.resolve() for p in paths]
        self.drop_zone.set_selected(self.input_paths)
        self.convert_button.setEnabled(True)
        if len(self.input_paths) == 1:
            self.status_label.setText("Ready to convert.")
        else:
            self.status_label.setText(f"{len(self.input_paths)} files ready to convert.")

    def _start_conversion(self) -> None:
        if not self.input_paths:
            return

        self.convert_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.status_label.setText("Starting conversion...")

        self.worker_thread = QThread(self)
        self.worker = ConvertWorker(self.input_paths)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.status.connect(self.status_label.setText)
        self.worker.progress_update.connect(self._update_progress)
        self.worker.done.connect(self._on_success)
        self.worker.failed.connect(self._on_failure)

        self.worker.done.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._on_thread_finished)

        self.worker_thread.start()

    def _on_success(self, output_paths: list[str]) -> None:
        if len(output_paths) == 1:
            self.status_label.setText(f"Conversion completed: {output_paths[0]}")
            QMessageBox.information(self, "Success", f"FCS file created:\n{output_paths[0]}")
        else:
            self.status_label.setText(f"{len(output_paths)} conversions completed.")
            QMessageBox.information(
                self,
                "Success",
                f"{len(output_paths)} FCS files created:\n" + "\n".join(output_paths),
            )

    def _on_failure(self, message: str) -> None:
        self.status_label.setText("Conversion failed.")
        QMessageBox.critical(self, "Conversion failed", message)

    def _update_progress(self, current: int, total: int) -> None:
        if total > 1:
            self.progress.setRange(0, total)
            self.progress.setValue(current)

    def _on_thread_finished(self) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.convert_button.setEnabled(bool(self.input_paths))
        self.worker = None
        self.worker_thread = None


def run_gui() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
