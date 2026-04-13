from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np

ProgressCallback = Callable[[str], None]

_OLE2_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
_ZIP_MAGIC = b"PK\x03\x04"
_DELIMITERS = ("\t", ",", ";", "|")
_TEXT_START = 58
_OFFSET_WIDTH = 12


@dataclass(slots=True)
class ScanResult:
    columns: list[str]
    total_events: int
    ranges: list[int]
    delimiter: str


class ConversionError(RuntimeError):
    pass


def convert_to_fcs(
    input_path: str | Path,
    output_path: str | Path | None = None,
    progress: ProgressCallback | None = None,
) -> Path:
    input_file = Path(input_path).expanduser().resolve()
    if not input_file.exists():
        raise ConversionError(f"Input file not found: {input_file}")
    if input_file.is_dir():
        raise ConversionError(f"Input path is a directory: {input_file}")

    output_file = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else input_file.with_suffix(".fcs")
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    _emit(progress, "Inspecting input format...")
    _assert_supported_input(input_file)

    _emit(progress, "Scanning rows...")
    scan = _scan_text_table(input_file)
    if scan.total_events <= 0:
        raise ConversionError("No numeric events found in the input file.")

    _emit(progress, "Writing FCS 3.0 file...")
    _write_fcs(input_file, output_file, scan)
    _emit(progress, f"Done: {output_file.name}")

    return output_file


def _emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _assert_supported_input(path: Path) -> None:
    with path.open("rb") as handle:
        head = handle.read(8)
    if head.startswith(_OLE2_MAGIC) or head.startswith(_ZIP_MAGIC):
        raise ConversionError(
            "Binary Excel workbooks are not supported by this build. "
            "Use TFADS text export (.xls tab-delimited) or CSV/TSV."
        )


def _scan_text_table(path: Path) -> ScanResult:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        header_line = handle.readline()
        if not header_line:
            raise ConversionError("Input file is empty.")

        delimiter = _detect_delimiter(header_line)
        columns = [c.strip() for c in header_line.strip().split(delimiter)]
        if len(columns) < 1:
            raise ConversionError("No columns detected in header row.")

        total_events = 0
        mins = np.full(len(columns), np.inf, dtype=np.float64)
        maxs = np.full(len(columns), -np.inf, dtype=np.float64)

        for row_index, line in enumerate(handle, start=2):
            stripped = line.strip()
            if not stripped:
                continue

            values = np.fromstring(stripped, sep=delimiter, dtype=np.float64)
            if values.size != len(columns):
                raise ConversionError(
                    f"Line {row_index}: expected {len(columns)} numeric values, got {values.size}."
                )
            if not np.all(np.isfinite(values)):
                raise ConversionError(f"Line {row_index}: found NaN or infinite value.")

            mins = np.minimum(mins, values)
            maxs = np.maximum(maxs, values)
            total_events += 1

    ranges = [_compute_range(mins[i], maxs[i]) for i in range(len(columns))]
    return ScanResult(columns=columns, total_events=total_events, ranges=ranges, delimiter=delimiter)


def _detect_delimiter(header_line: str) -> str:
    counts = {d: header_line.count(d) for d in _DELIMITERS}
    delimiter, count = max(counts.items(), key=lambda item: item[1])
    if count <= 0:
        raise ConversionError(
            "Could not detect delimiter. Supported delimiters: tab, comma, semicolon, pipe."
        )
    return delimiter


def _compute_range(min_value: float, max_value: float) -> int:
    if min_value == max_value:
        return max(1, int(math.ceil(abs(max_value))))
    if min_value < 0:
        return max(1, int(math.ceil(max_value - min_value)))
    return max(1, int(math.ceil(max_value)))


def _iter_numeric_rows(path: Path, expected_cols: int, delimiter: str):
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        _ = handle.readline()
        for row_index, line in enumerate(handle, start=2):
            stripped = line.strip()
            if not stripped:
                continue
            values = np.fromstring(stripped, sep=delimiter, dtype=np.float64)
            if values.size != expected_cols:
                raise ConversionError(
                    f"Line {row_index}: expected {expected_cols} numeric values, got {values.size}."
                )
            if not np.all(np.isfinite(values)):
                raise ConversionError(f"Line {row_index}: found NaN or infinite value.")
            yield values


def _sanitize_value(value: str, delimiter: str) -> str:
    return value.replace(delimiter, delimiter + delimiter)


def _build_text_segment(keywords: list[tuple[str, str]], delimiter: str = "|") -> bytes:
    parts = [delimiter]
    for key, value in keywords:
        parts.append(_sanitize_value(key, delimiter))
        parts.append(delimiter)
        parts.append(_sanitize_value(value, delimiter))
        parts.append(delimiter)
    text = "".join(parts)
    return text.encode("ascii", errors="replace")


def _header_field(number: int) -> str:
    if 0 <= number <= 99_999_999:
        return f"{number:>8d}"
    return f"{0:>8d}"


def _fcs_header(
    text_start: int,
    text_end: int,
    data_start: int,
    data_end: int,
    analysis_start: int = 0,
    analysis_end: int = 0,
) -> bytes:
    header = (
        "FCS3.0    "
        f"{_header_field(text_start)}"
        f"{_header_field(text_end)}"
        f"{_header_field(data_start)}"
        f"{_header_field(data_end)}"
        f"{_header_field(analysis_start)}"
        f"{_header_field(analysis_end)}"
    )
    if len(header) != 58:
        raise ConversionError("Internal error: FCS header must be exactly 58 bytes.")
    return header.encode("ascii")


def _write_fcs(input_file: Path, output_file: Path, scan: ScanResult) -> None:
    par = len(scan.columns)
    tot = scan.total_events
    data_bytes = tot * par * 4

    now = datetime.now()
    out_name = output_file.name

    keywords: list[tuple[str, str]] = [
        ("$BEGINANALYSIS", "0"),
        ("$ENDANALYSIS", "0"),
        ("$BEGINSTEXT", "0"),
        ("$ENDSTEXT", "0"),
        ("$BEGINDATA", "0" * _OFFSET_WIDTH),
        ("$ENDDATA", "0" * _OFFSET_WIDTH),
        ("$BYTEORD", "1,2,3,4"),
        ("$DATATYPE", "F"),
        ("$MODE", "L"),
        ("$NEXTDATA", "0"),
        ("$PAR", str(par)),
        ("$TOT", str(tot)),
        ("$DATE", now.strftime("%d-%b-%Y").upper()),
        ("$CYT", "TFADS"),
        ("$FIL", out_name),
    ]

    for index, name in enumerate(scan.columns, start=1):
        safe_name = name.strip() or f"P{index}"
        keywords.extend(
            [
                (f"$P{index}B", "32"),
                (f"$P{index}E", "0,0"),
                (f"$P{index}N", safe_name),
                (f"$P{index}S", safe_name),
                (f"$P{index}R", str(scan.ranges[index - 1])),
            ]
        )

    text_segment = _build_text_segment(keywords)
    text_start = _TEXT_START
    text_end = text_start + len(text_segment) - 1
    data_start = text_end + 1
    data_end = data_start + data_bytes - 1

    begin_data = f"{data_start:0{_OFFSET_WIDTH}d}"
    end_data = f"{data_end:0{_OFFSET_WIDTH}d}"

    patched_keywords = []
    for key, value in keywords:
        if key == "$BEGINDATA":
            patched_keywords.append((key, begin_data))
        elif key == "$ENDDATA":
            patched_keywords.append((key, end_data))
        else:
            patched_keywords.append((key, value))

    patched_text_segment = _build_text_segment(patched_keywords)
    if len(patched_text_segment) != len(text_segment):
        raise ConversionError("Internal error: text segment size changed after patching offsets.")
    text_segment = patched_text_segment

    header = _fcs_header(text_start, text_end, data_start, data_end)
    pack_row = np.ndarray.tobytes

    with output_file.open("wb") as handle:
        handle.write(header)
        handle.write(text_segment)

        current = handle.tell()
        if current != data_start:
            if current > data_start:
                raise ConversionError("Internal error: data start offset mismatch.")
            handle.write(b" " * (data_start - current))

        for values in _iter_numeric_rows(input_file, par, scan.delimiter):
            as_float32 = values.astype("<f4", copy=False)
            handle.write(pack_row(as_float32))
