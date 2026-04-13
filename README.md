# TFADS to FCS 3.0 Converter

Minimal desktop app to convert TFADS-exported `.xls` data tables into `.fcs` (FCS 3.0).

## Features

- Drag and drop input file
- One-click conversion (`Convert`)
- Clean single-screen desktop UI
- FCS 3.0 output using 32-bit float data (`$DATATYPE=F`)
- Streaming conversion (does not load all events into memory)
- Cross-platform build targets (Windows, macOS, Linux)

## Input Format

This build supports delimited text tables, including TFADS text-export files often named `.xls`, plus `.csv`/`.tsv`/`.txt`.

Expected format:

- First line is column headers (for example: `Time [ms]`, `PMT1 [Blue]`, ...)
- Remaining lines are numeric values only
- Delimiters: tab, comma, semicolon, or pipe

If your `.xls` is a true binary Excel workbook, export it as TSV/CSV first.

## Local Run

1. Install Python 3.11+
2. Install dependencies:

```bash
pip install -e .
```

3. Launch UI:

```bash
python -m tfads_to_fcs
```

4. Optional CLI mode:

```bash
python -m tfads_to_fcs "Live Data_time(ms)_PMT1_PMT2_PMT3.xls"
```

## Build Local Binary (PyInstaller)

Install build tool:

```bash
pip install pyinstaller
```

Build one-file executable:

- Windows:

```powershell
pyinstaller --noconfirm --clean --windowed --onefile --name TFADS_to_FCS --paths src --hidden-import tfads_to_fcs.gui --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets --add-data "Gemini_Generated_Image_72a67r72a67r72a6.png;." app.py
```

- macOS/Linux:

```bash
pyinstaller --noconfirm --clean --windowed --onefile --name TFADS_to_FCS --paths src --hidden-import tfads_to_fcs.gui --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets --add-data "Gemini_Generated_Image_72a67r72a67r72a6.png:." app.py
```

The executable appears in `dist/`.

## GitHub Releases (All OS)

Push a tag like `v0.1.0`. The workflow in `.github/workflows/release.yml` builds and uploads:

- `TFADS_to_FCS-windows.zip`
- `TFADS_to_FCS-macos.zip`
- `TFADS_to_FCS-linux.zip`

Each archive contains a ready-to-run binary from the corresponding runner OS.
