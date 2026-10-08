# Windows Storage Audit

A read-only Python utility that scans a Windows drive or directory and creates a JSON report of:

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

Limit the scan to five minutes:

```bat
python storage_scan.py --time-limit 300
```

## Output

The JSON report contains disk usage, directory breakdowns, scan statistics, and the largest files found. Reports are ignored by Git because they may reveal private local paths and filenames.

## Notes

- Run the script from a normal user account. Protected folders that cannot be read are counted as errors and skipped.
- Reparse points and directory junctions are skipped to prevent loops and duplicated scans.
- Windows system folders may contain hard links, so their logical file totals can be higher than their physical disk usage.
- Do not manually delete `pagefile.sys`, `hiberfil.sys`, or files inside the Windows directory based only on the report.
