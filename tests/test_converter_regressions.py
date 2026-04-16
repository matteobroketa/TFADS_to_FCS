from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tfads_to_fcs.converter import ConversionError, convert_to_fcs


class ConverterRegressionTests(unittest.TestCase):
    def test_rejects_unsupported_fcs_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "already_converted.fcs"
            input_path.write_bytes(b"FCS3.0\x00\x01\x02")

            with self.assertRaises(ConversionError):
                convert_to_fcs(input_path)

    def test_wraps_parser_value_error_as_conversion_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "bad.xls"
            input_path.write_text(
                "A\tB\n"
                "not-a-number\t2\n",
                encoding="utf-8",
            )

            with self.assertRaises(ConversionError):
                convert_to_fcs(input_path)

    def test_accepts_rows_missing_trailing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "sparse.xls"
            input_path.write_text(
                "A\tB\tC\n"
                "1\t2\t3\n"
                "4\t5\n",
                encoding="utf-8",
            )

            output_path = convert_to_fcs(input_path)

            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
