import csv
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import storage_scan


class CsvReportTests(unittest.TestCase):
    def test_write_csv_report_flattens_all_report_sections(self) -> None:
        writer = getattr(storage_scan, "write_csv_report", None)
        if writer is None:
            self.fail("CSV report writer is missing")
            return

        report = {
            "scan_root": r"C:\\Data",
            "generated_at": "2026-10-13T00:00:00+0800",
            "duration_seconds": 1.25,
            "timed_out": False,
            "files_seen": 2,
            "errors": 0,
            "skipped_reparse_points": 1,
            "disk": {
                "total_bytes": 1_000,
                "used_bytes": 600,
                "free_bytes": 400,
            },
            "breakdowns": {
                "scan_root": [
                    {"name": "Documents, Work", "size_bytes": 300},
                ]
            },
            "largest_files": [
                {"path": r"C:\\Data\\Documents, Work\\report.txt", "size_bytes": 200},
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.csv"
            writer(report, output)

            with output.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(
            list(rows[0]),
            ["section", "category", "name", "path", "size_bytes", "value"],
        )
        self.assertIn(
            {
                "section": "summary",
                "category": "",
                "name": "scan_root",
                "path": "",
                "size_bytes": "",
                "value": r"C:\\Data",
            },
            rows,
        )
        self.assertIn(
            {
                "section": "disk",
                "category": "",
                "name": "used_bytes",
                "path": "",
                "size_bytes": "600",
                "value": "",
            },
            rows,
        )
        self.assertIn(
            {
                "section": "breakdown",
                "category": "scan_root",
                "name": "Documents, Work",
                "path": "",
                "size_bytes": "300",
                "value": "",
            },
            rows,
        )
        self.assertIn(
            {
                "section": "largest_file",
                "category": "",
                "name": "",
                "path": r"C:\\Data\\Documents, Work\\report.txt",
                "size_bytes": "200",
                "value": "",
            },
            rows,
        )

    def test_write_csv_report_escapes_formula_cells(self) -> None:
        report = {
            "scan_root": r"C:\\Data",
            "generated_at": "2026-10-13T00:00:00+0800",
            "duration_seconds": 1.25,
            "timed_out": False,
            "files_seen": 1,
            "errors": 0,
            "skipped_reparse_points": 0,
            "disk": {"total_bytes": 1_000, "used_bytes": 600, "free_bytes": 400},
            "breakdowns": {
                "scan_root": [
                    {"name": "=2+2", "size_bytes": 5},
                    {"name": "  @SUM(1,1)", "size_bytes": 4},
                ]
            },
            "largest_files": [],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.csv"
            storage_scan.write_csv_report(report, output)

            with output.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))

        names = {row["name"] for row in rows if row["section"] == "breakdown"}
        self.assertEqual(names, {"'=2+2", "'  @SUM(1,1)"})

    def test_scan_writes_csv_when_requested(self) -> None:
        self.assertIn(
            "output_format",
            inspect.signature(storage_scan.scan).parameters,
            "scan() does not accept an output format",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "input"
            root.mkdir()
            (root / "example.txt").write_text("hello", encoding="utf-8")
            output = Path(temp_dir) / "report.csv"

            storage_scan.scan(
                root,
                output,
                top_files=10,
                time_limit=30,
                output_format="csv",
            )

            with output.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(any(row["section"] == "largest_file" for row in rows))

    def test_scan_preserves_json_output_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "input"
            root.mkdir()
            (root / "example.txt").write_text("hello", encoding="utf-8")
            output = Path(temp_dir) / "report.json"

            report = storage_scan.scan(root, output, top_files=10, time_limit=30)
            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(written, report)

    def test_scan_rejects_unknown_output_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "input"
            root.mkdir()
            output = Path(temp_dir) / "report.txt"

            with self.assertRaisesRegex(ValueError, "Unsupported output format"):
                storage_scan.scan(
                    root,
                    output,
                    top_files=10,
                    time_limit=30,
                    output_format="xml",
                )

    def test_cli_accepts_csv_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "input"
            root.mkdir()
            (root / "example.txt").write_text("hello", encoding="utf-8")
            output = Path(temp_dir) / "report.csv"

            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(storage_scan.__file__)),
                    "--root",
                    str(root),
                    "--output",
                    str(output),
                    "--format",
                    "csv",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.exists())
            self.assertIn("section,category,name,path,size_bytes,value", output.read_text(encoding="utf-8-sig"))

    def test_cli_uses_format_specific_default_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "input"
            root.mkdir()
            (root / "example.txt").write_text("hello", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(storage_scan.__file__)),
                    "--root",
                    str(root),
                    "--format",
                    "csv",
                ],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(temp_dir) / "storage_scan_report.csv").exists())


if __name__ == "__main__":
    unittest.main()
