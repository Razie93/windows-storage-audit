# Windows Storage Audit

A read-only Python utility that scans a Windows drive or directory and creates a JSON or CSV report of:

- Largest top-level folders
- User profile and `AppData` usage
- Installed application folders
- Largest individual files
- Total, used, and free disk space

The scanner **does not delete or modify files**.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer

## Usage

Scan the system drive:

```bat
python storage_scan.py
```

Scan a specific directory:

```bat
python storage_scan.py --root "C:\Users\YourName\Downloads"
```

Choose the output file and number of large files recorded:

```bat
python storage_scan.py --output my-report.json --top-files 50
```

Create a spreadsheet-friendly CSV report:

```bat
python storage_scan.py --format csv --output my-report.csv
```

When `--output` is omitted, the report is named `storage_scan_report.json` or
`storage_scan_report.csv` according to the selected format.

Limit the scan to five minutes:

```bat
python storage_scan.py --time-limit 300
```

## Output

Both report formats contain disk usage, directory breakdowns, scan statistics,
and the largest files found. JSON preserves the nested report structure. CSV
uses the columns `section`, `category`, `name`, `path`, `size_bytes`, and
`value` so the same information can be filtered and sorted in spreadsheet
software. CSV files are UTF-8 with a byte-order mark for compatibility with
Microsoft Excel.

Reports are ignored by Git because they may reveal private local paths and filenames.

## Notes

- Run the script from a normal user account. Protected folders that cannot be read are counted as errors and skipped.
- Reparse points and directory junctions are skipped to prevent loops and duplicated scans.
- Windows system folders may contain hard links, so their logical file totals can be higher than their physical disk usage.
- Do not manually delete `pagefile.sys`, `hiberfil.sys`, or files inside the Windows directory based only on the report.
